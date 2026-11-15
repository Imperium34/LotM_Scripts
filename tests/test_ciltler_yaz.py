# -*- coding: utf-8 -*-
"""ciltler_yaz.py -- _data/ciltler.yml uretimi ve LOTM_KOK'a uyum."""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lotm  # noqa: E402

BETIK = Path(__file__).resolve().parent.parent / "ciltler_yaz.py"


def _calistir(kok, *arg):
    # HEDEF modul yuklenirken lotm.SITE'tan hesaplanir; LOTM_KOK'un etkisini
    # gercekten sinamak icin ayri bir surecte, baska bir cwd'den calistirilir.
    env = {**os.environ, "LOTM_KOK": str(kok)}
    return subprocess.run([sys.executable, str(BETIK), *arg], env=env,
                          cwd=str(kok), capture_output=True, text=True)


def _hedef(depo):
    return depo / "Imperium34.github.io/_data/ciltler.yml"


def test_denetle_dosya_yoksa_1(depo):
    s = _calistir(depo, "--denetle")
    assert s.returncode == 1
    assert "GERİDE" in s.stdout
    assert not _hedef(depo).exists()


def test_yaz_sonra_denetle_0(depo):
    assert _calistir(depo).returncode == 0
    assert _hedef(depo).exists()
    s = _calistir(depo, "--denetle")
    assert s.returncode == 0
    assert "güncel" in s.stdout


def test_denetle_farkli_icerikte_1_ve_dokunmaz(depo):
    _hedef(depo).write_text("- numara: 1\n", encoding="utf-8")
    assert _calistir(depo, "--denetle").returncode == 1
    assert _hedef(depo).read_text(encoding="utf-8") == "- numara: 1\n"


def test_yazilan_ciltler_lotm_ciltleri_arti_yan_hikaye(depo):
    import ciltler_yaz
    _calistir(depo)
    metin = _hedef(depo).read_text(encoding="utf-8")
    assert metin == ciltler_yaz.metin()
    satirlar = metin.splitlines()
    numaralar = [int(x.split(":")[1]) for x in satirlar if x.startswith("- numara:")]
    assert numaralar == [c[0] for c in lotm.CILTLER] + [0]
    assert f"  ilk: {lotm.ANA_HIKAYE_SONU + 1}" in satirlar
    assert f"  son: {lotm.SON_BOLUM}" in satirlar
    for numara, _ad, ilk, son in lotm.CILTLER:
        i = satirlar.index(f"- numara: {numara}")
        assert satirlar[i + 2:i + 4] == [f"  ilk: {ilk}", f"  son: {son}"]


def test_hedef_LOTM_KOK_u_izler(depo, tmp_path_factory):
    baska = tmp_path_factory.mktemp("baska")
    (baska / "Imperium34.github.io/_data").mkdir(parents=True)
    _calistir(depo)
    # depo'da yazili, baska'da yok: --denetle her birinin KENDI kokune bakar
    assert _calistir(depo, "--denetle").returncode == 0
    assert _calistir(baska, "--denetle").returncode == 1
    assert not _hedef(baska).exists()
