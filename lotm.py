#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lotm.py -- LotM ceviri projesi icin ortak temel.

Uc sey bu projede birden fazla yerde tekrarlaniyordu ve zamanla birbirinden
kaymaya basladi. Hepsi burada tek tanima indirildi:

  1. BOLUME AYIRMA. chinese_lookup.py sirayla sayiyordu, kapi_denetle.py basliktaki
     numarayi okuyordu, yayim_denetle.py dosya adindan aliyordu. Ucu de "279. bolum"
     derken farkli seyler kastediyordu.

  2. SOZLUK YUKLEME. terimleri_topla / sozluk_yukle / load_yaml_entries ayni
     YAML'i uc ayri sekilde okuyordu. Artik tek Terim kaydi var; her betik
     kendi gorunumunu ondan turetir.

  3. "Turkce (English)" AYIRMA. ingilizce_al / ingilizce_ayikla /
     etiket_temizle / ISIM_PATTERN -- dort kopya, dort davranis.

CINCE NUMARALANDIRMA (dogrulanmis)
----------------------------------
Cince ham metinde numaralandirma HER CILTTE SIFIRLANIR (Qidian standardi).
Sekiz tane "第一章" vardir; basliktaki numara tek basina bolumu tanimlamaz.

Ustelik ham metinde iki yerde numara yanlis yazilmis:
    cilt 3: 231 yerine ikinci kez 230  -> surekli 713
    cilt 8:   7 yerine ikinci kez   6  -> surekli 1360
Ama her ciltteki bolum SAYISI wiki ile birebir tutuyor (213/269/250/214/
204/116/87/41). Yani cilt icindeki SIRA guvenilir, ETIKET degil.

Bu yuzden surekli numara sudur:  cilt_baslangici - 1 + cilt_icindeki_sira
Etiket yalnizca cilt sinirini bulmak icin kullanilir (yerel numaranin geri
sarmasi). Tekrar eden bir numara geri sarma degildir, dolayisiyla yukaridaki
iki yazim hatasi sinir tespitini bozmaz.

Kullanim:
    import lotm

    sozluk = lotm.sozluk_yukle()
    for t in sozluk.terimler:
        print(t.tr, t.en, t.zh)

    zh = lotm.bolum_al(279, "zh")
    en = lotm.bolum_al(279, "en")

Tanilar:
    python3 lotm.py kontrol      # uc kaynagin numaralari uyusuyor mu?
    python3 lotm.py ciltler      # cilt sinirlari wiki ile tutuyor mu?
    python3 lotm.py anomali      # ham metindeki numara hatalari
    python3 lotm.py cince        # sozlukte Cince karsiligi eksik terimler
    python3 lotm.py saglik       # arac neyi OKUYAMADI? (bulgu degil, kapsam)
    python3 lotm.py iz 1401 en   # eksik bir bolumun ham metinde izini surer

'kontrol' ile 'saglik' farkli sorular sorar ve biri digerinin yerine
gecmez: 'kontrol' bulunan verinin tutarli olup olmadigina bakar, 'saglik'
verinin ne kadarinin gercekten okunabildigine. Yarisi okunamamis bir
kaynak da tutarli gorunebilir.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from turkce import en_kucult, tr_buyut, tr_desen, tr_kucult  # noqa: F401 (disa verilir)

try:
    import yaml
except ImportError:
    print("HATA: PyYAML gerekli.  pip install pyyaml", file=sys.stderr)
    sys.exit(1)

import functools

# =====================================================================
# KAPSAM (SAGLIK) KAYDI
# =====================================================================
#
# Bu araclarin tamami yanlis pozitifi bastirmak uzerine kurulu ve bu
# dogru bir tercih: gurultulu arac okunmaz olur. Ama bastirmanin bedeli
# su: "hicbir sey bulamadim" ile "bakamadim" ciktida AYNI gorunuyor.
#
#   - ayristirilamayan front matter  -> sessizce dosya adina dusuluyor
#   - cozulemeyen kodlama            -> sessizce errors="replace"
#   - cilt sayisi tutmuyor           -> stderr'e uyari, zincir devam
#   - tekrar eden bolum numarasi     -> ilki sessizce kazaniyor
#
# Hicbiri BULGU degil; hepsi KAPSAM bilgisi. Ayri bir kanala yazilirlar
# ki bulgu listesini kirletmeden "bu calisma ne kadarini gercekten
# gordu" sorusu yanitlanabilsin.


def _tek_satir(s, n=60) -> str:
    """
    Rapora girecek her serbest metni tek satira indirger.

    GEREKCE: ham metinden gelen parcalar \\r icerebiliyor (Windows satir
    sonu). Terminale \\r basildiginda imlec satir basina doner ve yazilan
    satirin USTUNE yazar -- rapor okunamaz hale gelir, ustelik hangi
    dosyadan bahsedildigi de silinir. Ilk surumde yalnizca \\n
    temizleniyordu ve ciktida tam olarak bu olustu.
    """
    return re.sub(r"\s+", " ", str(s)).strip()[:n]


class Saglik:
    """Tarama sirasinda atlanan/dusulen seylerin sayaci."""

    def __init__(self):
        self.olaylar = defaultdict(list)

    def kaydet(self, tur: str, ayrinti: str = ""):
        self.olaylar[tur].append(ayrinti)

    def temiz(self) -> bool:
        return not self.olaylar

    def sifirla(self):
        self.olaylar.clear()

    def ozet(self) -> str:
        """Tek satirlik ozet -- betiklerin sonuna basmasi icin."""
        if not self.olaylar:
            return "kapsam: tam (atlanan/dusulen yok)"
        parcalar = [f"{t}={len(v)}" for t, v in sorted(self.olaylar.items())]
        return "kapsam UYARI: " + ", ".join(parcalar)

    def rapor(self, cikti=sys.stderr, ust=10):
        if not self.olaylar:
            print("kapsam: tam (atlanan/dusulen yok)", file=cikti)
            return
        print("\n--- KAPSAM UYARILARI ---", file=cikti)
        print("    Bunlar bulgu degil; aracin BAKAMADIGI yerler.", file=cikti)
        for tur, ayrintilar in sorted(self.olaylar.items()):
            print(f"  {tur}: {len(ayrintilar)}", file=cikti)
            for a in ayrintilar[:ust]:
                if a:
                    print(f"      {a}", file=cikti)
            kalan = len(ayrintilar) - ust
            if kalan > 0:
                print(f"      ... {kalan} tane daha", file=cikti)


SAGLIK = Saglik()


# =====================================================================
# YOLLAR
# =====================================================================
#
# Iki AYRI capa var ve karistirilmamalari gerekiyor:
#
#   KOK        -- VERI nerede. LOTM_KOK ile degistirilebilir. Depoya
#                 girmeyen ciltler, yayimlanmis bolumler, sozluk.
#   BETIK_KOK  -- KODUN kendisi nerede. Bu dosyanin yanidir.
#
# words.md koda ait bir dosya, veriye degil; bu yuzden BETIK_KOK'a
# baglidir. Eskiden "KOK/Tools/words.md" yaziyordu, yani betik klasorunun
# ADI koda gomuluydu -- klasoru yeniden adlandirmak (Tools -> scripts)
# sessizce bozuyordu. Artik betikler nereye tasinirsa words.md onlarla
# birlikte bulunur.

BETIK_KOK = Path(__file__).resolve().parent

# Varsayilan, betik klasorunun bir ustu -- calistir.sh ile AYNI kural.
# Eskiden burada ~/Projects/LotM sabitti: calistir.sh disindan calistirilan
# bir betik, depo baska yerdeyse sessizce baska bir koke bakardi.
KOK = Path(os.environ.get("LOTM_KOK") or BETIK_KOK.parent)
SITE = KOK / "Imperium34.github.io"

SOZLUK_YOLU = SITE / "_data/sozluk.yml"
BOLUMLER_TR = SITE / "_chapters"
KAYNAK_EN = KOK / "Source/LotM_Volumes"
KAYNAK_ZH = KOK / "Source/Lord_of_the_Mysteries_Chinese.txt"


# words.md betiklerle AYNI klasorde olmayabilir: betikler Scripts/'e tasindi,
# veri (words.md, Reports/, Voice_Maps/) KOK/Tools'ta kaldi. Tek sabit yol
# ikisinden birini sessizce kaciriyordu (sozluk_ara "madde listesi yok"
# diyordu). Sira: LOTM_KELIMELER, betik klasoru, KOK/Tools.
def _kelimeler_yolu() -> Path:
    if os.environ.get("LOTM_KELIMELER"):
        return Path(os.environ["LOTM_KELIMELER"])
    for aday in (BETIK_KOK / "words.md", KOK / "Tools" / "words.md"):
        if aday.exists():
            return aday
    return BETIK_KOK / "words.md"


KELIMELER = _kelimeler_yolu()


# =====================================================================
# CILT TABLOSU
# =====================================================================

# Wiki ile dogrulanmis araliklar. Cince ham metinden tespit edilen cilt
# uzunluklari bu tabloyla birebir ortusuyor (fark +0, sekizde sekiz).
# lotm_splitter.py de bu tabloyu kullanir (ayri bir kopyasi yok).
CILTLER = [
    (1, "Clown", 1, 213),
    (2, "Faceless", 214, 482),
    (3, "Traveler", 483, 732),
    (4, "Undying", 733, 946),
    (5, "Red_Priest", 947, 1150),
    (6, "Lightseeker", 1151, 1266),
    (7, "Hanged_Man", 1267, 1353),
    (8, "Fool", 1354, 1394),
]

# Ana hikaye 1394'te biter. Ingilizce metindeki 1395+ yan hikayelerdir
# (An Ordinary Person's Daily Life, In Modern Day) ve Cince ham dosyada
# YOKTUR -- eksik degil, kapsam disi. Wiki ayrica 1431-1432'de bir bonus
# bolumden (That Corner) soz ediyor; o da iki kaynakta da yok.
ANA_HIKAYE_SONU = 1394
SON_BOLUM = 1409  # Ingilizce metnin sonu (yan hikayeler dahil)

# Her kaynagin kendi beklentisi var; tek bir global sabit ucune de uymuyor.
# TR yayimlanmakta oldugu icin hicbir sona ulasmasi beklenmez.
BEKLENEN = {"ZH": ANA_HIKAYE_SONU, "EN": SON_BOLUM, "TR": None}


# =====================================================================
# METIN OKUMA
# =====================================================================


def metin_oku(yol) -> str:
    """
    Kodlamaya dayanikli okuma.

    Eski chinese_lookup.py yalnizca ILK SATIRI deneyerek karar veriyordu;
    ASCII bir satirla baslayan GBK dosyasi testi geciyor, sonra patliyordu.
    Burada dosyanin tamami denenir.

    utf-8-sig, BOM'lu ve BOM'suz UTF-8'in ikisini de cozer (Windows'tan gelen
    Cince ham metinler cogunlukla BOM'ludur). gb18030 ise GBK ve GB2312'nin
    ust kumesidir, yani tek deneme hepsini kapsar.
    """
    ham = Path(yol).read_bytes()
    for kod in ("utf-8-sig", "gb18030"):
        try:
            return ham.decode(kod)
        except UnicodeDecodeError:
            continue
    # Buraya dusmek "dosyayi okudum" degil "dosyayi TAHMIN ettim" demektir.
    # errors="replace" bozuk baytlari U+FFFD yapar; metin okunur gorunur
    # ama icindeki terim artik eslesmez. Sessiz kalirsa sonuc "terim
    # metinde yok" olur ve bu yanlistir.
    SAGLIK.kaydet("kodlama_cozulemedi", str(yol))
    return ham.decode("utf-8", errors="replace")


