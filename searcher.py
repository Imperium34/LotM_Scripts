#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
searcher.py -- "Bu ad metinde geciyor mu?" sorusunu yanitlar.

v1'e gore duzeltmeler:
  1. Parantez ve slash artik TUM girdilerden temizleniyor (v1 sadece
     mertebeler icin yapiyordu; "Blasphemer Amon (King of Angels)" gibi
     stringler oldugu gibi aranip garantili sifir donuyordu).
  2. Yazim varyantlari uretiliyor: "Grave Digger" -> "Gravedigger",
     "Wind-Blessed" -> "Wind Blessed" vb.
  3. Iki asamali arama. Once harf duyarli (ozel isimler icin dogru),
     bulunamayanlar icin harf duyarsiz ikinci tur. Boolean soru icin
     yanlis pozitif, yanlis negatiften ucuzdur.
  4. Ipucu listesi daraltildi. v1'de "Beyonder", "ritual", "angel",
     "advance" vardi; bu romanda bu kelimeler her yerde geciyor.
  5. Cins isim tespiti: terim metinde kucuk harfle de geciyorsa, bulunan
     bolum numarasi guvenilmez olarak isaretlenir.
  6. sozluk.yml'de istege bagli 'arama_adi' alani destekleniyor.

Terim uretimi, varyantlar ve bolume ayirma artik lotm.py'de.

BOLUM NUMARASI NE ANLAMA GELIR
------------------------------
'bolum' sutunu terimin ILK gectigi bolumdur -- cunku etiketle.py onu
bolum_siniri (kapi) olarak yazar ve kapi "bu addan once soz edilmez"
demektir.

Eskiden bu sutun guvene gore yaziliyordu: sonraki bir bolumde daha
yuksek guvenli bir gecis bulununca numara ILERI kayiyordu. etiketle.py
de yalnizca ileri yazdigi (tarayici > mevcut) icin kapi her calistirmada
biraz daha gec bir bolume suruklenebiliyor, denetci2 de arada kalan
mesru kullanimlari "kapidan once" diye isaretliyordu.

Artik once en yuksek guven KATMANI secilir, sonra o katmandaki EN ERKEN
bolum yazilir. Guven yine sonucu filtreler ama numarayi ileri itmez.

Kullanim:
    python3 searcher.py --sozluk sozluk.yml --kaynak ./LotM_Volumes \
        --rapor rapor.tsv --yama yama.yml
