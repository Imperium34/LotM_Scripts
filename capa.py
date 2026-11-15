#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capa.py -- capa kisitli hizalama.

SORUN
-----
Gale-Church'un tek ozelligi uzunluktur. Turkce'nin paragraf teamulu
Cince'ninkinden farkli olduguna gore (diyalog birlesir, uzun betimleme
bolunur) uzunluk tek basina yetmiyor ve HATA YAYILIYOR: bir yerdeki tek bir
kacirilmis birlesme, sonraki her paragrafi kaydiriyor.

Olculdu: etiket cezasi kesin'i 83'ten 64'e indirdi, ama duzyazi
standartlastirilinca 85'e cikti -- cunku Turkce dogru hâle geldikce Cince'nin
paragraf yapisindan UZAKLASIYOR. Ipucu temelli hizalamanin tavani burasi.

COZUM
-----
Iki dilde de DEGISMEDEN gecen nadir belirtecler var: ozel adlar (克莱恩/
Klein), yer adlari, rakamlar. Bunlar capa olarak bulunur (capa_bul) ve
bolum.hizala'ya YUMUSAK bir kisit olarak verilir: capali bir 1:1 eslesme
CAPA_ODULU kadar ucuzlar. Kayma o zaman cogunlukla bir sonraki ozel ada
kadar yayilir -- diyalog agirlikli bir bolumde bu birkac paragraftir.

Ilk surum SERT bir kisitti (hizala_capali: hizalama yalnizca iki capa
ARASINDA calisir, capa paragraflari zorla 1:1 baglanir). Tek bir yanlis
capa o zaman dilimi zorla bozuyordu; yumusak odul yanlis capayi uzunluk
kanitina karsi tartabildigi icin yerini aldi ve sert surum kaldirildi.

Capa hizalamanin dogrulugunu artirmaz; HATANIN MENZILINI kisaltir. Asil
kazanc budur.

