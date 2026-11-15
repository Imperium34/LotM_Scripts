# -*- coding: utf-8 -*-
"""
Hiz icin eklenen ON KONTROLLERIN (duz alt dizge / sozcuk kumesi / kucuk harf)
regex ile ayni sonucu verdigini sinar: ON KONTROL yanlissa regex de eslesmemeli.
"""

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
for yol in (KOK, KOK / "lint"):
    sys.path.insert(0, str(yol))

import sapka  # noqa: E402
import sozluk_lint as SL  # noqa: E402

METINLER = [
    "Bu kâğıt hâlâ _hâlâ_ ve 3hâlâ, hâlâ4 kâğıtlar KÂĞIT Kâğıt.",
    "tabi ki gelmedi; TABİ Kİ, Tabi, ve tabi kimseye. İlk Işık ışık ISIK.",
    "Klein'nın Klein’in Klein'ı xKlein'a Dunn’nın",
    "",
    "İki Ilık ılık",
]


def test_sapka_tara_kaba_kuvvetle_ayni():
    dosyalar = {f"{i}.md": m for i, m in enumerate(METINLER)}
    liste = {**sapka.GUVENLI, **sapka.KAYIT, "kagit": "kâğıt", "hala": "hâlâ"}
    bulgu = sapka.tara(dosyalar, liste)
    beklenen = {}
    for kelime in liste:
        for aranan, yazilacak in sapka.bicimler(kelime, liste[kelime]):
            for ad, metin in sorted(dosyalar.items()):
                for m in sapka.desen(aranan).finditer(metin):
                    beklenen.setdefault(kelime, []).append(
                        (ad, metin.count("\n", 0, m.start()) + 1, aranan, yazilacak))
    assert {k: [x[:4] for x in v] for k, v in bulgu.items()} == beklenen


def test_cevir_onkontrol_regexle_ayni():
    liste = {"kagit": "kâğıt", "hala": "hâlâ", "adet": "âdet"}
    for m in METINLER + ["kagit Kagit KAGIT hala adetler adet."]:
        beklenen, n = m, 0
        for kelime in liste:
            for aranan, yaz in sapka.bicimler(kelime, liste[kelime]):
                beklenen, k = sapka.desen(aranan).subn(yaz, beklenen)
                n += k
        assert sapka._cevir(m, liste) == (beklenen, n)


def test_yasakli_onkontrol_yanlis_negatif_vermez():
    bicimler = ["tabi ki", "Tabi,", "cehliyet", "ışık", "iki", "çığ", "I"]
    for m in METINLER:
        kucuk = SL.kucuk_metin(m)
        for b in bicimler:
            if SL.yasakli_deseni(b).search(m):
                assert SL.yasakli_olabilir(b, kucuk), (b, m)
