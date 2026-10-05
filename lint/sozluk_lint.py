#!/usr/bin/env python3
"""
sozluk_lint.py — LotM Türkçe çevirisi için tutarlılık denetleyicisi.

Okuyarak yakalanamayan hata sınıfını hedefler: dosyalar arası terim kayması,
diyakritik tutarsızlığı, birim sızması, kesme işareti karışıklığı, register
sapması. Bunların hiçbiri tek bir bölümü dikkatle okuyarak görülemez, çünkü
kanıt her zaman başka bir dosyadadır.

Kullanım:
    python3 sozluk_lint.py --sozluk sozluk.yml --kurallar lint-kurallari.yml BOLUMLER...
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
        bas = f"{isaret} {self.dosya}:{self.satir}"
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

# Klein'in ic sesi (_italik_) ile replik ("...") AYRI tutulur: ogrenme
# kurallarinda ikisi farkli davranir. Ic ses Klein'indir; replik kimin
# oldugunu bilemeyiz, o yuzden dusuk agirlikla raporlanir.
IC_SES = re.compile(r"_[^_\n]{3,}_")
REPLIK = re.compile(r"[\"“][^\"”\n]{3,}[\"”]")


def bolum_numarasi(dosya_adi: str) -> int | None:
    m = re.search(r"(\d+)", dosya_adi)
    return int(m.group(1)) if m else None


def diyakritiksiz(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def govde_metni(ham: str) -> str:
    """YAML front-matter'ı at."""
    if ham.startswith("---"):
        parca = ham.split("---", 2)
        if len(parca) >= 3:
            return parca[2]
    return ham


def satir_no(metin: str, indeks: int) -> int:
    return metin.count("\n", 0, indeks) + 1


def baglam(metin: str, bas: int, son: int, yaricap: int = 55) -> str:
    a = max(0, bas - yaricap)
    b = min(len(metin), son + yaricap)
    return re.sub(r"\s+", " ", metin[a:b]).strip()


def ic_ses_araliklari(metin: str) -> list[tuple[int, int]]:
    """Klein'in _italik_ ic sesi."""
    return [m.span() for m in IC_SES.finditer(metin)]


def replik_araliklari(metin: str) -> list[tuple[int, int]]:
    """Tirnak icindeki replikler -- konusan kim, bilinmiyor."""
    return [m.span() for m in REPLIK.finditer(metin)]


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


