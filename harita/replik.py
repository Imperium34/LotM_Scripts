#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harita/replik.py -- bir karakterin repliklerini ¶ numarasiyla toplar.

Adi (regex) ve bir tirnak (“) iceren gruplari, ardindaki k replik grubuyla
birlikte basar: konusma etiketi bir grupta, replik bir sonrakinde olabilir.
Desen konusmaciyi degil adi yakalar; atfi elle dogrula (yanlis konusmaciyi
da toplar).

Kullanim:
    harita/replik.py "阿里安娜" 992,1024,1029 [k=1] [tr|en]
    harita/replik.py "尼姆|大祭司" 1210-1215

Bolumler virgulle ya da araligla (1210-1215) verilir. Her bolumun basinda
"=== N" yazilir; alintiyi deftere gecirirken bolum numarasini buradan al
(toplu ciktida en sik hata alintinin yanlis bolume yazilmasidir).
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gruplar import gruplar  # noqa: E402


def bolum_listesi(arg: str) -> list:
    out = []
    for parca in arg.split(","):
        if "-" in parca:
            a, b = parca.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif parca.strip():
            out.append(int(parca))
    return out


def replikler(ad: str, bolumler, k: int = 1, ikinci: str = "en") -> dict:
    """{bolum: [(¶, ZH)]}"""
    desen = re.compile(ad)
    out = {}
    for no in bolumler:
        g = gruplar(no, ikinci)
        sira = sorted(g)
        secili = set()
        for i, p in enumerate(sira):
            if desen.search(g[p]["ZH"]) and "“" in g[p]["ZH"]:
                secili.add(p)
                for q in sira[i + 1 : i + 1 + k]:
                    if "“" in g[q]["ZH"]:
                        secili.add(q)
        out[no] = [(p, g[p]["ZH"]) for p in sorted(secili)]
    return out


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    ad, bolumler = sys.argv[1], bolum_listesi(sys.argv[2])
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    ikinci = sys.argv[4] if len(sys.argv) > 4 else "en"
    for no, satirlar in replikler(ad, bolumler, k, ikinci).items():
        print(f"=== {no}")
        for p, zh in satirlar:
            print(f"¶{p} {zh}")


if __name__ == "__main__":
    main()