# =====================================================================
# DOSYA YAZMA
# =====================================================================


def atomik_yaz(yol, icerik) -> None:
    """
    Dosyayi ya tamamen yazar ya hic dokunmaz. Veri yazan HER betik bunu
    kullanir (etiketle -> sozluk.yml, sapka -> bolumler/words.md,
    bicim_denetle -> taban, takvim_ata -> bolum tarihleri).

    Duz write_text() once dosyayi bosaltir, sonra yazar: arada bir
    Ctrl-C, dolu disk ya da cokme yarim bir sozluk.yml / bolum birakir.
    Burada icerik ayni klasordeki gecici dosyaya yazilir, diske indirilir
    (fsync) ve os.replace ile tek adimda yerine konur.

      - icerik str ise UTF-8 olarak, satir sonlarina DOKUNULMADAN yazilir
        (write_text Linux'ta da \n'i oldugu gibi yaziyordu; davranis ayni).
        bytes ise oldugu gibi.
      - Var olan dosyanin izinleri korunur. mkstemp gecici dosyayi 0600
        acar; korunmazsa yazilan her bolum yalnizca sahibine okunur kalirdi.
        Yeni dosya umask'a gore olusur, write_text gibi.
      - Sembolik baglanti varsa HEDEFI yazilir, baglanti korunur.
    """
    yol = Path(os.path.realpath(yol))
    veri = icerik.encode("utf-8") if isinstance(icerik, str) else icerik
    try:
        mod = yol.stat().st_mode & 0o7777
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        mod = 0o666 & ~umask
    fd, gecici = tempfile.mkstemp(dir=yol.parent, prefix=f".{yol.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(veri)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(gecici, mod)
        os.replace(gecici, yol)
    except BaseException:
        Path(gecici).unlink(missing_ok=True)
        raise


def bulgulari_yaz(yol, kayitlar) -> None:
    """
    Bir denetimin bulgularini fark.py'nin okuyacagi TSV olarak yazar.

    kayitlar: [(anahtar, gorunum)] -- anahtar bir demet, gorunum tek satir.
    ANAHTAR KARARLI OLMALI: satir numarasi icermez (bir paragraf eklenince
    butun bulgular "yeni" gorunurdu); dosya, kural ve alinti gibi alanlardan
    olusur. Gorunum yalnizca ekranda gosterilir, karsilastirmaya girmez.

    Satir: anahtar alanlari, sekmeyle; son sutun gorunum. Ayni anahtar iki
    kez gelirse biri kalir. Sirali yazilir ki dosyanin kendisi de diff'lenebilsin.
    """

    def temiz(x) -> str:
        return re.sub(r"[\t\r\n]+", " ", str(x if x is not None else "")).strip()

    satirlar = {}
    for anahtar, gorunum in kayitlar:
        a = "\t".join(temiz(x) for x in anahtar)
        satirlar.setdefault(a, temiz(gorunum))
    Path(yol).parent.mkdir(parents=True, exist_ok=True)
    atomik_yaz(yol, "".join(f"{a}\t{g}\n" for a, g in sorted(satirlar.items())))


# =====================================================================
# CINCE SAYILAR
# =====================================================================

_CN_RAKAM = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CN_BASAMAK = {"十": 10, "百": 100, "千": 1000}


def cn_sayi(s: str):
    """
    Cince rakami tamsayiya cevirir. Arap rakamlari oldugu gibi gecer.

        一千四百零九 -> 1409
        二十        -> 20
        十          -> 10      (basinda rakam yoksa 1 varsayilir)
        279         -> 279

    Cozulemezse None doner -- boylece cagiran taraf o satiri baslik saymaz.
    Cilt ici numaralar 269'u gecmedigi icin 万 (10000) gerekmiyor.
    """
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)

    bolum = sayi = 0
    for ch in s:
        if ch in _CN_RAKAM:
            sayi = _CN_RAKAM[ch]
        elif ch in _CN_BASAMAK:
            bolum += (sayi or 1) * _CN_BASAMAK[ch]  # "十五" -> 15
            sayi = 0
        else:
            return None
    return bolum + sayi


# =====================================================================
# ETIKET AYIRMA -- "Turkce (English)" ve "A / B"
# =====================================================================

_PARANTEZ = re.compile(r"\s*\([^)]*\)")
_PARANTEZ_ICI = re.compile(r"\(([^)]*)\)")


def parantezsiz(ham) -> str:
    """'Cirak (Seer)' -> 'Cirak'"""
    return _PARANTEZ.sub("", str(ham or "")).strip()


def ingilizce_ayikla(ham):
    """'Cirak (Seer)' -> 'Seer'. Parantez yoksa None."""
    m = _PARANTEZ_ICI.search(str(ham or ""))
    return m.group(1).strip() if m else None


def etiket_temizle(ham) -> list:
    """
    Bir etiketi aranabilir stringlere cevirir. Parantez DISI kisim birincil
    ad, parantez ici ek aday; slash ile ayrilanlar da bolunur.

        'Blasphemer Amon (King of Angels)' -> ['Blasphemer Amon', 'King of Angels']
        'Historical Void / Fog of History' -> ['Historical Void', 'Fog of History']
    """
    if not ham:
        return []
    ham = str(ham)
    parcalar = [_PARANTEZ_ICI.sub(" ", ham)]
    parcalar += _PARANTEZ_ICI.findall(ham)

    sonuc = []
    for p in parcalar:
        for alt in p.split("/"):
            alt = re.sub(r"\s+", " ", alt).strip(" .,;:-")
            if alt:
                sonuc.append(alt)
    return sonuc


def varyantlar(terim: str) -> set:
    """Yazim varyantlari: tire / bosluk / bitisik, ve bas artikeli."""
    v = {terim}
    if "-" in terim:
        v.add(terim.replace("-", " "))
        v.add(terim.replace("-", ""))
    if " " in terim:
        kelimeler = terim.split()
        if len(kelimeler) == 2:
            v.add("".join(kelimeler))
            v.add("-".join(kelimeler))
    if terim.startswith("The "):
        v.add(terim[4:])
    return {x for x in v if len(x) >= 3}


# =====================================================================
# TURKCE CEKIM EKLERI
# =====================================================================
#
# yayim_denetle.py'den tasindi. Turkce terimler metinde cekim ekleriyle gecer
# ("Kâhin'in", "Yolda", "Gizem Avcısı'nı"), dolayisiyla duz altdize aramasi
# ise yaramaz. Ama serbest bir "\w{0,12}" de olmaz: v1'de tam olarak o
# yuzden Haz -> Haziran, Bard -> bardak esleiyordu. Yalnizca gercek isim
# cekim ekleri kabul edilir.

COGUL = r"(?:ler|lar)"
# UNLUYLE BITEN GOVDELER. Cogul iyelik ekleri unluyle biten bir govdeye
# gelirken bas unlulerini kaybeder:
#     Kapı  + mız -> Kapımız      (Kapıımız degil)
#     Diyar + ımız -> Diyarımız
# Eskiden yalnizca ikinci bicim (imiz/ımız/...) vardi, yani unluyle biten
# HER terim cogul iyelikte sessizce eslesmiyordu -- "Kapımız", "Diyarınız"
# gibi kullanimlar taramada hic gorunmuyordu. Tekil bicimler (m, n, si)
# zaten listedeydi, o yuzden hata yalnizca cogulda ortaya cikiyordu.
IYELIK = (
    r"(?:imiz|ımız|umuz|ümüz|iniz|ınız|unuz|ünüz|leri|ları"
    r"|miz|mız|muz|müz|niz|nız|nuz|nüz"
    r"|siz|sız|suz|süz|si|sı|su|sü|im|ım|um|üm|in|ın|un|ün|i|ı|u|ü|m|n)"
)

HAL = (
    r"(?:nden|ndan|nde|nda|nin|nın|nun|nün|den|dan|ten|tan|de|da|te|ta"
    r"|yle|yla|ile|le|la|ni|nı|nu|nü|ne|na|yi|yı|yu|yü|ye|ya"
    r"|in|ın|un|ün|i|ı|u|ü|e|a)"
)

# EK-FİİL. Unluyle biten govdeden sonra kaynastirma "y" alir: üyesi + (y)di
# -> "üyesiydi", üye + (y)ken -> "üyeyken". Eskiden y'li bicimler, kisi
# ekleri (-ydim, -ymişsin) ve -(y)sA / -(y)ken yoktu; "Babam Gece
# Şahinleri'nin bir aslî üyesiydi" terimi iceriyor ama eslesmiyordu.
EKFIIL = (
    r"(?:y?[dt][ıiuü](?:m|n|k|n[ıiuü]z|l[ae]r)?"  # -(y)DI + kişi
    r"|y?m[ıiuü]ş(?:[ıiuü]m|s[ıiuü]n|[ıiuü]z|l[ae]r)?"  # -(y)mIş + kişi
    r"|y?s[ae](?:m|n|k|n[ıiuü]z|l[ae]r)?"  # -(y)sA + kişi
    r"|y?[ıiuü][mz]"  # -(y)Im / -(y)Iz
    r"|s[ıiuü]n(?:[ıiuü]z)?"  # -sIn / -sInIz
    r"|[dt][ıiuü]r(?:l[ae]r)?"  # -DIr
    r"|y?ken)"  # -(y)ken
)

SIFAT = r"(?:l[iıuü])?"  # -li / -lı / -lu / -lü
HAL_ILGI = r"(?:" + HAL + r"(?:ki)?)?"

# Kesme hem govdeden hemen sonra (Kâhin'in) hem iyelikten sonra
# (Diyarı'nı) gelebilir. Sondaki (?![\w]) sart: eksiz de olsa eslesme
# kelime sonunda bitmeli. Yoksa Haz -> Haz|iran, Zanaatkâr -> Zanaatkâr|lık
# gibi kirpik eslesmeler gecerli sayilir.
KESME = r"(?:['\u2019])?"
EK = (
    KESME
    + COGUL
    + r"?"
    + SIFAT
    + IYELIK
    + r"?"
    + KESME
    + HAL_ILGI
    + EKFIIL
    + r"?"
    + r"(?![^\W_])"
)
# Son sert unsuz yumusamasi
YUMUSAMA = {"k": "[kğ]", "p": "[pb]", "t": "[td]", "ç": "[çc]"}


# tr_kucult / tr_buyut artik turkce.py'de; yukarida ice aktarilip buradan
# disa veriliyor, yani lotm.tr_kucult cagiran her yer degismeden calisir.


# Tamlama coguluna donuste sesli harf oncesi yumusamis unsuzun sert hali.
# Sinif olarak yazilir ([pb]), yalniz sert degil: "ad -> adı -> adlar" gibi
# hic yumusamayan kokler de var ve bu denetleyicinin isi imla degil.
SERTLESME = {"b": "[pb]", "c": "[çc]", "d": "[td]", "ğ": "[kğ]"}
_UNLU = "aeıioöuüâîû"


