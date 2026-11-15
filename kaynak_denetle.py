#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kaynak_denetle.py -- Çince N. bölümle İngilizce N. bölüm aynı metni mi taşıyor?

`lotm.py kontrol` yalnız NUMARALARIN hizalandığına bakar; N. bölümün iki
kaynakta AYNI METİN olduğunu denetlemez. Çevirmen ikisini de N numarasıyla
eşleştirir (hizalayıcı, şablon, terim dökümü), yani kaynakların biri kayıksa
yanlış metinler sessizce eşleşir. Bu betik tüm romanı (1-1394) şimdi tarar,
çeviri o bölüme gelene kadar beklemez.

Sinyaller (her bölüm için; ayrıntılı gerekçe ve ölçümler kodda):
  uzunluk  EN karakter / ZH karakter oranının, bölümün çevresindeki
           +-KOMSU bölümün ortancasından sapması (log ölçeğinde, sağlam
           ölçekle: sapma / (1.4826 x MAD)). Oran ciltten cilde kayar
           (cilt 1 ~4.2, sonrası ~3.4), o yüzden tek bir genel merkez değil
           yerel ortanca kullanılır.
  paragraf EN paragraf sayısı / ZH paragraf sayısı, aynı yöntemle.
           Hizalayıcı buna bağımlı; uzunluktan bağımsız ikinci tanık.
  icerik   Sözlükteki (words.md + sozluk.yml) Çince-İngilizce terim
           çiftlerinin iki tarafta bulunması: ZH N'deki terim kümesi ile
           EN N'deki terim kümesinin idf ağırlıklı kosinüsü. Uzunluktan
           bağımsız: normal uzunlukta ama başka metin olan bölümü yakalar.
           Bayrak iki biçimde: (a) kosinüs çok düşük, (b) ZH N'nin başka bir
           EN bölümle eşleşmesi N'ninkini belirgin aşıyor (ya da tersi).
  yapi     Metnin KENDİSİNDEKİ kesin izler:
             ZH: bölüm gövdesinde kısa bir cilt başlığı / "bölüm sonu"
                 satırı ("第六部 逐光者", "（第五部完）", "第七部总结")
                 yani cilt sonu yazar notu bölümün sonuna yapışmış;
             EN: gövdede BAŞKA numaralı bir "Chapter NNNN" başlık satırı
                 (başında boşlukla olsa da) -- bölüm birleşmiş.
           Aynı numaralı yinelenen başlık (EN 946'daki gibi) sayılmaz.

Ölçüt ve eşikler (1-1394 gerçek veride ölçüldü):
  uzunluk/paragraf  |z| >= --esik (ESIK = 6). Temiz bölümlerde |z| nadiren 4'ü
                    geçer; 4-6 arası yazar/çevirmen notları ve paragraf
                    bölünmesi gürültüsüdür (--hepsi ile görülür). Gerçek
                    sapmalar 9-13 çıkar.
  icerik (a)        kendi kosinüsü < ICERIK_DUSUK (0.15). Gerçek çiftlerde en
                    düşük 0.19; rastgele yanlış çiftlerin %96'sı 0.15 altında.
  icerik (b)        başka bir bölümle kosinüs, kendisininkini >= ICERIK_FARK
                    (0.30) aşıyorsa. Gerçekte komşu bölümler bile en çok 0.25
                    fark verir (aynı sahne), yanlış kaymış metin ~0.6 verir.
                    İki terim kümesinden biri ICERIK_EN_AZ (8) terimin altındaysa
                    içerik sinyali susar.
  yapi              her zaman bayrak.
  Sentetik doğrulama (gerçek veride 60 bozma: uzak bölüm metni, +1 kaymış metin,
  yarıya kesilmiş, sonraki bölümle birleşmiş, %30 kesilmiş): 60/60 yakalandı,
  bozulmamış bölümlerde yanlış alarm 0.

Çıktı en kötüden başlar, her satırda tek cümle neden; kaynak sütunu [ZH]/[EN]
yanlış tarafı yalnız metin izi kesinse söyler, aksi halde [?]. İncelenmiş
vakalar KABUL tablosundadır: ayrı "BİLİNEN" bölümünde basılır, "YENİ" sayılmaz;
artık sapma değilse "ESKİMİŞ giriş" uyarısı çıkar.

Tam tarama EN'nin 1395-1409 bölümlerini de yalnız YAPI için tarar (ZH'de yok);
1400'ün içindeki 1401 başlığı böyle yakalanır.

