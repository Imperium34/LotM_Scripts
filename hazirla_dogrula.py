#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hazirla_dogrula.py -- hazirla.py'nin terim dokumunu YAYIMLANMIS bolumlere
karsi sinar.

UST DUZEY SORU: "Dokum, cevirmenin gercekten kullandigi yerlesik terimleri
buluyor mu; buldugu terimler cevirmenin kullandiklari mi?"

Yayimlanmis bir bolumun Turkcesi, o bolum icin "dogru cevap"in en yakin
tahminidir. Iki yonde olculur:

  KACAN   Sozlukteki bir terimin Turkcesi yayimlanmis metinde geciyor, ama
          dokum o terimi vermedi. Nedeni Cinceden okunur:
            anahtar-var   terimin Cince anahtari bu bolumde GECIYOR ama
                          dokum vermedi: arama hatasi (en onemlisi).
            anahtar-yok   anahtari var ama bu bolumde gecmiyor: ya kaynak
                          baska bir Cince sozcuk kullanmis (anahtara
                          eklenmeli), ya Turkce sozcuk burada siradan
                          anlamda (gurultu).
            cincesiz      terimin Cince anahtari hic yok: dokum yalniz
                          Ingilizceye bakabilir; sozluge anahtar girilmeli.
  YOK     Dokum terimi verdi ama yayimlanmis Turkcede hicbir bicimi yok:
          ya cevirmen yerlesik terimi kullanmadi (kayma), ya dokum yanlis
          eslesti (Cince anahtar baska anlamda).

Siradan sozcuk gurultusunu azaltmak icin KACAN listesine yalniz ayirt edici
terimler girir: Mertebe ve sozluk.yml terimleri, cok kelimeli ya da buyuk
harfli words.md karsiliklari ve uzun (7+ harf) tek kelimeler.

Kullanim:
    hazirla_dogrula.py 1-56
    hazirla_dogrula.py 40-56 --cikti dogrulama.md
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import hazirla as H
import lotm
from toplu_denetle import harf_duyarli_mi
from turkce import tr_kucult


def ayirt_edici(t) -> bool:
    if not t.tr or H._CJK_DIZI.search(t.tr):
        return False
    if not t.kategori.startswith(lotm.KELIME_KATEGORI):
        return True  # sozluk.yml: Mertebe, kavram, ilah, kurum
    return " " in t.tr or t.tr[:1].isupper() or len(t.tr) >= 7


def desenler(t, kardesler) -> list:
    """[(bicim, desen)] -- hazirla'nin yayim aramasiyla AYNI bicimler."""
    duyarli = harf_duyarli_mi(t)
    return [(b, lotm.desen_kur(b, harf_duyarli=duyarli)) for b in H.yayim_bicimleri(t, kardesler)]


_CUMLE_BASI = re.compile(r"(?:^|[.!?…:\"“”_\n])\s*$")


def gecisler(t, desen: dict, metin: str, kapsam: list) -> list:
    """
    Terimin yayimlanmis metindeki ANLAMLI gecisleri. Uc gurultu atilir:
      - daha uzun bir terimin icindeki gecis ("Kristal" ⊂ "Beyaz Kristal
        Odası", "Sezar" ⊂ "Sezar Limanı"); kapsam o terimlerin araliklari;
      - dort harften kisa tek kelimelik bicim (iş, saat, Ay, Yol): siradan
        sozcukle ayirt edilemez;
      - tek kelimelik bicimin cumle basindaki gecisi: orada her kelime
        buyuk harflidir ("Kadının", "Galiba").
    """
    out = []
    for b, d in desen[id(t)]:
        tek = " " not in b
        if tek and len(b) < 5:
            continue
        for m in d.finditer(metin):
            if any(x <= m.start() and m.end() <= y and (y - x) > (m.end() - m.start())
                   for x, y in kapsam):
                continue
            if tek and _CUMLE_BASI.search(metin[max(0, m.start() - 3) : m.start()]):
                continue
            out.append(m)
    return out


def baglam(metin: str, m, pay: int = 40) -> str:
    s = re.sub(r"\s+", " ", metin[max(0, m.start() - pay) : m.end() + pay])
    return "…" + s + "…"


