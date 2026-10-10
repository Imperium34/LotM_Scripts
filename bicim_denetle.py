#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bicim_denetle.py -- Turkce bolumlerde BICIM kurallarini denetler.

UST DUZEY SORU: "Bu bolumun dizgisi Sabit Cekirdek'in mutlak bicim
kurallarina uyuyor mu?" (tirnak, italik, noktalama, ilah zamiri, para
yazimi...)

Diger denetcilerden farki:
    yayim_denetle.py     terimlere bakar (sizinti, eskimis, kapi)
    kapanis_denetle.py   bir bolumu KENDI sablonuna karsi denetler
    ceviri_denetle.py    kaynak ile hedefi hizalayip karsilastirir
    bicim_denetle.py     yalnizca hedef metnin kendisine bakar; hizalama,
                         sozluk ya da sablon gerektirmez

kapanis_denetle italik ve tirnak denetimini bilerek disarida birakir
("paragraf kimligi ister, hizalama bunu tasiyamiyor"). Bu betik paragraf
kimligini hizalamadan degil hedef metnin KENDI paragraflarindan alir; o
iki madde burada denetlenir.

IKI DUZEY
---------
HATA  Kesin kural ihlali. Yanlis pozitif vermemesi icin dar tutuldu.
      Herhangi bir HATA varsa cikis kodu 1'dir (calistir.sh'de yayini
      durdurabilir).
BAK   Sezgisel. "Burada bir sorun olabilir" der, karar vermez. Tik
      sayimlari, noktali virgul, rakamla yazilmis sayilar, yazili metin
      tutarsizligi. Varsayilan olarak yalnizca sayilari yazilir; --bak
      ile tek tek listelenir.

YAYIMLANMIS BOLUMLER
--------------------
Cekirdek, yayimlanmis bolumlerdeki bicim farklarinin geriye donuk
duzeltilmeyecegini soyler. Bu yuzden bir TABAN dosyasi vardir:
    --taban-yaz taban.tsv   simdiki butun bulgulari tabana yazar
    --taban taban.tsv       tabandaki bulgulari bastirir, yalniz yenileri yazar
Anahtar (dosya, kod, alinti) ucludur; satir numarasi degildir, boylece
bir paragraf eklendiginde butun taban kaymaz.

