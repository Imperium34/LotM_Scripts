#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
turkce.py -- Turkce harf buyuklugu icin TEK kaynak.

Bu modulden once projede alti ayri kucultme fonksiyonu vardi (lotm'da iki,
sozluk_lint, kapanis_denetle, yayim_denetle, ceviri_denetle'de birer) ve
ikisi Turkce I/ı'yi yanlis ceviriyordu. Uc ayri tuzak var ve her biri en az
bir kez bu projede isirdi:

  1. str.lower()   'I' -> 'i' verir; Turkcede 'ı' olmali.
                   'İ' -> 'i' + U+0307 (birlesen ustnokta) verir; gorunuste
                   'i', ama "iyi" artik "İyi".lower()'in alt dizesi degil.
  2. str.casefold() 'I' icin ayni hata; 'İ' icin ayni U+0307. Ustnoktayi
                   atmak 2. yariyi duzeltir, 1. yariyi DUZELTMEZ:
                   "Işık" -> "işık", "ışık" ile eslesmez. sozluk_lint bu
                   yuzden yarim duzeltilmisti.
  3. re.IGNORECASE Denklik siniflarini upper() uzerinden kurar. 'ı'.upper()
                   da 'i'.upper() da 'I' oldugu icin ı ile i AYNI SINIFA
                   duser: re.search("Ayin", "ayının", re.I) eslesir,
                   "sira" deseni "sıra"yi bulur. Turkce metinde harf
                   duyarsiz arama icin re.IGNORECASE HIC kullanilmaz;
                   tr_desen() kullanilir.

Bu modul bilerek bagimliliksizdir: lint/ altindaki betikler lotm'u (ve
onun YAML bagimliligini) yuklemeden de bunu ice aktarabilsin diye.
lotm bu fonksiyonlari yeniden disa verir; lotm.tr_kucult ve eski
lotm._tr_kucult ayni fonksiyondur.

INGILIZCE METIN ICIN BUNLAR KULLANILMAZ. tr_kucult("Iron") = "ıron";
kullanicinin yazdigi "iron" onun alt dizesi degildir. Ingilizce alanlar
str.casefold() ile kucultulur (bkz. en_kucult).
"""

import re

_BUYUK = {"i": "İ", "ı": "I"}


def tr_kucult(s):
    """
    Turkce kucultme: 'İ' -> 'i', 'I' -> 'ı', gerisi str.lower().

    Uzunluk korunur (NFC metinde); yani kucultulmus metindeki bir konum
    asil metindeki ayni konumdur. casefold() bunu garanti etmez ("ß" -> "ss").

    Ayrisik yazilmis 'I' + U+0307 (bazi kopyala-yapistirlarda gelir) once
    'i'ye indirilir; yoksa 'ı' + ustnokta gibi Turkcede olmayan bir harf
    cikar. Yalnizca bu durumda uzunluk bir kisalir.

    None ya da bos dize icin bos dize doner.
    """
    if not s:
        return ""
    return s.replace("I\u0307", "i").replace("İ", "i").replace("I", "ı").lower()


def tr_buyut(s):
    """Yalniz ilk harfi buyutur: 'i' -> 'İ', 'ı' -> 'I'."""
    if not s:
        return s
    return _BUYUK.get(s[0], s[0].upper()) + s[1:]


def _harf_buyut(c):
    b = _BUYUK.get(c, c.upper())
    # Bazi harflerin buyugu iki karakterdir ("ß" -> "SS"); onlar icin sinif
    # kurulmaz, harf oldugu gibi aranir.
    return b if len(b) == 1 else c


def tr_desen(metin):
    """
    Duz bir dizeyi Turkceye gore HARF DUYARSIZ arayan regex parcasi.

        tr_desen("ışık") -> "[ıI][şŞ][ıI][kK]"
        tr_desen("Ayin") -> "[aA][yY][iİ][nN]"     ("ayın"i BULMAZ)

    re.IGNORECASE'in yerine gecer (bkz. modul notu, 3. tuzak). Donen dize
    bir regex parcasidir, derlenmis desen degil; cagiran kendi sinir ve
    ek kaliplariyla birlestirir. Harf olmayan her karakter kacislanir.
    """
    out = []
    for c in metin:
        if not c.isalpha():
            out.append(re.escape(c))
            continue
        k = tr_kucult(c)
        if len(k) != 1:
            out.append(re.escape(c))
            continue
        b = _harf_buyut(k)
        out.append(f"[{re.escape(k)}{re.escape(b)}]" if b != k else re.escape(c))
    return "".join(out)


def en_kucult(s):
    """Ingilizce (ve Cince) alanlar icin kucultme: str.casefold()."""
    return (s or "").casefold()
