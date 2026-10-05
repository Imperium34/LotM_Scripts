#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ceviri_denetle.py -- bir terimin bolumler boyunca NASIL cevrildigini gosterir.

UST DUZEY SORU: "YAYIMLANMIS ceviride bu terime ne karsilik geldi, tutarli mi?"

Dort "denetim/arama" betigi var ve dorderi de farkli seye bakiyor --
karistirilmasinlar:
    sozluk_ara.py       sozluk.yml'e bakar               -- ne karar verdim?
    kapi_denetle.py      KAYNAK (EN) metne bakar          -- nerede ilk geciyor?
    ceviri_denetle.py    YAYIMLANMIS metne bakar (hizali) -- ne yayimladim, tutarli mi?
    yayim_denetle.py     YAYIMLANMIS (TR) metne bakar     -- yayimlanan GUVENLI mi?

sozluk.yml "ne karar verdim" sorusunu yanitlar. Bu betik "ne yayimladim"
sorusunu yanitlar. Ikisi ayni olmak zorunda degil; aradaki fark zaten
aranan seydir.

NASIL CALISIR
-------------
Terim kaynak metinde (EN/ZH) aranir. Bulunan her paragraf, bolum.hizala ile
hedef metne (TR) hizalanir ve karsi paragraf cikarilir. Yani karsilik
sozlukten degil, YAYIMLANMIS METINDEN okunur.

Karsiligin hangi kelime oldugunu bulmak icin iki yol var:

  1. SOZLUKTEN. Terim sozlukte varsa karsiligi ve eski_karsiliklar
     adaylardir. Hangisi gectigine bakilir.
  2. KESFEDEREK. Sozlukte yoksa, terimin gectigi paragraflarda gecip
     GECMEDIGI paragraflarda gecmeyen govdeler aranir (tf-idf benzeri).
     Kesin degildir, aday uretir.

Ikisinde de asil ciktisi olan sey EŞLEŞMEYENLER'dir: terimin gectigi ama
hicbir adayin bulunmadigi paragraflar. Ya yeni bir karsilik kullanilmis,
ya terim atlanmis, ya da hizalama kaymis. Ucu de bakmaya deger.

Kullanim:
    ceviri_denetle.py "Beyonder"                  EN -> TR, ozet
    ceviri_denetle.py "Beyonder" --tam            her gecisi tek tek
    ceviri_denetle.py "Sıradışı" --hedef en       ters yon: arkasinda ne vardi?
    ceviri_denetle.py 序列 --hedef tr             Cinceden
    ceviri_denetle.py "Beyonder" --bolum 1-200
    ceviri_denetle.py "Beyonder" --aday Sıradışı --aday Olağanüstü
"""

import argparse
import functools
import math
import re
import sys
from collections import Counter, defaultdict

import lotm
from turkce import en_kucult, tr_desen, tr_kucult
import bolum as B
import capa as _capa
from hizalama_denetle import capa_yer_degistirme, grup_artiklari, kayma_bul

_CAPA_SOZLUGU = _capa.sozluk_yukle()

# Turkce cekim eki deseni. Migrasyondan once denetci2.py'deydi ve buradan
# oraya import ediliyordu; artik dogru yerde.
desen_kur = lotm.desen_kur


_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
_KELIME = re.compile(r"[^\W\d_]+", re.UNICODE)

# Kesif taramasinda govde uzunlugu. Turkce ekleri kirpmak icin: "Sıradışı",
# "Sıradışılar", "Sıradışının" hepsi "sıradı" olur. Kaba ama ek listesi
# bakmaktan ucuz ve bilinmeyen kelimelerde de calisir.
KOK_UZUNLUK = 6

# Bu govdeler hedef paragraflarin %25'inden fazlasinda geciyorsa aday
# sayilmaz -- ayirt edici degiller.
GURULTU_ESIGI = 0.25


# --------------------------------------------------------------- yardimci


def _kok(kelime: str, dil: str = "tr") -> str:
    """
    Kesif govdesi. Kucultme DILE GORE: Turkce metinde casefold() "Işık"i
    "işık" yapiyordu, "ışık" ile ayri govde cikiyordu; cumle basindaki her
    I/İ ile baslayan kelime kendi ikizinden ayri sayiliyordu ve kesif ya
    olmayan bir cesitleme uyduruyor ya da gercek bir karsiligi ikiye
    bolup esigin altina itiyordu.
    """
    k = en_kucult(kelime) if dil == "en" else tr_kucult(kelime)
    return k[:KOK_UZUNLUK]


def _koku_olanlar(metin: str, dil: str = "tr") -> set:
    return {_kok(k, dil) for k in _KELIME.findall(metin)}


def dili_kestir(sorgu: str) -> str:
    """Sorgudan kaynak dili tahmin eder."""
    if _CJK.search(sorgu):
        return "zh"
    if re.search(r"[ğışĞİŞçöüÇÖÜâî]", sorgu):
        return "tr"
    return "en"


_ZH_AYIRICI = re.compile(r"[/、，,;；\s]+")


@functools.lru_cache(maxsize=1)
def _sozluk_zh() -> tuple:
    """Sozlukteki butun Cince terimler. Sozluk yoksa bos (testler, tek dosya)."""
    try:
        s = lotm.sozluk_yukle(kelimeler=True)
    except (Exception, SystemExit):
        return ()
    out = set()
    for t in s.terimler:
        out.update(z for z in _ZH_AYIRICI.split(t.zh or "") if z)
    return tuple(sorted(out))


def zh_bilesikleri(sorgu: str, sozluk_zh=None) -> list:
    """
    sorgu'yu ICEREN ve ondan uzun sozluk terimleri, uzundan kisaya.

    Cince'de kelime siniri yok: 灵体 araninca 星灵体 (Astral Projection) ve
    灵体之线'nin her gecisi de bulunuyordu. 灵体 sorgusunun ESLESMEYEN
    listesi bu yuzden "Astral Projection" cumleleriyle doluydu. Ingilizce
    taramada ayni sorun "Hunter" -> "Demon Hunter" olarak cozulmustu
    (kapi_denetle); bu onun Cince karsiligi. Liste sozlukten TURETILIR,
    yani sozluge girilen her 'cince' alani burayi da besler.
    """
    kaynak = _sozluk_zh() if sozluk_zh is None else sozluk_zh
    return sorted({z for z in kaynak if sorgu in z and z != sorgu}, key=len, reverse=True)


def _zh_desen(sorgu: str, bilesikler) -> re.Pattern:
    """lotm.zh_desen'e yonlendirir (capa.py de ayni deseni kullanir)."""
    return lotm.zh_desen(sorgu, bilesikler)


