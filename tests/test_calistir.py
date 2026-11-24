# -*- coding: utf-8 -*-
"""
calistir.sh -- gercek betik, bash alt sureciyle, sentetik depoda.

calistir.sh Reports/'u betigin yanina yazar; gercek klasore dokunmamak icin
betik klasoru her test icin tmp_path'e KOPYALANIR (Reports, .git, onbellek,
tests haric). LOTM_RAPOR gibi bir anahtar yetmezdi: Python betiklerinin kendi
varsayilan yazma yerleri de olabilir; kopyada hepsi tmp_path icinde kalir.
'hepsi' ilk adimda pytest calistirir: LOTM_TEST_ATLA=1 ile ozyineleme kesilir.
"""

import os
import re
import shutil
import stat
import subprocess

import pytest
from conftest import BETIKLER, zh_korpus

from test_zincir import dolu_depo as _dolu  # noqa: F401  (fixture)

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash yok")

ADIMLAR = ["test", "kontrol", "takvim", "tarama", "etiket", "denetim", "lint",
           "bicim", "sapka", "toplu", "belgeler", "ciltler", "dogrula"]
ANSI = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture
def depo_tam(_dolu):
    """dolu_depo, ama bolum dosyalari gercek adlandirmayla (0001.md): zincirin
    son_bolum_dosyasi ^[0-9]+\\.md$ arar; bolum-001.md olursa dogrula adimi
    '10#' aritmetik hatasiyla betigin KENDISINI keser (var olan davranis)."""
    for p in (_dolu / "Imperium34.github.io/_chapters").glob("bolum-*.md"):
        p.rename(p.with_name(f"{int(p.stem[6:]):04d}.md"))
    # takvim.yml ve Cince kaynak: yoksa takvim (cikis 2) ve toplu HATA verir;
    # gercek bir kurulumda ikisi de vardir.
    (_dolu / "Imperium34.github.io/_data/takvim.yml").write_text(
        'saat: "20:00:00 +0300"\ndonemler:\n  - {baslangic: 1, gunler: [çarşamba, cumartesi]}\n',
        encoding="utf-8")
    (_dolu / "Source/Lord_of_the_Mysteries_Chinese.txt").write_text(
        zh_korpus([30]), encoding="utf-8")
    return _dolu


@pytest.fixture
def betikler(tmp_path):
    hedef = tmp_path / "betikler"
    shutil.copytree(
        BETIKLER, hedef,
        ignore=shutil.ignore_patterns("Reports", ".git", "__pycache__", ".pytest_cache", "tests"))
    return hedef


def _calistir(betikler, kok, *arg, ortam=None, **kw):
    env = dict(os.environ, LOTM_KOK=str(kok), LOTM_TEST_ATLA="1")
    env.pop("LOTM_HEPSI_KATI", None)
    env.pop("LOTM_KELIMELER", None)
    env.update(ortam or {})
    s = subprocess.run(["bash", str(betikler / "calistir.sh"), *arg],
                       capture_output=True, text=True, env=env, timeout=120, **kw)
    s.cikti = ANSI.sub("", s.stdout)  # sira: stdout; stderr ayri (s.stderr)
    return s


def _tablo(cikti):
    """Ozet satirlari: {ad: (durum, cikis, sure, bulgu)}, sirayla."""
    assert "--- ADIM OZETI ---" in cikti
    govde = cikti.split("--- ADIM OZETI ---")[1].strip().splitlines()
    assert govde[0].split() == ["adim", "durum", "cikis", "sure", "bulgu"]
    satirlar = {}
    for s in govde[1:]:
        p = s.split()
        if len(p) != 5:
            break
        satirlar[p[0]] = tuple(p[1:])
    return satirlar


def test_hepsi_cikis_0_ve_tablo_sirayla(depo_tam, betikler):
    s = _calistir(betikler, depo_tam, "hepsi")
    assert s.returncode == 0, s.cikti[-2000:]
    t = _tablo(s.cikti)
    assert list(t) == ADIMLAR
    for ad, (durum, kod, sure, bulgu) in t.items():
        assert durum in {"tamam", "bulgu", "ATLANDI", "HATA"}, ad
        assert kod.isdigit() and re.fullmatch(r"\d+s", sure), ad
    assert s.cikti.rstrip().endswith("bitti.")
    # baslik satirinin kalani ve renkli "bitti." disindaki satirlar renksiz
    satirlar = s.stdout.split("--- ADIM OZETI ---")[1].splitlines()[1:-1]
    assert len(satirlar) == len(ADIMLAR) + 1
    assert not any("\x1b" in x for x in satirlar)