# ÜNLÜ DÜŞMESİ. Ünlüyle başlayan ek gelince son hecenin dar ünlüsü düşer:
# mühür -> mühre, mührü; şehir -> şehri; kayıt -> kaydı. KAPALI LİSTE:
# düşmeyenler de çok ("kurum -> kurumu") ve kurala bağlanamaz; genel bir
# kural "kurum" terimini "kurma" ile eşleştirirdi. Sözlüğe yeni bir terim
# girip bölümde düşmüş biçimi kaçırırsa kelime buraya eklenir.
DUSEN = frozenset(
    {
        "ağız",
        "akıl",
        "akis",
        "alın",
        "asıl",
        "azim",
        "beniz",
        "beyin",
        "boyun",
        "burun",
        "cisim",
        "emir",
        "fasıl",
        "fetih",
        "fikir",
        "gönül",
        "göğüs",
        "hapis",
        "hatır",
        "hüküm",
        "hüzün",
        "ilim",
        "isim",
        "kabir",
        "kahır",
        "karın",
        "kayıp",
        "kayıt",
        "keşif",
        "kısım",
        "metin",
        "mühür",
        "nehir",
        "nesil",
        "oğul",
        "ömür",
        "resim",
        "sabır",
        "şehir",
        "şekil",
        "vakit",
        "zehir",
        "zihin",
    }
)
_DUSMUS = {w[:-2] + w[-1]: w for w in DUSEN}  # "mühr" -> "mühür"
_SOFT = {"t": "d", "p": "b", "k": "ğ", "ç": "c"}


def _dusmus_desen(kelime: str) -> str | None:
    """'mühür' -> 'mühr' (ardindan unlu gelmeli); 'kayıt' -> 'kay[td]'."""
    if tr_kucult(kelime) not in DUSEN:
        return None
    kok = kelime[:-2] + kelime[-1]
    if kok[-1] in YUMUSAMA:
        return re.escape(kok[:-1]) + YUMUSAMA[kok[-1]]
    return re.escape(kok)


def _dusmusu_geri(kok: str) -> str | None:
    """Iyelik atildiktan sonra kalan 'Şehr' / 'kayd' -> 'Şehir' / 'kayıt'."""
    k = tr_kucult(kok)
    for d, tam in _DUSMUS.items():
        if k == d or (d[-1] in _SOFT and k == d[:-1] + _SOFT[d[-1]]):
            return kok[:-1] + tam[-2] + tam[-1]
    return None


def _tamlama_koku(kelime: str) -> str | None:
    """
    Belirtisiz tamlamanin son kelimesinden 3. tekil iyelik ekini atar;
    kalan kokun desenini, ek yoksa None doner.

        mektebi -> mekte[pb]     (mektep + i, p yumusamis)
        lambası -> lamba         (lamba + sı)
        saati   -> saat          (saat + i)

    Cogulda ek, cogul ekinden SONRA gelir: pazar mektebi -> pazar
    mektep-ler-i. Terim eki zaten tasidigi icin EK deseni "mektebi"
    arkasina "leri" ekleyip hic bulamiyordu; "pazar mektepleri", "gaz
    lambaları", "cep saatleri" eslesmeyen sayiliyordu.
    """
    k = kelime
    if len(k) < 3 or k[-1] not in "ıiuü":
        return None
    if k[-2] == "s" and len(k) > 3 and k[-3] in _UNLU:
        return re.escape(k[:-2])
    kok = k[:-1]
    if kok[-1] in _UNLU:
        return None
    # "Rüzgâr Şehri" -> "Şehirleri": dusen unlu cogulda geri gelir.
    tam = _dusmusu_geri(kok)
    if tam:
        return re.escape(tam)
    if kok[-1] in SERTLESME:
        return re.escape(kok[:-1]) + SERTLESME[kok[-1]]
    return re.escape(kok)


_HAFIF_FIILLER = {
    "etmek",
    "edilmek",
    "eylemek",
    "olmak",
    "olunmak",
    "kılmak",
    "kılınmak",
}


def _fiil_koku(kelime: str, cok_kelimeli: bool) -> str | None:
    """
    Mastar halindeki fiil terimi icin govde deseni: 'tevdi etmek' -> 'e[td]…'.

    Terim mastarla yazilir ama metinde cekimli gecer: tevdi etti, tevdi
    ettiği, tevdi edildi. EK deseni "etmek"in ARKASINA ek bekledigi icin
    bunlarin hicbirini bulmuyordu (sozlukte "Şirazesini Yitirmek" icin
    arama_adi: [şiraze] tam da bu yuzden yazilmisti).

    Yalnizca guvenli oldugu yerde: kok en az dort harf olmali (damgala-,
    görül-, yitir-). "ekmek", "yemek", "parmak", "çakmak" isimdir ve
    kokleri (ek-, ye-, par-, çak-) her yere eslesirdi. Kisa koklu hafif
    fiiller (et-, ol-, kıl-) yalnizca cok kelimeli terimin sonunda kabul
    edilir; orada onlerindeki kelime baglami zaten daraltir.
    """
    if not re.search(r"m[ae]k$", kelime):
        return None
    kok = kelime[:-3]
    if len(kok) < 4 and not (cok_kelimeli and kelime in _HAFIF_FIILLER):
        return None
    if kok[-1] in YUMUSAMA:
        return re.escape(kok[:-1]) + YUMUSAMA[kok[-1]] + r"[^\W\d_]*"
    return re.escape(kok) + r"[^\W\d_]*"


# OLCU EKI -lIk. "altı librelik top", "iki yüz Sterlinlik ücret": sayidan
# sonra gelen birim -lIk alir. Her terime acilamaz: "İmparator" ->
# "İmparatorluk", "Aşkın" -> "Aşkınlık" baska kelimelerdir. Bu yuzden
# yalnizca ONUNDE SAYI varken kabul edilir (rakam ya da sayi sozcugu).
# Python'un lookbehind'i sabit genislik ister; her sozcuk ayri bir
# lookbehind olur ve alternatifle baglanir.
SAYI_SOZCUKLERI = (
    "bir",
    "iki",
    "üç",
    "dört",
    "beş",
    "altı",
    "yedi",
    "sekiz",
    "dokuz",
    "on",
    "yirmi",
    "otuz",
    "kırk",
    "elli",
    "altmış",
    "yetmiş",
    "seksen",
    "doksan",
    "yüz",
    "bin",
    "milyon",
    "yarım",
    "çeyrek",
    "buçuk",
    "birkaç",
    "kaç",
)
_SAYI_ONCESI = (
    "(?:"
    + "|".join(
        [r"(?<=\d\s)", r"(?<=\d)"]
        + [rf"(?<=(?<![^\W_]){re.escape(w)}\s)" for w in SAYI_SOZCUKLERI]
        + [rf"(?<=(?<![^\W_]){re.escape(tr_buyut(w))}\s)" for w in SAYI_SOZCUKLERI]
    )
    + ")"
)
OLCU_EKI = r"l[iıuü][kğ]"


def _govde(terim: str, olcu: bool = False) -> str:
    parcalar = []
    kelimeler = terim.split()
    son = len(kelimeler) - 1
    for i, kelime in enumerate(kelimeler):
        g = re.escape(kelime)
        if kelime and kelime[-1] in YUMUSAMA:
            g = re.escape(kelime[:-1]) + YUMUSAMA[kelime[-1]]
        if i < son:
            parcalar.append(g + r"(?![^\W_])")
            continue
        if olcu:
            # yalnizca -lIk'li bicim; cagiran (desen_kur) sayi sartini koyar
            parcalar.append(g + OLCU_EKI + EK)
            continue
        g += EK
        # Yalnizca cok kelimeli terimlerde: tek kelimede sondaki -i cogu
        # zaman kokun kendisidir (idadi, Kabine degil ama benzerleri).
        kok = _tamlama_koku(kelime) if son > 0 else None
        if kok:
            g = f"(?:{g}|{kok}l[ae]r{EK})"
        fiil = _fiil_koku(kelime, son > 0)
        if fiil:
            g = f"(?:{g}|{fiil})"
        dusmus = _dusmus_desen(kelime)
        if dusmus:
            g = f"(?:{g}|{dusmus}(?=[{_UNLU}]){EK})"
        parcalar.append(g)
    return r"\s+".join(parcalar)


@functools.lru_cache(maxsize=None)
def desen_kur(terim: str, harf_duyarli: bool = True):
    """
    Turkce bir terim icin cekim eklerine dayanikli desen (bkz. EK, _govde).

    Harf duyarliligi VARSAYILAN olarak aciktir ve oyle kalmalidir: Mertebe
    adlari ozel isimdir, cakismalari kucuk harflidir (Yol/yolu, Haz/hazine,
    Maraz/marazi, San/sansli).

    HARF DUYARSIZ DALDA re.IGNORECASE KULLANILMAZ (bkz. turkce.py, 3.
    tuzak): ı ile i ayni sinifa duser ve "Ayin" deseni "ayının"i bulur.
    Bunun yerine terimin kucuk ve bas harfi buyuk bicimleri ACIKCA uretilip
    alternatif olarak baglanir.

    Sonuc onbellege alinir: ayni terim her bolum icin yeniden derlenmez.
    """
    bicimler = (
        [terim]
        if harf_duyarli
        else list(dict.fromkeys([terim, tr_kucult(terim), tr_buyut(tr_kucult(terim))]))
    )
    secenekler = [_govde(b) for b in bicimler]

    # Olcu bicimi (bkz. OLCU_EKI): sayi on-kosulu bir kez yazilir, uc harf
    # bicimi onun arkasinda alternatif olur. Eskiden her bicim kendi
    # ~60 lookbehind'ini tasiyordu.
    #
    # Basta bir ILERI BAKIS var: lookbehind'lar ancak terimin kendisi o
    # konumda basliyorsa denenir. Yoksa alternatif bir lookbehind'la
    # basladigi icin motor metindeki HER konumda ~54 lookbehind calistirir
    # ve harf onekiyle ileri atlayamaz. yayim_denetle'nin 2 dakikasinin
    # cogu buydu; ileri bakisla ayni eslesmeler ~9 kat hizli.
    olcu = "(?:" + "|".join(_govde(b, olcu=True) for b in bicimler) + ")"
    secenekler.append(f"(?={olcu})" + _SAYI_ONCESI + olcu)

    kalip = r"(?<![^\W_])(?:" + "|".join(secenekler) + r")"
    return re.compile(kalip)


# =====================================================================
# SOZLUK
# =====================================================================


