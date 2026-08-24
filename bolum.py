#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bolum.py -- bir bolumu uc metnin herhangi birinden getirir, paragraf paragraf
hizalayarak.

chinese_lookup.py'nin yerini alir. Numaralandirma lotm.py'den gelir, yani
Cince cilt sifirlamalari ve ham metindeki iki numara yazim hatasi dogru
cozulur -- "279" ucunde de ayni bolumu gosterir.

NEDEN KURAL DEGIL HIZALAMA
--------------------------
Cince web romanlarinda konusma etiketi ("...diye sordu：") cogu zaman kendi
paragrafindadir, tirnak bir sonrakinde. Ingilizce ceviri BAZEN ikisini
birlestirir, bazen birlestirmez -- 713. bolumde ZH ¶9-10 birlesir ama ¶13-14
ayri kalir; Cince tarafta ikisinin sekli aynidir.

Yani paragraf bolunmesi kaynagin bir ozelligi degil, cevirmenin her seferinde
verdigi bir karar. Kaynaga bakan hicbir mekanik kural bunu bilemez. Once
"iki nokta + tirnak birlestir" kurali denendi ve 713'u 70 paragraftan 58'e
dusurdu -- 5 birlestirme gerekirken 12 yapti.

Dogru cozum paragraf sayilarini esitlemeye calismak degil, DIZI HIZALAMASI:
her konumda 1:1, 2:1, 1:2, 2:2 ve tek tarafli eslesmeler arasindan uzunluk
oranini en iyi koruyani secen dinamik programlama (Gale-Church). Etiket
birlesmesini "neden" oldugunu bilmeden dogal bir 2:1 olarak cozer.

