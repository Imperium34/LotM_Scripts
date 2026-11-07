# -*- coding: utf-8 -*-
"""lotm.py ortak yardimcilari (yedek klasoru, bolum araligi, cekirdek istem)
ve sonra.py'nin donem varsayilani, otomatik paralel sayisi, yedek_al."""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lotm  # noqa: E402
import sonra as S  # noqa: E402


def test_bolum_listesi_tek_aralik_liste_ve_bozuk():
    assert lotm.bolum_listesi("61") == [61]
    assert lotm.bolum_listesi(7) == [7]
    assert lotm.bolum_listesi("8-10, 9,12") == [8, 9, 10, 12]
    for bozuk in ("", "72-70", "6x", "61-", "a-b"):
        with pytest.raises(ValueError):
            lotm.bolum_listesi(bozuk)
    # Eski ad ayni islevi gosterir: davranis tek yerde (lotm.py).
    assert S.bolum_listesi.__module__ == "lotm"


def test_yedek_klasoru_tarih_etiket_ve_ortam(tmp_path, monkeypatch):
    monkeypatch.setenv("LOTM_YEDEK", str(tmp_path))
    y = lotm.yedek_klasoru("sonra-Ch_7", zaman=0)
    assert y.parent.parent == tmp_path
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", y.parent.name)
    assert re.fullmatch(r"sonra-Ch_7-\d{6}", y.name)
    assert not y.exists()  # olusturmaz


def test_cekirdek_istem_en_yeni_surum_old_klasoru_ve_oneri_atlanir(tmp_path, monkeypatch):
    for ad in ("lotm_system_prompt_v5.4.md", "lotm_system_prompt_v5.10.md",
               "lotm_system_prompt_v5_skill.md", "lotm_system_prompt_v6_oneri.md"):
        (tmp_path / ad).write_text("x", encoding="utf-8")
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "lotm_system_prompt_v9.md").write_text("eski", encoding="utf-8")
    monkeypatch.setattr(lotm, "ISTEMLER", tmp_path)
    monkeypatch.delenv("LOTM_CEKIRDEK", raising=False)
    assert lotm.cekirdek_istem().name == "lotm_system_prompt_v5.10.md"
    monkeypatch.setenv("LOTM_CEKIRDEK", str(tmp_path / "secilen.md"))
    assert lotm.cekirdek_istem().name == "secilen.md"


def test_donem_varsayilan_acik_kapatilabilir():
    assert S.donem_acik(False, False, None, ortam=True)
    assert not S.donem_acik(False, False, None, ortam=False)       # LOTM_DONEM=0
    assert S.donem_acik(True, False, None, ortam=False)            # --donem acar
    assert S.donem_acik(False, False, ["donem"], ortam=False)      # --otomatik donem
    assert not S.donem_acik(True, True, ["donem"], ortam=True)     # --donem-yok ezer


def test_paralel_sayisi(monkeypatch):
    monkeypatch.delenv("LOTM_PARALEL_UST", raising=False)
    assert S.paralel_sayisi("oto", 1) == (1, True)
    assert S.paralel_sayisi("oto", 2) == (2, True)
    assert S.paralel_sayisi("oto", 52) == (3, True)
    monkeypatch.setenv("LOTM_PARALEL_UST", "5")
    assert S.paralel_sayisi("auto", 52) == (5, True)
    assert S.paralel_sayisi("1", 52) == (1, False)
    assert S.paralel_sayisi(4, 2) == (4, False)
    with pytest.raises(ValueError):
        S.paralel_sayisi("cok", 3)