@dataclass
class Terim:
    """
    Sozlukteki tek bir terim -- ust duzey girdi ya da bir mertebe.

    IKI AYRI BOLUM NUMARASI, KARISTIRILMAMALI
    -----------------------------------------
    bolum_siniri  EDITORYAL KAPI. Terimin ACIKLANDIGI, yani okuyucunun
                  anlayabilecegi bolum. Cevirmen karari; arac ASLA
                  uzerine yazmaz. Bir ad aciklanmadan once anilabilir,
                  bu yuzden kapi ilk gecisten sonra gelir.
    ilk_gecis     TURETILEN. Adin Ingilizce metinde ilk gectigi bolum.
                  kapi_denetle.py bulur, etiketle.py yazar, her calistirmada
                  serbestce guncellenir.

    Ikisi arasindaki aralik anlamlidir: orada ad GECER ama HENUZ
    ACIKLANMAMISTIR. O aralikta Turkce metnin adi kullanmasi sadakattir,
    spoiler degil -- yayim_denetle bu ayrimi bu iki alanla yapar.

    Iki YAML sekli tek kayda indirgenir:
      ust duzey:  terim: X / ingilizce: Y      (ayri alanlar)
      mertebe:    isim: "X (Y)"                (tek alanda gomulu)

    ham: ruamel ile yuklendiyse CANLI referanstir. etiketle.py bunun uzerine
    yazip dosyayi bicimi bozulmadan geri kaydedebilir.
    """

    tr: str
    en: str | None = None
    en_ham: str | None = None  # ayrilmamis Ingilizce etiket (bkz. arama_adaylari)
    zh: str | None = None
    # Tek karakterlik Cince anahtar KASITLI mi? Varsayilan olarak tek karakter
    # aranmaz (法 魔法'in, 令 命令'in icinde gecer). Sozlukte ya da words.md'de
    # 「镑」 gibi kose parantezle yazilan karakter kasitlidir ve aranir.
    zh_kesin: bool = False
    kategori: str = ""
    yol: str | None = None  # bagli oldugu Yol (mertebeler icin)
    yol_en: str | None = None
    seviye: int | None = None
    bolum_siniri: int | None = None  # EDITORYAL kapi -- insan koyar
    ilk_gecis: int | None = None  # TURETILEN ilk gecis -- arac yazar
    eski_karsiliklar: list = field(default_factory=list)
    # IKI AYRI ALAN, IKI AYRI DIL. Eskiden tek 'arama_adi' vardi ve iki
    # betik onu iki ayri seyle okuyordu: toplu_denetle TURKCE karsilik
    # bicimleri olarak, arama_adaylari() (-> kapi_denetle) INGILIZCE arama
    # adi olarak. Sozlukteki butun kullanimlar Turkceydi ("gökkubbe",
    # "şiraze", "El Yazması"); yani kapi_denetle bu uc terimin ilk gecisini
    # Ingilizce metinde Turkce kelime arayarak bulmaya calisiyordu.
    arama_adi: list = field(default_factory=list)  # TURKCE karsilik bicimleri
    en_arama_adi: list = field(default_factory=list)  # INGILIZCE tarama adlari
    cevirmen_notu: str | None = None
    kardesler_tr: list = field(default_factory=list)
    kardesler_en: list = field(default_factory=list)
    ham: dict | None = None

    @property
    def mertebe_mi(self) -> bool:
        return self.yol is not None

    @property
    def tek_kelime(self) -> bool:
        return len(self.tr.split()) == 1

    @property
    def yer(self) -> str:
        """Rapor icin okunabilir konum."""
        if self.mertebe_mi:
            return f"{self.yol} S{self.seviye}"
        return self.kategori or "ust duzey"

    @property
    def anahtar(self) -> str | None:
        """
        Raporlarda ve betikler arasinda terimi tanimlayan KARARLI kimlik.

        Her zaman kanonik Ingilizce addir -- arama_adi DEGIL. Eskiden
        kapi_denetle.py raporu arama_adi[0] ile anahtarliyor, etiketle.py ise
        parantez icindeki adla ariyordu; arama_adi verilmis her terim
        sessizce eslesmiyordu ("raporda yok" sayilip etiketlenmiyordu).
        """
        return self.en or None

    def tr_bicimleri(self) -> list:
        """
        Terimin GUNCEL Turkce karsilik bicimleri: once terimin kendisi,
        sonra arama_adi; harf duyarsiz tekillestirilmis, sira korunur.

        Iki denetleyici bunu eskiden farkli kuruyordu: toplu_denetle
        "arama_adi verilmisse YALNIZCA o" diyordu (terimin kendisini
        listeye yazmayi unutmak tuzakti), ceviri_denetle ise arama_adi'yi
        hic okumuyordu. Ayni terim bir aracta temiz, digerinde eslesmeyen
        cikiyordu ("El Yazması" kisaltmasi gibi).
        """
        out, gorulen = [], set()
        for b in [self.tr, *self.arama_adi]:
            if b and tr_kucult(b) not in gorulen:
                gorulen.add(tr_kucult(b))
                out.append(b)
        return out

    def arama_adaylari(self) -> list:
        """
        Ingilizce tarama icin aday stringler, uzundan kisaya.
        en_arama_adi verilmisse yalnizca o kullanilir. (arama_adi DEGIL:
        o alan Turkce karsilik bicimleridir, bkz. alan notu.)

        en_ham uzerinden calisir, en uzerinden degil: 'en' cok adli
        etiketlerde ilk ada indirgenmistir ("Mystery Pryer / Pugilist" ->
        "Mystery Pryer"), ama tarama ikinci adi da gormeli. Ayni sekilde
        ust duzey girdilerde parantez ici ad ("Blasphemer Amon (King of
        Angels)" -> "King of Angels") yalnizca en_ham'da vardir.
        """
        if self.en_arama_adi:
            kaynak = list(self.en_arama_adi)
        elif self.en_ham or self.en:
            kaynak = etiket_temizle(self.en_ham or self.en)
        else:
            return []
        tum = set()
        for a in kaynak:
            tum |= varyantlar(a)
        return sorted(tum, key=lambda s: (-len(s), s))


# Eski ad. Burada ikinci bir tanim vardi (lower() ile) ve yukaridaki
# tr_kucult'tan (casefold() ile) farkli yazilmisti; ciktilari Turkce icin
# ayni olsa da iki tanim iki ayri gelecek demekti. Artik ayni fonksiyon.
_tr_kucult = tr_kucult


class Sozluk:
    """Yuklenmis sozluk: Terim kayitlari + ham YAML agaci."""

    def __init__(self, terimler, veri, _yaml=None, _yol=None):
        self.terimler = terimler
        self.veri = veri
        self._yaml = _yaml
        self._yol = _yol

    def __len__(self):
        return len(self.terimler)

    def __iter__(self):
        return iter(self.terimler)

    def ara(self, sorgu: str) -> list:
        """Iki yonlu arama: Turkce, Ingilizce veya Cince tarafinda."""
        # Turkce alan Turkce kucultmeyle, Ingilizce alan casefold ile. Tek
        # bir kucultme ikisine birden uygulaninca Ingilizce bozuluyordu:
        # tr_kucult("Iron Cross") = "ıron cross", yazilan "iron" bulunmuyordu.
        #
        # Turkce tarafta eski_karsiliklar ve arama_adi da aranir: "ritüel"
        # ya da "Rumuzcu" aramak, onlarin YERINE gecen terimi bulmali.
        # Eskiden yalnizca guncel ad aranirdi ve terk edilmis bir bicim
        # "eslesme yok" cikiyordu -- sanki hic karar verilmemis gibi.
        q_tr, q_en = tr_kucult(sorgu), en_kucult(sorgu)
        return [
            t
            for t in self.terimler
            if any(q_tr in tr_kucult(b) for b in [t.tr, *t.arama_adi, *t.eski_karsiliklar])
            or q_en in en_kucult(t.en)
            or sorgu in (t.zh or "")
        ]

    def yaz(self, hedef=None, duzeltici=None, dogrulayici=None) -> str:
        """
        Ham agaci geri yazar (atomik_yaz ile) ve yazilan metni doner.
        Yalnizca bicim_koru=True ile yuklendiyse calisir -- PyYAML'in dump'i
        yorumlari siler, anahtarlari siralar ve uzun dizeleri sarar, yani
        diff okunamaz hale gelir.

        duzeltici: dump edilmis metni alip duzeltilmisini donen bir islev.
        ruamel'in bos satir ve girinti davranisini toparlamak icin gerekir
        (bkz. etiketle.bosluk_duzelt); o duzeltme sozluk.yml'in kendi
        bicimine ozgu oldugu icin burada degil, cagiran tarafta durur.

        dogrulayici: son metni alip sorun varsa aciklamasini, yoksa None
        donen bir islev. Sorun varsa YazmaReddedildi firlatilir ve dosyaya
        hic dokunulmaz (bkz. etiketle.dogrula).
        """
        if self._yaml is None:
            raise RuntimeError(
                "yaz() icin sozluk_yukle(bicim_koru=True) ile yuklenmeli"
            )
        import io

        tampon = io.StringIO()
        self._yaml.dump(self.veri, tampon)
        metin = tampon.getvalue()
        if duzeltici:
            metin = duzeltici(metin)
        if dogrulayici:
            hata = dogrulayici(metin)
            if hata:
                raise YazmaReddedildi(hata)
        atomik_yaz(hedef or self._yol, metin)
        return metin


class YazmaReddedildi(ValueError):
    """Sozluk.yaz: dogrulayici uretilen metni reddetti; hicbir sey yazilmadi."""


def _terim_kur(ham_girdi, ham_mertebe=None, kardesler=None, kardesler_en=None):
    """
    Tek bir YAML dugumunden Terim uretir. kardesler / kardesler_en: ayni
    Yol'daki mertebelerin Turkce / Ingilizce adlari (terimin kendisi haric).
    """
    kardesler = kardesler or []
    kardesler_en = kardesler_en or []

    if ham_mertebe is not None:
        isim = str(ham_mertebe.get("isim", ""))
        tr = parantezsiz(isim)
        if not tr:
            return None
        en_ham = ingilizce_ayikla(isim)
        # cok adli mertebelerde ilk ad esas alinir
        en = en_ham.split("/")[0].strip() if en_ham else None
        kendi_en = {x.strip() for x in (en_ham or "").split("/")}
        yol_en_list = etiket_temizle(ham_girdi.get("ingilizce", ""))
        return Terim(
            tr=tr,
            en=en,
            en_ham=en_ham,
            zh=zh_ayikla(ham_mertebe.get("cince"))[0],
            zh_kesin=zh_ayikla(ham_mertebe.get("cince"))[1],
            kategori=ham_girdi.get("kategori", ""),
            yol=ham_girdi.get("terim"),
            yol_en=yol_en_list[0] if yol_en_list else None,
            seviye=ham_mertebe.get("seviye"),
            bolum_siniri=ham_mertebe.get("bolum_siniri"),
            ilk_gecis=ham_mertebe.get("ilk_gecis"),
            eski_karsiliklar=list(ham_mertebe.get("eski_karsiliklar") or []),
            arama_adi=list(ham_mertebe.get("arama_adi") or []),
            en_arama_adi=list(ham_mertebe.get("en_arama_adi") or []),
            cevirmen_notu=ham_mertebe.get("cevirmen_notu"),
            kardesler_tr=[k for k in kardesler if k != tr],
            # Cok adli mertebenin ("Mystery Pryer / Pugilist") butun adlari
            # haric tutulur. Eskiden hep bos kaliyordu ve kapi_denetle
            # Ingilizce metinde Turkce kardes adlarini ariyordu.
            kardesler_en=[k for k in kardesler_en if k not in kendi_en],
            ham=ham_mertebe,
        )

    tr = parantezsiz(ham_girdi.get("terim"))
    if not tr:
        return None
    return Terim(
        tr=tr,
        en=parantezsiz(ham_girdi.get("ingilizce")) or None,
        en_ham=str(ham_girdi.get("ingilizce") or "") or None,
        zh=zh_ayikla(ham_girdi.get("cince"))[0],
        zh_kesin=zh_ayikla(ham_girdi.get("cince"))[1],
        kategori=ham_girdi.get("kategori", ""),
        bolum_siniri=ham_girdi.get("bolum_siniri"),
        ilk_gecis=ham_girdi.get("ilk_gecis"),
        eski_karsiliklar=list(ham_girdi.get("eski_karsiliklar") or []),
        arama_adi=list(ham_girdi.get("arama_adi") or []),
        en_arama_adi=list(ham_girdi.get("en_arama_adi") or []),
        cevirmen_notu=ham_girdi.get("cevirmen_notu"),
        ham=ham_girdi,
    )


