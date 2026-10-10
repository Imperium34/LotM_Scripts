#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yayim_denetle.py -- Turkce bolumleri sozluge karsi denetler (ayarlanmis surum).

UST DUZEY SORU: "YAYIMLANMIS TR metin, sozluk kurallarina gore GUVENLI mi?"
(artik sablon isareti / eskimis karsilik / cevrilmemis Ingilizce sizintisi /
kapi -- yani spoiler -- ihlali)

Dort "denetim/arama" betigi var ve dorderi de farkli seye bakiyor --
karistirilmasinlar:
    sozluk_ara.py       sozluk.yml'e bakar               -- ne karar verdim?
    kapi_denetle.py      KAYNAK (EN) metne bakar          -- nerede ilk geciyor?
    ceviri_denetle.py    YAYIMLANMIS metne bakar (hizali) -- ne yayimladim, tutarli mi?
    yayim_denetle.py     YAYIMLANMIS (TR) metne bakar     -- yayimlanan GUVENLI mi?

kapi_denetle.py kapiyi (bolum_siniri) KAYNAK metinden TURETIR. Bu betik o
kapiya YAYIMLANMIS metnin UYUP UYMADIGINI denetler -- ikisi ters yonler.

v1'de 146 bulgu vardi, bunlarin ~5'i gercekti. Sebep: Turkce karsiliklar
gunluk Turkce kelimelerden secilmis (Haz, Yol, Ay, Sanli, Avci...) ve duz
eslesme "Mertebe adi" ile "siradan kelime" ayrimini yapamiyor.