def test_atlanan_adimlar(depo_tam, betikler):
    shutil.rmtree(depo_tam / "Source")
    t = _tablo(_calistir(betikler, depo_tam, "hepsi").cikti)
    assert t["test"][:2] == ("ATLANDI", "1")  # LOTM_TEST_ATLA
    assert t["tarama"][:2] == ("ATLANDI", "1")  # Source yok
    assert t["etiket"][:2] == ("ATLANDI", "1")  # rapor.tsv yok


def _bulgu_sayisi(betikler, ad):
    dosya = betikler / "Reports/bulgular" / f"{ad}.tsv"
    return len([x for x in dosya.read_text(encoding="utf-8").splitlines() if x])


def test_bulgulu_adim_bulgu_ve_sayi(depo_tam, betikler):
    # TR_BOLUMLER[2]'de ",\" dedi" bicimi var: bicim_denetle HATA bulur (cikis 1).
    s = _calistir(betikler, depo_tam, "hepsi")
    assert s.returncode == 0
    t = _tablo(s.cikti)
    n = _bulgu_sayisi(betikler, "bicim")
    assert n > 0
    assert t["bicim"] == ("bulgu", "1", t["bicim"][2], str(n))
    # Takvim de bulgu bildirir (basliksiz bolumler) ve kendi dosyasini sayar.
    assert t["takvim"][0] == "bulgu"
    assert t["takvim"][3] == str(_bulgu_sayisi(betikler, "takvim"))


def test_temiz_adim_tamam(depo_tam, betikler):
    t = _tablo(_calistir(betikler, depo_tam, "hepsi").cikti)
    assert t["lint"] == ("tamam", "0", t["lint"][2], "0")
    assert t["tarama"][:2] == ("tamam", "0")
    assert t["tarama"][3] == "-"  # bulgu dosyasi yazmayan adim
    assert t["toplu"][0] == "tamam" and t["toplu"][3] == str(_bulgu_sayisi(betikler, "toplu"))