Kullanim:
    bolum.py 279                 ZH/EN hizalanmis paragraf paragraf
    bolum.py 279 --tr --en       yayimlanmis Turkce ile Ingilizce
    bolum.py 279 --zh            yalniz Cince
    bolum.py 279 --zh --raw      basliksiz govde (prompt'a boru ile verilir)
    bolum.py 279 --hizalamasiz   sirayla esle (tani icin)
    bolum.py 279 --sutun         eski yan yana duzen
"""

import argparse
import math
import re
import shutil
import sys
import unicodedata

import lotm

KAYNAKLAR = {
    "zh": ("ZH", lotm.bolumler_zh, lotm.ZH_BASLIK),
    "en": ("EN", lotm.bolumler_en, lotm.EN_BASLIK),
    "tr": ("TR", lotm.bolumler_tr, lotm.TR_BASLIK),
}

_onbellek = {}


def getir(kaynak, no):
    if kaynak not in _onbellek:
        _onbellek[kaynak] = lotm.bolum_sozlugu(KAYNAKLAR[kaynak][1]())
    return _onbellek[kaynak].get(no)


# --------------------------------------------------------- genislik

# East Asian Width 'A' (Ambiguous): Cince tirnak isaretleri (“ ” ‘ ’), uzun
# tire, uc nokta, orta nokta. CJK yazi tipinde CIFT, Latin metinde TEK
# genislikte render edilirler; unicodedata hangisi oldugunu bilemez, yazi
# tipine baglidir. Metnin kendisine bakariz: icinde CJK varsa A=2.
_CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


def _kolon_fabrikasi(metin):
    genis_a = bool(_CJK.search(metin))

    def kolon(ch):
        w = unicodedata.east_asian_width(ch)
        if w in ("W", "F"):
            return 2
        if w == "A":
            return 2 if genis_a else 1
        return 1

    return kolon


def _sar(metin, sutun, kolon) -> list:
    """
    Genislige duyarli sarma.

    textwrap kullanilamaz: (1) karakter sayar, kolon degil; (2) bosluga gore
    boler, Cince'de kelime arasi bosluk yoktur ve tum paragraf tek "kelime"
    sayilir.
    """
    cikti = []
    for paragraf in metin.split("\n"):
        if not paragraf.strip():
            cikti.append("")
            continue
        aktif, g = "", 0
        for ch in paragraf:
            w = kolon(ch)
            if g + w > sutun:
                kes = aktif.rfind(" ")
                if kes > sutun * 0.6:
                    cikti.append(aktif[:kes])
                    aktif = aktif[kes + 1:]
                    g = sum(kolon(c) for c in aktif)
                else:
                    cikti.append(aktif)
                    aktif, g = "", 0
            aktif += ch
            g += w
        if aktif:
            cikti.append(aktif)
    return cikti


def _dolgu(s, sutun, kolon) -> str:
    return s + " " * max(0, sutun - sum(kolon(c) for c in s))


# --------------------------------------------------------- paragraflar


def paragraflar(metin, baslik_deseni=None) -> list:
    """
    Metni paragraflara boler -- HICBIR normalizasyon yapmadan. Yapisal
    farklari hizalayici cozer.

    Ingilizce/Turkce metinde paragraflar bos satirla ayrilir; Cince ham
    metinde her paragraf tek satirdir ve arada bos satir yoktur. Once bos
    satira gore denenir, tek blok cikarsa satir satir bolunur.

    baslik_deseni verilirse bolum basligi paragraflari atilir. Bu SART:
    lotm_splitter.py'nin clean_html'i EPUB'daki basligi hem baslik ogesinden
    hem govde metninden aldigi icin Ingilizce tarafta bolum adi IKI KEZ gecer;
    Cince tarafta ise _ayir govdeye 第…章 satirini dahil eder. Temizlenmezse
    hizalayici bastan yanlis bir sabit ofsetle basliyor.
    """
    bloklar = [b.strip() for b in re.split(r"\n\s*\n", metin) if b.strip()]
    if len(bloklar) <= 1:
        bloklar = [s.strip() for s in metin.split("\n") if s.strip()]
    else:
        bloklar = [re.sub(r"\s*\n\s*", " ", b) for b in bloklar]

    if baslik_deseni:
        bloklar = [b for b in bloklar if not baslik_deseni.match(b)]
    return bloklar


# --------------------------------------------------------- hizalama

# Gale-Church eslesme cezalari. 1:1 bedava; bolme/birlestirme pahali ama
# mumkun; tek tarafli eslesme en pahali. Degerler orijinal makaledeki
# -100*log(P) yaklasimindan.
_CEZA = {
    (1, 1): 0,
    (2, 1): 230,
    (1, 2): 230,
    (2, 2): 440,
    (1, 0): 450,
    (0, 1): 450,
}

_VARYANS = 6.8


def hizala(a, b) -> list:
    """
    Iki paragraf listesini uzunluga gore hizalar.

    Doner: [(a_indisleri, b_indisleri), ...] -- her oge bir eslesme grubu.
    Bos liste tek tarafli eslesme demektir (bir tarafta karsiligi yok).

    Fikir: dogru eslesmis metinlerde hedef/kaynak karakter orani sabittir.
    Bir grubun maliyeti, o orandan sapmanin karesi arti eslesme tipinin
    cezasi. Dinamik programlama toplam maliyeti en aza indiren bolunmeyi
    bulur -- yani "burada Cince iki paragraf, Ingilizce bir paragraf" gibi
    kararlari veriyi gorerek verir, kural ezberleyerek degil.
    """
    n, m = len(a), len(b)
    ua = [len(x) for x in a]
    ub = [len(x) for x in b]
    top_a, top_b = sum(ua) or 1, sum(ub) or 1
    c = top_b / top_a          # beklenen hedef/kaynak uzunluk orani

    INF = float("inf")
    D = [[INF] * (m + 1) for _ in range(n + 1)]
    G = [[None] * (m + 1) for _ in range(n + 1)]
    D[0][0] = 0.0

    for i in range(n + 1):
        for j in range(m + 1):
            if D[i][j] == INF:
                continue
            for (di, dj), ceza in _CEZA.items():
                ni, nj = i + di, j + dj
                if ni > n or nj > m:
                    continue
                la = sum(ua[i:ni])
                lb = sum(ub[j:nj])
                payda = math.sqrt(max(1.0, c * max(la, 1) * _VARYANS))
                sapma = ((lb - c * la) / payda) ** 2
                yeni = D[i][j] + ceza + sapma
                if yeni < D[ni][nj]:
                    D[ni][nj] = yeni
                    G[ni][nj] = (i, j)

    yol, i, j = [], n, m
    while (i, j) != (0, 0):
        if G[i][j] is None:
            # Ulasilamaz durum. (0,0)'dan her (n,m)'ye tek tarafli
            # eslesmelerle gidilebildigi icin normalde olmaz; savunma
            # amacli duruyor. Eskiden burada her iki tarafa da
            # range(max(n,m)) veriliyordu ve kisa taraf icin IndexError
            # uretiyordu -- yani calissa cokecekti. sirayla() zaten
            # dogrusunu yapiyor.
            return sirayla(a, b)
        pi, pj = G[i][j]
        yol.append((list(range(pi, i)), list(range(pj, j))))
        i, j = pi, pj
    yol.reverse()
    return yol


def sirayla(a, b) -> list:
    """Hizalama yapmadan indis indis esle (--hizalamasiz)."""
    return [([i] if i < len(a) else [], [i] if i < len(b) else [])
            for i in range(max(len(a), len(b)))]


# --------------------------------------------------------- cikti


def ic_ice(kumeler, adlar, genislik, gruplar):
    etiket_g = max(len(x) for x in adlar) + 2
    govde = genislik - etiket_g

    tekil = sum(1 for g in gruplar if not g[0] or not g[1])
    coklu = sum(1 for g in gruplar if len(g[0]) > 1 or len(g[1]) > 1)
    if tekil or coklu:
        print(f"{len(gruplar)} grup: {coklu} tanesi bolunmus/birlesmis, "
              f"{tekil} tanesi tek tarafli.", file=sys.stderr)
        print(file=sys.stderr)

    for k, (ia, ib) in enumerate(gruplar, 1):
        tip = ""
        if not ia or not ib:
            tip = "  (tek tarafli)"
        elif len(ia) > 1 or len(ib) > 1:
            tip = f"  ({len(ia)}:{len(ib)})"
        bas = f"──── ¶{k}{tip} "
        print(bas + "─" * max(4, genislik - len(bas)))

        for kume, ad, indisler in zip(kumeler, adlar, (ia, ib)):
            if not indisler:
                continue
            metin = "\n".join(kume[x] for x in indisler)
            kolon = _kolon_fabrikasi(metin)
            for j, s in enumerate(_sar(metin, govde, kolon)):
                print((f"{ad}  " if j == 0 else " " * etiket_g) + s)
            print()


def yan_yana(sol, sag, sol_ad, sag_ad, genislik):
    # -4: ayirici 3 kolon + 1 emniyet payi. Tam terminal genisligine kadar
    # yazmak cogu terminalde fazladan bir satir kaydirmasi tetikler.
    sutun = (genislik - 4) // 2
    kol_sol = _kolon_fabrikasi(sol)
    kol_sag = _kolon_fabrikasi(sag)

    a = _sar(sol, sutun, kol_sol)
    b = _sar(sag, sutun, kol_sag)

    print(f"{_dolgu(sol_ad, sutun, kol_sol)} │ {sag_ad}")
    print("─" * sutun + "─┼─" + "─" * sutun)
    for i in range(max(len(a), len(b))):
        sl = a[i] if i < len(a) else ""
        sg = b[i] if i < len(b) else ""
        print(f"{_dolgu(sl, sutun, kol_sol)} │ {sg}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bolum", type=int)
    ap.add_argument("--zh", action="store_true")
    ap.add_argument("--en", action="store_true")
    ap.add_argument("--tr", action="store_true")
    ap.add_argument("--raw", action="store_true",
                    help="baslik yazma; boru ile aktarmak icin")
    ap.add_argument("--hizalamasiz", action="store_true",
                    help="hizalamayi kapat, sirayla esle")
    ap.add_argument("--sutun", action="store_true",
                    help="yan yana sutun duzeni")
    ap.add_argument("--genislik", type=int, default=None,
                    help="terminal genisligini elle ver")
    a = ap.parse_args()

    genislik = a.genislik or shutil.get_terminal_size((100, 40)).columns

    secili = [k for k in ("zh", "en", "tr") if getattr(a, k)] or ["zh", "en"]
    if a.sutun and len(secili) != 2:
        sys.exit("--sutun tam olarak iki kaynak ister")

    cilt = lotm.cilt_bul(a.bolum)
    govdeler = {}
    for k in secili:
        b = getir(k, a.bolum)
        if b is None:
            sys.exit(f"{KAYNAKLAR[k][0]}: {a.bolum}. bolum bulunamadi")
        govdeler[k] = b.metin.strip()

    if len(secili) == 1:
        k = secili[0]
        if a.raw:
            print(govdeler[k])
        else:
            yer = f" -- cilt {cilt[0]} {cilt[1]}" if cilt else ""
            print(f"=== {KAYNAKLAR[k][0]} {a.bolum}{yer} ===\n")
            print(govdeler[k])
        return

    if a.raw:
        sys.exit("--raw yalnizca tek kaynakla kullanilabilir")

    if cilt:
        print(f"bolum {a.bolum} -- cilt {cilt[0]} {cilt[1]}\n")

    if a.sutun:
        x, y = secili
        yan_yana(govdeler[x], govdeler[y],
                 KAYNAKLAR[x][0], KAYNAKLAR[y][0], genislik)
        return

    kumeler = [paragraflar(govdeler[k], KAYNAKLAR[k][2]) for k in secili]
    gruplar = (sirayla if a.hizalamasiz else hizala)(kumeler[0], kumeler[1])
    ic_ice(kumeler, [KAYNAKLAR[k][0] for k in secili], genislik, gruplar)


if __name__ == "__main__":
    main()
