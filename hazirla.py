#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hazirla.py -- ceviriden ONCE: bir bolumun kaynak metninde gecen terimlerin
dokumu (Terim Dokumu), sablon uretecek modele verilmek uzere.

UST DUZEY SORU: "Bu bolumde HANGI kararlari zaten verdim?"

Diger betiklerin hepsi ceviriden SONRA calisir. Ceviriden once tek adim
bolum acilis sablonudur ve onu bir dil modeli uretir: butun sozluk.yml'i
(3000+ satir), words.md'yi ve ileride salahiyetler.yml'i (5000+ satir)
okuyup bu bolumde hangi terimlerin gectigini kendisi bulmaya calisir.
Sablon becerisinin kendi notu en sik hatayi soyle tarif ediyor: zaten
yerlesmis bir terime yeni bir karsilik uydurmak. Hangi terimin bolumde
gectigi bir YARGI degil bir ARAMADIR; burada mekanik olarak yapilir.

NE URETIR (tek Markdown dosyasi)
--------------------------------
  1. Yerlesmis terimler, OKUMA SIRASIYLA: sozluk.yml + words.md kayitlari
     bolumun Cincesinde (Cincesi girilmemisse Ingilizcesinde) gecenler.
     Turkce karsilik, kacinilacak eski karsiliklar, ceviri katmani
     eklemeleri (mudahale: ozgun / degistirme -- kaynak bunlari
     curutemez), yayimlanmis metindeki kullanim ve aciklama (dondurulmus
     dualar ve tazim isimleri cogunlukla buradadir).
  2. Salahiyetler: salahiyetler.yml'de Cincesi bolumde gecen kayitlar,
     tek karsilik ve Ingilizce tuzagi ile.
  3. Sozlukte olmayan adaylar: Ingilizcede buyuk harfle gecen ve hicbir
     sozlukte olmayan adlar, Ingilizce metinde ilk gectigi bolumle.
     O bolum yayimlanmissa karsiligi yayimlanmis metindedir (yazilip
     sozluge geri tasinmamis terimler); bakmak icin komut verilir.
  4. Tarama makbuzu: aday, eslesme ve aday ad sayilari.

KAPI (bolum_siniri) BURADA YOKTUR: okurun sozluk sayfasinda neyi ne zaman
gorecegini belirler, cevirmenin hangi kelimeyi kullanacagini degil.

Kullanim:
    hazirla.py 54                       ekrana
    hazirla.py 54 --cikti Ch_54_terimler.md
    hazirla.py 54 --notlar              cevirmen notlarini da ekle (uzun)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import capa as _capa
import lotm
from toplu_denetle import harf_duyarli_mi
from turkce import tr_kucult

# Bu kategoriler words.md'de ya da sozlukte bir KISI/kod adi listesidir;
# Ingilizce aday taramasinda bilinen ad sayilirlar.
_EN_KELIME = re.compile(r"[A-Za-z][A-Za-z'\-]+")
# Buyuk harfle baslayan ad obegi: "Backlund", "Tingen City", "House of Wind"
# Yalniz BOSLUK: satir sonu obegi bolmeli ("...Requester\n\nChapter" bir
# baslik ve bir sonraki satirdir, tek ad degil). Iyelik "'s" ayrica atilir.
_AD_OBEGI = re.compile(
    r"(?<![\w'])[A-Z][a-z\-]+(?:'[a-z]+)?"
    r"(?:[ ]+(?:of|the|de|von|van)[ ]+[A-Z][a-z\-]+|[ ]+[A-Z][a-z\-]+)*"
)
_IYELIK = re.compile(r"(?:'s|')$")
# Cumle basinda buyuk harf her kelimeyi ad gibi gosterir; bunlar ve
# Ingilizcenin buyuk harfle yazilan siradan sozcukleri aday sayilmaz.
_SIRADAN = set(
    """I I'm I'll I've I'd Mr Mrs Ms Miss Sir Madam Lady Lord Chapter The A An And But Or
    If When Then This That These Those There Here What Who Why How Where Which It Its
    He She They We You His Her Their Our Your My Me Him Them Us No Yes Not Oh Ah Ahem
    Well So As At By For From In Into On Of To With Without After Before Because Since
    Although Though While Just Only Even Still Yet Also Then Now However Moreover Instead
    Perhaps Maybe Indeed Of Sunday Monday Tuesday Wednesday Thursday Friday Saturday
    January February March April May June July August September October November December
    God Goddess Lady Sir""".split()
)