# ------------------------------------------------- Cince bilesik ipucu
#
# zh_bilesikleri YALNIZCA sozlukte kayitli bilesikleri haric tutar. Kayitli
# olmayan bir bilesigin gecisleri sorgunun kendisi sayilir ve ESLESMEYEN
# listesini doldurur: 占卜 (kehanet) taranirken 占卜家 (Kâhin) ve 占卜师
# (kâhin) sozlukte yoktu, dogru cevrilmis her Kâhin "kehanet eksik" diye
# raporlandi. Cince okumayan bir kullanici bunu ciktidan ayirt edemez;
# Turkce satirlar dogru gorunur ama neden eslesmedigi gorunmez.
#
# Asagidaki ipucu bunu gorunur kilar: eslesmeyen gecislerde sorgunun hemen
# solundaki ve sagindaki Cince harfi sayar. Bir dizi (占卜家) cok sayida
# eslesmeyende tekrar ediyorsa buyuk olasilikla sozlukte eksik bir
# bilesiktir. Tek harflik pencere kabadir ama yeter: Cince bilesiklerin
# cogu sorguya bir ek harf (家, 师, 者, 术) ya da bir on harf (星) ekler.
#
# Kelime kurmayan harfler (edat, zamir, yardimci fiil) sayilmaz; yoksa
# "占卜的", "去占卜" gibi diziler bilesik diye raporlanir. Liste kabadir ve
# bilerek kucuk tutulmustur: bir dizinin bilesik olup olmadigina insan karar
# verir, ipucu yalnizca nereye bakilacagini soyler.
_ZH_ISLEV = frozenset(
    "的了着过吗呢吧啊呀哦嘛么"      # parcaciklar
    "是在和与及或也都就还又再才已只很更最太不没别"
    "一个这那些此其每各某该"
    "我你您他她它们谁"
    "等时"
)
# Yalnizca SOLDA anlamsiz olanlar: fiilden, edattan ya da nesneden once
# gelirler ("去占卜", "会占卜", "替人占卜"). Sagda bilesik kurabilirler
# (收尸人), o yuzden ortak listede degiller.
_ZH_ONCE = frozenset("去来到被把对给为向往从自于以所将会能可要想让使请说道替帮找做进人")
# Yalnizca SAGDA anlamsiz olanlar: yer ve zaman sonekleri ("灵体中").
_ZH_SONRA = frozenset("上下中里内外后前间")


def _cjk_harf(c: str) -> bool:
    return bool(_CJK.fullmatch(c))


def zh_pencere(metin: str, desen) -> str:
    """
    Ilk gecisin bir harf solu ve bir harf sagiyla kesiti (yalniz CJK).
    Eslesmeyen satirlarin yanina yazilir: Cince okumayan biri de ayni
    pencerenin tekrar ettigini gorebilsin.
    """
    m = desen.search(metin or "")
    if not m:
        return ""
    s, e = m.span()
    sol = metin[s - 1] if s > 0 and _cjk_harf(metin[s - 1]) else ""
    sag = metin[e] if e < len(metin) and _cjk_harf(metin[e]) else ""
    return sol + m.group() + sag


