#!/usr/bin/env python3
"""
Sitenin _data/ciltler.yml dosyasını lotm.CILTLER'den üretir.

Cilt sınırları tek yerde durur (lotm.py); arşiv sayfası bu dosyayı okur.
Anahtar "numara"dır, "no" değil: YAML'da çıplak `no` false olarak okunur.

    python3 ciltler_yaz.py             yazar
    python3 ciltler_yaz.py --denetle   yazmaz; dosya lotm.CILTLER'den geride ise cikis 1
"""
import sys
from pathlib import Path

import lotm

HEDEF = Path(__file__).resolve().parent.parent / "Imperium34.github.io/_data/ciltler.yml"


def metin() -> str:
    sat = ["# ciltler_yaz.py ile lotm.CILTLER'den üretildi; elle düzenlemeyin.",
           "# Arşiv yalnızca yayımlanmış bölümü olan ciltleri gösterir."]
    for numara, ad, ilk, son in lotm.CILTLER:
        sat += [f"- numara: {numara}", f'  ad: "{ad.replace("_", " ")}"',
                f"  ilk: {ilk}", f"  son: {son}"]
    sat += ["# Ana hikâye lotm.ANA_HIKAYE_SONU'nda biter; sonrası yan hikâyeler.",
            "- numara: 0", '  ad: "Yan Hikâyeler"',
            f"  ilk: {lotm.ANA_HIKAYE_SONU + 1}", f"  son: {lotm.SON_BOLUM}"]
    return "\n".join(sat) + "\n"


def main():
    yeni = metin()
    if "--denetle" in sys.argv[1:]:
        if HEDEF.exists() and HEDEF.read_text(encoding="utf-8") == yeni:
            print(f"güncel: {HEDEF.name}")
            return 0
        print(f"GERİDE: {HEDEF} lotm.CILTLER ile uyuşmuyor (yazmak: ./calistir.sh ciltler --yaz)")
        return 1
    # Duz write_text yarida kesilirse arsiv sayfasini bos birakabilirdi.
    lotm.atomik_yaz(HEDEF, yeni)
    print(f"{HEDEF} yazıldı ({len(lotm.CILTLER)} cilt + yan hikâyeler)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
