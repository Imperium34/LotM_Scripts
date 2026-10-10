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
    """terim -> ingilizce eşlemesi. Mertebe adlarını da toplar."""
    veri = yaml.safe_load(yol.read_text(encoding="utf-8"))
    cikti: dict[str, str] = {}
    for girdi in veri:
        t = girdi.get("terim")
        if t:
            cikti[t] = girdi.get("ingilizce", "")
        for m in girdi.get("mertebeler", []) or []:
            isim = m.get("isim", "")
            eslesme = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", isim)
            if eslesme:
                cikti[eslesme.group(1).strip()] = eslesme.group(2).strip()
            elif isim:
                cikti[isim.strip()] = ""
    return cikti


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
}


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
        yanlislar = sorted(kural["yanlis"], key=len, reverse=True)

        for ad, metin in sorted(dosyalar.items()):
            kapali: list[tuple[int, int]] = []

            for yanlis in yanlislar:
                desen = tr_desen(yanlis) if duyarsiz else re.escape(yanlis)
                for m in re.finditer(desen, metin):
                    if any(a <= m.start() < b for a, b in kapali):
                        continue
                    kapali.append(m.span())
                    ctx = baglam(metin, m.start(), m.end())
                    if any(d.search(ctx) for d in istisnalar):
                        continue
                    mesaj = f"“{yanlis}” → “{dogru}”  [{kural['kavram']}]"
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


def denetle_yasakli(rapor, dosyalar, kurallar):
    for kural in kurallar.get("yasakli", []):
        bicim, yerine = kural["bicim"], kural["yerine"]
        desen = re.compile(rf"(?<![{TR_HARF}]){tr_desen(bicim)}")
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

    aileler = [
        ("ın", "in", "un", "ün"),
        ("a", "e"),
        ("ı", "i", "u", "ü"),
        ("dan", "den", "tan", "ten"),
        ("da", "de", "ta", "te"),
        ("nın", "nin"),
    ]

    for ad_ozel in adlar:
        dogrular = set((ayar.get(ad_ozel) or {}).get("dogru_ekler") or [])
        bicimler: dict[str, list] = defaultdict(list)

        for ad, metin in sorted(dosyalar.items()):
            for m in re.finditer(rf"{ad_ozel}['{KIVRIK}]([{TR_HARF}]+)", metin):
                bicimler[m.group(1)].append(
                    (ad, satir_no(metin, m.start()), baglam(metin, m.start(), m.end()))
                )

        for aile in aileler:
            mevcut = [e for e in aile if e in bicimler]
            if not mevcut:
                continue

            sayim = {e: len(bicimler[e]) for e in mevcut}

            hedef_kumesi = dogrular & set(aile)

            if hedef_kumesi:
                hedef = sorted(hedef_kumesi)[0]
                aciklama, agirlik = "kural dosyasında tanımlı", "hata"
            else:
                if len(mevcut) < 2:
                    continue
                hedef = max(sayim, key=sayim.get)
                aciklama, agirlik = "çoğunluk — TAHMİN, doğrulayın", "uyari"

            for ek in mevcut:
                if ek == hedef:
                    continue
                for dosya, satir, ctx in bicimler[ek]:
                    rapor.ekle(
                        "ek-uyumu",
                        dosya,
                        satir,
                        f"{ad_ozel}'{ek}",
                        f"“{ad_ozel}'{ek}” → “{ad_ozel}'{hedef}”  ({aciklama}; sayım {sayim})",
                        ctx,
                        agirlik=agirlik,
                    )


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
    except Exception:
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
# Ana akış
# ----------------------------------------------------------------------

DENETIMLER = [
    "varyant",
    "yasakli",
    "diyakritik",
    "kesme",
    "ek-uyumu",
    "anakronizm",
    "register",
]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="LotM Türkçe çevirisi tutarlılık denetleyicisi"
    )
    ap.add_argument("bolumler", nargs="+", help="bölüm .md dosyaları ya da klasörü")
    ap.add_argument("--sozluk", type=Path, default=Path("sozluk.yml"))
    ap.add_argument("--kurallar", type=Path, default=Path("lint-kurallari.yml"))
    ap.add_argument("--sadece", default="", help=f"virgülle: {','.join(DENETIMLER)}")
    ap.add_argument("--format", choices=["metin", "json"], default="metin")
    ap.add_argument(
        "--kaynak",
        action="store_true",
        help="anakronizm denetiminde Çince kaynağa da bak "
        "(lotm.py gerektirir; yoksa sessizce atlanır)",
    )
    args = ap.parse_args()

    kurallar = (
        yaml.safe_load(args.kurallar.read_text(encoding="utf-8"))
        if args.kurallar.exists()
        else {}
    )
    terimler = sozluk_terimleri(args.sozluk) if args.sozluk.exists() else {}

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
    if terimler:
        denetle_sozluk_kapsami(rapor, dosyalar, terimler)

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

    if "sozluk" in rapor.olcumler:
        s = rapor.olcumler["sozluk"]
        print(f"\n{'─' * 72}\nSÖZLÜK KAPSAMI\n{'─' * 72}")
        print(
            f"   {s['metinde_gecen']}/{s['toplam_terim']} terim bu bölümlerde geçiyor"
        )

    hata = sum(1 for b in rapor.bulgular if b.agirlik == "hata")
    uyari = sum(1 for b in rapor.bulgular if b.agirlik == "uyari")
    print(
        f"\n{'═' * 72}\n{hata} hata, {uyari} uyarı — {len(dosyalar)} bölüm"
        f" ({len(basliklar)} başlık)\n"
    )
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