@dataclass
class Eslesme:
    terim: lotm.Terim
    nasil: str  # "zh" | "en"
    sayi: int
    ilk: int  # kaynak metindeki ilk konum (okuma sirasi icin)
    yayim: list = field(default_factory=list)  # bu terimin gectigi yayimlanmis bolumler


# ---------------------------------------------------------------- kaynak


def kaynaklar(no: int) -> tuple:
    """(zh_metin | None, en_metin | None)."""
    def al(f):
        try:
            b = lotm.bolum_sozlugu(f()).get(no)
        except (FileNotFoundError, OSError):
            return None
        return b.metin if b else None

    return al(lotm.bolumler_zh), al(lotm.bolumler_en)


def _zh_parcalari(t) -> list:
    """Cince anahtar parcalari; tek karakter yalnizca kasitliysa (「」)."""
    return [
        z.strip()
        for z in (t.zh or "").split("/")
        if z.strip() and (len(z.strip()) > 1 or t.zh_kesin)
    ]


def _bilesik_deseni(z: str, hepsi: list):
    return lotm.zh_desen(z, [b for b in hepsi if z in b and b != z])


# ---------------------------------------------------------------- eslesme


def terimleri_bul(zh: str | None, en: str | None, terimler: list, zh_hepsi: list) -> list:
    """
    Kaynakta gecen sozluk/words.md terimleri, okuma sirasiyla.

    Cincesi girilmis terim YALNIZCA Cinceyle aranir (kesin; daha uzun bir
    sozluk teriminin icindeki gecis sayilmaz: 灵体 araninca 星灵体). Cincesi
    olmayan ya da Cince metin yoksa Ingilizceyle; harf duyarliligi
    toplu_denetle ile ayni kurala gore (yalniz 'Temel Kavramlar' duyarsiz).
    Ayni Turkce terim birden cok kayitta varsa (sozluk + words.md) sozluk
    kaydi kalir.
    """
    bulunan = {}
    for t in terimler:
        if not t.tr:
            continue
        konumlar, nasil = [], None
        zs = _zh_parcalari(t)
        if zh and zs:
            for z in zs:
                konumlar += [m.start() for m in _bilesik_deseni(z, zh_hepsi).finditer(zh)]
            nasil = "zh"
        elif en:
            bayrak = 0 if harf_duyarli_mi(t) else re.IGNORECASE
            for aday in t.arama_adaylari():
                if len(aday) < 4:
                    continue
                d = re.compile(r"(?<![\w-])" + re.escape(aday) + r"(?![\w-])", bayrak)
                konumlar += [m.start() for m in d.finditer(en)]
            nasil = "en"
        if not konumlar:
            continue
        anahtar = tr_kucult(t.tr)
        onceki = bulunan.get(anahtar)
        kelime = t.kategori.startswith(lotm.KELIME_KATEGORI)
        if onceki and (kelime or not onceki.terim.kategori.startswith(lotm.KELIME_KATEGORI)):
            continue  # sozluk kaydi words.md'ye tercih edilir
        bulunan[anahtar] = Eslesme(t, nasil, len(konumlar), min(konumlar))
    # Okuma sirasi: Cinceyle bulunanlar Cince konumuna gore, Ingilizceyle
    # bulunanlar onlardan sonra kendi sirasiyla (iki metnin konumlari
    # karsilastirilamaz).
    return sorted(bulunan.values(), key=lambda e: (e.nasil != "zh", e.ilk))


# Salahiyet BAGLAMI. Fihristin kendi gecis sinamasi: "Yalnizca tasarruf
# beyani gecis dogurur: 掌握X权柄 / 拥有X权柄 / 部分"X"权柄. Kavramin
# anilmasi gecis degildir." 力量 (guc), 天气 (hava), 海洋 (deniz) metinde
# cogunlukla siradan sozcuktur; bunlari "yerlesmis karsilik" diye vermek
# modeli duz "guc" yerine "Kudret" yazmaya iter. Salahiyet sayilmasi icin
# isaret terimin HEMEN ARDINDA olmali (X权柄, “X”权柄, X的象征) -- fihristin
# kendi sinamasi. Ilk surum ±12 karakterlik pencereye bakiyordu ve cumle
# sinirini asiyordu: "用尽了力量。祂掌握了死亡权柄" 力量'i de sayiyordu.
_SALAHIYET_ISARETI = re.compile(r"[”\"」』]?(?:的)?(?:权柄|象征|神国|领域)")


