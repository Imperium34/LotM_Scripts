#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lotm.py -- LotM ceviri projesi icin ortak temel.

Uc sey bu projede birden fazla yerde tekrarlaniyordu ve zamanla birbirinden
kaymaya basladi. Hepsi burada tek tanima indirildi:

  1. BOLUME AYIRMA. chinese_lookup.py sirayla sayiyordu, searcher.py basliktaki
     numarayi okuyordu, denetci2.py dosya adindan aliyordu. Ucu de "279. bolum"
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
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    print("HATA: PyYAML gerekli.  pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# =====================================================================
# YOLLAR -- LOTM_KOK ile degistirilebilir
# =====================================================================

KOK = Path(os.environ.get("LOTM_KOK", Path.home() / "Projects/LotM"))
SITE = KOK / "Imperium34.github.io"

SOZLUK_YOLU = SITE / "_data/sozluk.yml"
BOLUMLER_TR = SITE / "_chapters"
KAYNAK_EN = KOK / "Source/LotM_Volumes"
KAYNAK_ZH = KOK / "Source/Lord_of_the_Mysteries_Chinese.txt"
KELIMELER = KOK / "Tools/words.md"


# =====================================================================
# CILT TABLOSU
# =====================================================================

# Wiki ile dogrulanmis araliklar. Cince ham metinden tespit edilen cilt
# uzunluklari bu tabloyla birebir ortusuyor (fark +0, sekizde sekiz).
# lotm_splitter.py'deki VOLUME_RANGES bununla ayni olmali.
CILTLER = [
    (1, "Clown",       1,    213),
    (2, "Faceless",    214,  482),
    (3, "Traveler",    483,  732),
    (4, "Undying",     733,  946),
    (5, "Red_Priest",  947,  1150),
    (6, "Lightseeker", 1151, 1266),
    (7, "Hanged_Man",  1267, 1353),
    (8, "Fool",        1354, 1394),
]

# Ana hikaye 1394'te biter. Ingilizce metindeki 1395+ yan hikayelerdir
# (An Ordinary Person's Daily Life, In Modern Day) ve Cince ham dosyada
# YOKTUR -- eksik degil, kapsam disi. Wiki ayrica 1431-1432'de bir bonus
# bolumden (That Corner) soz ediyor; o da iki kaynakta da yok.
ANA_HIKAYE_SONU = 1394
SON_BOLUM = 1409          # Ingilizce metnin sonu (yan hikayeler dahil)

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
    return ham.decode("utf-8", errors="replace")


# =====================================================================
# CINCE SAYILAR
# =====================================================================

_CN_RAKAM = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
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
            bolum += (sayi or 1) * _CN_BASAMAK[ch]   # "十五" -> 15
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
# SOZLUK
# =====================================================================

@dataclass
class Terim:
    """
    Sozlukteki tek bir terim -- ust duzey girdi ya da bir mertebe.

    Iki YAML sekli tek kayda indirgenir:
      ust duzey:  terim: X / ingilizce: Y      (ayri alanlar)
      mertebe:    isim: "X (Y)"                (tek alanda gomulu)

    ham: ruamel ile yuklendiyse CANLI referanstir. etiketle.py bunun uzerine
    yazip dosyayi bicimi bozulmadan geri kaydedebilir.
    """
    tr: str
    en: str | None = None
    zh: str | None = None
    kategori: str = ""
    yol: str | None = None          # bagli oldugu Yol (mertebeler icin)
    yol_en: str | None = None
    seviye: int | None = None
    bolum_siniri: int | None = None
    eski_karsiliklar: list = field(default_factory=list)
    arama_adi: list = field(default_factory=list)
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

    def arama_adaylari(self) -> list:
        """
        Ingilizce tarama icin aday stringler, uzundan kisaya.
        arama_adi verilmisse yalnizca o kullanilir.
        """
        if self.arama_adi:
            kaynak = list(self.arama_adi)
        elif self.en:
            kaynak = etiket_temizle(self.en)
        else:
            return []
        tum = set()
        for a in kaynak:
            tum |= varyantlar(a)
        return sorted(tum, key=lambda s: (-len(s), s))


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
        q = sorgu.lower()
        return [
            t for t in self.terimler
            if q in (t.tr or "").lower()
            or q in (t.en or "").lower()
            or q in (t.zh or "")
        ]

    def yaz(self, hedef=None):
        """
        Ham agaci geri yazar. Yalnizca bicim_koru=True ile yuklendiyse
        calisir -- PyYAML'in dump'i yorumlari siler, anahtarlari siralar ve
        uzun dizeleri sarar, yani diff okunamaz hale gelir.
        """
        if self._yaml is None:
            raise RuntimeError(
                "yaz() icin sozluk_yukle(bicim_koru=True) ile yuklenmeli"
            )
        import io
        tampon = io.StringIO()
        self._yaml.dump(self.veri, tampon)
        Path(hedef or self._yol).write_text(tampon.getvalue(), encoding="utf-8")


def _terim_kur(ham_girdi, ham_mertebe=None, kardesler=None):
    """Tek bir YAML dugumunden Terim uretir."""
    kardesler = kardesler or []

    if ham_mertebe is not None:
        isim = str(ham_mertebe.get("isim", ""))
        tr = parantezsiz(isim)
        if not tr:
            return None
        en_ham = ingilizce_ayikla(isim)
        # cok adli mertebelerde ilk ad esas alinir
        en = en_ham.split("/")[0].strip() if en_ham else None
        yol_en_list = etiket_temizle(ham_girdi.get("ingilizce", ""))
        return Terim(
            tr=tr,
            en=en,
            zh=ham_mertebe.get("cince"),
            kategori=ham_girdi.get("kategori", ""),
            yol=ham_girdi.get("terim"),
            yol_en=yol_en_list[0] if yol_en_list else None,
            seviye=ham_mertebe.get("seviye"),
            bolum_siniri=ham_mertebe.get("bolum_siniri"),
            eski_karsiliklar=list(ham_mertebe.get("eski_karsiliklar") or []),
            arama_adi=list(ham_mertebe.get("arama_adi") or []),
            cevirmen_notu=ham_mertebe.get("cevirmen_notu"),
            kardesler_tr=[k for k in kardesler if k != tr],
            kardesler_en=[],
            ham=ham_mertebe,
        )

    tr = parantezsiz(ham_girdi.get("terim"))
    if not tr:
        return None
    return Terim(
        tr=tr,
        en=parantezsiz(ham_girdi.get("ingilizce")) or None,
        zh=ham_girdi.get("cince"),
        kategori=ham_girdi.get("kategori", ""),
        bolum_siniri=ham_girdi.get("bolum_siniri"),
        eski_karsiliklar=list(ham_girdi.get("eski_karsiliklar") or []),
        arama_adi=list(ham_girdi.get("arama_adi") or []),
        cevirmen_notu=ham_girdi.get("cevirmen_notu"),
        ham=ham_girdi,
    )


def sozluk_yukle(yol=None, bicim_koru=False) -> Sozluk:
    """
    sozluk.yml'i yukler.

    bicim_koru=True ise ruamel.yaml kullanilir ve Terim.ham canli referans
    olur; uzerine yazip .yaz() ile bicimi bozmadan kaydedebilirsiniz.
    Salt okuma yapan betikler icin varsayilan (PyYAML) daha hizlidir.
    """
    yol = Path(yol or SOZLUK_YOLU)
    if not yol.exists():
        raise FileNotFoundError(f"sozluk yok: {yol}")

    y = None
    if bicim_koru:
        try:
            from ruamel.yaml import YAML
        except ImportError:
            print("HATA: ruamel.yaml gerekli.  pip install ruamel.yaml",
                  file=sys.stderr)
            sys.exit(1)
        y = YAML()
        y.preserve_quotes = True
        y.width = 4096
        y.indent(mapping=2, sequence=2, offset=0)
        with open(yol, "r", encoding="utf-8") as f:
            veri = y.load(f)
    else:
        with open(yol, "r", encoding="utf-8") as f:
            veri = yaml.safe_load(f) or []

    terimler = []
    for girdi in veri:
        mertebeler = girdi.get("mertebeler")
        if mertebeler:
            kardesler = [parantezsiz(m.get("isim")) for m in mertebeler]
            kardesler = [k for k in kardesler if k]
            for m in mertebeler:
                t = _terim_kur(girdi, m, kardesler)
                if t:
                    terimler.append(t)
            ust = _terim_kur(girdi)      # Yol girdisinin kendisi de bir terim
            if ust:
                terimler.append(ust)
        else:
            t = _terim_kur(girdi)
            if t:
                terimler.append(t)

    return Sozluk(terimler, veri, _yaml=y, _yol=yol)


# =====================================================================
# BOLUMLERE AYIRMA
# =====================================================================

@dataclass
class Bolum:
    no: int | None
    metin: str
    kaynak: str          # dosya adi
    baslik: str | None = None


ZH_BASLIK = re.compile(r"^\s*第\s*([一二三四五六七八九十百千零〇两0-9]+)\s*章")
EN_BASLIK = re.compile(r"^(?:#+\s*)?Chapter\s*[:.\-]?\s*(\d+)", re.IGNORECASE)
TR_BASLIK = re.compile(r"^(?:#+\s*)?(?:B[oö]l[uü]m)\s*[:.\-]?\s*(\d+)",
                       re.IGNORECASE)
FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)