KODLAR
------
  B01  tirnak dengesi ve cok paragrafli konusma           (§2.1)
  B02  egri tirnak / egri kesme                            (§9)
  B03  virgulle kapanan replik ("...," dedi)               (§2.1)
  B04  atiftan sonra iki nokta (dedi: "...")               (§2.1)
  B05  replik basinda uzun cizgi                           (§2.1)
  B06  italik acilip kapanmamis / kapanistan sonra bosluk yok (§2.2)
  B07  italik ic sesin icinde cift tirnak                  (§2.2)
  B08  ilah zamiri bicimi (O, O'nun, O'na)                 (Yanki #13)
  B09  sira sayili Mertebe / Derece                        (§9)
  B10  para ve saat yazimi                                 (§9)
  B11  bitisik "birsey / hicbirsey / hersey"               (§5)
  B12  Latin disi yazi (Cince vb.)                         (denetim listesi 1)
  B13  sahne kesmesi tek satirlik "..." degil              (§2.3)
  B14  noktalama boslugu                                   (imla)
  B15  noktadan sonra kucuk harfle baslayan cumle          (imla)
  K01  noktali virgul liste disinda                        (§2)
  K02  ceviri tikleri: kume ya da her gecis               (§2, §3, §5)
  K03  rakamla yazilmis kucuk sayi / para                  (§9)
  K04  devam paragrafi anlatiyla suruyor                   (§2.1)
  K08  ayni algi/tepki fiili art arda paragraflarda        (§4.4)
  K11  cumle "O," ile aciliyor (gereksiz ozne zamiri)      (§5)
  K12  bir cumlede uc "ve"                                 (§5)
  K13  yerel tekrar: bolumlere yayilmis bir kok kisa mesafede (§4.4)

Sapka, nisbet -î ve ozel ad ekleri burada YOK: sapka.py ve ad eki lint'i
onlari kapsiyor.
  K06  kod adi ya da Mertebe adi tirnak icinde             (§9)

Kullanim:
    python3 bicim_denetle.py                        # butun yayimlanmis bolumler
    python3 bicim_denetle.py 47                     # tek bolum, numarayla (bolum.py gibi)
    python3 bicim_denetle.py 46 47 --bak            # birden cok bolum, BAK ayrintilariyla
    python3 bicim_denetle.py taslak/0048.md         # klasor disindaki bir dosya
    python3 bicim_denetle.py --kod B03,B04          # yalniz bu kurallar
    python3 bicim_denetle.py --taban-yaz taban.tsv  # bir kez, yayimlanmislar icin
    python3 bicim_denetle.py --taban taban.tsv      # sonra her zaman
    python3 bicim_denetle.py --duzelt               # otomatik duzeltmeler, KURU
    python3 bicim_denetle.py 22 --duzelt --uygula   # GUVENLI olanlari yaz
"""

import argparse
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import lotm
from turkce import tr_desen, tr_kucult

HATA, BAK = "HATA", "BAK"

ACIKLAMA = {
    "B01": "tırnak dengesi / çok paragraflı konuşma",
    "B02": "eğri tırnak ya da kesme",
    "B03": "virgülle kapanan replik",
    "B04": "iki nokta + çift tırnak (atıf ya da yazılı metin)",
    "B05": "replik başında uzun çizgi",
    "B06": "italik işaretleri",
    "B07": "italik iç seste çift tırnak",
    "B08": "ilah zamiri biçimi",
    "B09": "sıra sayılı Mertebe / Derece",
    "B10": "para ve saat yazımı",
    "B11": "bitişik yazılmış belgisiz",
    "B12": "Latin dışı yazı",
    "B13": "sahne kesmesi",
    "B14": "noktalama boşluğu",
    "B15": "noktadan sonra küçük harf",
    "K01": "noktalı virgül liste dışında",
    "K02": "çeviri tikleri",
    "K03": "rakamla yazılmış küçük sayı / para",
    "K04": "devam paragrafı anlatıyla sürüyor",
    "K08": "algı/tepki fiili art arda paragraflarda",
    "K11": "cümle 'O,' ile açılıyor",
    "K12": "bir cümlede üç 've'",
    "K13": "yerel tekrar (bölümlere yayılmış kök kısa mesafede)",
    "K06": "kod adı / Mertebe adı tırnak içinde",
}


@dataclass
class Bulgu:
    kod: str
    duzey: str
    dosya: str
    satir: int
    mesaj: str
    alinti: str

    def anahtar(self):
        return (self.dosya, self.kod, self.alinti)


@dataclass
class Paragraf:
    satir: int  # dosyadaki ilk satir (front matter dahil)
    metin: str  # satir sonlari bosluga indirgenmis
    ic: list = field(default_factory=list)  # karakter tirnak icinde mi
    italik: list = field(default_factory=list)  # karakter italik icinde mi
    # [(dosya satiri, bas bosluk, metindeki baslangic, uzunluk)]: birlesik
    # metindeki bir konumu dosyadaki satir/sutuna geri cevirmek icin.
    # Duzeltme dosyaya yazilirken satir kirilimlari korunur.
    parcalar: list = field(default_factory=list)

    def dosya_konumu(self, i):
        """Birlesik metindeki i -> (satir, sutun); birlestirme boslugundaysa None."""
        for satir, bosluk, bas, uz in self.parcalar:
            if bas <= i < bas + uz:
                return satir, bosluk + (i - bas)
        return None


# ------------------------------------------------------------- okuma


def paragraflara_bol(ham: str) -> list:
    """
    Front matter atilir; satir numarasi dosyadaki gercek satirdir.
    lotm.bolumler_tr de front matter'i ayni desenle atiyor; burada ayrica
    yapilir cunku satir numarasi lazim.
    """
    fm = lotm.FRONT_MATTER.match(ham)
    ofset = ham[: fm.end()].count("\n") if fm else 0
    govde = ham[fm.end() :] if fm else ham
    out, tampon, bas, parcalar = [], [], None, []
    for i, satir in enumerate(govde.split("\n"), 1 + ofset):
        sade = satir.strip()
        if sade:
            if bas is None:
                bas = i
            konum = sum(len(x) + 1 for x in tampon)
            parcalar.append((i, len(satir) - len(satir.lstrip()), konum, len(sade)))
            tampon.append(sade)
        elif tampon:
            out.append(Paragraf(bas, " ".join(tampon), parcalar=parcalar))
            tampon, bas, parcalar = [], None, []
    if tampon:
        out.append(Paragraf(bas, " ".join(tampon), parcalar=parcalar))
    # Markdown basliklari ve HTML yorumlari metin degil.
    return [p for p in out if not p.metin.startswith(("#", "<!--"))]


def _kisalt(s: str, i: int = 0, g: int = 60) -> str:
    a = max(0, i - g)
    return ("…" if a else "") + s[a : i + g].strip() + ("…" if i + g < len(s) else "")


# ---------------------------------------------- tirnak ve italik haritasi


def tirnak_haritasi(paragraflar, dosya) -> list:
    """
    B01 ve K04. Ayni zamanda her paragrafin 'ic' maskesini doldurur:
    B04, K02 gibi kurallar anlatici ile repligi bu maskeyle ayirir.

    Cok paragrafli konusma (§2.1): ayni konusmacinin art arda gelen
    paragraflarinda yalniz SONUNCUSU kapanir, her devam paragrafi
    acilis tirnagiyla baslar:

        "birinci paragraf
        "ikinci paragraf
        "son paragraf."

    Acik kalan bir paragraftan sonra:
      - sonraki paragraf tirnakla basliyorsa bu bir DEVAM'dir; o tirnak
        yeniden acistir, kapanis degil.
      - baslamiyorsa ya kapanis tirnagi unutulmustur ya da devam
        paragrafinin acilis tirnagi. Ikisi de HATA.

    COZULEMEYEN: kapanis tirnagi unutulmus bir repligin ardindan BASKA bir
    konusmacinin tirnakla baslayan repligi gelirse yapi gecerli bir devam
    gibi gorunur. Tek ipucu, gercek devam paragraflarinin cogunlukla yalniz
    replikten olusmasidir: devam paragrafi kapanip anlatiyla suruyorsa K04
    "bak" der.
    """
    bulgular = []
    acik = False
    onceki = None
    for p in paragraflar:
        t = p.metin
        ic = [False] * len(t)
        i0 = 0
        if acik:
            if t.startswith('"'):
                i0 = 1  # yeniden acis
            else:
                bulgular.append(
                    Bulgu(
                        "B01",
                        HATA,
                        dosya,
                        onceki.satir,
                        "kapanmamış replik: sonraki paragraf tırnakla başlamıyor "
                        "(kapanış tırnağı ya da devam paragrafının açılışı eksik)",
                        _kisalt(onceki.metin, len(onceki.metin), 70),
                    )
                )
                acik = False
        durum = acik
        son_kapanis = None
        for i in range(i0, len(t)):
            if t[i] == '"':
                if durum:
                    son_kapanis = i
                durum = not durum
                continue
            ic[i] = durum
        if acik and i0:
            # Devam paragrafinda acilistan once kalan kisim da replik.
            for i in range(0, i0):
                ic[i] = True
        if acik and son_kapanis is not None and not durum:
            kalan = t[son_kapanis + 1 :].strip()
            if re.search(r"[^\W\d_]", kalan):
                # Sorun bu paragrafta degil, ONCEKINDE olabilir: o yuzden
                # onceki paragrafin sonu da gosterilir. Ikisi ayni kisinin
                # konusmasiysa (cok paragrafli replik) bulgu yanlistir.
                son = onceki.metin[-70:].strip()
                bulgular.append(
                    Bulgu(
                        "K04",
                        BAK,
                        dosya,
                        p.satir,
                        f"devam paragrafı kapanıp anlatıyla sürüyor. Önceki paragraf (satır "
                        f"{onceki.satir}) açık bitiyor: …{son}  → aynı konuşmacıysa sorun yok; "
                        f"değilse orada kapanış tırnağı eksik",
                        _kisalt(t, son_kapanis, 60),
                    )
                )
        p.ic = ic
        acik = durum
        onceki = p
        if acik and t.strip() == "...":
            acik = False
    if acik and onceki is not None:
        bulgular.append(
            Bulgu(
                "B01",
                HATA,
                dosya,
                onceki.satir,
                "bölüm açık bir replikle bitiyor",
                _kisalt(onceki.metin, len(onceki.metin), 70),
            )
        )
    return bulgular


def italik_haritasi(p: Paragraf, dosya) -> list:
    """
    B06 ve B07. Italik '_..._' ile yazilir; duzyazida baska alt cizgi yok.
    Cift sayida '_' beklenir; kapanis '_' isaretinden hemen sonra harf
    gelmemeli (§2.2: italik kapanisi ile sonraki cumle arasinda bosluk;
    Markdown italigi ancak boyle kapatir).
    """
    t = p.metin
    bulgular = []
    for m in re.finditer(r"\\_", t):
        bulgular.append(
            Bulgu(
                "B06",
                HATA,
                "",
                p.satir,
                "kaçışlı alt çizgi (\\_): sayfada italik kapanmaz, düz _ görünür",
                _kisalt(t, m.start()),
            )
        )
    yerler = [i for i, c in enumerate(t) if c == "_" and not (i and t[i - 1] == "\\")]
    p.italik = [False] * len(t)
    if len(yerler) % 2:
        bulgular.append(
            Bulgu(
                "B06",
                HATA,
                "",
                p.satir,
                "italik açılıp kapanmamış (tek sayıda _)",
                _kisalt(t, yerler[-1]),
            )
        )
        yerler = yerler[:-1]
    for a, b in zip(yerler[::2], yerler[1::2]):
        for i in range(a + 1, b):
            p.italik[i] = True
        if b + 1 < len(t) and re.match(r"[^\W_]", t[b + 1]):
            bulgular.append(
                Bulgu(
                    "B06",
                    HATA,
                    "",
                    p.satir,
                    "italik kapanışından sonra boşluk yok",
                    _kisalt(t, b),
                )
            )
        if a > 0 and re.match(r"[^\W_]", t[a - 1]):
            bulgular.append(
                Bulgu(
                    "B06",
                    HATA,
                    "",
                    p.satir,
                    "italik açılışından önce boşluk yok",
                    _kisalt(t, a),
                )
            )
        # Ic sesi TIRNAKLA sarmak yasak; ic sesin icinde bir sozu ya da
        # kelimeyi tirnakla anmak ("Sindirmek" ve "rol yapmak") serbest.
        ic_metin = t[a + 1 : b].strip()
        if (
            ic_metin.startswith('"')
            and ic_metin.rstrip(".!?…").endswith('"')
            and ic_metin.count('"') == 2
        ):
            bulgular.append(
                Bulgu(
                    "B07",
                    HATA,
                    "",
                    p.satir,
                    "iç ses tırnağa sarılmış; iç ses yalnız italiktir",
                    _kisalt(t, a),
                )
            )
    for b in bulgular:
        b.dosya = dosya
    return bulgular


# ------------------------------------------------------------ yardimcilar

# Noktali virgul cumle sonu DEGIL: ardindan kucuk harfle devam edilir.
# Iki nokta sayilir: ardindan tam cumle gelirse buyuk harf dogrudur.
_CUMLE_SONU = set(".!?…:\"'_(—–")


def cumle_basi_mi(t: str, i: int) -> bool:
    """t[i]'den once yalnizca bosluk varsa ve oncesi cumle sonuysa."""
    j = i - 1
    while j >= 0 and t[j] == " ":
        j -= 1
    return j < 0 or t[j] in _CUMLE_SONU


def _anlatida(p: Paragraf, i: int) -> bool:
    return not (p.ic and p.ic[i]) and not (p.italik and p.italik[i])


# ------------------------------------------------------------ kurallar

# B08: ilah zamiri. Bicim: buyuk O, ekler kesmeyle (O'nun, O'na).
_ZAMIR_EK = r"(?:nun|na|nu|nda|ndan|nunla|nlar|nları|nların)"
_B08_KESMESIZ = re.compile(r"\bO" + _ZAMIR_EK + r"\b")
_B08_KUCUK_KESME = re.compile(r"\bo'" + _ZAMIR_EK + r"\b")
_B08_TIRNAKLI = re.compile(r"[\"']O[\"'](?!\w)(?!\s+(?:şekl|harf|biçim))")

# B10
_PARA_ADI = r"(?:Sterlin|sterlin|soli|Soli|peni|Peni)"
_RAKAMLA_PARA = re.compile(r"\b\d[\d.]*\s+" + _PARA_ADI)
_YAZI_SAYI = (
    "bir iki üç dört beş altı yedi sekiz dokuz on yirmi otuz kırk elli "
    "altmış yetmiş seksen doksan yüz bin milyon"
).split()
_YAZIYLA_PARA = re.compile(
    r"\b(?:" + "|".join(tr_desen(s) for s in _YAZI_SAYI) + r")\s+"
    r"(?:Sterlin|soli|peni)(?![lL][iıIİ][kğ])"
)
_SAAT_NOKTALI = re.compile(r"(?<![\d.])(?:[01]?\d|2[0-3])\.[0-5]\d(?![\d.])")
_BINLIK_VIRGUL = re.compile(r"\b\d{1,3},\d{3}\b")

# B11
_B11 = re.compile(
    r"\b(?:" + "|".join(tr_desen(s) for s in ("birşey", "hiçbirşey", "herşey")) + r")"
)


# B12: Latin disi harf. Yunanca/Kiril de dahil; romanda hicbiri gecmez.
def _latin_disi(c: str) -> bool:
    if not c.isalpha():
        return False
    try:
        ad = unicodedata.name(c)
    except ValueError:
        return True
    return not ad.startswith("LATIN")


# B15: nokta + bosluk + kucuk harf. Duzyazida neredeyse her zaman ya virgul
# olmasi gereken bir nokta ("Gel. otur") ya da buyutulmemis bir cumle basi
# ("yasanmaz. o yuzden"); cogu bir duzenlemeden artakalan izdir. Istisnalar:
#   - uc nokta: "Bu... bu" kekemeligi Turkcede kucuk harfle surer
#   - rakamdan sonraki nokta: sira sayisi ("19. yuzyil")
#   - kisaltmalar ve tek harfli ad basharfleri ("vb.", "bkz.", "J.")
# Otomatik duzeltilmez: dogru duzeltme cogu zaman harfi buyutmek degil
# noktayi virgule cevirmektir; hangisi oldugunu okuyan bilir.
_B15 = re.compile(r"(?<![.…])\.\s+(?=[a-zçğıöşüâîû])")
_KISALTMA = {
    "vb",
    "vs",
    "bkz",
    "örn",
    "dr",
    "prof",
    "no",
    "s",
    "sf",
    "yy",
    "çev",
    "ed",
    "st",
    "av",
    "bay",
    "bayan",
    "sn",
    "yb",
    "alb",
    "gen",
    "mr",
    "mrs",
}

# B13: sahne kesmesi gibi gorunen ama "..." olmayan satirlar
_KESME_BENZERI = re.compile(r"^(?:[.…*·•\-–—~ ]{3,}|…)$")


# K02: tikler. (desen, etiket, yalniz anlatida mi, esik, pencere)
#
# Cekirdek tikleri TOPLAMLA degil KUMEYLE tanimlar: "ayni jest bir sahnede
# iki kez kullanilamaz", "birbiri ardina gelen paragraflarda ayni fiili
# tekrarlama". Bolumde uc "olarak" normal Turkcedir; uc paragraf icinde iki
# "derin bir nefes" hatadir. Bu yuzden her tik bir ESIK ve bir PENCERE
# (paragraf) tasir: 'esik' gecis 'pencere' paragraf icinde toplanirsa BAK.
# esik=1 olanlar her gecisinde bildirilir (gercek tikler, her kullanimi
# bakmaya deger).
#
# §4.1-A donem kaydi (akabinde, vaziyet, nizam, teferruat...) BURAYA
# EKLENMEZ: cekirdek onu "kotasiz zemin" sayar. Onlardan biri tekrar
# ediyorsa bu bir kayit degil tekrar sorunudur; K13 yakalar.
def _tik(desen, etiket, anlatida, esik, pencere):
    return (re.compile(desen), etiket, anlatida, esik, pencere)


_TIKLER = [
    _tik(r"\b" + tr_desen("gayriihtiyari"), "gayriihtiyari", False, 1, 1),
    _tik(tr_desen("bir anlığına donakal"), "bir anlığına donakal-", False, 1, 1),
    _tik(tr_desen("derin bir nefes"), "derin bir nefes", False, 2, 12),
    _tik(r"\b" + tr_desen("olarak") + r"\b", "olarak", True, 3, 6),
    _tik(r"\b" + tr_desen("sahip ol"), "sahip ol-", True, 2, 8),
    _tik(
        r"\b[^\W\d_]+(?:mekte|makta)(?:dır|dir|ydı|ydi|ydılar|ydiler)?\b",
        "-mekte/-makta",
        True,
        2,
        6,
    ),
    _tik(r"\b" + tr_desen("gerçekleştir"), "gerçekleştir-", False, 2, 10),
    _tik(
        r"\b"
        + tr_desen("sağla")
        + r"(?:dı|dığ|yan|yarak|yıp|r\b|rd|mış|mak|ma[sy]|yacak|yor)",
        "sağla-",
        True,
        2,
        10,
    ),
    _tik(r"\b" + tr_desen("açısından") + r"\b", "açısından", True, 2, 10),
    _tik(r"\b" + tr_desen("ilişkin") + r"\b", "ilişkin", True, 2, 10),
    # §2 ani gecis: tek aile, cunku ayni tik ("Aniden", "Birden", "O an").
    _tik(
        r"\b(?:"
        + "|".join(
            tr_desen(s)
            for s in (
                "aniden",
                "birden",
                "bir anda",
                "o anda",
                "tam o esnada",
                "o esnada",
                "tam o sırada",
            )
        )
        + r"|[oO] an)\b",
        "ani geçiş (aniden/birden/o an…)",
        True,
        2,
        4,
    ),
    # §3 duyguyu gozle etiketlemek
    _tik(
        tr_desen("gözlerinde")
        + r"\b[^.!?\"]{0,40}?\b(?:"
        + "|".join(
            tr_desen(s) for s in ("parla", "yan", "beliren", "ışıltı", "ışık", "çak")
        )
        + r")",
        "göz metaforu",
        True,
        1,
        1,
    ),
    _tik(
        tr_desen("gözleri")
        + r"\b[^.!?\"]{0,40}?(?:\s"
        + tr_desen("ile")
        + r"|l[ae])\s+"
        + tr_desen("dol"),
        "göz metaforu",
        True,
        1,
        1,
    ),
]


# K03: rakamla kucuk sayi (birim, yil, saat, Mertebe/Sinif disinda)
_KUCUK_RAKAM = re.compile(
    r"(?<![\w.,:/-])([1-9]\d?)(?![\w.,:/%-]|\s*(?:\.|-?\s*(?:inci|ıncı|nci|ncı|uncu|üncü)))"
)
_RAKAM_ISTISNA = re.compile(
    r"^\s*(?:mililitre|litre|gram|kilogram|metre|santimetre|kilometre|derece|"
    r"yaş|mil|fit|inç|°)",
    re.I,
)
_RAKAM_ONCE_ISTISNA = re.compile(r"(?:Mertebe|Sınıf|Bölüm|bölüm|¶)\s*$")

# B04: anlatida iki nokta + CIFT tirnak her durumda ihlaldir:
#   - onceki kelime bir atif fiiliyse ("konustu:", "Klein'a dondu:") ardindan
#     replik gelir ve replik iki noktayla acilmaz (§2.1);
#   - degilse ("su ibare yer aliyordu:", "basligi gordu:") ardindan yazili bir
#     metin ya da anma gelir ve ev bicimi onu TEK tirnakla yazar
#     ('Siyah sacli, lacivert gozlu...').
# Ilk surumde ikinci hal BAK'ti (K07); yayimlanmis 6 ornegin altisi da tek
# tirnak olmasi gereken yerlerdi. Atif fiili yalnizca mesaji secer.
_ATIF_FIILI = re.compile(
    r"(?:konuş|ded|sor|ekle|söyle|bağır|fısılda|mırılda|seslen|haykır|yanıtla|"
    r"açıkla|anlat|emret|uyar|homurdan|kıkırda|gül|dön|verdi|girdi|etti|"
    r"başla|fırlat|kes|tekrarla)\w*$"
)


def paragraf_kurallari(p: Paragraf, dosya: str, kod_adlari) -> list:
    t = p.metin
    out = []

    def ekle(kod, duzey, mesaj, i):
        out.append(Bulgu(kod, duzey, dosya, p.satir, mesaj, _kisalt(t, i)))

    # B02
    for m in re.finditer(r"[“”„‟«»‘’‚‛]", t):
        ekle(
            "B02",
            HATA,
            f"eğri işaret '{m.group()}'; düz \" ya da ' kullanılır",
            m.start(),
        )

    # B03: tirnagin kapanisindan hemen once virgul. Turkcede tirnak icindeki
    # cumle kendi noktalamasiyla kapanir: "Gel." dedi.
    for m in re.finditer(r',"', t):
        if p.ic and m.start() < len(p.ic) and p.ic[m.start()]:
            ekle(
                "B03",
                HATA,
                'virgülle kapanan replik; tırnak kendi noktalamasıyla kapanır: "Gel." dedi',
                m.start(),
            )

    # B04: replik disinda iki nokta + acilis tirnagi; ya da paragraf iki
    # noktayla bitip sonraki tirnakla basliyor (o hali dosya duzeyinde).
    for m in re.finditer(r':\s*"', t):
        if not _anlatida(p, m.start()):
            continue
        onceki = re.findall(r"[^\W\d_]+", t[max(0, m.start() - 40) : m.start()])
        if onceki and _ATIF_FIILI.search(tr_kucult(onceki[-1])):
            ekle(
                "B04",
                HATA,
                "atıftan sonra iki nokta; replik iki noktayla açılmaz",
                m.start(),
            )
        else:
            ekle(
                "B04",
                HATA,
                "iki nokta + çift tırnak: replikse iki nokta kalkar, "
                "yazılı metin ya da anmaysa tek tırnak",
                m.start(),
            )

    # B05
    if re.match(r'^"?\s*[—–]', t):
        ekle("B05", HATA, "replik başında uzun çizgi", 0)

    # B08
    for m in _B08_KESMESIZ.finditer(t):
        if not cumle_basi_mi(t, m.start()):
            ekle(
                "B08",
                HATA,
                f"cümle ortasında '{m.group()}': ilah zamiri kesmeyle yazılır (O'{m.group()[1:]})",
                m.start(),
            )
    for m in _B08_KUCUK_KESME.finditer(t):
        ekle(
            "B08",
            HATA,
            f"'{m.group()}': kesme yalnız büyük harfli ilah zamirinde (O'nun)",
            m.start(),
        )
    for m in _B08_TIRNAKLI.finditer(t):
        ekle("B08", HATA, "ilah zamiri tırnak içinde; tırnaksız büyük O", m.start())

    # B09
    for m in re.finditer(r"\b\d+\.\s*(?:Mertebe|Derece)", t):
        ekle(
            "B09",
            HATA,
            "sıra sayılı biçim; 'Mertebe 9', 'Sınıf 0' kullanılır",
            m.start(),
        )

    # B10
    for m in re.finditer(r"\bsterlin", t):
        ekle("B10", HATA, "Sterlin büyük harfle yazılır", m.start())
    for m in re.finditer(r"\b(?:Soli|Peni)\b", t):
        if not cumle_basi_mi(t, m.start()):
            ekle(
                "B10",
                HATA,
                f"'{m.group()}' cümle ortasında küçük harfle yazılır",
                m.start(),
            )
    for m in _BINLIK_VIRGUL.finditer(t):
        ekle("B10", HATA, "binlik ayırıcı nokta olmalı (1.250)", m.start())
    for m in _SAAT_NOKTALI.finditer(t):
        ekle("B10", HATA, "kesin saat iki noktayla yazılır (11:55)", m.start())
    rakam = list(_RAKAMLA_PARA.finditer(t))
    yazi = list(_YAZIYLA_PARA.finditer(t))
    if rakam and yazi:
        # Hangi tutarin aykiri oldugunu soyle; "karisik" demek yetmiyor.
        # Iki ya da daha fazla rakamli tutar varsa bu bir hesap paragrafidir
        # ve yazili olanlar rakama cevrilir (§9 para, madde 2).
        if len(rakam) >= len(yazi):
            for m in yazi:
                ekle(
                    "B10",
                    HATA,
                    f"hesap paragrafında tutar yazıyla kalmış: '{m.group()}' → rakamla",
                    m.start(),
                )
        else:
            for m in rakam:
                ekle(
                    "B10",
                    HATA,
                    f"paragraftaki tutarlar yazıyla, bu rakamla: '{m.group()}' → yazıyla",
                    m.start(),
                )

    # B11
    for m in _B11.finditer(t):
        ekle("B11", HATA, f"'{m.group()}' ayrı yazılır", m.start())

    # B12
    for i, c in enumerate(t):
        if _latin_disi(c):
            ekle("B12", HATA, f"Latin dışı karakter '{c}'", i)
            break

    # B13
    if _KESME_BENZERI.match(t.strip()) and t.strip() != "...":
        ekle("B13", HATA, "sahne kesmesi tek satırlık '...' ile verilir", 0)

    # B14: noktalama boslugu. Uc nokta kendi kurallariyla serbest.
    for m in re.finditer(r"(?<=\S) +([,;?!]|\.(?!\.))", t):
        ekle("B14", HATA, f"'{m.group(1)}' işaretinden önce boşluk", m.start())
    for m in re.finditer(r"[,;](?=[^\s\d\"'_)\]—–.…])", t):
        ekle("B14", HATA, f"'{m.group()}' işaretinden sonra boşluk yok", m.start())
    for m in re.finditer(r"(?<![.\d])[.!?](?=[A-ZÇĞİÖŞÜ])", t):
        ekle("B14", HATA, f"'{m.group()}' işaretinden sonra boşluk yok", m.start())
    for m in re.finditer(r"  +", t):
        ekle("B14", HATA, "çift boşluk", m.start())
        break

    # B15
    for m in _B15.finditer(t):
        onceki = re.search(r"(\S+)$", t[: m.start()])
        kelime = onceki.group(1) if onceki else ""
        if not kelime or kelime[-1].isdigit():
            continue
        if tr_kucult(kelime.strip("\"'_(")) in _KISALTMA or re.fullmatch(
            r"[A-ZÇĞİÖŞÜ]", kelime.strip("\"'_(")
        ):
            continue
        ekle(
            "B15",
            HATA,
            "noktadan sonra küçük harf: nokta virgül mü olmalı, yoksa harf mi büyümeli?",
            m.start(),
        )

    # K01: noktali virgul, ayni cumlede ondan once virgul yoksa liste degil.
    for m in re.finditer(";", t):
        bas = max(
            t.rfind(". ", 0, m.start()),
            t.rfind("? ", 0, m.start()),
            t.rfind("! ", 0, m.start()),
            t.rfind('"', 0, m.start()),
        )
        if "," not in t[bas + 1 : m.start()]:
            ekle(
                "K01",
                BAK,
                "iki bağımsız cümle noktalı virgülle bağlanmış olabilir",
                m.start(),
            )

    # K03. Hesap ya da belge paragrafinda (en az uc rakamli sayi: bir kira
    # hesabi, bir ilan, bir makbuz) rakam cekirdegin kendi kuralidir
    # (§9 para, madde 2 ve 3); oradaki kucuk sayilar sayilmaz.
    hesap_paragrafi = len(re.findall(r"(?<![\w.])\d+", t)) >= 3
    for m in [] if hesap_paragrafi else _KUCUK_RAKAM.finditer(t):
        sonra, once = t[m.end() : m.end() + 14], t[max(0, m.start() - 12) : m.start()]
        if _RAKAM_ISTISNA.match(sonra) or _RAKAM_ONCE_ISTISNA.search(once):
            continue
        ekle(
            "K03",
            BAK,
            f"'{m.group(1)}' rakamla; doksan dokuza kadar yazıyla",
            m.start(),
        )
    if rakam and not yazi and len(rakam) == 1 and not hesap_paragrafi:
        ekle(
            "K03",
            BAK,
            "para rakamla; paragrafta kıyas yoksa ve iki sözcüğü geçmiyorsa yazıyla",
            rakam[0].start(),
        )

    # K06: kod adi / Mertebe adi tirnak icinde. Cekirdek istisna taniyor
    # (ad henuz ad degilse tirnak korunur), o yuzden BAK.
    if kod_adlari is not None:
        for m in kod_adlari.finditer(t):
            ekle(
                "K06",
                BAK,
                f"{m.group()} tırnak içinde; kod ve Mertebe adları tırnaksız",
                m.start(),
            )

    return out


def dosya_kurallari(paragraflar, dosya) -> list:
    """Paragraflar arasi kurallar: B04'un paragraf siniri hali."""
    out = []
    for a, b in zip(paragraflar, paragraflar[1:]):
        m = a.metin.rstrip()
        if not (m.endswith(":") and b.metin.startswith('"')):
            continue
        i = len(m) - 1
        if a.ic and i < len(a.ic) and a.ic[i]:
            continue  # repligin icindeki iki nokta serbest (§2.1)
        onceki = re.findall(r"[^\W\d_]+", m[-40:])
        if onceki and _ATIF_FIILI.search(tr_kucult(onceki[-1])):
            out.append(
                Bulgu(
                    "B04",
                    HATA,
                    dosya,
                    a.satir,
                    "paragraf atıf ve iki noktayla bitiyor, sonraki replikle açılıyor",
                    _kisalt(a.metin, len(a.metin)),
                )
            )
        else:
            out.append(
                Bulgu(
                    "B04",
                    HATA,
                    dosya,
                    a.satir,
                    "paragraf iki noktayla bitiyor, sonraki çift tırnakla açılıyor: "
                    "replikse iki nokta kalkar, yazılı metinse tek tırnak",
                    _kisalt(a.metin, len(a.metin)),
                )
            )
    return out


def tik_kumeleri(paragraflar, dosya):
    """
    K02. Her tik icin paragraf numaralarini toplar, 'pencere' paragraf
    icinde 'esik' gecis varsa kumenin SON gecisini bildirir (ilkine de atif
    yapar). Ayni kume iki kez bildirilmez.
    Ayrica eski sayim tablosu icin toplamlari doner (--tik-sayim).
    """
    say, out = Counter(), []
    for desen, etiket, anlatida, esik, pencere in _TIKLER:
        yerler = []  # (paragraf sirasi, Paragraf, konum)
        for i, p in enumerate(paragraflar):
            for m in desen.finditer(p.metin):
                if anlatida and not _anlatida(p, m.start()):
                    continue
                yerler.append((i, p, m.start()))
        say[etiket] += len(yerler)
        son_bildirilen = -1
        for k in range(len(yerler)):
            if esik == 1:
                i, p, c = yerler[k]
                out.append(
                    Bulgu(
                        "K02",
                        BAK,
                        dosya,
                        p.satir,
                        f"tik: {etiket}",
                        _kisalt(p.metin, c),
                    )
                )
                continue
            if k + 1 < esik:
                continue
            ilk = yerler[k - esik + 1]
            i, p, c = yerler[k]
            if i - ilk[0] < pencere and k - esik + 1 > son_bildirilen:
                out.append(
                    Bulgu(
                        "K02",
                        BAK,
                        dosya,
                        p.satir,
                        f"tik kümesi: {etiket} — {esik} kez {i - ilk[0] + 1} paragraf içinde "
                        f"(ilki satır {ilk[1].satir})",
                        _kisalt(p.metin, c),
                    )
                )
                son_bildirilen = k
    return out, say


# K08: §4.4, ayni algi/tepki fiili art arda paragraflarda (anlatida).
# "secti" bilerek yok: "Klein Kahin'i secti" (tercih) ile ayirt edilemez.
def _fiil(kok, ekler):
    return re.compile(r"\b" + tr_desen(kok) + r"(?:" + ekler + r")")


_ALGI_FIILLERI = [
    (
        "gör-",
        _fiil(
            "gör", r"dü|müş|ünce|ürken|üyordu|düğü|dükleri|düğünde|en\b|erek|mesiyle"
        ),
    ),
    ("bak-", _fiil("bak", r"tı|mış|ınca|arken|ıyordu|tığı|ıp|arak|an\b")),
    ("sez-", _fiil("sez", r"di|miş|ince|erek|en\b|diği|iyordu")),
    ("fark et-", re.compile(tr_desen("fark") + r"\s+e[td]")),
    ("algıla-", _fiil("algıla", r"\w*")),
    ("hisset-", re.compile(r"\b" + tr_desen("hisse") + r"[td]")),
    ("irkil-", _fiil("irkil", r"\w*")),
    ("ürper-", _fiil("ürper", r"\w*")),
    ("donakal-", _fiil("donakal", r"\w*")),
]


def algi_tekrari(paragraflar, dosya):
    out = []
    onceki = {}
    for p in paragraflar:
        simdi = {}
        for ad, desen in _ALGI_FIILLERI:
            for m in desen.finditer(p.metin):
                if _anlatida(p, m.start()):
                    simdi.setdefault(ad, m.start())
        for ad, c in simdi.items():
            if ad in onceki:
                out.append(
                    Bulgu(
                        "K08",
                        BAK,
                        dosya,
                        p.satir,
                        f"'{ad}' art arda iki paragrafta; edimi düşür ya da algıyı bedene kaydır",
                        _kisalt(p.metin, c),
                    )
                )
        onceki = simdi
    return out


# K11, K12: §5
_O_VIRGUL = re.compile(r"(?:^|[.!?…]\s+|\"\s*)(O),\s")


def ozne_ve_baglac(p, dosya):
    out = []
    for m in _O_VIRGUL.finditer(p.metin):
        out.append(
            Bulgu(
                "K11",
                BAK,
                dosya,
                p.satir,
                "cümle 'O,' ile açılıyor; özne zamiri işaretli bir tercihtir (vurgu yoksa düşer)",
                _kisalt(p.metin, m.start(1)),
            )
        )
    for cumle in re.finditer(r"[^.!?…]+", p.metin):
        if len(re.findall(r"\bve\b", cumle.group())) >= 3:
            out.append(
                Bulgu(
                    "K12",
                    BAK,
                    dosya,
                    p.satir,
                    "bir cümlede üç 've'; ulaç ya da sıfat-fiille bağla",
                    _kisalt(p.metin, cumle.start() + cumle.group().find(" ve ")),
                )
            )
    return out


# K13: yerel tekrar ("pet word"). Ayni kok kisa bir mesafede iki kez.
#
# Sorun su ayrimdir: bir matara sahnesinde "matara"nin tekrari dogaldir,
# "tekinsiz"in ayni cumlede iki kez gecmesi degildir. Ayrimi DERLEM yapar,
# ama sezgiye ters yonde: cevirmenin sevdigi kelime TANIMI GEREGI bolumlere
# YAYILMISTIR (tekinsiz, fevkalade, nihayetinde), sahne nesnesi ise tek bir
# bolumde toplanir. Bu yuzden yalniz ORTA bantta kalan kokler sayilir:
#   - cok az bolumde gecen (sahneye ozgu: matara, portre)   -> elenir
#   - bolumlerin cogunda gecen (kendi, sonra, ancak)        -> elenir
# Ayrica:
#   - yalniz anlatida; replikteki tekrar karakterin sesidir
#   - mesafe 1-2 kelime sayilmaz: ikileme ("zangir zangir", "yavas yavas")
#     Turkcenin kendi aracidir
#   - ozel adlar (cumle ortasinda buyuk harfle yazilanlar) hic sayilmaz
_K13_KOK = 6
_K13_MESAFE = 50  # kelime
_K13_EN_AZ = 2  # ikileme siniri: bundan yakin tekrar sayilmaz
_K13_ALT = 0.10  # bolumlerin bundan azinda geciyorsa sahneye ozgu
_K13_ALT_MUTLAK = 3  # ...ve en az bu kadar bolumde gecmeli
_K13_YAYGIN = 0.80  # bolumlerin bu kadarinda geciyorsa siradan
_K13_UST = 5  # bolum basina en cok


def _kelimeler(paragraflar):
    """(kok, ham, paragraf, konum, sira) -- ozel adlar ayiklanmis."""
    out, sira, adlar = [], 0, set()
    for p in paragraflar:
        for m in re.finditer(r"[^\W\d_]+", p.metin):
            ham = m.group()
            if len(ham) < _K13_KOK:
                sira += 1
                continue
            kok = tr_kucult(ham)[:_K13_KOK]
            if ham[0].isupper() and not cumle_basi_mi(p.metin, m.start()):
                adlar.add(kok)
            if _anlatida(p, m.start()):
                out.append((kok, ham, p, m.start(), sira))
            sira += 1
    return [w for w in out if w[0] not in adlar]


def belge_frekansi(bolum_paragraflari) -> tuple:
    df = Counter()
    for _dosya, pler in bolum_paragraflari:
        df.update({w[0] for w in _kelimeler(pler)})
    return df, len(bolum_paragraflari)


def yerel_tekrar(paragraflar, dosya, df, n_bolum):
    if not n_bolum:
        return []
    son = {}
    adaylar = {}
    alt = max(_K13_ALT_MUTLAK, _K13_ALT * n_bolum)
    for kok, ham, p, c, sira in _kelimeler(paragraflar):
        d = df.get(kok, 0)
        if d < alt or d / n_bolum >= _K13_YAYGIN:
            continue
        if kok in son and _K13_EN_AZ < sira - son[kok][0] <= _K13_MESAFE:
            mesafe = sira - son[kok][0]
            puan = 1 / mesafe
            if kok not in adaylar or puan > adaylar[kok][0]:
                adaylar[kok] = (puan, ham, son[kok][1], mesafe, p, c)
        son[kok] = (sira, ham)
    # Tavan YOK: sayi normdan sapma olcumune girer, tavan onu duzlestirirdi
    # (her bolum 5'te kalirdi). Puan sirasiyla doner; --bak yazdirirken
    # bolum basina ilk _K13_UST tanesi gosterilir.
    out = []
    for kok, (puan, ham, onceki, mesafe, p, c) in sorted(
        adaylar.items(), key=lambda kv: -kv[1][0]
    ):
        out.append(
            Bulgu(
                "K13",
                BAK,
                dosya,
                p.satir,
                f"'{onceki}' … '{ham}' {mesafe} kelime arayla; kök bölümlere yayılmış bir tercih",
                _kisalt(p.metin, c),
            )
        )
    return out


def kod_adi_deseni(sozluk_yolu=None):
    """
    K06 icin: Tarot Cemiyeti kod adlari ve Mertebe adlari, tirnak icinde.
    Sozluk okunamazsa None (kural atlanir, sessizce degil: stderr'e yazilir).
    """
    try:
        s = lotm.sozluk_yukle(sozluk_yolu)
    except (Exception, SystemExit) as e:
        print(f"  uyari: sözlük okunamadı ({e}); K06 atlandı.", file=sys.stderr)
        return None
    adlar = set()
    for t in s.terimler:
        kat = getattr(t, "kategori", "") or ""
        if kat == "Tarot Cemiyeti" or t.seviye is not None:
            if t.tr and len(t.tr) > 2:
                adlar.add(t.tr)
    if not adlar:
        return None
    alt = "|".join(sorted((re.escape(a) for a in adlar), key=len, reverse=True))
    return re.compile(r"[\"'](?:" + alt + r")[\"']")


# ---------------------------------------------------- otomatik duzeltme
#
# sapka.py ile ayni duzen: varsayilan KURU (yalniz gosterir), --uygula
# yazar. Iki liste:
#   GUVENLI  mekanik; bir kural, tek bir dogru sonuc. --uygula bunlari yazar.
#   ELLE     ayni kural ama sonuc yargi ister (yeniden kurulacak cumle,
#            ek uyumu degisen sayi). Yalniz listelenir, dokunulmaz.
#
# GUVENLI olanlar:
#   B03  "Gel," dedi          -> "Gel." dedi      (atif fiili yakinda ise)
#   B10  sterlin -> Sterlin;  cumle ortasinda Soli/Peni -> soli/peni
#   B02  egri tirnak/kesme    -> duz
#   B11  birsey/hicbirsey/hersey -> ayri
#   B14  noktalamadan once bosluk, cift bosluk
#   B13  "* * *" vb.          -> "..."
#   B06  kacisli alt cizgi    -> _
# ELLE kalanlar: atifin repligi boldugu B03 ("Ne var ki," dedi Neil,
# "bizim..."), italik icindeki B03, atif fiili bulunamayan B03 (tirnakla
# anilan bir kelime olabilir), B09 (9. Mertebe'den -> Mertebe 9'dan: ek
# degisir), B04, B01, B05, B07, B08, B10'un karisik para / saat / binlik
# halleri, noktalamadan sonra eksik bosluk (M.O. gibi kisaltmalar).


@dataclass
class Duzeltme:
    kod: str
    p: "Paragraf"
    bas: int  # birlesik metinde
    son: int
    yeni: str
    guvenli: bool
    neden: str = ""


_ATIF_DE = re.compile(
    r"^(?:dedi|diye|diyerek|diyen|derken|deyip|deyince|demek|der|dediğinde)"
)


def _atif_yakinda(metin: str) -> bool:
    for k in re.findall(r"[^\W\d_]+", metin)[:6]:
        k = tr_kucult(k)
        if _ATIF_DE.match(k) or _ATIF_FIILI.search(k):
            return True
    return False


def duzeltmeleri_bul(p: "Paragraf") -> list:
    t = p.metin
    out = []

    def ekle(kod, bas, son, yeni, guvenli=True, neden=""):
        out.append(Duzeltme(kod, p, bas, son, yeni, guvenli, neden))

    # B03
    for m in re.finditer(r',"', t):
        i = m.start()
        if not (p.ic and i < len(p.ic) and p.ic[i]):
            continue
        kalan = t[i + 2 :]
        sonraki = kalan.find('"')
        ara = kalan[:sonraki] if sonraki >= 0 else kalan
        if p.italik and p.italik[i]:
            ekle(
                "B03",
                i,
                i + 1,
                ".",
                False,
                "italik iç ses içinde; anma mı replik mi, okuyarak karar verin",
            )
        elif (
            sonraki >= 0
            and not re.search(r"[.!?…]", ara)
            and sonraki + 1 < len(kalan)
            and kalan[sonraki + 1].islower()
        ):
            ekle(
                "B03",
                i,
                i + 1,
                ".",
                False,
                "atıf repliği bölüyor; cümle yeniden kurulmalı",
            )
        elif not _atif_yakinda(ara):
            ekle(
                "B03",
                i,
                i + 1,
                ".",
                False,
                "yakında atıf fiili yok; tırnakla anılan bir kelime olabilir",
            )
        else:
            ekle("B03", i, i + 1, ".")

    # B10
    for m in re.finditer(r"\bsterlin", t):
        ekle("B10", m.start(), m.start() + 1, "S")
    for m in re.finditer(r"\b(?:Soli|Peni)\b", t):
        if not cumle_basi_mi(t, m.start()):
            ekle("B10", m.start(), m.start() + 1, t[m.start()].lower())

    # B02
    for m in re.finditer(r"[“”„‟«»]", t):
        ekle("B02", m.start(), m.end(), '"')
    for m in re.finditer(r"[‘’‚‛]", t):
        ekle("B02", m.start(), m.end(), "'")

    # B11
    for m in _B11.finditer(t):
        w = m.group()
        k = tr_kucult(w)
        ayri = {"birşey": "bir şey", "hiçbirşey": "hiçbir şey", "herşey": "her şey"}[k]
        if w[0].isupper():
            ayri = ayri[0].upper() + ayri[1:]
        ekle("B11", m.start(), m.end(), ayri)

    # B14
    for m in re.finditer(r"(?<=\S)( +)(?=[,;?!]|\.(?!\.))", t):
        ekle("B14", m.start(1), m.end(1), "")
    for m in re.finditer(r"(?<=\S)  +(?=\S)", t):
        ekle("B14", m.start(), m.end(), " ")

    # B13
    sade = t.strip()
    if _KESME_BENZERI.match(sade) and sade != "...":
        ekle("B13", 0, len(t), "...")

    # B06
    for m in re.finditer(r"\\_", t):
        ekle("B06", m.start(), m.end(), "_")

    # Cakisan duzeltmeler (ayni yere iki kural) yazilmaz; ilki kalir.
    out.sort(key=lambda d: (d.bas, d.son))
    temiz, son = [], -1
    for d in out:
        if d.bas >= son:
            temiz.append(d)
            son = max(son, d.son)
    return temiz


def _satir(d: Duzeltme) -> int:
    """Duzeltmenin dosyadaki GERCEK satiri (paragrafin ilk satiri degil)."""
    k = d.p.dosya_konumu(d.bas)
    return k[0] if k else d.p.satir


def _onizleme(d: Duzeltme, g: int = 40) -> tuple:
    t = d.p.metin
    a, b = max(0, d.bas - g), min(len(t), d.son + g)
    on = ("…" if a else "") + t[a:b] + ("…" if b < len(t) else "")
    son = (
        ("…" if a else "")
        + t[a : d.bas]
        + d.yeni
        + t[d.son : b]
        + ("…" if b < len(t) else "")
    )
    return on, son


def duzelt(yollar, kod_adlari, taban, kodlar, uygula: bool) -> int:
    """
    Kuru ya da yazan duzeltme gecisi. Taban verilmisse tabandaki
    bulgulara dokunulmaz (kabul edilmis gecmis). Doner: yazilan
    duzeltme sayisi.
    """
    toplam_g, toplam_e, yazilan, dosya_sayisi = 0, 0, 0, 0
    print(
        "=== OTOMATİK DÜZELTME ("
        + ("YAZILIYOR" if uygula else "KURU — hiçbir dosya değişmez")
        + ") ==="
    )
    for yol in yollar:
        ham = yol.read_text(encoding="utf-8")
        pler, bulgular, _ = dosyayi_denetle(yol, kod_adlari)
        dosya = yol.name
        duzeltmeler = []
        for p in pler:
            for d in duzeltmeleri_bul(p):
                if kodlar and d.kod not in kodlar:
                    continue
                if taban and (dosya, d.kod, _kisalt(p.metin, d.bas)) in taban:
                    continue
                duzeltmeler.append(d)
        # Duzeltme motorunun kapsamadigi HATA'lar da ELLE listesine.
        kapsanan = {"B02", "B03", "B11", "B13"}
        elle_bulgu = [
            b
            for b in bulgular
            if b.duzey == HATA
            and b.anahtar() not in (taban or set())
            and (not kodlar or b.kod in kodlar)
            and (
                b.kod not in kapsanan
                and not (b.kod == "B10" and "büyük harf" in b.mesaj)
                and not (b.kod == "B10" and "küçük harf" in b.mesaj)
                and not (b.kod == "B06" and "kaçışlı" in b.mesaj)
                and not (
                    b.kod == "B14"
                    and ("önce boşluk" in b.mesaj or "çift boşluk" in b.mesaj)
                )
            )
        ]
        guvenli = [d for d in duzeltmeler if d.guvenli]
        elle = [d for d in duzeltmeler if not d.guvenli]
        if not (guvenli or elle or elle_bulgu):
            continue
        dosya_sayisi += 1
        print(f"\n{dosya}")
        if guvenli:
            print(f"  GÜVENLİ ({len(guvenli)})")
            for d in guvenli:
                on, son = _onizleme(d)
                print(f"    {_satir(d):>4}  {d.kod}  {on}\n                →  {son}")
        if elle or elle_bulgu:
            print(f"  ELLE ({len(elle) + len(elle_bulgu)})")
            for d in elle:
                on, _s = _onizleme(d)
                print(f"    {_satir(d):>4}  {d.kod}  {d.neden}\n                {on}")
            for b in sorted(elle_bulgu, key=lambda b: b.satir):
                print(
                    f"    {b.satir:>4}  {b.kod}  {b.mesaj}\n                {b.alinti}"
                )
        toplam_g += len(guvenli)
        toplam_e += len(elle) + len(elle_bulgu)
        if uygula and guvenli:
            satirlar = ham.split("\n")
            yer = []
            atlanan = 0
            for d in guvenli:
                a, b = d.p.dosya_konumu(d.bas), d.p.dosya_konumu(max(d.son - 1, d.bas))
                if d.son == d.bas:  # bos aralik (olmaz ama)
                    continue
                if a is None or b is None or a[0] != b[0]:
                    atlanan += 1  # satir kirilimina denk geliyor; elle
                    continue
                yer.append((a[0], a[1], b[1] + 1, d.yeni))
            for satir, s1, s2, yeni in sorted(
                yer, key=lambda x: (x[0], x[1]), reverse=True
            ):
                s = satirlar[satir - 1]
                satirlar[satir - 1] = s[:s1] + yeni + s[s2:]
            lotm.atomik_yaz(yol, "\n".join(satirlar))
            yazilan += len(yer)
            if atlanan:
                print(
                    f"  ({atlanan} düzeltme satır kırılımına denk geldi, yazılmadı; elle bakın)"
                )
    print(
        f"\n--- ÖZET: {toplam_g} güvenli düzeltme, {toplam_e} elle, {dosya_sayisi} dosyada ---"
    )
    if uygula:
        print(f"  {yazilan} düzeltme yazıldı. Diff'i okuyun: git diff")
    elif toplam_g:
        print("  yazmak için aynı komuta --uygula ekleyin")
    return yazilan


# ------------------------------------------------------------ calistirma


def dosyayi_denetle(yol: Path, kod_adlari):
    ham = yol.read_text(encoding="utf-8")
    pler = paragraflara_bol(ham)
    dosya = yol.name
    bulgular = tirnak_haritasi(pler, dosya)
    for p in pler:
        bulgular += italik_haritasi(p, dosya)
    for p in pler:
        bulgular += paragraf_kurallari(p, dosya, kod_adlari)
    bulgular += dosya_kurallari(pler, dosya)
    bulgular += algi_tekrari(pler, dosya)
    for p in pler:
        bulgular += ozne_ve_baglac(p, dosya)
    tik_bulgu, tik_say = tik_kumeleri(pler, dosya)
    return pler, bulgular + tik_bulgu, tik_say


def derlem_yollari(yollar, bolumler_klasoru) -> list:
    """
    Norm (ve K13'un yayginlik olcusu) icin karsilastirma derlemi.
    Taranan dosyalar 10 ya da daha fazlaysa derlem onlardir. Daha azsa
    (tek bolum taslagi) yayimlanmis bolum klasoru eklenir: "bu bolum
    digerlerinden sapiyor mu?" sorusu ancak digerleriyle sorulabilir.
    """
    if len(yollar) >= 10:
        return list(yollar)
    try:
        hepsi = tr_dosyalari(bolumler_klasoru)
    except FileNotFoundError:
        return list(yollar)
    adlar = {y.name for y in yollar}
    return list(yollar) + [y for _no, y in hepsi if y.name not in adlar]


def tr_dosyalari(bolumler_klasoru=None) -> list:
    """
    [(numara, yol)] -- numaraya gore sirali.

    Numara bolum.py ile AYNI yerden gelir: lotm.bolumler_tr once front
    matter'a, yoksa dosya adina bakar; ayni numara iki kez varsa
    lotm.bolum_sozlugu ilkini tutar ve bunu kaydeder. Eskiden burada dosya
    adindaki ilk sayi kullaniliyordu; front matter'da numarasi farkli olan
    bir dosya iki aracta iki ayri bolum olurdu.

    Metin yine DOSYADAN okunur (lotm'un govdesinden degil): bulgularin satir
    numarasi, duzenleyicide acilacak .md dosyasinin gercek satiri olmali.
    """
    klasor = Path(bolumler_klasoru or lotm.BOLUMLER_TR)
    bolumler = lotm.bolumler_tr(klasor)
    sozluk = lotm.bolum_sozlugu(bolumler)
    numarali = sorted(sozluk.items())
    numarasiz = [b for b in bolumler if b.no is None]
    return [(no, klasor / b.kaynak) for no, b in numarali] + [
        (None, klasor / b.kaynak) for b in numarasiz
    ]


def kelime_sayisi(pler) -> int:
    return sum(len(re.findall(r"[^\W\d_]+", p.metin)) for p in pler)


def norm_disi(sayim, kelime, referans, taranan, en_az=3):
    """
    Bolum basina BAK oranlari (bin kelimede) derlem dagilimiyla
    karsilastirilir. Esik dort olcunun en buyugudur:
        2 x ortanca, ortanca + 3 x MAD, 90. yuzdelik, 2 x ortalama
    Ilk ikisi yogun kurallar icindir (noktali virgul her bolumde var):
    MAD uc degerlerden etkilenmez. Son ikisi SEYREK kurallar icindir:
    bolumlerin cogunda hic gecmeyen bir kuralda ortanca ve MAD sifirdir,
    esik de sifira inerdi ve 'en_az' bulgusu olan her bolum "sapan"
    gorunurdu (ilk surumun hatasi). Yuzdelik ve ortalama o durumda da
    anlamli bir cubuk koyar. Ayrica en az 'en_az' bulgu sart.

    Doner: {dosya: [(kod, oran, ortanca, esik, sayi), ...]}
    """
    import statistics

    def esik_hesapla(oranlar):
        med = statistics.median(oranlar)
        mad = statistics.median(abs(o - med) for o in oranlar)
        p90 = statistics.quantiles(oranlar, n=10)[-1]
        ort = statistics.fmean(oranlar)
        return med, max(2 * med, med + 3 * 1.4826 * mad, p90, 2 * ort)

    def oran(d, k):
        return 1000 * sayim[d].get(k, 0) / max(kelime[d], 1)

    kodlar = {k for d in sayim.values() for k in d}
    out = {}
    for d in taranan:
        # Birini-disarida-birak: bolum kendi esigine katilmaz. Yoksa tek
        # bir uc bolum ortalamayi ve yuzdeligi kendi lehine yukseltip
        # kendini gizlerdi.
        ref = [r for r in referans if r != d]
        if len(ref) < 10:
            continue
        for k in kodlar:
            n = sayim[d].get(k, 0)
            if n < en_az:
                continue
            med, e = esik_hesapla([oran(r, k) for r in ref])
            o = oran(d, k)
            if o > e and o > 0:
                out.setdefault(d, []).append((k, o, med, e, n))
    return out


def taban_oku(yol) -> set:
    if not yol:
        return set()
    try:
        with open(yol, encoding="utf-8") as f:
            return {tuple(s.rstrip("\n").split("\t")[:3]) for s in f if s.strip()}
    except OSError as e:
        sys.exit(f"HATA: taban okunamadı: {e}")


def taban_yaz(yol, bulgular):
    with open(yol, "w", encoding="utf-8") as f:
        for b in sorted(bulgular, key=lambda b: (b.dosya, b.satir, b.kod)):
            f.write("\t".join((b.dosya, b.kod, b.alinti)) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "dosyalar",
        nargs="*",
        help="bölüm numaraları (bolum.py gibi: 48) ya da .md yolları; "
        "hiçbiri yoksa bütün bölüm klasörü",
    )
    ap.add_argument(
        "--bolumler", default=None, help="bölüm klasörü (varsayılan: lotm.BOLUMLER_TR)"
    )
    ap.add_argument(
        "--bolum",
        type=int,
        help="klasörden yalnız bu numaralı bölüm (= konumsal numara)",
    )
    ap.add_argument("--sozluk", default=None)
    ap.add_argument("--kod", default=None, help="virgülle ayrılmış kodlar (B03,B04)")
    ap.add_argument("--bak", action="store_true", help="BAK bulgularını tek tek yaz")
    ap.add_argument(
        "--duzelt",
        action="store_true",
        help="otomatik düzeltmeleri göster (KURU; hiçbir dosya değişmez)",
    )
    ap.add_argument(
        "--uygula",
        action="store_true",
        help="--duzelt ile: GÜVENLİ düzeltmeleri dosyalara yaz",
    )
    ap.add_argument(
        "--tik-sayim",
        dest="tik_sayim",
        action="store_true",
        help="bölüm başına toplam tik sayımını da yaz",
    )
    ap.add_argument("--taban", default=None, help="bu dosyadaki bulgular bastırılır")
    ap.add_argument(
        "--taban-yaz",
        dest="taban_yaz",
        default=None,
        help="şimdiki bütün bulguları tabana yaz ve çık",
    )
    a = ap.parse_args()

    numaralar = [int(d) for d in a.dosyalar if d.isdigit()]
    if a.bolum is not None:
        numaralar.append(a.bolum)
    yollar = [Path(d) for d in a.dosyalar if not d.isdigit()]
    if numaralar or not yollar:
        try:
            hepsi = tr_dosyalari(a.bolumler)
        except FileNotFoundError as e:
            sys.exit(f"HATA: {e}")
        if numaralar:
            sozluk = dict(hepsi)
            eksik = [n for n in numaralar if n not in sozluk]
            if eksik:
                sys.exit(f"HATA: TR bölüm bulunamadı: {', '.join(map(str, eksik))}")
            yollar += [sozluk[n] for n in numaralar]
        else:
            yollar = [y for _no, y in hepsi]
    if not yollar:
        sys.exit("HATA: denetlenecek dosya yok")

    kodlar = {k.strip().upper() for k in a.kod.split(",")} if a.kod else None
    kod_adlari = (
        kod_adi_deseni(a.sozluk) if (kodlar is None or "K06" in kodlar) else None
    )

    if a.uygula and not a.duzelt:
        sys.exit("HATA: --uygula yalnız --duzelt ile birlikte kullanılır")
    if a.duzelt:
        duzelt(yollar, kod_adlari, taban_oku(a.taban), kodlar, a.uygula)
        return 0

    taranan = [y.name for y in yollar]
    derlem = derlem_yollari(yollar, a.bolumler)
    tum, tikler, bol_par, kelime = [], {}, [], {}
    for y in derlem:
        pler, bulgular, tik = dosyayi_denetle(y, kod_adlari)
        tum += bulgular
        tikler[y.name] = tik
        bol_par.append((y.name, pler))
        kelime[y.name] = kelime_sayisi(pler)
    if (kodlar is None or "K13" in kodlar) and len(bol_par) >= 10:
        df, n = belge_frekansi(bol_par)
        for dosya, pler in bol_par:
            tum += yerel_tekrar(pler, dosya, df, n)
    elif kodlar is None or "K13" in kodlar:
        print(
            "  uyarı: K13 ve norm için derlem yok (10'dan az bölüm); atlandı.",
            file=sys.stderr,
        )
    if kodlar:
        tum = [b for b in tum if b.kod in kodlar]

    # Norm butun derlem uzerinden olculur; rapor yalniz taranan dosyalar icindir.
    bak_sayim = defaultdict(Counter)
    for b in tum:
        if b.duzey == BAK:
            bak_sayim[b.dosya][b.kod] += 1
    for d in kelime:
        bak_sayim.setdefault(d, Counter())
    sapanlar = (
        norm_disi(bak_sayim, kelime, [d for d, _ in bol_par], taranan)
        if len(bol_par) >= 10
        else {}
    )
    tum = [b for b in tum if b.dosya in set(taranan)]

    if a.taban_yaz:
        taban_yaz(a.taban_yaz, tum)
        print(f"{len(tum)} bulgu tabana yazıldı: {a.taban_yaz}", file=sys.stderr)
        return 0

    taban = taban_oku(a.taban)
    bastirilan = sum(1 for b in tum if b.anahtar() in taban)
    tum = [b for b in tum if b.anahtar() not in taban]

    hatalar = [b for b in tum if b.duzey == HATA]
    baklar = [b for b in tum if b.duzey == BAK]

    print(
        f"{len(yollar)} dosya tarandı."
        + (f" {bastirilan} bulgu tabanda, bastırıldı." if bastirilan else "")
    )

    print("\n=== HATA ===")
    if not hatalar:
        print("  temiz")
    # Koda gore gruplu: 200 virgul bulgusu diger siniflari gommesin.
    # Kucuk siniflar once; tek bir kalabalik sinif en sona duser.
    gruplar = defaultdict(list)
    for b in hatalar:
        gruplar[b.kod].append(b)
    for kod in sorted(gruplar, key=lambda k: (len(gruplar[k]), k)):
        bs = sorted(gruplar[kod], key=lambda b: (b.dosya, b.satir))
        dosyalar = Counter(b.dosya for b in bs)
        print(
            f"\n--- {kod} {ACIKLAMA[kod]}: {len(bs)} bulgu, {len(dosyalar)} dosyada ---"
        )
        for b in bs:
            print(f"  [{b.dosya}:{b.satir}] {b.mesaj}\n      {b.alinti}")

    # BAK'in asil kullanimi tek tek bulgu degil, "bu bolum digerlerinden
    # sapiyor mu" sorusudur. Varsayilan gorunum budur; ayrinti --bak ile.
    print("\n=== NORMDAN SAPAN BÖLÜMLER (BAK; bin kelimede, öbür bölümlere göre) ===")
    if not bol_par or len(bol_par) < 10:
        print("  derlem yok; norm ölçülemedi")
    elif not sapanlar:
        print("  sapan yok")
    for d in sorted(sapanlar):
        print(f"  {d}")
        for k, o, m, e, n in sorted(sapanlar[d], key=lambda x: -x[1] / max(x[3], 0.01)):
            print(
                f"      {k} {ACIKLAMA[k]:<52} {o:5.1f}  (eşik {e:.1f} · ortanca {m:.1f} · {n} bulgu)"
            )

    print("\n=== BAK ===")
    if not baklar:
        print("  yok")
    elif a.bak:
        # K13 bolum basina en guclu _K13_UST kume (yerel_tekrar puan sirasiyla dondurur).
        k13_say, gosterilen = Counter(), []
        for b in baklar:
            if b.kod == "K13":
                k13_say[b.dosya] += 1
                if k13_say[b.dosya] > _K13_UST:
                    continue
            gosterilen.append(b)
        for b in sorted(gosterilen, key=lambda b: (b.dosya, b.satir, b.kod)):
            print(f"  [{b.dosya}:{b.satir}] {b.kod} {b.mesaj}\n      {b.alinti}")
        gizli = sum(max(0, n - _K13_UST) for n in k13_say.values())
        if gizli:
            print(
                f"  (K13: bölüm başına en güçlü {_K13_UST} küme gösterildi, {gizli} küme daha var)"
            )
    else:
        say = Counter(b.kod for b in baklar)
        print(
            "  "
            + " · ".join(f"{k} {n}" for k, n in sorted(say.items()))
            + "   (--bak ile tek tek)"
        )

    if a.tik_sayim:
        print("\n=== TİK SAYIMI (toplam; asıl ölçü K02 kümeleridir) ===")
        for dosya, say in tikler.items():
            if say and dosya in set(taranan):
                print(
                    f"  {dosya}: " + ", ".join(f"{e} {n}" for e, n in say.most_common())
                )

    print("\n--- ÖZET ---")
    say = Counter(b.kod for b in hatalar)
    for k in sorted(say):
        print(f"  {k} {ACIKLAMA[k]}: {say[k]}")
    print(f"  HATA toplam: {len(hatalar)}   BAK toplam: {len(baklar)}")
    if not lotm.SAGLIK.temiz():
        lotm.SAGLIK.rapor()
    return 1 if hatalar else 0


if __name__ == "__main__":
    sys.exit(main())
