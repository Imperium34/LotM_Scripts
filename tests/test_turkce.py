# -*- coding: utf-8 -*-
"""
Turkce cekim eki deseni (lotm.desen_kur).

denetci2.py'nin docstring'i v1'in neden 146 bulgunun 141'ini yanlis
uretttigini anlatiyor: serbest "\\w{0,12}" eki. Asagidaki vakalar o
docstring'de ADI GECEN vakalar -- prose olarak yazilmis regresyon testleri.
"""

import pytest


# Eslesmeli: gercek terim, gercek cekim eki
ESLESMELI = [
    ("Kâhin", "Kâhin'in sözü", "Kâhin'in"),
    ("Kâhin", "Kâhin balkondan izliyordu", "Kâhin"),
    ("Yol", "Yolda yürüdü", "Yolda"),
    ("Ay", "Ayın ışığı", "Ayın"),
    ("Avcı", "Gizem Avcısı geldi", "Avcısı"),
    ("Gizem Avcısı", "Gizem Avcısı'nı gördü", "Gizem Avcısı'nı"),
    ("Çırak", "Görücü Yolu'nun bir Çırağı", "Çırağı"),   # k -> ğ yumusamasi
    ("Sıradışı", "bir Sıradışı'nın ne olduğu", "Sıradışı'nın"),
    ("Haz", "başkalarına Haz getirirdi", "Haz"),
]

# Eslesmemeli: siradan Turkce kelime ya da kirpik eslesme
ESLESMEMELI = [
    ("Haz", "Haziran ayında"),          # kirpik: Haz|iran
    ("Haz", "hazine bulundu"),          # kucuk harf -> ozel isim degil
    ("Haz", "Hazır mısın"),
    ("Yol", "Yolsuzluk vardı"),
    ("Yol", "yolu takip etti"),
    ("Ay", "Ayrıca geldi"),
    ("San", "Sanat eseri"),
    ("San", "Sanki öyle"),
    ("Ana", "Anadolu'da yaşadı"),
    ("Aşkın", "Bir yılı aşkın süre"),
    ("Zanaatkâr", "Zanaatkârlık zor bir iştir"),
    ("Maraz", "marazi bir hâl"),
]


@pytest.mark.parametrize("terim,cumle,beklenen", ESLESMELI)
def test_gercek_cekim_eslesir(terim, cumle, beklenen):
    import lotm
    m = lotm.desen_kur(terim).search(cumle)
    assert m is not None, f"{terim!r} {cumle!r} icinde bulunamadi"
    assert m.group(0) == beklenen


@pytest.mark.parametrize("terim,cumle", ESLESMEMELI)
def test_siradan_kelime_eslesmez(terim, cumle):
    import lotm
    assert lotm.desen_kur(terim).search(cumle) is None, \
        f"{terim!r} yanlis yere {cumle!r} icinde eslesti"


def test_harf_duyarliligi_varsayilan_acik():
    """
    Mertebe adlari ozel isim; cakismalari kucuk harfli. Varsayilanin
    degismesi 146 bulguya geri donus demek.
    """
    import lotm
    assert lotm.desen_kur("Haz").search("hazine") is None
    assert lotm.desen_kur("Haz", harf_duyarli=False).search("hazine") is not None


def test_cumle_basi_buyuk_harf_bilinen_bosluk():
    """
    BILINEN SINIR: cumle basindaki 'Hazine' hâlâ 'Haz' ile eslesir.
    Ek deseni bunu ayirt edemez -- ayrimi denetci2.guven_ver yapar
    (--cumle-ici-yuksek). Test bu boslugu BELGELER; davranis degisirse
    kasitli mi diye bakilsin diye burada.
    """
    import lotm
    assert lotm.desen_kur("Haz").search("Hazine kapısı açıldı") is not None


def test_cok_kelimeli_terim_arada_ek_almaz():
    """Yalnizca SON kelime cekim eki alabilir."""
    import lotm
    d = lotm.desen_kur("Gizem Avcısı")
    assert d.search("Gizemi Avcısı") is None
    assert d.search("Gizem Avcısına") is not None