def denetle_varyant(rapor, dosyalar, kurallar):
    for kural in kurallar.get("varyantlar", []):
        dogru = kural["dogru"]
        ek_not = kural.get("not", "")
        sadece_anlatici = kural.get("sadece_anlatici", False)
        # Ogrenme bolumu: Klein terimi bu bolumde ogrenir. Oncesinde eski
        # kelime YALNIZCA onun ic sesinde serbesttir; anlatici ve diger
        # karakterler dunyanin kelimesini bastan beri kullanir. Bolumden
        # itibaren ic seste de yasaktir -- devrin tamamlanmasi budur.
        ogrenme = kural.get("ogrenme_bolumu")
        # KESIN GECIS (kesin_gecis: true). Ses ayrimi yerine tek bir bolumde
        # temiz gecis: ogrenme_bolumu'nden ONCE eski kelime her seste
        # serbesttir, o bolumden itibaren her seste hatadir. Gerekce:
        # ses ayrimi okura gorunmuyordu; ayni bolumde Dunn "ayin" derken
        # anlatici "ritüel" diyordu ve bu, kotu ceviri gibi okunuyordu.
        # Kaynakta tek kelime var (仪式); iki kelimelik ayrim yalnizca okurun
        # fark edebildigi tek bir gecis noktasi olarak anlam tasir. Ayrica
        # yeni kelime gecisten ONCE geciyorsa uyari verilir (geriye donuk
        # tasima icin liste).
        kesin = bool(kural.get("kesin_gecis")) and ogrenme is not None
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
            no = bolum_numarasi(ad)
            ic = ic_ses_araliklari(metin)
            rep = replik_araliklari(metin)
            kapali: list[tuple[int, int]] = []

            for yanlis in yanlislar:
                desen = tr_desen(yanlis) if duyarsiz else re.escape(yanlis)
                for m in re.finditer(desen, metin):
                    if any(a <= m.start() < b for a, b in kapali):
                        continue
                    ctx = baglam(metin, m.start(), m.end())
                    if any(d.search(ctx) for d in istisnalar):
                        kapali.append(m.span())
                        continue

                    icte = ic_seste_mi(ic, m.start())
                    replikte = ic_seste_mi(rep, m.start())

                    if kesin:
                        if no is not None and no < ogrenme:
                            kapali.append(m.span())
                            continue  # gecisten once her seste serbest
                        yer = (("Klein'in ic sesi" if icte else "replik" if replikte
                                else "anlatici sesi") + f", gecisten SONRA (bolum {ogrenme})")
                        agirlik = "hata"
                    elif ogrenme is not None:
                        if icte:
                            if no is not None and no < ogrenme:
                                kapali.append(m.span())
                                continue  # ogrenmeden once serbest
                            yer, agirlik = (
                                (
                                    "Klein'in ic sesi, ogrenmeden "
                                    f"SONRA (bkz. bolum {ogrenme})"
                                ),
                                "hata",
                            )
                        elif replikte:
                            yer, agirlik = (
                                ("replik -- konusan Klein mi? elle bakin"),
                                "uyari",
                            )
                        else:
                            yer, agirlik = "anlatici sesi", "hata"
                    elif sadece_anlatici:
                        if icte or replikte:
                            kapali.append(m.span())
                            continue
                        yer, agirlik = "anlatici sesi", "hata"
                    else:
                        yer, agirlik = "", "hata"

                    kapali.append(m.span())
                    mesaj = f"“{yanlis}” → “{dogru}”  [{kural['kavram']}]"
                    if yer:
                        mesaj += f"  ({yer})"
                    if ek_not:
                        mesaj += f"\n       {ek_not}"
                    rapor.ekle(
                        "varyant",
                        ad,
                        satir_no(metin, m.start()),
                        yanlis,
                        mesaj,
                        ctx,
                        agirlik=agirlik,
                    )

            # Kesin gecis: yeni kelime gecisten ONCE geciyorsa uyari. Hata
            # degil -- kilise ayini gibi baska bir anlamda da gecebilir.
            if kesin and no is not None and no < ogrenme:
                d = tr_desen(dogru) if duyarsiz else re.escape(dogru)
                for m in re.finditer(r"(?<![^\W_])" + d, metin):
                    ctx = baglam(metin, m.start(), m.end())
                    rapor.ekle(
                        "varyant", ad, satir_no(metin, m.start()), m.group(),
                        f"“{m.group()}” gecisten ONCE (bolum {ogrenme}): "
                        f"“{kural['yanlis'][0]}” mi olmali?  [{kural['kavram']}]",
                        ctx, agirlik="uyari",
                    )


