# -*- coding: utf-8 -*-
"""
lotm.Terim -- arama_adi (Turkce) ile en_arama_adi (Ingilizce) ayrimi.

Sozlukteki uc arama_adi kullanimi da Turkce: kapi_denetle bu terimlerin
ilk gecisini Ingilizce metinde "El Yazması", "gökkubbe", "şiraze"
arayarak bulmaya calisiyordu.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lotm  # noqa: E402


def test_ingilizce_tarama_turkce_arama_adini_kullanmaz():
    t = lotm.Terim(tr="Antigonus Ailesinin El Yazması", en="Antigonus Family Notebook",
                   en_ham="Antigonus Family Notebook", arama_adi=["El Yazması"])
    adaylar = t.arama_adaylari()
    assert "Antigonus Family Notebook" in adaylar
    assert not any("Yazması" in a for a in adaylar)


def test_en_arama_adi_verilirse_o_kullanilir():
    t = lotm.Terim(tr="Yıldızlı Gökkubbe", en="Cosmos", en_ham="Cosmos",
                   en_arama_adi=["starry sky"])
    assert "starry sky" in t.arama_adaylari()
    assert "Cosmos" not in t.arama_adaylari()


def test_yml_iki_alani_ayri_okur(tmp_path):
    pytest.importorskip("yaml")
    yol = tmp_path / "sozluk.yml"
    yol.write_text(
        "- terim: Şirazesini Yitirmek\n"
        "  ingilizce: Losing Control\n"
        "  kategori: Kavramlar\n"
        "  arama_adi: [şiraze]\n"
        "  en_arama_adi: [lose control]\n",
        encoding="utf-8",
    )
    t, = lotm.sozluk_yukle(yol).terimler
    assert t.arama_adi == ["şiraze"]
    assert t.en_arama_adi == ["lose control"]


def test_tr_bicimleri_terimi_ve_arama_adini_birlestirir():
    t = lotm.Terim(tr="Ruhani Beden", arama_adi=["ruhani varlık", "ruhani beden"])
    # terimin kendisi her zaman ilk ve tek; harf farki ikinci kopya degil
    assert t.tr_bicimleri() == ["Ruhani Beden", "ruhani varlık"]


def test_iki_denetleyici_ayni_bicimleri_kullanir(monkeypatch):
    import ceviri_denetle as C
    import toplu_denetle as TD

    t = lotm.Terim(tr="Antigonus Ailesinin El Yazması", en="Antigonus Family Notebook",
                   kategori="Temel Kavramlar", arama_adi=["El Yazması"],
                   eski_karsiliklar=["defter"])
    monkeypatch.setattr(lotm, "sozluk_yukle", lambda *a, **k: lotm.Sozluk([t], veri={}))
    tek = C.sozlukten_adaylar("Antigonus Family Notebook", "tr")
    (_s, _t, toplu, _d, eski), = TD.sweep_terimleri("en", "tr")[0]
    assert tek == toplu == ["Antigonus Ailesinin El Yazması", "El Yazması", "defter"]
    assert eski == {"defter"}
