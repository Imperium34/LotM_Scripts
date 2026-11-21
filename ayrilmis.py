#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ayrilmis.py -- Ayrilmis Sozcuk Dizini: Turkcede zaten bir seyin karsiligi
olan her sozcuk ve onu neyin ayirdigi.

UST DUZEY SORU: "Bu Turkce kelime baska bir seye ayrilmis mi?"

hazirla.py bolumde GECEN terimleri bulur. Sablonun komsu terim
carpismalari (A.3) ise cogunlukla bolumde GECMEYEN terimlerden dogar:
'Gemici' Denizci Yolu'nun 7. Mertebesidir, 'Şeamet' bir Mertebe adinin ve
bir tazim isminin parcasidir; siradan bir 'tayfa' ya da 'kotu talih' icin
secilirlerse iki kavram okurda birlesir. Bir varlik taramasi bunlari
bulamaz, cunku bolumde yoklar. Bu dizin, sablon ureticisinin butun sozlugu
(sozluk.yml + words.md + salahiyetler.yml, dokuz bin satir) okumadan ayni
bilgiye ulasmasi icindir. sablon_denetle.py A.2 ve B satirlarini da buna
karsi sinar.

KAYIT TURLERI (dizindeki sirayla)
  yasak      words.md notunda acikca yasaklanan ya da baska bir seye ayrilan
             sozcuk: "falcı" kullanılmaz, "ayin" 仪式'e ayrılı.
  eski       sozluk.yml'in eski_karsiliklar alani: bir kez kullanilmis,
             sonra birakilmis karsilik.
  mertebe    butun Mertebe adlari, Yol Yol, 9'dan 0'a.
  salahiyet  salahiyetler.yml'in Turkce adlari.
  kavram     sozluk.yml'in Mertebe disindaki ust duzey terimleri.
  kelime     words.md'nin TEK kelimelik karsiliklari. Cok kelimeli karsilik
             (Tingen Şehri, kabul salonu) bir addir ve duzyazida carpisma
             dogurmaz; o yuzden dizine girmez. Ondaki tehlikeli tek kelime
             zaten bir yasak notudur ("salon" kabul salonuna ayrılı).

Dizin uretilir, elle duzenlenmez: sozluk degisince yeniden calistirilir.

Kullanim:
    ayrilmis.py                      dizin, ekrana (Markdown)
    ayrilmis.py --cikti DOSYA        dizin, dosyaya
    ayrilmis.py --ara "Beş Deniz'in Kralı"
                                     metnin icerdigi ayrilmis sozcukler
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import lotm
from turkce import tr_kucult

TURLER = ("yasak", "eski", "mertebe", "salahiyet", "kavram", "kelime")

# A.2 ve B satirlarinda carpisma sayilan turler. 'kavram' ve 'kelime'
# bilesik adlarin parcasi olabilir (Rüya Kehaneti ⊃ Kehanet): carpisma
# degil, bilesimdir; sablon_denetle onlari ayrica, tam esitlikle sinar.
CARPISMA_TURLERI = ("yasak", "eski", "mertebe", "salahiyet")

_SALAHIYET_TURLERI = {
    "salahiyet": "Salahiyetler",
    "alt_salahiyet": "Alt salahiyetler",
    "simge": "Simgeler",
    "kabiliyet": "Kabiliyetler",
    "ilahi_hukumranlik": "İlahî hükümranlıklar",
    "yeganelik": "Yegânelikler",
    "mertebe_adi": "Yalnız Mertebe adında geçenler",
    "belirsiz": "Belirsiz",
}


@dataclass
class Ayrilmis:
    kelime: str  # ayrilmis Turkce bicim
    tur: str  # TURLER'den biri
    sahip: str  # onu ayiran kayit: "Denizci Yolu 7", "Kehanet", "kâhin"
    en: str | None = None
    zh: str | None = None
    not_: str = ""  # yasak: notun ilgili cumlesi; salahiyet: alt tur
    kapi: int | None = None  # eski: lotm.gecis_bolumu; bu bolumden ONCE eski bicim dogrudur


# ------------------------------------------------------------ yasak notlari

# words.md serbest yazilmis bir not dilidir; kapanis_denetle'nin dar
# YASAK_FIILLERI'nden genis tutulur. re.I KULLANILMAZ: "KULLANILMAZ"daki I
# noktasizdir, kucugu i degil ı'dir (bkz. turkce.py).
_GUCLU_IZ = re.compile(
    r"kullanılmaz|kullanılamaz|KULLANILMAZ|yazılmaz|ayrılı|ayrılmıştır|rezerve|"
    r"çarpar|karışır"
)
# "değil" zayif izdir: yalniz HEMEN onundeki tirnagi yasaklar. '"sandık",
# "çanta" değil' ikisini de; ama '"gümüş bıçak" (çakı değil)' izinli bicimi
# yasaklamaz, "değilse" hic iz degildir.
_DEGIL = re.compile(r"\b(?:değil|DEĞİL)\b")
_DEGIL_ONU = re.compile(r"[\s,/()]*(?:ve\s+)?(?:değil|DEĞİL)\b")
_ALINTI = re.compile(r'["“”]([^"“”\n]{1,40})["“”]')
# '"astrolabe" der': Ingilizce cevirinin sozcugu, Turkce bir yasak degil.
_DER = re.compile(r"\s*der\b")
_CJK = re.compile(r"[㐀-鿿]")


