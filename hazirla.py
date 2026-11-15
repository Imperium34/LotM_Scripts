#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hazirla.py -- ceviriden ONCE: bir bolumun kaynak metninde gecen terimlerin
dokumu (Terim Dokumu), sablon uretecek modele verilmek uzere.

UST DUZEY SORU: "Bu bolumde HANGI kararlari zaten verdim?"

Diger betiklerin hepsi ceviriden SONRA calisir. Ceviriden once tek adim
bolum acilis sablonudur ve onu bir dil modeli uretir: butun sozluk.yml'i
(3000+ satir), words.md'yi ve ileride salahiyetler.yml'i (5000+ satir)
okuyup bu bolumde hangi terimlerin gectigini kendisi bulmaya calisir.
Sablon becerisinin kendi notu en sik hatayi soyle tarif ediyor: zaten
yerlesmis bir terime yeni bir karsilik uydurmak. Hangi terimin bolumde
gectigi bir YARGI degil bir ARAMADIR; burada mekanik olarak yapilir.

NE URETIR
---------
Iki ayri cikti, iki ayri okur icin. DOKUM sablon ureticisine gider ve
yalniz onun kullanabilecegi seyi tasir: bu bolumde gecen yerlesmis
terimler ve karar bekleyen adlar. BAKIM RAPORU editore gider (--bakim):
sozluge geri tasinacak obekler, veri eksikleri, yayimlanmis karsiligina
bakilacak adlar icin komutlar. Sablon ureticisi komut calistiramaz ve
onceki bolumleri acamaz; bakim satirlari onun icin gurultudur ve gurultulu
bir satir sablona satir olarak girebilir.

