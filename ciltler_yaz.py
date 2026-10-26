#!/usr/bin/env python3
"""
Sitenin _data/ciltler.yml dosyasını lotm.CILTLER'den üretir.

Cilt sınırları tek yerde durur (lotm.py); arşiv sayfası bu dosyayı okur.
Anahtar "numara"dır, "no" değil: YAML'da çıplak `no` false olarak okunur.

    python3 ciltler_yaz.py
"""
from pathlib import Path

import lotm

HEDEF = Path(__file__).resolve().parent.parent / "Imperium34.github.io/_data/ciltler.yml"


def main():
    sat = ["# ciltler_yaz.py ile lotm.CILTLER'den üretildi; elle düzenlemeyin.",
           "# Arşiv yalnızca yayımlanmış bölümü olan ciltleri gösterir."]
    for numara, ad, ilk, son in lotm.CILTLER:
        sat += [f"- numara: {numara}", f'  ad: "{ad.replace("_", " ")}"',
                f"  ilk: {ilk}", f"  son: {son}"]
    sat += ["# Ana hikâye lotm.ANA_HIKAYE_SONU'nda biter; sonrası yan hikâyeler.",
            "- numara: 0", '  ad: "Yan Hikâyeler"',
            f"  ilk: {lotm.ANA_HIKAYE_SONU + 1}", f"  son: {lotm.SON_BOLUM}"]
    HEDEF.write_text("\n".join(sat) + "\n", encoding="utf-8")
    print(f"{HEDEF} yazıldı ({len(lotm.CILTLER)} cilt + yan hikâyeler)")


if __name__ == "__main__":
    main()