def zh_bilesik_ipuclari(vuruslar, desen, en_az: int = 2) -> list:
    """
    Vuruslarda sorgunun gectigi daha uzun dizilerin sayimi.

    Doner: [(dizi, vurus_sayisi, [vurus, ...]), ...] cogdan aza; yalniz
    en_az kez gecenler. Sayim VURUS basinadir (ayni paragrafta iki kez
    gecen dizi bir sayilir), boylece sayi eslesmeyen sayisiyla
    karsilastirilabilir.
    """
    sayac, uyan = Counter(), defaultdict(list)
    for v in vuruslar:
        metin = v.get("kaynak_metin") or ""
        diziler = set()
        for m in desen.finditer(metin):
            s, e = m.span()
            if e < len(metin):
                c = metin[e]
                if _cjk_harf(c) and c not in _ZH_ISLEV and c not in _ZH_SONRA:
                    diziler.add(m.group() + c)
            if s > 0:
                c = metin[s - 1]
                if _cjk_harf(c) and c not in _ZH_ISLEV and c not in _ZH_ONCE:
                    diziler.add(c + m.group())
        for d in diziler:
            sayac[d] += 1
            uyan[d].append(v)
    return [(d, n, uyan[d]) for d, n in sayac.most_common() if n >= en_az]


def zh_bilesik_raporu(eslesmeyen, desen, arka_plan=None, dil="tr", ust=4, en_az=2) -> list:
    """
    zh_bilesik_ipuclari + her dizi icin hedef metinde ne kullanildigi.

    Doner: [(dizi, vurus_sayisi, kokler), ...]. kokler, o dizinin gectigi
    eslesmeyenlerin hedef paragraflarinda sik gecip arka planda gecmeyen
    govdelerdir (adaylari_kesfet). 占卜家 kumesi icin "kâhin" cikar ve
    kullanici diziyi okuyamasa da neyin karsiligi oldugunu gorur.
    arka_plan verilmezse kesif yapilmaz.
    """
    out = []
    for dizi, n, vs in zh_bilesik_ipuclari(eslesmeyen, desen, en_az)[:ust]:
        kokler = []
        if arka_plan is not None:
            metinler = [v.get("hedef_metin_dar") or v.get("hedef_metin") or "" for v in vs]
            metinler = [m for m in metinler if m]
            # Kumenin kendi paragraflari arka plandan cikarilir; yoksa aranan
            # kelime paydada da gorunur (bkz. tara() notu).
            haric = {p for m in metinler for p in m.split("\n")}
            arka = [p for p in arka_plan if p not in haric]
            kokler = adaylari_kesfet(metinler, arka, ust=3, dil=dil)
        out.append((dizi, n, kokler))
    return out


def zh_bilesik_yaz(rapor, girinti="  "):
    """zh_bilesik_raporu ciktisini yazar; rapor bossa hicbir sey yazmaz."""
    if not rapor:
        return
    print(f"{girinti}Eşleşmeyenlerin yoğunlaştığı daha uzun Çince diziler (sözlükte kayıtlı değil):")
    for dizi, n, kokler in rapor:
        ek = f"   hedefte sık: {', '.join(kokler)}" if kokler else ""
        print(f"{girinti}  {dizi}  ×{n}{ek}")
    print(f"{girinti}  Dizi ayrı karşılığı olan bir bileşikse 'cince' alanına eklenince bu")
    print(f"{girinti}  terimin sayımından düşer ve kendi satırında denetlenir.")


@functools.lru_cache(maxsize=1)
def _zh_adlari() -> dict:
    """Cince anahtar -> Turkce terim adi (rapor icin). Sozluk yoksa bos."""
    try:
        s = lotm.sozluk_yukle(kelimeler=True)
    except (Exception, SystemExit):
        return {}
    out = {}
    for t in s.terimler:
        for z in _ZH_AYIRICI.split(t.zh or ""):
            if z:
                out.setdefault(z, t.tr)
    return out


def zh_elenenler(sorgu: str, metinler, haric=None) -> Counter:
    """
    Sozlukteki daha uzun terimlerin icinde kaldigi icin SAYILMAYAN
    gecisler: {bilesik: sayi}. Uzundan kisaya maskelenir; ic ice iki
    bilesik ayni gecisi iki kez saymaz. Bir bilesik sozluge eklendikten
    sonra maskelemenin gercekten islediginin kaniti budur.
    """
    bilesikler = zh_bilesikleri(sorgu) + [h for h in (haric or []) if sorgu in h and h != sorgu]
    bilesikler = sorted(dict.fromkeys(bilesikler), key=len, reverse=True)
    sayac = Counter()
    for metin in metinler:
        for b in bilesikler:
            n = metin.count(b)
            if n:
                sayac[b] += n
                metin = metin.replace(b, "\0" * len(b))
    return sayac


def zh_elenen_yaz(sayac, girinti="  "):
    if not sayac:
        return
    adlar = _zh_adlari()
    dokum = ", ".join(
        f"{b}×{n}" + (f" ({adlar[b]})" if b in adlar else "") for b, n in sayac.most_common()
    )
    print(f"{girinti}{sum(sayac.values())} geçiş daha uzun bir sözlük teriminin içinde, sayılmadı: {dokum}")


