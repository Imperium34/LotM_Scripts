#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tarayici2.py -- "Bu ad metinde geciyor mu?" sorusunu yanitlar.

v1'e gore duzeltmeler:
  1. Parantez ve slash artik TUM girdilerden temizleniyor (v1 sadece
     mertebeler icin yapiyordu; "Blasphemer Amon (King of Angels)" gibi
     stringler oldugu gibi aranip garantili sifir donuyordu).
  2. Yazim varyantlari uretiliyor: "Grave Digger" -> "Gravedigger",
     "Wind-Blessed" -> "Wind Blessed" vb.
  3. Iki asamali arama. Once harf duyarli (ozel isimler icin dogru),
     bulunamayanlar icin harf duyarsiz ikinci tur. Boolean soru icin
     yanlis pozitif, yanlis negatiften ucuzdur: az sayida sonucu gozle
     dogrulamak, gercek gecisi kacirmaktan iyidir.
  4. Ipucu listesi daraltildi. v1'de "Beyonder", "ritual", "angel",
     "advance" vardi; bu romanda bu kelimeler her yerde geciyor, yani
     "Death" gibi cins isimler icin hicbir ayirt edicilik saglamiyorlardi.
  5. Cins isim tespiti: terim metinde kucuk harfle de geciyorsa, bulunan
     bolum numarasi guvenilmez olarak isaretlenir.
  6. sozluk.yml'de istege bagli 'arama_adi' alani destekleniyor. Sozlukteki
     etiket metindeki ifadeden farkliysa gercek ifadeyi oraya yazin:
         arama_adi: ["Amon"]
         arama_adi: ["Spirit World"]

Kullanim:
    python3 tarayici2.py --sozluk sozluk.yml --kaynak ./LotM_Volumes \
        --rapor rapor.tsv --yama yama.yml
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


PENCERE = 250

# Daraltilmis ipucu listesi. Bu romanda gecen her seyde bulunan kelimeler
# (Beyonder, ritual, angel, advance) bilerek cikarildi; ayirt etmiyorlardi.
IPUCLARI = [
    r"\bSequence\s+\d\b",
    r"\bpotion\s+formula\b",
    r"\bformula\b",
    r"\bPathway\b",
    r"\bdemigod\b",
    r"\bActing Method\b",
]
IPUCU_RE = re.compile("|".join(IPUCLARI))

CUMLE_BASI = re.compile(r'[.!?"\u201c\u201d]\s+$')

BOLUM_BASLIGI = re.compile(
    r"^(?:#+\s*)?(?:Chapter|Bolum|B\u00f6l\u00fcm)\s*[:.\-]?\s*(\d+)",
    re.IGNORECASE,
)

YUKSEK, ORTA, ESNEK, YOK = "yuksek", "orta", "esnek", "yok"
SIRA = {YUKSEK: 3, ORTA: 2, ESNEK: 1, YOK: 0}


# ------------------------------------------------------------- terim uretimi


def etiket_temizle(ham):
    """
    Sozluk etiketini aranabilir stringlere cevirir.
    'Blasphemer Amon (King of Angels)' -> ['Blasphemer Amon', 'King of Angels']
    'Historical Void / Fog of History' -> ['Historical Void', 'Fog of History']
    'Pugilist / Gladiator'             -> ['Pugilist', 'Gladiator']
    """
    if not ham:
        return []
    # Parantez DISI kisim birincil ad; parantez ici yalnizca ek adaydir.
    disi = re.sub(r"\([^)]*\)", " ", ham)
    parcalar = [disi]
    for ic in re.findall(r"\(([^)]*)\)", ham):
        parcalar.append(ic)

    sonuc = []
    for p in parcalar:
        for alt in p.split("/"):
            alt = re.sub(r"\s+", " ", alt).strip(" .,;:-")
            if alt:
                sonuc.append(alt)
    return sonuc


def varyantlar(terim):
    """Yazim varyantlari: tire/bosluk/bitisik."""
    v = {terim}
    if "-" in terim:
        v.add(terim.replace("-", " "))
        v.add(terim.replace("-", ""))
    if " " in terim:
        kelimeler = terim.split()
        if len(kelimeler) == 2:
            v.add("".join(kelimeler))
            v.add("-".join(kelimeler))
    # bas artikeli olan/olmayan hali
    if terim.startswith("The "):
        v.add(terim[4:])
    return {x for x in v if len(x) >= 3}


