# -*- coding: utf-8 -*-
"""
kapi_denetle.tara -- hiz icin eklenen alt dize on kontrollerinin davranisi
degistirmedigini sinar (ESNEK tur katlamasi, cins isim sayaci).
"""

import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kapi_denetle as K  # noqa: E402


def _bolum(no, metin):
    return SimpleNamespace(no=no, metin=metin, kaynak=f"{no:04d}.md")


def _terim(*adaylar):
    return {"tur": "girdi", "yol": "", "yol_en": None, "kategori": "x",
            "seviye": None, "kardesler": [], "mevcut_bolum": None,
            "adaylar": list(adaylar)}


def test_esnek_katman_buyuk_harf():
    sonuc = K.tara({"nh": _terim("Night Hawk")},
                   [_bolum(2, "Nothing."), _bolum(5, "the NIGHT HAWK came."),
                    _bolum(9, "night hawk")])
    s = sonuc["nh"]
    assert s["en_iyi"] == K.ESNEK
    assert s["kanit_bolum"] == 5 and s["eslesen"] == "Night Hawk"


def test_esnek_tur_ozel_harflerle_duz_regex_ile_ayni():
    # i/I/dotless-i/dotted-I, s/long-s, k/Kelvin: re.IGNORECASE hepsini esler.
    metinler = ["xx İNK yy", "KELVİN", "ſnow", "King",
                "plain nothing", "kıng"]
    for aday in ["ink", "Kelvin", "snow", "King", "kIng", "KING", "ink s"]:
        bolumler = [_bolum(i + 1, m) for i, m in enumerate(metinler)]
        beklenen = None
        for no, m in enumerate(metinler, 1):
            mm = re.search(r"(?<!\w)" + re.escape(aday) + r"(?!\w)", m,
                           re.IGNORECASE)
            if mm:
                beklenen = (no, K.baglam(m, mm.start(), len(aday)))
                break
        s = K.tara({"t": _terim(aday)}, bolumler)["t"]
        if beklenen is None:
            assert s["en_iyi"] == K.YOK, aday
        else:
            assert s["en_iyi"] == K.ESNEK, aday
            assert (s["kanit_bolum"], s["baglam"]) == beklenen, aday


def test_ascii_disi_aday_regex_ile_aranir():
    s = K.tara({"t": _terim("Çağrı")},
               [_bolum(1, "x"), _bolum(3, "çağrı geldi")])["t"]
    assert s["en_iyi"] == K.ESNEK and s["kanit_bolum"] == 3


def test_kucuk_harf_sayaci_ayni_yerde_durur():
    # her bolumde 2 kucuk 'hawk'; 3. bolumde n=6 > 5 olur ve durur.
    # Araya 'hawk' icermeyen bolum girse de sayi ayni kalmali.
    bolumler = [_bolum(1, "hawk hawk"), _bolum(2, "none"),
                _bolum(3, "hawk hawk"), _bolum(4, "hawk hawk"),
                _bolum(5, "hawk hawk hawk")]
    s = K.tara({"h": _terim("Hawk")}, bolumler)["h"]
    assert s["kucuk_harf"] == 6
    assert K.tara({"h": _terim("Hawk")}, bolumler[:3])["h"]["kucuk_harf"] == 4