DOKUM:
  1. Yerlesmis terimler, OKUMA SIRASIYLA: sozluk.yml + words.md kayitlari
     bolumun Cincesinde gecenler. Cince anahtari olmayan kayit, ya da
     Cince anahtari bu bolumde TUTMAYAN kayit Ingilizceyle aranir ve
     hangisi oldugu yazilir (ikincisi bir veri eksigi ya da bir Ingilizce
     tuzagidir). Buyuk/kucuk harfle ayrilan iki kayit (Kâhin / kâhin)
     birlestirilmez; ikisi de bolumdeyse yan yana uyarilir.
     Cok bicimli kayitta ("kehanet gök haritası / gök haritası") bu bolumde
     HANGI bicimin gectigi yazilir; Cincesi sozlukte olmayan bir terimin
     anahtari bilesimden cikarilabiliyorsa (Rüya Kehaneti ← 梦境占卜) o da.
     1b. Cince anahtari tutmayan kayitlar, anahtara tek harf uzak Cince
         bicimle (双轮马车 / 两轮马车).
     1c. Ayni Cince anahtari paylasan FARKLI kayitlar (灵体: Ruhanî Beden /
         ruhanî varlık): hangisi oldugu bagla secilir, baglamla verilir.
     1d. Yalniz Ingilizceyle bulunmus, Ingilizcesi kucuk harfli siradan
         sozcuk olan words.md kayitlari (notebook, pen): baglamiyla, kesin
         sayilmaz.
     1e. Bolumde gecen capa sozlugu adlari (Klein, Glacis): Turkcesi
         Ingilizce adla aynidir.
  2. Salahiyetler: salahiyetler.yml'de Cincesi bolumde gecen kayitlar,
     tek karsilik ve Ingilizce tuzagi ile.
  3. Sozlukte olmayan adaylar, iki kaynaktan:
     a. Ingilizcede buyuk harfle gecen adlar. Bilinen bir terimin baska
        Ingilizce adi olan aday (Foodaholic Empire = Gourmet Empire)
        aday sayilmaz, ayri listelenir.
     b. Cincede ad isareti tasiyan diziler: unvandan onceki ad (X先生),
        nokta ile bolunmus ad (X·Y), tirnakli kisa ifade (‘X号’), ad
        verme kalibi (称呼我X). Ingilizce adayla eslesirse tek satir olur.
     c. Bilinen bir anahtarin ses parcasi yeni bir bilesikte (费内波特王国 ⊂
        费内波特高原咖啡'nin koku).
     Ingilizce adayin Turkcesi mekanik olarak belliyse yazilir: ad kurali
     (ad Ingilizcedeki gibi), ya da koku cevrilmis bir kayit (Caesar ->
     Sezar).
  4. Tarama makbuzu.

TOPLU CALISMA: kaynak_yukle() korpuslari bir kez okur, hazirla_bolum() bir
bolumu hazirlar. hazirla_dogrula.py dokumu yayimlanmis bolumlere karsi
bu ikisiyle sinar. Ayrilmis sozcukler (bolumde GECMEYEN, carpisma doguran
terimler) bu dokumun degil ayrilmis.py'nin isidir.

BAKIM RAPORU (--bakim):
  1. Yayimlanmis karsiligina bakilacak adlar (ceviri_denetle.py komutlari).
  2. Daha once cevrilmis ama hicbir sozluge girmemis tekrarli obekler:
     bu bolumde en az iki kez gecen, romanin butununde seyrek, yayimlanmis
     bir bolumde daha once gecmis Cince obekler. Yayimlanmis metinde
     cevrilip sozluge geri tasinmamis terimlerin tek izi budur.
  3. Veri eksikleri: Cincesi girilmemis kayitlar, Cince anahtari tutmayan
     kayitlar, sozluge eklenebilecek Ingilizce varyantlar.

KAPI (bolum_siniri) BURADA YOKTUR: okurun sozluk sayfasinda neyi ne zaman
gorecegini belirler, cevirmenin hangi kelimeyi kullanacagini degil.

Kullanim:
    hazirla.py 54                       ekrana
    hazirla.py 54 --cikti Ch_54_terimler.md
    hazirla.py 54 --notlar              cevirmen notlarini da ekle (uzun)
    hazirla.py 54 --bakim               bakim raporunu da ekrana (stderr) yaz
    hazirla.py 54 --cikti Ch_54_terimler.md --bakim Ch_54_bakim.md
    hazirla.py 54 --bakim --obek-yok    bakim raporu, obek taramasi olmadan
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import functools
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import capa as _capa
import lotm
from toplu_denetle import harf_duyarli_mi
from turkce import tr_buyut, tr_kucult

# Bu kategoriler words.md'de ya da sozlukte bir KISI/kod adi listesidir;
# Ingilizce aday taramasinda bilinen ad sayilirlar.
_EN_KELIME = re.compile(r"[A-Za-z][A-Za-z'\-]+")
# Buyuk harfle baslayan ad obegi: "Backlund", "Tingen City", "House of Wind"
# Yalniz BOSLUK: satir sonu obegi bolmeli ("...Requester\n\nChapter" bir
# baslik ve bir sonraki satirdir, tek ad degil). Iyelik "'s" ayrica atilir.
# Ic buyuk harf (McGovern) kelimenin parcasidir: eski desen "Welch Mc"
# diye kesiyordu (9).
_AD_KELIMESI = r"[A-Z][a-z\-]+(?:[A-Z][a-z\-]+)?"
_AD_OBEGI = re.compile(
    rf"(?<![\w']){_AD_KELIMESI}(?:'[a-z]+)?"
    rf"(?:[ ]+(?:of|the|de|von|van)[ ]+{_AD_KELIMESI}|[ ]+{_AD_KELIMESI})*"
)
_IYELIK = re.compile(r"(?:'s|')$")
# Cumle basinda buyuk harf her kelimeyi ad gibi gosterir; bunlar ve
# Ingilizcenin buyuk harfle yazilan siradan sozcukleri aday sayilmaz.
_SIRADAN = set(
    """I I'm I'll I've I'd Mr Mrs Ms Miss Sir Madam Lady Lord Chapter The A An And But Or
    If When Then This That These Those There Here What Who Why How Where Which It Its
    He She They We You His Her Their Our Your My Me Him Them Us No Yes Not Oh Ah Ahem
    Well So As At By For From In Into On Of To With Without After Before Because Since
    Although Though While Just Only Even Still Yet Also Then Now However Moreover Instead
    Perhaps Maybe Indeed Of Sunday Monday Tuesday Wednesday Thursday Friday Saturday
    January February March April May June July August September October November December
    God Goddess Lady Sir Dr
    Is Are Was Were Do Does Did Has Have Had Can Could Will Would Should Shall Might Must
    Let Please Every Each Some Any All Everyone Nobody Someone Actually""".split()
)
# "Mr. Glacis": unvandaki nokta cumle sonu degildir. Bu olmadan unvanla
# anilan her ad cumle basi sayilip eleniyordu (54'te Glacis ×4 → ×1, Vannas ×0).
_UNVAN_NOKTASI = re.compile(
    r"\b(?:Mr|Mrs|Ms|Mx|Dr|St|Mt|Prof|Capt|Sgt|Lt|Col|Gen|Rev)\.\s*$"
)
# Bir onceki cumlenin sonu. Uc nokta (…) eksikti: 55 ¶54 "...letting me go…
# All I can hope for" icinde "All" cumle basi sayilmayip aday oluyordu.
_CUMLE_SONU = re.compile(r"[.!?\"'“”:\n…]\s*$")
# Korpusta kucuk harfle yazilmis sozcuk (bkz. kucuk_sozcukler).
_KUCUK_SOZCUK = re.compile(r"(?<![\w'])[a-z][a-z'\-]*")

# Ad cevirisinde kullanilan ses karakterleri (乔伊斯, 迈尔, 瑞尔, 比伯, 安娜).
# Tam degildir ve olmasi gerekmez: yalniz bir Cince adayin SESLE mi (kisi,
# yer adi) yoksa ANLAMLA mi (生日灵数, 苜蓿号) cevrildigini kabaca ayirir.
_SES_HARFLERI = set(
    "阿埃艾安奥澳巴芭贝本比彼宾波伯勃布查达黛戴丹德迪蒂丁杜多恩尔法凡菲费芬弗福盖格戈"
    "古哈海汉豪赫亨胡华霍吉基加贾杰金卡凯坎康柯科克肯库奎拉莱兰朗劳勒雷蕾里利莉丽林琳"
    "卢鲁路伦罗洛马玛迈麦曼梅美蒙米敏莫默姆穆纳娜奈南内尼妮纽诺欧帕佩皮普奇乔切琼丘瑞"
    "萨塞赛桑瑟森沙莎尚舍什史斯苏索塔泰坦汤特提图托瓦万威韦维温沃乌西希席夏谢辛修雅亚"
    "扬耶伊因英尤约泽詹佐娅薇琪芙蓓茜丝嘉"
)

# Bir Ingilizce aday ile bilinen bir terimin gecisleri arasindaki en buyuk
# oransal mesafe (metnin uzunluguna gore). Cince ve Ingilizce paragraf
# paragraf ilerledigi icin ayni seyin iki metindeki oransal konumu yakindir.
_KONUM_TOLERANSI = 0.03

_CJK = "一-鿿"
_CJK_DIZI = re.compile(rf"[{_CJK}]+")


@dataclass
class Eslesme:
    terim: lotm.Terim
    nasil: str  # "zh" | "en" (Cince anahtar yok) | "en-yedek" (Cince anahtar tutmadi)
    sayi: int
    ilk: int  # kaynak metindeki ilk konum (okuma sirasi icin)
    konumlar: list = field(default_factory=list)  # butun gecisler (nasil'in metninde)
    yayim: list = field(default_factory=list)  # bu terimin gectigi yayimlanmis bolumler
    kardesler: list = field(default_factory=list)  # buyuk/kucuk harfle ayrilan kayitlar
    baglam: str = ""  # Ingilizceden bulunan icin ilk gecisin cevresi
    anahtarlar: dict = field(default_factory=dict)  # Cince anahtar -> konumlar
    cok_anlamli: list = field(default_factory=list)  # ayni anahtari paylasan baska kayitlar
    cikarim: str = ""  # sozlukte olmayan, bilesimden cikarilan Cince anahtar
    yakin: list = field(default_factory=list)  # 1b: anahtara tek harf uzak Cince bicimler
    kucuk_bicim: str = ""  # yayimlanmis metindeki kucuk harfli bicim (liste usulu buyuk harf)


@dataclass
class Aday:
    ad: str
    sayi: int
    konumlar: list  # bu bolumdeki gecisler (adin kendi dilinin metninde)
    dil: str  # "en" | "zh"
    tur: str = ""  # zh icin: "unvan", "noktalı ad", "tırnaklı", "gemi?", "ad verme"; en icin "başlık"
    ilk_bolum: int | None = None
    es: "Aday | None" = None  # karsi dildeki eslesen aday
    parcalar: dict = field(default_factory=dict)  # en: adin tek basina gecen parcalari -> sayi
    tirnakli: int | None = None  # zh tirnakli ifade: gecislerin kaci tirnak icinde


# ---------------------------------------------------------------- kaynak


def kaynaklar(no: int) -> tuple:
    """(zh_metin | None, en_metin | None, en_baslik | None)."""

    def al(f):
        try:
            return lotm.bolum_sozlugu(f()).get(no)
        except (FileNotFoundError, OSError):
            return None

    zh_b, en_b = al(lotm.bolumler_zh), al(lotm.bolumler_en)
    baslik = None
    if en_b is not None:
        baslik = getattr(en_b, "baslik", None) or getattr(en_b, "title", None)
    return (zh_b.metin if zh_b else None), (en_b.metin if en_b else None), baslik


def _zh_parcalari(t) -> list:
    """Cince anahtar parcalari; tek karakter yalnizca kasitliysa (「」)."""
    return [
        z.strip()
        for z in (t.zh or "").split("/")
        if z.strip() and (len(z.strip()) > 1 or t.zh_kesin)
    ]


# _bilesik_deseni onbellegi: [hepsi listesi, uzunlugu, {z: desen}]. Desen yalniz
# (z, hepsi)'ye baglidir ama her cagri hepsi'nin ~1000 ogesini suzup desen
# metnini yeniden kuruyordu (bolum basina binlerce kez, hazirla_dogrula'da
# her bolumde). Liste nesnesi ayni ve uzunlugu ayni kaldikca sonuc aynidir:
# kaynak_yukle ve cikarimla_yeniden listeyi hep YENI kurar, yerinde degistirmez.
_BILESIK_ONBELLEK: list = [None, 0, {}]


def _bilesik_deseni(z: str, hepsi: list):
    o = _BILESIK_ONBELLEK
    if o[0] is not hepsi or o[1] != len(hepsi):
        o[0], o[1], o[2] = hepsi, len(hepsi), {}
    d = o[2].get(z)
    if d is None:
        d = o[2][z] = lotm.zh_desen(z, [b for b in hepsi if z in b and b != z])
    return d


def _ingilizce_adlari(t) -> set:
    adlar = {a for a in t.arama_adaylari() if a}
    for a in (t.en, getattr(t, "yol_en", None)):
        if a:
            adlar.add(a)
    return adlar


def _oransal_fark(a_konum, a_uzunluk, b_konum, b_uzunluk):
    """
    Iki konum listesinin oransal olarak EN YAKIN cifti arasindaki fark; biri
    bossa None. Yalniz ilk gecisler karsilastirilinca bir ad, Ingilizcesinin
    ilk gecisi cumle basi diye elendiginde ya da cevirmen bir paragrafta adi
    dusurdugunde karsisini kaciriyordu (55: Anna ↔ 安娜 hic eslesmedi).
    """
    if not a_konum or not b_konum or not a_uzunluk or not b_uzunluk:
        return None
    return min(
        abs(a / a_uzunluk - b / b_uzunluk) for a in a_konum[:40] for b in b_konum[:40]
    )


class Korpus:
    """
    Ingilizce korpusun harf istatistigi: buyuk harfli bir sozcuk AD mi?

    Ad, korpusta hic kucuk yazilmamis VE cumle ortasinda da buyuk yazilmis
    sozcuktur (Angelica, Bieber, Hornacis). Kucuk de yazilan sozcuk (all,
    old, congratulations) siradandir. Yalniz cumle basinda gorulen sozcuk
    (Meanwhile, Anyways, Eugh) da siradandir: hic kucuk yazilmamasi ad
    oldugunu degil, hep cumleye bastigini gosterir.

    Eski kural cumle basindaki her tek kelimeyi atiyordu: 55 ¶20'de
    "...outside? Angelica will" boyle kayboldu.
    """

    # Cumle ortasi: kucuk harf, virgul ya da noktali virgulden sonra; ya da
    # bir unvan noktasindan sonra ("Mr. Vannas" -- adi baska turlu hic
    # cumle ortasinda gecmeyebilir; 54).
    _ORTA = re.compile(
        r"(?:[a-z,;]|\b(?:Mr|Mrs|Ms|Mx|Dr|St|Prof|Capt|Sgt|Lt|Col|Gen|Rev)\.) "
        r"([A-Z][a-z'\-]+)"
    )

    def __init__(self, kucuk=(), orta=()):
        self.kucuk = kucuk if isinstance(kucuk, Counter) else Counter(set(kucuk))
        self.orta = orta if isinstance(orta, Counter) else Counter(set(orta))

    def __bool__(self) -> bool:
        return bool(self.kucuk or self.orta)

    def siradan(self, kelime: str) -> bool:
        w = _IYELIK.sub("", kelime)
        return w.lower() in self.kucuk or bool(self.orta and w not in self.orta)

    def hic_kucuk_yazilmamis(self, kelime: str) -> bool:
        return _IYELIK.sub("", kelime).lower() not in self.kucuk

    def cumleden_buyumus(self, kelime: str) -> bool:
        """
        Buyuk harfini cumle basindan almis siradan sozcuk mu? Kucuk yazilisi
        cumle ortasindaki buyuk yazilisindan cok daha sik olmali. Varlik/yokluk
        yetmiyor: "Congratulations" korpusta bir iki kez cumle ortasinda da
        buyuk yazilmis; "Holy" ve "Saint" ise sik sik (Holy Numerics Cathedral,
        Saint Selena Cathedral) ve bir adin parcasidir.
        """
        w = _IYELIK.sub("", kelime)
        k = self.kucuk.get(w.lower(), 0)
        return k > 0 and self.orta.get(w, 0) <= max(2, k // 10)


# Korpus._ORTA'nin hizli esdegeri icin parcalari (bkz. _orta_sozcukler).
_ORTA_ADAY = re.compile(r" ([A-Z][a-z'\-]+)")
_ORTA_UNVAN = re.compile(r"\b(?:Mr|Mrs|Ms|Mx|Dr|St|Prof|Capt|Sgt|Lt|Col|Gen|Rev)\.")


def _orta_sozcukler(m: str) -> list:
    """
    Korpus._ORTA.findall(m) ile AYNI listeyi verir, ama cok daha hizli.

    _ORTA her konumda iki secenekli bir on-ek dener ve 16 MB'lik korpusta
    en pahali tarama buydu. Her eslesmenin icinde "bosluk + Buyuk sozcuk"
    bulunur; once yalniz onu ararim (sabit bosluk ile baslayan desen cok
    ucuz) ve on-eki adayin hemen onunde ayri sinarim:
      - tek harf [a-z,;] (aday konumu - 1), ya da
      - unvan + nokta, basinda \b (3-5 karakter).
    Ayni aday icin ikisi birden uygun olamaz (onceki karakter ya harf/,/;
    ya nokta). Eslesmeler ust uste binmez: _ORTA bir eslesmeden SONRA
    taramaya devam eder, yani yeni on-ek onceki eslesmenin sonundan once
    baslayamaz ("a Foo Bar": Bar'in on-eki Foo'nun icinde, sayilmaz);
    son_bitis bunu uygular. Adaylar birbirinden ayrik (sozcuk bosluk
    icermez), bu yuzden reddedilen aday baska bir adayi gizleyemez.
    """
    out = []
    son_bitis = 0
    for c in _ORTA_ADAY.finditer(m):
        b = c.start()  # bosluk
        if b - 1 >= son_bitis and b and m[b - 1] in "abcdefghijklmnopqrstuvwxyz,;":
            pass
        elif not (
            b
            and m[b - 1] == "."
            and any(
                b - k >= son_bitis and _ORTA_UNVAN.fullmatch(m, b - k, b)
                for k in (3, 4, 5)
            )
        ):
            continue
        out.append(c.group(1))
        son_bitis = c.end()
    return out


def kucuk_sozcukler(metinler) -> Korpus:
    """Korpusun kucuk harfli sozcukleri ve cumle ortasinda buyuk yazilanlar."""
    # Ham sozcukler once oldugu gibi sayilir (Counter.update(liste) C'de
    # calisir), rstrip/_IYELIK katlamasi yalniz BENZERSIZ sozcuklere uygulanir:
    # 16 MB'lik korpusta milyonlarca sozcuk icin tek tek rstrip cagirmak
    # saniyeler tutuyordu. Sayilar ayni: katlama toplamlari degistirmez.
    ham_kucuk, ham_orta = Counter(), Counter()
    for m in metinler:
        ham_kucuk.update(_KUCUK_SOZCUK.findall(m))
        ham_orta.update(_orta_sozcukler(m))
    kucuk, orta = Counter(), Counter()
    for w, n in ham_kucuk.items():
        kucuk[w.rstrip("'-")] += n
    for w, n in ham_orta.items():
        orta[_IYELIK.sub("", w.rstrip("-"))] += n
    return Korpus(kucuk, orta)


def _siradan_mi(kelime: str, sozcukler) -> bool:
    """sozcukler bir Korpus ya da (testlerde) kucuk harfli sozcuk kumesi."""
    if isinstance(sozcukler, Korpus):
        return sozcukler.siradan(kelime)
    return _IYELIK.sub("", kelime).lower() in sozcukler


def _ad_kokulu(kelime: str, sozcukler) -> bool:
    """Eslestirme icin: korpusta hic kucuk yazilmamis kelime (Vannas, Bieber)."""
    if isinstance(sozcukler, Korpus):
        return sozcukler.hic_kucuk_yazilmamis(kelime)
    return not _siradan_mi(kelime, sozcukler)


_BAGLAC = {"of", "the", "de", "von", "van"}
_HITAP = {"Mr", "Mrs", "Ms", "Mx", "Miss", "Sir", "Madam", "Ma'am", "Lady", "Dr", "Mister"}


def _tam_bilinen(ad: str, bilinen: set) -> bool:
    """_bilinen_mi'nin dar hali: yalniz tam ad (ve cogulu), icinde gecis yok."""
    k = ad.lower()
    return k in bilinen or re.sub(r"e?s$", "", k) in bilinen


def _bilinen_mi(ad: str, bilinen: set) -> bool:
    """
    Ad sozluklerden birinde var mi? Cogul da denenir: sozlukte "Mystery
    Pryer", metinde "Mystery Pryers" (55'te aday diye cikiyordu). Bilinen
    cok kelimeli bir adin icinde gecen ad da bilinir.
    """
    kucuk = ad.lower()
    if kucuk in bilinen or any(f" {kucuk} " in f" {b} " for b in bilinen if " " in b):
        return True
    # Tekil bicim yalniz TAM adla karsilastirilir: "Williams" (7, bir kisi)
    # "william"a indirilip "William I"in icinde bulunuyor ve dusuyordu.
    return re.sub(r"e?s$", "", kucuk) in bilinen or (
        kucuk.endswith("s") and kucuk[:-1] in bilinen
    )


def _zh_baglam(zh: str, konum: int, uzunluk: int, pay: int = 12) -> str:
    s = re.sub(r"\s+", "", zh[max(0, konum - pay) : konum + uzunluk + pay])
    return ("…" if konum > pay else "") + s + ("…" if konum + uzunluk + pay < len(zh) else "")


# ---------------------------------------------------------------- eslesme


def arama_adlari(t) -> list:
    """
    Ingilizce taramada aranacak adlar. Tarot Cemiyeti uye kayitlarinda
    'ingilizce' alani kod adinin SAHIBIDIR: "Yıldız (The Star)" kaydinin
    Ingilizcesi "Leonard Mitchell"dir. Metinde Leonard Mitchell'in anilmasi
    kod adinin gectigi anlamina gelmez; 45-56'da dokum "Yıldız ← Leonard
    Mitchell"i, "Adalet ← Audrey Hall"u yerlesmis terim diye veriyordu.
    Aranacak ad terimin parantezindeki kod adidir; parantez yoksa
    (Halas Meleği Gehrman Sparrow) kaydin kendi adlari.
    """
    if t.kategori == "Tarot Cemiyeti" and isinstance(t.ham, dict):
        kod = lotm.ingilizce_ayikla(t.ham.get("terim"))
        if kod:
            return sorted(lotm.varyantlar(kod), key=lambda a: (-len(a), a))
    return t.arama_adaylari()


@functools.lru_cache(maxsize=None)
def _en_deseni(aday: str, duyarli: bool):
    """Ingilizce aday deseni; re'nin 512'lik onbellegi 1200 terim icin yetmiyor."""
    bayrak = 0 if duyarli else re.IGNORECASE
    return re.compile(r"(?<![\w-])" + re.escape(aday) + r"(?:e?s)?(?![\w-])", bayrak)


# IGNORECASE'in ASCII harfe esledigi ASCII-disi karakterler: Kelvin isareti
# (k), uzun s (s), noktali buyuk I (i) ve noktasiz kucuk i (i).
_EN_OZEL_HARF = ("\u212a", "\u017f", "\u0130", "\u0131")
_EN_DURUM: list = [None, None, None, {}]  # [en, en.lower(), lower guvenli mi, {(aday, duyarli): araliklar}]


def _en_araliklari(en: str, aday: str, duyarli: bool) -> tuple:
    """
    aday'in en'deki (bas, son) gecisleri. Ayni bolumde ayni (aday, duyarli)
    ikinci kez sorulur (terimleri_bul, hazirla_bolum'deki en_bulunan, anahtar
    cikarimi sonrasi yeniden kurulus): sonuc en'e bagli bir onbellekte tutulur.

    Regex'ten once ucuz bir alt dize sinamasi: desenin ZORUNLU parcasi aday'in
    kendisidir (kalan (?:e?s)? ve bakislar yalniz ekleme/kosul koyar), yani
    aday metinde yoksa desen eslesemez. Harf duyarliysa alt dize sinamasi
    birebir; duyarsizda re.IGNORECASE ile ayni sonuc icin sinama yalniz
    aday ASCII ve metinde ASCII harfle denk sayilan ASCII-disi karakter
    (_EN_OZEL_HARF) yokken yapilir; o zaman IGNORECASE ASCII harf icin
    basit buyuk/kucuk esitligidir ve en.lower() ile birebir ayni sonucu verir.
    Sinama gecemezse sonuc kesin olarak bostur; gecerse regex yine calisir.
    """
    d = _EN_DURUM
    if d[0] is not en:
        d[0], d[1], d[2], d[3] = en, None, None, {}
    anahtar = (aday, duyarli)
    sonuc = d[3].get(anahtar)
    if sonuc is not None:
        return sonuc
    var = None
    if duyarli:
        var = aday in en
    elif aday.isascii():
        if d[2] is None:
            d[2] = not any(c in en for c in _EN_OZEL_HARF)
            d[1] = en.lower() if d[2] else None
        if d[2]:
            var = aday.lower() in d[1]
    if var is False:
        sonuc = ()
    else:
        sonuc = tuple(m.span() for m in _en_deseni(aday, duyarli).finditer(en))
    d[3][anahtar] = sonuc
    return sonuc


def en_isabetleri(en: str, terimler: list) -> dict:
    """
    {id(terim): [(bas, son), ...]} -- her terimin Ingilizce adaylarinin
    bolumdeki gecisleri. Bir gecis baska bir adayin DAHA UZUN gecisinin
    icindeyse atilir: 'divination' araninca 'Divination Club' ve
    'divination method' sayilmaz (Cincedeki _bilesik_deseni ile ayni kural).
    Bu olmadan Kehanet 54'te ×20 cikiyordu; Cincesi ×17.

    Cogul eki kabul edilir: Gizem Avcısı'nin adi "Mystery Pryer", 55'teki
    gecisi "Mystery Pryers"; terim bulunmuyor, ad aday diye listeleniyordu.
    """
    ham = {}
    for t in terimler:
        if not t.tr:
            continue
        duyarli = harf_duyarli_mi(t)
        araliklar = set()
        for aday in arama_adlari(t):
            if len(aday) < 4:
                continue
            araliklar.update(_en_araliklari(en, aday, duyarli))
        if araliklar:
            ham[id(t)] = araliklar
    hepsi = {a for s in ham.values() for a in s}
    # "Baska bir gecisin DAHA UZUN olani icinde" sinamasi her gecis icin
    # butun gecisleri taramak yerine tek siralamayla yapilir. Aralik (a, b)
    # icin ona esit olmayan bir (a2, b2) a2 <= a ve b >= b iken vardir; esit
    # olmayan ve kapsayan aralik zorunlu olarak daha uzundur. (a artan, b
    # azalan) siralamada kapsayan her aralik (a, b)'den ONCE gelir ve hepsi
    # tekil oldugu icin (a, b)'nin kendisi onceki en buyuk b2'ye girmez.
    kapsanan = set()
    en_b = -1
    for a, b in sorted(hepsi, key=lambda x: (x[0], -x[1])):
        if en_b >= b:
            kapsanan.add((a, b))
        elif b > en_b:
            en_b = b
    out = {}
    for k, araliklar in ham.items():
        kalan = sorted(x for x in araliklar if x not in kapsanan)
        if kalan:
            out[k] = kalan
    return out


def _ayni_terim(a, b) -> bool:
    """
    Iki kayit ayni Turkce terim mi? Ayni yazilis: evet. Yalniz buyuk/kucuk
    harfle ayriliyorsa: ikisi de harf duyarliysa HAYIR. Kâhin (Mertebe adi)
    ile kâhin (siradan meslek), Hekim ile hekim bilincli olarak ayri
    kayitlardir; eski surum tr_kucult ile birlestirip words.md kaydini
    atiyordu, kucuk harfli kâhin 54'te dokumden boyle dustu. Temel Kavramlar
    harf duyarsizdir: oradaki baslik buyuk harfi yalnizca baslik usuludur.
    """
    if a.tr.strip() == b.tr.strip():
        return True
    if tr_kucult(a.tr) != tr_kucult(b.tr):
        return False
    return not (harf_duyarli_mi(a) and harf_duyarli_mi(b))


_NASIL_SIRASI = {"zh": 0, "en": 1, "en-yedek": 2}


def _sayi(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _nitelikli(t) -> bool:
    """
    Ust duzey kaydin adi parantezli bir nitelik tasiyor mu? "Toprak Ana
    (Dünya Savaşı Sonrası)", "Ebedî Gece Tanrıçası (Sermedi Zulmet)": ayni
    ilahin baska bir hali. parantezsiz() ikisini de ana kayitla ayni adda
    birlestirir. Mertebe adindaki parantez Ingilizce addir, nitelik degil.
    """
    if t.mertebe_mi or not isinstance(t.ham, dict):
        return False
    ham = str(t.ham.get("terim") or "").strip()
    return bool(ham) and ham != lotm.parantezsiz(ham)


def _gosterim_sirasi(t, no) -> tuple:
    """Ayni terimin kayitlarindan hangisi GOSTERILIR: kucuk olan once."""
    kapi, ilk = _sayi(t.bolum_siniri), _sayi(t.ilk_gecis)
    return (
        _nitelikli(t),
        no is not None and kapi is not None and kapi > no,
        ilk if ilk is not None else 10**9,
    )


def _birlestir(grup: list, no: int | None = None) -> Eslesme:
    """
    Ayni terimin birden cok kaydi (sozluk + words.md): GOSTERILEN kayit
    sozluktur; SAYIM en iyi kanittan gelir (Cince > Ingilizce). Sozlukteki
    Kehanet'in Cincesi yok ama words.md'deki kehanet'in var (占卜): sayim
    Cinceden, gosterim sozlukten.
    """
    # Sozluk kaydi words.md kaydina tercih edilir; sozluk kayitlari arasinda
    # dosya sirasi DEGIL: niteliksiz, bu bolumde acilmis, en erken gecen.
    # 56'da Toprak Ana'nin "Dünya Savaşı Sonrası" kaydi (kapi 1409) ve Ebedî
    # Gece Tanrıçası'nin "Sermedi Zulmet" kaydi dosyada once geldigi icin
    # gosteriliyor, aciklamalari (tazim isimleri) doküme giriyordu.
    sozlukten = [e for e in grup if not e.terim.kategori.startswith(lotm.KELIME_KATEGORI)]
    goster = (
        min(sozlukten, key=lambda e: _gosterim_sirasi(e.terim, no)) if sozlukten else grup[0]
    )
    veri = min(grup, key=lambda e: (_NASIL_SIRASI[e.nasil], e is not goster))
    if veri is goster:
        return goster
    return Eslesme(
        goster.terim,
        veri.nasil,
        veri.sayi,
        veri.ilk,
        veri.konumlar,
        baglam=veri.baglam,
        anahtarlar=veri.anahtarlar,
    )


def _baglam(en: str, a: int, b: int, pay: int = 45) -> str:
    s = en[max(0, a - pay) : b + pay]
    s = re.sub(r"\s+", " ", s).strip()
    return ("…" if a > pay else "") + s + ("…" if b + pay < len(en) else "")


def terimleri_bul(
    zh: str | None, en: str | None, terimler: list, zh_hepsi: list, no: int | None = None
) -> list:
    """
    Kaynakta gecen sozluk/words.md terimleri, okuma sirasiyla.

    Cincesi girilmis terim once Cinceyle aranir (kesin; daha uzun bir
    sozluk teriminin icindeki gecis sayilmaz: 灵体 araninca 星灵体). Cince
    anahtar bolumde HIC tutmazsa Ingilizceyle denenir ve 'en-yedek' diye
    isaretlenir: 54'te Aşkın'in anahtari 非凡者, metinde 非凡力量 vardi ve
    eski surum Ingilizceye hic bakmadigi icin terimi kaciriyordu. Cincesi
    olmayan ya da Cince metin yoksa dogrudan Ingilizceyle ('en').

    Ingilizce bir gecis, Cinceyle bulunmus BASKA bir terimin Ingilizce
    adiysa Ingilizceyle aranan terime verilmez: 54'te 'client' müşteri'nin
    (客户) adidir; müvekkil'in de Ingilizcesi 'client' oldugu icin ilk surum
    müvekkil'i -- A.3'te yasaklanan sozcugu -- yerlesmis terim diye
    veriyordu.
    """
    en_isabet = en_isabetleri(en, terimler) if en else {}
    zh_bulunan = {}
    zh_anahtar = {}  # id(terim) -> {anahtar: konumlar}
    if zh:
        for t in terimler:
            zs = _zh_parcalari(t) if t.tr else []
            per = {}
            for z in zs:
                k = [m.start() for m in _bilesik_deseni(z, zh_hepsi).finditer(zh)]
                if k:
                    per[z] = k
            if per:
                zh_bulunan[id(t)] = sorted({p for k in per.values() for p in k})
                zh_anahtar[id(t)] = per
    sahipli: dict = {}  # ingilizce ad -> onu Cinceyle bulunmus terimler
    for t in terimler:
        if id(t) in zh_bulunan:
            for a in _ingilizce_adlari(t):
                sahipli.setdefault(a.lower(), []).append(t)

    def baskasinin(t, metin: str) -> bool:
        # Ayni terimin ikinci kaydi (sozlukteki Kehanet, words.md'deki
        # kehanet) "baska" sayilmaz; yoksa sozluk kaydi dokumden duser.
        # Isabet cogul ekini tasiyabilir (bkz. en_isabetleri).
        k = metin.lower()
        sahipler = sahipli.get(k) or sahipli.get(re.sub(r"e?s$", "", k), [])
        return any(not _ayni_terim(t, s) for s in sahipler)

    bulunan = []
    for t in terimler:
        if not t.tr:
            continue
        cince_anahtarli = bool(zh and _zh_parcalari(t))
        if id(t) in zh_bulunan:
            k = zh_bulunan[id(t)]
            bulunan.append(Eslesme(t, "zh", len(k), k[0], k, anahtarlar=zh_anahtar[id(t)]))
            continue
        araliklar = [
            (a, b) for a, b in en_isabet.get(id(t), []) if not baskasinin(t, en[a:b])
        ]
        if not araliklar:
            continue
        k = sorted({a for a, _b in araliklar})
        nasil = "en-yedek" if cince_anahtarli else "en"
        a0, b0 = araliklar[0]
        bulunan.append(Eslesme(t, nasil, len(k), k[0], k, baglam=_baglam(en, a0, b0)))

    gruplar: list[list] = []
    for e in bulunan:
        for g in gruplar:
            if _ayni_terim(e.terim, g[0].terim):
                g.append(e)
                break
        else:
            gruplar.append([e])
    sonuc = [_birlestir(g, no) for g in gruplar]

    # Ayri tutulan ama yalniz harfle ayrilan kayitlar: ikisi de bolumde.
    for e in sonuc:
        e.kardesler = [
            o.terim.tr
            for o in sonuc
            if o is not e and tr_kucult(o.terim.tr) == tr_kucult(e.terim.tr)
        ]
    # Ayni Cince anahtari paylasan FARKLI kayitlar. Iki kayit da "yerlesmis"
    # diye verilirse model ikisinden birini rastgele secer: 灵体 hem Ruhanî
    # Beden'in hem ruhanî varlık'in anahtari, ve hangisi oldugu baglamdadir.
    sahipler = defaultdict(list)
    for t in terimler:
        if t.tr:
            for z in _zh_parcalari(t):
                sahipler[z].append(t)
    for e in sonuc:
        diger = []
        for z in e.anahtarlar:
            for o in sahipler.get(z, []):
                if not _ayni_terim(o, e.terim) and o.tr not in diger:
                    diger.append(o.tr)
        e.cok_anlamli = diger
    # Okuma sirasi: Cinceyle bulunanlar Cince konumuna gore, Ingilizceyle
    # bulunanlar onlardan sonra kendi sirasiyla (iki metnin konumlari
    # karsilastirilamaz).
    return sorted(sonuc, key=lambda e: (e.nasil != "zh", e.ilk))


# Salahiyet BAGLAMI. Fihristin kendi gecis sinamasi: "Yalnizca tasarruf
# beyani gecis dogurur: 掌握X权柄 / 拥有X权柄 / 部分"X"权柄. Kavramin
# anilmasi gecis degildir." 力量 (guc), 天气 (hava), 海洋 (deniz) metinde
# cogunlukla siradan sozcuktur; bunlari "yerlesmis karsilik" diye vermek
# modeli duz "guc" yerine "Kudret" yazmaya iter. Salahiyet sayilmasi icin
# isaret terimin HEMEN ARDINDA olmali (X权柄, “X”权柄, X的象征) -- fihristin
# kendi sinamasi. Ilk surum ±12 karakterlik pencereye bakiyordu ve cumle
# sinirini asiyordu: "用尽了力量。祂掌握了死亡权柄" 力量'i de sayiyordu.
_SALAHIYET_ISARETI = re.compile(r"[”\"」』]?(?:的)?(?:权柄|象征|神国|领域)")


def salahiyetleri_bul(zh: str | None, kayitlar: list, zh_hepsi: list) -> tuple:
    """
    (salahiyet_olarak, siradan) -- her biri [(kayit, sayi, ilk)].

    salahiyet_olarak: en az bir gecisinin HEMEN ARDINDAN 权柄/象征/神国/领域
    geliyor (arada en cok kapanis tirnagi ve 的). siradan: Cincesi geciyor ama hicbir gecisinde
    salahiyet baglami yok; karsilik dayatilmaz, yalnizca adi anilir.
    """
    if not zh:
        return [], []
    baglamli, siradan = [], []
    for k in kayitlar:
        z = str(k["cince"]).strip()
        if len(z) < 2:
            continue  # tek karakter (神, 光...) her yerde gecer; sinama anlamsiz
        konumlar = [m.span() for m in _bilesik_deseni(z, zh_hepsi).finditer(zh)]
        if not konumlar:
            continue
        kayit = (k, len(konumlar), min(a for a, _b in konumlar))
        if any(_SALAHIYET_ISARETI.match(zh, b) for _a, b in konumlar):
            baglamli.append(kayit)
        else:
            siradan.append(kayit)
    return sorted(baglamli, key=lambda x: x[2]), sorted(siradan, key=lambda x: x[2])


def harf_kardesleri(terimler: list) -> set:
    """Yalniz buyuk/kucuk harfle ayrilan kayitlarin kucuk bicimleri (kâhin)."""
    d = defaultdict(set)
    for t in terimler:
        if t.tr:
            d[tr_kucult(t.tr)].add(t.tr)
    return {k for k, v in d.items() if len(v) > 1}


def _bas_harfi_kucult(s: str) -> str:
    return tr_kucult(s[:1]) + s[1:]


def _liste_buyuk_harfi(t, kardesler: set) -> bool:
    """
    words.md maddesinin bas harfi listenin usulu mu? "Kristal küre",
    "Ruhanî sarkaç": cok kelimeli, ilk kelime buyuk, gerisi kucuk. Boyle bir
    kayit yayimlanmis metinde cumle ortasinda kucuk harfle gecer ("kristal
    küre", 40 ve 51); harf duyarli arama onu bulamiyor ve 55'te "yayımlanmış
    metinde YOK — ilk kez" diyordu. Harfle ayrilan bir kardesi olan kayitta
    (Kâhin / kâhin) buyuk harf anlamlidir; tek kelimelik kayitta da (Gece,
    Tanrica'nin vechesi) anlamli olabilir. Ikisi katlanmaz.
    """
    if not t.kategori.startswith(lotm.KELIME_KATEGORI) or tr_kucult(t.tr) in kardesler:
        return False
    k = t.tr.split()
    return len(k) > 1 and k[0][:1].isupper() and all(w[:1].islower() for w in k[1:])


def yayim_bicimleri(t, kardesler: set = frozenset()) -> list:
    """
    Terimin yayimlanmis metinde aranacak bicimleri. Harf duyarli aramada iki
    katlama yapilir:
      - liste usulu buyuk harf: "Kristal küre" metinde "kristal küre";
      - cumle basi: kucuk harfle baslayan bicim cumle basinda buyuk yazilir
        ("Baston elindeydi."). Eskiden bu gecisler sayilmiyordu; 1-56
        dogrulamasinda baston, gaz lambası, ceket gibi terimler yayimlanmis
        metinde "yok" gorunuyordu.
    Harfle ayrilan kardesi olan kayit (kâhin / Kâhin) katlanmaz: obur harf
    baska bir terimdir.
    """
    bicimler = t.tr_bicimleri()
    if not harf_duyarli_mi(t):
        return bicimler
    if _liste_buyuk_harfi(t, kardesler):
        bicimler = bicimler + [_bas_harfi_kucult(b) for b in bicimler]
    if tr_kucult(t.tr) not in kardesler:
        bicimler = bicimler + [tr_buyut(b[:1]) + b[1:] for b in bicimler if b[:1].islower()]
    return list(dict.fromkeys(bicimler))


# yayim_kullanimi onbellegi: [bolumler, parmak izi, {(bicimler, duyarli): [no, ...]}].
# Bir terimin hangi yayimlanmis bolumlerde gectigi YALNIZ terime ve korpusa
# baglidir; bolumden bolume yalniz `haric` degisir. hazirla_dogrula 10-100
# bolumu ayni Kaynak ile dolasir ve ayni yerlesik terimler her bolumde
# yeniden cikar: bolum basina ~2 sn'lik tarama bir kez yapilir, sonrasi sozluk
# sorgusudur. Parmak izi (no, metin kimligi) korpusun ayni kaldigini sinar;
# metin nesneleri onbellekte tutulur ki kimlikleri baska nesneye devredilmesin.
_YAYIM_ONBELLEK: list = [None, None, {}]


def _yayim_onbellegi(tr_bolumler: list) -> dict:
    iz = tuple((b.no, id(b.metin)) for b in tr_bolumler)
    o = _YAYIM_ONBELLEK
    if o[1] != iz:
        o[0] = [b.metin for b in tr_bolumler]  # kimlikleri sabit tut
        o[1], o[2] = iz, {}
    return o[2]


def _gecen_bolumler(onbellek: dict, tr_bolumler: list, bicimler: list, duyarli: bool) -> list:
    """Desenlerden herhangi biri eslesen TUM bolumlerin no'lari (korpus sirasiyla)."""
    anahtar = (tuple(bicimler), duyarli)
    nolar = onbellek.get(anahtar)
    if nolar is None:
        # desen_kur vekili tembeldir ve metinde zorunlu parca yoksa derlemeden
        # "eslesmez" der (on-sinama lotm'da tek yerde tutulur).
        desenler = [lotm.desen_kur(b, harf_duyarli=duyarli) for b in bicimler]
        nolar = [b.no for b in tr_bolumler if any(d.search(b.metin) for d in desenler)]
        onbellek[anahtar] = nolar
    return nolar


def yayim_kullanimi(
    eslesmeler: list, tr_bolumler: list, haric: int, kardesler: set = frozenset()
) -> None:
    """Her eslesmenin .yayim alanini doldurur: bicimlerinin gectigi bolumler."""
    onbellek = _yayim_onbellegi(tr_bolumler)
    for e in eslesmeler:
        duyarli = harf_duyarli_mi(e.terim)
        bicimler = yayim_bicimleri(e.terim, kardesler)
        katla = duyarli and _liste_buyuk_harfi(e.terim, kardesler)
        e.yayim = sorted(
            n for n in _gecen_bolumler(onbellek, tr_bolumler, bicimler, duyarli)
            if n is not None and n != haric
        )
        if katla:
            kucuk = _bas_harfi_kucult(e.terim.tr)
            if any(n != haric for n in _gecen_bolumler(onbellek, tr_bolumler, [kucuk], True)):
                e.kucuk_bicim = kucuk


# ------------------------------------------------- Cince anahtar cikarimi


def anahtar_cikar(zh_adaylar: list, eslesmeler: list, terimler: list, zh, en) -> dict:
    """
    {id(terim): (terim, anahtar)} -- Cincesi sozlukte OLMAYAN, Ingilizceyle
    bulunmus bir terimin bu bolumdeki Cince anahtari, bilesimden.

    55'te Rüya Kehaneti'nin Cincesi yoktu. Metindeki 梦境占卜 tirnakli aday
    diye 3b'ye dusuyor, icindeki 占卜 da Kehanet'e sayiliyordu (×8; dogrusu
    ×6 + Rüya Kehaneti ×2). Sinama dar ve uc kosulludur:
      1. Cince aday bilinen bir terimin (X) anahtarini icerir: 梦境占卜 ⊃ 占卜.
      2. Ingilizceyle bulunmus terimin (Y) Turkcesi X'in Turkcesini icerir:
         Rüya Kehaneti ⊃ Kehanet. Bilesik ad, bilesik karsilik.
      3. Ikisi metinde ayni yerde gecer (oransal konum toleransi).
    Cikarim karar degildir: dokumde isaretlenir, bakim raporunda anahtara
    eklenmek uzere listelenir.
    """
    if not zh or not en:
        return {}
    sahip = defaultdict(list)
    for t in terimler:
        if t.tr:
            for z in _zh_parcalari(t):
                sahip[z].append(t)
    ingilizceden = [e for e in eslesmeler if e.nasil == "en"]
    out = {}
    for z in zh_adaylar:
        if z.es is not None or "·" in z.ad:
            continue
        for anahtar, xs in sahip.items():
            if anahtar == z.ad or anahtar not in z.ad:
                continue
            for x in xs:
                xk = tr_kucult(x.tr)
                for y in ingilizceden:
                    if y.terim is x or xk not in tr_kucult(y.terim.tr):
                        continue
                    f = _oransal_fark(y.konumlar, len(en), z.konumlar, len(zh))
                    if f is not None and f < _KONUM_TOLERANSI:
                        out.setdefault(id(y.terim), (y.terim, z.ad))
    return out


def cikarimla_yeniden(
    zh, en, terimler: list, zh_hepsi: list, cikarim: dict, no: int | None = None
) -> tuple:
    """
    Cikarilan anahtarlarla eslesmeyi yeniden kurar: (terimler, zh_hepsi,
    eslesmeler). Anahtar ayni zamanda bilesik listesine girer; boylece
    Kehanet artik 梦境占卜'nun icindeki 占卜'yu saymaz. Sozluge yazilmaz.
    """
    yeni = {i: dataclasses.replace(t, zh=k, zh_kesin=False) for i, (t, k) in cikarim.items()}
    terimler2 = [yeni.get(id(t), t) for t in terimler]
    hepsi2 = sorted(set(zh_hepsi) | {k for _t, k in cikarim.values()}, key=len, reverse=True)
    eslesmeler = terimleri_bul(zh, en, terimler2, hepsi2, no)
    tr_anahtar = {tr_kucult(t.tr): k for t, k in cikarim.values()}
    for e in eslesmeler:
        k = tr_anahtar.get(tr_kucult(e.terim.tr))
        if k and e.nasil == "zh":
            e.cikarim = k
    return terimler2, hepsi2, eslesmeler


def yakin_anahtarlar(e: Eslesme, zh, en) -> list:
    """
    1b icin: Cince anahtara TEK HARF uzak, Ingilizce isabetle ayni yerde
    gecen diziler. 55'te iki tekerlekli fayton'un anahtari 双轮马车, metinde
    两轮马车; kayit 1b'de anahtarin neden tutmadigi gosterilmeden duruyordu.
    Dort harften kisa anahtarlarda tek harf fark cok gurultu uretir; bakilmaz.
    """
    if not zh or not en:
        return []
    w = max(int(len(zh) * _KONUM_TOLERANSI), 60)  # kisa metinde pencere kapanmasin
    out = []
    for k in _zh_parcalari(e.terim):
        if len(k) < 4:
            continue
        for a in e.konumlar[:10]:
            m = int(a / len(en) * len(zh))
            pencere = zh[max(0, m - w) : m + w]
            for i in range(len(pencere) - len(k) + 1):
                p = pencere[i : i + len(k)]
                if (
                    p != k
                    and _CJK_DIZI.fullmatch(p)
                    and sum(x != y for x, y in zip(p, k)) == 1
                ):
                    out.append(p)
    return list(dict.fromkeys(out))


# ------------------------------------------------------------ 3a: Ingilizce adaylar


def bilinen_adlar(terimler: list, salahiyetler: list) -> set:
    """Ingilizce taramada 'bilinen' sayilan butun adlar, kucuk harfle."""
    adlar = set()
    for t in terimler:
        for a in _ingilizce_adlari(t):
            adlar.add(a.lower())
        for a in getattr(t, "kardesler_en", []) or []:
            adlar.add(a.lower())
    # Capa sozlugu kisi adlari (Klein, Dunn, Neil...): Turkcede ayni yazilir.
    for tr in _capa.sozluk_yukle().values():
        adlar.add(str(tr).lower())
    for s in salahiyetler:
        for parca in re.split(r"[/—–,;]", str(s.get("ingilizce_tuzak") or "")):
            if parca.strip():
                adlar.add(parca.strip().lower())
    return adlar


def _baslik_sonu(en: str, baslik: str | None) -> int:
    """Metnin basindaki baslik satirinin bittigi konum; baslik yoksa -1."""
    ilk = en.split("\n", 1)[0]
    if baslik and ilk.strip() == baslik.strip():
        return len(ilk)
    # Bolum nesnesinde baslik alani yoksa: noktalamasiz, kisa ilk satir.
    if ilk and len(ilk) < 100 and not re.search(r"[.!?\"”…:]\s*$", ilk):
        return len(ilk)
    return -1


def _iyelikte_bol(bas: int, obek: str) -> list:
    """
    [(konum, parca)] -- obegi IC iyelikte boler. Iyelik bir adin sonudur;
    ardindan gelen buyuk harfli kelimeler baska bir addir. 55'te "Joyce's
    Year Path Number" tek aday oluyor ve bilinen bir terimin takma adi
    saniliyordu (Doğum Günü Sayısı); dogrusu Joyce + Year Path Number.
    """
    out, i = [], 0
    for m in re.finditer(r"\S+", obek):
        son = m.end() >= len(obek.rstrip())
        if not son and re.search(r"'s?$", m.group()):
            out.append((bas + i, obek[i : m.end()]))
            i = m.end()
            while i < len(obek) and obek[i] == " ":
                i += 1
    out.append((bas + i, obek[i:]))
    return [(k, p) for k, p in out if p]


def _aday_temizle(en, bas, ham, bilinen, baslik_sonu, sozcukler):
    """Tek bir ad obegini adaya indirger: (konum, ad) ya da None."""
    kelimeler = [(m.start(), m.group()) for m in re.finditer(r"\S+", ham)]
    once = en[max(0, bas - 8) : bas]
    cumle_basi = (bas == 0 or bool(_CUMLE_SONU.search(once))) and not _UNVAN_NOKTASI.search(
        once
    )
    if 0 <= bas < baslik_sonu:
        cumle_basi = False  # baslik her kelimeyi buyuk yazar; obek olarak tutulur
    if len(kelimeler) == 1:
        w = _IYELIK.sub("", kelimeler[0][1])
        if w in _SIRADAN:
            return None
        # Cumle basindaki tek kelime: korpus sozcugu tanimiyorsa (hic kucuk
        # yazilmamis) yine de addir. Korpus verilmemisse eski kural: atilir.
        if cumle_basi and (not sozcukler or _siradan_mi(w, sozcukler)):
            return None
    elif cumle_basi and sozcukler:
        # Ilk kelime buyuk harfi cumleden almistir. Siradan bir sozcukse ve
        # ardindan bir AD geliyorsa atilir: "Congratulations Miss Anna" ->
        # "Miss Anna" (55 ¶61). Geri kalan da hep siradansa obek bir
        # basliktir ("Birth Month Path Number") ve oldugu gibi kalir.
        ilk = kelimeler[0][1]
        cumleden = (
            sozcukler.cumleden_buyumus(ilk)
            if isinstance(sozcukler, Korpus)
            else _siradan_mi(ilk, sozcukler)
        )
        if cumleden and any(not _siradan_mi(k, sozcukler) for _o, k in kelimeler[1:]):
            kelimeler = kelimeler[1:]
        elif cumleden and all(_IYELIK.sub("", k) in _SIRADAN for _o, k in kelimeler[1:]):
            # "Thank God" (56 ¶17, ¶20): cumle basindan buyumus bir sozcuk,
            # ardinda yalniz buyuk yazilan siradan sozcukler (God, Lord).
            # Baslik degil cumle basidir.
            return None
    # Obegin ORTASINDAKI hitap adin basidir: "Congratulations Miss Anna"
    # (55 ¶61) -> "Miss Anna". Korpus sayimi bunu ayiramaz ("Congratulations"
    # bes kez kucuk, uc kez cumle ortasinda buyuk yazilmis). Hitap sondaysa
    # ("Praise the Lady") dokunulmaz.
    for i in range(1, len(kelimeler) - 1):
        if kelimeler[i][1].rstrip(".") in _HITAP:
            kelimeler = kelimeler[i:]
            break
    # Bastaki siradan sozcuk ("The Hanged Man" -> "Hanged Man" degil,
    # ama "When Klein" -> "Klein"). Ardindan kalan kucuk harfli baglac da
    # atilir: "In the Divination Club" -> "the Divination Club" kaliyordu;
    # "Praise the Goddess" -> "the Goddess" 48'de 棕发 ile eslesmisti.
    while len(kelimeler) > 1 and (
        kelimeler[0][1] in _SIRADAN or kelimeler[0][1] in _BAGLAC
    ):
        kelimeler = kelimeler[1:]
    sozler = [k for _o, k in kelimeler]
    # Bilinen bir unvan + ad: "Corpse Collector Frye" (46). Butun obek bir
    # Mertebe'nin takma adi sanilip Frye kayboluyordu; aday Frye'dir. Unvan
    # siradan kelimelerden kurulur; "Dunn Smith"teki Dunn bir addir, unvan
    # degil.
    if sozcukler:
        for i in range(1, len(sozler)):
            onek, kalan = sozler[:i], sozler[i:]
            if kalan[0].lower() in _BAGLAC or onek[-1].lower() in _BAGLAC:
                continue
            if (
                all(_siradan_mi(k, sozcukler) for k in onek)
                and _tam_bilinen(" ".join(onek), bilinen)
                and all(not _siradan_mi(k, sozcukler) for k in kalan)
            ):
                kelimeler, sozler = kelimeler[i:], kalan
                break
    ad = _IYELIK.sub("", " ".join(sozler))
    if not ad or ad in _SIRADAN or ad[:-1] in _SIRADAN or len(ad) < 3:
        return None  # ad[:-1]: cogul siradan sozcuk (Sirs)
    if _bilinen_mi(ad, bilinen):
        return None
    if all(_IYELIK.sub("", k).lower() in bilinen for k in sozler):
        return None  # "Klein Moretti": parcalarin hepsi biliniyor
    # Lakap + bilinen ad: "Old Neil" (55 ¶53). Bastaki siradan sozcukler
    # atilinca kalan ad TAM olarak biliniyorsa bu yeni bir ad degil, bilinen
    # kisidir. Eski surum onu aday sayip 瑞尔·比伯 ile eslestiriyordu. Dar
    # tutulur: kalan gercek bir ad kelimesi tasimali ve dikis yeri baglac
    # olmamali; yoksa "Age of Steam" ("of Steam" bir ilahin adinda geciyor)
    # ve "Spiritual Vision" ("Vision") gibi gercek adaylar da dusuyor.
    if sozcukler:
        for i in range(1, len(sozler)):
            onek, kalan = sozler[:i], sozler[i:]
            if not all(_siradan_mi(k, sozcukler) for k in onek):
                break
            if onek[-1].lower() in _BAGLAC or kalan[0].lower() in _BAGLAC:
                continue
            if any(not _siradan_mi(k, sozcukler) for k in kalan) and _tam_bilinen(
                _IYELIK.sub("", " ".join(kalan)), bilinen
            ):
                return None
    return bas + kelimeler[0][0], ad


def aday_adlar(
    en: str,
    bilinen: set,
    en_kucuk: int = 1,
    baslik_sonu: int = -1,
    sozcukler: frozenset = frozenset(),
) -> list:
    """
    [Aday] -- Ingilizce metinde buyuk harfle gecen, hicbir sozlukte olmayan
    ad obekleri. Cumle basindaki tek kelimeler elenir (orada her kelime
    buyuk harflidir); unvandan sonraki ad ("Mr. Glacis") cumle basi sayilmaz.

    en_kucuk: tek kelimelik adayin en az gecis sayisi. Eski varsayilan 2
    idi ve tek gecen adlari (54'te Alfalfa gemisi, Anna) dusuruyordu; cok
    kelimeli obekler zaten tek geciste aday oluyordu.

    sozcukler: korpusun kucuk harfli sozcukleri (bkz. kucuk_sozcukler).
    Verilirse uc sey daha yapilir:
      - Cumle basindaki tek kelime, korpusta hic kucuk yazilmamissa tutulur
        (Angelica) ve siradansa atilir (All).
      - Tek kelimelik bir ad cok kelimeli bir adayin parcasiysa ayri aday
        olmaz, o adayin parcalari olarak yazilir: 55'te "Joyce ×2" ve
        "Meyer ×2", "Joyce Meyer ×4"un yanina ayri satirlar diye dusuyordu.
      - Tek kelimelik adin sayisi butun gecisleridir, cumle basindakiler
        dahil (55'te Anna ×5 cikiyordu; metinde cok daha fazla).
    """
    konum: dict = {}
    for m in _AD_OBEGI.finditer(en):
        for bas, ham in _iyelikte_bol(m.start(), m.group()):
            sonuc = _aday_temizle(en, bas, ham, bilinen, baslik_sonu, sozcukler)
            if sonuc:
                konum.setdefault(sonuc[1], []).append(sonuc[0])

    parcalar: dict = defaultdict(dict)
    if sozcukler:
        coklu = [a for a in konum if " " in a]
        for ad in [a for a in konum if " " not in a]:
            evler = [p for p in coklu if ad in p.split()]
            if evler:
                ev = max(evler, key=lambda p: len(konum[p]))
                parcalar[ev][ad] = len(konum.pop(ad))
        for ad in [a for a in konum if " " not in a]:
            if not _siradan_mi(ad, sozcukler):
                d = re.compile(r"(?<![\w-])" + re.escape(ad) + r"(?![\w-])")
                konum[ad] = [m.start() for m in d.finditer(en)] or konum[ad]

    out = []
    for ad, ks in sorted(konum.items(), key=lambda x: (-len(x[1]), x[1][0])):
        if len(ks) >= en_kucuk or " " in ad:
            # Yalniz baslikta gecen ad "başlık"tir ve eslestirilmez. Metinde de
            # geciyorsa siradan adaydir: 48'de "Hanass Vincent" basliktan
            # basliyor diye 海纳斯·凡森特 ile hic eslesmiyordu.
            tur = "başlık" if all(0 <= k < baslik_sonu for k in ks) else ""
            out.append(Aday(ad, len(ks), ks, "en", tur, parcalar=dict(parcalar.get(ad, {}))))
    return out


def parcalari_ac(aday: Aday, en: str) -> list:
    """
    Takma ad olarak bir terime baglanan adayin parcalari yeniden aday olur:
    parcalar bir kisinin adiysa, obek gidince ad da kayboluyordu.
    """
    out = []
    for p in aday.parcalar:
        d = re.compile(r"(?<![\w-])" + re.escape(p) + r"(?![\w-])")
        ks = [m.start() for m in d.finditer(en)]
        if ks:
            out.append(Aday(p, len(ks), ks, "en"))
    return out


def ilk_ingilizce_bolum(ad: str, en_bolumler: dict, simdiki: int):
    """Adin Ingilizce metinde gectigi ilk bolum (simdikiden once ya da o)."""
    d = re.compile(r"(?<![\w-])" + re.escape(ad) + r"(?![\w-])")
    for no in sorted(en_bolumler):
        if no > simdiki:
            break
        if d.search(en_bolumler[no].metin):
            return no
    return None


def takma_ad_puani(
    aday: Aday,
    en_uzunluk: int,
    zh_uzunluk: int,
    eslesmeler: list,
    sozcukler=frozenset(),
    en_bulunan: set | None = None,
) -> tuple:
    """
    Aday aslinda bilinen bir terimin baska bir Ingilizce adi mi? Iki sinama:
      1. Yazilis neredeyse ayni (Spiritual Vision ~ Spirit Vision).
      2. Ortak bir kelime VE ayni yerde: terimin gecislerinden biri adayin
         gecislerinden birine oransal olarak yakin (Foodaholic Empire,
         54 ¶10'da, Gourmet Empire'in Cincesi 大吃货帝国 ile ayni yerde).
    Yalniz ortak kelime yetmez: Balam Empire baska yerde gecer.
      3. Bilesik ad (en guclu kanit): adayin icinde Ingilizceyle bulunmus bir
         terimin (X) adi gecer, ve ayni yerde Cinceyle bulunmus, Ingilizce
         adi olmayan bir terimin (Y) Turkcesi X'in Turkcesini icerir. 55:
         "Astromancy Manual" ⊃ Astromancy (Müneccimlik); ayni yerde 占星手册
         (Müneccimlik Kılavuzu). Aday Y'nin adidir, X'in degil.
    Ilk tutan degil EN IYI eslesme doner: eski surum ilk tutani donduruyordu
    ve "Astromancy Manual"i Müneccimlik'e bagliyordu.

    2'deki ortak kelime GENEL olabilir (kingdom, empire: korpusta kucuk de
    yazilir). 56 ¶59'da "Feynapotter Kingdom" yalniz 'kingdom' yuzunden
    ayni paragraftaki Loen Krallığı'na baglaniyordu. Genel kelimeyle kurulan
    bag en dusuk puani alir ve yalniz terim YETIMSE kurulur: Cinceyle
    bulunmus, hicbir Ingilizce adi bu bolumde gecmiyor (en_bulunan disinda).
    Foodaholic Empire boyledir (Gourmet Empire hic gecmiyor). Ayni terime
    baska aday da baglaniyorsa genel bag dusurulur (takma_adlari_coz).
    Dondurur: (Eslesme ya da None, puan ya da None).
    """
    ad = aday.ad.lower()
    ad_kelimeleri = set(re.findall(r"[a-z]{4,}", ad))
    araliklar = [(k, k + len(aday.ad)) for k in aday.konumlar]
    en_iyi, en_iyi_puan = None, None

    def aday_puan(e, puan):
        nonlocal en_iyi, en_iyi_puan
        if en_iyi_puan is None or puan > en_iyi_puan:
            en_iyi, en_iyi_puan = e, puan

    # 3. bilesik ad
    icteki = [e for e in eslesmeler if e.nasil != "zh" and _icinde(e.konumlar, araliklar)]
    for x in icteki:
        xk = tr_kucult(x.terim.tr)
        for y in eslesmeler:
            if y is x or y.nasil != "zh" or _ingilizce_adlari(y.terim):
                continue
            if xk not in tr_kucult(y.terim.tr):
                continue
            f = _oransal_fark(aday.konumlar, en_uzunluk, y.konumlar, zh_uzunluk)
            if f is not None and f < _KONUM_TOLERANSI:
                aday_puan(y, (3, -f))

    for e in eslesmeler:
        adlar = {a.lower() for a in _ingilizce_adlari(e.terim)}
        if not adlar:
            continue
        oran = max(difflib.SequenceMatcher(None, ad, a).ratio() for a in adlar)
        if oran >= 0.8:
            aday_puan(e, (2, oran))
            continue
        ortak = ad_kelimeleri & {w for a in adlar for w in re.findall(r"[a-z]{4,}", a)}
        if not ortak:
            continue
        uzunluk = zh_uzunluk if e.nasil == "zh" else en_uzunluk
        f = _oransal_fark(aday.konumlar, en_uzunluk, e.konumlar, uzunluk)
        if f is None or f >= _KONUM_TOLERANSI:
            continue
        if any(_ad_kokulu(w, sozcukler) for w in ortak):
            aday_puan(e, (1, -f))
        elif e.nasil == "zh" and (en_bulunan is None or id(e.terim) not in en_bulunan):
            aday_puan(e, (0, -f))
    return en_iyi, en_iyi_puan


def takma_ad_mi(
    aday: Aday,
    en_uzunluk: int,
    zh_uzunluk: int,
    eslesmeler: list,
    sozcukler=frozenset(),
    en_bulunan: set | None = None,
):
    """takma_ad_puani'nin yalniz eslesmesi (Eslesme ya da None)."""
    return takma_ad_puani(aday, en_uzunluk, zh_uzunluk, eslesmeler, sozcukler, en_bulunan)[0]


def takma_adlari_coz(
    adaylar: list,
    en: str,
    zh: str | None,
    eslesmeler: list,
    sozcukler=frozenset(),
    en_bulunan: set | None = None,
) -> list:
    """
    [(aday, Eslesme ya da None)] -- adaylarin sirasiyla. Yalniz GENEL bir
    ortak kelimeyle kurulan bag (puan 0), terime baska aday baglanmiyorsa
    kalir. 56 ¶59: "Loen Kingdom" ('loen' ayirt edici) ve "Feynapotter
    Kingdom" (yalniz 'kingdom') ikisi de Loen Krallığı'na baglaniyordu.
    Yanlis bag bir adi saklar; baglanmayan bir varyant yalniz bir aday
    satiridir, bu yuzden suphede bag kurulmaz.
    """
    puanli = [
        (a, *takma_ad_puani(a, len(en), len(zh or ""), eslesmeler, sozcukler, en_bulunan))
        for a in adaylar
    ]
    talip = Counter(id(e.terim) for _a, e, _p in puanli if e is not None)
    out = []
    for a, e, puan in puanli:
        if e is not None and puan[0] == 0 and talip[id(e.terim)] > 1:
            e = None
        out.append((a, e))
    return out


def _icinde(konumlar, araliklar) -> bool:
    return bool(konumlar) and all(any(a <= k < b for a, b in araliklar) for k in konumlar)


def ic_isabetleri_at(eslesmeler: list, takma_adlar: list) -> list:
    """
    Ingilizceyle bulunmus bir terimin BUTUN gecisleri, baska bir terime
    baglanmis daha uzun bir adin icindeyse isabet curuktur ve atilir. 55'te
    "Astromancy Manual" Müneccimlik Kılavuzu'nun adidir; icindeki
    "Astromancy" Müneccimlik'i 1b'ye "dogrulanmamis" diye sokuyordu.
    """
    araliklar = [(k, k + len(a.ad)) for a, _e in takma_adlar for k in a.konumlar]
    hedefler = [e for _a, e in takma_adlar]
    return [
        e
        for e in eslesmeler
        if e.nasil == "zh"
        or any(e is h for h in hedefler)
        or not _icinde(e.konumlar, araliklar)
    ]


# ------------------------------------------------------------ 3b: Cince adaylar

# Ad sinirini bulmak icin geriye/ileriye yururken durulan karakterler.
# Cince bosluksuzdur: "见格拉西斯先生" icinde ad 格拉西斯'tir, 见 bir fiil.
# Liste tam degildir; kacan bir fiil adin onune yapisir ("告诉格拉西斯") ve
# _sonek_daralt bunu, ayni adin daha kisa bir gecisi varsa duzeltir.
_DUR = set(
    "的了是在和与对向给把被见看望问说道找请叫让跟同位个这那及我你他她它们您其将从于为以而并也都"
    "就还又再才只很更最不没无有着过地得之此该每各某啊吗呢吧呀哦嗯么什怎如若虽但却且因所当时后前"
    "里外上下中内间边旁面部头身听想知觉到遇称呼名做像替帮由经已正刚"
)
_SAG_DUR = _DUR | set("周围等手家")
_UNVAN_ZH = re.compile(r"先生|女士|小姐|夫人|太太|阁下|大人|主教|队长|船长|教授|医生")
_TIRNAK_ZH = re.compile(r"[“‘「『]([^“”‘’「」『』，。！？：；、…\s]{1,8})[”’」』]")
_AD_VERME_ZH = re.compile(r"称呼我|叫做|名叫|叫我|名为")


def _ses_icinde(zh: str, i: int) -> bool:
    """
    zh[i] bir ses dizisinin ICINDE mi: kendisi ve iki komsusu da ses harfi.
    Durma listesi ile ses harfleri dort karakter paylasir (里 内 因 什); 56'da
    "而特里斯先生" 斯'ye, "费内波特" 波特'ye kesiliyordu. Yalniz IKI yani ses
    harfi olan durma harfi gecilir, kenardaki gecilmez: "这里安娜小姐" 安娜
    kalir. Bu yuzden bas harfi durma harfi olan ad (因蒂斯) yine kesilir:
    sol kenardaki 因, 因为/因此'den ayirt edilemez.
    """
    return (
        0 < i < len(zh) - 1
        and zh[i] in _SES_HARFLERI
        and zh[i - 1] in _SES_HARFLERI
        and zh[i + 1] in _SES_HARFLERI
    )


def _sola_ad(zh: str, bitis: int, dur=_DUR, en_cok: int = 8) -> str:
    i = bitis
    while (
        i > 0
        and bitis - i < en_cok
        and _CJK_DIZI.match(zh[i - 1])
        and (zh[i - 1] not in dur or _ses_icinde(zh, i - 1))
    ):
        i -= 1
    return zh[i:bitis]


def _saga_ad(zh: str, bas: int, dur=_SAG_DUR, en_cok: int = 8) -> str:
    """Ileriye yurur; bir unvanin BASINDA durur (斯蒂夫先生). 夫, 太 gibi
    karakterleri durma listesine koymak 斯蒂夫'i 斯蒂'ye kesiyordu."""
    i = bas
    while (
        i < len(zh)
        and i - bas < en_cok
        and _CJK_DIZI.match(zh[i])
        and (zh[i] not in dur or _ses_icinde(zh, i))
        and not _UNVAN_ZH.match(zh, i)
    ):
        i += 1
    return zh[bas:i]


def _sonek_daralt(adlar: set) -> dict:
    """{ham: dar} -- "告诉格拉西斯" icin, kumede "格拉西斯" de varsa ona daralt."""
    out = {}
    for a in adlar:
        sonekler = [b for b in adlar if b != a and len(b) >= 2 and a.endswith(b)]
        out[a] = min(sonekler, key=len) if sonekler else a
    return out


def zh_bilinenler(zh_hepsi: list) -> tuple:
    """(tam anahtarlar, nokta ile bolunmus adlarin parcalari) -- sozluk + capa."""
    tam = set(zh_hepsi)
    try:
        tam |= {str(k) for k in _capa.sozluk_yukle().keys() if _CJK_DIZI.search(str(k))}
    except Exception:  # capa'nin anahtarlari Cince degilse 3b yalniz sozlukle calisir
        pass
    parcalar = {p for k in tam for p in k.split("·") if len(p) >= 2}
    return tam, parcalar


def _ortak_sonek(dizeler: list) -> str:
    s = dizeler[0]
    for d in dizeler[1:]:
        while s and not d.endswith(s):
            s = s[1:]
    return s


def _ortak_onek(dizeler: list) -> str:
    s = dizeler[0]
    for d in dizeler[1:]:
        while s and not d.startswith(s):
            s = s[:-1]
    return s


def _noktali_uzlas(grup: list) -> list:
    """
    Ayni cekirdegi (noktanin iki yanindaki harfler) paylasan gecisler tek
    ada indirgenir: sol parcalarin ortak soneki, sag parcalarin ortak oneki.
    Durma listesi Cincenin sozcuk sinirini bilmez; 55'te ayni ad dort gecisin
    ikisinde "粗略判断乔伊斯·迈尔会遭" ve "乔伊斯·迈尔现" diye kesiliyordu. Ad,
    gecislerin hepsinde ortak kalan kisimdir. Ortak kisim iki harften kisaysa
    (iki farkli ad ayni cekirdegi paylasiyor olabilir) gecisler oldugu gibi
    birakilir.
    """
    if len(grup) > 1:
        sol = _ortak_sonek([d[0] for d in grup])
        sag = _ortak_onek([d[-1] for d in grup])
        if len(sol) >= 2 and len(sag) >= 2:
            return ["·".join([sol, *grup[0][1:-1], sag])]
    return list(dict.fromkeys("·".join(d) for d in grup))


def _ses_soneki(ad: str) -> str:
    """
    Unvandan onceki ANLAMLI on ek atilir, sesle cevrilmis ad kalir: 56 ¶6
    "父亲韦恩" (babasi Wayne) -> 韦恩. Butunu sesle cevrilmis sayilan ad
    (老尼尔, 安提哥努斯: ses harfi listesi tam degildir) ve ses soneki
    olmayan niteleme (棕发) oldugu gibi kalir.
    """
    if _sesle_mi(ad):
        return ad
    i = len(ad)
    while i > 0 and ad[i - 1] in _SES_HARFLERI:
        i -= 1
    return ad[i:] if len(ad) - i >= 2 else ad


def zh_adaylari(zh: str, bilinen: tuple) -> list:
    """[Aday] -- Cincede ad isareti tasiyan, sozlukte ve capada olmayan diziler."""
    tam, parcalar = bilinen
    # Bu bolumde gecen bilinen anahtarlar: durma listesi bir adi bilinen bir
    # anahtarin ICINDE kesebilir (亨利·奥古斯都一世 -> 亨利·奥古斯, 都 bir durma
    # harfi; 48). O parca yeni bir ad degildir.
    mevcut = [k for k in tam if len(k) >= 3 and k in zh]

    def biliniyor(ad: str) -> bool:
        if ad in tam or ad in parcalar:
            return True
        if len(ad) >= 3 and any(ad in k for k in mevcut):
            return True  # iki harflik ad (安娜) baska bir adin icinde gecebilir (奥利安娜)
        p = [x for x in ad.split("·") if x]
        return len(p) > 1 and all(x in tam or x in parcalar for x in p)

    ham: dict = {}  # ad -> tur

    for m in _UNVAN_ZH.finditer(zh):
        ad = _sola_ad(zh, m.start())
        if len(ad) >= 2:
            ham.setdefault(ad, "unvan")
    noktali: dict = defaultdict(list)  # cekirdek -> [dilimler]
    for i, ch in enumerate(zh):
        if ch != "·":
            continue
        sol = _sola_ad(zh, i)
        if not sol or (i - len(sol) >= 1 and zh[i - len(sol) - 1] == "·"):
            continue  # zincirin ilk noktasi degil (X·Y·Z'nin ikinci noktasi)
        dilimler, j = [sol], i
        while j < len(zh) and zh[j] == "·":
            sag = _saga_ad(zh, j + 1)
            if not sag:
                break
            dilimler.append(sag)
            j += 1 + len(sag)
        if len(dilimler) >= 2:
            cekirdek = (dilimler[0][-1], *dilimler[1:-1], dilimler[-1][0])
            noktali[cekirdek].append(dilimler)
    for grup in noktali.values():
        for ad in _noktali_uzlas(grup):
            ham.setdefault(ad, "noktalı ad")
    for m in _AD_VERME_ZH.finditer(zh):
        ad = _saga_ad(zh, m.end())
        if len(ad) >= 2:
            ham.setdefault(ad, "ad verme")
    for m in _TIRNAK_ZH.finditer(zh):
        ad = m.group(1)
        if _CJK_DIZI.fullmatch(ad.replace("·", "")):
            ham.setdefault(ad, "gemi?" if ad.endswith("号") else "tırnaklı")

    # Baska bir adayin uc harfe kadar uzatilmis hali o adaydan turemistir:
    # 梦境占卜法 ⊃ 梦境占卜 (55 ¶33, ¶53), ikisi ayri satir oluyordu. Yalniz
    # bas ya da sondan uzama; noktali adlar (yukarida uzlastirildi) ve gemi
    # adlari (苜蓿号 ⊃ 苜蓿 olabilir, ad 号'yla birliktedir) haric. Kok en az
    # uc harf: iki harflik bir ad (安娜) baska bir adin basi olabilir (安娜贝尔).
    ust = {
        a
        for a, tur in ham.items()
        if "·" not in a
        and tur != "gemi?"
        and any(
            b != a
            and "·" not in b
            and len(b) >= 3
            and len(a) - len(b) <= 3
            and (a.startswith(b) or a.endswith(b))
            for b in ham
        )
    }
    ham = {a: tur for a, tur in ham.items() if a not in ust}
    # Yalniz geriye yurunerek bulunan adlar daraltilir; noktali ad ve
    # tirnakli ifadenin siniri zaten bellidir.
    dar = _sonek_daralt(set(ham))
    # Noktali bir adin parcasi tek basina aday olmaz: "罗塞尔·古斯塔夫·三世先生"
    # unvandan geriye yururken noktada durur ve yalniz 三世'yu verir.
    nokta_parcalari = {p for a in ham if "·" in a for p in a.split("·")}
    # Tirnakli ifadenin sayisi butun gecislerdir; kaci tirnak icinde ayrica
    # sayilir. 56'da 英雄 ×3 "(tırnaklı)" diye cikiyordu, oysa yalniz biri
    # tirnakliydi: tirnak bir vurgu, kelime siradan.
    tirnak_sayisi = Counter(m.group(1) for m in _TIRNAK_ZH.finditer(zh))
    out: dict = {}
    for a, tur in ham.items():
        ad = _ses_soneki(dar[a]) if tur == "unvan" else a
        if biliniyor(ad) or ad in out or ad in nokta_parcalari:
            continue
        konumlar = [m.start() for m in re.finditer(re.escape(ad), zh)]
        if konumlar:
            tirnakli = tirnak_sayisi[ad] if tur in ("tırnaklı", "gemi?") else None
            out[ad] = Aday(ad, len(konumlar), konumlar, "zh", tur, tirnakli=tirnakli)
    return sorted(out.values(), key=lambda a: a.konumlar[0])


def ilk_cince_bolum(ad: str, zh_bolumler: dict, simdiki: int):
    for no in sorted(zh_bolumler):
        if no > simdiki:
            break
        if ad in zh_bolumler[no].metin:
            return no
    return None


def _sesle_mi(ad: str) -> bool:
    """Cince aday sesle mi cevrilmis (乔伊斯·迈尔), anlamla mi (生日灵数)?"""
    h = [c for c in ad if c != "·"]
    return bool(h) and sum(c in _SES_HARFLERI for c in h) / len(h) >= 0.6


def _hece(ad: str) -> int:
    return sum(max(1, len(re.findall(r"[aeiouy]+", w.lower()))) for w in ad.split())


def adaylari_esle(
    en_adaylar: list,
    zh_adaylar: list,
    en_uzunluk: int,
    zh_uzunluk: int,
    sozcukler: frozenset = frozenset(),
) -> None:
    """
    Ayni adin Ingilizce ve Cince adaylarini eslestirir (Alfalfa ↔ 苜蓿号).

    Iki metin ayni sirayla ilerler; eslesme de SIRAYI KORUR: iki aday
    listesi ilk gecislerine gore dizilir ve en cok cifti, toplam konum
    farki en az olacak sekilde, capraz baglanti olmadan eslestiren hizalama
    secilir. Yalniz en yakin cifti secmek ayni paragraftaki iki adi
    caprazliyordu (54 ¶79: Berserk Sea ↔ 苜蓿号, Alfalfa ↔ 狂暴海).
    Bir cift icin: oransal konum farki toleransin altinda; ilk bolumlerin
    uyusmamasi yalniz ceza puanidir. Tirnakli siradan ifadeler (生意) ad
    degildir, eslestirilmez.

    55'teki iki yanlis ciftten sonra:
      - Konum farki ilk gecislerden degil, EN YAKIN gecis ciftinden olculur
        (bkz. _oransal_fark). 生日灵数 ¶9'da ilk geciyor, Ingilizcesi ¶9'u
        dusurdugu icin ¶11'de; ilk gecislere bakinca ¶8'deki Stevens Street
        daha yakin gorunuyordu.
      - Sesle cevrilmis bir Cince ad (乔伊斯·迈尔, 瑞尔·比伯) yalniz icinde
        gercek bir ad (korpusta hic kucuk yazilmamis kelime) bulunan
        Ingilizce adayla eslesir; "Birth Day Path Number" gibi siradan
        kelimelerden kurulu bir baslikla eslesmez. Anlamla cevrilmis ad
        (苜蓿号 ↔ Alfalfa) her ikisiyle eslesebilir ama gercek ada karsi
        kucuk bir ceza alir. Hece sayisi farki sesle cevrilmis cifte kucuk
        bir ceza ekler (瑞尔比伯 dort, Ray Bieber uc hece).
    """
    if not en_uzunluk or not zh_uzunluk:
        return
    E = sorted(
        (a for a in en_adaylar if a.tur != "başlık"), key=lambda a: a.konumlar[0]
    )
    Z = sorted(
        (a for a in zh_adaylar if a.tur != "tırnaklı"), key=lambda a: a.konumlar[0]
    )

    def fark(e: Aday, z: Aday):
        f = _oransal_fark(e.konumlar, en_uzunluk, z.konumlar, zh_uzunluk)
        if f is None or f >= _KONUM_TOLERANSI:
            return None
        if sozcukler:
            gercek_ad = any(_ad_kokulu(k, sozcukler) for k in e.ad.split())
            if z.tur == "unvan" and not _sesle_mi(z.ad):
                # Unvandan onceki ANLAMLI dizi bir ad degil, nitelemedir:
                # 棕发女士 "kahverengi sacli hanim" (48).
                return None
            if _sesle_mi(z.ad):
                if not gercek_ad:
                    return None
                f += abs(len(z.ad.replace("·", "")) - _hece(e.ad)) * _KONUM_TOLERANSI / 10
            elif gercek_ad and z.tur != "gemi?":
                f += _KONUM_TOLERANSI / 2
        # Ilk bolumlerin uyusmasi bir kanittir ama veto degildir: kisa bir
        # Cince dizi (安娜) baska bir adin icinde daha once gecebilir.
        if e.ilk_bolum and z.ilk_bolum and e.ilk_bolum != z.ilk_bolum:
            f += _KONUM_TOLERANSI / 2
        return f

    n, m = len(E), len(Z)
    # dp[i][j] = (eslesen cift sayisi, -toplam fark): ilk i Ingilizce, ilk j Cince aday
    dp = [[(0, 0.0)] * (m + 1) for _ in range(n + 1)]
    yol = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            secenek = [(dp[i - 1][j], "e"), (dp[i][j - 1], "z")]
            f = fark(E[i - 1], Z[j - 1])
            if f is not None:
                c, d = dp[i - 1][j - 1]
                secenek.append(((c + 1, d - f), "es"))
            dp[i][j], yol[i][j] = max(secenek, key=lambda x: x[0])
    i, j = n, m
    while i > 0 and j > 0:
        if yol[i][j] == "es":
            E[i - 1].es, Z[j - 1].es = Z[j - 1], E[i - 1]
            i, j = i - 1, j - 1
        elif yol[i][j] == "e":
            i -= 1
        else:
            j -= 1


# ------------------------------------------------- 3c: tekrarli, sozluksuz obekler


def _ngramlar(zh: str, en_kisa: int = 2, en_uzun: int = 6) -> Counter:
    sayac = Counter()
    for dizi in _CJK_DIZI.findall(zh):
        for n in range(en_kisa, en_uzun + 1):
            for i in range(len(dizi) - n + 1):
                sayac[dizi[i : i + n]] += 1
    return sayac


# jieba tur etiketleri: ad soylu sozcukler. nr/ns de dahil: jieba 红茶'yi nr,
# 锡伯'yi ns diye etiketliyor; gercek kisi adlari zaten maskeyle eleniyor.
# vn (发展), an (温暖) ve fiil/sifatlar disarida: 54'te gurultunun cogu onlardi.
_AD_ETIKETLERI = {"n", "nr", "ns", "nt", "nz", "nw", "ng"}


def _jieba_adlari(zh: str):
    """Counter -- jieba varsa bolumdeki ad soylu sozcukler; yoksa None."""
    try:
        import jieba
        import jieba.posseg as _ps
    except ImportError:
        return None
    jieba.setLogLevel(60)
    return Counter(
        w.word
        for w in _ps.cut(zh)
        if w.flag in _AD_ETIKETLERI and len(w.word) >= 2 and _CJK_DIZI.fullmatch(w.word)
    )


# n-gram yedeginde obegin ICINDE de bulunamayacak dilbilgisi ekleri: bunlari
# tasiyan obek bir fiil obegidir (轻敲了眉心, 使用哪), terim degil.
_EDAT = set("了着过的地得们吗呢吧哪么")

# Obek kenarinda duramayacak baglac/edat/zamir karakterleri. _DUR'dan
# dardir: 下, 上, 前 gibi yon sozcukleri terimin parcasi olabilir (下午好).
_KENAR = set(
    "的了是在着过地得也都就还又再才只很更最不没有和与把被对向给这那个位们他她它我你您其将从于为以而并"
    "之此该每各某啊吗呢吧呀哦嗯么什怎如若虽但却且因所当说道看见想听到"
)


def tekrarli_obekler(
    zh: str,
    zh_bolumler: dict,
    no: int,
    yayim_nolari: set,
    maske: set,
    en_az: int = 2,
    df_orani: float = 0.2,
    sinir: int = 15,
) -> tuple:
    """
    ([(obek, sayi, [yayimlanmis bolumler])], yontem) -- sozlukte olmayan ama
    daha once cevrilmis olmasi muhtemel terimler.

    Iki yontem:
      jieba (kuruluysa): bolum sozcuklere bolunur, yalniz AD soylu olanlar
        alinir. Fiil ve sifatlar (观察, 推荐, 担忧, 疲惫) burada elenir; ilk
        surumun gurultusunun cogu onlardi. Bilinen bir anahtarla, bu bolumun
        ad adaylariyla ya da bir unvanla cakisan sozcuk atilir.
      n-gram (yedek): bilinen her sey metinden silinir, kalandan 2-6
        karakterlik obekler sayilir; ayni sayida gectigi daha uzun obegin
        icindeki obek atilir (会议 yerine 会议室; 5 karakterlik 轻敲了眉心
        artik iki parcaya bolunmez). Kenari baglac/edat olan obek atilir.

    Iki yontemde de olcut ayni: bu bolumde en az `en_az` kez geciyor;
    ROMANIN TAMAMINDA bolumlerin en fazla `df_orani` kadarinda geciyor;
    bu bolumden once en az bir YAYIMLANMIS bolumde gecmis (karsiligi
    orada). Siralama: bolumdeki sayi, sonra seyreklik.

    Seyreklik butun Cince korpustan olculur, yalniz onceki bolumlerden
    degil: ilk surum 54 icin 53 bolume bakiyordu ve o kadar az bolumde
    观察, 推荐, 忧郁 gibi siradan sozcukler de "seyrek" gorunuyordu. Bin
    kusur bolumde siradan sozcuk yuzlerce bolumde gecer, sahne esyasi
    (图册) birkac yay boyunca.
    """
    maske = {k for k in maske if len(k) >= 2}
    # Bilinen uzun anahtarlarin bas isimleri de bilinir: 占卜俱乐部 → 俱乐部.
    maske |= {k[i:] for k in maske if len(k) >= 4 for i in range(1, len(k) - 2)}
    sozcukler = _jieba_adlari(zh)
    if sozcukler is not None:
        yontem = "jieba"
        aday = {
            w: c
            for w, c in sozcukler.items()
            if c >= en_az
            and not _UNVAN_ZH.fullmatch(w)
            and not any(w in k or k in w for k in maske)
        }
    else:
        yontem = "n-gram"
        temiz = zh
        for k in sorted(maske, key=len, reverse=True):
            temiz = temiz.replace(k, "|")
        temiz = _UNVAN_ZH.sub("|", temiz)
        ham = {
            g: c
            for g, c in _ngramlar(temiz).items()
            if c >= en_az
            and g[0] not in _KENAR
            and g[-1] not in _KENAR
            and not (_EDAT & set(g))
        }
        aday = {
            g: c
            for g, c in ham.items()
            if not any(len(h) > len(g) and g in h and c2 == c for h, c2 in ham.items())
        }

    korpus = [(n, b.metin) for n, b in sorted(zh_bolumler.items()) if n != no]
    if not korpus:
        return [], yontem
    tavan = max(3, int(df_orani * len(korpus)))
    out = []
    for g, c in aday.items():
        gectigi = [n for n, metin in korpus if g in metin]
        if len(gectigi) > tavan:
            continue
        yayimda = [n for n in gectigi if n < no and n in yayim_nolari]
        if yayimda:
            out.append((g, c, yayimda, len(gectigi)))
    out.sort(key=lambda x: (-x[1], x[3], zh.find(x[0])))
    return [(g, c, y) for g, c, y, _df in out[:sinir]], yontem


# ------------------------------------------------- 1d, 1e, 3c: yeni bolumler


def _siradan_ingilizce(e) -> bool:
    """
    Yalniz Ingilizceyle bulunmus words.md kaydi, Ingilizcesi kucuk harfli
    siradan bir sozcuk mu (notebook, pen)? Ayni Ingilizce sozcuk kaynakta
    bircok ayri seyi karsilar; yerlesmis terim diye verilmez, baglamiyla
    1d'ye gider. Buyuk harfli ozel adlar (Lord of Storms) 1'de kalir.
    """
    t = e.terim
    return (
        e.nasil == "en"
        and t.kategori.startswith(lotm.KELIME_KATEGORI)
        and not any(c.isupper() for c in (t.en or ""))
    )


_ACIK_TIRNAK = set("“‘「『\"")
_KAPALI_TIRNAK = set("”’」』\"")


def _tirnak_dagilimi(zh: str, anahtarlar: dict) -> tuple:
    """(tirnak icindeki gecis sayisi, tirnaksiz gecis sayisi)."""
    tirnakli = duz = 0
    for z, ks in anahtarlar.items():
        for k in ks:
            son = k + len(z)
            ic = k > 0 and son < len(zh) and zh[k - 1] in _ACIK_TIRNAK and zh[son] in _KAPALI_TIRNAK
            tirnakli += ic
            duz += not ic
    return tirnakli, duz


def _capa_adi_mi(ad: str, en: str | None, sozcukler) -> bool:
    """
    Capa degeri bir AD mi? Capanin Turkce kelime capalari (Nergis, Haç,
    Soytarı) ad degildir. Korpus varsa: Ingilizcede cumle ortasinda buyuk
    yazilmis ve hic kucuk yazilmamis. Yoksa: bu bolumun Ingilizcesinde gecer.
    """
    if not re.fullmatch(r"[A-Z][a-z]+(?:[ -][A-Z][a-z]+)*", ad):
        return False
    if isinstance(sozcukler, Korpus) and sozcukler:
        return sozcukler.orta.get(ad, 0) > 0 and sozcukler.hic_kucuk_yazilmamis(ad)
    return bool(en) and bool(re.search(r"(?<![\w-])" + re.escape(ad) + r"(?![\w-])", en))


def capa_adlari(zh, en, capa: dict, eslesmeler: list, sozcukler=frozenset()) -> list:
    """
    [(ad, cince, sayi, ingilizcede_yok)] -- bu bolumde gecen capa sozlugu
    adlari, okuma sirasiyla.

    Capa adlari Ingilizce aday taramasinda "bilinen" sayilir ve aday olmaz;
    ama dokumde hic gorunmuyorlardi: 56'da Glacis, Klein, Benson, Melissa
    sablonun terim tablosuna (ve kapanis denetimine) hic girmedi. Bulunmus
    bir terimin anahtarinin icinde kalan gecis sayilmaz (所罗门 ⊂ 所罗门帝国).
    ingilizcede_yok: Cincesi geciyor, ad Ingilizcede gecmiyor; ceviri adi
    baska yazmis olabilir (56: 弗萨克 Feysac, Ingilizcesi "Frosac").
    """
    if not zh or not capa:
        return []
    kapsam = [
        (k, k + len(z)) for e in eslesmeler for z, ks in e.anahtarlar.items() for k in ks
    ]
    anahtarlar = [str(k) for k in capa if _CJK_DIZI.search(str(k))]
    out = []
    for z in anahtarlar:
        ad = str(capa[z]).strip()
        if not _capa_adi_mi(ad, en, sozcukler):
            continue
        desen = lotm.zh_desen(z, [b for b in anahtarlar if z in b and b != z])
        ks = [
            m.start()
            for m in desen.finditer(zh)
            if not any(a <= m.start() < b for a, b in kapsam)
        ]
        if not ks:
            continue
        yok = bool(en) and not re.search(
            r"(?<![\w-])" + re.escape(ad) + r"(?![\w-])", en
        )
        out.append((ks[0], ad, z, len(ks), yok))
    return [x[1:] for x in sorted(out)]


@dataclass
class Kok:
    parca: str  # bolumde gecen ses parcasi
    sayi: int
    konumlar: list
    anahtar: str  # parcanin geldigi bilinen anahtar
    sahip: str  # o anahtarin Turkce terimi
    sahip_en: str | None = None
    baglam: str = ""
    en_es: str | None = None  # Ingilizcede ayni yerdeki aday


_SES_DIZISI = re.compile("[" + "".join(sorted(_SES_HARFLERI)) + "]{3,}")


def kok_isabetleri(zh, sahipler: dict, en_adaylar=(), en_uzunluk: int = 0) -> list:
    """
    [Kok] -- bilinen bir anahtarin SES PARCASI (en az uc harf), bilinen
    hicbir anahtarin tam gecisi icinde olmadan geciyor.

    anahtar_cikar tersini yapar (aday bilinen bir anahtari icerir). Burada
    bilinen bir adin koku yeni bir bilesikte gecer: 56 ¶59'da 费内波特王国,
    Feynapotter Yaylası Kahvesi'nin (费内波特高原咖啡) kokuyle kurulmus. Ad
    isareti tasimadigi icin hic aday olmuyor, Ingilizcesi de yeni bir ad gibi
    gorunuyordu. sahipler: {anahtar: (Turkce, Ingilizce)}.
    """
    if not zh or not sahipler:
        return []
    kapali = [False] * len(zh)
    for k in sorted(sahipler, key=len, reverse=True):
        for m in re.finditer(re.escape(k), zh):
            kapali[m.start() : m.end()] = [True] * (m.end() - m.start())
    parcalar: dict = {}
    for k in sorted(sahipler, key=len, reverse=True):
        for dizi in _SES_DIZISI.findall(k):
            for n in range(len(dizi), 2, -1):
                for i in range(len(dizi) - n + 1):
                    p = dizi[i : i + n]
                    if p != k and p not in sahipler:
                        parcalar.setdefault(p, k)
    bulunan: dict = {}
    for p in sorted(parcalar, key=len, reverse=True):
        for m in re.finditer(re.escape(p), zh):
            a, b = m.span()
            if any(kapali[a:b]):
                continue
            kapali[a:b] = [True] * (b - a)
            bulunan.setdefault(p, []).append(a)
    out = []
    for p, ks in bulunan.items():
        k = parcalar[p]
        tr, en_ad = sahipler[k]
        kok = Kok(p, len(ks), ks, k, tr, en_ad, _zh_baglam(zh, ks[0], len(p)))
        # Ingilizcede ayni yerdeki aday: sahibin Ingilizce adiyla kelime
        # paylasan once (Feynapotter), yoksa en yakin.
        if en_uzunluk:
            kelimeler = set(re.findall(r"[a-z]{4,}", (en_ad or "").lower()))
            secenek = []
            for a in en_adaylar:
                f = _oransal_fark(a.konumlar, en_uzunluk, ks, len(zh))
                if f is not None and f < _KONUM_TOLERANSI:
                    ortak = bool(kelimeler & set(re.findall(r"[a-z]{4,}", a.ad.lower())))
                    secenek.append((not ortak, f, a.ad))
            if secenek:
                kok.en_es = min(secenek)[2]
        out.append(kok)
    return sorted(out, key=lambda x: x.konumlar[0])


def cevrilmis_kokler(terimler: list, sozcukler) -> dict:
    """
    {ingilizce ad koku (kucuk harf): Turkce terim} -- Turkcesinde AYNEN
    yazilmayan ad kokleri. Ad kurali: kisi ve yer adi Ingilizcedeki gibi
    yazilir; sozlukte koku cevrilmis bir kayit (Caesar Port -> Sezar Limanı,
    Evernight Goddess -> Ebedî Gece Tanrıçası) bu kuralin istisnasidir ve
    ayni koku tasiyan yeni ad da ona uyar. Kok: korpusta cumle ortasinda buyuk
    yazilmis, hic kucuk yazilmamis kelime; Kingdom, Port gibi genel sozcukler
    kok degildir.
    """
    out: dict = {}
    if not (isinstance(sozcukler, Korpus) and sozcukler):
        return out
    for t in terimler:
        if not t.tr:
            continue
        trk = tr_kucult(t.tr)
        for ad in _ingilizce_adlari(t):
            for w in re.findall(r"[A-Z][a-z]{2,}", ad):
                if w in _SIRADAN or w.lower() in trk:
                    continue
                if sozcukler.orta.get(w, 0) > 0 and sozcukler.hic_kucuk_yazilmamis(w):
                    out.setdefault(w.lower(), t.tr)
    return out


def _ad_karari(ad: str, sozcukler, kokler: dict, es: "Aday | None" = None) -> str | None:
    """
    Ingilizce adayin Turkcesi mekanik olarak belli mi? Koku cevrilmis bir
    kelime tasiyorsa o kayda uyar; butun kelimeleri ad koku ise (korpusta
    hic kucuk yazilmamis) ad kurali geregi Ingilizcedeki gibi yazilir.
    Siradan kelime tasiyan obek (Sacred Emblem, Fourth Epoch) icin karar
    yoktur. Hitap (Miss, Mr) adin parcasi sayilmaz.

    Kesin karar yalniz sesle cevrilmis bir Cince adla eslesmis adaya
    verilir (Wayne ↔ 韦恩). Eşsiz aday "buyuk ihtimalle"dir: dil ve halk
    adlari da hic kucuk yazilmaz (56: Mandarin, Cincesi 中文 -> Çince).
    """
    kelimeler = [
        w
        for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", ad)
        if w.lower() not in _BAGLAC and w.rstrip(".") not in _HITAP
    ]
    if not kelimeler:
        return None
    cev = [(w, kokler[w.lower()]) for w in kelimeler if w.lower() in (kokler or {})]
    if cev:
        return (
            "kökü çevrilmiş: "
            + ", ".join(f"{w} → {tr}" for w, tr in cev)
            + "; ad buna göre kurulur"
        )
    if (
        isinstance(sozcukler, Korpus)
        and sozcukler
        and all(sozcukler.hic_kucuk_yazilmamis(w) for w in kelimeler)
    ):
        ad_tr = " ".join(kelimeler)
        if es is not None and _sesle_mi(es.ad):
            return f"Türkçesi: {ad_tr} (ad kuralı: İngilizcedeki gibi yazılır)"
        return (
            f"Türkçesi büyük ihtimalle: {ad_tr} (ad kuralı); sesle çevrilmiş Çince eşi "
            f"bulunamadı: dil, halk ya da sıfat adıysa geçmez"
        )
    return None


# ------------------------------------------------------------------ cikti


def _tek_satir(s, n=None) -> str:
    s = (
        re.sub(r"\s+", " ", str(s or ""))
        .replace("<br><br>", " ¶ ")
        .replace("<br>", " ")
        .strip()
    )
    return s if n is None or len(s) <= n else s[: n - 1] + "…"


def _yayim_ozeti(e: Eslesme) -> str:
    if not e.yayim:
        return "yayımlanmış metinde YOK — ilk kez, karar şimdi"
    return f"yayımlanmış {len(e.yayim)} bölümde (son: {e.yayim[-1]})"


def _aciklama(t):
    if isinstance(t.ham, dict):
        return t.ham.get("aciklama")
    # words.md kayitlari: aciklama Terim nesnesinde ayri bir alandaysa
    return getattr(t, "aciklama", None)


def _bicim_dagilimi(e: Eslesme):
    """
    [(Turkce bicim, sayi)] -- kaydin Turkce bicimleri Cince anahtarlarla
    SIRAYLA eslesiyorsa ("kehanet gök haritası / gök haritası" ↔ "占卜星盘 /
    星盘"), bu bolumde hangi bicimin kac kez gectigi. Eslesmiyorsa None.
    55'te baslik "kehanet gök haritası" idi, oysa bolumde yalniz 星盘 geciyor;
    sablon A.1'e metinde hic gecmeyecek bir bicim yaziyordu.
    """
    t = e.terim
    bicimler = [t.tr, *t.arama_adi]
    anahtarlar = [z.strip() for z in (t.zh or "").split("/") if z.strip()]
    if len(bicimler) < 2 or len(bicimler) != len(anahtarlar) or not e.anahtarlar:
        return None
    return [(b, len(e.anahtarlar.get(z, []))) for b, z in zip(bicimler, anahtarlar)]


_NOT_ARTIGI = re.compile(r"\([^()]*\)|_\d+(?:[–-]\d+)?_|\s+")


def _madde_notu(t):
    """
    words.md maddesinin, Ingilizce ad ve parantez disinda kalan aciklamasi;
    yoksa None. Tek anahtarli cok bicimli kayitta (Şeref Makamı / başköşe,
    上首) hangi bicimin secilecegini yalniz bu not soyler.
    """
    if not t.kategori.startswith(lotm.KELIME_KATEGORI) or not t.cevirmen_notu:
        return None
    kalan = str(t.cevirmen_notu)
    if t.en and kalan.startswith(t.en):
        kalan = kalan[len(t.en) :]
    if len(_NOT_ARTIGI.sub("", kalan).strip(" ;,.\"'“”—–-")) < 12:
        return None
    return _tek_satir(kalan, 300)


def _baglam_satirlari(e: Eslesme, zh: str, en_cok: int = 3) -> list:
    if not zh or not e.anahtarlar:
        return []
    out = []
    for z, ks in e.anahtarlar.items():
        for k in ks:
            out.append(f"  - bağlam: {_zh_baglam(zh, k, len(z))}")
    return out[:en_cok]


def _bolum_yeri(ilk, no, son_yayim, karar: str | None = None) -> str:
    """
    Adayin bolum yeri ve -- mekanik olarak belliyse -- Turkcesi. Yayimlanmis
    bir bolumde gecmis ama Turkcesi burada yazmayan aday icin "A.1" denmez:
    56'da Fourth Epoch, Sacred Emblem, Mandarin boyle A.1 diye verilip
    Turkcesi tahmin ediliyordu (Sacred Emblem 17'de baska bir amblemdi).
    """
    if ilk is not None and ilk < no and ilk <= son_yayim:
        yer = f"ilk: bölüm {ilk}, YAYIMLANMIŞ"
        if karar:
            return f"{yer} — {karar}"
        return f"{yer} — Türkçesi bu dökümde yok; bakılmadan A.1'e alınmaz"
    if ilk is not None and ilk < no:
        yer = f"ilk: bölüm {ilk} (henüz yayımlanmadı)"
    else:
        yer = "ilk kez bu bölümde"
    return f"{yer} — {karar}" if karar else yer


def _terim_satirlari(e: Eslesme, zh, notlar: bool, no: int | None = None) -> list:
    """Dokumde tek bir yerlesmis terimin satirlari."""
    t = e.terim
    kaynak_ad = "words.md" if t.kategori.startswith(lotm.KELIME_KATEGORI) else "sözlük"
    dagilim = _bicim_dagilimi(e)
    gecen = [b for b, n in dagilim if n] if dagilim else []
    bas = f"- **{' / '.join(gecen) if gecen else t.tr}**"
    if t.en:
        bas += f" ← {t.en}"
    bas += f"  ·  {t.yer} ({kaynak_ad}), bölümde ×{e.sayi}"
    if e.nasil == "en":
        bas += " (İngilizceden bulundu)"
    out = [bas]
    if e.cikarim:
        out.append(
            f"  - Çince anahtarı sözlükte YOK; bu bölümde {e.cikarim} olarak geçiyor "
            f"(bileşimden çıkarıldı, anahtara eklenmeli)"
        )
    if e.cok_anlamli:
        out.append(
            f"  - aynı anahtar ayrıca şunların karşılığı: {', '.join(e.cok_anlamli)}"
        )
    if e.kardesler:
        out.append(
            f"  - DİKKAT: {', '.join(e.kardesler)} ayrı bir kayıttır (büyük/küçük harf) ve o da "
            f"bu bölümde; ikisi birbirinin yerine kullanılmaz"
        )
    if t.mertebe_mi and e.nasil == "zh" and not e.kardesler and zh and e.anahtarlar:
        # Mertebe adlarinin cogu siradan bir meslektir (水手, Denizci): ayni
        # sozcuk sahnede siradan anlamda gecebilir. Cince Mertebe adini
        # cogunlukla tirnakla isaretler; dagilim yazilir, karar baglamdadir.
        tirnakli, duz = _tirnak_dagilimi(zh, e.anahtarlar)
        out.append(
            f"  - Mertebe adıyla aynı sözcük (tırnaklı ×{tirnakli}, tırnaksız ×{duz}): "
            f"Mertebe olarak geçiyorsa büyük harf, sıradan meslek anlamında küçük harf "
            f"(Şema 0.6); aynı Yolun başka bir Mertebe adı yerine kullanılmaz"
        )
    if dagilim:
        yok = [b for b, n in dagilim if not n]
        satir = "  - bu bölümde geçen biçim: " + ", ".join(
            f"{b} ×{n}" for b, n in dagilim if n
        )
        if yok:
            satir += f"; {', '.join(yok)} bu bölümde GEÇMİYOR, tabloya yazılmaz"
        out.append(satir)
    elif t.arama_adi:
        out.append(f"  - aynı karşılığın biçimleri: {', '.join(t.arama_adi)}")
        madde = _madde_notu(t)
        if madde:
            out.append(f"  - biçim bağlama göre seçilir; madde notu: {madde}")
            out += _baglam_satirlari(e, zh)
    if e.cok_anlamli and not (t.arama_adi and _madde_notu(t)):
        out += _baglam_satirlari(e, zh)
    if e.kucuk_bicim:
        out.append(
            f"  - metinde küçük harfle: {e.kucuk_bicim} (listedeki büyük harf yalnız "
            f"liste usulü)"
        )
    if t.eski_karsiliklar:
        out.append(f"  - KULLANILMAZ (eski karşılık): {', '.join(t.eski_karsiliklar)}")
    mudahale = (t.ham or {}).get("mudahale") if isinstance(t.ham, dict) else None
    if mudahale in ("ozgun", "degistirme", "birlestirme", "tamamlama"):
        out.append(
            f"  - çeviri katmanı ({mudahale}): kaynakta karşılığı olmayan bilinçli bir "
            f"tercih; kaynağa bakarak kapatılmaz"
        )
    out.append(f"  - {_yayim_ozeti(e)}")
    aciklama = _aciklama(t)
    kapi = _sayi(t.bolum_siniri)
    if aciklama and no is not None and kapi is not None and kapi > no:
        # Kapi kelimeyi degil, aciklamanin ne zaman okunacagini belirler:
        # sonraki bir bolumde acilan tazim ismi buraya girmez. Sayi yazilmaz.
        out.append("  - açıklama gösterilmedi: bu bölümden sonra açılıyor")
    elif aciklama:
        out.append(f"  - açıklama: {_tek_satir(aciklama)}")
    if notlar and t.cevirmen_notu:
        out.append(f"  - çevirmen notu: {_tek_satir(t.cevirmen_notu)}")
    return out


def yaz_dokum(
    no,
    zh,
    en,
    eslesmeler,
    salahiyetler,
    en_adaylar,
    zh_adaylar,
    takma_adlar,
    son_yayim,
    notlar=False,
    siradan=(),
    sozcukler=None,
    kokler=None,
    capa=(),
    koklu=(),
) -> str:
    """Sablon ureticisinin okudugu dokum: yalniz bu bolume ait kararlar."""
    # Yalniz baslikta gecen TEK kelime hic eslestirilmez; dokumde gurultudur
    # (56: "Escape"). Cok kelimeli baslik obegi kalir.
    en_adaylar = [a for a in en_adaylar if not (a.tur == "başlık" and " " not in a.ad)]
    kokler = kokler or {}
    out = [f"# Terim Dökümü — Bölüm {no}", ""]
    kaynak = (
        "Çince + İngilizce"
        if zh and en
        else ("yalnız Çince" if zh else "yalnız İngilizce")
    )
    out.append(
        f"Kaynak: {kaynak}. Bu döküm mekanik bir aramadır: aşağıdaki karşılıkların hepsi "
        f"ZATEN KARARA BAĞLANMIŞTIR, yenisi uydurulmaz. Listede olmayan bir terim için "
        f"önce 'Sözlükte olmayan adaylar' bölümüne bakın."
    )
    if not zh:
        out.append("\n**Çince metin yok: bölüm kaynakla doğrulanmadı.**")

    # ---- 1
    siradan_en = [e for e in eslesmeler if _siradan_ingilizce(e) and not e.cok_anlamli]
    kesin = [
        e
        for e in eslesmeler
        if e.nasil != "en-yedek" and not e.cok_anlamli and not _siradan_ingilizce(e)
    ]
    cok_anlamli = [e for e in eslesmeler if e.nasil != "en-yedek" and e.cok_anlamli]
    tutmayan = [e for e in eslesmeler if e.nasil == "en-yedek"]
    out += ["", "## 1. Yerleşmiş terimler (okuma sırasıyla)", ""]
    if not kesin:
        out.append("_yok_")
    for e in kesin:
        out += _terim_satirlari(e, zh, notlar, no)

    if cok_anlamli:
        out += [
            "",
            "### 1c. Aynı Çince anahtar birden çok kayda bağlı",
            "",
            "Bu anahtar sözlükte birden fazla kaydın karşılığıdır; her geçişte hangisinin "
            "kastedildiği bağlamdan seçilir. Bağlama bakmadan A.1'e alınmaz.",
            "",
        ]
        for e in cok_anlamli:
            out += _terim_satirlari(e, zh, notlar, no)

    out += [
        "",
        "### 1b. Doğrulanmamış: Çince anahtarı tutmayan, İngilizcesi geçen kayıtlar",
        "",
    ]
    out.append(
        "Kayıt yalnız İngilizceden bulundu. Ya kaynak aynı şeyi başka bir sözcükle söylüyor "
        "(anahtar eksik: terim geçerlidir), ya İngilizce başka bir Çince sözcüğü bu adla çevirmiş "
        "(tuzak: terim kullanılmaz). Bağlama ve Çinceye bakmadan A.1'e alınmaz."
    )
    out.append("")
    if not tutmayan:
        out.append("_yok_")
    for e in tutmayan:
        t = e.terim
        out.append(
            f"- **{t.tr}** ← {t.en or '—'}  ·  anahtar: {' / '.join(_zh_parcalari(t))}, "
            f"İngilizcede ×{e.sayi}"
        )
        if e.baglam:
            out.append(f'  - bağlam: "{e.baglam}"')
        if e.yakin:
            out.append(
                f"  - aynı yerde, anahtardan tek harf farklı Çince biçim: {', '.join(e.yakin)} "
                f"(büyük ihtimalle aynı terim; anahtar eksik)"
            )

    if siradan_en:
        out += [
            "",
            "### 1d. Yalnız İngilizceden bulunan sıradan sözcükler",
            "",
            "Çince anahtarı olmayan, İngilizcesi küçük harfli sözcük. Aynı İngilizce sözcük "
            "kaynakta birçok ayrı şeyi karşılayabilir; bağlama ve Çinceye bakmadan A.1'e alınmaz.",
            "",
        ]
        for e in siradan_en:
            t = e.terim
            out.append(f"- **{t.tr}** ← {t.en or '—'}  ·  {t.yer} (words.md), İngilizcede ×{e.sayi}")
            if e.baglam:
                out.append(f'  - bağlam: "{e.baglam}"')

    if capa:
        out += [
            "",
            "### 1e. Bilinen adlar (çapa sözlüğü)",
            "",
            "Kişi ve yer adları: Türkçesi İngilizce adla aynıdır ve A.1'e girer.",
            "",
        ]
        for ad, zh_ad, n, yok in capa:
            satir = f"- **{ad}** ← {zh_ad}  ·  bölümde ×{n}"
            if yok:
                satir += (
                    " (İngilizce bu bölümde bu adla geçmiyor: çeviri adı başka yazmış olabilir; "
                    "Türkçesi yine bu ad)"
                )
            out.append(satir)

    # ---- 2
    out += ["", "## 2. Salahiyetler", ""]
    if not salahiyetler:
        out.append("_salahiyet bağlamında geçen yok_")
    for k, n, _ilk in salahiyetler:
        out.append(f"- **{k['turkce']}**  ·  {k.get('tur', '')}, bölümde ×{n}")
        if k.get("ingilizce_tuzak"):
            out.append(f"  - İngilizce tuzağı: {_tek_satir(k['ingilizce_tuzak'])}")
        if k.get("not"):
            out.append(f"  - not: {_tek_satir(k['not'], 300)}")
    if siradan:
        out.append("")
        out.append(
            "Salahiyet adı olan ama bu bölümde SIRADAN anlamda geçen sözcükler (yanında "
            "权柄/象征/神国 yok); salahiyet karşılığı dayatılmaz: "
            + ", ".join(f"{k['turkce']} ×{n}" for k, n, _i in siradan)
        )

    # ---- 3
    out += ["", "## 3. Sözlükte olmayan adaylar", ""]
    out.append(
        "Hiçbir sözlükte (sozluk.yml, words.md, salahiyetler, çapa adları) bulunmayan adlar. "
        "Karşılık gerektirenler A.2'ye girer. YAYIMLANMIŞ bir bölümde geçmişse karşılık o "
        "bölümdedir; Türkçesi burada yazmıyorsa bakılmadan A.1'e alınmaz."
    )
    out += ["", "### 3a. İngilizcede büyük harfle geçenler", ""]
    if not en_adaylar:
        out.append("_yok_")
    for a in en_adaylar:
        etiket = f" ({a.tur})" if a.tur else ""
        if a.es is not None:
            # Ikisinin de sayisi: Ingilizce sayim cevirmenin tercihine bagli
            # (55'te Birth Day Path Number ×4, Cincesi ×5).
            ad = f"{a.ad} ↔ {a.es.ad} — İngilizcede ×{a.sayi}, Çincede ×{a.es.sayi}{etiket}"
        else:
            ad = f"{a.ad} ×{a.sayi}{etiket}"
        if a.parcalar:
            ad += " (ayrıca tek başına: " + ", ".join(
                f"{p} ×{n}" for p, n in a.parcalar.items()
            ) + ")"
        karar = _ad_karari(a.ad, sozcukler, kokler, a.es)
        satir = f"- {ad} — {_bolum_yeri(a.ilk_bolum, no, son_yayim, karar)}"
        if (
            a.es is not None
            and a.es.ilk_bolum
            and a.ilk_bolum
            and a.es.ilk_bolum < a.ilk_bolum
        ):
            satir += (
                f" (Çince dizi {a.es.ilk_bolum}. bölümde de geçiyor: ya daha uzun bir adın "
                f"parçası, ya İngilizce o bölümde adı başka yazmış)"
            )
        out.append(satir)
    if takma_adlar:
        out += [
            "",
            "Bilinen bir terimin başka İngilizce adı (aday değil; terim 1. bölümde):",
        ]
        for a, e in takma_adlar:
            out.append(f"- {a.ad} ×{a.sayi} → **{e.terim.tr}** ({e.terim.en or '—'})")

    zh_kalan = [z for z in zh_adaylar if z.es is None]
    out += ["", "### 3b. Çincede ad işareti taşıyanlar", ""]
    out.append(
        "Unvandan önceki ad (X先生), noktalı ad (X·Y), tırnaklı kısa ifade, ad verme kalıbı. "
        "İngilizce bir adayla eşleşenler 3a'da gösterildi."
    )
    out.append("")
    if not zh_kalan:
        out.append("_yok_")
    for z in zh_kalan:
        tur = z.tur
        if z.tirnakli is not None and z.tirnakli < z.sayi:
            tur = (
                f"{z.tur} ×{z.tirnakli}, öteki geçişler tırnaksız: tırnak bir vurgu "
                f"olabilir, ad değil"
            )
        out.append(f"- {z.ad} ×{z.sayi} ({tur}) — {_bolum_yeri(z.ilk_bolum, no, son_yayim)}")

    if koklu:
        out += [
            "",
            "### 3c. Bilinen bir adın kökü yeni bir bileşikte",
            "",
            "Sözlükteki bir anahtarın ses parçası, o anahtarın dışında geçiyor. Kök aynı ad ise "
            "yeni ad da aynı kökle kurulur.",
            "",
        ]
        for k in koklu:
            sahip = f"{k.sahip} ({k.sahip_en})" if k.sahip_en else k.sahip
            satir = f"- {k.parca} ×{k.sayi} — kök: {sahip}, anahtar {k.anahtar}"
            if k.en_es:
                satir += f"; İngilizcede aynı yerde: {k.en_es}"
            out.append(satir)
            out.append(f"  - bağlam: {k.baglam}")

    # ---- makbuz
    out += [
        "",
        "## Tarama makbuzu",
        "",
        f"{len(kesin)} yerleşmiş terim "
        f"({sum(1 for e in kesin if e.nasil == 'zh')} Çinceden, "
        f"{sum(1 for e in kesin if e.nasil == 'en')} İngilizceden, "
        f"{sum(1 for e in eslesmeler if e.cikarim)} Çince anahtarı çıkarılarak) + "
        f"{len(cok_anlamli)} çok anlamlı anahtar + {len(tutmayan)} doğrulanmamış, "
        f"{len(salahiyetler)} salahiyet (+{len(siradan)} sıradan anlamda); "
        f"adaylar: {len(en_adaylar)} İngilizce, {len(zh_kalan)} yalnız Çince, "
        f"{len(takma_adlar)} varyant ad terime bağlandı; "
        f"{sum(1 for e in kesin if not e.yayim)} terim yayımlanmış metinde ilk kez geçecek. "
        f"Ayrıca: {len(siradan_en)} sıradan İngilizce sözcük (1d), {len(capa)} bilinen ad (1e), "
        f"{len(koklu)} kök (3c).",
        "",
    ]
    return "\n".join(out)


def yaz_bakim(
    no,
    zh,
    eslesmeler,
    en_adaylar,
    zh_adaylar,
    takma_adlar,
    obekler,
    son_yayim,
    obek_yontemi="",
    obek_tarandi=True,
) -> str:
    """Editorun okudugu bakim raporu: sozluge geri tasinacaklar ve veri eksikleri."""
    out = [
        f"# Bakım Raporu — Bölüm {no}",
        "",
        "Editör içindir; şablon üreticisine verilmez.",
        "",
    ]

    # ---- 1
    out += ["## 1. Yayımlanmış karşılığına bakılacak adlar", ""]
    bakilacak = [
        a
        for a in en_adaylar
        if a.ilk_bolum is not None and a.ilk_bolum < no and a.ilk_bolum <= son_yayim
    ]
    if not bakilacak:
        out.append("_yok_")
    for a in bakilacak:
        out.append(
            f'- {a.ad} — `ceviri_denetle.py "{a.ad}" --bolum '
            f"{a.ilk_bolum}-{min(son_yayim, no - 1)}`"
        )
    zh_yayimli = [
        z
        for z in zh_adaylar
        if z.es is None
        and z.ilk_bolum is not None
        and z.ilk_bolum < no
        and z.ilk_bolum <= son_yayim
    ]
    if zh_yayimli:
        out.append("")
        out.append(
            "Yalnız Çincede bulunanlar (İngilizce eşi yok; Türkçesi o bölümün metnindedir):"
        )
        for z in zh_yayimli:
            out.append(f"- {z.ad} ({z.tur}) — ilk: bölüm {z.ilk_bolum}")

    # ---- 2
    out += ["", "## 2. Daha önce çevrilmiş, sözlüğe girmemiş tekrarlı öbekler", ""]
    out.append(
        "Bu bölümde en az iki kez geçen, romanın bütününde seyrek, yayımlanmış bir bölümde daha önce "
        "geçmiş Çince öbekler. Karşılığı o bölümlerdedir; bulunca words.md'ye geri taşınmalı. "
        "Sezgiseldir: gürültü içerebilir."
    )
    if obek_yontemi == "n-gram":
        out.append(
            "(jieba kurulu değil: ham n-gram taraması, daha gürültülü. `pip install jieba`)"
        )
    out.append("")
    if not obek_tarandi:
        out.append("_taranmadı (--obek-yok)_")
    elif not obekler:
        out.append("_yok_")
    for g, c, yayimda in obekler:
        son3 = ", ".join(str(n) for n in yayimda[-3:])
        out.append(f"- {g} ×{c} — yayımlanmış {len(yayimda)} bölümde (son: {son3})")

    # ---- 3
    cincesiz = [e for e in eslesmeler if e.nasil == "en" and zh]
    tutmayan = [e for e in eslesmeler if e.nasil == "en-yedek"]
    cikarilan = [e for e in eslesmeler if e.cikarim]
    yakinli = [e for e in tutmayan if e.yakin]
    cok = [e for e in eslesmeler if e.cok_anlamli]
    out += ["", "## 3. Veri eksikleri", ""]
    if not (cincesiz or tutmayan or takma_adlar or cikarilan or cok):
        out.append("_yok_")
    if cikarilan:
        out.append(
            "- Çince anahtarı bileşimden çıkarıldı; doğruysa `cince:` alanına yazılmalı: "
            + ", ".join(f"{e.terim.tr} ← {e.cikarim}" for e in cikarilan)
        )
    if yakinli:
        out.append(
            "- Anahtardan tek harf farklı Çince biçim; aynı terimse anahtara eklenmeli: "
            + ", ".join(
                f"{e.terim.tr}: {' / '.join(e.yakin)} (anahtar {' / '.join(_zh_parcalari(e.terim))})"
                for e in yakinli
            )
        )
    if cok:
        anahtarlar = sorted({z for e in cok for z in e.anahtarlar})
        out.append(
            "- Aynı Çince anahtar birden çok kayıtta (dökümde 1c; bilinçliyse dokunulmaz): "
            + ", ".join(anahtarlar)
        )
    if cincesiz:
        out.append(
            "- `cince:` alanı boş, İngilizceden bulundu (sayım İngilizce çevirinin tercihine "
            "bağlı kalır): " + ", ".join(e.terim.tr for e in cincesiz)
        )
    if tutmayan:
        out.append(
            "- Çince anahtarı bu bölümde tutmadı (dökümde 1b): bağlam terimi doğruluyorsa bu "
            "bölümdeki Çince sözcük anahtara eklenmeli: "
            + ", ".join(
                f"{e.terim.tr} ({' / '.join(_zh_parcalari(e.terim))})" for e in tutmayan
            )
        )
    if takma_adlar:
        out.append(
            "- Arama adına eklenebilecek İngilizce varyantlar: "
            + ", ".join(f"{a.ad} → {e.terim.tr}" for a, e in takma_adlar)
        )
    out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------ boru hatti


@dataclass
class Kaynak:
    """
    Bir kez yuklenen her sey: sozlukler, uc korpus, korpus istatistigi, capa.
    Tek bolumde main() bunu bir kez kurar; toplu calismada (hazirla_dogrula.py)
    butun bolumler ayni Kaynak'i paylasir -- korpuslari her bolum icin yeniden
    okumak bolum basina ~10 saniyedir.
    """

    terimler: list
    salahiyetler: list
    zh_hepsi: list
    zh_bolumler: dict
    en_bolumler: dict
    tr_bolumler: list
    sozcukler: object  # Korpus
    capa: dict


def kaynak_yukle() -> Kaynak:
    sozluk = lotm.sozluk_yukle(kelimeler=True)
    salahiyetler = lotm.salahiyetler_yukle()
    zh_hepsi = sorted(
        {z for t in sozluk.terimler for z in _zh_parcalari(t)}
        | {str(k["cince"]) for k in salahiyetler},
        key=len,
        reverse=True,
    )

    def al(f):
        try:
            return lotm.bolum_sozlugu(f())
        except (FileNotFoundError, OSError):
            return {}

    zh_bolumler, en_bolumler = al(lotm.bolumler_zh), al(lotm.bolumler_en)
    try:
        tr_bolumler = lotm.bolumler_tr()
    except FileNotFoundError:
        tr_bolumler = []
    sozcukler = (
        kucuk_sozcukler(b.metin for b in en_bolumler.values()) if en_bolumler else frozenset()
    )
    try:
        capa = _capa.sozluk_yukle() or {}
    except Exception:  # capa okunamazsa 1e ve 3c'nin capa kismi bos kalir
        capa = {}
    return Kaynak(
        sozluk.terimler, salahiyetler, zh_hepsi, zh_bolumler, en_bolumler, tr_bolumler,
        sozcukler, capa,
    )


@dataclass
class Hazirlik:
    """Bir bolumun dokumu ve bakim raporu icin gereken her sey."""

    no: int
    zh: str | None
    en: str | None
    terimler: list
    eslesmeler: list
    salahiyet_bulunan: list
    salahiyet_siradan: list
    zh_adaylar: list
    en_adaylar: list
    takma_adlar: list
    sozcukler: object
    son_yayim: int
    capa_listesi: list
    koklu: list
    kokler: dict
    obekler: list
    obek_yontemi: str
    obek_tarandi: bool


def hazirla_bolum(
    no: int,
    kay: Kaynak,
    en_az: int = 1,
    obek: bool = False,
    obek_orani: float = 0.03,
    obek_sinir: int = 15,
):
    """Bir bolumu hazirlar; bolum ne Cincede ne Ingilizcede yoksa None."""
    zh_b, en_b = kay.zh_bolumler.get(no), kay.en_bolumler.get(no)
    zh = zh_b.metin if zh_b else None
    en = en_b.metin if en_b else None
    en_baslik = (getattr(en_b, "baslik", None) or getattr(en_b, "title", None)) if en_b else None
    if not zh and not en:
        return None

    salahiyetler, zh_hepsi = kay.salahiyetler, kay.zh_hepsi
    terimler = kay.terimler
    eslesmeler = terimleri_bul(zh, en, terimler, zh_hepsi, no)
    salahiyet_bulunan, salahiyet_siradan = salahiyetleri_bul(zh, salahiyetler, zh_hepsi)

    # Cince adaylar Ingilizcelerden ONCE kurulur: bir adayin bilinen bir
    # terimin Cince anahtari oldugu anlasilirsa (anahtar_cikar) eslesme
    # yeniden kurulur ve yayim, takma ad, eslestirme hepsi o eslesmeyle yapilir.
    zh_adaylar, zh_bilinen = [], (set(), set())
    if zh:
        zh_bilinen = zh_bilinenler(zh_hepsi)
        zh_adaylar = zh_adaylari(zh, zh_bilinen)
        for z in zh_adaylar:
            z.ilk_bolum = ilk_cince_bolum(z.ad, kay.zh_bolumler, no)
        # Tirnakli ifade yalniz bu bolumde DOGUYORSA aday: daha once gecmis
        # tirnakli sozcuk (生意, 17'den beri) bir vurgu tirnagidir, ad degil.
        # Ayni kural unvandan onceki ANLAMLI diziye de: 棕发 (kahverengi
        # sacli) ve 漂亮 (guzel) 48'de "hanım"in nitelemesiydi, ad degil.
        zh_adaylar = [
            z
            for z in zh_adaylar
            if not (
                (z.tur == "tırnaklı" or (z.tur == "unvan" and not _sesle_mi(z.ad)))
                and z.ilk_bolum is not None
                and z.ilk_bolum < no
            )
        ]
        cikarim = anahtar_cikar(zh_adaylar, eslesmeler, terimler, zh, en)
        if cikarim:
            terimler, zh_hepsi, eslesmeler = cikarimla_yeniden(
                zh, en, terimler, zh_hepsi, cikarim, no
            )
            cikan = {k for _t, k in cikarim.values()}
            zh_adaylar = [z for z in zh_adaylar if z.ad not in cikan]

    tr_bolumler = kay.tr_bolumler
    yayim_nolari = {b.no for b in tr_bolumler if b.no is not None}
    son_yayim = max(yayim_nolari, default=0)
    yayim_kullanimi(eslesmeler, tr_bolumler, no, harf_kardesleri(terimler))
    for e in eslesmeler:
        if e.nasil == "en-yedek":
            e.yakin = yakin_anahtarlar(e, zh, en)

    en_adaylar, takma_adlar, sozcukler = [], [], frozenset()
    if en:
        sozcukler = kay.sozcukler
        bilinen = bilinen_adlar(terimler, salahiyetler)
        en_bulunan = set(en_isabetleri(en, terimler))
        adaylar = aday_adlar(en, bilinen, en_az, _baslik_sonu(en, en_baslik), sozcukler)
        for aday, es in takma_adlari_coz(
            adaylar, en, zh, eslesmeler, sozcukler, en_bulunan
        ):
            if es is not None:
                takma_adlar.append((aday, es))
                for p in parcalari_ac(aday, en):
                    p.ilk_bolum = ilk_ingilizce_bolum(p.ad, kay.en_bolumler, no)
                    en_adaylar.append(p)
                continue
            aday.ilk_bolum = ilk_ingilizce_bolum(aday.ad, kay.en_bolumler, no)
            en_adaylar.append(aday)
        if takma_adlar:
            eslesmeler = ic_isabetleri_at(eslesmeler, takma_adlar)

    obekler, obek_yontemi = [], ""
    if zh:
        adaylari_esle(en_adaylar, zh_adaylar, len(en or ""), len(zh), sozcukler)
        if obek:
            bilinen_tam, bilinen_parca = zh_bilinen
            obekler, obek_yontemi = tekrarli_obekler(
                zh,
                kay.zh_bolumler,
                no,
                yayim_nolari,
                maske=bilinen_tam
                | bilinen_parca
                | {z.ad for z in zh_adaylar}
                | {p for z in zh_adaylar for p in z.ad.split("·")},
                df_orani=obek_orani,
                sinir=obek_sinir,
            )

    capa_listesi = capa_adlari(zh, en, kay.capa, eslesmeler, sozcukler)
    sahipler: dict = {}
    for t in terimler:
        if t.tr:
            for z in _zh_parcalari(t):
                sahipler.setdefault(z, (t.tr, t.en))
    for z, v in kay.capa.items():
        if _CJK_DIZI.search(str(z)):
            sahipler.setdefault(str(z), (str(v), str(v)))
    koklu = kok_isabetleri(zh, sahipler, en_adaylar, len(en or ""))

    return Hazirlik(
        no, zh, en, terimler, eslesmeler, salahiyet_bulunan, salahiyet_siradan,
        zh_adaylar, en_adaylar, takma_adlar, sozcukler, son_yayim, capa_listesi, koklu,
        cevrilmis_kokler(terimler, sozcukler), obekler, obek_yontemi,
        bool(zh) and obek,
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("bolum", type=int)
    ap.add_argument(
        "--cikti", type=Path, default=None, help="Markdown dosyasi (varsayilan: ekran)"
    )
    ap.add_argument("--notlar", action="store_true", help="cevirmen notlarini da ekle")
    ap.add_argument(
        "--en-az",
        type=int,
        default=1,
        help="tek kelimelik Ingilizce adayin en az gecis sayisi (varsayilan 1)",
    )
    ap.add_argument(
        "--bakim",
        nargs="?",
        const="-",
        default=None,
        metavar="DOSYA",
        help="editor icin bakim raporu; dosya verilmezse stderr'e (dokume karismaz)",
    )
    ap.add_argument(
        "--obek-yok", action="store_true", help="bakim: obek taramasini atla"
    )
    ap.add_argument(
        "--obek-orani",
        type=float,
        default=0.03,
        help="bakim: obegin gecebilecegi bolum orani ust siniri, butun romana gore (varsayilan 0.03)",
    )
    ap.add_argument(
        "--obek-sinir", type=int, default=15, help="bakim: en cok kac obek satiri"
    )
    a = ap.parse_args()

    kay = kaynak_yukle()
    h = hazirla_bolum(
        a.bolum, kay, a.en_az, bool(a.bakim) and not a.obek_yok, a.obek_orani, a.obek_sinir
    )
    if h is None:
        sys.exit(f"HATA: {a.bolum}. bölüm ne Çince ne İngilizce kaynakta bulundu")

    metin = yaz_dokum(
        h.no,
        h.zh,
        h.en,
        h.eslesmeler,
        h.salahiyet_bulunan,
        h.en_adaylar,
        h.zh_adaylar,
        h.takma_adlar,
        h.son_yayim,
        a.notlar,
        siradan=h.salahiyet_siradan,
        sozcukler=h.sozcukler,
        kokler=h.kokler,
        capa=h.capa_listesi,
        koklu=h.koklu,
    )
    if a.cikti:
        lotm.atomik_yaz(a.cikti, metin)
        print(f"yazıldı: {a.cikti}", file=sys.stderr)
    else:
        print(metin)

    if a.bakim:
        rapor = yaz_bakim(
            h.no,
            h.zh,
            h.eslesmeler,
            h.en_adaylar,
            h.zh_adaylar,
            h.takma_adlar,
            h.obekler,
            h.son_yayim,
            obek_yontemi=h.obek_yontemi,
            obek_tarandi=bool(h.zh) and not a.obek_yok,
        )
        if a.bakim == "-":
            print("\n" + rapor, file=sys.stderr)
        else:
            lotm.atomik_yaz(Path(a.bakim), rapor)
            print(f"yazıldı: {a.bakim}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
