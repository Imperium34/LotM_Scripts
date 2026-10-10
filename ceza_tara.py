#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ceza_tara.py -- hizalama sabitlerini capa yer degistirme sayisiyla ayarlar.

NEDEN SIMDI YAPILABILIYOR
-------------------------
capa.py'deki kayitli denemede etiket cezasi kesin'i 83'ten 64'e indirmis,
duzyazi duzeldikce 85'e cikmisti. O olcut kirliydi: kesin icindeki capa
sinyali, yon filtresinden once yogun adlarin tesadufi carpismalarini
sayiyordu (Bolum 6: 15 bulgunun 14'u 周明瑞/奥黛丽 carpismasi).

Yon filtresinden sonra yer degistirme sayisi dogrulanabilir bir olcut:
uyusmazlik kumesindeki 8 bulgunun 8'i elle dogrulandi.

TARANAN IKI SABIT KARSI KARSIYA
-------------------------------
Dogrulanan butun kaymalar iki grup uzunlugunda ve UZUNLUK BAKIMINDAN
NOTR -- metin kaybolmuyor, grup sinirini asiyor. z artigi susuyor, karar
tamamen sabitlere kaliyor:

    _ETIKET_CEZASI (400)  iki nokta ile biten paragrafta grubu kapatmayi
                          cezalandirir  -> BIRLESTIRMEYE iter
    CAPA_ODULU     (400)  capali 1:1'i odullendirir                -> AYIRMAYA iter

Ikisi ayni gruplarda, zit yonde ve esit buyuklukte. Sentetik olarak
olculdu: odul cezayi gectiginde hizalama tam da kayma seklini uretiyor.

Kullanim:
    ceza_tara.py                              _ETIKET_CEZASI: 400..700
    ceza_tara.py --degisken CAPA_ODULU --cezalar 0,200,400
    ceza_tara.py --modul /path/bolum_yama.py  yamali hizalayiciyla kiyas
    ceza_tara.py --bolumler 6,32,39
"""

import argparse
import importlib.util
import sys
from collections import Counter

import capa as _capa
import lotm
from hizalama_denetle import capa_yer_degistirme

# Elle dogrulanmis kaymalar: (bolum, capa_zh). Grup numarasi YAZILMAZ --
# sabit degisince numaralandirma da degisir. Bir vakanin kaybolmasi iyi
# haberdir (hizalayici duzeltti) AMA yalnizca grup/tek sayilari sabit
# kalmissa; yoksa duzelmemis, buyuk gruplarin icinde saklanmistir.
DOGRULANMIS = [
    (40, "尼尔"), (41, "阿尔杰"), (42, "伦纳德"), (43, "伦纳德"),
    (39, "伦纳德"), (39, "克莱恩"), (39, "梅丽莎"),
    (32, "克莱恩"), (32, "尼尔"), (1, "周明瑞"),
]


def modul_yukle(yol):
    if not yol:
        import bolum
        return bolum
    spec = importlib.util.spec_from_file_location("bolum_alt", yol)
    m = importlib.util.module_from_spec(spec)
    sys.modules["bolum_alt"] = m
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cezalar", default="400,500,600,700")
    ap.add_argument("--degisken", default="_ETIKET_CEZASI")
    ap.add_argument("--modul", default=None)
    ap.add_argument("--bolumler", default=None)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--terim-capali", dest="terim", action="store_const", const=True,
                   help="sozluk terimi capalarini zorla AC")
    g.add_argument("--terim-capasiz", dest="terim", action="store_const", const=False,
                   help="sozluk terimi capalarini zorla KAPAT")
    # Varsayilan: capa.TERIM_CAPALARI -- yani uretimde kullanilan ayar olculur.
    a = ap.parse_args()

    B = modul_yukle(a.modul)
    if not hasattr(B, a.degisken):
        sys.exit(f"{a.degisken} yok")
    ilk = getattr(B, a.degisken)

    # Olcut (capa_yer_degistirme) her iki modda da YALNIZCA ad sozlugunu
    # kullanir; degisen tek sey hizalamanin kendisidir.
    if a.terim is not None:
        _capa.TERIM_CAPALARI = a.terim
    acik = _capa.TERIM_CAPALARI
    print(f"sozluk terimi capalari: {'acik' if acik else 'kapali'}"
          f" ({len(_capa.terim_capalari()) if acik else 0} terim, "
          f"bolumde en cok {_capa.TERIM_EN_COK} kez ve esit sayida gecenler)",
          file=sys.stderr)
    sozluk = _capa.sozluk_yukle()
    k_hepsi = lotm.bolum_sozlugu(lotm.bolumler_zh())
    h_hepsi = lotm.bolum_sozlugu(lotm.bolumler_tr())
    ortak = sorted(set(k_hepsi) & set(h_hepsi))
    if a.bolumler:
        istek = {int(x) for x in a.bolumler.split(",")}
        ortak = [n for n in ortak if n in istek]

    def paragraflar():
        return {
            no: (
                B.paragraflar(k_hepsi[no].metin, B.KAYNAKLAR["zh"][2]),
                B.paragraflar(h_hepsi[no].metin, B.KAYNAKLAR["tr"][2]),
            )
            for no in ortak
        }

    print(f"{len(ortak)} bölüm | {a.degisken} (şu an {ilk})"
          f"{' | modül: ' + a.modul if a.modul else ''}\n")
    print(f"{'değer':>7}{'yer değ.':>10}{'grup':>8}{'tek':>6}{'çoklu':>7}"
          f"{'ort.grup':>10}{'doğrulanmış':>13}")
    print("─" * 61)

    try:
        for deger in [int(x) for x in a.cezalar.split(",")]:
            setattr(B, a.degisken, deger)
            # Her deger icin yeniden ayristirilir: bazi degiskenler
            # (etiket_birlestir) paragraflamanin KENDISINI degistirir.
            # Eskiden bir kez, dongu disinda yapiliyordu ve o degiskenler
            # icin her satir ayni cikiyordu -- olcum sessizce bostu.
            par = paragraflar()
            s = Counter()
            kalan = set()
            for no in ortak:
                k_par, h_par = par[no]
                capalar = set(_capa.capa_bul(k_par, h_par, sozluk))
                gruplar = B.hizala(k_par, h_par, capalar)
                yerler = capa_yer_degistirme(k_par, h_par, gruplar, sozluk)
                s["grup"] += len(gruplar)
                s["tek"] += sum(1 for ia, ib in gruplar if not ia or not ib)
                s["coklu"] += sum(1 for ia, ib in gruplar
                                  if len(ia) > 1 or len(ib) > 1)
                s["yer"] += sum(len(v) for v in yerler.values())
                for v in yerler.values():
                    for zh, _t, _y in v:
                        kalan.add((no, zh))
            hala = sum(1 for vaka in DOGRULANMIS if vaka in kalan)
            print(f"{deger:>7}{s['yer']:>10}{s['grup']:>8}{s['tek']:>6}"
                  f"{s['coklu']:>7}{s['grup'] / max(1, len(ortak)):>10.1f}"
                  f"{hala:>8}/{len(DOGRULANMIS)}")
    finally:
        setattr(B, a.degisken, ilk)

    print("\nOkuma: 'yer değ.' düşerken 'grup' ve 'tek' sabit kalmalı.")
    print("Grup sayısı da düşüyorsa ölçüt kandırılıyor demektir.")


if __name__ == "__main__":
    main()