def yasak_cumleleri(not_metni: str) -> list:
    """Notun yasak ya da ayirma bildiren cumleleri (';' ve ' — ' ile bolunur)."""
    return [
        c.strip()
        for c in re.split(r";|\s—\s", not_metni or "")
        if _GUCLU_IZ.search(c) or _DEGIL.search(c)
    ]


def yasak_kayitlari(t) -> list:
    """
    Bir words.md maddesinin notundaki yasaklar. Tirnakli her bicim bir
    kayittir; "/" ile ayrilmis tirnak ("şükür/hamd") parcalanir.
    """
    out = []
    for cumle in yasak_cumleleri(str(t.cevirmen_notu or "")):
        guclu = bool(_GUCLU_IZ.search(cumle))
        for m in _ALINTI.finditer(cumle):
            if _DER.match(cumle, m.end()):
                continue
            if not guclu and not _DEGIL_ONU.match(_ALINTI.sub("", cumle[m.end() :])):
                continue
            ham = m.group(1).strip()
            parcalar = [p.strip() for p in ham.split("/")]
            for p in dict.fromkeys(parcalar):
                if p and not _CJK.search(p) and re.search(r"\w", p):
                    out.append(Ayrilmis(p, "yasak", t.tr, t.en, t.zh, cumle))
    return out


# ------------------------------------------------------------ kayitlar


def kayitlar(sozluk_terimleri, kelime_terimleri, salahiyetler) -> list:
    """Butun ayrilmis sozcukler, TURLER sirasiyla; ayni kayit bir kez."""
    out = []
    for t in kelime_terimleri:
        out += yasak_kayitlari(t)
    for t in sozluk_terimleri:
        for e in t.eski_karsiliklar or []:
            out.append(Ayrilmis(str(e), "eski", t.tr, t.en, t.zh, kapi=lotm.gecis_bolumu(t)))
    for t in sozluk_terimleri:
        if t.mertebe_mi:
            for b in t.tr_bicimleri():
                out.append(Ayrilmis(b, "mertebe", f"{t.yol} {t.seviye}", t.en, t.zh))
    for k in salahiyetler:
        tr = str(k.get("turkce") or "").strip()
        if tr:
            zh = str(k.get("cince") or "") or None
            tur = str(k.get("tur") or "belirsiz")
            out.append(
                Ayrilmis(tr, "salahiyet", f"{tur} {zh or ''}".strip(), None, zh, tur)
            )
    for t in sozluk_terimleri:
        if not t.mertebe_mi:
            for b in t.tr_bicimleri():
                out.append(Ayrilmis(b, "kavram", t.kategori or "üst düzey", t.en, t.zh))
    for t in kelime_terimleri:
        bolum = t.kategori.split("›")[-1].strip()
        for b in t.tr_bicimleri():
            if len(b.split()) == 1 and not _CJK.search(b):
                out.append(Ayrilmis(b, "kelime", bolum, t.en, t.zh))
    tekil, gorulen = [], set()
    for k in out:
        anahtar = (tr_kucult(k.kelime), k.tur, k.sahip)
        if anahtar not in gorulen:
            gorulen.add(anahtar)
            tekil.append(k)
    return tekil


def yukle() -> list:
    """Diskteki sozluklerden butun kayitlar."""
    return kayitlar(
        lotm.sozluk_yukle().terimler, lotm.kelimeler_yukle(), lotm.salahiyetler_yukle()
    )


@lru_cache(maxsize=None)
def _desen(kelime: str):
    # Buyuk harfle baslayan ayrilmis sozcuk (Mertebe, salahiyet) harf
    # duyarli aranir: "Ay" Mertebesi siradan "ay"i yakalamamali.
    return lotm.desen_kur(kelime, harf_duyarli=kelime[:1].isupper())


def icerenler(metin: str, kayit_listesi: list, turler=TURLER) -> list:
    """
    [(Ayrilmis, (bas, son))] -- metnin ICERDIGI ayrilmis sozcukler, ekli
    bicimleriyle (Gemicinin, falcıya). Uzun kayit once: "Gizem Avcısı"
    bulunduysa ayni yerdeki "Avcı" ayrica verilmez.
    """
    out, kapali = [], []
    for k in sorted(kayit_listesi, key=lambda k: -len(k.kelime)):
        if k.tur not in turler or len(k.kelime) < 2:
            continue
        for m in _desen(k.kelime).finditer(metin):
            a, b = m.span()
            if any(x <= a and b <= y and (x, y) != (a, b) for x, y in kapali):
                continue
            kapali.append((a, b))
            out.append((k, (a, b)))
    return sorted(out, key=lambda x: (x[1][0], TURLER.index(x[0].tur)))


