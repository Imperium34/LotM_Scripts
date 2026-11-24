#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sablon_denetle.py -- sablon yazildiktan SONRA, ceviriden ONCE: sablonun karar
tablolarini (A.1, A.2, B) butun kaynaklara karsi sinar.

UST DUZEY SORU: "Sablon zaten verilmis bir karari yeniden mi veriyor, ya da
verilmemis bir karari verilmis mi sayiyor?"

Sablon becerisinin teslimden onceki son adimi bir aramadir: her [YENİ]
satirin ve her dondurulmus satirin Turkcesi butun dosyalarda aranir. Bunu
model yaparsa butun sozlugu baglaminda tutmasi gerekir; yapmazsa zaten
karara baglanmis bir terime yeni karsilik uydurmak -- becerinin en sik
hatasi -- sessiz kalir. Burada mekanik olarak yapilir; boylece sablon
ureticisine butun sozluk degil, Terim Dokumu ve Ayrilmis Sozcuk Dizini
yeter.

DENETIMLER
  A.1 (sablonun "yerlesik" dedigi)
    HATA   Ingilizcesi sozlukte bir terim, Turkcesi o terimin bicimlerinden
           hicbiri degil: sablon verilmis bir karari degistiriyor.
    UYARI  Turkcesi hicbir yerde gecmiyor (sozluk, words.md, ses haritalari,
           onceki sablonlar, yayimlanmis bolumler): "yerlesik" denilen
           karar aslinda yeni; A.2'ye [YENİ] diye girmeli.
  A.2 (sablonun "yeni" dedigi)
    UYARI  Turkcesi sozlukte baska bir terimin karsiligi: ya A.1'e tasinir
           ya iki kavram ayni sozcugu paylasiyor.
    UYARI  Ingilizcesi sozlukte bir terim: karar zaten verilmis.
    UYARI  Ayrilmis bir sozcugu iceriyor (Mertebe, salahiyet, yasak, eski
           karsilik; bkz. ayrilmis.py).
  B (dondurulmus satirlar)
    UYARI  Yasaklanmis ya da eski bir karsiligi iceriyor.
  A.1, A.2, B
    UYARI  Onceki bir sablonda AYNI Ingilizceye baska Turkce verilmis.
           Cince farkliysa bilinclidir; degilse bolumler arasi kayma.