Duzeltmeler:
  1. HARF DUYARLI. Mertebe adlari ozel isim, cakismalar kucuk harfli:
     Yol/yolu, Haz/hazine, Maraz/marazi, San/sansli, Askin/"yili askin".
  2. GERCEK TURKCE EKLERI. v1 "\\w{0,12}" kabul ediyordu; bu yuzden
     Haz -> Haziran, Bard -> bardak esleiyordu. Artik yalnizca gercek
     isim cekim ekleri kabul ediliyor. (Desen artik lotm.desen_kur'da.)
  3. IPUCU SARTI. Tek kelimelik terimler ancak yakininda Mertebe / Yol /
     iksir / formul gibi bir isaret ya da ayni yoldan cok kelimeli bir
     kardes ad varsa "yuksek" sayilir.
  4. OZEL ISIMLER SIZINTI TARAMASINDAN CIKARILDI. "Audrey Hall" bir terim
     degil, kisi adi; Turkcede de oyle kalmali.

COZULEMEYEN: es adli gonderge. "Kara Imparator" 5. bolumde Solomon
Imparatorlugu'nun hukumdari anlamina gelir, Mertebe 0 anlamina degil.
Metin ayni, gonderge farkli. Bu ayrimi regex yapamaz; arac adaylari
daraltir, karari insan verir. Rapor bu yuzden "hata" degil "aday" der.

Sozluk yukleme, bolum okuma ve Turkce ek deseni artik lotm.py'de.

Kullanim:
    python3 yayim_denetle.py --sozluk sozluk.yml --bolumler ./_chapters
    python3 yayim_denetle.py --sozluk sozluk.yml --bolumler ./_chapters --hepsi

Cikis kodu 1: artik isaret, eskimis karsilik (lint kapsami disinda) ya da
Ingilizce sizinti varsa. Kapi adaylari cikis kodunu etkilemez.

Basliklar ("Bölüm N: " oneki atilarak) govdeyle ayni denetimlerden gecer ve
"0050.md:başlık" olarak raporlanir (sozluk_lint ile ayni adlandirma).
"""

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import lotm
from turkce import tr_desen, tr_kucult

# Tek kelimelik terimleri "yuksek guven" yapan yakin isaretler.
#
# "Yol" AYRI: [una] BIR KARAKTERLIK sinif demektir ("u" VEYA "n" VEYA "a"),
# "u"/"un"/"una" ALTERNATIFI DEGIL -- yazim hatasi. .search() tam kelime
# sinirina bakmadigi icin bu yanlislik "Yolu"/"Yolun"/"Yoluna"/"Yola"da
# tesadufen calisiyordu (hepsi "Yol" + tek bir u/n/a harfiyle basliyor),
# ama "Yolda"/"Yoldan" gibi COK YAYGIN durum ekleri hic yakalanmiyordu --
# yani bu iki durumda gecen tek-kelimelik "Yol" ailesi terimleri, aslinda
# guclu bir baglam ipucu varken sessizce DUSUK guvene dusuyordu. Duzeltme:
# ayni amacla zaten var olan lotm.desen_kur kullanilir (tum durum eklerini
# doğru kapsar), ozel-durum bir karakter sinifi degil.
# Harf duyarsiz, ama re.IGNORECASE ile degil: IGNORECASE ı ile i'yi ayni
# harf sayar ("Aşkın" deseni "aşkin"i, "Sıra" deseni "sira"yi bulurdu).
IPUCU_RE = re.compile(
    "|".join(
        [r"\b" + tr_desen(k) for k in ("Mertebe", "iksir", "formül", "Aşkın")]
        + [r"\b" + tr_desen("Sıra") + r"\b"]
        + [r"\b(?i:potion)"]  # Ingilizce sozcuk: burada IGNORECASE dogru
    )
)
_YOL_IPUCU = lotm.desen_kur("Yol", harf_duyarli=False)


def _ipucu_var_mi(pencere: str) -> bool:
    return bool(IPUCU_RE.search(pencere) or _YOL_IPUCU.search(pencere))


# Cumle basi: noktalama ya da acilis isaretinden SONRA bosluk OLABILIR de
# OLMAYABILIR de. Eski desen bosluk sart kosuyordu; tirnak kelimeye bitisik
# yazildigi icin ('konuştu. "Kusura bakmayın') replik baslari cumle basi
# sayilmiyordu. Paragraf basi (satir sonu), italik (_) ve tek tirnak da
# acilis sayilir.
CUMLE_BASI = re.compile(
    r"(?:^|[.!?:;\u2026\"\u201c\u201d\u2018\u2019'\u00ab\u00bb\u2014\-_(\n])\s*$"
)

# Sistem istemi ve bolum acilis sablonu, duzeltme sirasinda elle silinmesi
# gereken isaretler uretir. Onda dokuzu yakalanir; yakalanmayan biri canli
# sayfada gorunur. Ucuz kontrol, pahali hata.
ARTIK_ISARETLER = [
    (re.compile(r"\[BELİRSİZ\]"), "çeviri belirsizlik etiketi (§7)"),
    (re.compile(r"\[ÖNERİ[:\]]"), "isteğe bağlı detay önerisi (§8)"),
    (re.compile(r"\[DURUM NOTU\]"), "durum notu bloğu (§9)"),
    (re.compile(r"Biten kayıt\s*:"), "durum notu alanı"),
    (re.compile(r"Son duygusal vurgu\s*:"), "durum notu alanı"),
    (re.compile(r"\[END OF OUTPUT\]"), "şablon sonu işareti"),
    (re.compile(r"Bölüm Açılış Şablonu"), "açılış şablonu başlığı"),
    (re.compile(r"##\s*[ABC]\.\s*(AKTİF|BÖLÜME)"), "açılış şablonu bölüm başlığı"),
    (
        re.compile(r"\[(Term|Translation|Karakter Adı)\s*\d*\]"),
        "doldurulmamış şablon alanı",
    ),
    (
        re.compile(r"\[Extract/adapt|\[Determine from|\[Tek paragraf"),
        "şablon yönergesi",
    ),
    (re.compile(r"^\s*\|\s*İngilizce\s*\|", re.M), "aktif terimler tablosu"),
]

# Kisi adi kalibi: iki bas harfi buyuk kelime, aralarinda baglac yok
KISI_ADI = re.compile(r"^[A-ZÇĞİÖŞÜ][\w'-]+ [A-ZÇĞİÖŞÜ][\w'-]+$")

# Bu esikteki bolum_siniri degerleri gercek bir kapi bildirmez; ya "seri
# bitmeden acilmaz" (Mertebe 0 adlari) ya da "bolum henuz tespit edilmedi"
# demektir. Ikisi de kapi denetimine girmemeli: bu adlarin cogu gunluk
# Turkce kelime (Ana, Ay, Kapi, Olum, Karanlik) ve her bolumde yanlis
# pozitif uretirler. Deger lotm.py'den gelir; eskiden burada 1409 sabiti
# vardi ve iki dosya birbirinden kayabiliyordu.
SON_BOLUM = lotm.SON_BOLUM

YUKSEK, DUSUK = "yuksek", "dusuk"


def gecis_bolumu(terim) -> int | None:
    """
    Eski karsiliklarin GECIS bolumu: terimin bolum_siniri.

    Mantik kapi denetiminin aynasi. Kapidan once yeni ad henuz acilmamistir;
    o bolgede eski bicim (Ayin icin "ritüel") o donemin dogru kelimesidir.
    Kapidan itibaren eski bicim eskimistir. Yeni adin kapidan once gecmesi
    ise zaten kapi adayi olarak raporlanir -- ters yon icin ayri bir denetim
    gerekmez.

    Gercek bir kapi bildirmeyen degerler (yok, 0, >= SON_BOLUM) gecis
    sayilmaz: o terimin eski bicimi HER bolumde eskimistir. Aksi hâlde
    "seri bitmeden acilmaz" isaretli bir terimin eski bicimi hic
    raporlanmazdi.

    Eskiden bu bilgi lint-kurallari.yml'de 'ogrenme_bolumu' olarak
    duruyordu; ayni karar iki dosyada iki farkli
    sayiyla tutulabiliyordu. Artik tek kaynak sozluk.yml.
    """
    esik = getattr(terim, "bolum_siniri", None) or 0
    return esik if 0 < esik < SON_BOLUM else None


@dataclass
class Kayit:
    """Bir lotm.Terim + denetim icin derlenmis desenler."""

    terim: lotm.Terim
    desen: object = None
    en_desen: object = None
    eski_desen: list = field(default_factory=list)
    # Ters yon icin: eski bicimi OLAN terimlerde yeni bicimin harf duyarsiz
    # deseni. Kapi taramasi harf duyarlidir (gunluk kelime gurultusu
    # yuzunden, bkz. guven_ver); "ayinlerinde" gibi kucuk harfli bir erken
    # kullanim orada hic gorunmez. Bkz. denetle(), ters yon.
    yeni_duyarsiz: object = None
    # Basliklar icin: eski bicimlerin harf duyarsiz desenleri. Baslik Title
    # Case yazildigi icin kucuk harfli bir eski bicim ("ritüel") baslikta
    # "Ritüeli" olarak gecer ve harf duyarli desen onu hic gormez.
    eski_desen_duyarsiz: list = field(default_factory=list)
    kardesler: list = field(default_factory=list)

    # denetle()/rapor() bu adlarla okur
    @property
    def tr(self):
        return self.terim.tr

    @property
    def en(self):
        return self.terim.en

    @property
    def kapi(self):
        return self.terim.bolum_siniri

    @property
    def ilk_gecis(self):
        return self.terim.ilk_gecis

    @property
    def gecis(self):
        return gecis_bolumu(self.terim)

    @property
    def yer(self):
        return self.terim.yer

    @property
    def tek_kelime(self):
        return self.terim.tek_kelime


def kayitlari_kur(sozluk) -> list:
    """lotm.Terim kayitlarini denetim kayitlarina cevirir."""
    kayitlar = []
    for t in sozluk.terimler:
        if not t.tr:
            continue
        en = t.en
        kisi = bool(en and KISI_ADI.match(en))
        kayitlar.append(
            Kayit(
                terim=t,
                desen=lotm.desen_kur(t.tr),
                # sizinti taramasi: ozel isimler ve Tarot kartlari haric
                en_desen=(
                    re.compile(r"(?<![\w])" + re.escape(en) + r"(?![\w])")
                    if en and len(en) >= 5 and not kisi and t.kategori != "Tarot Kulübü"
                    else None
                ),
                eski_desen=[(e, lotm.desen_kur(e)) for e in t.eski_karsiliklar],
                yeni_duyarsiz=(
                    lotm.desen_kur(t.tr, harf_duyarli=False)
                    if t.eski_karsiliklar
                    else None
                ),
                eski_desen_duyarsiz=[
                    (e, lotm.desen_kur(e, harf_duyarli=False))
                    for e in t.eski_karsiliklar
                ],
                # tek kelimelik kardes ad ipucu sayilmaz: "Avci" yakininda
                # "Avci" gormek hicbir sey soylemez.
                kardesler=[k for k in t.kardesler_tr if len(k.split()) > 1],
            )
        )
    return kayitlar


def guven_ver(kayit, metin, konum, cumle_ici_yuksek=False):
    """
    Tek kelimelik terimler yakin isaret istemeden yuksek sayilmaz.

    CUMLE_BASI hakkinda: bu dal eskiden iki kolunda da DUSUK donuyordu,
    yani olcum yapiliyor ama sonuca yansimiyordu. Davranis korunuyor
    (varsayilan kapali), cunku 146 -> 5 bastirma turu tam da bu yolla
    yapilmis olabilir.

    --cumle-ici-yuksek ile acilir. Gerekcesi: cumle ORTASINDA buyuk
    harfle gecen tek kelimelik bir terim ("... bir Haz getirirdi")
    neredeyse kesin Mertebe adidir; cumle BASINDAKI buyuk harf ise
    ayirt edici degildir, "Hazine" gibi siradan kelimeler de oyle
    baslar. Acmadan once --hepsi ile ne kadar bulgu ekledigine bakin.
    """
    if not kayit.tek_kelime:
        return YUKSEK
    bas, son = max(0, konum - 200), min(len(metin), konum + 200)
    pencere = metin[bas:son]
    if _ipucu_var_mi(pencere):
        return YUKSEK
    for kardes in kayit.kardesler:
        if kardes in pencere:
            return YUKSEK
    onceki = metin[max(0, konum - 40) : konum]
    cumle_basinda = bool(CUMLE_BASI.search(onceki)) or konum == 0
    if cumle_ici_yuksek and not cumle_basinda:
        return YUKSEK
    return DUSUK


def baglam(metin, a, b, g=75):
    return re.sub(r"\s+", " ", metin[max(0, a - g) : min(len(metin), b + g)]).strip()


BASLIK_EK = ":başlık"
_BASLIK_ONEKI = re.compile(r"^Bölüm\s+\d+\s*:\s*")


def baslik_mi(birim) -> bool:
    return birim.kaynak.endswith(BASLIK_EK)


def birimler_kur(bolumler) -> list:
    """
    Her bolumun govdesi ve -- varsa -- hemen ardindan basligi.

    lotm.bolumler_tr basligi front matter'dan zaten ayristiriyor (b.baslik)
    ama 'metin' yalnizca govdedir; bu betigin butun denetimleri 'metin'e
    baktigi icin basliklar hic taranmiyordu. Baslik ayri bir birim olarak
    eklenir: govdedeki konumlar ve baglam alintilari degismez.

    "Bölüm N: " oneki atilir (sozluk_lint.baslik_adi ile ayni kural);
    yoksa "Bölüm" her baslikta ayni ilgisiz adayi uretebilirdi.
    """
    out = []
    for b in bolumler:
        out.append(b)
        if getattr(b, "baslik", None):
            out.append(
                SimpleNamespace(
                    no=b.no,
                    kaynak=b.kaynak + BASLIK_EK,
                    baslik=None,
                    metin=_BASLIK_ONEKI.sub("", b.baslik, count=1),
                )
            )
    return out


def satir_kaymalari(klasor, bolumler) -> dict:
    """
    {dosya: front matter satir sayisi}. 'metin' front matter'dan sonra
    basladigi icin govdeye gore sayilan satir numaralari editordekinden
    o kadar geride kaliyordu (sozluk_lint'te de ayni duzeltme yapildi).
    """
    out = {}
    for b in bolumler:
        try:
            ham = (Path(klasor) / b.kaynak).read_text(encoding="utf-8")
        except OSError:
            continue
        if ham.endswith(b.metin):
            out[b.kaynak] = ham[: len(ham) - len(b.metin)].count("\n")
    return out


def artik_tara(bolumler, kaymalar=None):
    """Yayimlanmis bolumlerde kalmis istem/sablon isaretleri."""
    kaymalar = kaymalar or {}
    bulgular = []
    for b in bolumler:
        kayma = kaymalar.get(b.kaynak, 0)
        for satir_no, satir in enumerate(b.metin.split("\n"), 1 + kayma):
            for desen, aciklama in ARTIK_ISARETLER:
                m = desen.search(satir)
                if m:
                    bulgular.append(
                        (
                            b.kaynak,
                            satir_no,
                            aciklama,
                            re.sub(r"\s+", " ", satir).strip()[:160],
                        )
                    )
                    break
    return bulgular


def siradan_kelime_desenleri(kayitlar, bolumler) -> dict:
    """
    Tek kelimelik terimlerden KUCUK HARFLE de gecenler: {terim: True}.

    "kadın", "ölüm", "kusur" metinde siradan kelime olarak yasiyorsa, cumle
    basinda buyuk harfle gecen "Kadın", "Ölümünün", "Kusura" terimin kendisi
    DEGILDIR -- buyuk harfi konumdan gelir. Kucuk harfli desen harf duyarli
    kurulur, yani yalnizca kucuk harfli gecisler sayilir.

    Ayni sorun BUYUK HARFLI tek kelimelik eski bicimlerde de var: "Şanslı"
    eski Mertebe adiysa, cumle basindaki "Şanslı adam" yine de siradan
    sifattir. Bu yuzden onlar da ayni sozluge girer (anahtar kelimenin
    kendisi; terim ile eski bicim ayni yazimdaysa cevap da aynidir).
    """
    metin = "\n".join(b.metin for b in bolumler)
    adaylar = {k.tr for k in kayitlar if k.tek_kelime and k.tr[:1].isupper()}
    adaylar |= {e for k in kayitlar for e, _ in k.eski_desen if buyuk_tek_kelime(e)}
    return {
        w: bool(lotm.desen_kur(tr_kucult(w), harf_duyarli=True).search(metin))
        for w in adaylar
    }


def buyuk_tek_kelime(w: str) -> bool:
    """
    Siradan-kelime kuralinin uygulanabilecegi eski bicim: tek kelime VE
    buyuk harfle baslar. Kucuk harfli eski bicimlerde ("ritüel") belirsizlik
    yoktur -- buyuk harfli gecisi (cumle basi, baslik) yine o kelimedir ve
    bulgu olarak kalmalidir.
    """
    return " " not in w.strip() and w[:1].isupper()


def siradan_mi(k, metin, aday, siradan: dict, baslik: bool = False) -> bool:
    return siradan_konum(k.tr, metin, aday, siradan, baslik)


def siradan_konum(kelime, metin, aday, siradan: dict, baslik: bool = False) -> bool:
    """
    Bu gecis terimin kendisi mi, cumle basinda buyuk harf almis siradan
    bir kelime mi? Siradan sayilmasi icin UCU birden:
      - tek kelimelik terim, metinde kucuk harfle de geciyor (siradan dict)
      - gecis cumle basinda (CUMLE_BASI)
      - terimin hemen ardinda kesme yok: "Ölüm'e" ozel ad isaretidir
    """
    if not siradan.get(kelime):
        return False
    son = aday.start() + len(kelime)
    if son < len(metin) and metin[son] in "'\u2019":
        return False
    # Basliklarda her kelime buyuk harfle baslar ("İhtiyar Neil'ın Borç
    # Ödeme Çaresi"); buyuk harf orada konumdan da gelmez, bicimden gelir.
    # Yani baslikta cumle basi sarti aranmaz: kucuk harfle de gecen tek
    # kelimelik terim, kesme almamissa, baslikta siradan kelime sayilir.
    if baslik:
        return True
    onceki = metin[max(0, aday.start() - 40) : aday.start()]
    return aday.start() == 0 or bool(CUMLE_BASI.search(onceki))


def denetle(kayitlar, bolumler, cumle_ici_yuksek=False, maske=()):
    """
    maske: cok kelimeli words.md adlarinin desenleri. Glossary'nin kendi
    "uzun ad once" kurali gibi, bunlarin icindeki kisa terimler sayilmaz:
    "Savaşçı ve Deniz Tavernası"ndaki "Savaşçı" bir Mertebe adi degildir.
    """
    sizinti, eskimis, kapi, sadik, erken_yeni = [], [], [], [], []
    envanter = defaultdict(list)
    siradan = siradan_kelime_desenleri(kayitlar, bolumler)
    atlanan = defaultdict(int)
    atlanan_eski = defaultdict(int)

    # En uzun terim once denenir ve kapsadigi aralik isaretlenir. Boylece
    # "Gizem Avcısı" araligi tuketir ve "Avcı" o konumu goremez. Ayni sorun
    # Ana/Toprak Ana, Güneş/Ebedi Yanan Güneş, Ölüm/Ölüm Sefiri, Ay/Kadim Ay
    # ciftlerinde de var: kisa ad uzun adin icinde sayiliyordu.
    uzun_once = sorted(kayitlar, key=lambda k: -len(k.tr))

    for b in bolumler:
        no, metin, dosya = b.no, b.metin, b.kaynak
        baslikta = baslik_mi(b)
        kapali = []  # (bas, son) -- uzun bir terimin tuketip birakmadigi araliklar
        for d in maske:
            kapali.extend((x.start(), x.end()) for x in d.finditer(metin))

        for k in uzun_once:
            # TERS YON: yeni bicim gecisten ONCE (Ayin, 22'den once). Eskiden
            # lint'in ogrenme_bolumu kurallarindaki uyariydi; gecisler artik
            # yalnizca sozluk.yml'de, bu uyari da yalnizca burada.
            #   - Harf duyarsiz: kucuk harfli kullanim da sayilir.
            #   - Bu noktada 'kapali' YALNIZCA daha uzun terimleri (ve
            #     words.md maskesini) icerir; terimin kendi gecisleri henuz
            #     eklenmedi. "Ayin İlmi" icindeki "Ayin" boylece sayilmaz.
            #   - Ayni bolumde kapi taramasi bu terim icin zaten bir aday
            #     uretirse tekrar listelenmez (asagida, erken_aday).
            erken_aday = None
            if (
                k.yeni_duyarsiz is not None
                and k.gecis is not None
                and no is not None
                and no < k.gecis
            ):
                for x in k.yeni_duyarsiz.finditer(metin):
                    if not any(
                        x.start() < son and x.end() > bas for bas, son in kapali
                    ):
                        erken_aday = x
                        break

            m = None  # ilk gecis: envanter icin (her eslesme sayilir)
            mk = None  # ilk KAPI gecisi: cumle basindaki siradan kelime degil
            # Uzun terimin TUM gecisleri isaretlenmeli. Yalnizca ilki
            # isaretlenirse "Gizem Avcısı" ikinci kez gectiginde o konum
            # bos kalir ve "Avcı" oraya yerlesir.
            for aday in k.desen.finditer(metin):
                if any(aday.start() < son and aday.end() > bas for bas, son in kapali):
                    continue
                kapali.append((aday.start(), aday.end()))
                if m is None:
                    m = aday
                # Envanter her gecisi sayar ("İksiri içti" de terimin
                # kullanimidir); cumle basi eleme YALNIZCA kapi adayligini
                # etkiler. Ilk surum ikisini birden eliyordu ve İksir, Kapı,
                # Ay envanterden tamamen dusmustu.
                if mk is None:
                    if siradan_mi(k, metin, aday, siradan, baslik=baslikta):
                        atlanan[k.tr] += 1
                    else:
                        mk = aday
            if m:
                envanter[k.tr].append(no)
            if mk:
                g = guven_ver(k, metin, mk.start(), cumle_ici_yuksek)
                esik = k.kapi or 0
                if no and 0 < esik < SON_BOLUM and no < esik:
                    ctx = baglam(metin, mk.start(), mk.end())
                    # Kapi ile ilk gecis arasindaki aralik: ad Ingilizce
                    # metinde GECIYOR ama henuz ACIKLANMAMIS. Orada Turkce
                    # metnin adi kullanmasi kaynaga SADAKATTIR, spoiler
                    # degil. Bu ayrim olmadan boyle terimler (kapisi
                    # aciklama bolumune elle konmus olanlar) her
                    # calistirmada sonsuza dek aday olarak cikiyordu.
                    if k.ilk_gecis and no >= k.ilk_gecis:
                        sadik.append((no, dosya, k, ctx))
                    else:
                        kapi.append((g, no, dosya, k, ctx))
                    erken_aday = None  # kapi listesinde zaten gorunuyor
            if erken_aday is not None:
                erken_yeni.append(
                    (
                        no,
                        dosya,
                        k,
                        erken_aday.group(),
                        baglam(metin, erken_aday.start(), erken_aday.end()),
                    )
                )

        for k in kayitlar:
            if k.en_desen:
                me = k.en_desen.search(metin)
                if me:
                    sizinti.append((no, dosya, k, baglam(metin, me.start(), me.end())))

            for eski_ad, desen in k.eski_desen_duyarsiz if baslikta else k.eski_desen:
                # Buyuk harfli tek kelimelik eski bicimde, cumle basinda ya da
                # baslikta siradan kelime olarak gecenler atlanir; ilk gercek
                # gecis aranir (kapi taramasindaki siradan_mi ile ayni kural).
                mo = None
                for x in desen.finditer(metin):
                    if buyuk_tek_kelime(eski_ad) and siradan_konum(
                        eski_ad, metin, x, siradan, baslik=baslikta
                    ):
                        atlanan_eski[eski_ad] += 1
                        continue
                    mo = x
                    break
                if mo:
                    eskimis.append(
                        (no, dosya, k, eski_ad, baglam(metin, mo.start(), mo.end()))
                    )

    if atlanan_eski:
        ornek = ", ".join(
            f"{t} ×{n}"
            for t, n in sorted(atlanan_eski.items(), key=lambda x: -x[1])[:6]
        )
        print(
            f"  eski bicim: {sum(atlanan_eski.values())} gecis siradan kelime sayildi -- "
            f"cumle basinda ya da baslikta, metinde kucuk harfle de geciyor ({ornek})",
            file=sys.stderr,
        )
    if atlanan:
        ornek = ", ".join(
            f"{t} ×{n}" for t, n in sorted(atlanan.items(), key=lambda x: -x[1])[:6]
        )
        print(
            f"  kapi: {sum(atlanan.values())} gecis kapi adayligindan cikti -- cumle "
            f"basinda, metinde kucuk harfle de geciyor ({ornek}); envanter etkilenmez",
            file=sys.stderr,
        )
    return sizinti, eskimis, kapi, sadik, envanter, erken_yeni


def kelime_maskesi(sozluk) -> list:
    """
    words.md'deki cok kelimeli adlar, glossary'de AYNI ad yoksa. Aynisi
    varsa maske glossary teriminin kendisini gizlerdi.
    """
    sozluk_adlari = {tr_kucult(t.tr) for t in sozluk.terimler if t.tr}
    return [
        lotm.desen_kur(t.tr)
        for t in lotm.kelimeler_yukle()
        if t.tr and len(t.tr.split()) > 1 and tr_kucult(t.tr) not in sozluk_adlari
    ]


# Eski yerel ad; turkce.tr_kucult ile ayni.
_tr_kucult = tr_kucult


def lint_kapsami(yol) -> set:
    """
    lint-kurallari.yml'nin ZATEN bildigi eskimis bicimler.

    NEDEN: ayni karar iki yerde duruyor. sozluk.yml bir terimin terk
    edilmis yazimlarini tutar (ceviri_denetle KULLANILAN KARSILIKLAR icin
    buna muhtac -- silmek 'Olaganustu hala 2. bolumde' bulgusunu
    oldurur). lint-kurallari.yml ayni yazimlari kendi kurallariyla tutar:
    istisna regexleri, harf duyarliligi.

    Lint kapsamindakiler cikis kodunu ETKILEMEZ; lint kendi bulgusunda
    zaten hata veriyor. Gecis donemli terimler (bolum_siniri'na kadar eski
    karsilik dogru) artik yalnizca burada; lint'te karsiliklari yok.

    Ikisi de bildiginde lint'inki kesinlikle daha bilgilidir; bu betigin
    duz listesi ayni bulgunun ikinci, nuanssiz kopyasidir. Veri yerinde
    kalir, YALNIZCA RAPOR birakilir: kapsanan bulgular tek satira
    indirilir, kapsanmayanlar tam listelenir.

    Yon onemli: kurallar dosyasindaki bir eksik GURULTU uretir, SESSIZLIK
    degil.
    """
    if not yol:
        return set()
    try:
        import yaml

        with open(yol, encoding="utf-8") as f:
            k = yaml.safe_load(f) or {}
    except (OSError, ImportError) as e:
        print(
            f"  uyari: lint kurallari okunamadi ({e}); eskimis listesi tam yazilacak.",
            file=sys.stderr,
        )
        return set()

    kapsam = set()
    for v in k.get("varyantlar") or []:
        for y in v.get("yanlis") or []:
            kapsam.add(_tr_kucult(y))
    for y in k.get("yasakli") or []:
        if y.get("bicim"):
            kapsam.add(_tr_kucult(y["bicim"]))
    return kapsam


def rapor(
    artiklar,
    sizinti,
    eskimis,
    kapi,
    sadik,
    envanter,
    kayitlar,
    hepsi,
    envanter_ister,
    lint_kapsam=frozenset(),
    gecis_oncesi=(),
    erken_yeni=(),
):
    print("\n=== 0. ARTIK ISTEM/SABLON ISARETLERI ===")
    print("    Bunlar okuyucuya GORUNUR. Once bunlar temizlenmeli.")
    if not artiklar:
        print("  temiz")
    for dosya, satir_no, aciklama, ctx in artiklar:
        print(f"  [{dosya}:{satir_no}] {aciklama}\n      {ctx}")

    kapsanan, kalan = [], []
    for v in eskimis:
        (kapsanan if _tr_kucult(v[3]) in lint_kapsam else kalan).append(v)

    print("\n=== 1. ESKIMIS KARSILIKLAR ===")
    print("  yok" if not eskimis else "")
    for no, dosya, k, eski_ad, ctx in kalan:
        print(f"  [{dosya}] '{eski_ad}' -> '{k.tr}'\n      {ctx}")
    if kapsanan:
        gruplar = {}
        for _no, _dosya, k, eski_ad, _ctx in kapsanan:
            gruplar.setdefault((eski_ad, k.tr), 0)
            gruplar[(eski_ad, k.tr)] += 1
        print("  --- lint tarafindan baglamiyla bildirilenler ---")
        print("      Burada duz listelenmez: sozluk_lint ayni bulgulari kendi")
        print("      kurallariyla veriyor. './calistir.sh lint' ciktisina bakin.")
        for (eski_ad, yeni), n in sorted(gruplar.items(), key=lambda x: -x[1]):
            print(f"      '{eski_ad}' -> '{yeni}': {n} bulgu")

    print(f"\n=== 1a. GECISTEN ONCE ESKI BICIM ({len(gecis_oncesi)}) -- bilgi ===")
    print("    Kapidan once eski bicim o donemin kelimesidir (Ayin <- ritüel).")
    print("    Ama yeni ad o bolumde henuz acilmamissa eski adla gecmesi de bir")
    print("    sizinti olabilir. Hata degil; cikis kodunu etkilemez.")
    if not gecis_oncesi:
        print("  yok")
    elif not hepsi:
        # Ayni bolumde bir eski bicim iki kez listelenebilir (iki terim ayni
        # eski bicimi tasiyorsa); "bolumde" sayisi bu yuzden kume uzerinden.
        bolumler_ = defaultdict(set)
        for no, _dosya, k, eski_ad, _ctx in gecis_oncesi:
            bolumler_[(eski_ad, k.tr, k.gecis)].add(no)
        for (eski_ad, yeni, g), nolar in sorted(
            bolumler_.items(), key=lambda x: -len(x[1])
        ):
            print(
                f"  '{eski_ad}' -> '{yeni}' (gecis {g}): {len(nolar)} bolumde  (--hepsi ile ayrinti)"
            )
    else:
        for no, dosya, k, eski_ad, ctx in sorted(gecis_oncesi, key=lambda x: x[0] or 0):
            print(f"  [{dosya}] '{eski_ad}' -> '{k.tr}' (gecis {k.gecis})\n      {ctx}")

    print(f"\n=== 1b. GECISTEN ONCE YENI BICIM ({len(erken_yeni)}) -- bakilacak ===")
    print("    Yeni ad, eski bicimin hala gecerli oldugu bolumde. Ya geriye donuk")
    print('    tasima fazla gitti ya da kelime burada baska anlamda ("kurban ve')
    print('    dua ayinleri"). Hata degil; cikis kodunu etkilemez.')
    if not erken_yeni:
        print("  yok")
    for no, dosya, k, bulunan, ctx in sorted(erken_yeni, key=lambda x: x[0] or 0):
        eskiler = "/".join(e for e, _ in k.eski_desen)
        print(
            f"  [{dosya}] '{bulunan}' (gecis {k.gecis}): '{eskiler}' mi olmali?\n      {ctx}"
        )

    print("\n=== 2. CEVRILMEDEN KALMIS INGILIZCE TERIMLER ===")
    print("  yok" if not sizinti else "")
    for no, dosya, k, ctx in sizinti:
        print(f"  [{dosya}] '{k.en}' -> beklenen '{k.tr}' ({k.yer})\n      {ctx}")

    yuksek = [x for x in kapi if x[0] == YUKSEK]
    dusuk = [x for x in kapi if x[0] == DUSUK]

    print("\n=== 3. KAPI ADAYLARI (yuksek guven) ===")
    print("    Bunlar hata degil, ADAYDIR. Metin ayni olsa da gonderge farkli")
    print("    olabilir: 'Kara Imparator' hem Mertebe 0 hem tarihi bir unvandir.")
    print("  yok" if not yuksek else "")
    for g, no, dosya, k, ctx in sorted(yuksek, key=lambda x: x[1] or 0):
        print(
            f"  [{dosya}] '{k.tr}' ({k.yer}) kapi={k.kapi} kullanim={no}\n      {ctx}"
        )

    print(f"\n=== 3a. KAYNAKTA DA GECIYOR ({len(sadik)}) -- sorun degil ===")
    print("    Kapidan once ama ILK GECISTEN sonra kullanilmis. Ingilizce")
    print("    metin de adi orada aniyor; ceviri sadik. Kapi 'aciklandigi")
    print("    yer' oldugu icin bu aralik normaldir.")
    if not sadik:
        print("  yok")
    elif not hepsi:
        terimler = sorted({k.tr for _, _, k, _ in sadik})
        print(
            f"  {len(terimler)} terim: {', '.join(terimler[:12])}"
            f"{' ...' if len(terimler) > 12 else ''}  (--hepsi ile ayrinti)"
        )
    else:
        for no, dosya, k, ctx in sorted(sadik, key=lambda x: x[0] or 0):
            print(
                f"  [{dosya}] '{k.tr}' kapi={k.kapi} "
                f"ilk_gecis={k.ilk_gecis} kullanim={no}\n      {ctx}"
            )

    if hepsi:
        print("\n=== 3b. KAPI ADAYLARI (dusuk guven -- muhtemelen siradan kelime) ===")
        for g, no, dosya, k, ctx in sorted(dusuk, key=lambda x: x[1] or 0):
            print(
                f"  [{dosya}] '{k.tr}' ({k.yer}) kapi={k.kapi} "
                f"kullanim={no}\n      {ctx}"
            )

    if envanter_ister:
        print("\n=== 4. ENVANTER (yayimlanmis yuzey) ===")
        # denetle() her terim icin bolum basina EN FAZLA bir kez ekler
        # (ilk gecerli gecis), yani ham 'b' listesinin uzunlugu GERCEK
        # gecis SAYISI degil, terimin gectigi bolum SAYISIdir -- ama eski
        # etiket "kez" (defa) buna aykiri okunuyordu. Ayrica bolumler_tr()
        # burada bolum_sozlugu() UZERINDEN degil DOGRUDAN okunuyor, yani
        # ayni numarali IKI dosya olsa (veri hatasi) o numara ham 'b'ye
        # iki kez girer; set() + None filtresiyle hem bu cift-sayimi hem
        # numarasi cozulemeyen (None) dosyalari ayikliyoruz.
        goruntu = [
            (terim, sorted(set(x for x in b if x is not None)))
            for terim, b in envanter.items()
        ]
        for terim, bl in sorted(goruntu, key=lambda tb: -len(tb[1])):
            print(f"    {terim}: {len(bl)} bolumde, bolum {bl}")
        hic = [k.tr for k in kayitlar if k.tr not in envanter]
        print(
            f"\n  {len(hic)} terim henuz hic kullanilmamis -- "
            f"serbestce degistirilebilir."
        )

    print("\n--- OZET ---")
    print(f"  ARTIK ISARET      : {len(artiklar)}   <- varsa ilk is bu")
    _kapsanan = sum(1 for v in eskimis if _tr_kucult(v[3]) in lint_kapsam)
    _ek = f"   ({_kapsanan} lint kapsaminda)" if _kapsanan else ""
    print(f"  eskimis           : {len(eskimis)}{_ek}")
    print(f"  gecisten once     : {len(gecis_oncesi)}   (bilgi)")
    print(
        f"  erken yeni bicim  : {len(erken_yeni)}"
        + ("   <- bakilacaklar" if erken_yeni else "")
    )
    print(f"  sizinti           : {len(sizinti)}")
    print(f"  kapi (yuksek)     : {len(yuksek)}   <- bakilacaklar")
    print(f"  kaynakta da var   : {len(sadik)}   (sorun degil)")
    print(f"  kapi (dusuk)      : {len(dusuk)}   (--hepsi ile gorulur)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sozluk", default=None)
    ap.add_argument("--bolumler", default=None)
    ap.add_argument("--hepsi", action="store_true")
    ap.add_argument("--envanter", action="store_true")
    ap.add_argument(
        "--kurallar",
        default=None,
        help="lint-kurallari.yml; burada kapsanan eskimis "
        "bicimler tek satira indirilir (bkz. lint_kapsami)",
    )
    ap.add_argument(
        "--cumle-ici-yuksek",
        action="store_true",
        dest="cumle_ici",
        help="cumle ortasindaki tek kelimelik terimleri yuksek "
        "guven say (bkz. guven_ver)",
    )
    a = ap.parse_args()

    try:
        sozluk = lotm.sozluk_yukle(a.sozluk)
        bolumler = lotm.bolumler_tr(a.bolumler)
    except (FileNotFoundError, OSError) as e:
        sys.exit(f"HATA: {e}")

    kayitlar = kayitlari_kur(sozluk)
    birimler = birimler_kur(bolumler)
    n_baslik = len(birimler) - len(bolumler)
    print(
        f"{len(kayitlar)} terim, {len(bolumler)} bolum ({n_baslik} baslik).",
        file=sys.stderr,
    )

    kaymalar = satir_kaymalari(a.bolumler or lotm.BOLUMLER_TR, bolumler)
    artiklar = artik_tara(birimler, kaymalar)
    s, e, kp, sd, env, ey = denetle(
        kayitlar, birimler, a.cumle_ici, maske=kelime_maskesi(sozluk)
    )

    # Gecis (bolum_siniri, bkz. gecis_bolumu): gecisten ONCEKI eski bicim o
    # donemin dogru karsiligidir, eskimis sayilmaz. Karar TERIM BASINA
    # verilir; eskiden eski bicimin kendisine gore anahtarlaniyordu ve ayni
    # eski yazim iki terimde farkli gecislerle dursa biri digerini ezerdi.
    def gecisten_once(v):
        no, _dosya, k, _eski, _ctx = v
        return k.gecis is not None and no is not None and no < k.gecis

    gecis_oncesi = [v for v in e if gecisten_once(v)]
    e = [v for v in e if not gecisten_once(v)]

    lint_kapsam = lint_kapsami(a.kurallar)
    rapor(
        artiklar,
        s,
        e,
        kp,
        sd,
        env,
        kayitlar,
        a.hepsi,
        a.envanter,
        lint_kapsam,
        gecis_oncesi,
        ey,
    )

    # Cikis kodu: okura gorunen ya da kesin yanlis olan bulgular. Kapi
    # adaylari ADAYDIR (karari insan verir) ve cikis kodunu etkilemez.
    # Lint kapsamindaki eski bicimler lint'in kendi cikis kodunda.
    kalan = [v for v in e if tr_kucult(v[3]) not in lint_kapsam]
    return 1 if (artiklar or kalan or s) else 0


if __name__ == "__main__":
    sys.exit(main())
