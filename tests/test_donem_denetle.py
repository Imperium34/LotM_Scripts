# -*- coding: utf-8 -*-
"""donem_denetle.py -- cagdas sozcuk adaylari: ic ses, dondurulmus satir, kisa kok."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import donem_denetle as D  # noqa: E402

KURAL = {"alinti": ["detay", "panik"], "agiz": ["baya", "olay yeri", "falan"],
         "istisna": ["bayağı", "falanca"], "ozdes": {"durum": "vaziyet"}, "ozdes_istisna": []}

METIN = ("---\ntitle: x\n---\n\n"
         "Klein detayı gördü. _Bu detay da ne, panik yok._\n\n"
         "\"Bir şey muhakkak, falan.\" dedi.\n\n"
         "Olay yerine gitti, baya yoruldu; bayağı da bayattı, falanca da.\n\n"
         "Durum buydu. Durumu sordu; vaziyet aynıydı.")


def test_ic_ses_ve_dondurulmus_atlanir():
    out = D.tara(METIN, KURAL, donmus=["Bir şey muhakkak, falan"])
    assert [(x["p"], x["aile"], x["sozcuk"]) for x in out] == [
        (1, "D.1", "detayı"), (3, "D.2", "Olay yerine"), (3, "D.2", "baya")]
    assert out[0]["cumle"] == "Klein detayı gördü."


def test_kisa_kok_yalniz_ekle():
    # "baya" bayat'i ve bayağı'yi saymaz; "bayası" sayilir.
    d = D.desen(["baya"], ["bayağı"])
    assert [m.group() for m in d.finditer("bayat bayağı baya bayası")] == ["baya", "bayası"]


def test_ozdes_sayim():
    assert D.ozdes_sayim(METIN, KURAL) == [("durum", 2, "vaziyet", 1)]


def test_bolum_listesi():
    assert D.bolum_listesi("3,5-6") == [3, 5, 6]