def terimleri_topla(sozluk_yolu):
    with open(sozluk_yolu, "r", encoding="utf-8") as f:
        veri = yaml.safe_load(f)

    terimler = {}

    def ekle(anahtar, adaylar, bilgi):
        adaylar = [a for a in adaylar if a]
        if not adaylar:
            return
        tum = set()
        for a in adaylar:
            tum |= varyantlar(a)
        bilgi = dict(bilgi)
        bilgi["adaylar"] = sorted(tum, key=lambda s: (-len(s), s))
        terimler.setdefault(anahtar, bilgi)

    for girdi in veri:
        mertebeler = girdi.get("mertebeler")

        if mertebeler:
            yol_en_list = etiket_temizle(girdi.get("ingilizce", ""))
            yol_en = yol_en_list[0] if yol_en_list else ""

            kardesler = []
            for m in mertebeler:
                kardesler += etiket_temizle(str(m.get("isim", "")))

            for m in mertebeler:
                ham = str(m.get("isim", ""))
                adaylar = etiket_temizle(ham)
                if not adaylar:
                    continue
                # mertebe adinda Turkce kisim da var; sadece Ingilizce parantezi al
                ing = re.search(r"\(([^)]*)\)", ham)
                if ing:
                    adaylar = etiket_temizle(ing.group(1))
                if m.get("arama_adi"):
                    adaylar = list(m["arama_adi"])
                anahtar = adaylar[0]
                ekle(
                    anahtar,
                    adaylar,
                    {
                        "tur": "mertebe",
                        "yol": girdi["terim"],
                        "yol_en": yol_en,
                        "seviye": m.get("seviye"),
                        "kardesler": [k for k in kardesler if k not in adaylar],
                        "mevcut_bolum": m.get("bolum_siniri"),
                    },
                )
        else:
            adaylar = etiket_temizle(girdi.get("ingilizce", ""))
            if girdi.get("arama_adi"):
                adaylar = list(girdi["arama_adi"])
            if not adaylar:
                continue
            ekle(
                adaylar[0],
                adaylar,
                {
                    "tur": "girdi",
                    "kategori": girdi.get("kategori", ""),
                    "yol": None,
                    "yol_en": None,
                    "seviye": None,
                    "kardesler": [],
                    "mevcut_bolum": girdi.get("bolum_siniri"),
                },
            )

    return terimler


# ------------------------------------------------------------------- kaynak


def dosyalari_bul(klasor):
    if not os.path.isdir(klasor):
        print(f"HATA: '{klasor}' klasoru yok.", file=sys.stderr)
        sys.exit(1)
    d = [x for x in os.listdir(klasor) if x.lower().endswith((".txt", ".md"))]
    if not d:
        print(f"HATA: '{klasor}' icinde .txt/.md yok.", file=sys.stderr)
        sys.exit(1)

    def anahtar(ad):
        s = re.findall(r"\d+", ad)
        return (int(s[0]) if s else 0, ad)

    return [os.path.join(klasor, x) for x in sorted(d, key=anahtar)]


def bolumlere_ayir(yol):
    bolumler, aktif, tampon = {}, None, []
    with open(yol, "r", encoding="utf-8", errors="ignore") as f:
        for satir in f:
            m = BOLUM_BASLIGI.match(satir.strip())
            if m:
                if aktif is not None:
                    bolumler.setdefault(aktif, []).append("".join(tampon))
                aktif, tampon = int(m.group(1)), []
                continue
            if aktif is not None:
                tampon.append(satir)
    if aktif is not None:
        bolumler.setdefault(aktif, []).append("".join(tampon))
    return {n: "".join(p) for n, p in bolumler.items()}


# ------------------------------------------------------------------- tarama