KAPSAM DIŞI: bölüm içinde küçük kayıklık (tek paragraf eksik/fazla: uzunluk
sapması yeterince büyük değilse görünmez), ZH ile EN'nin aynı metnin FARKLI
çevirisi olup olmadığı (anlam karşılaştırması yok), bölüm ORTASINDA yazar notu,
terimsiz çok kısa bölümlerde içerik sinyali, yazar notunun ZH ile EN'de ikisinde
birden bulunması (iki tarafı da şişirir, oran bozulmaz), TR metni.

Kullanim:
    kaynak_denetle.py                   1-1394'ü tara, raporu bas
    kaynak_denetle.py 940-950           aralıktaki HER bölümü sinyalleriyle bas
                                        (bayraklı olsun olmasın; 63, 55,58,60-64 de olur)
    kaynak_denetle.py --esik 6          uzunluk/paragraf eşiği (z)
    kaynak_denetle.py --hepsi           zayıf katmanı (eşiğin altı, 0.6 x) da listele

Çıkış kodu: 0 = YENİ (kabul tablosunda olmayan) bayraklı bölüm yok,
            1 = en az bir yeni bayraklı bölüm var (kapı olarak kullanılabilir),
            2 = kullanım hatası.

Kod olarak:  kaynak_denetle.tara(nolar=None) -> [Bulgu]
"""

import math
import re
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lotm  # noqa: E402

# ---------------------------------------------------------------- ayarlar

KOMSU = 15           # yerel ortanca: n-KOMSU .. n+KOMSU (n haric)
ESIK = 6.0           # uzunluk/paragraf: |z| bunu gecerse bayrak
ZAYIF_CARPAN = 0.6   # --hepsi: ESIK * bu .. ESIK arasi zayif katman
SAPMA_TABAN = 0.04   # log-oran sapmasinin alt siniri (sentetik/sabit veride 0'a bolme)
ICERIK_EN_AZ = 8     # iki taraftan biri bundan az terim iceriyorsa icerik sinyali susar
ICERIK_DUSUK = 0.15  # kosinus bunun altindaysa bayrak (a)
ICERIK_FARK = 0.30   # baska bolumle eslesme kendi eslesmesini bu kadar asarsa bayrak (b)

# ---------------------------------------------------------------- KABUL TABLOSU
# {bolum_no: (yanlis_kaynak, dogrulanmis_neden)}. lotm.BILINEN_EKSIK ile ayni
# ilke: giris YALNIZCA ham metne bakilip nedeni dogrulandiktan sonra eklenir;
# tahminle degil. Bolum artik sapma degilse "eskimis giris" uyarisi basilir,
# satir silinir.
KABUL = {
    # Boş: önceden kabul edilen on bölüm (ZH 213, 482, 732, 946, 1150, 1266, 1353;
    # EN 129, 1400, 1409) kaynak dosyalardan yazar/çevirmen notları, cilt sonu
    # satırları, ePub içindekiler listesi silinerek ve EN 1401 başlığı tanınır
    # hale getirilerek giderildi; artık sapma kalmadı.
}


# ---------------------------------------------------------------- yapi izleri

# Kisa satir: cilt basligi ("第六部 逐光者", "第七卷 倒吊人"), "(第五部完)",
# "第七部总结", ya da sonsoz basligi. Uzun satirlar duzyazidir ("边总结边..."
# gibi sozcuklerle yanlis alarm vermesin diye 22 karakterle sinirli).
_ZH_CILT_SATIRI = re.compile(
    r"^[（(]?第[一二三四五六七八九十百]+[部卷](?:\s*\S.{0,12}|完[）)]?|总结|[:：].{0,12})?[）)]?$"
    r"|^(?:后记|完本感言|感言)$"
)
_EN_BASLIK_SATIRI = re.compile(r"^\s*(?:#+\s*)?Chapter\s*[:.\-]?\s*(\d+)", re.IGNORECASE)


def _paragraflar(metin: str) -> list:
    return [s.strip() for s in metin.splitlines() if s.strip()]


def yapi_izleri(no: int, zh_metin, en_metin) -> list:
    """[(kaynak, aciklama)]: metnin icinde dogrudan gorunen kesin izler."""
    izler = []
    if zh_metin:
        for i, s in enumerate(_paragraflar(zh_metin)):
            if i > 0 and len(s) <= 22 and _ZH_CILT_SATIRI.match(s):
                izler.append(("ZH", f"gövdede cilt başlığı/son satırı {s!r} "
                                    f"(yazar notu bölüme yapışmış)"))
                break
    if en_metin:
        yabanci = []
        for s in en_metin.splitlines():
            m = _EN_BASLIK_SATIRI.match(s)
            if m and int(m.group(1)) != no:
                yabanci.append((int(m.group(1)), s.strip()))
        if len(yabanci) >= 10:   # tek tek karisma degil, baslik listesi (ePub icindekiler)
            izler.append(("EN", f"gövdede {len(yabanci)} adet başka başlık satırı "
                                f"(içindekiler listesi gibi; ilki {yabanci[0][1][:40]!r})"))
        elif yabanci:
            izler.append(("EN", f"gövdede başka bir başlık: {yabanci[0][1][:50]!r} "
                                f"(bölüm {yabanci[0][0]} bu bölüme karışmış)"))
    return izler


# ---------------------------------------------------------------- icerik sinyali

def terim_ciftleri() -> list:
    """[( [zh bicimleri], [en bicimleri] )]; sozluk.yml + words.md.

    Ayri fonksiyon: testler gercek sozlugu okumadan buraya sahte liste koyar.
    Tek karakterlik Cince anahtarlar atilir (魔法'in icindeki 法 gibi sayisiz
    sozcukte gecer); en kisa Ingilizce bicim 4 harf (genel sozcukleri azaltir).
    """
    sozluk = lotm.sozluk_yukle(kelimeler=True)
    cift = []
    for t in sozluk.terimler:
        if not t.zh or not t.en:
            continue
        zs = [z.strip() for z in re.split(r"[/／]", t.zh) if len(z.strip()) >= 2]
        es = [re.sub(r"\s+", " ", e.strip().lower())
              for e in re.split(r"/", re.sub(r"\([^)]*\)", "", t.en))
              if len(e.strip()) >= 4]
        if zs and es:
            cift.append((zs, es))
    return cift


class _Terimler:
    """Terim cikarma: Cince icin 2-harf onek dizini, Ingilizce icin n-gram kumesi.

    Neden: 1000 desenlik regex x 1394 bolum x 2 dil ~dakikalar surer; onek
    dizini ve kume aramasiyla tum tarama birkac saniye."""

    def __init__(self, ciftler):
        self.zh_onek = defaultdict(list)   # ilk 2 harf -> [(terim, {id})]
        zh_id = defaultdict(set)
        self.en_id = defaultdict(set)
        for i, (zs, es) in enumerate(ciftler):
            for z in zs:
                zh_id[z].add(i)
            for e in es:
                self.en_id[e].add(i)
        for z, ids in zh_id.items():
            self.zh_onek[z[:2]].append((z, ids))
        self.en_uzunluklar = sorted({len(e.split()) for e in self.en_id})

    def zh(self, metin: str) -> set:
        t = re.sub(r"\s", "", metin)
        cikti = set()
        onek = self.zh_onek
        for j in range(len(t) - 1):
            adaylar = onek.get(t[j:j + 2])
            if adaylar:
                for z, ids in adaylar:
                    if t.startswith(z, j):
                        cikti |= ids
        return cikti

    def en(self, metin: str) -> set:
        w = re.findall(r"[a-z']+", metin.lower())
        cikti = set()
        for n in self.en_uzunluklar:
            for j in range(len(w) - n + 1):
                ids = self.en_id.get(" ".join(w[j:j + n]) if n > 1 else w[j])
                if ids:
                    cikti |= ids
        return cikti


def _icerik_hesapla(zh_kume: dict, en_kume: dict) -> dict:
    """{no: (kendi_kosinus, en_iyi_baska_en, kos, en_iyi_baska_zh, kos, zterim, eterim)}

    idf, iki taraftaki bolum sayisindan: her bolumde gecen terim (Klein)
    eslesmeyi ayirt etmez, nadir ad (belirli bir yan karakter) eder."""
    n_bolum = len(zh_kume) + 1
    df = defaultdict(int)
    for no in zh_kume:
        for i in zh_kume[no] | en_kume.get(no, set()):
            df[i] += 1
    w2 = {i: math.log(n_bolum / (1 + d)) ** 2 for i, d in df.items()}
    # yalniz zh ya da yalniz en tarafta gecen terimin w2'si de var (df'ten)
    norm_z = {no: math.sqrt(sum(w2[i] for i in k)) for no, k in zh_kume.items()}
    norm_e = {no: math.sqrt(sum(w2[i] for i in k)) for no, k in en_kume.items()}
    post_e = defaultdict(list)
    post_z = defaultdict(list)
    for no, k in en_kume.items():
        for i in k:
            post_e[i].append(no)
    for no, k in zh_kume.items():
        for i in k:
            post_z[i].append(no)

    def kos(a, b):
        if not a or not b:
            return 0.0
        return sum(w2[i] for i in a & b)

    out = {}
    for no, zk in zh_kume.items():
        ek = en_kume.get(no, set())
        dz, de = norm_z[no], norm_e.get(no, 0.0)
        own = kos(zk, ek) / (dz * de) if dz and de else 0.0
        # ZH no'nun en iyi baska EN eslesmesi (inverted index)
        skor = defaultdict(float)
        for i in zk:
            for m in post_e.get(i, ()):
                if m != no:
                    skor[m] += w2[i]
        eb_m, eb_k = 0, 0.0
        for m, s in skor.items():
            c = s / (dz * norm_e[m]) if dz and norm_e.get(m) else 0.0
            if c > eb_k:
                eb_m, eb_k = m, c
        skor = defaultdict(float)
        for i in ek:
            for m in post_z.get(i, ()):
                if m != no:
                    skor[m] += w2[i]
        zb_m, zb_k = 0, 0.0
        for m, s in skor.items():
            c = s / (de * norm_z[m]) if de and norm_z.get(m) else 0.0
            if c > zb_k:
                zb_m, zb_k = m, c
        out[no] = (own, eb_m, eb_k, zb_m, zb_k, len(zk), len(ek))
    return out


# ---------------------------------------------------------------- sinyaller

@dataclass
class Sinyal:
    no: int
    zc: int = 0           # ZH karakter (bosluksuz)
    ec: int = 0           # EN karakter (bosluk daraltilmis)
    zp: int = 0           # ZH paragraf
    ep: int = 0           # EN paragraf
    oran: float = 0.0     # ec / zc
    oran_merkez: float = 0.0
    z_uzunluk: float = 0.0
    p_oran: float = 0.0   # ep / zp
    p_merkez: float = 0.0
    z_paragraf: float = 0.0
    icerik: float | None = None  # kendi kosinusu (None: terim az, sinyal susar)
    zt: int = 0
    et: int = 0
    en_iyi_en: int = 0    # ZH N'ye en cok benzeyen EN bolum (N degil)
    en_iyi_en_k: float = 0.0
    en_iyi_zh: int = 0    # EN N'ye en cok benzeyen ZH bolum (N degil)
    en_iyi_zh_k: float = 0.0
    yapi: list = field(default_factory=list)  # [(kaynak, aciklama)]
    eksik: str = ""       # "ZH" / "EN": o kaynakta bolum yok


@dataclass
class Bulgu:
    no: int
    kaynak: str            # "ZH", "EN" ya da "?" (hangisi yanlis belli degil)
    siddet: float          # siralama icin (buyuk = kotu)
    neden: str             # tek satir
    sinyal: Sinyal
    bilinen: bool = False
    kabul_nedeni: str = ""
    zayif: bool = False    # --hepsi katmani


def _yerel_merkez(deger: dict, no: int) -> float | None:
    komsular = [deger[m] for m in range(no - KOMSU, no + KOMSU + 1)
                if m != no and m in deger]
    return statistics.median(komsular) if komsular else None


def _sapma(artiklar) -> float:
    """1.4826 x MAD; sabit/sentetik veride tabanla sinirli."""
    artiklar = list(artiklar)
    if not artiklar:
        return SAPMA_TABAN
    m = statistics.median(artiklar)
    mad = statistics.median(abs(a - m) for a in artiklar)
    return max(1.4826 * mad, SAPMA_TABAN)


def sinyalleri_hesapla(zh: dict, en: dict, nolar, ciftler=None) -> dict:
    """{no: Sinyal} (yalniz nolar). zh/en: {no: Bolum}. Yerel merkezler ve
    sapma TUM ortak bolumlerden hesaplanir (aralik modunda da)."""
    ortak = sorted(set(zh) & set(en))
    zc = {n: len(re.sub(r"\s", "", zh[n].metin)) for n in ortak}
    ec = {n: len(re.sub(r"\s+", " ", en[n].metin).strip()) for n in ortak}
    zp = {n: len(_paragraflar(zh[n].metin)) for n in ortak}
    ep = {n: len(_paragraflar(en[n].metin)) for n in ortak}
    log_o = {n: math.log(ec[n] / zc[n]) for n in ortak if zc[n] and ec[n]}
    log_p = {n: math.log(ep[n] / zp[n]) for n in ortak if zp[n] and ep[n]}

    def artik(log_d):
        r = {}
        for n in log_d:
            c = _yerel_merkez(log_d, n)
            if c is not None:
                r[n] = log_d[n] - c
        return r

    art_o, art_p = artik(log_o), artik(log_p)
    sap_o, sap_p = _sapma(art_o.values()), _sapma(art_p.values())

    ic = {}
    if ciftler:
        tm = _Terimler(ciftler)
        zk = {n: tm.zh(zh[n].metin) for n in ortak}
        ek = {n: tm.en(en[n].metin) for n in ortak}
        ic = _icerik_hesapla(zk, ek)

    sonuc = {}
    for no in nolar:
        s = Sinyal(no)
        if no not in zh or no not in en:
            s.eksik = "+".join(k for k, d in (("ZH", zh), ("EN", en)) if no not in d)
            if no in en:   # yalniz EN var (1395+ yan hikaye): yalniz yapi bakilir
                s.ec = len(re.sub(r"\s+", " ", en[no].metin).strip())
                s.ep = len(_paragraflar(en[no].metin))
                s.yapi = yapi_izleri(no, None, en[no].metin)
            sonuc[no] = s
            continue
        s.zc, s.ec, s.zp, s.ep = zc[no], ec[no], zp[no], ep[no]
        if no in log_o:
            s.oran = ec[no] / zc[no]
            s.oran_merkez = math.exp(log_o[no] - art_o[no]) if no in art_o else 0.0
            s.z_uzunluk = art_o.get(no, 0.0) / sap_o
        if no in log_p:
            s.p_oran = ep[no] / zp[no]
            s.p_merkez = math.exp(log_p[no] - art_p[no]) if no in art_p else 0.0
            s.z_paragraf = art_p.get(no, 0.0) / sap_p
        if no in ic:
            own, eb_m, eb_k, zb_m, zb_k, zt, et = ic[no]
            s.zt, s.et = zt, et
            if min(zt, et) >= ICERIK_EN_AZ:
                s.icerik = own
                s.en_iyi_en, s.en_iyi_en_k = eb_m, eb_k
                s.en_iyi_zh, s.en_iyi_zh_k = zb_m, zb_k
        s.yapi = yapi_izleri(no, zh[no].metin, en[no].metin)
        sonuc[no] = s
    return sonuc


def degerlendir(s: Sinyal, esik: float):
    """-> (siddet, kaynak, neden, guclu) ya da None.

    guclu=False: zayif katman (esigin ZAYIF_CARPAN'i ile esigi arasi). Siddet
    siralama icindir: esikte 10, yapisal iz 500, eksik bolum 1000."""
    adaylar = []  # (siddet, kaynak, neden, guclu)
    for kaynak, aciklama in s.yapi:
        adaylar.append((500.0, kaynak, aciklama, True))
    if s.eksik:
        # Numara eksikligi lotm.py kontrol'un konusu: bilinen eksik ve 1394 sonrasi
        # (ZH'de yok) burada bayrak olmaz; baska her eksik ise sessiz kalmaz.
        yok = [k for k in s.eksik.split("+")
               if not (s.no in lotm.BILINEN_EKSIK.get(k, {}) or
                       (k == "ZH" and s.no > lotm.ANA_HIKAYE_SONU))]
        if yok:
            adaylar.append((1000.0, "+".join(yok),
                            f"{'+'.join(yok)} kaynağında bu numaralı bölüm yok", True))
        if not adaylar:
            return None
        adaylar.sort(key=lambda a: -a[0])
        return (adaylar[0][0], adaylar[0][1], "; ".join(a[2] for a in adaylar), True)
    if s.zc and abs(s.z_uzunluk) >= esik * ZAYIF_CARPAN:
        yon = ("EN fazla uzun ya da ZH eksik" if s.z_uzunluk > 0
               else "EN eksik ya da ZH'ye ek metin yapışmış")
        adaylar.append((abs(s.z_uzunluk) / esik * 10, "?",
                        f"uzunluk oranı {s.oran:.2f} (yerel {s.oran_merkez:.2f}, "
                        f"{s.z_uzunluk:+.1f} sapma): {yon}",
                        abs(s.z_uzunluk) >= esik))
    if s.zp and abs(s.z_paragraf) >= esik * ZAYIF_CARPAN:
        adaylar.append((abs(s.z_paragraf) / esik * 10, "?",
                        f"paragraf oranı {s.p_oran:.2f} (yerel {s.p_merkez:.2f}, "
                        f"{s.z_paragraf:+.1f} sapma; ZH {s.zp}, EN {s.ep} paragraf)",
                        abs(s.z_paragraf) >= esik))
    if s.icerik is not None:
        if s.icerik < ICERIK_DUSUK:
            adaylar.append((20 + (ICERIK_DUSUK - s.icerik) * 20, "?",
                            f"içerik örtüşmesi {s.icerik:.2f} < {ICERIK_DUSUK} "
                            f"(ZH {s.zt}, EN {s.et} sözlük terimi): iki metin başka metin gibi",
                            True))
        if s.en_iyi_en_k - s.icerik >= ICERIK_FARK:
            adaylar.append((20 + (s.en_iyi_en_k - s.icerik) * 20, "?",
                            f"ZH {s.no} metni EN {s.no}'den çok EN {s.en_iyi_en}'e benziyor "
                            f"({s.en_iyi_en_k:.2f} > {s.icerik:.2f})", True))
        if s.en_iyi_zh_k - s.icerik >= ICERIK_FARK:
            adaylar.append((20 + (s.en_iyi_zh_k - s.icerik) * 20, "?",
                            f"EN {s.no} metni ZH {s.no}'den çok ZH {s.en_iyi_zh}'e benziyor "
                            f"({s.en_iyi_zh_k:.2f} > {s.icerik:.2f})", True))
    if not adaylar:
        return None
    adaylar.sort(key=lambda a: -a[0])
    neden = "; ".join(a[2] for a in adaylar[:3])
    return (adaylar[0][0], adaylar[0][1], neden, any(a[3] for a in adaylar))


def tara(nolar=None, ciftler=None, zh=None, en=None, esik: float = ESIK,
         zayif: bool = False) -> list:
    """Bayrakli bolumlerin listesi (en kotu once); bkz. tara_sinyalli."""
    return tara_sinyalli(nolar, ciftler, zh, en, esik, zayif)[0]


def tara_sinyalli(nolar=None, ciftler=None, zh=None, en=None, esik: float = ESIK,
                  zayif: bool = False) -> tuple:
    """(bulgular, nolar, sinyaller): tara'nin ayrintili hali (CLI ayni hesabi
    ikinci kez yapmasin diye).

    nolar None: 1..ANA_HIKAYE_SONU. zh/en verilmezse lotm'dan okunur; ciftler
    None ise sozlukten (terim_ciftleri). Testler hepsini enjekte eder.
    zayif=True: zayif katmani da dondurur (Bulgu.zayif)."""
    zh = zh if zh is not None else lotm.bolum_sozlugu(lotm.bolumler_zh())
    en = en if en is not None else lotm.bolum_sozlugu(lotm.bolumler_en())
    if nolar is None:
        # ZH yalniz 1394'e kadar; EN'nin 1395+ bolumleri de taranir (yalniz yapi):
        # EN 1400'un icindeki 1401 basligi tam burada yakalanir.
        nolar = list(range(1, lotm.ANA_HIKAYE_SONU + 1)) + sorted(
            n for n in en if n > lotm.ANA_HIKAYE_SONU)
    nolar = list(nolar)
    if ciftler is None:
        ciftler = terim_ciftleri()
    sinyaller = sinyalleri_hesapla(zh, en, nolar, ciftler)
    bulgular = []
    for no in nolar:
        s = sinyaller[no]
        d = degerlendir(s, esik)
        if d is None or (not d[3] and not zayif):
            continue
        siddet, kaynak, neden, guclu = d
        b = Bulgu(no, kaynak, siddet, neden, s, zayif=not guclu)
        if no in KABUL:
            b.bilinen, b.kabul_nedeni = True, KABUL[no][1]
        bulgular.append(b)
    bulgular.sort(key=lambda b: -b.siddet)
    return bulgular, nolar, sinyaller


# ---------------------------------------------------------------- cikti

def _satir(no, s: Sinyal) -> str:
    ic = f"{s.icerik:.2f}" if s.icerik is not None else " -- "
    return (f"{no:>5}  ZH {s.zc:>6} EN {s.ec:>6}  oran {s.oran:5.2f} ({s.z_uzunluk:+5.1f})"
            f"  ¶ ZH {s.zp:>3} EN {s.ep:>3} ({s.z_paragraf:+5.1f})  içerik {ic}"
            f"{'  yapı' if s.yapi else ''}")


def _bulgu_satiri(b: Bulgu) -> str:
    return f"  {b.no:>5} [{b.kaynak}] {b.neden}"


def rapor(nolar, bulgular, cikti=None) -> int:
    """Raporu basar, cikis kodunu doner. (cikti varsayilani CAGRI aninda
    sys.stdout: tanimda baglanirsa testin yakaladigi akisi kacirir.)"""
    cikti = cikti or sys.stdout
    yeni = [b for b in bulgular if not b.bilinen and not b.zayif]
    zayiflar = [b for b in bulgular if not b.bilinen and b.zayif]
    bilinen = [b for b in bulgular if b.bilinen]
    print(f"kaynak denetimi: {len(nolar)} bölüm tarandı "
          f"(ZH N <-> EN N içerik/uzunluk/yapı)", file=cikti)
    if yeni:
        print(f"\nYENİ ({len(yeni)}), en kötüsü önce:", file=cikti)
        for b in yeni:
            print(_bulgu_satiri(b), file=cikti)
    else:
        print("\nYENİ bayraklı bölüm yok.", file=cikti)
    if zayiflar:
        print(f"\nZAYIF katman ({len(zayiflar)}):", file=cikti)
        for b in zayiflar:
            print(_bulgu_satiri(b), file=cikti)
    if bilinen:
        print(f"\nBİLİNEN ({len(bilinen)}), incelenmiş ve kabul edilmiş:", file=cikti)
        for b in sorted(bilinen, key=lambda b: b.no):
            print(f"  {b.no:>5} [{KABUL[b.no][0]}] {b.kabul_nedeni}", file=cikti)
    bayrakli = {b.no for b in bulgular if not b.zayif}
    eskimis = [no for no in KABUL if no in set(nolar) and no not in bayrakli]
    for no in sorted(eskimis):
        print(f"\nESKİMİŞ giriş: {no} artık sapma değil ({KABUL[no][1]}); "
              f"KABUL tablosundan silin.", file=cikti)
    return 1 if yeni else 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    esik, hepsi, alan = ESIK, False, None
    try:
        i = 0
        while i < len(argv):
            a = argv[i]
            if a == "--esik":
                esik = float(argv[i + 1])
                i += 2
            elif a == "--hepsi":
                hepsi = True
                i += 1
            elif a in ("-h", "--help"):
                print(__doc__)
                return 0
            elif a.startswith("--") or alan is not None:
                raise ValueError(f"tanınmayan argüman: {a}")
            else:
                alan = a
                i += 1
        nolar = lotm.bolum_listesi(alan) if alan else None
    except (ValueError, IndexError) as e:
        print(f"kullanım hatası: {e}\n\n{__doc__}", file=sys.stderr)
        return 2

    bulgular, hedef, sinyaller = tara_sinyalli(
        nolar, esik=esik, zayif=hepsi or nolar is not None)
    if nolar is None:
        return rapor(hedef, bulgular)

    # aralik modu: her bolum, sinyalleriyle
    isaret = {b.no: b for b in bulgular}
    for no in hedef:
        s = sinyaller[no]
        b = isaret.get(no)
        if s.eksik:
            ek = ""
            if any(no in lotm.BILINEN_EKSIK.get(k, {}) for k in s.eksik.split("+")):
                ek = " (lotm.BILINEN_EKSIK)"
            elif s.eksik == "ZH" and no > lotm.ANA_HIKAYE_SONU:
                ek = " (ana hikaye dışı)"
            print(f"{no:>5}  {s.eksik.replace('+', ' ve ')} kaynağında yok{ek}"
                  + (f"  EN {s.ec} karakter, {s.ep} paragraf" if s.ec else ""))
            if b:
                print(f"        -> BAYRAK: {b.neden}")
            continue
        etiket = ""
        if b:
            etiket = "  BAYRAK" + (" (bilinen)" if b.bilinen else " (zayıf)" if b.zayif else "")
        print(_satir(no, s) + etiket)
        if b:
            print(f"        -> {b.neden}")
    return 1 if any(not b.bilinen and not b.zayif for b in bulgular) else 0


if __name__ == "__main__":
    sys.exit(main())
