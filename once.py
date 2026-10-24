#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
once.py -- ceviriden ONCE: hazirlik ve sablon denetimi tek komutla.

UST DUZEY SORU: "Bu bolumun sablonu ceviriye hazir mi?"

sonra.py'nin ikizi. Iki adim, sirasi bagimliliktan gelir:

    hazirlik   calistir.sh hazirla N -> Reports/hazirlik/Ch_N_terimler.md
               + ayrilmis_dizin.md. Dokum yoksa ya da sozluk.yml / words.md
               ondan yeniyse yeniden uretilir: sablon ureticisi en son
               karari gormeli.
    sablon     Tools/Schemas/Ch_N.md kaydedilince sablon_denetle.py
               -> Reports/once/Ch_N/sablon_denetimi.md. Sablon yeniden
               yazilinca denetim yeniden calisir. HATA, sablonun verilmis
               bir karari degistirdigi demektir: ceviriden once duzeltilir.

Sablonun kendisi model isidir (lotm-chapter-template becerisi); bu betik
ona verilecek dosyalari hazirlar ve dondugunde denetler.

Kullanim:
    once.py 61                 durum: hazirlik, sablon bekleniyor mu, denetim
    once.py 61 --yeniden       hazirligi ve denetimi zorla yeniden uret
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
KOK = Path(os.environ.get("LOTM_KOK") or BETIKLER.parent)
SITE = KOK / "Imperium34.github.io"
SABLONLAR = Path(os.environ.get("LOTM_SABLONLAR") or KOK / "Tools" / "Schemas")
HAZIRLIK = BETIKLER / "Reports" / "hazirlik"
RAPOR = Path(os.environ.get("LOTM_ONCE_RAPOR") or BETIKLER / "Reports" / "once")
# Dokumun dayandigi veriler: biri degisirse dokum bayattir.
VERILER = [SITE / "_data" / "sozluk.yml", SITE / "_data" / "salahiyetler.yml",
           Path(os.environ.get("LOTM_KELIMELER") or KOK / "Tools" / "words.md")]


def bayat_mi(cikti: Path, kaynaklar: list) -> bool:
    if not cikti.exists():
        return True
    return any(k.exists() and k.stat().st_mtime > cikti.stat().st_mtime for k in kaynaklar)


def ozet(rapor: str) -> tuple:
    """sablon_denetle raporunun ozet satirindan (HATA, UYARI)."""
    m = re.search(r"(\d+) HATA, (\d+) UYARI", rapor)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ceviri oncesi hat.")
    ap.add_argument("no", type=int)
    ap.add_argument("--yeniden", action="store_true")
    a = ap.parse_args(argv)
    no = a.no

    dokum = HAZIRLIK / f"Ch_{no}_terimler.md"
    dizin = HAZIRLIK / "ayrilmis_dizin.md"
    sablon = SABLONLAR / f"Ch_{no}.md"
    onceki = SABLONLAR / f"Ch_{no - 1}.md"
    klasor = RAPOR / f"Ch_{no}"
    denetim = klasor / "sablon_denetimi.md"
    satirlar = [f"# {no}. bölüm — çeviri öncesi hattı", ""]

    # 1. hazirlik
    if a.yeniden or bayat_mi(dokum, VERILER) or bayat_mi(dizin, VERILER):
        print(f"hazirlik: calistir.sh hazirla {no} ...", flush=True)
        p = subprocess.run(["bash", str(BETIKLER / "calistir.sh"), "hazirla", str(no)],
                           capture_output=True, text=True, cwd=BETIKLER)
        if p.returncode != 0 or not dokum.exists():
            print(p.stdout[-2000:], p.stderr[-2000:], sep="\n")
            print("HATA: hazirlik uretilemedi")
            return 1
    satirlar += ["## Hazırlık", "Şablon üreticisine verilecekler:",
                 f"- {dokum}", f"- {dizin}",
                 f"- {onceki}" if onceki.exists() else f"- (önceki şablon yok: {onceki.name})", ""]

    # 2. sablon
    satirlar.append("## Şablon")
    kod = 0
    if not sablon.exists():
        satirlar.append(f"BEKLIYOR  {sablon} — kaydedince bu komutu yeniden çalıştırın.")
    else:
        if a.yeniden or bayat_mi(denetim, [sablon, *VERILER]):
            print(f"sablon: sablon_denetle.py {sablon.name} ...", flush=True)
            klasor.mkdir(parents=True, exist_ok=True)
            p = subprocess.run([sys.executable, str(BETIKLER / "sablon_denetle.py"), str(sablon),
                                "--cikti", str(denetim)],
                               capture_output=True, text=True, cwd=BETIKLER)
            if not denetim.exists():
                print(p.stdout[-2000:], p.stderr[-2000:], sep="\n")
                print("HATA: sablon denetimi calismadi")
                return 1
        hata, uyari = ozet(denetim.read_text(encoding="utf-8"))
        if hata:
            durum, kod = "HATA", 1
        else:
            durum = "UYARI" if uyari else "TEMIZ"
        satirlar.append(f"{durum:9} {denetim.name} — {hata} HATA, {uyari} UYARI")
        if hata:
            satirlar.append("  Şablon verilmiş bir kararı değiştiriyor: çeviriden önce düzeltin.")
        elif uyari:
            satirlar.append("  Uyarılar karar değil aday: A.2'deki satır zaten sözlükte olabilir.")
        if not hata:
            satirlar += ["", f"Çeviriden sonra: ./calistir.sh sonra {no} --otomatik"]

    rapor = "\n".join(satirlar) + "\n"
    if sablon.exists():
        (klasor / "DURUM.md").write_text(rapor, encoding="utf-8")
    print()
    print(rapor)
    return kod


if __name__ == "__main__":
    sys.exit(main())
