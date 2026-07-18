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
     Haz -> Haziran, Bard -> bardak eslesiyordu. Artik yalnizca gercek
     isim cekim ekleri kabul ediliyor.
  3. IPUCU SARTI. Tek kelimelik terimler ancak yakininda Mertebe / Yol /
     iksir / formul gibi bir isaret ya da ayni yoldan cok kelimeli bir
     kardes ad varsa "yuksek" sayilir.
  4. OZEL ISIMLER SIZINTI TARAMASINDAN CIKARILDI. "Audrey Hall" bir terim
     degil, kisi adi; Turkcede de oyle kalmali.

COZULEMEYEN: es adli gonderge. "Kara Imparator" 5. bolumde Solomon
Imparatorlugu'nun hukumdari anlamina gelir, Mertebe 0 anlamina degil.
Metin ayni, gonderge farkli. Bu ayrimi regex yapamaz; arac adaylari
daraltir, karari insan verir. Rapor bu yuzden "hata" degil "aday" der.

Kullanim:
    python3 denetci2.py --sozluk /_data/sozluk.yml --bolumler ./_chapters
    python3 denetci2.py --sozluk sozluk.yml --bolumler ./_chapters --hepsi
"""

import argparse
import os
import re
import sys
from collections import defaultdict

try:
    import yaml
except ImportError:
    print("HATA: PyYAML gerekli.  pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------- ekler

# Turkce isim cekim ekleri. Uzunlugu uzun olan once denenmeli.
COGUL = r"(?:ler|lar)"
IYELIK = (
    r"(?:imiz|ımız|umuz|ümüz|iniz|ınız|unuz|ünüz|leri|ları"
    r"|siz|sız|suz|süz|si|sı|su|sü|im|ım|um|üm|in|ın|un|ün|i|ı|u|ü|m|n)"
)
HAL = (
    r"(?:nden|ndan|nde|nda|nin|nın|nun|nün|den|dan|ten|tan|de|da|te|ta"
    r"|yle|yla|ile|le|la|ni|nı|nu|nü|ne|na|yi|yı|yu|yü|ye|ya|i|ı|u|ü|e|a)"
)

# Kesme hem govdeden hemen sonra (Kâhin'in) hem iyelikten sonra
# (Diyarı'nı) gelebilir. Sondaki (?![\w]) sart: eksiz de olsa eslesme
# kelime sonunda bitmeli. Yoksa Haz -> Haz|iran, Zanaatkâr -> Zanaatkâr|lık
# gibi kirpik eslesmeler gecerli sayiliyor.
KESME = r"(?:['\u2019])?"
EK = KESME + COGUL + r"?" + IYELIK + r"?" + KESME + HAL + r"?" + r"(?![\w])"

# Son sert unsuz yumusamasi
YUMUSAMA = {"k": "[kğ]", "p": "[pb]", "t": "[td]", "ç": "[çc]"}

# Tek kelimelik terimleri "yuksek guven" yapan yakin isaretler
IPUCU_RE = re.compile(
    r"\bMertebe|\bYol[una]|\biksir|\bformül|\bAşkın|\bSıra\b|\bpotion", re.IGNORECASE
)

CUMLE_BASI = re.compile(r'[.!?:;"\u201c\u201d\u2014\-]\s+$')
FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)

# Kisi adi kalibi: iki bas harfi buyuk kelime, aralarinda baglac yok
KISI_ADI = re.compile(r"^[A-ZÇĞİÖŞÜ][\w'-]+ [A-ZÇĞİÖŞÜ][\w'-]+$")

YUKSEK, DUSUK = "yuksek", "dusuk"


def desen_kur(terim, harf_duyarli=True):
    parcalar = []
    kelimeler = terim.split()
    for i, kelime in enumerate(kelimeler):
        govde = re.escape(kelime)
        if kelime and kelime[-1] in YUMUSAMA:
            govde = re.escape(kelime[:-1]) + YUMUSAMA[kelime[-1]]
        parcalar.append(govde + (EK if i == len(kelimeler) - 1 else r"(?![\w])"))
    kalip = r"(?<![\w'])" + r"\s+".join(parcalar)
    return re.compile(kalip) if harf_duyarli else re.compile(kalip, re.IGNORECASE)


def parantezsiz(m):
    return re.sub(r"\s*\([^)]*\)", "", str(m or "")).strip()


def ingilizce_al(m):
    g = re.search(r"\(([^)]*)\)", str(m or ""))
    return g.group(1).strip() if g else None


def sozluk_yukle(yol):
    with open(yol, "r", encoding="utf-8") as f:
        veri = yaml.safe_load(f)

    kayitlar = []
    for girdi in veri:
        mert = girdi.get("mertebeler")
        if mert:
            kardesler = [parantezsiz(m.get("isim")) for m in mert]
            for m in mert:
                tr = parantezsiz(m.get("isim"))
                if not tr:
                    continue
                kayitlar.append(
                    {
                        "tr": tr,
                        "en": ingilizce_al(m.get("isim")),
                        "kapi": m.get("bolum_siniri"),
                        "yer": f"{girdi['terim']} S{m.get('seviye')}",
                        "kategori": girdi.get("kategori", ""),
                        "kardesler": [
                            k for k in kardesler if k != tr and len(k.split()) > 1
                        ],
                        "eski": m.get("eski_karsiliklar") or [],
                    }
                )
        else:
            tr = parantezsiz(girdi.get("terim"))
            kayitlar.append(
                {
                    "tr": tr,
                    "en": parantezsiz(girdi.get("ingilizce")),
                    "kapi": girdi.get("bolum_siniri"),
                    "yer": girdi.get("kategori", ""),
                    "kategori": girdi.get("kategori", ""),
                    "kardesler": [],
                    "eski": girdi.get("eski_karsiliklar") or [],
                }
            )

    for k in kayitlar:
        k["desen"] = desen_kur(k["tr"])
        k["tek_kelime"] = len(k["tr"].split()) == 1
        # sizinti taramasi: ozel isimler ve Tarot kartlari haric
        en = k["en"]
        kisi = bool(en and KISI_ADI.match(en))
        k["en_desen"] = (
            re.compile(r"(?<![\w])" + re.escape(en) + r"(?![\w])")
            if en and len(en) >= 5 and not kisi and k["kategori"] != "Tarot Kulübü"
            else None
        )
        k["eski_desen"] = [(e, desen_kur(e)) for e in k["eski"]]
    return kayitlar


def bolum_oku(klasor):
    if not os.path.isdir(klasor):
        print(f"HATA: '{klasor}' yok.", file=sys.stderr)
        sys.exit(1)
    cikti = []
    for ad in sorted(os.listdir(klasor)):
        if not ad.lower().endswith((".md", ".markdown", ".html")):
            continue
        s = re.findall(r"\d+", ad)
        no = int(s[0]) if s else None
        ham = open(os.path.join(klasor, ad), encoding="utf-8").read()
        fm = FRONT_MATTER.match(ham)
        govde = ham[fm.end() :] if fm else ham
        if fm:
            try:
                bilgi = yaml.safe_load(fm.group(0).strip("-\n")) or {}
                for a in ("bolum", "chapter", "bolum_no", "number"):
                    if a in bilgi and str(bilgi[a]).isdigit():
                        no = int(bilgi[a])
                        break
            except yaml.YAMLError:
                pass
        cikti.append((no, govde, ad))
    return cikti


def guven_ver(kayit, metin, konum):
    """Tek kelimelik terimler yakin isaret istemeden yuksek sayilmaz."""
    if not kayit["tek_kelime"]:
        return YUKSEK
    bas, son = max(0, konum - 200), min(len(metin), konum + 200)
    pencere = metin[bas:son]
    if IPUCU_RE.search(pencere):
        return YUKSEK
    for kardes in kayit["kardesler"]:
        if kardes in pencere:
            return YUKSEK
    onceki = metin[max(0, konum - 40) : konum]
    if CUMLE_BASI.search(onceki) or konum == 0:
        return DUSUK
    return DUSUK


def baglam(metin, a, b, g=75):
    return re.sub(r"\s+", " ", metin[max(0, a - g) : min(len(metin), b + g)]).strip()


def denetle(kayitlar, bolumler):
    sizinti, eskimis, kapi = [], [], []
    envanter = defaultdict(list)

    # En uzun terim once denenir ve kapsadigi aralik isaretlenir. Boylece
    # "Gizem Avcısı" araligi tuketir ve "Avcı" o konumu goremez. Ayni sorun
    # Ana/Toprak Ana, Güneş/Ebedi Yanan Güneş, Ölüm/Ölüm Sefiri, Ay/Kadim Ay
    # ciftlerinde de var: kisa ad uzun adin icinde sayiliyordu.
    uzun_once = sorted(kayitlar, key=lambda k: -len(k["tr"]))

    for no, metin, dosya in bolumler:
        kapali = []  # (bas, son) -- uzun bir terimin tuketip birakmadigi araliklar

        for k in uzun_once:
            m = None
            # Uzun terimin TUM gecisleri isaretlenmeli. Yalnizca ilki
            # isaretlenirse "Gizem Avcısı" ikinci kez gectiginde o konum
            # bos kalir ve "Avcı" oraya yerlesir.
            for aday in k["desen"].finditer(metin):
                if any(aday.start() < son and aday.end() > bas for bas, son in kapali):
                    continue
                kapali.append((aday.start(), aday.end()))
                if m is None:
                    m = aday
            if m:
                g = guven_ver(k, metin, m.start())
                envanter[k["tr"]].append(no)
                if k["kapi"] and no and no < k["kapi"] and k["kapi"] != 9999:
                    kapi.append((g, no, dosya, k, baglam(metin, m.start(), m.end())))

        for k in kayitlar:
            if k["en_desen"]:
                me = k["en_desen"].search(metin)
                if me:
                    sizinti.append((no, dosya, k, baglam(metin, me.start(), me.end())))

            for eski_ad, desen in k["eski_desen"]:
                mo = desen.search(metin)
                if mo:
                    eskimis.append(
                        (no, dosya, k, eski_ad, baglam(metin, mo.start(), mo.end()))
                    )

    return sizinti, eskimis, kapi, envanter


def rapor(sizinti, eskimis, kapi, envanter, kayitlar, hepsi, envanter_ister):
    print("\n=== 1. ESKIMIS KARSILIKLAR ===")
    print("  yok" if not eskimis else "")
    for no, dosya, k, eski_ad, ctx in eskimis:
        print(f"  [{dosya}] '{eski_ad}' -> '{k['tr']}'\n      {ctx}")

    print("\n=== 2. CEVRILMEDEN KALMIS INGILIZCE TERIMLER ===")
    print("  yok" if not sizinti else "")
    for no, dosya, k, ctx in sizinti:
        print(
            f"  [{dosya}] '{k['en']}' -> beklenen '{k['tr']}' ({k['yer']})\n      {ctx}"
        )

    yuksek = [x for x in kapi if x[0] == YUKSEK]
    dusuk = [x for x in kapi if x[0] == DUSUK]

    print("\n=== 3. KAPI ADAYLARI (yuksek guven) ===")
    print("    Bunlar hata degil, ADAYDIR. Metin ayni olsa da gonderge farkli")
    print("    olabilir: 'Kara Imparator' hem Mertebe 0 hem tarihi bir unvandir.")
    print("  yok" if not yuksek else "")
    for g, no, dosya, k, ctx in sorted(yuksek, key=lambda x: x[1] or 0):
        print(
            f"  [{dosya}] '{k['tr']}' ({k['yer']}) kapi={k['kapi']} kullanim={no}\n      {ctx}"
        )

    if hepsi:
        print("\n=== 3b. KAPI ADAYLARI (dusuk guven -- muhtemelen siradan kelime) ===")
        for g, no, dosya, k, ctx in sorted(dusuk, key=lambda x: x[1] or 0):
            print(
                f"  [{dosya}] '{k['tr']}' ({k['yer']}) kapi={k['kapi']} kullanim={no}\n      {ctx}"
            )

    if envanter_ister:
        print("\n=== 4. ENVANTER (yayimlanmis yuzey) ===")
        for terim, b in sorted(envanter.items(), key=lambda kv: -len(kv[1])):
            bl = sorted(set(x for x in b if x is not None))
            print(f"    {terim}: {len(b)} kez, bolum {bl}")
        hic = [k["tr"] for k in kayitlar if k["tr"] not in envanter]
        print(
            f"\n  {len(hic)} terim henuz hic kullanilmamis -- serbestce degistirilebilir."
        )

    print("\n--- OZET ---")
    print(f"  eskimis           : {len(eskimis)}")
    print(f"  sizinti           : {len(sizinti)}")
    print(f"  kapi (yuksek)     : {len(yuksek)}   <- bakilacaklar")
    print(f"  kapi (dusuk)      : {len(dusuk)}   (--hepsi ile gorulur)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sozluk", default="sozluk.yml")
    ap.add_argument("--bolumler", default="./_chapters")
    ap.add_argument("--hepsi", action="store_true")
    ap.add_argument("--envanter", action="store_true")
    a = ap.parse_args()

    kayitlar = sozluk_yukle(a.sozluk)
    bolumler = bolum_oku(a.bolumler)
    print(f"{len(kayitlar)} terim, {len(bolumler)} bolum.", file=sys.stderr)

    s, e, kp, env = denetle(kayitlar, bolumler)
    rapor(s, e, kp, env, kayitlar, a.hepsi, a.envanter)


if __name__ == "__main__":
    main()
