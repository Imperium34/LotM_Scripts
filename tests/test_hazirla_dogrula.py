# -*- coding: utf-8 -*-
"""hazirla_dogrula.py -- dokumu yayimlanmis Turkceye karsi sinarken gurultu."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hazirla_dogrula as D  # noqa: E402
import lotm  # noqa: E402


def _t(tr, kategori="words.md › Objects", **kw):
    return lotm.Terim(tr=tr, kategori=kategori, **kw)


def _gecisler(t, metin, uzunlar=()):
    desen = {id(x): D.desenler(x, set()) for x in [t, *uzunlar]}
    kapsam = [m.span() for u in uzunlar for _b, d in desen[id(u)] for m in d.finditer(metin)]
    return [m.group() for m in D.gecisler(t, desen, metin, kapsam)]


def test_uzun_terimin_icindeki_gecis_sayilmaz():
    # "Sezar" ⊂ "Sezar Limanı": kaçan sayılıyordu.
    sezar, liman = _t("Sezar", kategori="words.md › Key"), _t("Sezar Limanı")
    assert _gecisler(sezar, "Yonca, Sezar Limanı'ndan demir aldı.", [liman]) == []
    assert _gecisler(sezar, "Sezar'ın unvanı, İmparator Sezar.", [liman]) == ["Sezar"]


def test_kisa_bicim_ve_cumle_basi_gurultudur():
    # "iş" (tevdi etmek / iş) her bölümde; "Kadı" (dört harf) "Kadının"da.
    tevdi = _t("tevdi etmek", arama_adi=["iş"])
    assert _gecisler(tevdi, "Türlü türlü işleri var.") == []
    kadi = lotm.Terim(tr="Kadı", kategori="Arabulucu Yolu", yol="Arabulucu Yolu", seviye=6)
    assert _gecisler(kadi, "O bir Kadı'ydı.") == []
    # Cumle basi: buyuk harf orada her kelimenindir.
    gemici = lotm.Terim(tr="Gemici", kategori="Denizci Yolu", yol="Denizci Yolu", seviye=7)
    assert _gecisler(gemici, "Gemicinin elleri titriyordu.") == []
    assert _gecisler(gemici, "Artık bir Gemici'ydi.") == ["Gemici'ydi"]
