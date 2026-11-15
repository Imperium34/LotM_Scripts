# -*- coding: utf-8 -*-
"""
sapka.py -- eşadlısı olmayan nisbet, sözlük koruması, keşif.
"""

import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
for yol in (KOK, KOK / "lint"):
    sys.path.insert(0, str(yol))

import sapka  # noqa: E402


def test_ruhani_buyuk_harfle_de_cevrilir_turetilmis_kelimeye_dokunmaz(tmp_path):
    f = tmp_path / "32.md"
    f.write_text(
        "Ruhani Âlem'de ruhani varlıklar; ruhaniyet ayrı bir kelime.", encoding="utf-8"
    )
    sapka.uygula(f, sapka.NISBET_GUVENLI)
    assert f.read_text(encoding="utf-8") == (
        "Ruhanî Âlem'de ruhanî varlıklar; ruhaniyet ayrı bir kelime."
    )


def test_kayit_grubu_hedefsiz_kalmaz():
    assert sapka.bicimler("lazım") == [("lazım", "lâzım"), ("Lazım", "Lâzım")]


def _yazimlar(tmp_path, yml="", md=None):
    yol = tmp_path / "sozluk.yml"
    yol.write_text(yml, encoding="utf-8")
    kel = None
    if md is not None:
        kel = tmp_path / "words.md"
        kel.write_text(md, encoding="utf-8")
    return sapka.sozluk_yazimlari(sapka.sozluk_adlari(yol, kel))


def test_sozluk_kelimenin_yonunu_belirler(tmp_path):
    pytest.importorskip("yaml")
    y = _yazimlar(
        tmp_path,
        "- terim: Ruhani Âlem\n- terim: Esrarî Müşahede\n"
        "- terim: Ebedi Gece Tanrıçası\n- terim: Semavi Muazzez\n",
    )
    ileri, geri, celisen = sapka.sozluge_gore(sapka.NISBET_GUVENLI, y)
    assert {"esrari", "mizahi", "asli"} <= set(ileri)  # sozlukte yok ya da sapkali
    assert geri == {"ruhanî": "ruhani", "ebedî": "ebedi", "semavî": "semavi"}
    assert celisen == {}


def test_sozlukte_iki_yazim_varsa_dokunulmaz(tmp_path):
    pytest.importorskip("yaml")
    y = _yazimlar(tmp_path, "- terim: Ruhani Âlem\n- terim: Ruhanî Beden\n")
    _i, _g, celisen = sapka.sozluge_gore(sapka.NISBET_GUVENLI, y)
    assert "ruhani" in celisen


def test_words_md_ve_parantez_ici_de_sozluktur(tmp_path):
    pytest.importorskip("yaml")
    y = _yazimlar(
        tmp_path,
        "- terim: Kadim Şeytaniçe (Tam Tazim İsmi)\n",
        md="- **asli üye** — formal member (正式队员)\n",
    )
    assert "asli" in y and "ismi" in y
    _i, geri, _c = sapka.sozluge_gore(sapka.NISBET_GUVENLI, y)
    assert geri["aslî"] == "asli"


def test_tersine_uygulama_sozluk_adini_duzeltir(tmp_path):
    f = tmp_path / "40.md"
    f.write_text("Semavî Muazzez'in ebedî uykusu; ebedi gece.", encoding="utf-8")
    sapka.uygula(f, {"semavî": "semavi", "ebedî": "ebedi"})
    assert (
        f.read_text(encoding="utf-8") == "Semavi Muazzez'in ebedi uykusu; ebedi gece."
    )


def test_kesif_iki_yazimli_kelimeyi_bulur():
    ciftler = sapka.kesfet(
        {
            "32.md": "Ruhanî Âlem'de ruhanî varlıklar.",
            "33.md": "biçimsiz ruhani varlıklar; hâlâ, hala da orada.",
            "34.md": "tek yazım: kâhin",
        }
    )
    by = {c[0]: c for c in ciftler}
    assert by["ruhani"][1:5] == ("ruhanî", 1, 2, 2)
    assert by["ruhani"][5] is True  # artik listede
    assert by["hala"][5] is True  # esadli grubunda
    assert "kahin" not in by  # tek yazimli kelime cift degil