CINCE ANAHTAR
  Ingilizce ceviri iki ayri Cince terimi tek sozcukle verebilir (深眠花 ve
  月亮花 ikisi de "Moon flower"; 符号 ve 象征 ikisi de "symbol"). Satirin
  Cincesi anahtaridir: sozlukle ve onceki sablonlarla Cince eslesir,
  Ingilizce yalniz Cincesi olmayan satirlarda kullanilir. Sablon yalniz
  Latin harfiyle yazildigi icin Cince yan dosyadadir: Ch_N.md'nin yanindaki
  Ch_N_zh.tsv, satir basina `Ingilizce<TAB>Cince` (Ingilizce, sablonun
  Ingilizce hucresindeki bicimlerden biri; # ile baslayan satir yorum).
  Ingilizce hucrede Cince yaziliysa o da okunur. Cincesi yazilmamis satirda da sozluk teriminin
  Cincesi bu bolumun Cince metninde hic gecmiyorsa Ingilizce eslesme
  sayilmaz: Ingilizce iki terimi birlestirmistir.

TEREDDUT satirlari denetlenmez: karar insanindir (kapanis_denetle ile ayni).

Kullanim:
    sablon_denetle.py ../Tools/Schemas/Ch_56.md
    sablon_denetle.py Ch_56.md --sablonlar DIZIN --cikti rapor.md
    sablon_denetle.py Ch_56.md --ayrinti     her satirin nerede bulundugu da
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import ayrilmis as AY
import kapanis_denetle as K
import lotm
from turkce import tr_kucult

SABLONLAR = lotm.KOK / "Tools" / "Schemas"
SES_HARITALARI = lotm.KOK / "Tools" / "Voice_Maps"

_EN_ONEK = re.compile(r"^(?:the|a|an|mr\.?|mrs\.?|miss|ms\.?|dr\.?)\s+", re.I)


def en_norm(s: str) -> str:
    """Ingilizce hucre bicimi -> karsilastirma anahtari: 'the sofa' -> 'sofa'."""
    s = re.sub(r"\s+", " ", K._PARANTEZ.sub("", s)).strip().strip("\"“”'").lower()
    onceki = None
    while s != onceki:
        onceki, s = s, _EN_ONEK.sub("", s)
    return s


def tr_norm(s: str) -> str:
    """Turkce bicim -> karsilastirma anahtari; etiketler ([GEÇİCİ]) ve govde tiresi atilir."""
    s = re.sub(r"\[[^\]]*\]", "", s)
    return re.sub(r"\s+", " ", tr_kucult(s.strip().rstrip("-").rstrip())).strip()


# Hitap adin parcasi degildir: "Bay Tris" karari "Tris"in kararidir.
_HITAP_TR = re.compile(
    r"^(?:Bay ve Bayan|Bay|Bayan|Sayın)\s+|\s+(?:Bey|Hanım|Efendi|Beyefendi|Hanımefendi)$"
)


def hitapsiz(s: str) -> str:
    return _HITAP_TR.sub("", s.strip()).strip() or s


_NOKTALAMA = ".,;:!?…\"'“”‘’"
_SERTLESTIR = {"b": "p", "c": "ç", "d": "t", "ğ": "k", "g": "k"}
_UNLU = set("aeıioöuü")  # sapkali âîû bilincli olarak disarida
_DAR_UNLU = set("ıiuü")
_UNSUZ = set("bcçdfgğhjklmnprsştvyz")
_HARF_TIRE = re.compile(r"(?<=[a-zçğıöşüâîû])-(?=[a-zçğıöşüâîû])")

# Turkce ad cekim ekleri (sagdan sola): kesme -> hal/ki -> iyelik -> cogul.
_HAL_EKI = re.compile(
    r"(?:ndaki|ndeki|daki|deki|taki|teki|ki"
    r"|ndan|nden|dan|den|tan|ten"
    r"|nda|nde|da|de|ta|te"
    r"|nın|nin|nun|nün|ın|in|un|ün"
    r"|yla|yle|la|le"
    r"|yı|yi|yu|yü|nı|ni|nu|nü"
    r"|ya|ye|na|ne"
    r"|ı|i|u|ü|a|e)$"
)
_IYELIK_EKI = re.compile(
    r"(?:larımız|lerimiz|larınız|leriniz|ları|leri"
    r"|ımız|imiz|umuz|ümüz|ınız|iniz|unuz|ünüz"
    r"|mız|miz|muz|müz|nız|niz|nuz|nüz"
    r"|sı|si|su|sü"
    r"|ım|im|um|üm|ın|in|un|ün"
    r"|ı|i|u|ü)$"
)
_COGUL_EKI = re.compile(r"(?:lar|ler)$")
_KESME_EKI = re.compile(
    r"['’](?:"
    r"(?:lar|ler)?(?:ımız|imiz|umuz|ümüz|ınız|iniz|unuz|ünüz|sı|si|su|sü|ım|im|um|üm|ın|in|un|ün|ı|i|u|ü)?"
    r"(?:ndaki|ndeki|daki|deki|taki|teki|ki|ndan|nden|dan|den|tan|ten|nda|nde|da|de|ta|te"
    r"|nın|nin|nun|nün|ın|in|un|ün|yla|yle|la|le|yı|yi|yu|yü|nı|ni|nu|nü|ya|ye|na|ne|ı|i|u|ü|a|e)"
    r"|(?:lar|ler)(?:ı|i|u|ü)?"
    r"|(?:ımız|imiz|umuz|ümüz|ınız|iniz|unuz|ünüz|mız|miz|muz|müz|nız|niz|nuz|nüz|sı|si|su|sü|ım|im|um|üm)"
    r")$"
)
_FIIL_EK_RE = re.compile(lotm._FIIL_ILK_EK + r"[^\W\d_]*$")


def _unlu_dusur(kok: str) -> str | None:
    """Unlu dusmesi govdesi: 'şehir' -> 'şehr', 'isim' -> 'ism', 'kayıt' -> 'kayt'."""
    if len(kok) >= 4 and kok[-3] in _UNSUZ and kok[-2] in _DAR_UNLU and kok[-1] in _UNSUZ:
        return kok[:-2] + kok[-1]
    return None


def _kok_adaylari(w: str) -> dict[str, bool]:
    """
    Bir Turkce sozcugun olasi kok adaylari -> guclu_mu.

    guclu_mu yalnizca 3 harfli bir kokte tek harflik unlu eki atilmissa False
    olur ("dere"->"der", "deri"->"der"): boylece iki ayri 4 harfli kok
    (dere/deri, sure/suru, yara/yari) yalnizca 3 harfli ortak onekten eslesmez.
    """
    adaylar: dict[str, bool] = {w: True}

    def ekle(kok: str, guclu: bool) -> None:
        if kok:
            adaylar[kok] = adaylar.get(kok, False) or guclu

    g = lotm.fiil_govdesi(w)
    if g:
        ekle(g, True)
    m = _KESME_EKI.search(w)
    if m and m.start() >= 2:
        ekle(w[: m.start()], True)

    for desen in (_HAL_EKI, _IYELIK_EKI, _COGUL_EKI):
        for s in list(adaylar):
            m = desen.search(s)
            if not m:
                continue
            kok, ek = s[: m.start()], m.group()
            min_kok = 2 if ek in ("lar", "ler", "ları", "leri") else 3
            if len(kok) < min_kok:
                continue
            guclu = len(kok) >= 4 or (len(w) - len(kok)) >= 2
            ekle(kok, guclu)
            if ek[0] in _UNLU and kok[-1] in _SERTLESTIR:
                ekle(kok[:-1] + _SERTLESTIR[kok[-1]], guclu)

    for s, guclu in list(adaylar.items()):
        d = _unlu_dusur(s)
        if d:
            ekle(d, guclu)
    return adaylar


def _fiil_eslesir(govde: str, kelime: str) -> bool:
    """Fiil govdesi ('et', 'yitir', 'ol') cekimli bicimle ('etti', 'ediyor', 'yitirdi') eslesir mi?"""
    return any(
        kelime.startswith(g)
        and (len(kelime) == len(g) or bool(_FIIL_EK_RE.match(kelime[len(g) :])))
        for g in K.govde_bicimleri(govde)
    )


def _kelime_esit(a: str, b: str) -> bool:
    """
    Iki Turkce sozcuk ayni kokun cekimli bicimleri mi?
    Ek/yumusama/unlu dusmesi/kesme/fiil cekimi: usul/usulü, beden/bedeni,
    sarkaç/sarkacı, çiçeği/çiçekleri, kâhin/kâhinlerin, şehir/şehri,
    Tanrıça/Tanrıça'nın, et/etmek/etti/ediyor. Sapka farki esit DEGILDIR.
    """
    a, b = a.strip(_NOKTALAMA), b.strip(_NOKTALAMA)
    if not a or not b:
        return False
    if a == b:
        return True
    ka, kb = _kok_adaylari(a), _kok_adaylari(b)
    if any(ka[k] or kb[k] for k in ka.keys() & kb.keys()):
        return True
    ga, gb = lotm.fiil_govdesi(a), lotm.fiil_govdesi(b)
    if ga and _fiil_eslesir(ga, b):
        return True
    if gb and _fiil_eslesir(gb, a):
        return True
    if (len(a) >= 4 or a in ("et", "ol")) and _fiil_eslesir(a, b):
        return True
    if (len(b) >= 4 or b in ("et", "ol")) and _fiil_eslesir(b, a):
        return True
    return False


def bicim_esit(a: str, b: str) -> bool:
    """
    Iki Turkce bicim AYNI karar mi? Sablonlar terimi cogu zaman govde, cekimli
    bicim ya da araya niteleyici alarak yazar: "kehanet usul" = "Kehanet usulü",
    "şirazesini yitir" = "Şirazesini Yitirmek", "himaye et" = "himaye",
    "tekerlekli fayton" ⊂ "iki tekerlekli fayton", "umumî fayton" ⊂ "umumî at
    faytonu", "elf çiçeği" = "elf çiçekleri". Kisa bicimin her kelimesi uzunda
    ayni sirayla ve ek farkiyla gecer (sirali altdizi). Sapka farki (umumi /
    umumî, Alem / Âlem) esit DEGILDIR: o bir karar farkidir.
    """
    wa = _HARF_TIRE.sub(" ", tr_norm(a)).split()
    wb = _HARF_TIRE.sub(" ", tr_norm(b)).split()
    if not wa or not wb:
        return False
    kisa, uzun = sorted((wa, wb), key=len)
    it = iter(uzun)
    return all(any(_kelime_esit(x, y) for y in it) for x in kisa)


def _aynen_ac(trler, enler) -> set:
    """'aynen' (ad Ingilizcedeki gibi) -> Ingilizce bicimler."""
    out = set()
    for t in trler:
        out |= {tr_norm(e) for e in enler} if tr_norm(t) == "aynen" else {tr_norm(t)}
    return out - {""}


_ZH = re.compile(r"[\u3400-\u9fff][\u3400-\u9fff·・]*")


def zh_hucre(hucre: str) -> list:
    """Ingilizce hucredeki Cince: 'Moon flower (深眠花)' -> ['深眠花']."""
    return _ZH.findall(hucre)


def zh_parcalari(t) -> list:
    return [z.strip() for z in (t.zh or "").split("/") if z.strip()]


def zh_yan_yolu(sablon: Path) -> Path:
    return Path(sablon).with_name(Path(sablon).stem + "_zh.tsv")


def zh_yan_oku(yol: Path) -> dict:
    """Ch_N_zh.tsv -> {en_norm(Ingilizce): [Cince, ...]}; dosya yoksa {}."""
    out: dict = {}
    if not Path(yol).exists():
        return out
    for satir in lotm.metin_oku(yol).splitlines():
        if not satir.strip() or satir.lstrip().startswith("#") or "\t" not in satir:
            continue
        en, zh = satir.split("\t", 1)
        zhler = zh_hucre(zh)
        for e in en.split("/"):
            if en_norm(e) and zhler:
                out.setdefault(en_norm(e), []).extend(z for z in zhler if z not in out.get(en_norm(e), []))
    return out


def gecici_mi(satir) -> bool:
    return any("GEÇİCİ" in t or "GECICI" in t for t in satir.tr)


@dataclass
class SablonSatiri:
    bolum: str  # "A.1" | "A.2" | "B"
    en: list  # Ingilizce bicimler
    tr: list  # Turkce bicimler (govde tiresi atilmis)
    tereddut: bool = False
    zh: list = field(default_factory=list)  # Ingilizce hucredeki Cince anahtar


def sablon_satirlari(metin: str, zh_yan: dict | None = None) -> list:
    """A.1, A.2 ve B tablolarinin satirlari; zh_yan: zh_yan_oku() ciktisi."""
    p = K.bolumler(metin)
    zh_yan = zh_yan or {}

    def zh_al(hucre, enler):
        return zh_hucre(hucre) or list(dict.fromkeys(
            z for e in enler for z in zh_yan.get(en_norm(e), [])))

    def bul(*anahtarlar):
        for a in anahtarlar:
            for k, v in p.items():
                if k.startswith(a):
                    return v
        return ""

    out = []
    for ad in ("A.1", "A.2"):
        govde = bul(ad)
        hucreler = [h for h in K.tablo(govde) if len(h) >= 2]
        for st, h in zip(K.satirlar(govde), hucreler):
            out.append(SablonSatiri(ad, st.en, [t for t, _g in st.tr], st.tereddut,
                                    zh_al(h[0], st.en)))
    for h in K.tablo(bul("B. DONDURULAN", "B.")):
        if len(h) < 2:
            continue
        en = K._bicimler(h[0])
        tr = [K._govde_ayir(k)[0] for k in K.kaliplar(h[1])]
        if tr:
            out.append(SablonSatiri("B", en, tr, zh=zh_al(h[0], en)))
    return out


@dataclass
class Kaynaklar:
    """Denetimin karsilastirdigi her sey; testlerde elle kurulur."""

    terimler: list = field(default_factory=list)  # sozluk + words.md Terim'leri
    salahiyetler: list = field(default_factory=list)
    ayrilmis: list = field(default_factory=list)  # ayrilmis.Ayrilmis
    metinler: dict = field(default_factory=dict)  # ad -> ham metin (words.md, ses haritalari)
    sablonlar: dict = field(default_factory=dict)  # bolum no -> sablon metni
    zh_yanlar: dict = field(default_factory=dict)  # bolum no -> zh_yan_oku() ciktisi
    yayim: list = field(default_factory=list)  # lotm.Bolum (Turkce)
    zh_metin: str = ""  # bu bolumun Cince metni; bossa Cince suzme yapilmaz
    # onceki sablonu olan bolumlerin Cince metni: Ch_N_zh.tsv'si olmayan eski
    # sablonlarda (<63) 'ayni Ingilizce' uyarisi Cince metinden suzulur
    zh_metinler: dict = field(default_factory=dict)
    no: int | None = None  # denetlenen bolum: eski karsiligin kapisindan (bolum_siniri) once mi

    def __post_init__(self):
        self.en_dizin: dict = {}
        self.tr_dizin: dict = {}
        self.zh_dizin: dict = {}
        for t in self.terimler:
            for z in zh_parcalari(t):
                self.zh_dizin.setdefault(z, []).append(t)
            for a in set(t.arama_adaylari()) | ({t.en} if t.en else set()):
                self.en_dizin.setdefault(en_norm(a), []).append(t)
            for b in t.tr_bicimleri():
                self.tr_dizin.setdefault(tr_norm(b), []).append(t)
        for k in self.salahiyetler:
            if k.get("turkce"):
                self.tr_dizin.setdefault(tr_norm(str(k["turkce"])), []).append(
                    lotm.Terim(tr=str(k["turkce"]), zh=str(k.get("cince") or ""),
                               kategori="salahiyet")
                )
        self.sablon_satirlari = {
            no: sablon_satirlari(m, self.zh_yanlar.get(no)) for no, m in self.sablonlar.items()
        }
        self._metin_kucuk = {ad: tr_kucult(m) for ad, m in self.metinler.items()}


def yukle(no: int, sablon_klasoru: Path = SABLONLAR) -> Kaynaklar:
    sozluk = lotm.sozluk_yukle(kelimeler=True)
    salahiyetler = lotm.salahiyetler_yukle()
    metinler = {}
    for yol in [lotm.KELIMELER, lotm.SOZLUK_YOLU, *sorted(SES_HARITALARI.glob("*.md"))]:
        if Path(yol).exists():
            metinler[Path(yol).name] = lotm.metin_oku(yol)
    sablonlar, zh_yanlar = {}, {}
    for yol in sorted(Path(sablon_klasoru).glob("Ch_*.md")):
        m = re.fullmatch(r"Ch_(\d+)\.md", yol.name)
        if m and int(m.group(1)) < no:
            sablonlar[int(m.group(1))] = lotm.metin_oku(yol)
            zh_yanlar[int(m.group(1))] = zh_yan_oku(zh_yan_yolu(yol))
    try:
        yayim = [b for b in lotm.bolumler_tr() if b.no is not None and b.no < no]
    except FileNotFoundError:
        yayim = []
    try:
        zh_hepsi = {b.no: b.metin for b in lotm.bolumler_zh() if b.no in sablonlar or b.no == no}
    except FileNotFoundError:
        zh_hepsi = {}
    zh_metin = zh_hepsi.pop(no, "")
    return Kaynaklar(
        terimler=sozluk.terimler,
        salahiyetler=salahiyetler,
        ayrilmis=AY.kayitlar(
            [t for t in sozluk.terimler if not t.kategori.startswith(lotm.KELIME_KATEGORI)],
            [t for t in sozluk.terimler if t.kategori.startswith(lotm.KELIME_KATEGORI)],
            salahiyetler,
        ),
        metinler=metinler,
        sablonlar=sablonlar,
        zh_yanlar=zh_yanlar,
        yayim=yayim,
        zh_metin=zh_metin,
        zh_metinler=zh_hepsi,
        no=no,
    )


# ------------------------------------------------------------ aramalar


def nerede(bicim: str, kay: Kaynaklar, en_cok: int = 3) -> list:
    """Turkce bicimin karara baglandigi ya da gectigi yerler: ['words.md:174', ...]."""
    out = []
    n = tr_norm(bicim)
    if n in kay.tr_dizin:
        out.append("sözlük: " + ", ".join(dict.fromkeys(t.tr for t in kay.tr_dizin[n])))
    else:
        nw = n.split()
        eslesen = [
            t.tr
            for k, ts in kay.tr_dizin.items()
            if (kw := k.split()) and len(kw) == len(nw)
            and all(_kelime_esit(x, y) for x, y in zip(nw, kw))
            for t in ts
        ]
        if eslesen:
            out.append("sözlük: " + ", ".join(dict.fromkeys(eslesen)))
    for no in sorted(kay.sablon_satirlari, reverse=True):
        if any(n in {tr_norm(t) for t in s.tr} for s in kay.sablon_satirlari[no]):
            out.append(f"Ch_{no}")
            break
    for ad, kucuk in kay._metin_kucuk.items():
        i = kucuk.find(n)
        if i >= 0:
            out.append(f"{ad}:{kucuk.count(chr(10), 0, i) + 1}")
    if len(out) < en_cok:
        desen = lotm.desen_kur(bicim, harf_duyarli=bicim[:1].isupper())
        for b in sorted(kay.yayim, key=lambda b: -b.no):
            if desen.search(b.metin):
                out.append(f"bölüm {b.no}")
                break
    return out[:en_cok]


def sozluk_terimleri(s: SablonSatiri, kay: Kaynaklar) -> tuple:
    """
    (terimler, birlestirilmis) -- satirin sozlukte karsiligi olan terimler.
    Cincesi yazilmissa Cinceyle eslesir. Yazilmamissa Ingilizceyle; ama
    Cincesi bu bolumde hic gecmeyen terim atilir (birlestirilmis): Ingilizce
    burada baska bir Cince terimi ayni sozcukle vermistir.
    """
    if s.zh:
        return [t for z in s.zh for t in kay.zh_dizin.get(z, [])], []
    terimler = [t for e in s.en for t in kay.en_dizin.get(en_norm(e), [])]
    if not kay.zh_metin:
        return terimler, []
    tutan, atilan = [], []
    for t in terimler:
        zs = zh_parcalari(t)
        (atilan if zs and not any(z in kay.zh_metin for z in zs) else tutan).append(t)
    return tutan, atilan


def ayni_karar(eski: set, yeni: set, kay: Kaynaklar) -> bool:
    """
    Iki sablonun Turkce bicimleri ayni karar mi? Ortak bicim; ya da biri
    otekinin icinde (B'deki cekirdek "yel değirmen" ⊂ A.1'deki "oyuncak yel
    değirmeni"); ya da ikisi ayni sozluk teriminin bicimleri (İlahlar Çağı /
    Dördüncü Çağ: words.md'de esanlamli).
    """
    if eski & yeni:
        return True
    if any(bicim_esit(a, b) for a in eski for b in yeni):
        return True
    for b in yeni:
        for t in kay.tr_dizin.get(b, []):
            if eski & {tr_norm(x) for x in t.tr_bicimleri()}:
                return True
    return False


def _bolumde_yok(trler: set, kay: Kaynaklar) -> bool:
    """Bu Turkce bicimler sozlukte Cincesi bu bolumde hic gecmeyen bir terimin mi?"""
    if not kay.zh_metin:
        return False
    zs = [z for b in trler for t in kay.tr_dizin.get(b, []) for z in zh_parcalari(t)]
    return bool(zs) and not any(z in kay.zh_metin for z in zs)


def onceki_kararlar(satir: SablonSatiri, kay: Kaynaklar) -> list:
    """[(bolum no, onceki satir)] -- ayni Ingilizceye BASKA Turkce vermis en yakin sablon."""
    anahtarlar = {en_norm(e) for e in satir.en} - {""}
    simdiki = _aynen_ac(satir.tr, satir.en)
    for no in sorted(kay.sablon_satirlari, reverse=True):
        for s in kay.sablon_satirlari[no]:
            if s.tereddut or not anahtarlar & {en_norm(e) for e in s.en}:
                continue
            if satir.zh and s.zh and not set(satir.zh) & set(s.zh):
                continue  # ayni Ingilizce, baska Cince: baska kavram
            eski_zh = kay.zh_metinler.get(no, "")
            if satir.zh and not s.zh and eski_zh and not any(z in eski_zh for z in satir.zh):
                continue  # eski sablonun Cince anahtari yok; bu Cince o bolumde hic gecmiyor
            if s.zh and not satir.zh and kay.zh_metin and not any(z in kay.zh_metin for z in s.zh):
                continue  # ayni durum, ters yon
            if gecici_mi(s):
                return []  # gecici karar: sonradan degismesi beklenir
            onceki = _aynen_ac(s.tr, s.en)
            if onceki and not satir.zh and _bolumde_yok(onceki, kay):
                continue  # onceki karar baska bir Cince terimin: Ingilizce birlestirmis
            if onceki and not ayni_karar(onceki, simdiki, kay):
                return [(no, s)]
            return []  # en yakin sablon ayni karari vermis
    return []


@dataclass
class Bulgu:
    seviye: str  # HATA | UYARI
    bolum: str
    satir: str
    mesaj: str


def _etiket(s: SablonSatiri) -> str:
    return f"{' / '.join(s.tr)} ← {' / '.join(s.en) or '—'}"


def erken(t, no: int | None) -> bool:
    """Bolum, terimin eski karsiliktan yeni ada gecis bolumunden once mi?"""
    g = lotm.gecis_bolumu(t)
    return bool(g and no is not None and no < g)


def denetle(metin: str, kay: Kaynaklar, zh_yan: dict | None = None) -> tuple:
    """(bulgular, satirlar)"""
    satirlar = sablon_satirlari(metin, zh_yan)
    out = []
    for s in satirlar:
        if s.tereddut:
            continue
        et = _etiket(s)
        en_terimler, _birlesik = sozluk_terimleri(s, kay)
        tr_n = {tr_norm(t) for t in s.tr}

        # Ad kurali: Turkcesi Ingilizcesiyle ayni (ya da "aynen") olan satir
        # bir kisi adidir; sozlukte ayni Ingilizceyi parantezde tasiyan kod
        # adi kaydina (Yıldız (Leonard Mitchell)) baglanmaz.
        ad_satiri = tr_n <= ({en_norm(e) for e in s.en} | {"aynen"})
        sozlukte = [b for t in en_terimler for b in t.tr_bicimleri()]
        # Kapidan (bolum_siniri) once eski karsilik o donemin dogru kelimesidir
        # (Ayin/ritüel 22, Rol İfası/rol yapma 93): lotm.gecis_bolumu.
        sozlukte += [b for t in en_terimler if erken(t, kay.no)
                     for e in t.eski_karsiliklar or [] for b in (e, re.sub(r"m[ae]k?$", "", e))]
        if s.bolum == "A.1" and en_terimler and not ad_satiri:
            if not any(bicim_esit(a, b) for a in s.tr for b in sozlukte):
                adlar = ", ".join(dict.fromkeys(t.tr for t in en_terimler))
                # Ozel ad ya da cok kelimeli Ingilizce: kesin celiski. Tek
                # kucuk harfli sozcuk (materials, symbol) bircok Cince
                # sozcugu karsilar; ayni kavram olmayabilir.
                kesin = any(" " in e.strip() or e.strip()[:1].isupper() for e in s.en)
                out.append(Bulgu(
                    "HATA" if kesin else "UYARI", s.bolum, et,
                    f"sözlükte bu İngilizcenin karşılığı {adlar}; şablon başka bir karar "
                    f"yazıyor" + ("" if kesin else " (tek, sıradan bir İngilizce sözcük: "
                                  "Çince aynıysa çelişki)")))
        if s.bolum == "A.1":
            yok = [
                t for t in s.tr
                if not any(bicim_esit(t, b) for b in sozlukte)
                and not nerede(hitapsiz(t), kay, en_cok=1)
            ]
            if yok:
                out.append(Bulgu("UYARI", s.bolum, et,
                                 f"{', '.join(yok)} hiçbir yerde karara bağlanmamış (sözlük, "
                                 f"words.md, ses haritaları, önceki şablonlar, yayımlanmış "
                                 f"bölümler): yerleşik değil, A.2'ye [YENİ] diye girmeli"))
        if s.bolum == "A.2":
            for t in s.tr:
                sahipler = kay.tr_dizin.get(tr_norm(t), [])
                if sahipler:
                    adlar = ", ".join(dict.fromkeys(
                        f"{x.tr} ({x.en or x.zh or x.kategori})" for x in sahipler))
                    out.append(Bulgu("UYARI", s.bolum, et,
                                     f"'{t}' sözlükte zaten var: {adlar}. Aynı kavramsa A.1'e "
                                     f"taşınır; değilse iki kavram aynı sözcüğü paylaşıyor"))
            if en_terimler:
                adlar = ", ".join(dict.fromkeys(t.tr for t in en_terimler))
                if not tr_n & {tr_norm(b) for t in en_terimler for b in t.tr_bicimleri()}:
                    out.append(Bulgu("UYARI", s.bolum, et,
                                     f"İngilizcesi sözlükte bir terim ({adlar}): karar zaten "
                                     f"verilmiş"))
        if s.bolum in ("A.2", "B"):
            turler = AY.CARPISMA_TURLERI if s.bolum == "A.2" else ("yasak", "eski")
            for t in s.tr:
                for k, (a, b) in AY.icerenler(t, kay.ayrilmis, turler):
                    if k.tur == "eski" and k.kapi and kay.no is not None and kay.no < k.kapi:
                        continue  # kapidan once eski bicim dogru
                    if tr_norm(k.kelime) == tr_norm(t) and s.bolum == "A.2" and k.tur in ("mertebe", "salahiyet"):
                        continue  # ayni sozcuk: yukaridaki 'sözlükte zaten var' soyler
                    if k.tur == "yasak":
                        mesaj = (f"'{t[a:b]}' words.md'de yasaklı ya da başka bir yere ayrılmış "
                                 f"(madde: {k.sahip}): {k.not_}. Satır o anlamdaysa sorun yok")
                    else:
                        mesaj = f"'{t[a:b]}' ayrılmış sözcük — {k.tur}, {k.sahip}"
                    out.append(Bulgu("UYARI", s.bolum, et, mesaj))
        for no, onceki in onceki_kararlar(s, kay):
            out.append(Bulgu("UYARI", s.bolum, et,
                             f"Ch_{no} ({onceki.bolum}) aynı İngilizceye "
                             f"'{' / '.join(onceki.tr)}' vermiş. Çince farklıysa bilinçlidir; "
                             f"değilse bölümler arası kayma"))
    out += sizinti(metin)
    return out, satirlar


# Sablon cevirmenin istemine eklenir: Latin disi yazi, cekirdegin § numarasi ve
# ses haritasi / Yanki Defteri kodu cevirmene bir sey soylemez, metne de sizabilir
# (73: "ters방향으로", "Sabit Çekirdek §9", "K1.1–K1.2", "Yankı #80"). Tablo
# satirlari Latin disi denetiminden muaf: Ingilizce hucre Cince anahtar tasiyabilir.
_LATIN_DISI = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]+")
_KOD = re.compile(r"§\s?\d+(?:\.\d+)*|\b(?:[A-ZÇĞİÖŞÜ]{1,4}\d+\.\d+)(?:[–-][A-ZÇĞİÖŞÜ]{0,4}\d+\.\d+)?\b|Yankı\s+#\d+")