def gecis_bolumu(terim) -> int | None:
    """
    Eski karsiliklarin GECIS bolumu: terimin bolum_siniri.

    Kapidan once yeni ad henuz acilmamistir; o bolgede eski bicim (Ayin
    icin "ritüel") o donemin dogru kelimesidir. Kapidan itibaren eski bicim
    eskimistir. Ters yon (yeni ad kapidan once) yayim_denetle'de 'erken
    yeni bicim' olarak ayrica raporlanir.

    Gercek bir kapi bildirmeyen degerler (yok, 0, >= SON_BOLUM) gecis
    sayilmaz: o terimin eski bicimi HER bolumde eskimistir. Aksi hâlde
    "seri bitmeden acilmaz" isaretli bir terimin eski bicimi hic
    raporlanmazdi.

    Eskiden bu bilgi lint-kurallari.yml'de 'ogrenme_bolumu' olarak da
    duruyordu ve ayni karar iki dosyada iki sayiyla tutulabiliyordu. Tek
    kaynak sozluk.yml; yayim_denetle, toplu_denetle ve belge_denetle bunu
    kullanir.
    """
    esik = getattr(terim, "bolum_siniri", None) or 0
    return esik if 0 < esik < SON_BOLUM else None


# --------------------------------------------------------------- words.md

_KELIME_MADDE = re.compile(r"^\s*-\s*\*\*(.+?)\*\*\s*[—–-]\s*(.*?)\s*$")
_MD_BASLIK = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_CJK = re.compile(r"[\u3400-\u9fff]+")
# Ad ayiricisi (·, ・) yalnizca iki CJK harfinin ARASINDAYSA korunur.
_ZH_AD = re.compile(r"[\u3400-\u9fff](?:[\u3400-\u9fff·・]*[\u3400-\u9fff])?")
_TR_OZEL = re.compile(r"[çğıöşüÇĞİÖŞÜâîûÂÎÛ]")
_PARANTEZ_BLOK = re.compile(r"\(([^()]*)\)")
KELIME_KATEGORI = "words.md"
_YAML_YUKLEYICI = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def yaml_yukle(akis):
    return yaml.load(akis, Loader=_YAML_YUKLEYICI)


def zh_desen(sorgu: str, bilesikler=()) -> re.Pattern:
    """
    Cince sorgu, ama daha uzun bir bilesigin PARCASI oldugu yerde degil:
    灵体 araninca 星灵体'nin icindekiler sayilmaz. Her bilesikteki her konum
    bir negatif ileri bakisa donusur: 星灵体 -> (?!(?<=星)灵体). Duz bir
    derlenmis desen olarak kalir (.search / .sub / .finditer calisir).
    ceviri_denetle ve capa ayni desenle arar.
    """
    haric = []
    for b in bilesikler:
        bas = 0
        while (i := b.find(sorgu, bas)) != -1:
            on, son = b[:i], b[i + len(sorgu) :]
            ic = re.escape(sorgu + son)
            haric.append(f"(?!(?<={re.escape(on)}){ic})" if on else f"(?!{ic})")
            bas = i + 1
    return re.compile("".join(haric) + re.escape(sorgu))


_KOSE = re.compile(r"「([^」]+)」")


def zh_ayikla(ham) -> tuple:
    """
    'cince' degeri ya da words.md parantezi -> (anahtar, kesin_mi).

        "印章/盖章"      -> ("印章/盖章", False)
        "「镑」"          -> ("镑", True)     tek karakter, kasitli
    """
    if not ham:
        return None, False
    ham = str(ham)
    kesin = bool(_KOSE.search(ham))
    temiz = _KOSE.sub(lambda m: m.group(1), ham).strip()
    return (temiz or None), kesin


def _parcala(s: str) -> list:
    return [p.strip() for p in re.split(r"\s*[/,]\s*", s) if p.strip()]


def _madde_zh(kalan: str) -> list:
    """
    Cince karsiliklar: CJK iceren ILK parantezin '/' ile ayrilmis
    parcalari, her biri (anahtar, kesin_mi) olarak; parantez yoksa
    satirdaki ilk CJK dizisi. 'Negan Dükü (尼根公爵). eşi Della
    Hanımefendi (黛拉夫人)' -> 尼根公爵; ikincisi baska bir kisidir.

        "(「镑」/苏勒/便士)"  -> [("镑", True), ("苏勒", False), ("便士", False)]
    """
    for ic in _PARANTEZ_BLOK.findall(kalan):
        if not _CJK.search(ic):
            continue
        # Karsiliklar ilk ';' oncesindedir; sonrasi Turkce nottur. Iki eski
        # hata burada: (1) yalniz '/' ayiriciydi, oysa cok terimli maddeler
        # virgulle yaziliyor ("(褐星, 绯星, 蓝星; ...)"); tek parca sayilip
        # uc gezegen de Cince anahtarsiz kaliyordu. (2) Parcadaki CJK
        # harfleri birlestirilirken ad ayiricisi '·' atiliyordu:
        # 罗塞尔·古斯塔夫 -> 罗塞尔古斯塔夫, metinde hic gecmeyen bir dize.
        bas = re.split(r"[;；]", ic, maxsplit=1)[0]
        if not _CJK.search(bas):
            bas = ic
        out = []
        for parca in re.split(r"[/,，、]", bas):
            kesin = bool(_KOSE.search(parca))
            cjk = "".join(_ZH_AD.findall(parca))
            if cjk:
                out.append((cjk, kesin))
        return out
    m = _CJK.search(kalan)
    return [(m.group(), False)] if m else []


def _madde_en(kalan: str) -> list:
    """Ingilizce karsilik(lar): ilk '(' ya da ';' oncesi. Turkce harf ya da
    CJK iceriyorsa Ingilizce degildir (orn. 'kadim bir kaynak metin')."""
    bas = re.split(r"[(;]", kalan, maxsplit=1)[0].strip().strip('"“”')
    # Parca parca bakilir: "spirit body, varlık anlamında" -> ilk parca
    # Ingilizce, ikincisi Turkce aciklama. Ilk Turkce parcada durulur.
    out = []
    for p in _parcala(bas):
        if _CJK.search(p) or _TR_OZEL.search(p):
            break
        out.append(p.strip('"“”'))
    return out


def kelimeler_yukle(yol=None) -> list:
    """
    words.md'deki "- **Türkçe** — English (中文) ; not" maddelerini Terim'e
    cevirir. Numarali satirlar (Dondurulmus Satirlar) ve kalin baslikli
    aciklama satirlari ("**Epochs:** ...") madde degildir, atlanir.

    Birden cok bicim:
      "Başak, Yengeç, Akrep — Virgo, Cancer, Scorpio"   sayilar esit: ayri
                                                        terimler, sirayla
      "damga / damgalamak — stamp"                      esit degil: tek terim,
                                                        ikincisi arama_adi
    kategori "words.md › <bolum basligi>"dir; harf_duyarli_mi icin
    'Temel Kavramlar' degildir, yani Ingilizce arama harf duyarlidir.
    """
    yol = Path(yol) if yol else KELIMELER
    if not yol.exists():
        return []
    out, bolum = [], ""
    for satir in yol.read_text(encoding="utf-8").splitlines():
        h = _MD_BASLIK.match(satir)
        if h:
            bolum = h.group(2)
            continue
        m = _KELIME_MADDE.match(satir)
        if not m:
            continue
        kalin, kalan = m.group(1).strip(), m.group(2)
        # Iki nokta ile BITEN madde kendisinden sonraki listenin basligidir
        # ("Şans artırma ayini çağrısı — 福生玄黄…, four steps:"), terim
        # degil; metinde o ad degil, altindaki satirlar gecer.
        if not kalan or kalin.endswith(":") or kalan.rstrip().endswith(":"):
            continue
        tr_list = _parcala(_PARANTEZ_BLOK.sub("", kalin))
        if not tr_list:
            continue
        en_list = _madde_en(kalan)
        zh_list = _madde_zh(kalan)
        zh = "/".join(z for z, _k in zh_list) or None
        zh_kesin = any(k for _z, k in zh_list)
        kategori = f"{KELIME_KATEGORI} › {bolum}" if bolum else KELIME_KATEGORI
        if len(tr_list) > 1 and len(en_list) == len(tr_list):
            # Cince de ayni sayidaysa sirayla eslenir ("(「镑」/苏勒/便士)").
            eslesir = len(zh_list) == len(tr_list)
            for i, (tr, en) in enumerate(zip(tr_list, en_list)):
                out.append(
                    Terim(
                        tr=tr,
                        en=en,
                        en_ham=en,
                        zh=zh_list[i][0] if eslesir else None,
                        zh_kesin=zh_list[i][1] if eslesir else False,
                        kategori=kategori,
                        cevirmen_notu=kalan,
                    )
                )
        else:
            en = en_list[0] if en_list else None
            out.append(
                Terim(
                    tr=tr_list[0],
                    en=en,
                    en_ham=en,
                    zh=zh,
                    zh_kesin=zh_kesin,
                    kategori=kategori,
                    arama_adi=tr_list[1:],
                    cevirmen_notu=kalan,
                )
            )
    return out


def sozluk_yukle(yol=None, bicim_koru=False, kelimeler=False) -> Sozluk:
    """
    sozluk.yml'i yukler.

    kelimeler=True (ya da bir yol) ise words.md maddeleri de eklenir.
    Yalnizca OKUYAN denetleyiciler icin: bu terimlerin 'ham'i yoktur,
    yani etiketle/yaz() onlari yazmaz. bicim_koru ile birlikte verilemez.

    bicim_koru=True ise ruamel.yaml kullanilir ve Terim.ham canli referans
    olur; uzerine yazip .yaz() ile bicimi bozmadan kaydedebilirsiniz.
    Salt okuma yapan betikler icin varsayilan (PyYAML) daha hizlidir.
    """
    if kelimeler and bicim_koru:
        # Once kontrol edilir: yazmak icin yukleyen biri (etiketle) words.md
        # terimlerini de agaca yazmaya calismasin.
        raise ValueError("kelimeler bicim_koru ile kullanilamaz (words.md yazilmaz)")
    yol = Path(yol or SOZLUK_YOLU)
    if not yol.exists():
        raise FileNotFoundError(f"sozluk yok: {yol}")

    y = None
    if bicim_koru:
        try:
            from ruamel.yaml import YAML
        except ImportError:
            print(
                "HATA: ruamel.yaml gerekli.  pip install ruamel.yaml", file=sys.stderr
            )
            sys.exit(1)
        y = YAML()
        y.preserve_quotes = True
        y.width = 4096
        y.indent(mapping=2, sequence=2, offset=0)
        with open(yol, "r", encoding="utf-8") as f:
            # ruamel ile yuklenmeli: PyYAML (yaml_yukle) duz dict dondurur ve
            # yaz() "# ---" bolum basliklarini sessizce siler. Bir kez
            # oldu (test_etiketle.test_bolum_basligi_yorumu_dosyayi_bozmaz).
            veri = y.load(f) or []
    else:
        with open(yol, "r", encoding="utf-8") as f:
            veri = yaml.safe_load(f) or []

    # Kok ogenin liste oldugu her yerde varsayiliyor ama hicbir yerde
    # dogrulanmiyordu. Sozluk yanlislikla ust duzey bir esleme icine
    # sarilirsa (elle duzenlemede kolay bir hata) 'for girdi in veri'
    # ANAHTARLAR uzerinde doner ve str.get() yok diye AttributeError
    # firlar -- hata mesaji sorunun YAML seklinde oldugunu hic soylemez.
    if not isinstance(veri, list):
        raise ValueError(
            f"sozluk kok ogesi liste olmali, {type(veri).__name__} geldi: {yol}\n"
            f"  (dosya yanlislikla ust duzey bir esleme icine sarilmis olabilir)"
        )

    terimler = []
    for ix, girdi in enumerate(veri):
        if not isinstance(girdi, dict):
            # Tek bozuk girdi yuzunden butun sozlugu dusurmek yerine onu
            # atla, ama SESSIZCE atlama -- kapsam kaydina yaz.
            SAGLIK.kaydet(
                "sozluk_girdisi_bozuk",
                f"{yol.name} girdi #{ix + 1}: {type(girdi).__name__} "
                f"(esleme bekleniyordu)",
            )
            continue
        mertebeler = girdi.get("mertebeler")
        if mertebeler:
            kardesler = [parantezsiz(m.get("isim")) for m in mertebeler]
            kardesler = [k for k in kardesler if k]
            kardesler_en = [
                ad.strip()
                for m in mertebeler
                for ad in (ingilizce_ayikla(m.get("isim")) or "").split("/")
                if ad.strip()
            ]
            for m in mertebeler:
                t = _terim_kur(girdi, m, kardesler, kardesler_en)
                if t:
                    terimler.append(t)
            ust = _terim_kur(girdi)  # Yol girdisinin kendisi de bir terim
            if ust:
                terimler.append(ust)
        else:
            t = _terim_kur(girdi)
            if t:
                terimler.append(t)

    if kelimeler:
        terimler += kelimeler_yukle(None if kelimeler is True else kelimeler)

    return Sozluk(terimler, veri, _yaml=y, _yol=yol)