def desen_kur_kaynak(sorgu: str, kaynak: str, harf_duyarsiz: bool, haric=None):
    """
    Her dil icin farkli eslesme:
      zh  duz altdize (kelime siniri yok), ama sozlukteki daha uzun bir
          terimin icindeki gecisler sayilmaz (bkz. zh_bilesikleri);
          haric ile elle bilesik eklenebilir
      tr  Turkce cekim ekleri (denetci2.desen_kur)
      en  kelime siniri; sorgu buyuk harf iceriyorsa harf duyarli
    """
    if kaynak == "zh":
        bilesikler = zh_bilesikleri(sorgu) + [h for h in (haric or []) if sorgu in h and h != sorgu]
        return _zh_desen(sorgu, bilesikler)
    if kaynak == "tr":
        return desen_kur(sorgu, harf_duyarli=not harf_duyarsiz)
    bayrak = re.IGNORECASE if (harf_duyarsiz or sorgu.islower()) else 0
    return re.compile(r"(?<!\w)" + re.escape(sorgu) + r"(?!\w)", bayrak)


def bolum_araligi(ifade):
    """'1-200' -> (1, 200);  '279' -> (279, 279);  None -> None"""
    if not ifade:
        return None
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", ifade)
    if not m:
        sys.exit(f"bolum araligi anlasilmadi: {ifade!r}  (ornek: 1-200)")
    bas = int(m.group(1))
    return (bas, int(m.group(2)) if m.group(2) else bas)


# --------------------------------------------------------------- adaylar


def sozlukten_adaylar(sorgu: str, hedef: str) -> list:
    """
    Sorguyla eslesen sozluk kayitlarindan hedef dildeki karsiliklari toplar.
    eski_karsiliklar da dahil -- asil merak edilen zaten onlarin metinde
    kalip kalmadigi.
    """
    try:
        sozluk = lotm.sozluk_yukle(kelimeler=True)  # words.md maddeleri de
    except (FileNotFoundError, OSError) as e:
        print(f"uyari: sozluk okunamadi ({e}); kesif moduna geciliyor", file=sys.stderr)
        return []

    # Her alan kendi diliyle kucultulur; sorgu da her alan icin o dile gore.
    # Tek casefold() Turkce alanda "Işık"i "işık" yapiyordu.
    q_tr, q_en = tr_kucult(sorgu), en_kucult(sorgu)
    adaylar = []
    for t in sozluk.terimler:
        ciftler = [(q_tr, tr_kucult(t.tr)), (q_en, en_kucult(t.en)), (sorgu, t.zh or "")]
        if not any(q == a or (len(q) > 3 and q in a) for q, a in ciftler if a):
            continue
        if hedef == "tr":
            adaylar += t.tr_bicimleri()  # toplu_denetle ile ayni kural
            adaylar += list(t.eski_karsiliklar)
        elif hedef == "en" and t.en:
            adaylar.append(t.en)
        elif hedef == "zh" and t.zh:
            adaylar.append(t.zh)

    kucult = en_kucult if hedef == "en" else tr_kucult
    gorulen, temiz = set(), []
    for a in adaylar:
        a = (a or "").strip()
        if a and kucult(a) not in gorulen:
            gorulen.add(kucult(a))
            temiz.append(a)
    return temiz


def adaylari_kesfet(vurus_paragraflari, arka_plan, ust=8, dil="tr") -> list:
    """
    Terimin gectigi paragraflarda gecip digerlerinde gecmeyen govdeler.

    Skor = (vurus orani) * log(toplam / arka plan orani). Yani hem sik hem
    ayirt edici olan kazanir. 'bir', 'bu', 've' her yerde gectigi icin
    ikinci carpan onlari sifira yaklastirir.
    """
    if not vurus_paragraflari:
        return []

    vurus_df = Counter()
    for p in vurus_paragraflari:
        vurus_df.update(_koku_olanlar(p, dil))

    arka_df = Counter()
    for p in arka_plan:
        arka_df.update(_koku_olanlar(p, dil))

    n_vurus, n_arka = len(vurus_paragraflari), max(1, len(arka_plan))
    puanlar = []
    for kok, df in vurus_df.items():
        if len(kok) < 3:
            continue
        if arka_df[kok] / n_arka > GURULTU_ESIGI:
            continue
        oran = df / n_vurus
        if oran < 0.15:  # dagilmis gurultu
            continue
        puanlar.append((oran * math.log(n_arka / (arka_df[kok] + 1) + 1), kok))

    puanlar.sort(reverse=True)
    return [kok for _, kok in puanlar[:ust]]


# --------------------------------------------------------------- tarama