def _ayir(metin, desen, kaynak, cevir=int) -> list:
    """Metni basliklara gore boler. Her Bolum'un no'su baslikta YAZAN degerdir."""
    bolumler, aktif, baslik, tampon = [], None, None, []
    for satir in metin.splitlines(keepends=True):
        m = desen.match(satir)
        no = cevir(m.group(1)) if m else None
        if m and no is not None:
            if aktif is not None:
                bolumler.append(Bolum(aktif, "".join(tampon), kaynak, baslik))
            aktif, baslik, tampon = no, satir.strip(), [satir]
            continue
        if aktif is not None:
            tampon.append(satir)
    if aktif is not None:
        bolumler.append(Bolum(aktif, "".join(tampon), kaynak, baslik))
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


def bolumler_zh(yol=None, surekli=True) -> list:
    """
    Cince ham metin.

    surekli=True (varsayilan): numara CILT ICI SIRADAN turetilir, basliktan
    degil. Modul basindaki nota bakin -- ham metinde iki numara yanlis
    yazilmis, ama cilt uzunluklari wiki ile birebir tutuyor.

    surekli=False: basliktaki ham yerel numara. Tani icindir; bu degerler
    ciltler arasinda tekrar eder ve tek basina bolumu tanimlamaz.
    """
    yol = Path(yol or KAYNAK_ZH)
    ham = _ayir(metin_oku(yol), ZH_BASLIK, yol.name, cn_sayi)
    if not surekli:
        return ham

    ciltler = _ciltlere_bol(ham)
    if len(ciltler) != len(CILTLER):
        print(f"UYARI: {len(ciltler)} cilt tespit edildi, {len(CILTLER)} "
              f"bekleniyordu. 'python3 lotm.py ciltler' ile bakin.",
              file=sys.stderr)

    cikti = []
    for ix, cilt in enumerate(ciltler):
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
        ham = p.read_text(encoding="utf-8")
        fm = FRONT_MATTER.match(ham)
        govde = ham[fm.end():] if fm else ham
        if fm:
            try:
                bilgi = yaml.safe_load(fm.group(0).strip("-\n")) or {}
                for a in ("bolum", "chapter", "bolum_no", "number"):
                    if a in bilgi and str(bilgi[a]).isdigit():
                        no = int(bilgi[a])
                        break
            except yaml.YAMLError:
                pass
        cikti.append(Bolum(no, govde, p.name))
    return cikti