# =====================================================================
# BOLUMLERE AYIRMA
# =====================================================================


@dataclass
class Bolum:
    no: int | None
    metin: str
    kaynak: str  # dosya adi
    baslik: str | None = None


ZH_BASLIK = re.compile(r"^\s*第\s*([一二三四五六七八九十百千零〇两0-9]+)\s*章")
EN_BASLIK = re.compile(r"^(?:#+\s*)?Chapter\s*[:.\-]?\s*(\d+)", re.IGNORECASE)
TR_BASLIK = re.compile(r"^(?:#+\s*)?(?:B[oö]l[uü]m)\s*[:.\-]?\s*(\d+)", re.IGNORECASE)
FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)


def _ayir(metin, desen, kaynak, cevir=int) -> list:
    """
    Metni basliklara gore boler. Her Bolum'un no'su baslikta YAZAN degerdir.

    IKI SESSIZ KAYIP YOLU VARDI, IKISI DE ARTIK KAYDEDILIYOR
    --------------------------------------------------------
    1. ILK BASLIKTAN ONCEKI METIN. aktif None oldugu surece satirlar
       hicbir tampona girmiyordu, yani atiliyorlardi. Normalde bu yalnizca
       dosya basligi/telif satiridir ve atilmasi dogrudur; ama basligi
       BOZUK olan bir bolum de ayni yola duser ve butun govdesi kaybolur.

    2. ESLESEN AMA COZULEMEYEN BASLIK. desen tutuyor ama cevir() None
       donuyorsa (Cince rakam cozulemedi) satir baslik SAYILMIYOR ve
       sessizce onceki bolumun govdesine ekleniyor. Iki bolum tek bolum
       olarak birlesiyor, ikincisinin numarasi "eksik" gorunuyor.

    Ikinci durum tam olarak EN tarafindaki 1401 gibi vakalarin sekli:
    bolum kaybolmaz, bir oncekinin ICINE girer. "eksik" raporu bunu
    "yok" diye gosterir; asil soru "nereye gitti" ve cevabi burasidir.
    """
    bolumler, aktif, baslik, tampon = [], None, None, []
    onsoz = []  # ilk baslik gorulmeden once gelen satirlar
    for satir in metin.splitlines(keepends=True):
        m = desen.match(satir)
        no = cevir(m.group(1)) if m else None
        if m and no is None:
            # Baslik gibi duruyor ama numarasi cozulemedi.
            SAGLIK.kaydet(
                "baslik_numarasi_cozulemedi",
                f"{_tek_satir(kaynak, 40)}: {_tek_satir(satir, 60)}",
            )
        if m and no is not None:
            if aktif is not None:
                bolumler.append(Bolum(aktif, "".join(tampon), kaynak, baslik))
            aktif, baslik, tampon = no, satir.strip(), [satir]
            continue
        if aktif is not None:
            tampon.append(satir)
        else:
            onsoz.append(satir)
    if aktif is not None:
        bolumler.append(Bolum(aktif, "".join(tampon), kaynak, baslik))

    onsoz_metni = "".join(onsoz).strip()
    if len(onsoz_metni) > 200:
        # Kisa onsoz beklenir (dosya basligi). Uzun onsoz, ilk bolumun
        # basliginin tutmadigi anlamina gelir ve o metin ATILIYOR demektir.
        SAGLIK.kaydet(
            "ilk_baslik_oncesi_metin_atildi",
            f"{_tek_satir(kaynak, 40)}: {len(onsoz_metni)} karakter atildi "
            f"-- basi: {_tek_satir(onsoz_metni, 70)!r}",
        )
    return bolumler


def _ciltlere_bol(ham) -> list:
    """
    Ham ZH bolumlerini ciltlere ayirir.

    Sinir olcutu: yerel numaranin KESIN AZALMASI. Esitlik degil -- ham
    metindeki iki yazim hatasi (cilt 3'te ikinci 230, cilt 8'de ikinci 6)
    tekrar uretir ama azalma uretmez, dolayisiyla sinir tespitini bozmaz.
    """
    ciltler, cilt, onceki = [], [], 0
    for b in ham:
        if b.no is not None and b.no < onceki:
            ciltler.append(cilt)
            cilt = []
        if b.no is not None:
            onceki = b.no
        cilt.append(b)
    if cilt:
        ciltler.append(cilt)
    return ciltler


def bolumler_zh(yol=None, surekli=True, kati=False) -> list:
    """
    Cince ham metin.

    surekli=True (varsayilan): numara CILT ICI SIRADAN turetilir, basliktan
    degil. Modul basindaki nota bakin -- ham metinde iki numara yanlis
    yazilmis, ama cilt uzunluklari wiki ile birebir tutuyor.

    surekli=False: basliktaki ham yerel numara. Tani icindir; bu degerler
    ciltler arasinda tekrar eder ve tek basina bolumu tanimlamaz.

    kati=True: cilt sayisi tutmuyorsa uyarip devam etmek yerine hata
    firlatir. Numaralandirmaya guvenerek YAZAN betikler (etiketle.py gibi)
    bunu kullanmali; yalnizca OKUYAN betikler icin gereksiz.
    """
    yol = Path(yol or KAYNAK_ZH)
    ham = _ayir(metin_oku(yol), ZH_BASLIK, yol.name, cn_sayi)
    if not surekli:
        return ham

    ciltler = _ciltlere_bol(ham)

    # Surekli numara cilt BASLANGICI + cilt ICI SIRA'dan turetiliyor. Yani
    # cilt sinirlari kayarsa TEK BIR bolum degil, o noktadan sonraki HER
    # bolum numarasi kayar. Bu, "ceviri hatasi" gibi gorunen ama aslinda
    # kaynak hatasi olan en pahali sessiz bozulma yolu.
    if len(ciltler) != len(CILTLER):
        mesaj = f"{len(ciltler)} cilt tespit edildi, {len(CILTLER)} bekleniyordu"
        SAGLIK.kaydet("cilt_sayisi_tutmuyor", mesaj)
        print(f"UYARI: {mesaj}. 'python3 lotm.py ciltler' ile bakin.", file=sys.stderr)
        if kati:
            raise ValueError(
                f"cilt sinirlari tutmuyor ({mesaj}); kati=True ile "
                f"numaralandirma uretilmedi"
            )

    # Cilt SAYISI tutsa bile cilt UZUNLUGU tutmayabilir. Uzunluk kaymasi
    # sinir noktasinda cakisma ya da bosluk uretir: cilt 3 bir fazla
    # bolum icerirse son bolumu 733 olur ve cilt 4'un ilk bolumuyle
    # carpisir. Cakismayi bolum_sozlugu sessizce cozerdi.
    for ix, cilt in enumerate(ciltler):
        if ix >= len(CILTLER):
            continue
        _, ad, bas, son = CILTLER[ix]
        beklenen = son - bas + 1
        if len(cilt) != beklenen:
            SAGLIK.kaydet(
                "cilt_uzunlugu_tutmuyor",
                f"cilt {ix + 1} ({ad}): {len(cilt)} bolum, {beklenen} bekleniyordu "
                f"(fark {len(cilt) - beklenen:+d})",
            )

    cikti = []
    for ix, cilt in enumerate(ciltler):
        if ix >= len(CILTLER):
            # CILTLER'de karsiligi olmayan fazladan cilt. Hepsine ayni
            # baslangic verilirse numaralar birbirinin uzerine yazar.
            SAGLIK.kaydet(
                "cilt_tablosunda_karsiligi_yok",
                f"tespit edilen cilt {ix + 1} ({len(cilt)} bolum) -- "
                f"numaralari guvenilmez",
            )
        bas = CILTLER[ix][2] if ix < len(CILTLER) else ANA_HIKAYE_SONU + 1
        for sira, b in enumerate(cilt, 1):
            cikti.append(Bolum(bas - 1 + sira, b.metin, b.kaynak, b.baslik))
    return cikti


def bolumler_en(klasor=None) -> list:
    """Ingilizce ceviri -- lotm_splitter.py'nin urettigi cilt .txt'leri."""
    klasor = Path(klasor or KAYNAK_EN)
    if not klasor.is_dir():
        raise FileNotFoundError(f"kaynak klasoru yok: {klasor}")

    def anahtar(p):
        s = re.findall(r"\d+", p.name)
        return (int(s[0]) if s else 0, p.name)

    cikti = []
    for p in sorted(klasor.glob("*.txt"), key=anahtar):
        cikti += _ayir(metin_oku(p), EN_BASLIK, p.name)
    return cikti


def bolumler_tr(klasor=None) -> list:
    """
    Yayimlanmis Turkce bolumler -- _chapters icindeki .md dosyalari.
    Numara once front matter'dan, yoksa dosya adindan alinir.
    """
    klasor = Path(klasor or BOLUMLER_TR)
    if not klasor.is_dir():
        raise FileNotFoundError(f"bolum klasoru yok: {klasor}")

    cikti = []
    for p in sorted(klasor.iterdir()):
        if p.suffix.lower() not in (".md", ".markdown", ".html"):
            continue
        s = re.findall(r"\d+", p.name)
        no = int(s[0]) if s else None
        baslik = None
        ham = p.read_text(encoding="utf-8")
        fm = FRONT_MATTER.match(ham)
        govde = ham[fm.end() :] if fm else ham
        if fm:
            try:
                bilgi = yaml_yukle(fm.group(0).strip("-\n")) or {}
                if not isinstance(bilgi, dict):
                    raise yaml.YAMLError(
                        f"front matter esleme degil: {type(bilgi).__name__}"
                    )
                for a in ("bolum", "chapter", "bolum_no", "number"):
                    if a in bilgi and str(bilgi[a]).isdigit():
                        no = int(bilgi[a])
                        break
                # title: "Bolum 41: Audrey ve Onun Susie'si" -- ZH/EN
                # tarafinda ayni bilgi govde metninin ilk satirindan
                # (Bolum.baslik) geliyor; TR'de govde baslik icermez,
                # tek kaynak front matter'daki bu alandir.
                ham_baslik = bilgi.get("title")
                if ham_baslik and str(ham_baslik).strip():
                    baslik = str(ham_baslik).strip()
            except yaml.YAMLError as e:
                # Sessizce dosya adina dusmek cogu zaman DOGRU sonucu
                # verir ve tam bu yuzden tehlikeli: bozuk front matter ile
                # "front matter'da numara yok" ayirt edilemez hale gelir.
                # Jekyll de ayni dosyayi ayristiramayacagi icin bu ayni
                # zamanda bir YAYIN hatasidir.
                SAGLIK.kaydet(
                    "front_matter_ayristirilamadi", f"{p.name}: {_tek_satir(e, 80)}"
                )
        if no is None:
            SAGLIK.kaydet("bolum_numarasi_bulunamadi", p.name)
        if baslik is None:
            # Baslik da kapsam bilgisi: govdede yer almiyor, front
            # matter'da da yoksa basliksiz kaliriz ama bunu sessizce
            # atlamak "yok" ile "okunamadi"yi ayni gosterir.
            SAGLIK.kaydet("tr_baslik_bulunamadi", p.name)
        cikti.append(Bolum(no, govde, p.name, baslik))
    return cikti