def _kayma_haritasi(k_par, h_par, gruplar, kaynak, hedef) -> dict:
    """
    {grup_indisi: yon} -- hizalamanin kaydigi bolgeler.

    NEDEN GEREKLI
    -------------
    ESLESMEYEN listesinin uc sebebi var: yeni bir karsilik, atlanmis bir
    cumle, kaymis hizalama. Ucuncusu ceviri hatasi DEGILDIR ama ilk
    ikisinden ayirt edilemez: terim kaynakta, karsilik hedefte, ama ikisi
    ayni gruba dusmedigi icin "bulunamadi" gorunur.

    hizalama_denetle.capa_yer_degistirme bu bolgeleri isaretler ve YONUNU
    verir. Isaretli bir bolgede hedef metin komsu grupla genisletilir;
    disarida siki kalinir.

    Hedef metnin paragraflandirmasi okunabilirlik icin yapildigindan
    hizalamanin bir gruplik hatasi kalicidir; cozum hizalayiciyi
    duzeltmek degil, tuketicinin bunu bilmesidir.

    IKI SINYAL, IKI CESIT ISARET
    ----------------------------
    capa yer degistirmesi YONLUDUR ama tek grupluk: ad bir grup otede.
    Uzunluk/replik kaymasi yonsuzdur ama ARALIK verir ve daha uzun
    kaymalari gorur. Bolum 6 ikincisini gerektiriyor: orada hedef IKI grup
    geride (ZH ¶42'nin Turkcesi ¶44'te) ve capa, yon filtresi yuzunden o
    bolumde zaten susturulmus durumda. Aralik (¶42-47) ise bildiriliyor.

    Yonu bilinmeyen gruplarda iki komsuya birden bakilir; bilinen
    gruplarda yalnizca isaret edilen yone.
    """
    harita = {}
    for g, kayitlar in capa_yer_degistirme(k_par, h_par, gruplar, _CAPA_SOZLUGU).items():
        yon = kayitlar[0][2]
        harita.setdefault(g, yon)
        harita.setdefault(g + 1, yon)

    artiklar = list(
        grup_artiklari(k_par, h_par, gruplar, k_dil=kaynak, h_dil=hedef)
    )
    for bas, son in kayma_bul(artiklar):
        for g in range(bas, son + 1):
            harita.setdefault(g, "belirsiz")
    return harita


def _hedef_metin(kume_b, indisler) -> str:
    return "\n".join(kume_b[x] for x in indisler)


def vurus_kur(bolum, kaynak_metin, h_par, ib, ib_dar=None, genis=None, **ek) -> dict:
    """
    Vurus kaydinin TEK kurucusu. siniflandir() ve ozet fonksiyonlari bu
    semayi okur.

    Iki uretici var: tara() (tek terim, kendi hizalamasi) ve
    toplu_denetle.terimi_tara() (onbellekten). Eskiden ikisi sozlugu elle
    kuruyordu; tara()'ya 'hedef_metin_dar' eklenince siniflandir() onu
    okumaya basladi, toplu tarafinda alan yoktu ve toplu_denetle ilk
    terimde KeyError ile duruyordu. Alan artik yalnizca burada eklenir.

    ib      hedef paragraf indisleri (kayma bolgesinde komsu grupla
            genisletilmis olabilir)
    ib_dar  yalnizca hizalamanin verdigi indisler; verilmezse ib ile ayni
            (genisletme yapmayan uretici icin, orn. toplu_denetle)
    genis   genisletmenin sebebi ("hedef geride" / "ileride" / "belirsiz")
            ya da None
    ek      ureticiye ozgu ek alanlar (toplu: 'kayan'); ortak alanlarin
            ustune yazamaz
    """
    ib = list(ib or [])
    ib_dar = ib if ib_dar is None else list(ib_dar)
    kayit = {
        "bolum": bolum,
        "kaynak_metin": kaynak_metin,
        "hedef_metin": _hedef_metin(h_par, ib) if ib else "",
        "hedef_metin_dar": _hedef_metin(h_par, ib_dar) if ib_dar else "",
        "tip": "eslesti" if ib else "tek_tarafli",
        "genis": genis,
    }
    cakisan = set(ek) & set(kayit)
    if cakisan:
        raise ValueError(f"vurus_kur: ek alanlar ortak alanlarin ustune yazamaz: {cakisan}")
    kayit.update(ek)
    return kayit


