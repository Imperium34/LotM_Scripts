#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fark.py -- bir denetimin bulgularini ONCEKI calistirmayla karsilastirir.

UST DUZEY SORU: "Son calistirmadan beri ne DEGISTI?"

Raporlar her calistirmada butun bulgulari yeniden yazar. Bilinen, kabul
edilmis bulgular her seferinde ayni yerde durur ve yeni bir bulgu onlarin
arasinda kaybolur. Bu betik yalnizca farki gosterir:

    + yeni     bu calistirmada var, oncekinde yoktu
    - giden    oncekinde vardi, artik yok (duzeltildi ya da metin degisti)

Bulgu dosyalari denetimlerin --bulgular ciktisidir (bkz. lotm.bulgulari_yaz):
her satir kararli bir anahtar + bir gorunum. Karsilastirma ANAHTARA gore;
satir numarasi anahtarda olmadigi icin bir paragraf eklemek butun bulgulari
"yeni" yapmaz.

Karsilastirmadan sonra simdiki dosya bir sonraki calistirmanin "onceki"si
olarak saklanir (--son-dizini). Ilk calistirmada karsilastirilacak bir sey
yoktur; yalnizca kayit alinir.

Kullanim:
    fark.py Reports/bulgular/lint.tsv                 Reports/son/lint.tsv ile
    fark.py Reports/bulgular/lint.tsv --kaydetme      karsilastir, saklama
    fark.py ... --ust 50                              en cok 50 satir goster

Cikis kodu her zaman 0: bu bir rapor, kapi degil.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def oku(yol: Path) -> dict:
    """{anahtar: gorunum}. Dosya yoksa None."""
    if not yol.exists():
        return None
    out = {}
    for satir in yol.read_text(encoding="utf-8").splitlines():
        if not satir.strip():
            continue
        anahtar, _, gorunum = satir.rpartition("\t")
        out[anahtar] = gorunum
    return out


def karsilastir(onceki: dict, simdiki: dict) -> tuple:
    """(yeni, giden) -- her biri [(anahtar, gorunum)], anahtara gore sirali."""
    yeni = sorted((a, g) for a, g in simdiki.items() if a not in onceki)
    giden = sorted((a, g) for a, g in onceki.items() if a not in simdiki)
    return yeni, giden


def yaz(ad: str, onceki, simdiki: dict, ust: int = 30) -> None:
    if onceki is None:
        print(f"  fark [{ad}]: ilk kayit ({len(simdiki)} bulgu); "
              f"bir sonraki calistirmada karsilastirilacak")
        return
    yeni, giden = karsilastir(onceki, simdiki)
    if not yeni and not giden:
        print(f"  fark [{ad}]: degisiklik yok ({len(simdiki)} bulgu)")
        return
    print(f"  fark [{ad}]: +{len(yeni)} yeni, -{len(giden)} giden "
          f"({len(onceki)} -> {len(simdiki)} bulgu)")
    for isaret, liste in (("+", yeni), ("-", giden)):
        for _a, g in liste[:ust]:
            print(f"    {isaret} {g}")
        if len(liste) > ust:
            print(f"    {isaret} ... {len(liste) - ust} tane daha")


def main() -> int:
    ap = argparse.ArgumentParser(description="Bulgulari onceki calistirmayla karsilastirir.")
    ap.add_argument("simdiki", type=Path, help="denetimin --bulgular ciktisi")
    ap.add_argument("--son-dizini", type=Path, default=None,
                    help="onceki kayitlarin klasoru (varsayilan: simdikinin ../son/)")
    ap.add_argument("--kaydetme", action="store_true",
                    help="karsilastir ama simdikini 'onceki' olarak saklama")
    ap.add_argument("--ust", type=int, default=30, help="her yonde en cok bu kadar satir")
    a = ap.parse_args()

    simdiki = oku(a.simdiki)
    if simdiki is None:
        print(f"  fark: {a.simdiki} yok (denetim calismadi mi?)", file=sys.stderr)
        return 0
    son_dizini = a.son_dizini or a.simdiki.parent.parent / "son"
    onceki_yol = son_dizini / a.simdiki.name
    yaz(a.simdiki.stem, oku(onceki_yol), simdiki, a.ust)
    if not a.kaydetme:
        son_dizini.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a.simdiki, onceki_yol)
    return 0


if __name__ == "__main__":
    sys.exit(main())