def bolum_sozlugu(bolumler) -> dict:
    """
    [Bolum] -> {no: Bolum}. Ayni numara tekrarlarsa ilki kalir.

    "Ilki kalir" makul bir politika ama SESSIZ oldugu surece tehlikeli:
    bolum_al() cagiran taraf hangisini aldigini ve bir seyin dusuruldugunu
    bilmez. numaralari_dogrula() tekrarlari zaten buluyor, ama yalnizca
    calistirilirsa. Burasi kullanim ANINDA kayda gecirir.
    """
    d = {}
    for b in bolumler:
        if b.no is None:
            continue
        if b.no in d:
            SAGLIK.kaydet(
                "tekrar_eden_bolum_numarasi",
                f"{b.no}: {_tek_satir(d[b.no].kaynak, 40)} tutuldu, "
                f"{_tek_satir(b.kaynak, 40)} dusuruldu",
            )
            continue
        d[b.no] = b
    return d


def cilt_bul(no: int):
    """Bir bolum numarasinin hangi cilde dustugunu doner."""
    for c in CILTLER:
        if c[2] <= no <= c[3]:
            return c
    return None


def bolum_al(no: int, kaynak: str = "zh"):
    """Tek bolum getirir. kaynak: 'zh' | 'en' | 'tr'."""
    f = {"zh": bolumler_zh, "en": bolumler_en, "tr": bolumler_tr}[kaynak]
    return bolum_sozlugu(f()).get(no)


# =====================================================================
# TANILAR
# =====================================================================