def tara(sorgu, kaynak, hedef, aralik, harf_duyarsiz, haric=None):
    """
    Doner: (vuruslar, arka_plan)
      vuruslar   -> [{bolum, kaynak_metin, hedef_metin, tip}]
      arka_plan  -> ayni bolumlerin terimin GECMEDIGI hedef paragraflari

    Arka plana vurus paragraflari DAHIL EDILMEZ. Edilirse kesif bozulur:
    aranan karsilik hem sayacta hem paydada gorunur, "her yerde geciyor"
    diye elenir ve tam da bulunmasi gereken kelime gurultu sayilir.
    """
    desen = desen_kur_kaynak(sorgu, kaynak, harf_duyarsiz, haric)
    ham_desen = re.compile(re.escape(sorgu)) if kaynak == "zh" else None
    elenen = 0

    yukle = {"zh": lotm.bolumler_zh, "en": lotm.bolumler_en, "tr": lotm.bolumler_tr}

    def oku(ad):
        try:
            return lotm.bolum_sozlugu(yukle[ad]())
        except (FileNotFoundError, OSError) as e:
            sys.exit(
                f"{ad.upper()} kaynagi okunamadi: {e}\n"
                f"LOTM_KOK dogru mu? (su an: {lotm.KOK})"
            )

    k_bolumler, h_bolumler = oku(kaynak), oku(hedef)

    ortak = sorted(set(k_bolumler) & set(h_bolumler))
    if aralik:
        ortak = [n for n in ortak if aralik[0] <= n <= aralik[1]]
    if not ortak:
        sys.exit(
            "kaynak ve hedefte ortak bolum yok (TR yayimlanmis bolumler mi eksik?)"
        )

    print(
        f"{len(ortak)} ortak bolum taraniyor ({ortak[0]}-{ortak[-1]})...",
        file=sys.stderr,
    )

    k_baslik = B.KAYNAKLAR[kaynak][2]
    h_baslik = B.KAYNAKLAR[hedef][2]

    vuruslar, arka_plan = [], []
    for no in ortak:
        k_ham = k_bolumler[no].metin
        if ham_desen is not None:
            elenen += len(ham_desen.findall(k_ham)) - len(desen.findall(k_ham))
        if not desen.search(k_ham):
            continue

        k_par = B.paragraflar(k_ham, k_baslik)
        h_par = B.paragraflar(h_bolumler[no].metin, h_baslik)

        capalar = set(_capa.capa_bul(k_par, h_par, _CAPA_SOZLUGU))
        gruplar = B.hizala(k_par, h_par, capalar)
        kayma = _kayma_haritasi(k_par, h_par, gruplar, kaynak, hedef)
        nereye, grup_no = {}, {}
        for gi, (ia, ib) in enumerate(gruplar):
            for i in ia:
                nereye[i] = ib
                grup_no[i] = gi

        tuketilen = set()
        for i, p in enumerate(k_par):
            if not desen.search(p):
                continue
            ib = list(nereye.get(i, []))
            ib_dar = list(ib)
            gi = grup_no.get(i)
            genis = None
            if gi is not None and gi in kayma:
                # "hedef geride" -> karsilik bir sonraki grupta; "ileride"
                # -> bir oncekinde. Yonu sinyalin kendisi veriyor.
                if kayma[gi] == "belirsiz":
                    komsular = (gi - 1, gi + 1)
                else:
                    komsular = (gi + 1,) if kayma[gi] == "hedef geride" else (gi - 1,)
                ek = [
                    j
                    for komsu in komsular
                    if 0 <= komsu < len(gruplar)
                    for j in gruplar[komsu][1]
                    if j not in ib
                ]
                if ek:
                    ib += sorted(set(ek))
                    genis = kayma[gi]
            tuketilen.update(ib)
            vuruslar.append(vurus_kur(no, p, h_par, ib, ib_dar=ib_dar, genis=genis))

        arka_plan.extend(p for j, p in enumerate(h_par) if j not in tuketilen)

    if elenen:
        # Bilesik basina sayi ve sozlukteki adi: "占卜俱乐部×7 (Kehanet
        # Kulübü)". Eskiden yalnizca bilesik listesi yaziliyordu; Cince
        # okumayan biri hangisinin neyi yuttugunu goremiyordu.
        sayac = zh_elenenler(sorgu, [k_bolumler[no].metin for no in ortak], haric)
        adlar = _zh_adlari()
        print(
            f"  {elenen} gecis daha uzun bir terimin icinde, sayilmadi: "
            + ", ".join(f"{b}×{n}" + (f" ({adlar[b]})" if b in adlar else "")
                        for b, n in sayac.most_common()),
            file=sys.stderr,
        )
    return vuruslar, arka_plan


def siniflandir(vuruslar, adaylar, hedef, kesif=False):
    """
    Her vurusa, hedef paragrafinda gecen adaylari etiketler.

    kesif=True ise adaylar sozlukten degil adaylari_kesfet()'ten gelir --
    KOK_UZUNLUK (6) karakterlik kirpilmis GOVDELER, tam kelime degil.
    Boyle bir govdeyi desen_kur/tam-kelime-sinir desenleriyle aramak
    govdenin kendi geldigi kelimeyi bile bulamaz: "sıradı" govdesi
    desen_kur'a verilirse, kelimenin kalan harfleri ("şı") ne bilinen bir
    Turkce ek ne de bos oldugu icin sondaki kelime-siniri sarti hic
    tutmaz -- "Sıradışı" metinde acikca varken "bulunamadi" cikar. Ayni
    sey EN icin de gecerli: "extrao" govdesi ile "(?<!\\w)extrao(?!\\w)"
    "extraordinary" icindeki "extrao"yu YAKALAMAZ, cunku hemen ardindan
    "rdinary" harfleri geliyor ve kelime siniri orada bitmiyor.

    Dogrusu ONEK eslesmesi: govde nereden turetildiyse (bkz. _kok), o
    govdeyle BASLAYAN herhangi bir kelimeyi yakalamak. ZH'de zaten boyle
    calisiyordu (sinirsiz alt dize arama) cunku Cince'de kelime siniri
    kavrami yok; TR/EN'de govde+devam icin ayni gevsekligi acikca
    kurmak gerekiyor.
    """
    if hedef == "tr" and not kesif:
        desenler = [(a, desen_kur(a, harf_duyarli=False)) for a in adaylar]
    elif hedef == "tr" and kesif:
        desenler = [
            (
                a,
                # tr_desen, re.IGNORECASE degil: ı ile i ayri harfler.
                re.compile(r"(?<![\w'\u2019])" + tr_desen(a) + r"[\w'\u2019]*"),
            )
            for a in adaylar
        ]
    elif hedef == "zh":
        desenler = [(a, re.compile(re.escape(a))) for a in adaylar]
    elif kesif:
        desenler = [
            (a, re.compile(r"(?<!\w)" + re.escape(a) + r"\w*", re.IGNORECASE))
            for a in adaylar
        ]
    else:
        desenler = [
            (a, re.compile(r"(?<!\w)" + re.escape(a) + r"(?!\w)", re.IGNORECASE))
            for a in adaylar
        ]

    for v in vuruslar:
        v["bulunan"] = [ad for ad, d in desenler if d.search(v["hedef_metin"])]
        v["bulunan_dar"] = [ad for ad, d in desenler if d.search(v["hedef_metin_dar"])]
    return vuruslar