def guven(aday, bilgi, metin, konum):
    bas = max(0, konum - PENCERE)
    son = min(len(metin), konum + len(aday) + PENCERE)
    pencere = metin[bas:son]

    if len(aday.split()) >= 2:
        return YUKSEK
    if IPUCU_RE.search(pencere):
        return YUKSEK
    for k in bilgi.get("kardesler", []):
        if k and len(k.split()) >= 2 and k in pencere:
            return YUKSEK
    yol_en = bilgi.get("yol_en")
    if yol_en and yol_en in pencere:
        return YUKSEK

    onceki = metin[max(0, konum - 40) : konum]
    if CUMLE_BASI.search(onceki) or konum == 0:
        return ORTA
    return ORTA


def baglam(metin, konum, uzunluk, genislik=110):
    bas = max(0, konum - genislik)
    son = min(len(metin), konum + uzunluk + genislik)
    return re.sub(r"\s+", " ", metin[bas:son].replace("\n", " ")).strip()


def tara(terimler, dosyalar):
    duyarli = {}
    duyarsiz = {}
    for t, bilgi in terimler.items():
        duyarli[t] = [
            (a, re.compile(r"(?<!\w)" + re.escape(a) + r"(?!\w)"))
            for a in bilgi["adaylar"]
        ]
        duyarsiz[t] = [
            (a, re.compile(r"(?<!\w)" + re.escape(a) + r"(?!\w)", re.IGNORECASE))
            for a in bilgi["adaylar"]
        ]

    sonuc = {
        t: {
            "en_iyi": YOK,
            "bolum": None,
            "baglam": None,
            "eslesen": None,
            "kucuk_harf": 0,
        }
        for t in terimler
    }

    bolum_deposu = []
    for yol in dosyalar:
        print(f"[{os.path.basename(yol)}] taraniyor...", file=sys.stderr)
        b = bolumlere_ayir(yol)
        if not b:
            print("  UYARI: bolum basligi bulunamadi.", file=sys.stderr)
        for no in sorted(b):
            bolum_deposu.append((no, b[no]))

    # 1. tur: harf duyarli
    for no, metin in bolum_deposu:
        for t, bilgi in terimler.items():
            for aday, desen in duyarli[t]:
                if aday not in metin:
                    continue
                for m in desen.finditer(metin):
                    g = guven(aday, bilgi, metin, m.start())
                    s = sonuc[t]
                    daha_iyi = SIRA[g] > SIRA[s["en_iyi"]]
                    ayni_erken = (
                        g == s["en_iyi"] and s["bolum"] is not None and no < s["bolum"]
                    )
                    if daha_iyi or ayni_erken:
                        s.update(
                            en_iyi=g,
                            bolum=no,
                            baglam=baglam(metin, m.start(), len(aday)),
                            eslesen=aday,
                        )
                    break

    # 2. tur: sadece bulunamayanlar icin harf duyarsiz
    kalan = [t for t in terimler if sonuc[t]["en_iyi"] == YOK]
    if kalan:
        print(f"\n{len(kalan)} terim icin esnek tur...", file=sys.stderr)
        for no, metin in bolum_deposu:
            for t in kalan:
                if sonuc[t]["en_iyi"] != YOK:
                    continue
                for aday, desen in duyarsiz[t]:
                    m = desen.search(metin)
                    if m:
                        sonuc[t].update(
                            en_iyi=ESNEK,
                            bolum=no,
                            baglam=baglam(metin, m.start(), len(aday)),
                            eslesen=aday,
                        )
                        break

    # cins isim tespiti: terim metinde kucuk harfle de geciyor mu?
    for t, bilgi in terimler.items():
        ana = bilgi["adaylar"][0]
        if len(ana.split()) > 1:
            continue
        kucuk = re.compile(r"(?<!\w)" + re.escape(ana.lower()) + r"(?!\w)")
        n = 0
        for no, metin in bolum_deposu:
            n += len(kucuk.findall(metin))
            if n > 5:
                break
        sonuc[t]["kucuk_harf"] = n

    return sonuc


# -------------------------------------------------------------------- cikti


