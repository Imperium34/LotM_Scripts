#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harita/gruplar.py -- bir bolumun hizalama gruplarini ¶ numarasiyla verir.

Ses haritalarindaki ve not dosyalarindaki ¶ numaralari bolum.py'nin hizalama
gruplaridir: cevrilmemis bolumlerde ZH/EN, yayimlanmislarda ZH/TR. Iki duzen
ayni bolumde bir kayabilir (55: ZH/EN ¶73 = ZH/TR ¶74), o yuzden alinti
hangi duzenle yazildiysa o duzenle dogrulanir.

Eskiden bolum.py'nin ekran ciktisi --genislik 100000 ile ayristiriliyordu;
grup basliklari "(2:1)" eki tasidigi ve paragraflar dort bosluklu satirlara
sarildigi icin saf bir ayristirici ikisini de kaybediyordu. Bu modul ayni
islevleri (getir, paragraflar, capa, hizala) dogrudan cagirir; numaralar
bolum.py'nin bastigi ¶ ile birebir aynidir.

Kullanim:
    harita/gruplar.py 53 tr                 ZH/TR, butun gruplar
    harita/gruplar.py 1213 en "大祭司"       yalniz deseni iceren gruplar
"""

import functools
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bolum  # noqa: E402

# Bir grubun paragraflari tek satirda bu ayiriciyla birlestirilir; notlardaki
# alintilar da ayni bicimi kullanir ("“…” / “…”").
AYIRICI = " / "


@functools.lru_cache(maxsize=None)
def gruplar(no: int, ikinci: str = "en") -> dict:
    """
    {¶: {"ZH": metin, "EN" ya da "TR": metin}}. Bolum yoksa bos sozluk.
    """
    ikinci = ikinci.lower()
    if ikinci not in ("en", "tr"):
        raise ValueError("ikinci kaynak 'en' ya da 'tr' olmali")
    a, b = bolum.getir("zh", no), bolum.getir(ikinci, no)
    if a is None or b is None:
        return {}
    pa = bolum.paragraflar(a.metin.strip(), bolum.KAYNAKLAR["zh"][2])
    pb = bolum.paragraflar(b.metin.strip(), bolum.KAYNAKLAR[ikinci][2])
    capalar = set(bolum._capa.capa_bul(pa, pb, bolum._CAPA_SOZLUGU))
    ad = ikinci.upper()
    out = {}
    for k, (ia, ib) in enumerate(bolum.hizala(pa, pb, capalar), 1):
        out[k] = {
            "ZH": AYIRICI.join(pa[i] for i in ia),
            ad: AYIRICI.join(pb[j] for j in ib),
        }
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    no = int(sys.argv[1])
    ikinci = sys.argv[2] if len(sys.argv) > 2 else "en"
    desen = re.compile(sys.argv[3]) if len(sys.argv) > 3 else None
    ad = ikinci.upper()
    for k, g in gruplar(no, ikinci).items():
        if desen and not desen.search(g["ZH"] + g[ad]):
            continue
        print(f"¶{k} ZH {g['ZH']}")
        print(f"    {ad} {g[ad]}")


if __name__ == "__main__":
    main()