def test_gunluk_kota_ve_gecici_hiz_siniri_ayrilir(tmp_path):
    g = tmp_path / "kosu.log"
    msj = "You've hit your session limit · resets 6:30am (Europe/Istanbul)"
    g.write_text(f"  claude: 5_birlestir_girdi.md -> 5_birlestir_cikti.md ...\n"
                 f"  HATA (cikis 1): {msj}\n  KOTA claude: {msj}\n", encoding="utf-8")
    assert S.gunluk_sorunu(g) == ({"claude": msj}, False)
    g.write_text("  HATA (cikis 1): API Error: 429 Too Many Requests\n", encoding="utf-8")
    assert S.gunluk_sorunu(g) == ({}, True)
    g.write_text("okuma: rate limit kurali hakkinda bir not\n  HATA (cikis 1): baska bir sey\n",
                 encoding="utf-8")
    assert S.gunluk_sorunu(g) == ({}, False)
    assert S.gunluk_sorunu(tmp_path / "yok.log") == ({}, False)
    assert "6:30am" in S.kota_notu({"claude": msj})


def test_kota_dolunca_o_motorun_kalan_cagrilari_atlanir(tmp_path, monkeypatch):
    sahte = tmp_path / "sahte.sh"
    sahte.write_text("#!/bin/sh\ncat >/dev/null\necho \"You've hit your session limit · resets 6:30am\" >&2\nexit 1\n")
    sahte.chmod(0o755)
    monkeypatch.setenv("LOTM_CLAUDE", str(sahte))
    monkeypatch.setattr(S, "KOTA_DOLU", {})
    girdi = tmp_path / "1_okuma_girdi.md"
    girdi.write_text("girdi", encoding="utf-8")
    assert not S.yurut(girdi, tmp_path / "1_okuma_cikti.md", None, 30)
    assert "session limit" in S.KOTA_DOLU["claude"]
    sahte.write_text("#!/bin/sh\ncat >/dev/null\necho tamam\n")  # artik basarirdi, ama denenmez
    assert not S.yurut(girdi, tmp_path / "2_cikti.md", None, 30)
    assert not (tmp_path / "2_cikti.md").exists()


def test_yedek_al_kopyalar_yoksa_atlar(tmp_path, monkeypatch):
    monkeypatch.setenv("LOTM_YEDEK", str(tmp_path / "yedek"))
    a = tmp_path / "0007.md"
    a.write_text("asil", encoding="utf-8")
    assert S.yedek_al("sonra-Ch_7", tmp_path / "yok.md") is None
    hedef = S.yedek_al("sonra-Ch_7", a, tmp_path / "yok.md")
    assert (hedef / "0007.md").read_text(encoding="utf-8") == "asil"
    assert hedef.is_relative_to(tmp_path / "yedek")


def test_cevir_her_zaman_sistem_istemiyle(tmp_path):
    import cevir
    k = cevir.claude_komutu(None, tmp_path / "cekirdek.md")
    i = k.index("--system-prompt-file")
    assert k[i + 1] == str(tmp_path / "cekirdek.md") and k[k.index("--tools") + 1] == ""
    assert cevir.yaz_degisirse.__module__ == "sonra"


def test_yayim_tarihi_ve_terim_tablolari():
    from datetime import datetime, timezone
    simdi = datetime(2026, 11, 7, 22, 0, tzinfo=timezone.utc)
    fm = '---\nlayout: post\ntitle: "x"\ndate: {}\n---\n\nmetin\n'
    assert S.yayim_tarihi_gecti(fm.format("2026-07-07 20:00:00 +0300"), simdi)
    assert not S.yayim_tarihi_gecti(fm.format("2026-12-14 20:00:00 +0300"), simdi)
    assert S.yayim_tarihi_gecti(fm.format("2026-11-07"), simdi)
    assert not S.yayim_tarihi_gecti("---\ntitle: x\n---\n\nmetin\n", simdi)  # tarihsiz: taslak
    sablon = ("# Ch\n\n## A. TERİMLER\n\n### A.1 Yerleşik\n| kira arabası |\n\n### A.2 Özel adlar\n| Noterlik |\n\n"
              "### A.3 Eklenmeyecek\n- dipnot\n\n## B. DONDURULAN SATIRLAR\n- satır\n\n## C. SES\n- Klein\n")
    s = S.terim_tablolarini_at(sablon)
    assert "kira arabası" not in s and "Noterlik" not in s
    assert "### A.3" in s and "## B. DONDURULAN" in s and "## C. SES" in s