# --------------------------------------------------------------- cikti


def _yaz_paragraf(etiket, metin, genislik, desen=None):
    girinti = " " * (len(etiket) + 2)
    govde = genislik - len(girinti)
    if desen:
        metin = desen.sub(lambda m: f"«{m.group(0)}»", metin)
    kolon = B._kolon_fabrikasi(metin)
    for j, s in enumerate(B._sar(metin, govde, kolon)):
        print((f"{etiket}  " if j == 0 else girinti) + s)


def ozet_yaz(vuruslar, adaylar, kesif, sorgu, kaynak, hedef, desen=None, arka_plan=None):
    print(f"\n'{sorgu}'  [{kaynak.upper()} -> {hedef.upper()}]")
    print(f"{len(vuruslar)} gecis, {len({v['bolum'] for v in vuruslar})} bolumde\n")

    if not vuruslar:
        return

    if kesif:
        print("Adaylar sozlukten degil, metinden KESFEDILDI (govde eslesmesi):")
        print(f"  {', '.join(adaylar) if adaylar else '(hicbiri)'}\n")

    sayim = defaultdict(list)
    eslesmeyen = []
    tek_tarafli = []
    for v in vuruslar:
        if v["tip"] == "tek_tarafli":
            tek_tarafli.append(v)
        elif v["bulunan"]:
            for ad in v["bulunan"]:
                sayim[ad].append(v["bolum"])
        else:
            eslesmeyen.append(v)

    print("=== KULLANILAN KARSILIKLAR ===")
    if not sayim:
        print("  hicbir aday hedef metinde bulunamadi")
    for ad, bolumler in sorted(sayim.items(), key=lambda kv: -len(kv[1])):
        b = sorted(set(bolumler))
        yer = f"bolum {b}" if len(b) <= 12 else f"{len(b)} bolum, ilk {b[:6]}..."
        print(f"  {ad}: {len(bolumler)} gecis, {yer}")

    if len(sayim) > 1:
        print("\n  ^ birden fazla karsilik var. Kasitli mi?")

    print(f"\n=== ESLESMEYEN ({len(eslesmeyen)}) ===")
    print("    Terim kaynakta var, bilinen hicbir karsilik hedefte yok.")
    print("    Yeni bir karsilik, atlanmis bir cumle, ya da kaymis hizalama.")
    if not eslesmeyen:
        print("  yok")
    zh_mi = kaynak == "zh" and desen is not None
    for v in eslesmeyen[:15]:
        ozet = re.sub(r"\s+", " ", v["hedef_metin"])[:110]
        im = "  ~" if v.get("genis") else ""
        # Cince kaynakta gecisin bir harf solu ve sagi: ayni pencere (占卜家)
        # tekrar ediyorsa eslesmeme buyuk olasilikla sozlukte eksik bir
        # bilesikten gelir, ceviriden degil.
        pen = f" 〔{zh_pencere(v['kaynak_metin'], desen)}〕" if zh_mi else ""
        print(f"  [bolum {v['bolum']}]{im}{pen} {ozet}")
    if len(eslesmeyen) > 15:
        print(f"  ... {len(eslesmeyen) - 15} tane daha (--tam ile hepsi)")
    if zh_mi and eslesmeyen:
        print()
        zh_bilesik_yaz(zh_bilesik_raporu(eslesmeyen, desen, arka_plan, dil=hedef))

    genisletilen = [v for v in vuruslar if v.get("genis")]
    # YALNIZCA genisletmeyle eslesenler. Bunlar tek tek bakilmaya deger:
    # gercek bir kaymanin duzelmesi de olabilir, komsu paragraftaki
    # alakasiz bir gecisin yanlislikla sayilmasi da. Ikisi sayilarda ayni
    # gorunur; toplamin icinde birakmak yanlis eslesmeyi gorunmez yapar.
    sadece_genis = [
        v
        for v in genisletilen
        if v.get("bulunan") and not v.get("bulunan_dar")
    ]
    if genisletilen:
        b = sorted({v["bolum"] for v in genisletilen})
        print(f"\n  ~ {len(genisletilen)} gecis kaymis bolgede; hedef metin komsu")
        print(f"    grupla genisletildi (bolum {b if len(b) <= 12 else b[:12]}).")
    if sadece_genis:
        print(f"\n=== YALNIZCA GENISLETMEYLE BULUNAN ({len(sadece_genis)}) ===")
        print("    Dar hedefte yoktu, komsu grupta bulundu. Dogrulanmali:")
        print("    kayma duzeltmesi mi, komsu paragraftan sizma mi?")
        for v in sadece_genis[:15]:
            ozet = re.sub(r"\s+", " ", v["hedef_metin_dar"])[:70] or "(bos)"
            print(f"  [bolum {v['bolum']}] {', '.join(v['bulunan'])}  <- dar: {ozet}")

    if tek_tarafli:
        print(f"\n=== HIZALANAMAYAN ({len(tek_tarafli)}) ===")
        print("    Kaynak paragrafin hedefte karsiligi yok. Cogunlukla")
        print("    birlestirilmis paragraf; bazen atlanmis metin.")
        b = sorted({v["bolum"] for v in tek_tarafli})
        print(f"  bolum {b if len(b) <= 20 else b[:20]}")


