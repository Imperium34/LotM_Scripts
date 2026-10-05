# -*- coding: utf-8 -*-
"""
ceviri_denetle -- Cince sorguda daha uzun terimlerin haric tutulmasi.

Cince'de kelime siniri yok: 灵体 araninca 星灵体 (Astral Projection) ve
灵体之线 da bulunuyordu. 灵体 taramasinin 162 ESLESMEYEN'inin buyuk kismi
"Astral Projection" cumleleriydi.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ceviri_denetle as C  # noqa: E402

BILESIK = ["星灵体", "灵体之线"]


def desen():
    return C.desen_kur_kaynak("灵体", "zh", False, haric=BILESIK)


def test_bilesigin_icindeki_gecis_sayilmaz():
    assert not desen().search("你的星灵体在灵界游荡")
    assert not desen().search("他看见了灵体之线")


def test_tek_basina_gecis_sayilir():
    assert desen().search("直接看到一些灵体，鬼魂和怨灵")
    assert len(desen().findall("星灵体和灵体，还有灵体之线")) == 1


def test_isaretleme_bilesigi_atlar():
    assert desen().sub(lambda m: f"«{m.group(0)}»", "星灵体与灵体") == "星灵体与«灵体»"


def test_sozlukten_turetme_uzundan_kisaya():
    sozluk = ("灵体", "星灵体", "灵体之线", "精神体", "星灵体之线")
    assert C.zh_bilesikleri("灵体", sozluk) == ["星灵体之线", "灵体之线", "星灵体"]
    assert C.zh_bilesikleri("精神体", sozluk) == []


def test_haric_ilgisiz_bilesigi_yok_sayar():
    # sorguyu icermeyen bir --haric degeri desene girmez
    d = C.desen_kur_kaynak("精神体", "zh", False, haric=["星灵体"])
    assert d.search("最核心叫精神体")