def _birlesme_adaylari(bolumler, eksik) -> list:
    """
    Eksik bir bolum numarasinin metni NEREYE gitti?

    Basligi bozuk/eksik olan bir bolum kaybolmaz -- _ayir onu bir onceki
    bolumun govdesine ekler. Yani "1401 eksik" iki AYRI sey olabilir:

        BIRLESMIS  -> metin duruyor, bir oncekinin icinde. Onceki bolum
                      belirgin sekilde uzundur. Duzeltme: basligi onar.
        GERCEKTEN YOK -> metin kaynakta hic yok. Onceki bolum normal
                      uzunluktadir. Duzeltme: kaynagi tamamla.

    Ikisi tamamen farkli isler gerektirir, o yuzden "sessiz kalip yalnizca
    supheliyi bildirmek" yetmez: suphe YOKSA da bunu soylemek gerekir,
    cunku "supheli degil" burada anlamli bir bulgudur ("metin gercekten
    yok" demektir), bilgi yoklugu degil.

    Doner: [(no, onceki_no, kaynak, oran, birlesme_suphesi)]

    OLCUT YEREL, KURESEL DEGIL
    --------------------------
    Ilk surum kuresel ortancayi kullaniyordu ve tam da 1401 vakasinda
    yaniltti: 1395+ yan hikayeler ana hikayeden belirgin sekilde KISA.
    1400 ile 1401 birleseydi bile ortaya cikan uzunluk, 1394 ana hikaye
    bolumunun cektigi kuresel ortancanin 1.6 katina ulasmayabilirdi --
    yani gercek bir birlesme sessizce "birlesme yok" diye raporlanirdi.
    Karsilastirma artik KOMSU bolumlere gore yapilir; her rejim (ana
    hikaye / yan hikaye) kendi olcegiyle degerlendirilir.
    """
    harita = {b.no: b for b in bolumler if b.no is not None}
    if not harita:
        return []

    def yerel_ortanca(n, pencere=15):
        """n'in cevresindeki bolumlerin ortanca uzunlugu (n haric)."""
        yakin = [
            len(harita[k].metin)
            for k in range(n - pencere, n + pencere + 1)
            if k in harita and k != n
        ]
        if not yakin:
            yakin = [len(b.metin) for b in bolumler if b.no is not None]
        if not yakin:
            return 0
        yakin.sort()
        return yakin[len(yakin) // 2]

    adaylar = []
    for n in eksik:
        onceki = harita.get(n - 1)
        if onceki is None:
            adaylar.append((n, None, None, 0.0, False))
            continue
        taban = yerel_ortanca(n - 1)
        if taban <= 0:
            adaylar.append((n, n - 1, onceki.kaynak, 0.0, False))
            continue
        oran = len(onceki.metin) / taban
        adaylar.append((n, n - 1, onceki.kaynak, oran, oran >= 1.6))
    return adaylar


def numaralari_dogrula(cikti=sys.stdout) -> bool:
    """
    Uc kaynagin bolum numaralandirmasi uyusuyor mu?

    Asil olarak Cince taraf icindir: Cince okuyamiyorsaniz bir kayma
    "ceviri hatasi" gibi gorunur ve fark edilmez. Once burada gorun.
    """
    sorun = False

    def rapor(ad, bolumler):
        nonlocal sorun
        nolar = sorted(b.no for b in bolumler if b.no is not None)
        adsiz = sum(1 for b in bolumler if b.no is None)
        if not nolar:
            print(f"  {ad}: BOLUM BULUNAMADI", file=cikti)
            sorun = True
            return set()
        kume = set(nolar)
        tekrar = len(nolar) - len(kume)
        eksik = [n for n in range(1, max(nolar) + 1) if n not in kume]
        print(f"  {ad}: {len(kume)} bolum, {min(nolar)}-{max(nolar)}", file=cikti)
        if adsiz:
            print(f"      {adsiz} parca numarasiz", file=cikti)
        if tekrar:
            print(f"      {tekrar} TEKRAR EDEN numara", file=cikti)
            sorun = True
        if eksik:
            gosterim = eksik[:10]
            devam = " ..." if len(eksik) > 10 else ""
            print(f"      {len(eksik)} EKSIK: {gosterim}{devam}", file=cikti)
            sorun = True
            # "Eksik" iki ayri sey olabilir ve ikisi farkli is gerektirir.
            for n, onceki, dosya, oran, suphe in _birlesme_adaylari(bolumler, eksik)[
                :10
            ]:
                if onceki is None:
                    print(
                        f"      -> {n}: bir onceki bolum de yok, "
                        f"kaynak burada kesiliyor olabilir",
                        file=cikti,
                    )
                elif suphe:
                    print(
                        f"      -> {n} muhtemelen {onceki} ICINDE BIRLESTI "
                        f"({_tek_satir(dosya, 30)}, {onceki} uzunlugu "
                        f"komsularinin {oran:.1f} kati)",
                        file=cikti,
                    )
                    print(
                        f"         metin duruyor; {onceki}'in govdesinde "
                        f"{n}'in basligini arayin",
                        file=cikti,
                    )
                else:
                    print(
                        f"      -> {n}: birlesme izi YOK ({onceki} uzunlugu "
                        f"normal, komsularinin {oran:.1f} kati)",
                        file=cikti,
                    )
                    print(
                        "         metin muhtemelen kaynakta HIC yok "
                        "-- EPUB'da o bolum eksik olabilir",
                        file=cikti,
                    )
        bek = BEKLENEN.get(ad)
        if bek and max(nolar) != bek:
            print(f"      son bolum {max(nolar)}, beklenen {bek}", file=cikti)
            sorun = True
        return kume

    print("bolum numaralandirma kontrolu\n", file=cikti)

    kumeler = {}
    for ad, f in (("ZH", bolumler_zh), ("EN", bolumler_en), ("TR", bolumler_tr)):
        try:
            kumeler[ad] = rapor(ad, f())
        except FileNotFoundError as e:
            print(f"  {ad}: {e}", file=cikti)

    if "ZH" in kumeler and "EN" in kumeler:
        # Karsilastirma yalnizca ANA HIKAYE araliginda anlamli. EN'deki
        # 1395+ yan hikayelerdir; Cince dosyada olmamalari eksiklik degil.
        ortak = set(range(1, ANA_HIKAYE_SONU + 1))
        yalniz_zh = (kumeler["ZH"] & ortak) - kumeler["EN"]
        yalniz_en = (kumeler["EN"] & ortak) - kumeler["ZH"]
        yan = sorted(kumeler["EN"] - ortak)

        print(f"\n  ZH/EN karsilastirmasi (1-{ANA_HIKAYE_SONU}):", file=cikti)
        if not yalniz_zh and not yalniz_en:
            print("      ana hikaye birebir ortusuyor", file=cikti)
        else:
            sorun = True
            if yalniz_zh:
                print(f"      yalniz ZH'de: {sorted(yalniz_zh)[:10]}", file=cikti)
            if yalniz_en:
                print(f"      yalniz EN'de: {sorted(yalniz_en)[:10]}", file=cikti)
        if yan:
            print(
                f"      EN'de ayrica {len(yan)} yan hikaye bolumu "
                f"({yan[0]}-{yan[-1]}) -- beklenen",
                file=cikti,
            )

    # Kapsam uyarilari BULGU DEGIL, o yuzden 'sorun' bayragini kaldirmaz;
    # ama ciktida gorunmeleri sart: "temiz" yazip yarim dosya okumus olmak
    # en kotu sonuc. Ayri baslik altinda, ayri kanaldan.
    print("\n" + ("SORUN VAR -- yukariya bakin" if sorun else "temiz"), file=cikti)
    if not SAGLIK.temiz():
        print(f"  ({SAGLIK.ozet()})", file=cikti)
        SAGLIK.rapor()
    return not sorun


def _cilt_durumu(cikti=sys.stdout):
    """Tespit edilen cilt sinirlarini CILTLER tablosuyla karsilastirir."""
    ham = _ayir(metin_oku(KAYNAK_ZH), ZH_BASLIK, "zh", cn_sayi)
    ciltler = _ciltlere_bol(ham)

    print(f"{len(ham)} baslik, {len(ciltler)} cilt tespit edildi\n", file=cikti)
    for ix, c in enumerate(ciltler):
        nolar = [b.no for b in c if b.no is not None]
        if ix < len(CILTLER):
            _, ad, bas, son = CILTLER[ix]
            bek = son - bas + 1
            fark = f"  ({ad}: beklenen {bek}, fark {len(c) - bek:+d})"
            sur = f"{bas}-{bas + len(c) - 1}"
        else:
            fark = "  (CILTLER tablosunda karsiligi yok)"
            sur = "?"
        print(
            f"  cilt {ix + 1}: {len(c)} bolum, yerel "
            f"{min(nolar)}-{max(nolar)}, surekli {sur}{fark}",
            file=cikti,
        )


def _zh_anomali(cikti=sys.stdout):
    """Cilt icinde tekrar eden veya atlanan yerel numaralar."""
    ham = _ayir(metin_oku(KAYNAK_ZH), ZH_BASLIK, "zh", cn_sayi)
    temiz = True

    for ix, c in enumerate(_ciltlere_bol(ham)):
        nolar = [b.no for b in c if b.no is not None]
        gorulen, tekrar = set(), []
        for b in c:
            if b.no in gorulen:
                tekrar.append(b)
            gorulen.add(b.no)
        eksik = [n for n in range(1, max(nolar) + 1) if n not in gorulen]
        if not tekrar and not eksik:
            continue
        temiz = False
        bas = CILTLER[ix][2] if ix < len(CILTLER) else None
        print(f"\ncilt {ix + 1}:", file=cikti)
        for b in tekrar:
            print(f"  TEKRAR yerel {b.no}: {b.baslik}", file=cikti)
        for n in eksik:
            sur = f" -> surekli {bas - 1 + n}" if bas else ""
            komsu = [b.baslik for b in c if b.no in (n - 1, n + 1)]
            print(f"  EKSIK yerel {n}{sur}  (komsular: {komsu})", file=cikti)

    if temiz:
        print("ham metinde numara anomalisi yok", file=cikti)
    else:
        print(
            "\nNot: bunlar ham metindeki YAZIM hatalaridir. Bolum sayilari"
            "\ndogru oldugu icin surekli numaralandirma etkilenmez --"
            "\nnumara siradan turetilir, etiketten degil.",
            file=cikti,
        )


def _cince_durumu(cikti=sys.stdout):
    """Sozlukte kac terimin Cince karsiligi girilmis?"""
    s = sozluk_yukle()
    var = [t for t in s.terimler if t.zh]
    yok = [t for t in s.terimler if not t.zh]
    print(
        f"{len(s.terimler)} terim, {len(var)} Cince girilmis, {len(yok)} eksik\n",
        file=cikti,
    )
    for t in sorted(yok, key=lambda t: (t.kategori, t.tr))[:40]:
        print(f"  {t.yer}: {t.tr}  ({t.en or '-'})", file=cikti)
    if len(yok) > 40:
        print(f"  ... {len(yok) - 40} tane daha", file=cikti)


def _eksik_iz(no: int, kaynak: str = "en", cikti=sys.stdout):
    """
    Eksik bir bolum numarasinin ham metinde NE oldugunu gosterir.

    'kontrol' yalnizca "1401 yok" der. Bu, uc olasiligi ayirt etmez:
        a) bolum gercekten yok (EPUB'da da yok)
        b) bolum var ama basligi desene uymuyor  -> onceki bolume karisti
        c) bolum var, basligi da var ama GORUNMEYEN bir karakter iceriyor
           (sifir genislikli bosluk, tam genislikli rakam, BOM, NBSP)
    (c) en sinsi olani: dosyaya bakinca baslik KUSURSUZ gorunur. Bu yuzden
    burada satirlar repr() ile basilir -- gorunmeyen her sey gorunur olur.

    Kullanim:  python3 lotm.py iz 1401 [en|zh|tr]
    """
    desen = {"zh": ZH_BASLIK, "en": EN_BASLIK, "tr": TR_BASLIK}[kaynak]
    cevir = cn_sayi if kaynak == "zh" else int

    if kaynak == "en":
        klasor = Path(KAYNAK_EN)
        if not klasor.is_dir():
            print(f"kaynak klasoru yok: {klasor}", file=cikti)
            return

        def _anahtar(p):
            s = re.findall(r"\d+", p.name)
            return (int(s[0]) if s else 0, p.name)

        dosyalar = sorted(klasor.glob("*.txt"), key=_anahtar)
    elif kaynak == "zh":
        dosyalar = [Path(KAYNAK_ZH)]
    else:
        dosyalar = sorted(
            p
            for p in Path(BOLUMLER_TR).iterdir()
            if p.suffix.lower() in (".md", ".markdown", ".html")
        )

    akis = []  # (dosya, dosya_ici_satir_no, satir)
    for p in dosyalar:
        try:
            metin = metin_oku(p)
        except OSError as e:
            print(f"  okunamadi: {p} ({e})", file=cikti)
            continue
        for i, satir in enumerate(metin.splitlines(), 1):
            akis.append((p.name, i, satir))

    basliklar = {}  # bolum_no -> akis indisi
    for ix, (_dosya, _i, satir) in enumerate(akis):
        m = desen.match(satir)
        if m:
            v = cevir(m.group(1))
            if v is not None and v not in basliklar:
                basliklar[v] = ix

    print(f"\n=== {no} icin iz ({kaynak.upper()}, {len(akis)} satir) ===\n", file=cikti)

    if no in basliklar:
        dosya, i, satir = akis[basliklar[no]]
        print(f"  {no} ZATEN tanindi: {dosya}:{i}\n    {satir!r}", file=cikti)
        return

    onceki, sonraki = basliklar.get(no - 1), basliklar.get(no + 1)
    print(
        f"  {no - 1}: {'bulundu' if onceki is not None else 'YOK'}"
        f"   {no + 1}: {'bulundu' if sonraki is not None else 'YOK'}\n",
        file=cikti,
    )

    if onceki is not None and sonraki is not None and onceki < sonraki:
        # Aradaki bolge: no'nun basligi burada OLMALIYDI.
        print(f"  --- {no - 1} ile {no + 1} arasindaki satirlar ---", file=cikti)
        print(
            "      (baslik burada olmali; repr ile basiliyor ki "
            "gorunmeyen karakterler gorunsun)\n",
            file=cikti,
        )
        bolge = akis[onceki : sonraki + 1]

        # BASLIK BENZERI SATIRLAR ASLA KIRPILMAZ.
        # Ilk surum bolgenin ortasini atiyordu ve tam da aranan satir
        # orada olabiliyordu -- tanilamanin kendisi kaniti gizliyordu.
        # Artik yalnizca duz govde satirlari kirpilir.
        def _baslik_benzeri(s):
            return bool(
                desen.match(s)
                or re.search(r"chapter|第.*章|b[oö]l[uü]m", s, re.IGNORECASE)
                or str(no) in s
            )

        onemli = [ix for ix, (_d, _i, s) in enumerate(bolge) if _baslik_benzeri(s)]
        if len(bolge) > 40:
            tut = set(onemli)
            tut.update(range(0, min(12, len(bolge))))
            tut.update(range(max(0, len(bolge) - 12), len(bolge)))
            # onemli satirlarin cevresinden birer satir da goster
            for ix in list(onemli):
                tut.update({ix - 1, ix + 1})
            tut = {x for x in tut if 0 <= x < len(bolge)}
        else:
            tut = set(range(len(bolge)))

        onceki_ix = None
        for ix in sorted(tut):
            if onceki_ix is not None and ix > onceki_ix + 1:
                print(
                    f"  ... [{ix - onceki_ix - 1} duz govde satiri atlandi]", file=cikti
                )
            dosya, i, satir = bolge[ix]
            isaret = ""
            if desen.match(satir):
                isaret = "  <- baslik olarak TANINDI"
            elif re.search(r"chapter|第.*章|b[oö]l[uü]m", satir, re.IGNORECASE):
                isaret = "  <- baslik GIBI ama desen tutmuyor"
            elif str(no) in satir:
                isaret = f"  <- icinde '{no}' geciyor"
            print(f"  {dosya}:{i}  {satir!r}{isaret}", file=cikti)
            onceki_ix = ix
        print(file=cikti)

    # Kaynagin tamaminda: ICINDE BU NUMARA GECEN, baslik benzeri satirlar.
    #
    # Ilk surum "baslik gibi durup taninmayan TUM satirlar" listeliyordu ve
    # bu ise yaramaz: bu EPUB'da her bolumun basligi IKI kez geciyor (biri
    # baslik ogesinden, girintisiz -> taninir; biri govde metninden,
    # girintili -> taninmaz). Yani 1400+ mesru "taninmayan" satir var,
    # liste 25'te doluyor ve aranan numaraya hic sira gelmiyordu.
    print(
        f"  --- tum kaynakta icinde '{no}' gecen baslik benzeri satirlar ---",
        file=cikti,
    )
    sayi = 0
    for dosya, i, satir in akis:
        if str(no) not in satir:
            continue
        s = satir.strip()
        if not s or len(s) > 200:
            continue
        if not re.search(r"chapter|第.*章|b[oö]l[uü]m", s, re.IGNORECASE):
            continue
        durum = "TANINDI" if desen.match(satir) else "TANINMADI"
        print(f"  [{durum}] {dosya}:{i}  {satir!r}", file=cikti)
        sayi += 1
        if sayi >= 30:
            print("  ... (ilk 30 tanesi)", file=cikti)
            break
    if sayi == 0:
        print(f"  yok -- '{no}' iceren baslik benzeri hicbir satir yok.", file=cikti)
        print(
            "      Bu, bolumun ham .txt'de HIC olmadigina isaret eder."
            " Kaynagi (EPUB -> .txt) yeniden uretmeyi deneyin.",
            file=cikti,
        )


def _saglik_durumu(cikti=sys.stdout):
    """
    Uc kaynagi da okur ve YALNIZCA kapsam sorunlarini bildirir.

    'kontrol' bulgu arar ("numaralar tutuyor mu"); bu ise aracin
    BAKABILDIGI yeri olcer ("kac dosyayi gercekten okuyabildim").
    Ikisi ayri sorular ve birbirinin yerine gecmez: tutarli gorunen bir
    numaralandirma, yarisi okunamamis bir kaynaktan da cikabilir.
    """
    SAGLIK.sifirla()
    for ad, f in (("ZH", bolumler_zh), ("EN", bolumler_en), ("TR", bolumler_tr)):
        try:
            bolumler = f()
            print(f"  {ad}: {len(bolumler)} parca okundu", file=cikti)
        except FileNotFoundError as e:
            print(f"  {ad}: OKUNAMADI -- {e}", file=cikti)
            SAGLIK.kaydet("kaynak_okunamadi", f"{ad}: {e}")
    try:
        s = sozluk_yukle()
        print(f"  SOZLUK: {len(s.terimler)} terim okundu", file=cikti)
    except (FileNotFoundError, ValueError) as e:
        print(f"  SOZLUK: OKUNAMADI -- {e}", file=cikti)
        SAGLIK.kaydet("kaynak_okunamadi", f"SOZLUK: {e}")

    print(file=cikti)
    SAGLIK.rapor(cikti)
    return SAGLIK.temiz()


if __name__ == "__main__":
    komut = sys.argv[1] if len(sys.argv) > 1 else "kontrol"
    if komut == "kontrol":
        sys.exit(0 if numaralari_dogrula() else 1)
    elif komut == "ciltler":
        _cilt_durumu()
    elif komut == "anomali":
        _zh_anomali()
    elif komut == "cince":
        _cince_durumu()
    elif komut == "saglik":
        sys.exit(0 if _saglik_durumu() else 1)
    elif komut == "iz":
        if len(sys.argv) < 3 or not sys.argv[2].isdigit():
            print("kullanim: lotm.py iz <bolum_no> [en|zh|tr]", file=sys.stderr)
            sys.exit(1)
        _kaynak = sys.argv[3] if len(sys.argv) > 3 else "en"
        if _kaynak not in ("en", "zh", "tr"):
            print(f"bilinmeyen kaynak: {_kaynak}", file=sys.stderr)
            sys.exit(1)
        _eksik_iz(int(sys.argv[2]), _kaynak)
    else:
        print(
            "kullanim: lotm.py [kontrol|ciltler|anomali|cince|saglik|iz]",
            file=sys.stderr,
        )
        sys.exit(1)