def test_eski_bulgu_dosyasi_sayilmaz(depo_tam, betikler):
    """Adim calismadiysa onceki calistirmanin bulgu dosyasi tabloya girmez."""
    b = betikler / "Reports/bulgular"
    b.mkdir(parents=True)
    (b / "lint.tsv").write_text("a\tb\nc\td\n", encoding="utf-8")
    old = (b / "lint.tsv").stat()
    os.utime(b / "lint.tsv", (old.st_atime - 100, old.st_mtime - 100))
    # lint'in betigini coktur: dosya yazilmaz
    (betikler / "lint/sozluk_lint.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    t = _tablo(_calistir(betikler, depo_tam, "hepsi").cikti)
    assert t["lint"][:2] == ("HATA", "3")
    assert t["lint"][3] == "-"


@pytest.fixture
def python_stub(tmp_path):
    """PATH'in basinda, yalniz kapi_denetle.py'yi coktuguren python3."""
    d = tmp_path / "stub"
    d.mkdir()
    gercek = shutil.which("python3")
    s = d / "python3"
    s.write_text(f'#!/bin/bash\ncase "$*" in *kapi_denetle.py*) exit 7;; esac\nexec "{gercek}" "$@"\n')
    s.chmod(s.stat().st_mode | stat.S_IEXEC)
    return d


def test_kati_degisken_hata_ile_1(depo_tam, betikler, python_stub):
    yol = f"{python_stub}{os.pathsep}{os.environ['PATH']}"
    s = _calistir(betikler, depo_tam, "hepsi", ortam={"PATH": yol})
    assert s.returncode == 0
    assert _tablo(s.cikti)["tarama"][:2] == ("HATA", "7")
    k = _calistir(betikler, depo_tam, "hepsi", ortam={"PATH": yol, "LOTM_HEPSI_KATI": "1"})
    assert k.returncode == 1
    assert _tablo(k.cikti)["tarama"][:2] == ("HATA", "7")


def test_kati_degisken_bulgu_ve_atlandi_icin_1_degil(depo_tam, betikler):
    # varsayilan depoda: test ATLANDI (anahtar), bicim/takvim/kontrol bulgu
    s = _calistir(betikler, depo_tam, "hepsi", ortam={"LOTM_HEPSI_KATI": "1"})
    t = _tablo(s.cikti)
    durumlar = {v[0] for v in t.values()}
    assert {"ATLANDI", "bulgu"} <= durumlar and "HATA" not in durumlar, t
    assert s.returncode == 0


def test_bilinmeyen_komut_kullanimi(depo_tam, betikler):
    s = _calistir(betikler, depo_tam, "yok-boyle-bir-komut")
    assert s.returncode == 1
    for ad in ("kaynak", "kiyas", "sayi"):
        assert f"./calistir.sh {ad}" in s.cikti


def test_bolum_bos_chapters_sessiz_cikis_1(depo, betikler):
    s = _calistir(betikler, depo, "bolum")
    assert s.returncode == 1
    assert s.cikti == "" and s.stderr == ""


def test_kaynak_python_betigine_gider(depo, betikler):
    # kaynak_denetle.py bu kopyada olmayabilir; her halde Python'a ulasilir.
    s = _calistir(betikler, depo, "kaynak")
    if (betikler / "kaynak_denetle.py").exists():
        assert s.returncode in (0, 1, 2)
    else:
        assert s.returncode == 2 and "kaynak_denetle.py" in s.stderr


def test_bolum_gecersiz_numara_reddedilir(depo_tam, betikler):
    s = _calistir(betikler, depo_tam, "bolum", "abc")
    assert s.returncode == 1 and "kullanim:" in s.cikti


def test_kontrol_cokmesi_bulgu_degil_hata_sayilir(depo_tam, betikler, tmp_path):
    d = tmp_path / "stub_k"
    d.mkdir()
    gercek = shutil.which("python3")
    st = d / "python3"
    st.write_text(f'#!/bin/bash\ncase "$*" in *"lotm.py kontrol"*) exit 2;; esac\nexec "{gercek}" "$@"\n')
    st.chmod(st.stat().st_mode | stat.S_IEXEC)
    yol = f"{d}{os.pathsep}{os.environ['PATH']}"
    s = _calistir(betikler, depo_tam, "hepsi", ortam={"PATH": yol, "LOTM_HEPSI_KATI": "1"})
    assert s.returncode == 1
    assert _tablo(s.cikti)["kontrol"][:2] == ("HATA", "2")


def test_dogrula_numarasiz_bolumde_zinciri_kesmez(_dolu, betikler):
    # _dolu'da bolum-001.md var, NNNN.md yok: dogrula ATLANDI demeli, 10# hatasiyla cokmemeli.
    (_dolu / "Imperium34.github.io/_data/takvim.yml").write_text(
        'saat: "20:00:00 +0300"\ndonemler:\n  - {baslangic: 1, gunler: [çarşamba, cumartesi]}\n',
        encoding="utf-8")
    s = _calistir(betikler, _dolu, "hepsi")
    assert s.returncode == 0
    assert _tablo(s.cikti)["dogrula"][:2] == ("ATLANDI", "1")


def test_takvim_ek_argumani_iletir(depo_tam, betikler):
    s = _calistir(betikler, depo_tam, "takvim", "--bolum", "1")
    assert s.returncode in (0, 1)
    assert "fark [takvim]" not in s.cikti  # tek bolum kipinde fark yazilmaz


def test_basarisiz_adim_atlandi_demez(depo_tam, betikler, python_stub):
    yol = f"{python_stub}{os.pathsep}{os.environ['PATH']}"
    s = _calistir(betikler, depo_tam, "hepsi", ortam={"PATH": yol})
    assert "tarama basarisiz" in s.cikti and "tarama atlandi" not in s.cikti


def test_otomatik_zincir_hatasinda_duzeltmeler_baslamaz(depo_tam, betikler, python_stub):
    isaret = betikler / "duzeltme_basladi"
    (betikler / "zincir_oku.py").write_text(
        f"from pathlib import Path\nPath({str(isaret)!r}).touch()\n")
    yol = f"{python_stub}{os.pathsep}{os.environ['PATH']}"
    sonuc = _calistir(betikler, depo_tam, "hepsi", "--otomatik",
                      ortam={"PATH": yol, "LOTM_HEPSI_KATI": "1"})
    assert sonuc.returncode == 1
    assert _tablo(sonuc.cikti)["tarama"][:2] == ("HATA", "7")
    assert not isaret.exists()
