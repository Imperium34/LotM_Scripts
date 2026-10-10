#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sozluk_ara.py -- sozlukte terim arar (Turkce / Ingilizce / Cince).

UST DUZEY SORU: "Bu terim icin NE KARAR VERDIM?"

Dort "denetim/arama" betigi var ve dorderi de farkli seye bakiyor --
karistirilmasinlar:
    sozluk_ara.py       sozluk.yml'e bakar               -- ne karar verdim?
    kapi_denetle.py      KAYNAK (EN) metne bakar          -- nerede ilk geciyor?
    ceviri_denetle.py    YAYIMLANMIS metne bakar (hizali) -- ne yayimladim, tutarli mi?
    yayim_denetle.py     YAYIMLANMIS (TR) metne bakar     -- yayimlanan GUVENLI mi?

Artik YAML'i kendisi ayristirmiyor; lotm.sozluk_yukle() kullaniyor. Bu
sayede 'mertebeler' icindeki "Turkce (English)" gomulu ciftler, arama_adi,
cevirmen_notu ve yeni 'cince' alani otomatik olarak gelir.

words.md artik lotm.kelimeler_yukle ile okunur; ayni maddeler
ceviri_denetle ve toplu_denetle'ye de girer.

Kullanim:
    sozluk_ara.py <sorgu>
    sozluk_ara.py --notes <sorgu>    # cevirmen notlarini da yaz
    sozluk_ara.py --eksik <sorgu>    # yalnizca Cincesi girilmemisler
"""

import sys
from pathlib import Path

import lotm

def kelimeler_yukle(yol=None):
    """words.md maddeleri -- artik lotm.kelimeler_yukle (tek ayristirici;
    Cince ve Ingilizce alanlari da cikarir, butun denetleyiciler ayni
    okumayi kullanir)."""
    yol = yol or lotm.KELIMELER
    if not Path(yol).exists():
        print(f"uyari: madde listesi yok: {yol}", file=sys.stderr)
        return []
    return lotm.kelimeler_yukle(yol)


def yaz(t, notlar=False):
    satir = f"  {t.tr}  →  {t.en or '-'}"
    if t.zh:
        satir += f"  ({t.zh})"
    satir += f"   [{t.yer}]"
    print(satir)
    if t.eski_karsiliklar:
        print(f"    eski karsiliklar: {', '.join(t.eski_karsiliklar)}")
    if t.bolum_siniri:
        print(f"    bolum siniri: {t.bolum_siniri}")
    if notlar and t.cevirmen_notu:
        print(f"    not: {t.cevirmen_notu}")


def main():
    args = sys.argv[1:]
    notlar = "--notes" in args
    eksik = "--eksik" in args
    for bayrak in ("--notes", "--eksik"):
        while bayrak in args:
            args.remove(bayrak)

    if not args:
        print("kullanim: sozluk_ara.py [--notes] [--eksik] <sorgu>",
              file=sys.stderr)
        sys.exit(1)

    sorgu = " ".join(args)

    sozluk = lotm.sozluk_yukle()
    sozluk.terimler.extend(kelimeler_yukle())

    sonuc = sozluk.ara(sorgu)
    if eksik:
        sonuc = [t for t in sonuc if not t.zh]

    if not sonuc:
        print(f"'{sorgu}' icin eslesme yok.")
        return

    print(f"'{sorgu}' icin {len(sonuc)} eslesme:\n")
    for t in sonuc:
        yaz(t, notlar)
        print()


if __name__ == "__main__":
    main()
