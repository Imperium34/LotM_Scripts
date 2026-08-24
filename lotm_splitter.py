#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lotm_splitter.py -- EPUB'i cilt .txt dosyalarina boler.

Cilt tablosu artik lotm.CILTLER'den geliyor. Eskiden burada ayri bir
VOLUME_RANGES vardi ve ikisi kaymisti:

    cilt 6:  Light_Seeker              vs  Lightseeker
    cilt 7:  The_Hanged_Man            vs  Hanged_Man
    cilt 8:  Ordinary_Persons_Daily_Life (1354-9999) vs Fool (1354-1394)

lotm.py "bu tablo lotm_splitter.py ile ayni olmali" diyordu; degildi.
Artik tek tablo var.

Ana hikaye 1394'te biter. 1395+ bolumler (yan hikayeler) CILTLER'de
karsiliksizdir; bir cilde atanmadiklari icin acik olan son cilde
eklenirler -- eski 9999 ust siniriyla ayni sonuc, ama sinir uydurmadan.

Kullanim:
    python3 lotm_splitter.py                          varsayilan yollar
    python3 lotm_splitter.py --epub X.epub --cikti Out/
"""

import argparse
import html
import os
import re
import sys
import zipfile

import lotm

VARSAYILAN_EPUB = "Lord_of_the_Mysteries.epub"


def clean_html(html_content):
    """HTML etiketlerini atar, duz metin dondurur."""
    html_content = re.sub(r"<script.*?>.*?</script>", "", html_content, flags=re.DOTALL)
    html_content = re.sub(r"<style.*?>.*?</style>", "", html_content, flags=re.DOTALL)
    html_content = re.sub(r"</p>|<br\s*/?>|</div>", "\n", html_content)
    text = re.sub(r"<[^>]+>", "", html_content)
    # html.unescape hem adli hem sayisal varliklari cozer. Elle yazilmis
    # alti varlik listesi &#8220; gibi sayisal olanlari kaciriyordu ve
    # EPUB'larda tirnak isaretleri cogunlukla sayisal gelir.
    return html.unescape(text)


def _dogal_anahtar(ad):
    """
    Dosya adlarini SAYISAL siraya koyar.

    Duz siralama sozluk sirasidir: chapter_10 < chapter_2. EPUB'da bolum
    dosyalari cogunlukla sifirsiz numaralidir, yani duz siralama okuma
    sirasini bozar. (Tam dogrusu OPF spine'i okumaktir; bu ondan once
    gelen ucuz duzeltme.)
    """
    return [int(p) if p.isdigit() else p.lower()
            for p in re.split(r"(\d+)", ad)]


def cilt_bul(bolum_no):
    return lotm.cilt_bul(bolum_no)


def split_epub_by_chapters(epub_path, output_folder):
    if not os.path.exists(epub_path):
        sys.exit(f"HATA: '{epub_path}' bulunamadi.")

    os.makedirs(output_folder, exist_ok=True)
    print(f"Okunuyor: {epub_path}")

    cilt_metinleri = {c[0]: [] for c in lotm.CILTLER}
    aktif_cilt = lotm.CILTLER[0][0]

    with zipfile.ZipFile(epub_path, "r") as arsiv:
        dosyalar = sorted(arsiv.infolist(),
                          key=lambda x: _dogal_anahtar(x.filename))
        for bilgi in dosyalar:
            if not bilgi.filename.endswith((".html", ".xhtml")):
                continue
            with arsiv.open(bilgi) as f:
                ham = f.read().decode("utf-8", errors="ignore")
            blok = clean_html(ham).strip()
            if not blok:
                continue

            m = lotm.EN_BASLIK.match(blok)
            if m:
                c = cilt_bul(int(m.group(1)))
                if c:
                    aktif_cilt = c[0]
                # Karsiligi yoksa (1395+ yan hikayeler) acik cilt korunur.

            cilt_metinleri[aktif_cilt].append(blok)

    print("\nCilt dosyalari yaziliyor...")
    for no, ad, _bas, _son in lotm.CILTLER:
        icerik = "\n\n".join(cilt_metinleri[no]).strip()
        if not icerik:
            print(f"UYARI: cilt {no} icin icerik yok")
            continue
        dosya = f"Volume_{no}_{ad}.txt"
        with open(os.path.join(output_folder, dosya), "w", encoding="utf-8") as f:
            f.write(icerik)
        print(f"Yazildi: {dosya}")

    print(f"\nBitti. '{output_folder}' klasorune bakin.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epub", default=VARSAYILAN_EPUB)
    ap.add_argument("--cikti", default=str(lotm.KAYNAK_EN))
    a = ap.parse_args()
    split_epub_by_chapters(a.epub, a.cikti)


if __name__ == "__main__":
    main()