def denetle_yasakli(rapor, dosyalar, kurallar):
    for kural in kurallar.get("yasakli", []):
        bicim, yerine = kural["bicim"], kural["yerine"]
        desen = re.compile(rf"(?<![{TR_HARF}]){tr_desen(bicim)}")
        for ad, metin in dosyalar.items():
            for m in desen.finditer(metin):
                rapor.ekle(
                    "yasaklı",
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
            nerede[anahtar].add(ad)

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


def denetle_kesme(rapor, dosyalar):
    """
    Karisik kesme isareti.

    Dosya basina sayi vermek yetmiyor: kivrik (’) ile duz (') ekranda
    neredeyse ayni gorunur, yani "10 dosyada karisik" bilgisiyle insan
    onlari elle bulamaz. Azinlikta olan bicimin HER GECISI satir numarasiyla
    raporlanir; boylece dogrudan o satira gidilebilir.
    """
    for ad, metin in sorted(dosyalar.items()):
        kivrik = metin.count(KIVRIK)
        duz = metin.count(DUZ)
        if not (kivrik and duz):
            continue
        azinlik = KIVRIK if kivrik <= duz else DUZ
        adi = "kıvrık ’" if azinlik == KIVRIK else "düz '"
        hedef = "düz '" if azinlik == KIVRIK else "kıvrık ’"
        rapor.ekle(
            "kesme",
            ad,
            0,
            azinlik,
            f"karışık kesme: düz ×{duz}, kıvrık ×{kivrik} — "
            f"azınlık {adi}, {len(metin.split(azinlik)) - 1} yerde",
            agirlik="uyari",
        )
        for m in re.finditer(re.escape(azinlik), metin):
            rapor.ekle(
                "kesme",
                ad,
                satir_no(metin, m.start()),
                azinlik,
                f"{adi} → {hedef}",
                baglam(metin, m.start(), m.end(), 40),
                agirlik="uyari",
            )


def denetle_ek_uyumu(rapor, dosyalar, kurallar=None):
    """
    Özel adlara gelen eklerin ünlü uyumu.

    ÇOĞUNLUK HER ZAMAN DOĞRU DEĞİLDİR. "Alger" son hecesinde ön ünlü taşır,
    yani doğru ek "-in"dir; metinde 6 kez "Alger'ın", 3 kez "Alger'in" geçiyor
    — yani azınlıkta olan biçim doğru olandır. Bu yüzden kural dosyasındaki
    "ozel_adlar" bölümü doğru eki ELLE bildirebilir. Bildirmezse araç
    çoğunluğa bakar ama bunu bir TAHMİN olarak işaretler (uyarı, hata değil).
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
        ("dan", "den"),
        ("da", "de"),
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
            if len(mevcut) < 2:
                continue
            sayim = {e: len(bicimler[e]) for e in mevcut}

            if dogrular & set(mevcut):
                hedef = sorted(dogrular & set(mevcut))[0]
                aciklama, agirlik = "kural dosyasında tanımlı", "hata"
            else:
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
                        f"“{ad_ozel}'{ek}” → “{ad_ozel}'{hedef}”  "
                        f"({aciklama}; sayım {sayim})",
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
    {dosya_adi: Cince govde}. lotm ya da ham metinler yoksa BOS doner ve
    denetim bugunku (kaynaksiz) davranisina duser.

    lint/ bir alt klasor; lotm.py bir ust dizinde.
    """
    import sys as _sys
    from pathlib import Path as _P

    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
    try:
        import lotm

        zh = lotm.bolum_sozlugu(lotm.bolumler_zh())
    except Exception:
        return {}

    out = {}
    for ad in dosyalar:
        m = re.search(r"(\d+)", ad)
        if m:
            b = zh.get(int(m.group(1)))
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
        yogunluk = len(desen.findall(diyakritiksiz(tr_kucult(metin)))) * 1000 / kelime_sayisi
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
    ap.add_argument("bolumler", nargs="+", help="bölüm .md dosyaları")
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

    dosyalar = {}
    for y in args.bolumler:
        p = Path(y)
        dosyalar[p.name] = govde_metni(p.read_text(encoding="utf-8"))

    secili = set(args.sadece.split(",")) if args.sadece else set(DENETIMLER)
    rapor = Rapor()

    if "varyant" in secili:
        denetle_varyant(rapor, dosyalar, kurallar)
    if "yasakli" in secili:
        denetle_yasakli(rapor, dosyalar, kurallar)
    if "diyakritik" in secili:
        denetle_diyakritik(rapor, dosyalar, kurallar)
    if "kesme" in secili:
        denetle_kesme(rapor, dosyalar)
    if "ek-uyumu" in secili:
        denetle_ek_uyumu(rapor, dosyalar, kurallar)
    if "anakronizm" in secili:
        denetle_anakronizm(
            rapor,
            dosyalar,
            kurallar,
            kaynak_metinleri(dosyalar) if args.kaynak else None,
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

    for kural in DENETIMLER:
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
    print(f"\n{'═' * 72}\n{hata} hata, {uyari} uyarı — {len(dosyalar)} bölüm\n")
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