def salahiyetleri_bul(zh: str | None, kayitlar: list, zh_hepsi: list) -> tuple:
    """
    (salahiyet_olarak, siradan) -- her biri [(kayit, sayi, ilk)].

    salahiyet_olarak: en az bir gecisinin HEMEN ARDINDAN 权柄/象征/神国/领域
    geliyor (arada en cok kapanis tirnagi ve 的). siradan: Cincesi geciyor ama hicbir gecisinde
    salahiyet baglami yok; karsilik dayatilmaz, yalnizca adi anilir.
    """
    if not zh:
        return [], []
    baglamli, siradan = [], []
    for k in kayitlar:
        z = str(k["cince"]).strip()
        if len(z) < 2:
            continue  # tek karakter (神, 光...) her yerde gecer; sinama anlamsiz
        konumlar = [m.span() for m in _bilesik_deseni(z, zh_hepsi).finditer(zh)]
        if not konumlar:
            continue
        kayit = (k, len(konumlar), min(a for a, _b in konumlar))
        if any(_SALAHIYET_ISARETI.match(zh, b) for _a, b in konumlar):
            baglamli.append(kayit)
        else:
            siradan.append(kayit)
    return sorted(baglamli, key=lambda x: x[2]), sorted(siradan, key=lambda x: x[2])


def yayim_kullanimi(eslesmeler: list, tr_bolumler: list, haric: int) -> None:
    """Her eslesmenin .yayim alanini doldurur: bicimlerinin gectigi bolumler."""
    for e in eslesmeler:
        duyarli = harf_duyarli_mi(e.terim)
        desenler = [lotm.desen_kur(b, harf_duyarli=duyarli) for b in e.terim.tr_bicimleri()]
        e.yayim = sorted(
            b.no
            for b in tr_bolumler
            if b.no is not None and b.no != haric and any(d.search(b.metin) for d in desenler)
        )


# ------------------------------------------------------------ aday adlar


def bilinen_adlar(terimler: list, salahiyetler: list) -> set:
    """Ingilizce taramada 'bilinen' sayilan butun adlar, kucuk harfle."""
    adlar = set()
    for t in terimler:
        for a in t.arama_adaylari():
            adlar.add(a.lower())
        for a in (t.en, t.yol_en):
            if a:
                adlar.add(a.lower())
        for a in getattr(t, "kardesler_en", []) or []:
            adlar.add(a.lower())
    # Capa sozlugu kisi adlari (Klein, Dunn, Neil...): Turkcede ayni yazilir.
    for tr in _capa.sozluk_yukle().values():
        adlar.add(str(tr).lower())
    for s in salahiyetler:
        for parca in re.split(r"[/—–,;]", str(s.get("ingilizce_tuzak") or "")):
            if parca.strip():
                adlar.add(parca.strip().lower())
    return adlar


def aday_adlar(en: str, bilinen: set, en_kucuk: int = 2) -> list:
    """
    [(ad, sayi)] -- Ingilizce metinde buyuk harfle gecen, hicbir sozlukte
    olmayan ad obekleri. Cumle basindaki tek kelimeler elenir (orada her
    kelime buyuk harflidir); cok kelimeli obek ya da cumle ortasindaki tek
    kelime aday olur.
    """
    sayac = Counter()
    for m in _AD_OBEGI.finditer(en):
        ad = m.group()
        kelimeler = ad.split()
        once = en[max(0, m.start() - 3) : m.start()]
        cumle_basi = m.start() == 0 or bool(re.search(r"[.!?\"'“”:\n]\s*$", once))
        if len(kelimeler) == 1 and (cumle_basi or ad in _SIRADAN):
            continue
        # Bastaki siradan sozcuk ("The Hanged Man" -> "Hanged Man" degil,
        # ama "When Klein" -> "Klein")
        while kelimeler and kelimeler[0] in _SIRADAN and len(kelimeler) > 1:
            kelimeler = kelimeler[1:]
        ad = _IYELIK.sub("", " ".join(kelimeler))
        if not ad or ad in _SIRADAN or len(ad) < 3:
            continue
        kucuk = ad.lower()
        if kucuk in bilinen or any(kucuk == b or f" {kucuk} " in f" {b} " for b in bilinen if " " in b):
            continue
        if all(k.lower() in bilinen for k in ad.split()):
            continue  # "Klein Moretti": parcalarin hepsi biliniyor
        sayac[ad] += 1
    return [(a, n) for a, n in sayac.most_common() if n >= en_kucuk or " " in a]