def tam_yaz(vuruslar, sorgu, kaynak, hedef, genislik, harf_duyarsiz, haric=None):
    desen = desen_kur_kaynak(sorgu, kaynak, harf_duyarsiz, haric)
    k_ad, h_ad = kaynak.upper(), hedef.upper()

    for v in vuruslar:
        etiketler = ", ".join(v.get("bulunan") or [])
        durum = f"  -> {etiketler}" if etiketler else "  -> ESLESMEYEN"
        if v["tip"] == "tek_tarafli":
            durum = "  -> HIZALANAMADI"
        bas = f"──── bolum {v['bolum']}{durum} "
        print(bas + "─" * max(4, genislik - len(bas)))

        _yaz_paragraf(k_ad, v["kaynak_metin"], genislik, desen)
        print()
        if v["hedef_metin"]:
            _yaz_paragraf(h_ad, v["hedef_metin"], genislik)
            print()


def main():
    ap = argparse.ArgumentParser(
        description="Bir terimin bolumler boyunca nasil cevrildigini gosterir."
    )
    ap.add_argument("sorgu")
    ap.add_argument(
        "--kaynak",
        choices=("zh", "en", "tr"),
        default=None,
        help="varsayilan: sorgudan kestirilir",
    )
    ap.add_argument(
        "--hedef",
        choices=("zh", "en", "tr"),
        default=None,
        help="varsayilan: tr (kaynak tr ise en)",
    )
    ap.add_argument(
        "--aday", action="append", default=[], help="karsilik adayi; tekrarlanabilir"
    )
    ap.add_argument("--bolum", default=None, help="'1-200' ya da '279'")
    ap.add_argument(
        "--tam", action="store_true", help="her gecisi paragraf paragraf yaz"
    )
    ap.add_argument("--harf-duyarsiz", action="store_true", dest="duyarsiz")
    ap.add_argument(
        "--haric", action="append", default=[],
        help="Cince: bu daha uzun terimin icindeki gecisleri sayma "
             "(orn. 灵体 icin --haric 星灵体). Sozlukte 'cince' alani olan "
             "terimler zaten otomatik haric tutulur; tekrarlanabilir",
    )
    ap.add_argument("--genislik", type=int, default=None)
    a = ap.parse_args()

    import shutil

    genislik = a.genislik or shutil.get_terminal_size((100, 40)).columns

    kaynak = a.kaynak or dili_kestir(a.sorgu)
    hedef = a.hedef or ("en" if kaynak == "tr" else "tr")
    if kaynak == hedef:
        sys.exit("kaynak ve hedef ayni olamaz")
    if not a.kaynak:
        print(
            f"kaynak dil '{kaynak}' varsayildi (--kaynak ile degistirin)",
            file=sys.stderr,
        )

    vuruslar, arka_plan = tara(
        a.sorgu, kaynak, hedef, bolum_araligi(a.bolum), a.duyarsiz, a.haric
    )

    adaylar, kesif = a.aday, False
    if not adaylar:
        adaylar = sozlukten_adaylar(a.sorgu, hedef)
    if not adaylar:
        kesif = True
        adaylar = adaylari_kesfet(
            [v["hedef_metin"] for v in vuruslar if v["hedef_metin"]], arka_plan,
            dil=hedef,
        )

    siniflandir(vuruslar, adaylar, hedef, kesif)

    if a.tam:
        tam_yaz(vuruslar, a.sorgu, kaynak, hedef, genislik, a.duyarsiz, a.haric)
    desen = desen_kur_kaynak(a.sorgu, kaynak, a.duyarsiz, a.haric) if kaynak == "zh" else None
    ozet_yaz(vuruslar, adaylar, kesif, a.sorgu, kaynak, hedef, desen=desen, arka_plan=arka_plan)


if __name__ == "__main__":
    main()
