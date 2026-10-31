#!/usr/bin/env python3
"""
sozluk_lint.py — LotM Türkçe çevirisi için tutarlılık denetleyicisi.

Okuyarak yakalanamayan hata sınıfını hedefler: dosyalar arası terim kayması,
diyakritik tutarsızlığı, birim sızması, kesme işareti karışıklığı, register
sapması. Bunların hiçbiri tek bir bölümü dikkatle okuyarak görülemez, çünkü
kanıt her zaman başka bir dosyadadır.

Kullanım:
    python3 sozluk_lint.py --sozluk sozluk.yml --kurallar lint-kurallari.yml BOLUMLER...
    python3 sozluk_lint.py ... ../Imperium34.github.io/_chapters/     (klasör de olur)

Bölümler lotm.bolumler_tr ile okunur (yayim_denetle ile aynı ayrıştırıcı).
Başlıklar ("Bölüm N: " öneki atılarak) gövdeyle aynı dil denetimlerinden
geçer ve "0050.md:başlık" olarak raporlanır. Register ve sözlük kapsamı
yalnızca gövdeyi ölçer.
    python3 sozluk_lint.py ... --sadece varyant,diyakritik
    python3 sozluk_lint.py ... --format json > rapor.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML gerekli:  pip install pyyaml")

# turkce.py Tools/ kokunde; bu betik lint/ alt klasorunde. Once kendi
# klasorune, sonra bir ustune bakilir (duz bir kopyada da calissin diye).
# turkce.py bagimliliksizdir: lotm'u ya da YAML'i yuklemez.
for _yol in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent):
    if (_yol / "turkce.py").exists():
        sys.path.insert(0, str(_yol))
        break
from turkce import tr_desen, tr_kucult  # noqa: E402

# lotm.py Tools/ kokunde. Bolumler onunla okunur: lint'in kendi front matter
# ayristiricisi ('---' uzerinden kaba bolme) ile lotm.bolumler_tr (regex +
# YAML) ayni dosya icin farkli sonuc verebiliyordu ve basligi hic okumuyordu
# -- Bolum 50'deki "Neil'in" ek denetiminden boyle gecti.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    import lotm  # noqa: E402
except ImportError as _e:
    sys.exit(f"lotm.py bulunamadi (lint/ klasorunun bir ustunde olmali): {_e}")


# ----------------------------------------------------------------------
# Bulgular
# ----------------------------------------------------------------------


@dataclass
class Bulgu:
    kural: str
    dosya: str
    satir: int
    bulunan: str
    mesaj: str
    baglam: str = ""
    agirlik: str = "hata"  # hata | uyari | bilgi

    def satir_olarak(self) -> str:
        isaret = {"hata": "!!", "uyari": " *", "bilgi": "  "}[self.agirlik]
        # Baslik tek satirdir; satir numarasi bilgi tasimaz.
        konum = (
            self.dosya
            if self.dosya.endswith(BASLIK_EK)
            else f"{self.dosya}:{self.satir}"
        )
        bas = f"{isaret} {konum}"
        govde = f"{self.mesaj}"
        if self.baglam:
            govde += f"\n       … {self.baglam} …"
        return f"{bas}  {govde}"


@dataclass
class Rapor:
    bulgular: list[Bulgu] = field(default_factory=list)
    olcumler: dict = field(default_factory=dict)

    def ekle(self, *a, **kw):
        self.bulgular.append(Bulgu(*a, **kw))


# ----------------------------------------------------------------------
# Yardımcılar
# ----------------------------------------------------------------------

TR_HARF = "A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîûÊê"
KIVRIK = "\u2019"
DUZ = "'"

# Klein'in ic sesi (_italik_). Yalnizca anakronizm denetimi kullanir: dunya
# disi sozcukler anlatici sesinde hata, ic seste serbesttir. (Varyant
# kurallarindaki ses ayrimi kaldirildi; bkz. denetle_varyant.)
IC_SES = re.compile(r"_[^_\n]{3,}_")


def bolum_numarasi(dosya_adi: str) -> int | None:
    m = re.search(r"(\d+)", dosya_adi)
    return int(m.group(1)) if m else None


def diyakritiksiz(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


BASLIK_EK = ":başlık"
_BASLIK_ONEKI = re.compile(r"^Bölüm\s+\d+\s*:\s*")


def bolum_anahtari(ad: str) -> str:
    """'0050.md:başlık' -> '0050.md' (bolum sayimlari icin)."""
    return ad[: -len(BASLIK_EK)] if ad.endswith(BASLIK_EK) else ad


def baslik_adi(baslik: str) -> str:
    """
    'Bölüm 50: İhtiyar Neil'ın ...' -> 'İhtiyar Neil'ın ...'. Onek atilmazsa
    "Bölüm" her baslikta ayni ilgisiz bulguyu uretebilir. Bicime uymayan
    baslik oldugu gibi denetlenir (bicim hatasi takvim_denetle'nin isi).
    """
    return _BASLIK_ONEKI.sub("", baslik, count=1)


def bolumleri_yukle(yollar) -> tuple[dict, dict]:
    """
    ({dosya_adi: govde}, {dosya_adi + BASLIK_EK: baslik_adi}).

    Klasor verilirse icindeki butun bolumler; dosya verilirse yalnizca o
    dosyalar (bulundugu klasor lotm.bolumler_tr ile okunur ve suzulur, her
    klasor bir kez). Boylece hem 'lint _chapters/' hem eski '*.md' cagrisi
    calisir.
    """
    klasorler: dict[Path, set | None] = {}
    for y in map(Path, yollar):
        if y.is_dir():
            klasorler[y.resolve()] = None  # hepsi
        else:
            k = y.resolve().parent
            if klasorler.get(k, set()) is not None:
                klasorler.setdefault(k, set()).add(y.name)

    govdeler, basliklar = {}, {}
    for klasor, isimler in klasorler.items():
        bulunan = set()
        for b in lotm.bolumler_tr(klasor):
            if isimler is not None and b.kaynak not in isimler:
                continue
            bulunan.add(b.kaynak)
            # Satir numaralari DOSYAYA gore olsun: govde front matter'dan
            # sonra basladigi icin eskiden her bulgu editordeki satirdan
            # front matter uzunlugu kadar (genelde 4) geride gorunuyordu.
            # Govdenin onune o kadar bos satir eklemek satir_no'yu duzeltir;
            # baglam bosluklari zaten tek bosluga indirir.
            ham = (klasor / b.kaynak).read_text(encoding="utf-8")
            kayma = (
                ham[: len(ham) - len(b.metin)].count("\n")
                if ham.endswith(b.metin)
                else 0
            )
            govdeler[b.kaynak] = "\n" * kayma + b.metin
            if b.baslik:
                basliklar[b.kaynak + BASLIK_EK] = baslik_adi(b.baslik)
        for eksik in sorted((isimler or set()) - bulunan):
            print(
                f"  uyari: {klasor / eksik} bolum olarak okunmadi "
                f"(uzanti ya da dosya yok)",
                file=sys.stderr,
            )
    return govdeler, basliklar


def satir_no(metin: str, indeks: int) -> int:
    return metin.count("\n", 0, indeks) + 1


def baglam(metin: str, bas: int, son: int, yaricap: int = 55) -> str:
    a = max(0, bas - yaricap)
    b = min(len(metin), son + yaricap)
    return re.sub(r"\s+", " ", metin[a:b]).strip()


def ic_ses_araliklari(metin: str) -> list[tuple[int, int]]:
    """Klein'in _italik_ ic sesi."""
    return [m.span() for m in IC_SES.finditer(metin)]


def ic_seste_mi(araliklar, bas: int) -> bool:
    return any(a <= bas < b for a, b in araliklar)


# ----------------------------------------------------------------------
# Sözlükten kanonik terimleri çıkar
# ----------------------------------------------------------------------


def sozluk_terimleri(yol: Path) -> dict[str, str]:
    """
    terim -> ingilizce eslemesi (mertebeler dahil), lotm.sozluk_yukle ile.

    Eskiden YAML'i burada kendisi ayristiriyordu ve ust duzey adlari
    parantezleriyle birlikte aliyordu: "Ruhanî Âlem (Âlem-i Ervah)" metinde
    hic oldugu gibi gecmedigi icin kapsam olcumu 25 terimi hep "gecmiyor"
    sayiyordu (86 yerine 81).
    """
    return {t.tr: t.en or "" for t in lotm.sozluk_yukle(yol).terimler if t.tr}


# ----------------------------------------------------------------------
# Denetimler
# ----------------------------------------------------------------------


VARYANT_ANAHTARLARI = {
    "kavram",
    "dogru",
    "yanlis",
    "harf_duyarsiz",
    "istisna",
    "not",
    "duzelt",
    "tam_kelime",
}


def varyant_hedefi(kural, yanlis: str) -> str | None:
    """
    Bu yanlis bicim icin OTOMATIK duzeltme hedefi; yoksa None.

    'duzelt' anahtari kural basina acikca verilir (varsayilan: yok):
        duzelt: true                  her 'yanlis' -> 'dogru', harfi harfine
        duzelt: {Firaseti: Firaset'i} yalnizca listelenen bicimler
    Bir kural ancak yanlis bicimin yerine dogru bicim KELIMESI KELIMESINE
    oturuyorsa acilir: "Fırtına Hâkimi" -> "Fırtınalar Hâkimi" oturur;
    "Kaos Çağı'nda" -> "Heyûlâ'da" oturmaz (ek degisir), o kural rapor kalir.
    """
    d = kural.get("duzelt")
    if d is True:
        return kural["dogru"]
    if isinstance(d, dict):
        return d.get(yanlis)
    return None


def _istisnada(metin: str, m, istisnalar, yaricap: int = 80) -> bool:
    """
    Istisna YALNIZ kendi gecisini susturur: istisna kalibinin eslesmesi bu
    gecisi kapsamali, ortmeli ya da hemen bitisik olmali ("şans artırma" +
    "ritüeli"). Eskiden 55 karakterlik baglamda herhangi bir yerde
    gecmesi yetiyordu; "Orta Deniz Ticaret Şirketi"nin hemen ardindaki
    yanlis "Orta Deniz'de" de susuyordu.
    """
    a = max(0, m.start() - yaricap)
    parca = metin[a:m.end() + yaricap]
    for d in istisnalar:
        for e in d.finditer(parca):
            es, ee = e.start() + a, e.end() + a
            # Kapsiyor, ortusuyor ya da hemen bitisik (arada en cok 2 karakter).
            if es <= m.end() + 2 and ee >= m.start() - 2:
                return True
    return False


def varyant_eslesmeleri(metin: str, kural):
    """
    (eslesme, yanlis bicim, baglam) -- denetimin raporladigi her gecis.
    Rapor ve duzeltme ayni eslesmeleri kullanir; ikisi ayrisamaz.
    """
    # Istisnalar harf duyarsiz: cumle basindaki "Şans artırma ritüeli"
    # de kapsanmali. IGNORECASE'in ı/i gevsekligi burada zararsizdir --
    # istisna yalnizca bulguyu SUSTURUR, yeni bulgu uretmez.
    istisnalar = [re.compile(d, re.IGNORECASE) for d in kural.get("istisna", [])]
    # Harf duyarliligi VARSAYILAN OLARAK ACIK. Turkce karsiliklarin cogu
    # gunluk kelimelerden secildigi icin (Yol/yolu, Haz/hazine, San/sansli)
    # duz harf duyarsiz eslesme yanlis pozitif uretir -- yayim_denetle.py
    # v1'in 146 bulgudan 5'inin gercek cikmasinin sebebi tam olarak buydu.
    # Yalnizca terim tek anlamli oldugunda (ritüel, mistisizm) kapatilir.
    # Harf duyarsiz dalda re.IGNORECASE degil tr_desen: IGNORECASE ı ile
    # i'yi ayni harf sayar ve "sira" kurali "sıra"yi yakalardi.
    duyarsiz = bool(kural.get("harf_duyarsiz"))
    # Solda kelime siniri her zaman. Sagda yalniz 'tam_kelime: true' ile:
    # cogu kural ek alan bicimi de yakalamali ("Firasetiydi"), ama
    # "Yaratıcı" kurali "Yaratıcılık"i (yaraticilik) yakalamamali.
    sag = rf"(?![{TR_HARF}])" if kural.get("tam_kelime") else ""
    kapali: list[tuple[int, int]] = []
    for yanlis in sorted(kural["yanlis"], key=len, reverse=True):
        desen = (rf"(?<![{TR_HARF}])"
                 + (tr_desen(yanlis) if duyarsiz else re.escape(yanlis)) + sag)
        for m in re.finditer(desen, metin):
            if any(a <= m.start() < b for a, b in kapali):
                continue
            kapali.append(m.span())
            ctx = baglam(metin, m.start(), m.end())
            if _istisnada(metin, m, istisnalar):
                continue
            yield m, yanlis, ctx


def denetle_varyant(rapor, dosyalar, kurallar):
    """
    'yanlis' listesindeki her gecis hatadir.

    Gecis donemleri (eski karsilik bir bolume kadar dogru, sonra eskimis)
    burada degil: sozluk.yml'de 'eski_karsiliklar' + 'bolum_siniri' olarak
    durur ve yayim_denetle.py denetler (bkz. yayim_denetle.gecis_bolumu).
    Eskiden lint'te 'ogrenme_bolumu' / 'kesin_gecis' anahtarlariyla ayni
    karar ikinci kez tutuluyordu; o anahtarlar artik taninmaz.

    Taninmayan anahtarlar (ogrenme_bolumu, kesin_gecis, sadece_anlatici ya
    da bir yazim hatasi) kural dosyasi hatasi olarak raporlanir; sessizce
    yok sayilmaz -- yoksa kural anlamini degistirerek calisirdi.

    Buradaki gruplar ayni kavramin yazim varyantlaridir.
    """
    for kural in kurallar.get("varyantlar", []):
        bilinmeyen = set(kural) - VARYANT_ANAHTARLARI
        if bilinmeyen:
            rapor.ekle(
                "varyant",
                "lint-kurallari.yml",
                0,
                kural.get("kavram", "?"),
                f"tanınmayan anahtar(lar): {', '.join(sorted(bilinmeyen))} "
                f"[{kural.get('kavram', '?')}] -- kural atlandi",
                agirlik="hata",
            )
            continue

        dogru = kural["dogru"]
        ek_not = kural.get("not", "")
        for ad, metin in sorted(dosyalar.items()):
            for m, yanlis, ctx in varyant_eslesmeleri(metin, kural):
                hedef = varyant_hedefi(kural, yanlis) or dogru
                mesaj = f"“{yanlis}” → “{hedef}”  [{kural['kavram']}]"
                if ek_not:
                    mesaj += f"\n       {ek_not}"
                rapor.ekle(
                    "varyant",
                    ad,
                    satir_no(metin, m.start()),
                    yanlis,
                    mesaj,
                    ctx,
                    agirlik="hata",
                )


def yasakli_deseni(bicim: str) -> re.Pattern:
    """
    Solda sinir her zaman; sagda YALNIZCA cok kelimeli bicimde. Tek kelime
    ek alabilir ("cehliyetini" de yakalanmali) ama "tabi ki" kurali
    "tabi kimseye" icindeki "tabi ki"yi yakalamamali (tâbi = bagli).
    """
    sag = rf"(?![{TR_HARF}])" if " " in bicim.strip() and bicim[-1:].isalpha() else ""
    return re.compile(rf"(?<![{TR_HARF}]){tr_desen(bicim)}{sag}")


def denetle_yasakli(rapor, dosyalar, kurallar):
    for kural in kurallar.get("yasakli", []):
        bicim, yerine = kural["bicim"], kural["yerine"]
        desen = yasakli_deseni(bicim)
        for ad, metin in dosyalar.items():
            for m in desen.finditer(metin):
                rapor.ekle(
                    # "yasaklı" (noktasiz ı) idi: DENETIMLER'deki "yasakli" ile
                    # eslesmedigi icin metin ciktisinda bu bulgular HIC
                    # basilmiyor, yalnizca toplam hata sayisina giriyordu.
                    "yasakli",
                    ad,
                    satir_no(metin, m.start()),
                    m.group(),
                    f"“{m.group()}” terk edilmiş → “{yerine}”",
                    baglam(metin, m.start(), m.end()),
                )


def denetle_diyakritik(rapor, dosyalar, kurallar):
    """
    İki iş yapar:
      (a) Kural dosyasındaki anlam ayırıcı çiftleri şapkasız kullanımda yakalar.
      (b) Tüm metinde, diyakritikleri atıldığında çakışan yazımları otomatik
          bulur — yani kural yazmadan da 'Alem/Âlem' türü sapmayı raporlar.
    """
    for cift in kurallar.get("diyakritik_ciftleri", []):
        for supheli in cift["supheli"]:
            desen = re.compile(rf"(?<![{TR_HARF}]){re.escape(supheli)}(?![{TR_HARF}])")
            for ad, metin in dosyalar.items():
                for m in desen.finditer(metin):
                    rapor.ekle(
                        "diyakritik",
                        ad,
                        satir_no(metin, m.start()),
                        m.group(),
                        f"“{m.group()}” belirsiz: {cift['a']} ({cift['a_anlam']}) "
                        f"mı, {cift['b']} ({cift['b_anlam']}) mi?",
                        baglam(metin, m.start(), m.end()),
                        agirlik="uyari",
                    )

    # (b) otomatik sapma taraması
    #
    # Gruplama diyakritiksiz + küçük harfe indirgenmiş biçime göre yapılır,
    # ama RAPORLAMA yalnızca DİYAKRİTİK farkı varsa yapılır. Aksi hâlde
    # "hâlâ×59, Hâlâ×13" ya da "tezgâhtar×3, Tezgâhtar×3" gibi salt cümle
    # başı büyük harften doğan gürültü listeyi doldurur: ikisi de aynı
    # yazımdır, yalnızca konumları farklıdır. Aranan soru "şapka var mı",
    # "büyük harf mi" değil.
    gruplar: dict[str, Counter] = defaultdict(Counter)
    nerede: dict[str, set] = defaultdict(set)
    for ad, metin in dosyalar.items():
        for m in re.finditer(rf"[{TR_HARF}]+", metin):
            k = m.group()
            # Once kucult, SONRA diyakritigi at. Ters sirada "İ" once "I"ya
            # iner (ustnokta bir birlesen isarettir) ve Turkce kucultme onu
            # "ı" yapar: "İlâveten" ile "ilaveten" ayri gruplara duserdi.
            # Eski casefold tabanli kucultme bunu tesadufen ortuyordu, cunku
            # "I"yi yanlislikla "i" yapiyordu; ayni hata "Işık"i "ışık"tan
            # ayiriyordu.
            anahtar = diyakritiksiz(tr_kucult(k))
            gruplar[anahtar][tr_kucult(k)] += 1
            nerede[anahtar].add(bolum_anahtari(ad))

    # Eşadlılar (adet/âdet, resmi/resmî, tarihi/tarihî, kar/kâr ...) İKİ
    # AYRI KELİMEDİR, bir kelimenin iki yazımı değil: "sekiz adet banknot" ile
    # "eski bir âdet" ikisi de doğrudur. Bu tarama hangisinin kastedildiğini
    # bilemez; her çalıştırmada aynı beş satırı "uyarı" diye basıyordu. Liste
    # sapka.py'den gelir (ESADLI ve NISBET: orada da "elle bakılır" grubu),
    # yani ikinci bir liste tutulmaz; bağlamıyla okumak için sapka --elle.
    try:
        from sapka import ESADLI, NISBET

        esadli = {tr_kucult(k) for k in (*ESADLI, *NISBET)}
    except Exception:  # sapka yoksa eski davranış
        esadli = set()
    atlanan = 0

    for anahtar, yazimlar in sorted(gruplar.items()):
        if len(yazimlar) < 2:
            continue
        if not any(c in y for y in yazimlar for c in "âîûê"):
            continue
        if anahtar in esadli:
            atlanan += 1
            continue
        dokum = ", ".join(f"{f}×{n}" for f, n in yazimlar.most_common())
        rapor.ekle(
            "diyakritik",
            f"({len(nerede[anahtar])} bölüm)",
            0,
            anahtar,
            f"“{anahtar}” için {len(yazimlar)} yazım: {dokum}",
            agirlik="uyari",
        )
    if atlanan:
        print(
            f"  diyakritik: {atlanan} eşadlı çift atlandı (iki ayrı kelime; "
            f"bağlamla okumak için: sapka.py --elle).",
            file=sys.stderr,
        )


def denetle_kesme(rapor, dosyalar, basliklar=None):
    """
    Karisik kesme isareti.

    Dosya basina sayi vermek yetmiyor: kivrik (’) ile duz (') ekranda
    neredeyse ayni gorunur, yani "10 dosyada karisik" bilgisiyle insan
    onlari elle bulamaz. Azinlikta olan bicimin HER GECISI satir numarasiyla
    raporlanir; boylece dogrudan o satira gidilebilir.

    Baslik kendi bolumuyle BIRLIKTE sayilir: govde kivrik, baslik duz ise
    tek basina bakilan iki birim de "temiz" gorunur ama okur ayni sayfada
    iki ayri kesme gorur.
    """
    basliklar = basliklar or {}
    for ad, metin in sorted(dosyalar.items()):
        b_ad = ad + BASLIK_EK
        baslik = basliklar.get(b_ad, "")
        kivrik = metin.count(KIVRIK) + baslik.count(KIVRIK)
        duz = metin.count(DUZ) + baslik.count(DUZ)
        if not (kivrik and duz):
            continue
        azinlik = KIVRIK if kivrik <= duz else DUZ
        adi = "kıvrık ’" if azinlik == KIVRIK else "düz '"
        hedef = "düz '" if azinlik == KIVRIK else "kıvrık ’"
        adet = metin.count(azinlik) + baslik.count(azinlik)
        rapor.ekle(
            "kesme",
            ad,
            0,
            azinlik,
            f"karışık kesme (başlık dahil): düz ×{duz}, kıvrık ×{kivrik} — "
            f"azınlık {adi}, {adet} yerde",
            agirlik="uyari",
        )
        for birim, yazi in ((b_ad, baslik), (ad, metin)):
            for m in re.finditer(re.escape(azinlik), yazi):
                rapor.ekle(
                    "kesme",
                    birim,
                    satir_no(yazi, m.start()),
                    azinlik,
                    f"{adi} → {hedef}",
                    baglam(yazi, m.start(), m.end(), 40),
                    agirlik="uyari",
                )


EK_AILELERI = [
    ("ın", "in", "un", "ün"),
    ("a", "e"),
    ("ı", "i", "u", "ü"),
    ("dan", "den", "tan", "ten"),
    ("da", "de", "ta", "te"),
    # Unluyle biten adlarin kaynastirmali bicimleri (Melissa'nın, Audrey'ye).
    ("nın", "nin", "nun", "nün"),
    ("ya", "ye"),
    ("yı", "yi", "yu", "yü"),
]

# Kaynastirmasiz <-> kaynastirmali es aileler: ayni hal eki. "Melissa'ın"
# hedefini "nın" ailesinde, "Klein'nın" hedefini "ın" ailesinde bulur.
_ES_AILE = {0: 5, 5: 0, 1: 6, 6: 1, 2: 7, 7: 2}


def ek_hedefi(ek: str, dogrular: set) -> tuple[int, str] | None:
    """
    (aile indeksi, dogru ek) -- 'ek' bir aileye dusuyorsa ve o halin
    dogru eki kural dosyasinda tanimliysa. Once kendi ailesi, sonra es
    ailesi (kaynastirma farki) aranir. Tanimli degilse None.
    """
    for i, aile in enumerate(EK_AILELERI):
        if ek in aile:
            for j in (i, _ES_AILE.get(i)):
                if j is None:
                    continue
                h = dogrular & set(EK_AILELERI[j])
                if h:
                    return i, sorted(h)[0]
            return None
    return None


def denetle_ek_uyumu(rapor, dosyalar, kurallar=None):
    """
    Özel adlara gelen eklerin ünlü uyumu.
    """
    ayar = (kurallar or {}).get("ozel_adlar", {}) or {}
    adlar = list(ayar) or [
        "Klein",
        "Dunn",
        "Benson",
        "Welch",
        "Melissa",
        "Audrey",
        "Alger",
        "Naya",
        "Rozanne",
    ]

    aileler = EK_AILELERI

    for ad_ozel in adlar:
        dogrular = set((ayar.get(ad_ozel) or {}).get("dogru_ekler") or [])
        bicimler: dict[str, list] = defaultdict(list)

        for ad, metin in sorted(dosyalar.items()):
            for m in re.finditer(
                rf"(?<![{TR_HARF}]){re.escape(ad_ozel)}['{KIVRIK}]([{TR_HARF}]+)", metin
            ):
                bicimler[m.group(1)].append(
                    (ad, satir_no(metin, m.start()), baglam(metin, m.start(), m.end()))
                )

        # Tanimli ad: her ek kendi halinin dogru ekine bakar (es aile dahil).
        if dogrular:
            sayim = {e: len(v) for e, v in bicimler.items() if ek_hedefi(e, dogrular)}
            for ek in sorted(bicimler):
                h = ek_hedefi(ek, dogrular)
                if not h or h[1] == ek:
                    continue
                for dosya, satir, ctx in bicimler[ek]:
                    rapor.ekle(
                        "ek-uyumu", dosya, satir, f"{ad_ozel}'{ek}",
                        f"“{ad_ozel}'{ek}” → “{ad_ozel}'{h[1]}”  (kural dosyasında tanımlı; sayım {sayim})",
                        ctx, agirlik="hata",
                    )
            continue

        # Tanimsiz ad: aile icinde cogunluk -- TAHMIN.
        for aile in aileler:
            mevcut = [e for e in aile if e in bicimler]
            if len(mevcut) < 2:
                continue
            sayim = {e: len(bicimler[e]) for e in mevcut}
            hedef = max(sayim, key=sayim.get)
            for ek in mevcut:
                if ek == hedef:
                    continue
                for dosya, satir, ctx in bicimler[ek]:
                    rapor.ekle(
                        "ek-uyumu", dosya, satir, f"{ad_ozel}'{ek}",
                        f"“{ad_ozel}'{ek}” → “{ad_ozel}'{hedef}”  (çoğunluk — TAHMİN, doğrulayın; sayım {sayim})",
                        ctx, agirlik="uyari",
                    )


# ----------------------------------------------------------------------
# Özel ad adayları: ek alan ama kuralı olmayan adlar
# ----------------------------------------------------------------------

_AD_EKLI = re.compile(
    rf"(?<![{TR_HARF}])([A-Z][a-zâîûê]+(?:-[A-Z][a-z]+)?)['{KIVRIK}]([{TR_HARF}]+)"
)
_TURKCE_HARF = set("çğıöşüÇĞİÖŞÜ")
_SERT = set("çfhkpsşt")
_UNLU = "aeıioöuü"
# Son unluye gore (tamlayan, yonelme, belirtme) -- buyuk unlu uyumu.
_UYUM = {"a": ("ın", "a", "ı"), "ı": ("ın", "a", "ı"), "o": ("un", "a", "u"),
         "u": ("un", "a", "u"), "e": ("in", "e", "i"), "i": ("in", "e", "i"),
         "ö": ("ün", "e", "ü"), "ü": ("ün", "e", "ü")}


_ONERI_UNLU = {"ı": ("ı", "a"), "u": ("u", "a"), "i": ("i", "e"), "ü": ("ü", "e")}


def ek_onerisi(ad: str, gorulen: Counter) -> tuple[list, str]:
    """
    (dogru_ekler onerisi, kaynak). Uc ozellik ayri ayri belirlenir ve beş
    ek onlardan TUTARLI uretilir: unlu (ı/u/i/ü), kaynastirma (unluyle
    biten ad: nın/ya/yı), sertlik (-tan/-ta). Her ozellik once metinde
    goruldugu gibi (cogunluk), gorulmediyse yazimdan TAHMIN edilir. Yazim
    telaffuzu tam gostermez (Royale, Joyce): oneridir, karar sizin.
    """
    k = tr_kucult(ad)
    unluler = [c for c in k if c in _UNLU]
    tahmin_unlu = _UYUM[unluler[-1] if unluler else "a"][2]
    unlu_oy, kalin_oy, kay_oy, sert_oy = Counter(), Counter(), Counter(), Counter()
    for ek, n in gorulen.items():
        for i, aile in enumerate(EK_AILELERI):
            if ek not in aile:
                continue
            if i in (0, 2, 5, 7):  # tamlayan / belirtme: unluyu tam soyler
                unlu_oy[ek.lstrip("ny")[0]] += n
            else:  # yonelme / ayrilma / bulunma: yalniz kalin-ince
                kalin_oy["a" in ek] += n
            if i in (0, 1, 2):
                kay_oy[False] += n
            elif i in (5, 6, 7):
                kay_oy[True] += n
            if i in (3, 4):
                sert_oy[ek[0] == "t"] += n
    kaynak = 0
    if unlu_oy:
        unlu = unlu_oy.most_common(1)[0][0]
        kaynak += 1
    elif kalin_oy:
        kalin = kalin_oy.most_common(1)[0][0]
        unlu = tahmin_unlu if (tahmin_unlu in "ıu") == kalin else ("ı" if kalin else "i")
        kaynak += 1
    else:
        unlu = tahmin_unlu
    if kay_oy:
        kay = kay_oy.most_common(1)[0][0]
        kaynak += 1
    else:
        kay = k[-1] in _UNLU or (k[-1] == "y" and len(k) > 1 and k[-2] in _UNLU)
    if sert_oy:
        sert = sert_oy.most_common(1)[0][0]
        kaynak += 1
    else:
        sert = k[-1] in _SERT
    v, a = _ONERI_UNLU[unlu]
    n_, y_ = ("n", "y") if kay else ("", "")
    d = "t" if sert else "d"
    oneri = [f"{n_}{v}n", f"{y_}{a}", f"{y_}{v}", f"{d}{a}n", f"{d}{a}"]
    return oneri, ("metinden" if kaynak == 3 else "metin + tahmin" if kaynak else "tahmin")


def turkce_adlar(sozluk_yolu=None, kelimeler_yolu=None) -> set:
    """
    Sozlukte ve words.md'de TURKCE olan ad parcalari: Turkce adinda gecip
    Ingilizcesinde gecmeyen kelimeler (Basiret/Spirit Vision, Semti, Efendi).
    Tingen / Tingen gibi Ingilizcesiyle ayni yazilan adlar disarida kalir:
    onlar yabanci addir, kural isteyebilir.
    """
    ciftler = []
    try:
        if sozluk_yolu and Path(sozluk_yolu).exists():
            ciftler += list(sozluk_terimleri(Path(sozluk_yolu)).items())
    except Exception:
        pass
    if kelimeler_yolu and Path(kelimeler_yolu).exists():
        for satir in Path(kelimeler_yolu).read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*-\s*\*\*(.+?)\*\*\s*(?:—|-|:)?\s*([^(;]*)", satir)
            if m:
                ciftler.append((m.group(1), m.group(2)))
    out = set()
    for tr, en in ciftler:
        en_k = set(re.findall(r"[A-Za-z]+", en or ""))
        for w in re.findall(rf"[{TR_HARF}]+", tr or ""):
            if w[:1].isupper() and w not in en_k:
                out.add(w)
    return out


def ozel_ad_adaylari(dosyalar, kurallar, turkce: set | None = None) -> list:
    """
    [(ad, toplam, bolum_sayisi, ek sayimi)] -- kesmeyle ek alan, ama
    ozel_adlar'da kurali olmayan adlar. Elenir: Turkce harf iceren
    kelimeler (Soytarı, Kilise), metinde kucuk harfle de gecen kelimeler
    (Adam/adam, Kaptan/kaptan), sozlukteki Turkce ad parcalari (bkz.
    turkce_adlar), 'ozel_ad_disi' listesi, esigin altindakiler.
    """
    ayar = kurallar.get("ozel_adlar") or {}
    disi = set(kurallar.get("ozel_ad_disi") or []) | (turkce or set())
    esik = int(kurallar.get("ozel_ad_esik") or 3)
    sayim, bolum, ekler = Counter(), defaultdict(set), defaultdict(Counter)
    for ad, metin in dosyalar.items():
        for m in _AD_EKLI.finditer(metin):
            w = m.group(1)
            if w in ayar or w in disi or _TURKCE_HARF & set(w):
                continue
            sayim[w] += 1
            bolum[w].add(bolum_anahtari(ad))
            ekler[w][m.group(2)] += 1
    if not sayim:
        return []
    birlesik = "\n".join(dosyalar.values())
    kucuk = {tr_kucult(w) for w in sayim}
    var = {k for k in kucuk
           if re.search(rf"(?<![{TR_HARF}]){re.escape(k)}(?![{TR_HARF}])", birlesik)}
    return sorted(
        ((w, n, len(bolum[w]), ekler[w]) for w, n in sayim.items()
         if n >= esik and tr_kucult(w) not in var),
        key=lambda t: (-t[1], t[0]))


def denetle_ozel_ad(rapor, dosyalar, kurallar, turkce=None):
    adaylar = ozel_ad_adaylari(dosyalar, kurallar, turkce)
    oneriler = []
    for w, n, nb, ekler in adaylar:
        oneri, kaynak = ek_onerisi(w, ekler)
        oneriler.append((w, oneri, kaynak))
        dokum = ", ".join(f"{e}×{k}" for e, k in ekler.most_common(6))
        rapor.ekle(
            "ozel-ad", f"({nb} bölüm)", 0, w,
            f"{w} ×{n}, kuralı yok — ekler: {dokum}  → öneri ({kaynak}): "
            f"{', '.join(oneri)}",
            agirlik="bilgi",
        )
    rapor.olcumler["ozel_ad"] = oneriler


def anakronizm_kurallari(kurallar) -> list:
    """
    [(kelime, [kaynak_karsiligi, ...])].

    Kural dosyasinda iki bicim de gecerli:
        - "internet"                      (kaynak denetimi yok)
        - {kelime: metre, kaynak: [米]}   (kaynakta varsa bulgu degil)
    """
    out = []
    for g in (kurallar.get("anakronizm") or {}).get("sadece_ic_ses") or []:
        if isinstance(g, str):
            out.append((g, []))
        elif g.get("kelime"):
            out.append((g["kelime"], list(g.get("kaynak") or [])))
    return out


def kaynak_metinleri(dosyalar) -> dict:
    """
    {dosya_adi: Cince govde}. Ham metinler yoksa BOS doner ve denetim
    bugunku (kaynaksiz) davranisina duser. Baslik birimleri ("…:başlık")
    kendi bolumlerinin Cincesini alir.
    """
    try:
        zh = lotm.bolum_sozlugu(lotm.bolumler_zh())
    except (FileNotFoundError, OSError) as e:
        # --kaynak acikca istendi; sessizce kaynaksiz calismak "kaynakta
        # karsiligi var" elemesinin hic yapilmadigini gizlerdi.
        print(f"  uyari: --kaynak: Cince metin okunamadi ({e}); "
              f"anakronizm kaynaksiz denetlendi.", file=sys.stderr)
        return {}

    out = {}
    for ad in dosyalar:
        no = bolum_numarasi(ad)
        b = zh.get(no) if no is not None else None
        if b:
            out[ad] = b.metin
    return out


def denetle_anakronizm(rapor, dosyalar, kurallar, kaynaklar=None):
    """
    Dunya disi sozcukler anlatici sesinde.

    KAYNAK DENETIMI
    ---------------
    Anakronizm KAYNAK DUNYANIN ozelligidir, cevirinin degil. Bolum 43'te
    Cince metin dogrudan "公里" diyor; "kilometresi dört peni" sadik bir
    ceviridir, bulgu degil. Kaynaga bakmayan bir kural burada yazari
    sorgular, cevirmeni degil.

    Bu denetim yalnizca BOLUM DUZEYINDE ortak gecise bakar -- terim bu
    bolumun Cincesinde geciyor mu. Paragraf kimligi gerekmez, dolayisiyla
    hizalama kaymasindan hic etkilenmez.

    Kaynak yoksa (kaynaklar bos) denetim eskisi gibi calisir.
    """
    kaynaklar = kaynaklar or {}
    kelimeler = anakronizm_kurallari(kurallar)
    elenen = 0
    for ad, metin in dosyalar.items():
        araliklar = ic_ses_araliklari(metin)
        kaynak = kaynaklar.get(ad, "")
        for kelime, kaynak_karsiliklari in kelimeler:
            if kaynak and any(k in kaynak for k in kaynak_karsiliklari):
                elenen += 1
                continue
            desen = re.compile(rf"(?<![{TR_HARF}]){tr_desen(kelime)}")
            for m in desen.finditer(metin):
                if ic_seste_mi(araliklar, m.start()):
                    continue
                rapor.ekle(
                    "anakronizm",
                    ad,
                    satir_no(metin, m.start()),
                    m.group(),
                    f"“{m.group()}” anlatıcı sesinde — dünya dışı sözcük "
                    f"yalnızca Klein'ın iç sesinde serbest",
                    baglam(metin, m.start(), m.end()),
                    agirlik="uyari",
                )
    if elenen:
        print(
            f"  anakronizm: {elenen} kelime/bölüm çifti kaynakta karşılığı "
            f"olduğu için elendi.",
            file=sys.stderr,
        )


def denetle_register(rapor, dosyalar, kurallar):
    """
    Bölüm başına arkaik sözcük yoğunluğu.

    Eşleşme ŞAPKASIZ biçim üzerinden yapılır. Aksi hâlde ölçüm imlaya
    duyarlı olur: "sükunet" kök listesindeki "sükûnet" ile eşleşmediği için,
    yalnızca şapkaları düzeltmek — metne tek kelime eklemeden — yoğunluğu
    yükseltir. Bir izleme metriğinin, ölçtüğü şeyle ilgisi olmayan bir
    düzeltmeden etkilenmemesi gerekir.
    """
    ayar = kurallar.get("register", {})
    kokler = ayar.get("sozcukler", "").split()
    if not kokler:
        return
    # Kokler ve metin AYNI yoldan gecer: once Turkce kucultme, sonra
    # diyakritik atma; arama harf duyarli. Eskiden ikisi diyakritiksiz
    # hale getirilip re.IGNORECASE ile araniyordu, o da ı ile i'yi
    # ayni harf sayiyordu.
    desen = re.compile(
        r"(?<![^\W_])("
        + "|".join(re.escape(diyakritiksiz(tr_kucult(k))[:6]) for k in kokler)
        + r")\w*"
    )
    alt, ust = ayar.get("hedef_alt", 3.0), ayar.get("hedef_ust", 10.0)
    olcum = {}
    for ad, metin in sorted(dosyalar.items()):
        kelime_sayisi = len(metin.split())
        if not kelime_sayisi:
            continue
        yogunluk = (
            len(desen.findall(diyakritiksiz(tr_kucult(metin)))) * 1000 / kelime_sayisi
        )
        olcum[ad] = round(yogunluk, 1)
        if yogunluk > ust:
            rapor.ekle(
                "register",
                ad,
                0,
                f"{yogunluk:.1f}",
                f"arkaik yoğunluk {yogunluk:.1f}/1000 — hedef bant "
                f"{alt}–{ust}. Ayin, ilahi unvan veya kozmoloji sahnesi "
                f"değilse gözden geçirin.",
                agirlik="uyari",
            )
    rapor.olcumler["register"] = olcum


def denetle_sozluk_kapsami(rapor, dosyalar, terimler):
    """Sözlükteki hangi terimler metinde hiç geçmiyor / hangileri geçiyor."""
    birlesik = "\n".join(dosyalar.values())
    gecen = {t for t in terimler if len(t) > 3 and t in birlesik}
    rapor.olcumler["sozluk"] = {
        "toplam_terim": len(terimler),
        "metinde_gecen": len(gecen),
        "gecenler": sorted(gecen),
    }



# ----------------------------------------------------------------------
# Otomatik düzeltme
# ----------------------------------------------------------------------
#
# Bu betik dosya YAZMAZ. duzeltme_plani() bellekte yeni metni kurar;
# yazmak, fark gostermek ve yedeklemek duzelt.py'nin isidir
# (./calistir.sh duzelt). Tek yazma yolu var ki yedek hic atlanmasin.
#
# KESIN sayilanlar (bulgunun kendisi tek dogru sonucu soyluyor):
#   varyant   yalniz 'duzelt' anahtari olan kurallar (bkz. varyant_hedefi)
#   yasakli   'bicim' -> 'yerine', buyuk harf korunur; kural 'duzelt: false'
#             ile kapatilabilir
#   ek-uyumu  yalniz 'dogru_ekler'i tanimli adlar (hata duzeyi). Hal
#             basina tek dogru ek; kaynastirma farki da kapsanir
#             ("Melissa'ın" -> "Melissa'nın", tanimda "nın" varsa).
# Geri kalan her sey (diyakritik, kesme, anakronizm, register, cogunluk
# TAHMINI ek-uyumu) rapor kalir. Kesme isareti bicim_denetle B02'nin isi.

@dataclass
class Onerge:
    kural: str
    bas: int  # HAM dosya metninde
    son: int
    yeni: str
    eski: str
    satir: int


_BASLIK_SATIRI = re.compile(r"^title[ \t]*:[ \t]*(.*?)[ \t]*$", re.M)


def _harf_tasi(ornek: str, hedef: str) -> str:
    """Eslesmenin bas harfi buyukse hedefin de (Turkce: i -> İ)."""
    if ornek[:1].isupper() and hedef[:1].islower():
        from turkce import tr_buyut
        return tr_buyut(hedef)
    return hedef


def _bolgeler(ham: str) -> list[tuple[int, str]]:
    """
    (ham metindeki baslangic, metin) -- duzeltilebilir bolgeler: govde ve
    front matter'daki baslik degeri ("Bölüm N: " oneki ve tirnaklar
    disinda). Front matter'in geri kalani (date, layout) bolge degildir.
    """
    fm = lotm.FRONT_MATTER.match(ham)
    bolgeler = [(fm.end() if fm else 0, ham[fm.end():] if fm else ham)]
    if fm:
        m = _BASLIK_SATIRI.search(ham, 0, fm.end())
        if m:
            bas, deger = m.start(1), m.group(1)
            if len(deger) >= 2 and deger[0] == deger[-1] and deger[0] in "\"'":
                bas, deger = bas + 1, deger[1:-1]
            onek = _BASLIK_ONEKI.match(deger)
            if onek:
                bas, deger = bas + onek.end(), deger[onek.end():]
            bolgeler.append((bas, deger))
    return bolgeler


def metin_onergeleri(metin: str, kurallar) -> list[tuple[int, int, str, str]]:
    """Tek bir metin parcasi icin (bas, son, yeni, kural) onergeleri."""
    out = []
    for kural in kurallar.get("varyantlar", []) or []:
        if set(kural) - VARYANT_ANAHTARLARI or not kural.get("duzelt"):
            continue
        for m, yanlis, _ctx in varyant_eslesmeleri(metin, kural):
            hedef = varyant_hedefi(kural, yanlis)
            if hedef:
                out.append((m.start(), m.end(), _harf_tasi(m.group(), hedef), "varyant"))
    for kural in kurallar.get("yasakli", []) or []:
        if kural.get("duzelt") is False or not kural.get("yerine"):
            continue
        for m in yasakli_deseni(kural["bicim"]).finditer(metin):
            out.append((m.start(), m.end(), _harf_tasi(m.group(), kural["yerine"]), "yasakli"))
    for ad_ozel, ayar in ((kurallar.get("ozel_adlar") or {}) or {}).items():
        dogrular = set((ayar or {}).get("dogru_ekler") or [])
        if not dogrular:
            continue
        desen = re.compile(
            rf"(?<![{TR_HARF}]){re.escape(ad_ozel)}['{KIVRIK}]([{TR_HARF}]+)(?![{TR_HARF}])"
        )
        for m in desen.finditer(metin):
            h = ek_hedefi(m.group(1), dogrular)
            if h and h[1] != m.group(1):
                out.append((m.start(1), m.end(1), h[1], "ek-uyumu"))
    return out


def duzeltme_plani(ham: str, kurallar) -> tuple[str, list[Onerge]]:
    """
    Bir bolum dosyasinin HAM metni -> (duzeltilmis metin, onergeler).
    Cakisan onergelerden once baslayan kalir (ayni yere iki kural).
    """
    onergeler = []
    for bas, metin in _bolgeler(ham):
        for a, b, yeni, kural in metin_onergeleri(metin, kurallar):
            if metin[a:b] != yeni:
                onergeler.append(Onerge(kural, bas + a, bas + b, yeni,
                                        metin[a:b], satir_no(ham, bas + a)))
    onergeler.sort(key=lambda o: (o.bas, -o.son))
    temiz, son = [], -1
    for o in onergeler:
        if o.bas >= son:
            temiz.append(o)
            son = o.son
    yeni = ham
    for o in reversed(temiz):
        yeni = yeni[: o.bas] + o.yeni + yeni[o.son :]
    return yeni, temiz


def kelime_icinde(ham: str, o: Onerge) -> tuple[str, str]:
    """Onergeyi butun kelimesiyle: "in" -> "ın" yerine "Alger'in" -> "Alger'ın"."""
    kel = rf"[{TR_HARF}'{KIVRIK}]"
    a = o.bas
    while a > 0 and re.match(kel, ham[a - 1]):
        a -= 1
    b = o.son
    while b < len(ham) and re.match(kel, ham[b]):
        b += 1
    return ham[a:b], ham[a:o.bas] + o.yeni + ham[o.son:b]


def onizleme_yaz(yollar, kurallar) -> int:
    """--duzelt: ne degisecegini satir satir gosterir; YAZMAZ."""
    toplam = 0
    for yol in yollar:
        ham = yol.read_text(encoding="utf-8")
        _yeni, onergeler = duzeltme_plani(ham, kurallar)
        for o in onergeler:
            ctx = baglam(ham, o.bas, o.son, 40)
            eski, yeni = kelime_icinde(ham, o)
            print(f"  {yol.name}:{o.satir}  {o.kural}  “{eski}” → “{yeni}”\n       … {ctx} …")
        toplam += len(onergeler)
    print(f"\n{toplam} kesin düzeltme. Yazmak için:  ./calistir.sh duzelt lint --uygula")
    # Bekleyen duzeltme = cikis 1 (lint'in "bulgu var" sozlesmesi; kanca bunu kullanir).
    return 1 if toplam else 0


def _dosya_yollari(yollar) -> list[Path]:
    out = []
    for y in map(Path, yollar):
        if y.is_dir():
            out += sorted(p for p in y.iterdir() if p.suffix.lower() == ".md")
        else:
            out.append(y)
    return out

# ----------------------------------------------------------------------
# Ana akış
# ----------------------------------------------------------------------

def _fark_kaydi(b: Bulgu) -> tuple:
    """
    fark.py icin (anahtar, gorunum). Anahtar satir numarasi ve SAYI icermez:
      register     yogunluk degeri her duzenlemede degisir -> (kural, dosya)
      diyakritik   ozet satirinin 'dosyasi' "(12 bölüm)" bir sayidir
                   -> (kural, yazim anahtari)
      digerleri    (kural, dosya, bulunan, baglam)
    """
    if b.kural == "register":
        anahtar = (b.kural, b.dosya)
    elif b.dosya.startswith("("):
        anahtar = (b.kural, b.bulunan)
    else:
        anahtar = (b.kural, b.dosya, b.bulunan, b.baglam)
    konum = b.dosya if not b.satir else f"{b.dosya}:{b.satir}"
    return anahtar, f"[{konum}] {b.kural} {b.agirlik}: {b.mesaj.splitlines()[0]}"


DENETIMLER = [
    "varyant",
    "yasakli",
    "diyakritik",
    "kesme",
    "ek-uyumu",
    "anakronizm",
    "register",
    "ozel-ad",
]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="LotM Türkçe çevirisi tutarlılık denetleyicisi"
    )
    ap.add_argument("bolumler", nargs="+", help="bölüm .md dosyaları ya da klasörü")
    # Varsayilanlar gercek yollar. Eskiden cwd'ye gore "sozluk.yml" /
    # "lint-kurallari.yml" idi ve bulunamazsa sessizce bos kurallarla
    # calisip "0 hata" diyordu.
    ap.add_argument("--sozluk", type=Path, default=lotm.SOZLUK_YOLU)
    ap.add_argument(
        "--kurallar", type=Path, default=Path(__file__).resolve().parent / "lint-kurallari.yml"
    )
    ap.add_argument("--sadece", default="", help=f"virgülle: {','.join(DENETIMLER)}")
    ap.add_argument("--format", choices=["metin", "json"], default="metin")
    ap.add_argument("--bulgular", default=None, help="bulgulari fark.py icin TSV olarak yaz")
    ap.add_argument(
        "--kaynak",
        action="store_true",
        help="anakronizm denetiminde Çince kaynağa da bak "
        "(lotm.py gerektirir; yoksa sessizce atlanır)",
    )
    ap.add_argument(
        "--duzelt",
        action="store_true",
        help="kesin düzeltmeleri göster (hiçbir dosya değişmez; yazmak: "
        "./calistir.sh duzelt lint --uygula). Bekleyen varsa çıkış 1",
    )
    args = ap.parse_args()

    if not args.kurallar.exists():
        sys.exit(f"HATA: kural dosyasi yok: {args.kurallar}")
    kurallar = yaml.safe_load(args.kurallar.read_text(encoding="utf-8")) or {}
    if args.duzelt:
        return onizleme_yaz(_dosya_yollari(args.bolumler), kurallar)
    if args.sozluk.exists():
        terimler = sozluk_terimleri(args.sozluk)
    else:
        print(f"  uyari: sozluk yok ({args.sozluk}); kapsam olculmedi", file=sys.stderr)
        terimler = {}

    try:
        dosyalar, basliklar = bolumleri_yukle(args.bolumler)
    except (FileNotFoundError, OSError) as e:
        sys.exit(f"HATA: {e}")
    if not dosyalar:
        sys.exit("HATA: okunacak bölüm bulunamadı")
    # Dil denetimleri gövdeye VE başlığa bakar; ölçümler yalnızca gövdeye.
    metinler = {**dosyalar, **basliklar}

    secili = set(args.sadece.split(",")) if args.sadece else set(DENETIMLER)
    rapor = Rapor()

    if "varyant" in secili:
        denetle_varyant(rapor, metinler, kurallar)
    if "yasakli" in secili:
        denetle_yasakli(rapor, metinler, kurallar)
    if "diyakritik" in secili:
        denetle_diyakritik(rapor, metinler, kurallar)
    if "kesme" in secili:
        denetle_kesme(rapor, dosyalar, basliklar)
    if "ek-uyumu" in secili:
        denetle_ek_uyumu(rapor, metinler, kurallar)
    if "anakronizm" in secili:
        denetle_anakronizm(
            rapor,
            metinler,
            kurallar,
            kaynak_metinleri(metinler) if args.kaynak else None,
        )
    if "register" in secili:
        denetle_register(rapor, dosyalar, kurallar)
    if "ozel-ad" in secili:
        denetle_ozel_ad(rapor, metinler, kurallar,
                        turkce_adlar(args.sozluk, lotm.KELIMELER))
    if terimler:
        denetle_sozluk_kapsami(rapor, dosyalar, terimler)

    if args.bulgular:
        lotm.bulgulari_yaz(args.bulgular, [_fark_kaydi(b) for b in rapor.bulgular])

    if args.format == "json":
        print(
            json.dumps(
                {
                    "bulgular": [asdict(b) for b in rapor.bulgular],
                    "olcumler": rapor.olcumler,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if any(b.agirlik == "hata" for b in rapor.bulgular) else 0

    gruplu = defaultdict(list)
    for b in rapor.bulgular:
        gruplu[b.kural].append(b)

    # DENETIMLER'de olmayan bir kural adi (yazim farki) bulgularini
    # gizlememeli: sona eklenir, sessizce dusmez.
    for kural in DENETIMLER + sorted(set(gruplu) - set(DENETIMLER)):
        if kural not in gruplu:
            continue
        blok = gruplu[kural]
        print(f"\n{'─' * 72}\n{kural.upper()}  ({len(blok)})\n{'─' * 72}")
        for b in blok:
            print(b.satir_olarak())

    if "register" in rapor.olcumler:
        print(f"\n{'─' * 72}\nARKAİK YOĞUNLUK (sözcük/1000)\n{'─' * 72}")
        for ad, deger in sorted(
            rapor.olcumler["register"].items(), key=lambda kv: -kv[1]
        ):
            cubuk = "█" * int(deger)
            print(f"   {ad:>12}  {deger:5.1f}  {cubuk}")

    if rapor.olcumler.get("ozel_ad"):
        print(f"\n{'─' * 72}\nÖZEL AD ADAYLARI — lint-kurallari.yml › ozel_adlar'a yapıştırmaya hazır\n"
              f"(önerileri telaffuza göre okuyun; ad değilse ozel_ad_disi listesine ekleyin)\n{'─' * 72}")
        for w, oneri, kaynak in rapor.olcumler["ozel_ad"]:
            print(f"  {w}:\n    dogru_ekler: {json.dumps(oneri, ensure_ascii=False)}  # {kaynak}")

    if "sozluk" in rapor.olcumler:
        s = rapor.olcumler["sozluk"]
        print(f"\n{'─' * 72}\nSÖZLÜK KAPSAMI\n{'─' * 72}")
        print(
            f"   {s['metinde_gecen']}/{s['toplam_terim']} terim bu bölümlerde geçiyor"
        )

    hata = sum(1 for b in rapor.bulgular if b.agirlik == "hata")
    uyari = sum(1 for b in rapor.bulgular if b.agirlik == "uyari")
    aday = len(rapor.olcumler.get("ozel_ad") or [])
    print(
        f"\n{'═' * 72}\n{hata} hata, {uyari} uyarı, {aday} özel ad adayı — {len(dosyalar)} bölüm"
        f" ({len(basliklar)} başlık)\n"
    )
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
