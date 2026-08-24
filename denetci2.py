#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
denetci2.py -- Turkce bolumleri sozluge karsi denetler (ayarlanmis surum).

v1'de 146 bulgu vardi, bunlarin ~5'i gercekti. Sebep: Turkce karsiliklar
gunluk Turkce kelimelerden secilmis (Haz, Yol, Ay, Sanli, Avci...) ve duz
eslesme "Mertebe adi" ile "siradan kelime" ayrimini yapamiyor.

Duzeltmeler:
  1. HARF DUYARLI. Mertebe adlari ozel isim, cakismalar kucuk harfli:
     Yol/yolu, Haz/hazine, Maraz/marazi, San/sansli, Askin/"yili askin".
  2. GERCEK TURKCE EKLERI. v1 "\\w{0,12}" kabul ediyordu; bu yuzden
     Haz -> Haziran, Bard -> bardak esleiyordu. Artik yalnizca gercek
     isim cekim ekleri kabul ediliyor. (Desen artik lotm.desen_kur'da.)
  3. IPUCU SARTI. Tek kelimelik terimler ancak yakininda Mertebe / Yol /
     iksir / formul gibi bir isaret ya da ayni yoldan cok kelimeli bir
     kardes ad varsa "yuksek" sayilir.
  4. OZEL ISIMLER SIZINTI TARAMASINDAN CIKARILDI. "Audrey Hall" bir terim
     degil, kisi adi; Turkcede de oyle kalmali.

COZULEMEYEN: es adli gonderge. "Kara Imparator" 5. bolumde Solomon
Imparatorlugu'nun hukumdari anlamina gelir, Mertebe 0 anlamina degil.
Metin ayni, gonderge farkli. Bu ayrimi regex yapamaz; arac adaylari
daraltir, karari insan verir. Rapor bu yuzden "hata" degil "aday" der.

Sozluk yukleme, bolum okuma ve Turkce ek deseni artik lotm.py'de.

Kullanim:
    python3 denetci2.py --sozluk sozluk.yml --bolumler ./_chapters
    python3 denetci2.py --sozluk sozluk.yml --bolumler ./_chapters --hepsi
"""

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field

import lotm

# Tek kelimelik terimleri "yuksek guven" yapan yakin isaretler
IPUCU_RE = re.compile(
    r"\bMertebe|\bYol[una]|\biksir|\bformül|\bAşkın|\bSıra\b|\bpotion", re.IGNORECASE
)

CUMLE_BASI = re.compile(r'[.!?:;"\u201c\u201d\u2014\-]\s+$')

# Sistem istemi ve bolum acilis sablonu, duzeltme sirasinda elle silinmesi
# gereken isaretler uretir. Onda dokuzu yakalanir; yakalanmayan biri canli
# sayfada gorunur. Ucuz kontrol, pahali hata.
ARTIK_ISARETLER = [
    (re.compile(r"\[BELİRSİZ\]"), "çeviri belirsizlik etiketi (§7)"),
    (re.compile(r"\[ÖNERİ[:\]]"), "isteğe bağlı detay önerisi (§8)"),
    (re.compile(r"\[DURUM NOTU\]"), "durum notu bloğu (§9)"),
    (re.compile(r"Biten kayıt\s*:"), "durum notu alanı"),
    (re.compile(r"Son duygusal vurgu\s*:"), "durum notu alanı"),
    (re.compile(r"\[END OF OUTPUT\]"), "şablon sonu işareti"),
    (re.compile(r"Bölüm Açılış Şablonu"), "açılış şablonu başlığı"),
    (re.compile(r"##\s*[ABC]\.\s*(AKTİF|BÖLÜME)"), "açılış şablonu bölüm başlığı"),
    (
        re.compile(r"\[(Term|Translation|Karakter Adı)\s*\d*\]"),
        "doldurulmamış şablon alanı",
    ),
    (
        re.compile(r"\[Extract/adapt|\[Determine from|\[Tek paragraf"),
        "şablon yönergesi",
    ),
    (re.compile(r"^\s*\|\s*İngilizce\s*\|", re.M), "aktif terimler tablosu"),
]

# Kisi adi kalibi: iki bas harfi buyuk kelime, aralarinda baglac yok
KISI_ADI = re.compile(r"^[A-ZÇĞİÖŞÜ][\w'-]+ [A-ZÇĞİÖŞÜ][\w'-]+$")

# Bu esikteki bolum_siniri degerleri gercek bir kapi bildirmez; ya "seri
# bitmeden acilmaz" (Mertebe 0 adlari) ya da "bolum henuz tespit edilmedi"
# demektir. Ikisi de kapi denetimine girmemeli: bu adlarin cogu gunluk
# Turkce kelime (Ana, Ay, Kapi, Olum, Karanlik) ve her bolumde yanlis
# pozitif uretirler. Deger lotm.py'den gelir; eskiden burada 1409 sabiti
# vardi ve iki dosya birbirinden kayabiliyordu.
SON_BOLUM = lotm.SON_BOLUM

YUKSEK, DUSUK = "yuksek", "dusuk"


@dataclass
class Kayit:
    """Bir lotm.Terim + denetim icin derlenmis desenler."""
    terim: lotm.Terim
    desen: object = None
    en_desen: object = None
    eski_desen: list = field(default_factory=list)
    kardesler: list = field(default_factory=list)

    # denetle()/rapor() bu adlarla okur
    @property
    def tr(self):
        return self.terim.tr

    @property
    def en(self):
        return self.terim.en

    @property
    def kapi(self):
        return self.terim.bolum_siniri

    @property
    def ilk_gecis(self):
        return self.terim.ilk_gecis

    @property
    def yer(self):
        return self.terim.yer

    @property
    def tek_kelime(self):
        return self.terim.tek_kelime


def kayitlari_kur(sozluk) -> list:
    """lotm.Terim kayitlarini denetim kayitlarina cevirir."""
    kayitlar = []
    for t in sozluk.terimler:
        if not t.tr:
            continue
        en = t.en
        kisi = bool(en and KISI_ADI.match(en))
        kayitlar.append(
            Kayit(
                terim=t,
                desen=lotm.desen_kur(t.tr),
                # sizinti taramasi: ozel isimler ve Tarot kartlari haric
                en_desen=(
                    re.compile(r"(?<![\w])" + re.escape(en) + r"(?![\w])")
                    if en and len(en) >= 5 and not kisi
                    and t.kategori != "Tarot Kulübü"
                    else None
                ),
                eski_desen=[(e, lotm.desen_kur(e)) for e in t.eski_karsiliklar],
                # tek kelimelik kardes ad ipucu sayilmaz: "Avci" yakininda
                # "Avci" gormek hicbir sey soylemez.
                kardesler=[k for k in t.kardesler_tr if len(k.split()) > 1],
            )
        )
    return kayitlar


def guven_ver(kayit, metin, konum, cumle_ici_yuksek=False):
    """
    Tek kelimelik terimler yakin isaret istemeden yuksek sayilmaz.

    CUMLE_BASI hakkinda: bu dal eskiden iki kolunda da DUSUK donuyordu,
    yani olcum yapiliyor ama sonuca yansimiyordu. Davranis korunuyor
    (varsayilan kapali), cunku 146 -> 5 bastirma turu tam da bu yolla
    yapilmis olabilir.

    --cumle-ici-yuksek ile acilir. Gerekcesi: cumle ORTASINDA buyuk
    harfle gecen tek kelimelik bir terim ("... bir Haz getirirdi")
    neredeyse kesin Mertebe adidir; cumle BASINDAKI buyuk harf ise
    ayirt edici degildir, "Hazine" gibi siradan kelimeler de oyle
    baslar. Acmadan once --hepsi ile ne kadar bulgu ekledigine bakin.
    """
    if not kayit.tek_kelime:
        return YUKSEK
    bas, son = max(0, konum - 200), min(len(metin), konum + 200)
    pencere = metin[bas:son]
    if IPUCU_RE.search(pencere):
        return YUKSEK
    for kardes in kayit.kardesler:
        if kardes in pencere:
            return YUKSEK
    onceki = metin[max(0, konum - 40):konum]
    cumle_basinda = bool(CUMLE_BASI.search(onceki)) or konum == 0
    if cumle_ici_yuksek and not cumle_basinda:
        return YUKSEK
    return DUSUK


def baglam(metin, a, b, g=75):
    return re.sub(r"\s+", " ", metin[max(0, a - g):min(len(metin), b + g)]).strip()


def artik_tara(bolumler):
    """Yayimlanmis bolumlerde kalmis istem/sablon isaretleri."""
    bulgular = []
    for b in bolumler:
        for satir_no, satir in enumerate(b.metin.split("\n"), 1):
            for desen, aciklama in ARTIK_ISARETLER:
                m = desen.search(satir)
                if m:
                    bulgular.append(
                        (b.kaynak, satir_no, aciklama,
                         re.sub(r"\s+", " ", satir).strip()[:160])
                    )
                    break
    return bulgular


def denetle(kayitlar, bolumler, cumle_ici_yuksek=False):
    sizinti, eskimis, kapi, sadik = [], [], [], []
    envanter = defaultdict(list)

    # En uzun terim once denenir ve kapsadigi aralik isaretlenir. Boylece
    # "Gizem Avcısı" araligi tuketir ve "Avcı" o konumu goremez. Ayni sorun
    # Ana/Toprak Ana, Güneş/Ebedi Yanan Güneş, Ölüm/Ölüm Sefiri, Ay/Kadim Ay
    # ciftlerinde de var: kisa ad uzun adin icinde sayiliyordu.
    uzun_once = sorted(kayitlar, key=lambda k: -len(k.tr))

    for b in bolumler:
        no, metin, dosya = b.no, b.metin, b.kaynak
        kapali = []  # (bas, son) -- uzun bir terimin tuketip birakmadigi araliklar

        for k in uzun_once:
            m = None
            # Uzun terimin TUM gecisleri isaretlenmeli. Yalnizca ilki
            # isaretlenirse "Gizem Avcısı" ikinci kez gectiginde o konum
            # bos kalir ve "Avcı" oraya yerlesir.
            for aday in k.desen.finditer(metin):
                if any(aday.start() < son and aday.end() > bas
                       for bas, son in kapali):
                    continue
                kapali.append((aday.start(), aday.end()))
                if m is None:
                    m = aday
            if m:
                g = guven_ver(k, metin, m.start(), cumle_ici_yuksek)
                envanter[k.tr].append(no)
                esik = k.kapi or 0
                if no and 0 < esik < SON_BOLUM and no < esik:
                    ctx = baglam(metin, m.start(), m.end())
                    # Kapi ile ilk gecis arasindaki aralik: ad Ingilizce
                    # metinde GECIYOR ama henuz ACIKLANMAMIS. Orada Turkce
                    # metnin adi kullanmasi kaynaga SADAKATTIR, spoiler
                    # degil. Bu ayrim olmadan boyle terimler (kapisi
                    # aciklama bolumune elle konmus olanlar) her
                    # calistirmada sonsuza dek aday olarak cikiyordu.
                    if k.ilk_gecis and no >= k.ilk_gecis:
                        sadik.append((no, dosya, k, ctx))
                    else:
                        kapi.append((g, no, dosya, k, ctx))

        for k in kayitlar:
            if k.en_desen:
                me = k.en_desen.search(metin)
                if me:
                    sizinti.append((no, dosya, k,
                                    baglam(metin, me.start(), me.end())))

            for eski_ad, desen in k.eski_desen:
                mo = desen.search(metin)
                if mo:
                    eskimis.append((no, dosya, k, eski_ad,
                                    baglam(metin, mo.start(), mo.end())))

    return sizinti, eskimis, kapi, sadik, envanter


def rapor(artiklar, sizinti, eskimis, kapi, sadik, envanter, kayitlar, hepsi,
          envanter_ister):
    print("\n=== 0. ARTIK ISTEM/SABLON ISARETLERI ===")
    print("    Bunlar okuyucuya GORUNUR. Once bunlar temizlenmeli.")
    if not artiklar:
        print("  temiz")
    for dosya, satir_no, aciklama, ctx in artiklar:
        print(f"  [{dosya}:{satir_no}] {aciklama}\n      {ctx}")

    print("\n=== 1. ESKIMIS KARSILIKLAR ===")
    print("  yok" if not eskimis else "")
    for no, dosya, k, eski_ad, ctx in eskimis:
        print(f"  [{dosya}] '{eski_ad}' -> '{k.tr}'\n      {ctx}")

    print("\n=== 2. CEVRILMEDEN KALMIS INGILIZCE TERIMLER ===")
    print("  yok" if not sizinti else "")
    for no, dosya, k, ctx in sizinti:
        print(f"  [{dosya}] '{k.en}' -> beklenen '{k.tr}' ({k.yer})\n      {ctx}")

    yuksek = [x for x in kapi if x[0] == YUKSEK]
    dusuk = [x for x in kapi if x[0] == DUSUK]

    print("\n=== 3. KAPI ADAYLARI (yuksek guven) ===")
    print("    Bunlar hata degil, ADAYDIR. Metin ayni olsa da gonderge farkli")
    print("    olabilir: 'Kara Imparator' hem Mertebe 0 hem tarihi bir unvandir.")
    print("  yok" if not yuksek else "")
    for g, no, dosya, k, ctx in sorted(yuksek, key=lambda x: x[1] or 0):
        print(f"  [{dosya}] '{k.tr}' ({k.yer}) kapi={k.kapi} kullanim={no}\n      {ctx}")

    print(f"\n=== 3a. KAYNAKTA DA GECIYOR ({len(sadik)}) -- sorun degil ===")
    print("    Kapidan once ama ILK GECISTEN sonra kullanilmis. Ingilizce")
    print("    metin de adi orada aniyor; ceviri sadik. Kapi 'aciklandigi")
    print("    yer' oldugu icin bu aralik normaldir.")
    if not sadik:
        print("  yok")
    elif not hepsi:
        terimler = sorted({k.tr for _, _, k, _ in sadik})
        print(f"  {len(terimler)} terim: {', '.join(terimler[:12])}"
              f"{' ...' if len(terimler) > 12 else ''}  (--hepsi ile ayrinti)")
    else:
        for no, dosya, k, ctx in sorted(sadik, key=lambda x: x[0] or 0):
            print(f"  [{dosya}] '{k.tr}' kapi={k.kapi} "
                  f"ilk_gecis={k.ilk_gecis} kullanim={no}\n      {ctx}")

    if hepsi:
        print("\n=== 3b. KAPI ADAYLARI (dusuk guven -- muhtemelen siradan kelime) ===")
        for g, no, dosya, k, ctx in sorted(dusuk, key=lambda x: x[1] or 0):
            print(f"  [{dosya}] '{k.tr}' ({k.yer}) kapi={k.kapi} "
                  f"kullanim={no}\n      {ctx}")

    if envanter_ister:
        print("\n=== 4. ENVANTER (yayimlanmis yuzey) ===")
        for terim, b in sorted(envanter.items(), key=lambda kv: -len(kv[1])):
            bl = sorted(set(x for x in b if x is not None))
            print(f"    {terim}: {len(b)} kez, bolum {bl}")
        hic = [k.tr for k in kayitlar if k.tr not in envanter]
        print(f"\n  {len(hic)} terim henuz hic kullanilmamis -- "
              f"serbestce degistirilebilir.")

    print("\n--- OZET ---")
    print(f"  ARTIK ISARET      : {len(artiklar)}   <- varsa ilk is bu")
    print(f"  eskimis           : {len(eskimis)}")
    print(f"  sizinti           : {len(sizinti)}")
    print(f"  kapi (yuksek)     : {len(yuksek)}   <- bakilacaklar")
    print(f"  kaynakta da var   : {len(sadik)}   (sorun degil)")
    print(f"  kapi (dusuk)      : {len(dusuk)}   (--hepsi ile gorulur)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sozluk", default=None)
    ap.add_argument("--bolumler", default=None)
    ap.add_argument("--hepsi", action="store_true")
    ap.add_argument("--envanter", action="store_true")
    ap.add_argument("--cumle-ici-yuksek", action="store_true",
                    dest="cumle_ici",
                    help="cumle ortasindaki tek kelimelik terimleri yuksek "
                         "guven say (bkz. guven_ver)")
    a = ap.parse_args()

    try:
        sozluk = lotm.sozluk_yukle(a.sozluk)
        bolumler = lotm.bolumler_tr(a.bolumler)
    except (FileNotFoundError, OSError) as e:
        sys.exit(f"HATA: {e}")

    kayitlar = kayitlari_kur(sozluk)
    print(f"{len(kayitlar)} terim, {len(bolumler)} bolum.", file=sys.stderr)

    artiklar = artik_tara(bolumler)
    s, e, kp, sd, env = denetle(kayitlar, bolumler, a.cumle_ici)
    rapor(artiklar, s, e, kp, sd, env, kayitlar, a.hepsi, a.envanter)


if __name__ == "__main__":
    main()
