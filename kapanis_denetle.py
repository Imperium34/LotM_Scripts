#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kapanis_denetle.py -- Ch_NN.md acilis sablonunu bitmis Turkce bolume uygular.

Ch_NN.md'nin sonundaki "Kapanis denetimi" listesi zaten bir sinama plani.
Burada o listenin HIZALAMA GEREKTIRMEYEN maddeleri otomatiklestirilir:

  1. Cince karakter kalmadi                     -> madde 1
  2. A.1/A.2'deki Ingilizce terim ceviriye       -> madde 1'in ikinci yarisi
     oldugu gibi sizmadi
  3. B'deki dondurulmus satirlar birebir ve      -> madde 3
     dogru sayida
  4. A.3'te yasaklanan kelimeler yok             -> madde 4'un ikinci yarisi
  5. A.1/A.2'deki her karsilik metinde var       -> madde 4'un ilk yarisi (zayif
                                                    bicimi: varlik, tekillik degil)

Madde 2 (italikler) ve madde 5 (tirnaklar) paragraf kimligi ister; hizalama
bunu tasiyamiyor (hedef metin okunabilirlik icin paragraf birlestirip
boluyor), o yuzden buraya alinmadi.

IKI TUZAK
---------
1. YASAK KELIME, IZINLI TERIMIN ICINDE OLABILIR. Bolum 44 bunu kendisi
   soyluyor: ¶15'te "silindir" yasaktir (altipatlarin parcasi "top"tur) ama
   ¶22'deki "silindir sapka" dogrudur. Duz arama her seferinde yanlis alarm
   verir. Cozum: once A.1/A.2'deki izinli karsiliklar metinde maskelenir,
   yasak arama maskelenmis metinde yapilir.

2. BUYUK HARF ANLAM TASIR. "Aptal" Soytari'nin yasak esanlamlisidir; kucuk
   "aptal" siradan bir sifattir ("yuzunun aptallastigini gordu"). Bu yuzden
   buyuk harfle baslayan yasaklar buyuk/kucuk harfe duyarli aranir.

   Turkce kucultme ayrica ozel: Python'un .lower()'i I -> i verir, oysa
   Turkce'de I -> ı'dır. turkce.tr_kucult bunu duzeltir; harf duyarsiz
   arama da re.IGNORECASE ile degil turkce.tr_desen ile yapilir.

TEREDDUT SATIRLARI UYGULANMAZ. A.2'deki `[TEREDDUT]` etiketi "karar senin"
demektir, "karar verildi" degil; bunlari dayatmak verilmemis bir karari
zorlar.

SABLONUN YAZIM KURALLARI
------------------------
Bu betigin okudugu hucre dilbilgisi, sablonu ureten skill'in
cikti-sartnamesi.md dosyasinda "Makine sozlesmesi" basligi altinda yazili.
Burada bir okuma kurali degisirse orasi da degismeli; ikisi ayni
sozlesmenin iki yuzu.