def bolum_sozlugu(bolumler) -> dict:
    """[Bolum] -> {no: Bolum}. Ayni numara tekrarlarsa ilki kalir."""
    d = {}
    for b in bolumler:
        if b.no is not None and b.no not in d:
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
            print(f"      EN'de ayrica {len(yan)} yan hikaye bolumu "
                  f"({yan[0]}-{yan[-1]}) -- beklenen", file=cikti)

    print("\n" + ("SORUN VAR -- yukariya bakin" if sorun else "temiz"), file=cikti)
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
        print(f"  cilt {ix + 1}: {len(c)} bolum, yerel "
              f"{min(nolar)}-{max(nolar)}, surekli {sur}{fark}", file=cikti)


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
        print("\nNot: bunlar ham metindeki YAZIM hatalaridir. Bolum sayilari"
              "\ndogru oldugu icin surekli numaralandirma etkilenmez --"
              "\nnumara siradan turetilir, etiketten degil.", file=cikti)


def _cince_durumu(cikti=sys.stdout):
    """Sozlukte kac terimin Cince karsiligi girilmis?"""
    s = sozluk_yukle()
    var = [t for t in s.terimler if t.zh]
    yok = [t for t in s.terimler if not t.zh]
    print(f"{len(s.terimler)} terim, {len(var)} Cince girilmis, "
          f"{len(yok)} eksik\n", file=cikti)
    for t in sorted(yok, key=lambda t: (t.kategori, t.tr))[:40]:
        print(f"  {t.yer}: {t.tr}  ({t.en or '-'})", file=cikti)
    if len(yok) > 40:
        print(f"  ... {len(yok) - 40} tane daha", file=cikti)


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
    else:
        print("kullanim: lotm.py [kontrol|ciltler|anomali|cince]", file=sys.stderr)
        sys.exit(1)
