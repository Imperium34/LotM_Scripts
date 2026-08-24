#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translation_lookup.py -- sozlukte terim arar (Turkce / Ingilizce / Cince).

Artik YAML'i kendisi ayristirmiyor; lotm.sozluk_yukle() kullaniyor. Bu
sayede 'mertebeler' icindeki "Turkce (English)" gomulu ciftler, arama_adi,
cevirmen_notu ve yeni 'cince' alani otomatik olarak gelir.

words.md (basit madde listesi) hâlâ burada okunur -- baska hicbir betik
kullanmadigi icin lotm.py'ye tasinmadi.

Kullanim:
    translation_lookup.py <sorgu>
    translation_lookup.py --notes <sorgu>    # cevirmen notlarini da yaz
    translation_lookup.py --eksik <sorgu>    # yalnizca Cincesi girilmemisler
"""

import re
import sys

import lotm

# "- **Turkce** — English"  (uzun tire yerine duz tire de kabul edilir)
MADDE = re.compile(r"^\s*-\s*\*\*(.+?)\*\*\s*[—-]\s*(.+?)\s*$")


def kelimeler_yukle(yol=None):
    """words.md'deki madde listesini Terim kayitlarina cevirir."""
    yol = yol or lotm.KELIMELER
    if not yol.exists():
        print(f"uyari: madde listesi yok: {yol}", file=sys.stderr)
        return []

    terimler = []
    with open(yol, "r", encoding="utf-8") as f:
        for satir in f:
            m = MADDE.match(satir)
            if m:
                terimler.append(
                    lotm.Terim(
                        tr=m.group(1).strip(),
                        en=m.group(2).strip(),
                        kategori="basit liste",
                    )
                )
    return terimler


def yaz(t, notlar=False):
    satir = f"  {t.tr}  →  {t.en or '-'}"
    if t.zh:
        satir += f"  ({t.zh})"
    satir += f"   [{t.yer}]"
    print(satir)
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
        print("kullanim: translation_lookup.py [--notes] [--eksik] <sorgu>",
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