Kullanim:
    kapanis_denetle.py Reports/Ch_44.md cevrilmis_44.md
    kapanis_denetle.py Reports/Ch_44.md --bolum 44      (lotm'dan ceker)
"""

import argparse
import re
import sys
from dataclasses import dataclass, field

from turkce import tr_desen, tr_kucult

CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")

# Tabloda ¶ atiflari ve parantezli aciklamalar terimin parcasi degildir.
_PARANTEZ = re.compile(r"\([^)]*\)")
_PILOT = re.compile(r"^\s*\|")

# A.3'te yasak bildiren fiiller. TEK liste: yasaklar() ile istisnalar()
# eskiden ayri listeler tutuyordu ve "sokulmaz" yalnizca birinde vardi;
# **"x" sokulmaz** x'i yasakliyor ama istisnasini maskelemiyordu. Okuyucu
# hosgorulu: sozlesme yalnizca "yasak" ve "yazılmaz"i yazdirir, ama eski
# sablonlar da okunabilsin diye hepsi taninir.
YASAK_FIILLERI = ("yasak", "yazılmaz", "girmez", "kullanılmaz", "sokulmaz")

_BR = re.compile(r"<br\s*/?>", re.I)


def bolumler(metin: str) -> dict:
    """### / ## basliklarina gore metni parcalar."""
    parcalar, ad, birikim = {}, None, []
    for satir in metin.split("\n"):
        m = re.match(r"^#{2,3}\s+(.+?)\s*$", satir)
        if m:
            if ad:
                parcalar[ad] = "\n".join(birikim)
            ad, birikim = m.group(1), []
        else:
            birikim.append(satir)
    if ad:
        parcalar[ad] = "\n".join(birikim)
    return parcalar


def tablo(govde: str) -> list:
    """Markdown tablosunu satir listesine cevirir (baslik ve ayirici atilir)."""
    satirlar = [s for s in govde.split("\n") if _PILOT.match(s)]
    cikti = []
    for i, s in enumerate(satirlar):
        hucreler = [h.strip() for h in s.strip().strip("|").split("|")]
        if i == 0 or all(set(h) <= set("- :") for h in hucreler if h):
            continue
        cikti.append(hucreler)
    return cikti


_ISARET = re.compile(r"\*\*|\*|`|<br\s*/?>")
_ALINTI = re.compile(r'["\u201c\u201d\u2018\u2019]([^"\u201c\u201d\u2018\u2019]+)["\u201c\u201d\u2018\u2019]')


def kaliplar(hucre: str) -> list:
    """
    Tablo hucresinden ARANACAK dizeleri cikarir.

    Hucre duz bir dize degil; icinde markdown ve aciklama var:
        **"Elliott'in yeri."**              -> kalin + tirnak
        fiil daima **"koyulas-"**           -> nesir + tirnakli govde
        ruh aracisi — **kucuk harfle**      -> terim + em-dash notu
        A<br>B<br>C                         -> tek hucrede COK kalip

    Kural: <br> ile bol; her parcadan isaretleri at; em-dash'ten sonrasini
    (aciklama) at; icinde tirnak varsa YALNIZCA tirnakli kismi al, yoksa
    parcanin kendisini al.
    """
    out = []
    for parca in re.split(r"<br\s*/?>", hucre):
        parca = _ISARET.sub("", parca).strip()
        parca = re.split(r"\s+[—–]\s+", parca)[0].strip()
        if not parca:
            continue
        alintilar = _ALINTI.findall(parca)
        out.extend(a.strip() for a in alintilar) if alintilar else out.append(parca)
    return [k for k in out if k]


# Ok ya da uc nokta tasiyan hucre KALIP tarifidir, dize degil:
#     paralı asker → kesinti → güvenlik …
# Ortadaki "kesinti" aranacak bir metin degil, ARADAKI SEYIN ADI. Boyle
# bir hucreyi duz dize gibi aramak her seferinde 0/4 verir.
#
# Otomatiklesmesi icin literal parcalar TIRNAK ICINE alinmalidir:
#     "paralı asker" → kesinti → "güvenlik" …
# O zaman tirnakli parcalar SIRAYLA, aralarinda sinirli bosluk olacak
# sekilde aranir. Tirnak yoksa uydurmak yerine ELLE'ye birakilir.
_OK = re.compile(r"[→⇒>]|\.\.\.|…")
ARA_SINIRI = 60  # iki literal parca arasinda en fazla bu kadar karakter


def kalip_turu(hucre: str) -> str:
    """
    'dize' | 'govde' | 'dizi' | 'elle'

    Govde isareti '-' TIRNAGIN ICINDEDIR ("koyulaş-"), hucrenin sonunda
    degil; bu yuzden karar ham hucreye degil AYIKLANMIS kalibina bakar.

    <br> ok testinden ONCE ayiklanir. _OK '>' karakterini de ok sayar ve
    eskiden "<br>" her seferinde ok gibi okunuyordu: '"A"<br>"B"' iki ayri
    dondurulmus satir yerine tek bir "dizi" kalibi oluyordu. <br> artik
    sablon sozlesmesinde yasak (denetle() bunu ayrica uyarir); burada
    yalnizca eski sablonlar dogru okunsun diye ayirici olarak ele alinir.
    """
    oksuz = _BR.sub(" ", hucre)
    if not _OK.search(oksuz):
        temiz = kaliplar(hucre)
        return "govde" if temiz and _govde_mi(temiz[0]) else "dize"
    return "dizi" if len(_ALINTI.findall(oksuz)) >= 2 else "elle"


def dizi_deseni(hucre: str) -> str:
    parcalar = [re.escape(a.strip()) for a in _ALINTI.findall(hucre)]
    return (r".{0," + str(ARA_SINIRI) + r"}?").join(parcalar)


def govde_deseni(kalip: str) -> str:
    """
    Aranacak regex. Sonu '-' ile biten kalip GOVDEDIR: "koyulas-" hem
    "koyulasti" hem "koyulasmis" hem "koyulasirken" ile eslesir.
    """
    return re.escape(kalip[:-1]) if kalip.endswith("-") else re.escape(kalip)


def _govde_mi(kalip: str) -> bool:
    """Sonu '-' ile biten kalip govdedir: butun cekimleriyle eslesir."""
    return kalip.rstrip().endswith("-")


def _govde_ayir(kalip: str) -> tuple:
    """'havale et-' -> ('havale et', True);  'kanepe' -> ('kanepe', False)"""
    k = kalip.strip()
    return (k.rstrip("-").rstrip(), True) if _govde_mi(k) else (k, False)


@dataclass
class Satir:
    """
    A.1 / A.2 tablosunun bir satiri, BIR KEZ ayristirilmis hali.

    Eskiden terimler() her Turkce bicim icin ayri bir (en, tr, not) uclusu
    uretiyordu. Uc tuketicinin ihtiyaci farkli oldugu icin bu sekil
    hicbirine tam uymuyordu:
      - varlik denetimi Turkce bicimleri ve hangisinin govde oldugunu ister,
      - maskeleme literal bicimleri ister,
      - sizinti denetimi her Ingilizce bicimi, AYNI SATIRIN butun Turkce
        bicimleriyle karsilastirmak ister.
    Ingilizce hucre hic bolunmuyordu ("Seer / Seer potion" tek dize
    olarak aranip hic bulunmuyor, yani sizinti denetimi o satirda sessizce
    kapaliydi) ve govde tiresi aranan dizenin parcasi kaliyordu.
    """

    en: list = field(default_factory=list)    # ["Seer", "Seer potion"]
    tr: list = field(default_factory=list)    # [("havale et", True), ...]
    kalan: str = ""
    tereddut: bool = False


def _bicimler(hucre: str) -> list:
    """' / ' ile ayrilmis bicimler; parantez ve markdown isareti atilmis."""
    out = []
    for parca in hucre.split("/"):
        out.extend(kaliplar(_PARANTEZ.sub("", parca)))
    return out


def satirlar(govde: str) -> list:
    """A.1 / A.2 govdesini Satir listesine cevirir. TEREDDUT satirlari da
    doner, tereddut=True isaretiyle; hangi denetimin onlari atlayacagina
    cagiran karar verir."""
    out = []
    for h in tablo(govde):
        if len(h) < 2:
            continue
        kalan = " ".join(h[2:])
        out.append(
            Satir(
                en=_bicimler(h[0]),
                tr=[_govde_ayir(t) for t in _bicimler(h[1])],
                kalan=kalan,
                tereddut="TEREDDÜT" in kalan,
            )
        )
    return out


def terimler(govde: str, tereddut_atla=True) -> list:
    """
    ESKI ARAYUZ, uyumluluk icin: (ingilizce, turkce, not) uclulari.
    denetle() artik satirlar()'i kullaniyor. Bu fonksiyon eski davranisi
    birebir korur (Ingilizce bolunmez, govde tiresi kalir) ki mevcut
    testler ya da elle cagrilar degismeden calissin.
    """
    out = []
    for h in tablo(govde):
        if len(h) < 2:
            continue
        en, tr = h[0], h[1]
        kalan = " ".join(h[2:])
        if tereddut_atla and "TEREDDÜT" in kalan:
            continue
        for parca in tr.split("/"):
            for temiz in kaliplar(_PARANTEZ.sub("", parca)):
                out.append((_PARANTEZ.sub("", en).strip(), temiz, kalan))
    return out


def dondurulmus(govde: str) -> list:
    """(turkce_kalip, beklenen_sayi) -- sayi sutunundaki bas tamsayi."""
    out = []
    for h in tablo(govde):
        if len(h) < 3:
            continue
        m = re.match(r"\s*(\d+)", h[2])
        if not m:
            continue
        # Eski sablonlarda bir hucre <br> ile ayrilmis birden cok satir
        # tasiyabilir; her biri AYRI AYRI ve ayni sayida aranir. Sozlesme
        # artik her satiri ayri tablo satirina yazdirir; denetle() <br>
        # gorunce ayrica uyarir.
        tur = kalip_turu(h[1])
        if tur == "elle":
            # Kalip tarifi ama literal parcalari tirnakli degil: sessizce
            # 0 bulup HATA vermektense elle bakilmak uzere isaretlenir.
            out.append((h[1].strip(), int(m.group(1)), "elle"))
            continue
        if tur == "dizi":
            out.append((h[1].strip(), int(m.group(1)), "dizi"))
            continue
        for kalip in kaliplar(h[1]):
            # Tur kalip basina belirlenir: bir hucrede hem dize hem govde
            # bulunabilir.
            out.append(
                (kalip, int(m.group(1)),
                 "govde" if _govde_mi(kalip) else "dize")
            )
    return out


# Sol sinir. '\b' KULLANILMAZ: Python'da '_' kelime karakteridir ve
# Klein'in ic sesi bastan sona _italik_; markdown isaretine bitisik bir
# kelime '\b' ile yakalanmaz. Sag taraf ACIK birakilir, cunku Turkce
# eklemelidir: "defter" -> "defteri", "ekip" -> "ekibi".
_SOL_SINIR = r"(?<![^\W_])"


def sozcuk_gecer_mi(kelime: str, metin: str) -> bool:
    return bool(re.search(_SOL_SINIR + re.escape(kelime), metin))


# Turkce unsuz yumusamasi: sert unsuzle biten sozcuk unlu ekle birlesince
# yumusar. "ekip" -> "ekibi", "kitap" -> "kitabi", "sokak" -> "sokagi".
# On ek eslemesi bu yuzden TEK BASINA yetmez; yumusamis govde de aranir.
_YUMUSAMA = {"p": "b", "ç": "c", "t": "d", "k": ["ğ", "g"]}


def govde_bicimleri(kelime: str) -> list:
    out = [kelime]
    son = kelime[-1:]
    if son in _YUMUSAMA:
        yeni = _YUMUSAMA[son]
        for y in [yeni] if isinstance(yeni, str) else yeni:
            out.append(kelime[:-1] + y)
    return out


def yasak_gecer_mi(kelime: str, metin: str) -> bool:
    """
    Yasak kelime denetimi -- sol sinirli.

    Duz altdize aramasi "ekip"i "cekip" icinde bulur; bolum 44'te tam bu
    oldu ("omzunu geriye CEKIP"). Sag tarafi acik birakmak sarttir, yoksa
    "ekibi" kacar.
    """
    if kelime[:1].isupper():
        return any(sozcuk_gecer_mi(b, metin) for b in govde_bicimleri(kelime))
    kucuk = tr_kucult(metin)
    return any(
        sozcuk_gecer_mi(b, kucuk) for b in govde_bicimleri(tr_kucult(kelime))
    )


def istisnalar(govde: str) -> list:
    """
    A.3 maddelerinde yasagin YANINDA duran izinli bicimler.

    Bolum 44 kendi kuralini soyle yaziyor:
        **"silindir" yasaktir** (altipatlarin parcasi "top"tur).
        ¶22'deki sapka icin "silindir sapka" ise DOGRUDUR

    Yani istisna zaten maddede, kalin vurgunun DISINDA, tirnak icinde
    duruyor. Kalin kismi yasak, geri kalan tirnaklar izinli bicimdir;
    bunlar maskelenmezse "silindir sapka" her bolumde yanlis alarm verir.
    """
    out = []
    for madde in re.findall(r"^\s*[-*]\s+(.+)$", govde, re.M):
        kalinlar = re.findall(r"\*\*(.+?)\*\*", madde, re.S)
        if not any(f in tr_kucult(" ".join(kalinlar)) for f in YASAK_FIILLERI):
            continue
        kuyruk = re.sub(r"\*\*.+?\*\*", " ", madde, flags=re.S)
        out.extend(a.strip() for a in _ALINTI.findall(kuyruk) if a.strip())
    return out


def yasaklar(govde: str) -> list:
    """
    A.3'teki kalin vurgulardan yasak kelimeleri ayiklar.

    Sekiller: **"X" yasaktir**, **"X", "Y" yasaktir**, **"X" yazilmaz.**,
    **"X" metne girmez**. Yalnizca yasak fiili gecen kalin blok okunur;
    kalan kalin vurgular (ornegin **resimdir**) atlanir.
    """
    out = []
    for kalin in re.findall(r"\*\*(.+?)\*\*", govde, re.S):
        if not any(f in tr_kucult(kalin) for f in YASAK_FIILLERI):
            continue
        for alinti in re.findall(r'["“]([^"”]+)["”]', kalin):
            alinti = alinti.strip()
            if alinti:
                out.append(alinti)
    return out


def taninmayan_yasaklar(govde: str) -> list:
    """
    Yasak gibi GORUNUP makinenin okumadigi kalin bloklar.

    Icinde cift tirnakli dize olan ama taninan bir yasak fiili olmayan
    kalin blok: **"mahzen" yok**. yasaklar() bunu sessizce atliyordu;
    sablon yazari yasak koydugunu, makine hic yasak olmadigini sanirdi.
    Bolum 47 sablonunun ilk halinde uc yasak tam bu yuzden kayboldu.
    """
    out = []
    for kalin in re.findall(r"\*\*(.+?)\*\*", govde, re.S):
        if any(f in tr_kucult(kalin) for f in YASAK_FIILLERI):
            continue
        if re.search(r'["“][^"”]+["”]', kalin):
            out.append(re.sub(r"\s+", " ", kalin).strip())
    return out


def maskele(metin: str, izinli: list) -> str:
    """
    Izinli karsiliklari metinden siler; yasak arama kalan metinde yapilir.

    Uzundan kisaya: "silindir sapka" once silinsin ki geriye "silindir"
    kalmasin. Ayni sey "Sen Avi Mermisi" / "Mermi" gibi ic ice geciren
    butun ciftler icin gecerli.
    """
    # re.IGNORECASE KULLANILMAZ: ı ile i'yi ayni harf sayar. Izinli "ayin"
    # metindeki "ayın"i da silerdi ve oradaki bir yasak gorulmezdi.
    for t in sorted(izinli, key=len, reverse=True):
        if t:
            metin = re.sub(tr_desen(t), " ", metin)
    return metin


def gecis_sayisi(metin: str, kalip: str) -> int:
    return len(re.findall(govde_deseni(kalip), metin))


def karsilik_var_mi(terim: str, metin: str, govde: bool = False):
    """
    VARLIK denetimi -- ek ve bicim toleransli.

    Donus: True (var) | False (yok) | None (dogrulanamaz: terimin butun
    sozcukleri iki harf ya da daha kisa, orn. "iş").

    Iki gercek vaka:
      "Gece Sahinleri" metinde "Gece Sahini" olarak gecer  (cogul -> tekil)
      "terennum etmek" metinde "terennumu ... etmeyi" olur (mastar -> cekim)

    Bu yuzden (1) sozcukler AYRI AYRI aranir, bitisik obek olarak degil,
    (2) her sozcugun sonundan dort karaktere kadar kirpilir. Gevsek bir
    olcut; ama bu yalnizca UYARI uretir, dondurulmus satirlarda degil --
    orada birebirlik sart ve hicbir kirpma yapilmaz.

    IKI DUZELTME
      - Uc harfli sozcukler: denenen on ek uzunluklari eskiden
        range(len, 3, -1) idi, yani uc harfli bir sozcukte BOS. any() bos
        dizide False doner; "Ray Bieber", "Bay Neil", "ruh göçü" her
        bolumde "bulunamadi" diye raporlaniyordu. Artik tam sozcuk her
        zaman denenir, kirpma dort harfte durur.
      - Govde (govde=True, sablonda sonu '-' ile biten bicim): SON sozcuk
        yazarin sectigi govdedir ve kirpilmaz; "rol yap-" -> "yap" on eki
        "yapmaya"yi bulur. Tire artik aranan dizenin parcasi degil.

    Iki harfli sozcukler atlanir (eskiden de atlaniyordu). Terimin HICBIR
    sozcugu denetlenemiyorsa eskiden sessizce True donuyordu, yani "iş"
    her bolumde "var" sayiliyordu; artik None doner ve rapor bunu ayrica
    soyler.
    """
    kucuk = tr_kucult(metin)
    sozcukler = terim.split()
    denetlenen = 0
    for i, sozcuk in enumerate(sozcukler):
        s = tr_kucult(sozcuk)
        if len(s) < 3:
            continue
        denetlenen += 1
        if govde and i == len(sozcukler) - 1:
            if not sozcuk_gecer_mi(s, kucuk):
                return False
            continue
        # Tam bicimden dort karaktere kadar her on ek denenir. "damgalamak"
        # metinde "damgasini basmak" olarak gecebilir. Alt sinir dorttur
        # ama tam sozcuk her zaman denenir (uc harfliler dahil).
        alt = min(len(s), 4)
        if not any(sozcuk_gecer_mi(s[:n], kucuk) for n in range(len(s), alt - 1, -1)):
            return False
    return True if denetlenen else None


def denetle(rapor: str, ceviri: str) -> list:
    """[(seviye, mesaj)] doner. seviye: HATA / UYARI / TAMAM"""
    p = bolumler(rapor)

    def bul(*anahtarlar):
        for a in anahtarlar:
            for k, v in p.items():
                if k.startswith(a):
                    return v
        return ""

    # TEREDDUT satirlari hicbir denetime girmez (karar insanin); eskiden de
    # terimler() onlari bastan atiyordu.
    a12 = [
        st for st in satirlar(bul("A.1")) + satirlar(bul("A.2"))
        if not st.tereddut
    ]
    b = dondurulmus(bul("B. DONDURULAN", "B."))
    a3 = yasaklar(bul("A.3"))
    izinli = (
        [tr for st in a12 for tr, _g in st.tr]
        + [t[0] for t in b if t[2] == "dize"]
        + istisnalar(bul("A.3"))
    )

    bulgular = []

    # 0. Sablonun kendisi: makinenin yanlis okuyacagi bicimler. Bunlar
    # cevirinin degil SABLONUN hatasidir; ama sessiz kalirlarsa asagidaki
    # denetimler ya hic calismaz ya da yanlis alarm verir.
    for ad, anahtarlar in (("A.1", ("A.1",)), ("A.2", ("A.2",)),
                           ("B", ("B. DONDURULAN", "B."))):
        brli = [
            satir.strip()[:60] for satir in bul(*anahtarlar).split("\n")
            if _PILOT.match(satir) and _BR.search(satir)
        ]
        if brli:
            bulgular.append(
                ("UYARI", f"şablon: {ad} tablosunda <br> var, her dize ayrı "
                          f"satıra yazılmalı ({len(brli)} satır): «{brli[0]}»")
            )
    for kalin in taninmayan_yasaklar(bul("A.3")):
        bulgular.append(
            ("UYARI", f"şablon: A.3'te tanınmayan yasak biçimi, makine "
                      f"denetlemiyor: «{kalin[:60]}»  — \"yasak\" ya da "
                      f"\"yazılmaz\" ile yazın")
        )

    # 1. Cince karakter
    cin = CJK.findall(ceviri)
    bulgular.append(
        ("HATA", f"{len(cin)} Çince karakter kaldı: {''.join(sorted(set(cin))[:20])}")
        if cin
        else ("TAMAM", "Çince karakter yok")
    )

    # 2. Ingilizce terim sizintisi
    # Ozel adlar iki dilde AYNI yazilir (Klein, Backlund, Leonard
    # Mitchell). Bunlari "cevrilmeden kalmis" saymak her bolumde yanlis
    # alarm demek; sizinti ancak Ingilizce bicim Turkce karsiligindan
    # FARKLIYSA anlamlidir.
    #
    # Her Ingilizce bicim, AYNI SATIRIN butun Turkce bicimleriyle
    # karsilastirilir: "Leonard / Captain Dunn" satirinda "Leonard"
    # Turkce bicimlerden birinde de gectigi icin sizinti sayilmaz.
    sizan = set()
    for st in a12:
        tr_kucukler = [tr_kucult(tr) for tr, _g in st.tr]
        for en in st.en:
            en_k = tr_kucult(en)
            if len(en) <= 3 or any(en_k == t or en_k in t for t in tr_kucukler):
                continue
            if re.search(r"\b" + re.escape(en) + r"\b", ceviri):
                sizan.add(en)
    sizan = sorted(sizan)
    bulgular.append(
        ("HATA", "İngilizce terim çeviride: " + ", ".join(sizan))
        if sizan
        else ("TAMAM", "İngilizce terim sızıntısı yok")
    )

    # 3. Dondurulmus satirlar
    for kalip, bekle, tur in b:
        if tur == "elle":
            bulgular.append(
                ("UYARI",
                 f"kalıp tarifi, elle bakın (×{bekle} bekleniyor): «{kalip[:60]}»"
                 "  — literal parçaları tırnağa alırsanız otomatik denetlenir")
            )
            continue
        n = (
            len(re.findall(dizi_deseni(kalip), ceviri, re.S))
            if tur == "dizi"
            else gecis_sayisi(ceviri, kalip)
        )
        etiket = {"dize": "dondurulmuş", "govde": "gövde", "dizi": "dizi"}[tur]
        bulgular.append(
            ("TAMAM", f"{etiket} «{kalip[:58]}» ×{n}")
            if n == bekle
            else ("HATA", f"{etiket} «{kalip[:58]}»: beklenen {bekle}, bulunan {n}")
        )

    # 4. Yasak kelimeler (maskelenmis metinde)
    temiz = maskele(ceviri, izinli)
    for y in a3:
        if yasak_gecer_mi(y, temiz):
            bulgular.append(("HATA", f"yasak kelime geçiyor: «{y}»"))
    if not any(s == "HATA" and "yasak kelime" in m for s, m in bulgular):
        bulgular.append(("TAMAM", f"{len(a3)} yasak kelimenin hiçbiri geçmiyor"))

    # 5. Karsiliklarin varligi (zayif bicim)
    eksik, dogrulanamaz, toplam = set(), set(), 0
    for st in a12:
        for tr, govde in st.tr:
            toplam += 1
            sonuc = karsilik_var_mi(tr, ceviri, govde=govde)
            gorunen = tr + ("-" if govde else "")
            if sonuc is None:
                dogrulanamaz.add(gorunen)
            elif not sonuc:
                eksik.add(gorunen)
    ek = (f"  (iki harfli, doğrulanamadı: {', '.join(sorted(dogrulanamaz))})"
          if dogrulanamaz else "")
    bulgular.append(
        ("UYARI", "metinde bulunamayan karşılık: " + ", ".join(sorted(eksik)) + ek)
        if eksik
        else ("TAMAM", f"{toplam - len(dogrulanamaz)} karşılığın hepsi metinde var" + ek)
    )
    return bulgular


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rapor")
    ap.add_argument("ceviri", nargs="?")
    ap.add_argument("--bolum", type=int)
    a = ap.parse_args()

    rapor = open(a.rapor, encoding="utf-8").read()
    if a.ceviri:
        ceviri = open(a.ceviri, encoding="utf-8").read()
    elif a.bolum:
        import lotm

        b = lotm.bolum_sozlugu(lotm.bolumler_tr()).get(a.bolum)
        if b is None:
            sys.exit(f"{a.bolum}. bölüm Türkçe kaynakta yok")
        ceviri = b.metin
    else:
        sys.exit("çeviri dosyası ya da --bolum gerekli")

    hata = 0
    for seviye, mesaj in denetle(rapor, ceviri):
        isaret = {"HATA": "✗", "UYARI": "!", "TAMAM": "✓"}[seviye]
        print(f" {isaret} {mesaj}")
        hata += seviye == "HATA"
    print(f"\n{hata} hata." if hata else "\nTemiz.")
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