def ilk_ingilizce_bolum(ad: str, en_bolumler: dict, simdiki: int):
    """Adin Ingilizce metinde gectigi ilk bolum (simdikiden once ya da o)."""
    d = re.compile(r"(?<![\w-])" + re.escape(ad) + r"(?![\w-])")
    for no in sorted(en_bolumler):
        if no > simdiki:
            break
        if d.search(en_bolumler[no].metin):
            return no
    return None


# ------------------------------------------------------------------ cikti


def _tek_satir(s, n=None) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).replace("<br><br>", " ¶ ").replace("<br>", " ").strip()
    return s if n is None or len(s) <= n else s[: n - 1] + "…"


def _yayim_ozeti(e: Eslesme) -> str:
    if not e.yayim:
        return "yayımlanmış metinde YOK — ilk kez, karar şimdi"
    return f"yayımlanmış {len(e.yayim)} bölümde (son: {e.yayim[-1]})"


def yaz(no, zh, en, eslesmeler, salahiyetler, adaylar, son_yayim, notlar=False, siradan=()) -> str:
    out = [f"# Terim Dökümü — Bölüm {no}", ""]
    kaynak = "Çince + İngilizce" if zh and en else ("yalnız Çince" if zh else "yalnız İngilizce")
    out.append(
        f"Kaynak: {kaynak}. Bu döküm mekanik bir aramadır: aşağıdaki karşılıkların hepsi "
        f"ZATEN KARARA BAĞLANMIŞTIR, yenisi uydurulmaz. Listede olmayan bir terim için "
        f"önce 'Sözlükte olmayan adaylar' bölümüne bakın."
    )
    if not zh:
        out.append("\n**Çince metin yok: bölüm kaynakla doğrulanmadı.**")
    out += ["", "## 1. Yerleşmiş terimler (okuma sırasıyla)", ""]
    if not eslesmeler:
        out.append("_yok_")
    for e in eslesmeler:
        t = e.terim
        kaynak_ad = "words.md" if t.kategori.startswith(lotm.KELIME_KATEGORI) else "sözlük"
        bas = f"- **{t.tr}**"
        if t.en:
            bas += f" ← {t.en}"
        bas += f"  ·  {t.yer} ({kaynak_ad}), bölümde ×{e.sayi}"
        if e.nasil == "en":
            bas += " (İngilizceden bulundu)"
        out.append(bas)
        if t.arama_adi:
            out.append(f"  - aynı karşılığın biçimleri: {', '.join(t.arama_adi)}")
        if t.eski_karsiliklar:
            out.append(f"  - KULLANILMAZ (eski karşılık): {', '.join(t.eski_karsiliklar)}")
        mudahale = (t.ham or {}).get("mudahale") if isinstance(t.ham, dict) else None
        if mudahale in ("ozgun", "degistirme", "birlestirme", "tamamlama"):
            out.append(
                f"  - çeviri katmanı ({mudahale}): kaynakta karşılığı olmayan bilinçli bir "
                f"tercih; kaynağa bakarak kapatılmaz"
            )
        out.append(f"  - {_yayim_ozeti(e)}")
        aciklama = (t.ham or {}).get("aciklama") if isinstance(t.ham, dict) else None
        if aciklama:
            out.append(f"  - açıklama: {_tek_satir(aciklama)}")
        if notlar and t.cevirmen_notu:
            out.append(f"  - çevirmen notu: {_tek_satir(t.cevirmen_notu)}")

    out += ["", "## 2. Salahiyetler", ""]
    if not salahiyetler:
        out.append("_salahiyet bağlamında geçen yok_")
    for k, n, _ilk in salahiyetler:
        out.append(f"- **{k['turkce']}**  ·  {k.get('tur', '')}, bölümde ×{n}")
        if k.get("ingilizce_tuzak"):
            out.append(f"  - İngilizce tuzağı: {_tek_satir(k['ingilizce_tuzak'])}")
        if k.get("not"):
            out.append(f"  - not: {_tek_satir(k['not'], 300)}")

    if siradan:
        out.append("")
        out.append(
            "Salahiyet adı olan ama bu bölümde SIRADAN anlamda geçen sözcükler (yanında "
            "权柄/象征/神国 yok); salahiyet karşılığı dayatılmaz: "
            + ", ".join(f"{k['turkce']} ×{n}" for k, n, _i in siradan)
        )

    out += ["", "## 3. Sözlükte olmayan adaylar", ""]
    out.append(
        "İngilizcede büyük harfle geçen, hiçbir sözlükte (sozluk.yml, words.md, salahiyetler, "
        "çapa adları) bulunmayan adlar. Kişi adları da burada görünür; karşılık gerektirenler "
        "A.2'ye girer."
    )
    out.append("")
    if not adaylar:
        out.append("_yok_")
    for ad, n, ilk in adaylar:
        if ilk is not None and ilk < no and ilk <= son_yayim:
            yer = (f"ilk: bölüm {ilk}, YAYIMLANMIŞ — karşılık orada: "
                   f"`ceviri_denetle.py \"{ad}\" --bolum {ilk}-{min(son_yayim, no - 1)}`")
        elif ilk is not None and ilk < no:
            yer = f"ilk: bölüm {ilk} (henüz yayımlanmadı)"
        else:
            yer = "ilk kez bu bölümde"
        out.append(f"- {ad} ×{n} — {yer}")

    out += [
        "",
        "## Tarama makbuzu",
        "",
        f"{len(eslesmeler)} yerleşmiş terim "
        f"({sum(1 for e in eslesmeler if e.nasil == 'zh')} Çinceden, "
        f"{sum(1 for e in eslesmeler if e.nasil == 'en')} İngilizceden), "
        f"{len(salahiyetler)} salahiyet (+{len(siradan)} sıradan anlamda), "
        f"{len(adaylar)} sözlükte olmayan aday; "
        f"{sum(1 for e in eslesmeler if not e.yayim)} terim yayımlanmış metinde ilk kez geçecek.",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("bolum", type=int)
    ap.add_argument("--cikti", type=Path, default=None, help="Markdown dosyasi (varsayilan: ekran)")
    ap.add_argument("--notlar", action="store_true", help="cevirmen notlarini da ekle")
    a = ap.parse_args()

    zh, en = kaynaklar(a.bolum)
    if not zh and not en:
        sys.exit(f"HATA: {a.bolum}. bölüm ne Çince ne İngilizce kaynakta bulundu")

    sozluk = lotm.sozluk_yukle(kelimeler=True)
    salahiyetler = lotm.salahiyetler_yukle()
    zh_hepsi = sorted(
        {z for t in sozluk.terimler for z in _zh_parcalari(t)}
        | {str(k["cince"]) for k in salahiyetler},
        key=len,
        reverse=True,
    )

    eslesmeler = terimleri_bul(zh, en, sozluk.terimler, zh_hepsi)
    salahiyet_bulunan, salahiyet_siradan = salahiyetleri_bul(zh, salahiyetler, zh_hepsi)

    try:
        tr_bolumler = lotm.bolumler_tr()
    except FileNotFoundError:
        tr_bolumler = []
    son_yayim = max((b.no for b in tr_bolumler if b.no is not None), default=0)
    yayim_kullanimi(eslesmeler, tr_bolumler, haric=a.bolum)

    adaylar = []
    if en:
        en_bolumler = lotm.bolum_sozlugu(lotm.bolumler_en())
        bilinen = bilinen_adlar(sozluk.terimler, salahiyetler)
        adaylar = [
            (ad, n, ilk_ingilizce_bolum(ad, en_bolumler, a.bolum))
            for ad, n in aday_adlar(en, bilinen)
        ]

    metin = yaz(
        a.bolum, zh, en, eslesmeler, salahiyet_bulunan, adaylar, son_yayim, a.notlar,
        siradan=salahiyet_siradan,
    )
    if a.cikti:
        lotm.atomik_yaz(a.cikti, metin)
        print(f"yazıldı: {a.cikti}", file=sys.stderr)
    else:
        print(metin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