def test_yayimlanmis_bolumde_sablon_kisaltilir(tmp_path, monkeypatch):
    bolumler, sablonlar = tmp_path / "ch", tmp_path / "sch"
    bolumler.mkdir(), sablonlar.mkdir()
    monkeypatch.setattr(S, "BOLUMLER", bolumler)
    monkeypatch.setattr(S, "SABLONLAR", sablonlar)
    monkeypatch.delenv("LOTM_SABLON_TAM", raising=False)
    (sablonlar / "Ch_45.md").write_text("### A.1 T\n| eski terim |\n\n## C. SES\n- ses\n", encoding="utf-8")
    (bolumler / "0045.md").write_text("---\ndate: 2026-01-01 20:00:00 +0300\n---\n\nm\n", encoding="utf-8")
    b = S.Bolum(45, 6000)
    blok = b.sablon_blogu("bolum_sablonu")
    assert b.yayimlandi() and "eski terim" not in blok and "yayımlanmış" in blok and "## C. SES" in blok
    monkeypatch.setenv("LOTM_SABLON_TAM", "1")
    assert "eski terim" in b.sablon_blogu("bolum_sablonu")
    monkeypatch.delenv("LOTM_SABLON_TAM")
    (bolumler / "0045.md").write_text("---\ndate: 2099-01-01 20:00:00 +0300\n---\n\nm\n", encoding="utf-8")
    blok = b.sablon_blogu("bolum_sablonu")
    assert "eski terim" in blok and "sözlük ve words.md esastır" in blok


def test_son_adim_okuma_1_6_kendiliginden_uygulanir(tmp_path, monkeypatch):
    import json
    bolumler = tmp_path / "ch"
    bolumler.mkdir()
    asil = "---\ntitle: x\n---\n\nKlein baktı, yine baktı ve uzun uzun baktı.\n\nKapı açıldı.\n"
    (bolumler / "0099.md").write_text(asil, encoding="utf-8")
    for ad, deger in (("BOLUMLER", bolumler), ("RAPOR", tmp_path / "sonra"),
                      ("SABLONLAR", tmp_path / "yok"), ("OTOMATIK", {"okuma 1.6"})):
        monkeypatch.setattr(S, ad, deger)
    monkeypatch.setenv("LOTM_YEDEK", str(tmp_path / "yedek"))
    b = S.Bolum(99, 6000)
    b.klasor.mkdir(parents=True)
    monkeypatch.setattr(S.Bolum, "yeni_terimler", lambda self: [])
    duz = [{"p": 1, "sinif": "KARAR", "kural": "okuma 1.6 tekrar", "kaynak": ["okuma"],
            "eski": "Klein baktı, yine baktı ve uzun uzun baktı.", "yeni": "Klein baktı, yine baktı ve uzun uzun süzdü.", "neden": "Yakın tekrar."},
           {"p": 2, "sinif": "KARAR", "kural": "okuma 1.6 tekrar", "kaynak": ["okuma"],
            "eski": "Kapı açıldı.", "yeni": "Kapı açıldı.", "neden": "Ritim bilinçli olabilir."}]
    (b.klasor / "5_birlestir_cikti.md").write_text(json.dumps({"duzeltmeler": duz, "bilgi": []}), encoding="utf-8")
    sonuc = b.son_adim(kuru=False)
    assert sonuc.startswith("1 kesin duzeltme uygulandi, 1 karar"), sonuc
    assert "uzun uzun süzdü" in (bolumler / "0099.md").read_text(encoding="utf-8")
    inc = (b.klasor / "5_inceleme.md").read_text(encoding="utf-8")
    assert "· otomatik" in inc and "Ritim bilinçli" in inc
    assert list((tmp_path / "yedek").rglob("0099.md"))