"""

import argparse
import re
import sys
from collections import defaultdict

import lotm

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

YUKSEK, ORTA, ESNEK, YOK = "yuksek", "orta", "esnek", "yok"
SIRA = {YUKSEK: 3, ORTA: 2, ESNEK: 1, YOK: 0}


# ------------------------------------------------------------- terim uretimi


def terimleri_topla(sozluk_yolu=None):
    """
    lotm.Terim kayitlarini {anahtar: bilgi} tarama gorunumune cevirir.

    Anahtar KANONIK INGILIZCE addir (Terim.anahtar), arama_adi degil.
    Eskiden anahtar arama_adi[0] idi ama etiketle.py raporu parantez
    icindeki adla ariyordu; arama_adi verilmis terimler sessizce
    eslesmiyor, "raporda yok" sayilip hic etiketlenmiyorlardi.
    """
    sozluk = lotm.sozluk_yukle(sozluk_yolu)

    terimler = {}
    cakisma = defaultdict(list)
    for t in sozluk.terimler:
        anahtar = t.anahtar
        adaylar = t.arama_adaylari()
        if not anahtar or not adaylar:
            continue
        cakisma[anahtar].append(t.yer)
        if anahtar in terimler:
            continue          # ilk kayit kalir (eski davranis)
        terimler[anahtar] = {
            "tur": "mertebe" if t.mertebe_mi else "girdi",
            "yol": t.yol,
            "yol_en": t.yol_en,
            "kategori": t.kategori,
            "seviye": t.seviye,
            "kardesler": [k for k in t.kardesler_tr if k not in adaylar],
            "mevcut_bolum": t.bolum_siniri,
            "adaylar": adaylar,
        }

    for anahtar, yerler in cakisma.items():
        if len(yerler) > 1:
            print(f"  uyari: '{anahtar}' birden fazla girdide: "
                  f"{', '.join(yerler)} -- ilki kullanildi", file=sys.stderr)

    return terimler


# ------------------------------------------------------------------- tarama


def guven(aday, bilgi, metin, konum):
    """
    Bir gecisin ne kadar ikna edici oldugu.

    Not: burada eskiden bir CUMLE_BASI kontrolu vardi ama iki kolunda da
    ORTA donuyordu, yani olcup atiyordu. ORTA'nin altinda anlamli bir
    katman da yok (ESNEK "yalnizca harf duyarsiz turda bulundu" demek,
    baska bir sey), o yuzden kaldirildi. Cumle basi ayrimi denetci2'de
    duruyor; orada gercekten bir karsiligi var.
    """
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
    return ORTA


def baglam(metin, konum, uzunluk, genislik=110):
    bas = max(0, konum - genislik)
    son = min(len(metin), konum + uzunluk + genislik)
    return re.sub(r"\s+", " ", metin[bas:son].replace("\n", " ")).strip()


def golge_haritasi(terimler):
    """
    {aday: [onu iceren daha uzun adlar]}

    'Hunter' hem kendi basina hem 'Demon Hunter' icinde gecer. Eskiden bu
    yuzden Hunter'a HIC bolum yazilmiyordu (once elle liste, sonra
    turetilen liste). Ama bu, sorunu yanlis yerde cozmek: risk terimin
    KENDISINDE degil, tek tek GECISLERDE. 'Hunter' metinde bagimsiz da
    geciyor; o gecisler gayet gecerli.

    Bu harita ile her gecis ayri ayri sorgulanabilir: bu konumdaki
    'Hunter' daha uzun bir adin parcasi mi, degil mi?
    """
    tum = set()
    for bilgi in terimler.values():
        tum.update(bilgi["adaylar"])

    harita = {}
    for kisa in tum:
        desen = re.compile(r"(?<!\w)" + re.escape(kisa) + r"(?!\w)")
        uzunlar = [u for u in tum
                   if len(u) > len(kisa) and desen.search(u)]
        if uzunlar:
            harita[kisa] = sorted(uzunlar, key=len, reverse=True)
    return harita


def golgede_mi(metin, bas, son, uzunlar) -> bool:
    """Bu gecis daha uzun bir adin icinde mi kaliyor?"""
    for uzun in uzunlar:
        pencere_bas = max(0, bas - len(uzun))
        parca = metin[pencere_bas:son + len(uzun)]
        i = parca.find(uzun)
        while i != -1:
            mutlak_bas = pencere_bas + i
            mutlak_son = mutlak_bas + len(uzun)
            if mutlak_bas <= bas and mutlak_son >= son:
                return True
            i = parca.find(uzun, i + 1)
    return False


def tara(terimler, bolumler):
    duyarli, duyarsiz = {}, {}
    for t, bilgi in terimler.items():
        duyarli[t] = [(a, re.compile(r"(?<!\w)" + re.escape(a) + r"(?!\w)"))
                      for a in bilgi["adaylar"]]
        duyarsiz[t] = [(a, re.compile(r"(?<!\w)" + re.escape(a) + r"(?!\w)",
                                      re.IGNORECASE))
                       for a in bilgi["adaylar"]]

    # katman -> ilk gorulen bolum. "En yuksek katmanin en erken bolumu"
    # ancak butun katmanlar ayri tutulursa hesaplanabilir.
    sonuc = {t: {"katman": {}, "kucuk_harf": 0, "golgelendi": 0}
             for t in terimler}
    golge = golge_haritasi(terimler)

    bolum_deposu = [(b.no, b.metin) for b in bolumler if b.no is not None]
    bolum_deposu.sort(key=lambda x: x[0])

    # 1. tur: harf duyarli
    for no, metin in bolum_deposu:
        for t, bilgi in terimler.items():
            for aday, desen in duyarli[t]:
                if aday not in metin:
                    continue
                uzunlar = golge.get(aday)
                # Bolum icindeki EN IYI gecisi bul; YUKSEK'e ulasinca dur.
                # Eskiden ilk eslesmeden sonra kosulsuz break vardi, yani
                # ayni bolumde daha ikna edici bir gecis varsa gorulmuyordu.
                for m in desen.finditer(metin):
                    if uzunlar and golgede_mi(metin, m.start(), m.end(), uzunlar):
                        sonuc[t]["golgelendi"] += 1
                        continue
                    g = guven(aday, bilgi, metin, m.start())
                    katman = sonuc[t]["katman"]
                    if g not in katman:
                        katman[g] = (no, baglam(metin, m.start(), len(aday)), aday)
                    if g == YUKSEK:
                        break
                break

    # 2. tur: sadece hic bulunamayanlar icin harf duyarsiz
    kalan = [t for t in terimler if not sonuc[t]["katman"]]
    if kalan:
        print(f"\n{len(kalan)} terim icin esnek tur...", file=sys.stderr)
        for no, metin in bolum_deposu:
            for t in kalan:
                if sonuc[t]["katman"]:
                    continue
                for aday, desen in duyarsiz[t]:
                    m = desen.search(metin)
                    if m:
                        sonuc[t]["katman"][ESNEK] = (
                            no, baglam(metin, m.start(), len(aday)), aday)
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

    # katmanlari duzlestir.
    #
    # Iki AYRI soru var ve eskiden tek sayiya sikistirilmislardi:
    #   'bolum'        -> terim ILK nerede geciyor?   (kapi budur)
    #   'kanit_bolum'  -> en ikna edici gecis nerede? (tani icindir)
    # Guven katmani "metinde var mi" sorusunu yanitlar; nerede BASLADIGINI
    # yanitlamaz. Ikisini karistirmak kapiyi surekli ileri itiyordu.
    #
    # ESNEK katmani digerleriyle bir arada bulunamaz (ikinci tur yalnizca
    # hicbir katmani olmayan terimler icin calisir), o yuzden en erken
    # bolum dogrudan alinabilir.
    duz = {}
    for t, s in sonuc.items():
        katman = s["katman"]
        if not katman:
            duz[t] = {"en_iyi": YOK, "bolum": None, "kanit_bolum": None,
                      "baglam": None, "eslesen": None,
                      "kucuk_harf": s["kucuk_harf"],
                      "golgelendi": s["golgelendi"]}
            continue
        en_iyi = max(katman, key=lambda g: SIRA[g])
        kanit_no, ctx, aday = katman[en_iyi]
        duz[t] = {
            "en_iyi": en_iyi,
            "bolum": min(v[0] for v in katman.values()),
            "kanit_bolum": kanit_no,
            "baglam": ctx,
            "eslesen": aday,
            "kucuk_harf": s["kucuk_harf"],
            "golgelendi": s["golgelendi"],
        }
    return duz


# -------------------------------------------------------------------- cikti


def rapor_yaz(terimler, sonuc, yol):
    bas = ("guven\tbolum\tkanit_bolum\tguvenilir_mi\tseviye\tyol\tterim"
           "\teslesen\tmevcut\tbaglam")
    satirlar = [bas]
    for t, bilgi in sorted(terimler.items(),
                           key=lambda kv: (SIRA[sonuc[kv[0]]["en_iyi"]], kv[0])):
        s = sonuc[t]
        guvenilir = "hayir(cins_isim)" if s["kucuk_harf"] > 0 else "evet"
        satirlar.append("\t".join([
            s["en_iyi"],
            str(s["bolum"] or ""),
            str(s["kanit_bolum"] or ""),
            guvenilir,
            str(bilgi.get("seviye") if bilgi.get("seviye") is not None else ""),
            str(bilgi.get("yol") or bilgi.get("kategori") or ""),
            t,
            str(s["eslesen"] or ""),
            str(bilgi.get("mevcut_bolum") or ""),
            (s["baglam"] or "")[:200],
        ]))
    with open(yol, "w", encoding="utf-8") as f:
        f.write("\n".join(satirlar) + "\n")


def yama_yaz(terimler, sonuc, yol):
    import yaml
    cikti = {}
    for t, bilgi in terimler.items():
        s = sonuc[t]
        cikti[t] = {
            "metinde": s["en_iyi"] != YOK,
            "guven": s["en_iyi"],
            "bolum": s["bolum"],
            "kanit_bolum": s["kanit_bolum"],
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
    n = sum(1 for t in terimler
            if sonuc[t]["kucuk_harf"] > 0 and sonuc[t]["bolum"])
    print(f"  {n} terim metinde kucuk harfle de geciyor; bolum numaralarini")
    print("  'metinde' icin degil, sadece ipucu olarak kullanin.")

    golgeli = [(t, sonuc[t]["golgelendi"]) for t in terimler
               if sonuc[t]["golgelendi"]]
    if golgeli:
        print("\n--- DAHA UZUN BIR ADIN ICINDE ELENEN GECISLER ---")
        print("  Bu gecisler sayilmadi ('Hunter' ama aslinda 'Demon Hunter').")
        print("  Terimin BAGIMSIZ gecisleri varsa bolum numarasi yine yazilir;")
        print("  eskiden bu terimlere hic numara yazilmiyordu.")
        for t, n in sorted(golgeli, key=lambda x: -x[1])[:15]:
            durum = sonuc[t]["bolum"] or "bagimsiz gecis yok"
            print(f"  {t}: {n} gecis elendi, kalan kapi {durum}")

    gec = [(t, sonuc[t]) for t in terimler
           if sonuc[t]["bolum"] and sonuc[t]["kanit_bolum"]
           and sonuc[t]["bolum"] < sonuc[t]["kanit_bolum"]]
    if gec:
        print("\n--- KAPI ILK GECISTE, KANIT DAHA GEC ---")
        print("  Bu terimler once daha zayif bir baglamda geciyor, ikna edici")
        print("  gecis sonra geliyor. Kapi ILK gecistir; asagidaki ikinci sayi")
        print("  yalnizca 'gercekten bu terim mi' sorusunun kaniti nerede.")
        for t, s in sorted(gec, key=lambda x: x[1]["bolum"])[:20]:
            print(f"  {t}: kapi {s['bolum']}, kanit {s['kanit_bolum']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sozluk", default=None)
    ap.add_argument("--kaynak", default=None)
    ap.add_argument("--rapor", default="rapor.tsv")
    ap.add_argument("--yama", default=None)
    a = ap.parse_args()

    try:
        terimler = terimleri_topla(a.sozluk)
        print(f"{len(terimler)} terim yuklendi.", file=sys.stderr)
        bolumler = lotm.bolumler_en(a.kaynak)
    except (FileNotFoundError, OSError) as e:
        sys.exit(f"HATA: {e}")
    print(f"{len(bolumler)} bolum bulundu.\n", file=sys.stderr)

    sonuc = tara(terimler, bolumler)

    rapor_yaz(terimler, sonuc, a.rapor)
    print(f"\nRapor: {a.rapor}")
    if a.yama:
        yama_yaz(terimler, sonuc, a.yama)
        print(f"Yama: {a.yama}")
    ozet(terimler, sonuc)


if __name__ == "__main__":
    main()