def dogrula(no: int, kay, tr_metin: str, ayirt: list, desen: dict) -> dict:
    h = H.hazirla_bolum(no, kay)
    if h is None:
        return {}
    bulunan = {tr_kucult(e.terim.tr) for e in h.eslesmeler}
    zh = h.zh or ""
    # Cok kelimeli terimlerin yayimlanmis metindeki araliklari: icindeki
    # kisa terim ayrica sayilmaz.
    kapsam = [
        m.span()
        for t in ayirt
        if " " in t.tr
        for _b, d in desen[id(t)]
        for m in d.finditer(tr_metin)
    ]
    kacan, yok, harf = [], [], []
    for t in ayirt:
        if tr_kucult(t.tr) in bulunan:
            continue
        g = gecisler(t, desen, tr_metin, kapsam)
        if g:
            anahtarlar = H._zh_parcalari(t)
            if not anahtarlar:
                neden = "cincesiz"
            elif any(z in zh for z in anahtarlar):
                neden = "anahtar-var"
            else:
                neden = "anahtar-yok"
            kacan.append((neden, t, baglam(tr_metin, g[0])))
    for e in h.eslesmeler:
        if e.nasil == "en-yedek":
            continue
        if any(d.search(tr_metin) for _b, d in desen.get(id(e.terim)) or desenler(e.terim, set())):
            continue
        # Yalniz buyuk/kucuk harf farki: veri sorunu (words.md "Altıpatlar",
        # metin "altıpatlar"), ceviri kaymasi degil.
        kucuk = tr_kucult(tr_metin)
        if any(lotm.desen_kur(tr_kucult(b), harf_duyarli=True).search(kucuk)
               for b in e.terim.tr_bicimleri()):
            harf.append(e)
        else:
            yok.append(e)
    return {"h": h, "kacan": kacan, "yok": yok, "harf": harf}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("aralik", help="bolum araligi, orn. 1-56 (1,5,10-20 de olur)")
    ap.add_argument("--cikti", type=Path)
    a = ap.parse_args()
    try:
        nolar = lotm.bolum_listesi(a.aralik)
    except ValueError as e:
        ap.error(str(e))
    bas, son = min(nolar), max(nolar)

    t0 = time.time()
    kay = H.kaynak_yukle()
    tr = {b.no: b.metin for b in kay.tr_bolumler if b.no is not None}
    kardesler = H.harf_kardesleri(kay.terimler)
    ayirt = [t for t in kay.terimler if ayirt_edici(t)]
    desen = {id(t): desenler(t, kardesler) for t in kay.terimler if t.tr}
    print(f"yükleme {time.time() - t0:.0f}s, {len(ayirt)} ayırt edici terim", file=sys.stderr)

    satirlar, kacanlar, yoklar, harfler = [], defaultdict(list), defaultdict(list), defaultdict(list)
    for no in nolar:
        if no not in tr:
            continue
        s = dogrula(no, kay, tr[no], ayirt, desen)
        if not s:
            continue
        h = s["h"]
        say = defaultdict(int)
        for neden, t, bag in s["kacan"]:
            say[neden] += 1
            kacanlar[(neden, t.tr, t.en, t.zh)].append((no, bag))
        for e in s["yok"]:
            yoklar[(e.terim.tr, e.terim.en, e.nasil)].append(no)
        for e in s["harf"]:
            harfler[(e.terim.tr, e.terim.en, e.nasil)].append(no)
        satirlar.append(
            f"| {no} | {sum(e.nasil == 'zh' for e in h.eslesmeler)} | "
            f"{sum(e.nasil == 'en' for e in h.eslesmeler)} | {say['anahtar-var']} | "
            f"{say['anahtar-yok']} | {say['cincesiz']} | {len(s['yok'])} |"
        )
        print(f"  {no}: {time.time() - t0:.0f}s", file=sys.stderr)

    out = [f"# Terim Dökümü Doğrulaması — bölüm {bas}–{son}", ""]
    out += ["| bölüm | Çinceden | İngilizceden | kaçan: anahtar var | kaçan: anahtar yok | "
            "kaçan: Çincesiz | dökümde var, Türkçede yok |",
            "| --- | --- | --- | --- | --- | --- | --- |"] + satirlar
    for baslik, neden in (("Kaçan — anahtar bu bölümde geçiyor (arama hatası)", "anahtar-var"),
                          ("Kaçan — Çincesiz terim (anahtar girilmeli)", "cincesiz"),
                          ("Kaçan — anahtar bu bölümde yok (başka Çince sözcük ya da gürültü)",
                           "anahtar-yok")):
        liste = sorted(((k, v) for k, v in kacanlar.items() if k[0] == neden),
                       key=lambda kv: -len(kv[1]))
        out += ["", f"## {baslik} ({len(liste)} terim)", ""]
        for (_n, t_tr, t_en, t_zh), yerler in liste:
            nolar = ", ".join(str(n) for n, _b in yerler[:12]) + (" …" if len(yerler) > 12 else "")
            out.append(f"- **{t_tr}** ← {t_en or '—'} ({t_zh or 'Çincesiz'}) — {len(yerler)} bölüm: "
                       f"{nolar}; örnek: {yerler[0][1]}")
    for baslik, kume in (
        ("Dökümde var, yayımlanmış Türkçede yok (kayma ya da yanlış eşleşme)", yoklar),
        ("Yalnız büyük/küçük harf farkı (sözlükteki yazım metindekinden farklı)", harfler),
    ):
        liste = sorted(kume.items(), key=lambda kv: -len(kv[1]))
        out += ["", f"## {baslik} ({len(liste)} terim)", ""]
        for (t_tr, t_en, nasil), nolar in liste:
            out.append(f"- **{t_tr}** ← {t_en or '—'} [{nasil}] — {len(nolar)} bölüm: "
                       + ", ".join(map(str, nolar[:15])) + (" …" if len(nolar) > 15 else ""))
    metin = "\n".join(out) + "\n"
    if a.cikti:
        lotm.atomik_yaz(a.cikti, metin)
        print(f"yazıldı: {a.cikti}", file=sys.stderr)
    else:
        print(metin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