# ------------------------------------------------------------ cikti


def _gloss(k: Ayrilmis) -> str:
    return f"{k.kelime} ({k.en or k.zh})" if (k.en or k.zh) else k.kelime


def dizin_md(kayit_listesi: list) -> str:
    gruplar = {t: [k for k in kayit_listesi if k.tur == t] for t in TURLER}
    out = [
        "# Ayrılmış Sözcük Dizini",
        "",
        "ayrilmis.py üretir; elle düzenlenmez. Buradaki her Türkçe sözcük zaten bir şeyin "
        "karşılığıdır ve bölümde BAŞKA bir şeyin karşılığı olarak yazılmaz. Salahiyet adları "
        "bunun istisnasıdır: çoğu aynı zamanda dönemin sıradan sözcüğüdür ve sıradan anlamda "
        "serbesttir. Cümle istiyorsa yazılır ama aranmaz, büyük harfle de yazılmaz. Bağlam onu "
        "salahiyetin kendisi gibi okutuyorsa çarpışmadır: büyük harfle yazılmışsa ya da "
        "salahiyetin alanı veya sembolüyle yan yana duruyorsa. Başka bir bölümde de yasaklı ya "
        "da ayrılmış olan sözcük yasaklı kalır. Şablonun komşu terim çarpışmaları (A.3) buradan "
        "seçilir. Bölümde geçen terimlerin kendisi Terim Dökümü'ndedir; bu dizin bölümde "
        "GEÇMEYENLER içindir.",
    ]

    out += ["", "## 1. Açık yasaklar ve başka yere ayrılmış sözcükler", ""]
    out.append("Not, yasağı koyan words.md maddesinin kendi cümlesidir.")
    out.append("")
    for k in gruplar["yasak"]:
        out.append(f"- **{k.kelime}** — {k.not_}  ·  madde: {k.sahip}")
    for k in gruplar["eski"]:
        if k.kapi:
            out.append(f"- **{k.kelime}** — eski karşılık; {k.kapi}. bölümden itibaren **{k.sahip}**, "
                       f"{k.kapi}'ten önceki bölümlerde '{k.kelime}' doğrudur")
        else:
            out.append(f"- **{k.kelime}** — eski karşılık; artık **{k.sahip}**")

    out += ["", "## 2. Mertebe adları (Yol Yol, 9 → 0)", ""]
    yollar: dict = {}
    for k in gruplar["mertebe"]:
        yol, _bosluk, seviye = k.sahip.rpartition(" ")
        yollar.setdefault(yol, []).append((int(seviye) if seviye.isdigit() else -1, k))
    for yol in sorted(yollar, key=tr_kucult):
        dizi = sorted(yollar[yol], key=lambda x: -x[0])
        out.append(f"- **{yol}:** " + " · ".join(f"{s} {_gloss(k)}" for s, k in dizi))

    out += ["", "## 3. Salahiyet adları", ""]
    for tur, ad in _SALAHIYET_TURLERI.items():
        ks = [k for k in gruplar["salahiyet"] if k.not_ == tur]
        if ks:
            out.append(f"- **{ad}:** " + ", ".join(_gloss(k) for k in ks))

    out += ["", "## 4. Kavramlar ve adlar (sozluk.yml)", ""]
    kategoriler: dict = {}
    for k in gruplar["kavram"]:
        kategoriler.setdefault(k.sahip, []).append(k)
    for kat, ks in kategoriler.items():
        out.append(f"- **{kat}:** " + ", ".join(_gloss(k) for k in ks))

    out += ["", "## 5. Tek kelimelik karşılıklar (words.md)", ""]
    bolumler: dict = {}
    for k in gruplar["kelime"]:
        bolumler.setdefault(k.sahip, []).append(k)
    for bol, ks in bolumler.items():
        out.append(f"- **{bol}:** " + ", ".join(_gloss(k) for k in ks))

    out += [
        "",
        f"_{len(gruplar['yasak'])} yasak, {len(gruplar['eski'])} eski karşılık, "
        f"{len(gruplar['mertebe'])} Mertebe adı, {len(gruplar['salahiyet'])} salahiyet, "
        f"{len(gruplar['kavram'])} kavram, {len(gruplar['kelime'])} tek kelime._",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cikti", type=Path, help="Markdown dosyasi (varsayilan: ekran)")
    ap.add_argument("--ara", metavar="METIN", help="metnin icerdigi ayrilmis sozcukler")
    a = ap.parse_args()
    ks = yukle()
    if a.ara:
        bulunan = icerenler(a.ara, ks)
        if not bulunan:
            print("ayrılmış sözcük yok")
        for k, (x, y) in bulunan:
            ek = f" — {k.not_}" if k.not_ and k.tur == "yasak" else ""
            print(f"{a.ara[x:y]}: {k.tur} · {k.sahip}{ek}")
        return 0
    metin = dizin_md(ks)
    if a.cikti:
        lotm.atomik_yaz(a.cikti, metin)
        print(f"yazıldı: {a.cikti}", file=sys.stderr)
    else:
        print(metin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