def sizinti(metin: str) -> list:
    """Latin disi yazi (tablo disinda) ve § / harita kodu: UYARI."""
    out = []
    for i, satir in enumerate(metin.splitlines(), 1):
        if not satir.lstrip().startswith("|"):
            for m in _LATIN_DISI.finditer(satir):
                out.append(Bulgu("UYARI", "metin", f"satır {i}",
                                 f"Latin dışı yazı '{m.group()}': şablon yalnız Latin harfiyle yazılır "
                                 f"(Çince anahtar Ch_N_zh.tsv'ye)"))
        for m in _KOD.finditer(satir):
            out.append(Bulgu("UYARI", "metin", f"satır {i}",
                             f"'{m.group()}': kurala adıyla atıf yapılır; § numarası ve harita kodu "
                             f"çevirmene bir şey söylemez"))
    return out


def rapor_md(ad: str, bulgular: list, satirlar: list, kay: Kaynaklar, ayrinti: bool) -> str:
    say = {b: sum(1 for s in satirlar if s.bolum == b) for b in ("A.1", "A.2", "B")}
    hata = [b for b in bulgular if b.seviye == "HATA"]
    uyari = [b for b in bulgular if b.seviye == "UYARI"]
    out = [
        f"# Şablon Denetimi — {ad}",
        "",
        f"_{say['A.1']} A.1, {say['A.2']} A.2, {say['B']} B satırı denetlendi "
        f"({sum(1 for s in satirlar if s.tereddut)} TEREDDÜT atlandı; "
        f"{sum(1 for s in satirlar if s.zh)} satır Çince anahtarlı); "
        f"{len(hata)} HATA, {len(uyari)} UYARI._",
    ]
    for baslik, liste in (("HATA", hata), ("UYARI", uyari)):
        out += ["", f"## {baslik}", ""]
        out += [f"- **{b.bolum}** `{b.satir}` — {b.mesaj}" for b in liste] or ["_yok_"]
    if ayrinti:
        out += ["", "## Satırların bulunduğu yerler", ""]
        for s in satirlar:
            yerler = {t: nerede(t, kay) for t in s.tr}
            out.append(f"- **{s.bolum}** `{_etiket(s)}` — " + "; ".join(
                f"{t}: {', '.join(y) or 'hiçbir yerde'}" for t, y in yerler.items()))
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("sablon", type=Path)
    ap.add_argument("--bolum", type=int, help="bolum numarasi (varsayilan: dosya adindan)")
    ap.add_argument("--sablonlar", type=Path, default=SABLONLAR, help="onceki sablonlarin klasoru")
    ap.add_argument("--cikti", type=Path)
    ap.add_argument("--ayrinti", action="store_true", help="her satirin bulundugu yerler")
    a = ap.parse_args()
    no = a.bolum
    if no is None:
        m = re.search(r"Ch_(\d+)", a.sablon.name)
        if not m:
            sys.exit("HATA: bolum numarasi dosya adindan cikmadi; --bolum verin")
        no = int(m.group(1))
    metin = lotm.metin_oku(a.sablon)
    kay = yukle(no, a.sablonlar)
    zh_yan = zh_yan_oku(zh_yan_yolu(a.sablon))
    bulgular, satirlar = denetle(metin, kay, zh_yan)
    rapor = rapor_md(a.sablon.name, bulgular, satirlar, kay, a.ayrinti)
    if a.cikti:
        lotm.atomik_yaz(a.cikti, rapor)
        print(f"yazıldı: {a.cikti}", file=sys.stderr)
    else:
        print(rapor)
    return 1 if any(b.seviye == "HATA" for b in bulgular) else 0


if __name__ == "__main__":
    sys.exit(main())
