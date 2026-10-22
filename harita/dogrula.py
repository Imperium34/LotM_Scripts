#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harita/dogrula.py -- haritadaki alintilarin ¶ numaralarini dogrular.

Girdi dosyasinda her satir:  bolum|¶|ZH alt dizgisi   (# ile baslayan satir
yorumdur). Alt dizgi o grubun ZH metninde geciyorsa OK; gecmiyorsa dogru
(bolum, ¶) aranir: once ±2 bolum, bulunamazsa --genis ile butun kitap.

Toplu cikarmalarda alinti cogu zaman bir bolum kayar (bir oturumda bir
sahnenin tamami 541 yerine 510'da cikti), o yuzden her ¶ yazildiktan sonra
bu dosyadan gecirilir.

Kullanim:
    harita/dogrula.py alintilar.txt [--tr] [--genis]

--tr: yayimlanmis bolumler icin ZH/TR duzeni (varsayilan ZH/EN).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gruplar import gruplar  # noqa: E402
import lotm  # noqa: E402


def bul(alt: str, adaylar, ikinci: str):
    for no in adaylar:
        for p, v in gruplar(no, ikinci).items():
            if alt in v["ZH"]:
                return no, p
    return None


def genis_bul(alt: str, ikinci: str):
    adaylar = [b.no for b in lotm.bolumler_zh() if alt in b.metin]
    return bul(alt, adaylar, ikinci)


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not argv:
        sys.exit(__doc__)
    ikinci = "tr" if "--tr" in sys.argv else "en"
    genis = "--genis" in sys.argv
    hata = 0
    for satir in Path(argv[0]).read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#"):
            continue
        no, p, alt = satir.split("|", 2)
        no, p = int(no), int(p)
        g = gruplar(no, ikinci)
        if p in g and alt in g[p]["ZH"]:
            print(f"OK  {no} ¶{p} {alt[:30]}")
            continue
        hata += 1
        r = bul(alt, [no] + [no + d for d in (-2, -1, 1, 2)], ikinci)
        if r is None and genis:
            r = genis_bul(alt, ikinci)
        yer = f"{r[0]} ¶{r[1]}" if r else "bulunamadi (--genis dene)"
        print(f"FIX {no} ¶{p} -> {yer}  {alt[:30]}")
    sys.exit(1 if hata else 0)


if __name__ == "__main__":
    main()