YML = """\
# --- İlahlar ---
- terim: Ebedi Gece Tanrıçası (Sermedi Zulmet)
  ingilizce: Evernight Goddess
  arama_adi: [ruhani varlık, Ruhani Beden]
  eski_karsiliklar:
  - ruhani eski
  aciklama: >-
    ebedi bir tanrıça; ruhani âlem.

  mertebeler:
  - isim: Semavi Muazzez
    seviye: 1
- terim: Kâhin
  arama_adi:
  - ruhani biçim
  cevirmen_notu: ebedi
"""


def test_gocu_yalniz_ad_alanlarini_degistirir():
    yeni, degisen = sapka.sozluk_yml_gocu(YML, sapka.GUVENLI)
    assert "- terim: Ebedî Gece Tanrıçası (Sermedi Zulmet)" in yeni
    assert "  arama_adi: [ruhanî varlık, Ruhanî Beden]" in yeni
    assert "  - isim: Semavî Muazzez" in yeni
    assert "  - ruhanî biçim" in yeni  # blok liste, offset 0
    assert "  - ruhani eski" in yeni  # eski_karsiliklar dokunulmaz
    assert "    ebedi bir tanrıça; ruhani âlem." in yeni  # duzyazi kapali
    assert "  cevirmen_notu: ebedi" in yeni
    assert (
        "# --- İlahlar ---" in yeni and "\n\n  mertebeler:" in yeni
    )  # yorum, bos satir
    assert len(degisen) == 4


def test_gocu_duzyazi_ile_aciklamayi_da_tasir_ama_eskiyi_degil():
    yeni, _ = sapka.sozluk_yml_gocu(YML, sapka.GUVENLI, duzyazi=True)
    assert "    ebedî bir tanrıça; ruhanî âlem." in yeni
    assert "  cevirmen_notu: ebedî" in yeni
    assert "  - ruhani eski" in yeni


def test_gocu_yapisi_denetlenir():
    yaml = pytest.importorskip("yaml")
    yeni, _ = sapka.sozluk_yml_gocu(YML, sapka.GUVENLI)
    assert (
        sapka._yapi_farki(yaml.safe_load(YML), yaml.safe_load(yeni), sapka.AD_ALANLARI)
        == []
    )
    # izinsiz bir alan degisirse yakalanir
    bozuk = YML.replace("ingilizce: Evernight Goddess", "ingilizce: Evernight Godess")
    assert sapka._yapi_farki(
        yaml.safe_load(YML), yaml.safe_load(bozuk), sapka.AD_ALANLARI
    )


def test_gocu_yazar_ve_words_md_yi_de_tasir(tmp_path):
    pytest.importorskip("yaml")
    yml, md = tmp_path / "sozluk.yml", tmp_path / "words.md"
    yml.write_text(YML, encoding="utf-8")
    md.write_text("- **asli üye** — formal member (正式队员)\n", encoding="utf-8")
    assert sapka.sozluk_gocu(yml, md, sapka.GUVENLI, uygula_=True, duzyazi=False) == 0
    assert "Ebedî Gece" in yml.read_text(encoding="utf-8")
    assert (
        md.read_text(encoding="utf-8") == "- **aslî üye** — formal member (正式队员)\n"
    )
    # gocten sonra sozluk yonu ileri: tersine donecek kelime kalmaz
    y = sapka.sozluk_yazimlari(sapka.sozluk_adlari(yml, md))
    _i, geri, celisen = sapka.sozluge_gore(sapka.NISBET_GUVENLI, y)
    assert geri == {} and celisen == {}


def test_elle_tabani_yalniz_yeni_gecisi_gosterir(tmp_path, capsys):
    f = tmp_path / "1.md"
    f.write_text("Bir adet elma.\n\nSelam verdi.\n", encoding="utf-8")
    taban = tmp_path / "sapka-taban.tsv"
    assert sapka.taban_yaz(taban, {"1.md": f.read_text("utf-8")}) == 2
    f.write_text(
        "Bir adet elma.\n\nSelam verdi.\n\nYeni bir adet daha.\n", encoding="utf-8"
    )
    bulgu = sapka.tara({"1.md": f.read_text("utf-8")}, sapka.elle_listesi())
    kalan, bastirilan = sapka.tabandan_suz(bulgu, sapka.taban_oku(taban))
    assert bastirilan == 2
    assert [k[4].strip() for v in kalan.values() for k in v] == ["Yeni bir adet daha."]