def rapor_yaz(terimler, sonuc, yol):
    bas = "guven\tbolum\tguvenilir_mi\tseviye\tyol\tterim\teslesen\tmevcut\tbaglam"
    satirlar = [bas]
    for t, bilgi in sorted(
        terimler.items(), key=lambda kv: (SIRA[sonuc[kv[0]]["en_iyi"]], kv[0])
    ):
        s = sonuc[t]
        guvenilir = "hayir(cins_isim)" if s["kucuk_harf"] > 0 else "evet"
        satirlar.append(
            "\t".join(
                [
                    s["en_iyi"],
                    str(s["bolum"] or ""),
                    guvenilir,
                    str(bilgi.get("seviye") if bilgi.get("seviye") is not None else ""),
                    str(bilgi.get("yol") or bilgi.get("kategori") or ""),
                    t,
                    str(s["eslesen"] or ""),
                    str(bilgi.get("mevcut_bolum") or ""),
                    (s["baglam"] or "")[:200],
                ]
            )
        )
    with open(yol, "w", encoding="utf-8") as f:
        f.write("\n".join(satirlar) + "\n")


def yama_yaz(terimler, sonuc, yol):
    cikti = {}
    for t, bilgi in terimler.items():
        s = sonuc[t]
        cikti[t] = {
            "metinde": s["en_iyi"] != YOK,
            "guven": s["en_iyi"],
            "bolum": s["bolum"],
            "bolum_guvenilir": s["kucuk_harf"] == 0,
            "eslesen_string": s["eslesen"],
            "mevcut_bolum": bilgi.get("mevcut_bolum"),
            "yol": bilgi.get("yol"),
            "seviye": bilgi.get("seviye"),
        }
    with open(yol, "w", encoding="utf-8") as f:
        yaml.safe_dump(cikti, f, allow_unicode=True, sort_keys=True)


def ozet(terimler, sonuc):
    c = defaultdict(int)
    for t in terimler:
        c[sonuc[t]["en_iyi"]] += 1
    print("\n--- OZET ---")
    print(f"  yuksek : {c[YUKSEK]:>4}  metinde, ipucu dogrulanmis")
    print(f"  orta   : {c[ORTA]:>4}  metinde, buyuk harfli")
    print(f"  esnek  : {c[ESNEK]:>4}  sadece harf duyarsiz turda bulundu <- gozle bak")
    print(f"  yok    : {c[YOK]:>4}  hicbir turda bulunamadi <- metinde: false")

    print("\n--- ESNEK TURDA BULUNANLAR (dogrula) ---")
    for t, bilgi in sorted(terimler.items()):
        if sonuc[t]["en_iyi"] == ESNEK:
            s = sonuc[t]
            yer = bilgi.get("yol") or bilgi.get("kategori") or ""
            print(f"  {yer} / {t}  (ch.{s['bolum']}, '{s['eslesen']}')")
            print(f"      {(s['baglam'] or '')[:150]}")

    print("\n--- HIC BULUNAMAYANLAR (metinde: false adaylari) ---")
    for t, bilgi in sorted(terimler.items()):
        if sonuc[t]["en_iyi"] == YOK:
            sv = bilgi.get("seviye")
            sv = f"S{sv}" if sv is not None else "--"
            yer = bilgi.get("yol") or bilgi.get("kategori") or ""
            print(f"  {yer} {sv}: {t}")

    print("\n--- BOLUM NUMARASI GUVENILMEZ (cins isim) ---")
    n = 0
    for t, bilgi in sorted(terimler.items()):
        if sonuc[t]["kucuk_harf"] > 0 and sonuc[t]["bolum"]:
            n += 1
    print(f"  {n} terim metinde kucuk harfle de geciyor; bolum numaralarini")
    print("  'metinde' icin degil, sadece ipucu olarak kullanin.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sozluk", default="sozluk.yml")
    ap.add_argument("--kaynak", default="./LotM_Volumes")
    ap.add_argument("--rapor", default="rapor.tsv")
    ap.add_argument("--yama", default=None)
    a = ap.parse_args()

    terimler = terimleri_topla(a.sozluk)
    print(f"{len(terimler)} terim yuklendi.", file=sys.stderr)
    dosyalar = dosyalari_bul(a.kaynak)
    print(f"{len(dosyalar)} dosya bulundu.\n", file=sys.stderr)

    sonuc = tara(terimler, dosyalar)

    rapor_yaz(terimler, sonuc, a.rapor)
    print(f"\nRapor: {a.rapor}")
    if a.yama:
        yama_yaz(terimler, sonuc, a.yama)
        print(f"Yama: {a.yama}")
    ozet(terimler, sonuc)


if __name__ == "__main__":
    main()