IKI CAPA KAYNAGI
----------------
1. capa-sozlugu.yml: elle tutulan ozel adlar (克莱恩: Klein). Duz altdize.
2. SOZLUK TERIMLERI: sozluk.yml + words.md'de hem Cincesi hem Turkcesi
   olan her girdi (磅: libre, 便士: peni). Bolum 5'te "Beleş mi?" gibi kisa
   replikler hizalamayi uc paragraf kaydirmisti; ZH ¶46'da 磅/便士/苏勒,
   TR ¶49'da libre/peni/soli vardi -- sozlugun zaten bildigi uc cift.
   Turkce taraf lotm.desen_kur ile aranir (cekim, unlu dusmesi, tamlama
   cogulu); Cince taraf lotm.zh_desen ile (灵体 星灵体'nin icinde sayilmaz).
   Yalnizca bas bicim kullanilir, arama_adi degil: "ceket" gibi genis
   bicimler yanlis capa uretir. Yalnizca bolumde iki tarafta ESIT sayida
   ve en cok TERIM_EN_COK kez gecen terimler kullanilir. Olcumde notr,
   hedef vakalarda yararli oldugu icin acik (bkz. TERIM_CAPALARI).

Kayma denetimi (hizalama_denetle.capa_yer_degistirme) ve ceza_tara'nin
olcutu YALNIZCA 1. kaynagi kullanir: olcut degismeden kalir ki yeni
capalarin etkisi olculebilsin.

Kullanim:
    capa.py --oner                  capa adayi uret (sozluk yazmadan once)
    capa.py 16                      tek bolumun capalarini goster
    capa.py --kendini-dene          ic testler (depo gerektirmez)

Kod olarak kullanim:
    import bolum, capa
    capalar = set(capa.capa_bul(k_par, h_par, capa.sozluk_yukle()))
    gruplar = bolum.hizala(k_par, h_par, capalar)
"""

from __future__ import annotations

import argparse
import functools
import re
import sys
from bisect import bisect_left
from collections import Counter, defaultdict

CAPA_DOSYASI = "capa-sozlugu.yml"

# Sozluk terimlerinden capa (bkz. modul belgesi). ACIK.
#
# Ilk olcum (ceza_tara, 46 bolum): butun terimlerle capa, her ceza degerinde
# yer degistirmeyi ARTIRDI (400'de 97 -> 112). Sik gecen terimler (baston,
# sterlin) onlarca aday cift uretiyor ve LIS en UZUN tutarli zinciri seciyor,
# en DOGRU olani degil; Turkcenin birlestirdigi paragraflarda 1:1 odulu de
# dogru 2:1 gruplamaya karsi cekiyor. Simdi yalnizca TERIM_EN_COK kez ve iki
# tarafta ESIT sayida gecen terimler capa olur. Ikinci olcum (bu kuralla):
#     yer.deg  97 -> 99, tek 43 -> 41, dogrulanmis 10/10 -> 10/10
# yani olcutte notr; hedef vakalarda Bolum 9'un iki kayik gecisini duzeltti.
# Bu yuzden acik. Kurali gevsetmeden once ceza_tara.py ile yeniden olcun.
TERIM_CAPALARI = True
TERIM_TR_EN_AZ = 4  # daha kisa Turkce bas bicim capa olmaz ("Ay", "top")
TERIM_EN_COK = 2  # bolumde bundan sik gecen terim capa olmaz

# Turkce'de ozel ad adayi: buyuk harfle baslayan kelime.
# Cince'de kelime siniri YOKTUR, dolayisiyla bir desenle "kelime" aranamaz.
# Once "[\u4e00-\u9fff]{2,4}" denendi ve calismadi: acgozlu niceleyici
# 克莱恩克莱恩 dizisinden 克莱恩克 ve 莱恩克莱 uretiyor, aranan 克莱恩'i hic
# vermiyor. Dogrusu her konumdan 2-4 karakterlik BUTUN pencereleri uretmek;
# gercek ad, pencereler arasinda en yuksek frekansli olan olarak zaten
# one cikiyor.
_CJK_HARF = re.compile(r"[\u4e00-\u9fff]")
_TR_OZEL = re.compile(r"(?<![^\W_])[A-ZÇĞİÖŞÜ][a-zçğıöşüâîû]{2,}")
_SAYI = re.compile(r"\d+")


# ----------------------------------------------------------------- capa


def _gecisler(paragraflar, desen) -> dict:
    """belirtec -> [paragraf indisleri] (tekrarlar korunur)."""
    yer = defaultdict(list)
    for i, p in enumerate(paragraflar):
        for m in desen.finditer(p):
            yer[m.group()].append(i)
    return yer


def capa_bul(k_par, h_par, sozluk: dict, tolerans: float = 0.06, terimler=None) -> list:
    """
    (kaynak_indis, hedef_indis) capa ciftleri, artan sirada.

    ILK SURUM yalnizca AYNI SAYIDA gecen terimleri kullaniyordu: 克莱恩 12
    kez, Klein 12 kez geciyorsa k'inci gecis k'inci gecise baglanir. Temiz
    bir kuraldi ama pratikte cok az capa uretti -- Bolum 16'da 17 capa,
    aralarinda 38 paragrafliK bir bosluk.

    Sebep Turkce'nin ozne dusurmesi. Cince her cumlede 克莱恩 der; Turkce
    ayni yerde "o" der ya da ozneyi tamamen atar. Sayilar bu yuzden bir
    bolumde neredeyse hicbir zaman TAM tutmuyor ve terim -- en degerli
    capa olan Klein dahil -- o bolum icin bastan eleniyordu.

    BU SURUM goreli konuma bakiyor: bir terimin i'inci kaynak gecisi ile
    j'inci hedef gecisi, bolum icindeki oransal konumlari birbirine
    yakinsa aday sayilir. Sayilarin esit olmasi gerekmez; yanlis ciftleri
    zaten _monoton() eliyor.
    """
    n, m = max(len(k_par), 1), max(len(h_par), 1)
    ham = []

    def yakin(i, j, sinir):
        return abs(i / n - j / m) <= sinir

    def ciftle(k, h):
        # Esit sayida geciyorsa dogrudan k'inci <-> k'inci. Guclu kanit,
        # ama TEK BASINA yetmiyor: bir terim iki tarafta da birer kez
        # gecip bolumun zit uclarinda durabilir ve len(k)==len(h)==1
        # oldugu icin capa uretirdi. Esit sayida da olsa konum makul
        # olmali; sinir gevsek tutuluyor cunku sayi esitligi zaten kanit.
        if k and len(k) == len(h):
            return [(i, j) for i, j in zip(k, h) if yakin(i, j, tolerans * 3)]
        # Degilse: oransal konumu yakin olan butun ciftler aday.
        return [(i, j) for i in k for j in h if yakin(i, j, tolerans)]

    for zh, tr in sozluk.items():
        k = _gecisler(k_par, re.compile(re.escape(zh))).get(zh, [])
        h = _gecisler(h_par, re.compile(re.escape(tr))).get(tr, [])
        if k and h:
            ham.extend(ciftle(k, h))

    # Sozluk terimleri: yalnizca kaynak Cince ise (Ingilizce hizalamada
    # Cince desenler zaten eslesmez; bosuna taranmasin).
    if terimler is None:
        terimler = terim_capalari() if TERIM_CAPALARI else ()
    if terimler and any(_CJK_HARF.search(p) for p in k_par[:20]):
        k_hepsi, h_hepsi = "\n".join(k_par), "\n".join(h_par)
        for zh, _tr, zd, td in terimler:
            if zh in sozluk or not zd.search(k_hepsi) or not td.search(h_hepsi):
                continue
            k = [i for i, p in enumerate(k_par) for _ in zd.finditer(p)]
            h = [j for j, p in enumerate(h_par) for _ in td.finditer(p)]
            # Yalnizca belirsizligi olmayan yerler: esit sayida ve seyrek.
            if len(k) == len(h) <= TERIM_EN_COK:
                ham.extend(ciftle(k, h))

    # Rakamlar sozluksuz calisir: iki tarafta da Arap rakamiyla yaziliyorsa.
    ks, hs = _gecisler(k_par, _SAYI), _gecisler(h_par, _SAYI)
    for sayi, k in ks.items():
        h = hs.get(sayi, [])
        if k and h:
            ham.extend(ciftle(k, h))

    return _monoton(sorted(set(ham), key=lambda p: (p[0], -p[1])))


def _monoton(ciftler: list) -> list:
    """
    En uzun artan altdizi -- HER IKI koordinatta birden.

    Capalar celisebilir: bir isim yanlis yerde gecebilir, bir sayi
    tekrarlanabilir. Hizalama monoton olmak ZORUNDA -- ¶10 ¶40'a gidiyorsa
    ¶11 ¶39'a gidemez. Celisenleri atmak yerine EN BUYUK tutarli alt
    kumeyi tutmak, tek bir kotu capanin butun bolumu bozmasini onler.

    SIRALAMA (a, -b) OLMAK ZORUNDA. Ilk surum (a, b) siraliyordu ve LIS
    yalnizca b uzerinden hesaplandigi icin AYNI a'ya sahip ciftler zinciri
    besliyordu: Bolum 16'da tek bir kaynak paragrafi (¶19) yedi ayri hedefe
    baglanmisti (19→6, 19→7, 19→9, 19→11, 19→13, 19→18, 19→19) ve hepsi
    "gecerli" sayilmisti. Ustelik bu sahte zincirler LIS'i doyurdugu icin
    tolerans degeri hic fark yaratmiyordu: 0.06 ile 0.50 ayni 64 capayi
    veriyordu. b'yi azalan siralamak, ayni a'dan yalnizca birinin
    secilebilmesini garanti eder.
    """
    if not ciftler:
        return []
    kuyruk, izleme, onceki = [], [], [-1] * len(ciftler)
    for idx, (_a, b) in enumerate(ciftler):
        yer = bisect_left(kuyruk, b)
        if yer == len(kuyruk):
            kuyruk.append(b)
            izleme.append(idx)
        else:
            kuyruk[yer] = b
            izleme[yer] = idx
        onceki[idx] = izleme[yer - 1] if yer else -1
    yol, k = [], izleme[-1]
    while k != -1:
        yol.append(ciftler[k])
        k = onceki[k]
    return yol[::-1]


# ------------------------------------------------------------ sozluk


class _Tembel:
    """Ilk kullanimda derlenen desen. capa_bul yalnizca search/finditer kullanir."""

    __slots__ = ("_fabrika", "_desen")

    def __init__(self, fabrika):
        self._fabrika, self._desen = fabrika, None

    def _al(self):
        if self._desen is None:
            self._desen = self._fabrika()
        return self._desen

    def search(self, *a, **k):
        return self._al().search(*a, **k)

    def finditer(self, *a, **k):
        return self._al().finditer(*a, **k)

    def findall(self, *a, **k):
        return self._al().findall(*a, **k)


def capalari_kur(terimler) -> tuple:
    """
    Terim listesinden (zh, tr, zh_deseni, tr_deseni) dortluleri.

    Eleme: Turkce bas bicim TERIM_TR_EN_AZ harften kisaysa ya da Cince
    parca tek karakterse (「」 ile kasitli isaretlenmedikce) capa olmaz.
    Ayni Cince iki terimde varsa ilki kalir. Cince desen, listedeki daha
    uzun Cince terimleri haric tutar.
    """
    import lotm

    ciftler = {}
    for t in terimler:
        tr = (t.tr or "").strip()
        if not t.zh or len(tr) < TERIM_TR_EN_AZ:
            continue
        for z in str(t.zh).split("/"):
            z = z.strip()
            if z and (len(z) > 1 or t.zh_kesin):
                ciftler.setdefault(z, tr)
    hepsi = list(ciftler)
    out = []
    for z, tr in ciftler.items():
        bilesik = [b for b in hepsi if z in b and b != z]
        out.append(
            (
                z,
                tr,
                lotm.zh_desen(z, bilesik),
                _Tembel(functools.partial(lotm.desen_kur, tr, tr[:1].isupper())),
            )
        )
    return tuple(out)


@functools.lru_cache(maxsize=1)
def terim_capalari() -> tuple:
    """Sozluk + words.md'den capalar; sozluk yoksa bos (testler, tek dosya)."""
    try:
        import lotm

        return capalari_kur(lotm.sozluk_yukle(kelimeler=True).terimler)
    except (Exception, SystemExit):
        return ()


def sozluk_yukle(yol: str = CAPA_DOSYASI) -> dict:
    import yaml
    from pathlib import Path

    p = Path(yol)
    # Goreli yol calisma dizinine gore cozuluyordu: betikleri baska bir
    # klasorden cagirmak ad capalarini sessizce kapatiyordu. Yoksa betigin
    # kendi klasorune bakilir.
    if not p.is_absolute() and not p.exists():
        p = Path(__file__).resolve().parent / yol
    if not p.exists():
        print(
            f"uyarı: {yol} yok, yalnızca rakam çapaları kullanılacak", file=sys.stderr
        )
        return {}
    # C yukleyici (libyaml), yoksa saf Python; capa lotm'a bagimli degil.
    yukleyici = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    return yaml.load(p.read_text(encoding="utf-8"), Loader=yukleyici) or {}


def capa_oner(bolumler: dict, en_az: int = 5, esik: float = 0.9) -> list:
    """
    Capa sozlugu icin aday cift uretir -- elle 100 satir yazmamak icin.

    Fikir: bir ozel ad, bolumden bolume AYNI SIKLIK PROFILINI izler. 克莱恩
    hangi bolumde 40 kez geciyorsa Klein da o bolumde ~40 kez gecer. Iki
    belirtecin bolum bazli sayim vektorleri ortusuyorsa ayni seye isaret
    ediyorlardir.

    bolumler: {bolum_no: (zh_metin, tr_metin)}
    Doner: [(zh, tr, benzerlik, toplam_gecis)] -- azalan sirada.
    """
    zh_say, tr_say = defaultdict(Counter), defaultdict(Counter)
    for no, (zh, tr) in bolumler.items():
        for m in re.finditer(r"[\u4e00-\u9fff]{2,}", zh):
            blok = m.group()
            for n in (2, 3, 4):
                for i in range(len(blok) - n + 1):
                    zh_say[blok[i : i + n]][no] += 1
        for m in _TR_OZEL.finditer(tr):
            tr_say[m.group()][no] += 1

    zh_say = {k: v for k, v in zh_say.items() if sum(v.values()) >= en_az}
    tr_say = {k: v for k, v in tr_say.items() if sum(v.values()) >= en_az}

    def benzer(a: Counter, b: Counter) -> float:
        ortak = set(a) | set(b)
        ust = sum(min(a[n], b[n]) for n in ortak)
        alt = sum(max(a[n], b[n]) for n in ortak)
        return ust / alt if alt else 0.0

    cikti = []
    for zh, a in zh_say.items():
        en_iyi, skor = None, 0.0
        for tr, b in tr_say.items():
            s = benzer(a, b)
            if s > skor:
                en_iyi, skor = tr, s
        if en_iyi and skor >= esik:
            cikti.append((zh, en_iyi, skor, sum(a.values())))

    # ALTDIZE ELEME. Her konumdan 2-4 karakterlik butun pencereler
    # uretildigi icin 克莱恩 ile birlikte 克莱 ve 莱恩 da listeye giriyor ve
    # ucu de Klein'a isaret ediyor. Hepsini sozluge yazmak capayi BOZAR:
    # capa_bul sayilari ayri ayri sayar, 克莱 her 克莱恩'in icinde bir kez
    # daha gectigi icin sayilar tutmaz ve terim sessizce atlanir.
    # Ayni Turkce hedefe isaret eden ve daha uzun bir adayin ICINDE gecen
    # kisa adaylar atilir.
    hedefe_gore = defaultdict(list)
    for zh, tr, s, g in cikti:
        hedefe_gore[tr].append((zh, s, g))
    tutulan = []
    for tr, grup in hedefe_gore.items():
        uzunlar = sorted((z for z, _s, _g in grup), key=len, reverse=True)
        secilen = []
        for z in uzunlar:
            if not any(z in u for u in secilen):
                secilen.append(z)
        tutulan += [(z, tr, s, g) for z, s, g in grup if z in secilen]
    return sorted(tutulan, key=lambda x: (-x[2], -x[3]))


# ------------------------------------------------------------------ CLI


def main() -> int:
    ap = argparse.ArgumentParser(description="Çapa kısıtlı hizalama")
    ap.add_argument("bolum", nargs="?", type=int)
    ap.add_argument("--oner", action="store_true")
    ap.add_argument("--kendini-dene", action="store_true", dest="dene")
    ap.add_argument("--esik", type=float, default=0.9)
    ap.add_argument(
        "--tolerans",
        type=float,
        default=0.06,
        help="çapa eşleşmesinde izin verilen oransal konum farkı",
    )
    a = ap.parse_args()

    if a.dene:
        return kendini_dene()

    import lotm
    import bolum as B

    zh = lotm.bolum_sozlugu(lotm.bolumler_zh())
    tr = lotm.bolum_sozlugu(lotm.bolumler_tr())
    ortak = sorted(set(zh) & set(tr))

    if a.oner:
        veri = {n: (zh[n].metin, tr[n].metin) for n in ortak}
        print(f"{'ÇİNCE':<10}{'TÜRKÇE':<20}{'benzerlik':>10}{'geçiş':>7}")
        print("─" * 50)
        for z, t, s, g in capa_oner(veri, esik=a.esik):
            print(f"{z:<10}{t:<20}{s:>9.0%}{g:>7}")
        print('\nDoğru olanları capa-sozlugu.yml\'ye yazın:  "克莱恩": Klein')
        return 0

    if not a.bolum:
        sys.exit("bir bölüm numarası ya da --oner verin")

    sozluk = sozluk_yukle()
    k_par = B.paragraflar(zh[a.bolum].metin, B.KAYNAKLAR["zh"][2])
    h_par = B.paragraflar(tr[a.bolum].metin, B.KAYNAKLAR["tr"][2])
    capalar = capa_bul(k_par, h_par, sozluk, a.tolerans)
    print(f"bölüm {a.bolum}: {len(k_par)} ZH / {len(h_par)} TR, {len(capalar)} çapa")
    if capalar:
        aralik = [capalar[0][0]] + [b[0] - a_[0] for a_, b in zip(capalar, capalar[1:])]
        print(
            f"çapa aralığı: ortalama {sum(aralik) / len(aralik):.1f}, "
            f"en büyük {max(aralik)} paragraf"
        )
        print("  " + "  ".join(f"{i}→{j}" for i, j in capalar[:24]))
    return 0


# ------------------------------------------------------------------ test


def kendini_dene() -> int:
    hata = 0

    # LIS: celisen capa atilir, en buyuk tutarli kume kalir
    if _monoton([(1, 1), (2, 9), (3, 3), (4, 4)]) != [(1, 1), (3, 3), (4, 4)]:
        print("HATA: monoton filtre")
        hata += 1

    # Ayni kaynak paragrafi birden fazla hedefe baglanamaz
    cok = sorted(
        {(19, 6), (19, 7), (19, 9), (23, 20), (24, 22)}, key=lambda p: (p[0], -p[1])
    )
    s = _monoton(cok)
    if len(s) != len({a for a, _ in s}):
        print("HATA: aynı kaynak birden çok hedefe bağlandı", s)
        hata += 1

    # Ayni sayida gecmeyen terim capa uretmez
    k = ["克莱恩来了", "别的事情", "克莱恩走了"]
    h = ["Klein geldi", "başka şeyler", "başka bir cümle", "Klein gitti"]
    if len(capa_bul(k, h, {"克莱恩": "Klein"})) != 2:
        print("HATA: eşit sayılı terim çapa üretmeli")
        hata += 1
    # Sayilar esit degilse: goreli konumu YAKIN olanlar aday olur,
    # uzak olanlar elenir. Asagida iki kaynak gecisi (0/2 ve 1/2) tek bir
    # hedef gecisiyle (0/1) karsilasiyor; yalnizca ilki tolerans icinde.
    k2 = ["克莱恩来了", "başka", "克莱恩走了"]
    h2 = ["Klein geldi", "başka", "başka"]
    c2 = capa_bul(k2, h2, {"克莱恩": "Klein"}, tolerans=0.10)
    if c2 != [(0, 0)]:
        print("HATA: oransal konum filtresi", c2)
        hata += 1

    # Cok uzaktaki gecisler hic aday olmamali
    k3 = ["克莱恩"] + ["x"] * 20
    h3 = ["y"] * 20 + ["Klein"]
    if capa_bul(k3, h3, {"克莱恩": "Klein"}, tolerans=0.06):
        print("HATA: uzak eşleşme elenmeli")
        hata += 1

    # Sozluk onerisi: ayni profil yakalanmali
    veri = {
        1: ("克莱恩克莱恩克莱恩", "Klein Klein Klein"),
        2: ("克莱恩克莱恩", "Klein Klein"),
        3: ("梅丽莎梅丽莎", "Melissa Melissa"),
    }
    oneri = {z: t for z, t, _s, _g in capa_oner(veri, en_az=2)}
    if oneri.get("克莱恩") != "Klein" or oneri.get("梅丽莎") != "Melissa":
        print("HATA: çapa önerisi", oneri)
        hata += 1

    print("kendini-dene:", "geçti" if not hata else f"{hata} HATA")
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
