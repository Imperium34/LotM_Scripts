#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hizalama_denetle.py -- hizalamanin KAYIP oldugu bolumleri bulur.

UST DUZEY SORU: "Bu bolumun hizalamasina guvenebilir miyim?"

NEDEN GEREKLI
-------------
ceviri_denetle ve toplu_denetle'nin butun ciktisi hizalamanin dogruluguna
dayanir. Hizalama kaydiginda, ESLESMEYEN listesi sessizce curur: terim
kaynakta vardir, karsilik hedefte vardir, ama ikisi ayni gruba dusmedigi
icin "eslesmedi" gorunur. Bu, ceviri hatasindan ayirt edilemez.

Bolum 4 bunun canli ornegi. Turkce ¶52, Cince ¶52'yi ikiye boluyor;
Gale-Church bunu 1:2 olarak kaydetmek yerine (230 puan ceza) bir dizi 1:1
olarak yutuyor, cunku uzun vadede daha ucuz. Sonuc: ¶53'ten sonuna kadar
her sey bir paragraf kayiyor ve BASLIKTA hicbir sey gorunmuyor --
"102 grup, 4 tanesi bolunmus/birlesmis" der, sanki her sey yolundaymis gibi.

NEDEN PARAGRAF SAYISI YETMEZ
----------------------------
Ilk akla gelen olcut, kaynak ve hedef paragraf sayilarinin farkidir. Ise
yaramaz: gruplarin (len(ia) - len(ib)) toplami zaten TANIMI GEREGI n - m'e
esittir, yani her hizalama bu sinavi gecer. Ustelik Bolum 4'te bir birlesme
ile bir bolunme birbirini gotururuyor; sayilar tutuyor, icerik kayiyor.

IKI GERCEK SINYAL
-----------------
1. UZUNLUK ARTIGI. Gale-Church'un kendi z-skoru: bir grubun hedef uzunlugu,
   bolum genelindeki orandan ne kadar sapiyor. TEK BASINA bir sapma normaldir
   (gercek bir birlesme, atlanmis bir cumle). Onemli olan ARDISIK sapma
   dizisidir -- kayma, tek bir hatanin sonraki her grubu bozmasidir.

2. REPLIK UYUSMAZLIGI. Cince'de replik “ ile, Turkce'de " ile baslar. Bir
   grupta taraflardan biri replik, digeri anlatiysa o grup neredeyse kesin
   yanlistir. Ucuz, yerel ve yorum gerektirmez.

Kullanim:
    hizalama_denetle.py                 butun ortak bolumler, ozet
    hizalama_denetle.py 4               tek bolum, grup grup
    hizalama_denetle.py --esik 2.5
    hizalama_denetle.py --kendini-dene  ic testler (depo gerektirmez)
"""

from __future__ import annotations

import argparse
import math
import re
import sys

# Ardisik supheli grup sayisi bunu asarsa "kayma" denir. 2 dusuk kalir
# (gercek bir bolunme cevresinde iki grup bozulabilir); 3 iyi bir esik.
KAYMA_UZUNLUGU = 3

# z-skor esigi. Gale-Church'un varyansi 6.8; 2.0 kabaca %95'lik dilim.
Z_ESIGI = 2.0

# Konusma tespiti iki tuzagi birden atlamak zorunda:
#
#   (1) BASLANGICA BAKMAK YETMEZ. Turkce konusma etiketini one aliyor
#       ("Kadın kıkırdayarak, '...' dedi"); paragraf replikle baslamadigi
#       hâlde replik iceriyor. Bu yuzden paragrafin ICINDE aranir.
#
#   (2) TIRNAK HER ZAMAN KONUSMA DEGIL. Cince'de “ ” ayni zamanda TERIM
#       isaretidir (“占卜家”魔药) ve LotM bunu her paragrafta kullaniyor.
#       Ayirt edici olan uzunluk: terim birkac karakter, replik uzun.
#       15 karakter ikisini temiz ayiriyor.
#
# Turkce tarafta ayrica bir kolaylik var: bu cevirinin kendi teamulunde
# " konusma, ' terim demek. O yuzden TR'de yalnizca cift tirnak sayilir.
_ALINTI = {
    "zh": re.compile(r'[“"]([^”"\n]{15,})[”"]'),
    "tr": re.compile(r'"([^"\n]{15,})"'),
    "en": re.compile(r'"([^"\n]{15,})"'),
}


def replik_mi(metin: str, dil: str = "zh") -> bool:
    return bool(_ALINTI.get(dil, _ALINTI["zh"]).search(metin))


# Capa yer degistirme penceresi. 1 = yalnizca komsu gruplar. Genisletmek
# geri donusu hizla azaltir: 2'de gercek bir kayma zaten baska bir sinyalle
# yakalanmis olur, 3'te ayni adin iki normal gecisi tesadufen eslesmeye
# baslar.
CAPA_PENCERESI = 1


def capa_yer_degistirme(k_par, h_par, gruplar, sozluk, pencere=CAPA_PENCERESI):
    """
    Bir capa terimi bir grupta YALNIZ kaynakta, komsu bir grupta YALNIZ
    hedefte geciyorsa, o ad kaybolmamis -- KAYMISTIR.

    Uzunluk artigi ve replik uyusmazligindan farkli olarak bu, bir supheyi
    degil belirli bir arizayi olcer: ozel ad ceviride degismeden gectigi
    icin (capa.py'nin dayandigi ozellik) iki tarafta da aranabilir ve
    konum farki dogrudan kaymanin YONUNU verir.

    Doner: {grup_indisi: [(zh, tr, yon), ...]} -- indis kaymanin BASI.
    """
    n = len(gruplar)
    metin_k, metin_h = [], []
    for ia, ib in gruplar:
        metin_k.append("".join(k_par[i] for i in ia))
        metin_h.append(" ".join(h_par[j] for j in ib))

    bulgular = {}
    for zh, tr in sozluk.items():
        yalniz_k = [i for i in range(n) if zh in metin_k[i] and tr not in metin_h[i]]
        if not yalniz_k:
            continue
        yalniz_h = [i for i in range(n) if tr in metin_h[i] and zh not in metin_k[i]]

        terim_bulgu = []
        for i in yalniz_k:
            for j in yalniz_h:
                if 0 < abs(i - j) <= pencere:
                    yon = "hedef geride" if j > i else "hedef ileride"
                    terim_bulgu.append((min(i, j), zh, tr, yon))

        # YON TUTARLILIGI. Bir terim bolum icinde HEM geride HEM ileride
        # yer degistiriyorsa bulgulari tesadufidir, hepsi atilir.
        #
        # Gerekcesi mekanizmanin kendisi: bir ad iki tarafta da seyrek
        # aralikli tek-yonlu geciyorsa (Cince ozneyi tekrarlar, Turkce
        # duserir; Turkce bazen ad ekler) ZH-yalniz {16,18,20} ile
        # TR-yalniz {17,19} ic ice gecer ve her bosluk bir cift uretir --
        # sirayla geride, ileride, geride. Gercek kayma bunu yapamaz:
        # hedef ¶17'de bir grup gerideyse ¶18'de ilerde olamaz.
        #
        # Bolum 6'da 周明瑞 (o bolumde Klein'in kullandigi ad) ¶15-20 ve
        # 奥黛丽 ¶48-51 tam bu sekli veriyordu.
        if len({y for *_x, y in terim_bulgu}) > 1:
            continue
        for i, z, t, y in terim_bulgu:
            bulgular.setdefault(i, []).append((z, t, y))

    return {i: sorted(set(v)) for i, v in bulgular.items()}


def grup_artiklari(
    k_par, h_par, gruplar, varyans: float = 6.8, k_dil: str = "zh", h_dil: str = "tr"
):
    """
    Her grup icin (z_skoru, replik_uyusmazligi) uretir.

    z, DP'nin kendi maliyet fonksiyonuyla ayni: hedef uzunlugun, bolum
    genelindeki oranin ongordugu uzunluktan kac standart sapma uzakta
    oldugu. Tek tarafli gruplar (bir tarafi bos) tanimsizdir; onlar
    zaten baslikta ayrica sayiliyor.
    """
    top_k = sum(len(p) for p in k_par) or 1
    top_h = sum(len(p) for p in h_par) or 1
    c = top_h / top_k

    for ia, ib in gruplar:
        if not ia or not ib:
            yield None, False
            continue
        la = sum(len(k_par[i]) for i in ia)
        lb = sum(len(h_par[j]) for j in ib)
        payda = math.sqrt(max(1.0, c * max(la, 1) * varyans))
        z = abs(lb - c * la) / payda
        # Grubun ICINDE replik VAR MI diye bakilir, grubun BASI replik mi
        # diye degil. Turkce, Cince'nin aksine konusma etiketini sik sik one
        # aliyor ("Kadın kıkırdayarak, '...' dedi"), yani hedef paragraf
        # replikle basmadigi hâlde replik icerebiliyor. Ilk surum yalnizca
        # ilk paragrafa bakiyordu ve bu yapiyi her seferinde uyusmazlik
        # sayiyordu -- diyalog agirlikli bolumlerde yanlis alarm ureten
        # sistematik kaynak buydu.
        uyusmaz = any(replik_mi(k_par[i], k_dil) for i in ia) != any(
            replik_mi(h_par[j], h_dil) for j in ib
        )
        yield z, uyusmaz


def kayma_bul(artiklar, z_esigi=Z_ESIGI, uzunluk=KAYMA_UZUNLUGU):
    """
    Ardisik supheli gruplarin dizilerini bulur.

    Doner: [(bas_indis, son_indis, dizideki_uyusmazlik_sayisi)]
    """
    diziler, bas = [], None
    for i, art in enumerate(artiklar):
        z, uyusmaz = art[0], art[1]
        yer = art[2] if len(art) > 2 else False
        supheli = uyusmaz or yer or (z is not None and z > z_esigi)
        if supheli and bas is None:
            bas = i
        elif not supheli and bas is not None:
            if i - bas >= uzunluk:
                diziler.append((bas, i - 1))
            bas = None
    if bas is not None and len(artiklar) - bas >= uzunluk:
        diziler.append((bas, len(artiklar) - 1))
    return diziler


def bolumu_denetle(
    k_par, h_par, gruplar, z_esigi=Z_ESIGI, k_dil="zh", h_dil="tr", sozluk=None
):
    ikili = list(grup_artiklari(k_par, h_par, gruplar, k_dil=k_dil, h_dil=h_dil))
    yerler = capa_yer_degistirme(k_par, h_par, gruplar, sozluk) if sozluk else {}
    artiklar = [(z, u, i in yerler) for i, (z, u) in enumerate(ikili)]
    diziler = kayma_bul(artiklar, z_esigi)
    uyusmaz = sum(1 for _z, u, _y in artiklar if u)
    tek = sum(1 for ia, ib in gruplar if not ia or not ib)
    coklu = sum(1 for ia, ib in gruplar if len(ia) > 1 or len(ib) > 1)
    return {
        "grup": len(gruplar),
        "kaynak_par": len(k_par),
        "hedef_par": len(h_par),
        "uyusmazlik": uyusmaz,
        "tek_tarafli": tek,
        "coklu": coklu,
        "kaymalar": diziler,
        "kayan_grup": sum(b - a + 1 for a, b in diziler),
        "yer_degistirme": yerler,
        # Iki sinyalin de isaret ettigi gruplar: hem uzunluk artigi hem
        # replik uyusmazligi. Tek sinyale dayanan bir bulgu tartisilir,
        # ikisine birden dayanan neredeyse kesindir.
        # Uc sinyalden en az IKISI. Capa yer degistirmesi tek basina da
        # neredeyse kesindir, ama sayim olcutu ayni kalsin diye burada
        # digerleriyle ayni agirliktadir.
        "kesin": sum(
            1
            for z, u, y in artiklar
            if (u + y + bool(z is not None and z > z_esigi)) >= 2
        ),
        "artiklar": artiklar,
    }


# ------------------------------------------------------------------ CLI


def ana(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Hizalama kayması denetimi")
    ap.add_argument("bolum", nargs="?", type=int)
    ap.add_argument("--kaynak", default="zh", choices=("zh", "en"))
    ap.add_argument("--hedef", default="tr", choices=("tr", "en"))
    ap.add_argument("--esik", type=float, default=Z_ESIGI)
    ap.add_argument("--kendini-dene", action="store_true", dest="dene")
    ap.add_argument(
        "--capasiz", action="store_true", help="çapa kısıtını kapat (kıyas için)"
    )
    a = ap.parse_args(argv)

    if a.dene:
        return kendini_dene()

    import lotm
    import bolum as B
    import capa as _capa

    _capa_sozlugu = _capa.sozluk_yukle()

    yukle = {"zh": lotm.bolumler_zh, "en": lotm.bolumler_en, "tr": lotm.bolumler_tr}
    k = lotm.bolum_sozlugu(yukle[a.kaynak]())
    h = lotm.bolum_sozlugu(yukle[a.hedef]())
    ortak = sorted(set(k) & set(h))
    if a.bolum:
        ortak = [a.bolum] if a.bolum in ortak else []
        if not ortak:
            sys.exit(f"{a.bolum}. bölüm iki kaynakta birden yok")

    k_bas = B.KAYNAKLAR[a.kaynak][2]
    h_bas = B.KAYNAKLAR[a.hedef][2]

    supheli = []
    for no in ortak:
        k_par = B.paragraflar(k[no].metin, k_bas)
        h_par = B.paragraflar(h[no].metin, h_bas)
        capalar = (
            set() if a.capasiz else set(_capa.capa_bul(k_par, h_par, _capa_sozlugu))
        )
        gruplar = B.hizala(k_par, h_par, capalar)
        r = bolumu_denetle(
            k_par,
            h_par,
            gruplar,
            a.esik,
            k_dil=a.kaynak,
            h_dil=a.hedef,
            sozluk=_capa_sozlugu,
        )
        r["bolum"] = no
        # Yalnizca GERCEK kayma dizisi olanlar listelenir. Tek tuk replik
        # uyusmazligi normaldir ve tek basina bir sey soylemez; ilk surum
        # bunlari da listeleyip 42 bolumun 38'ini "supheli" gosteriyordu.
        if r["kaymalar"] or r["yer_degistirme"]:
            supheli.append(r)

        if a.bolum:
            print(
                f"bölüm {no}: {r['grup']} grup "
                f"({r['kaynak_par']} ZH / {r['hedef_par']} TR), "
                f"{r['coklu']} bölünme, {r['tek_tarafli']} tek taraflı"
            )
            for i, (z, u, y) in enumerate(r["artiklar"], 1):
                if u or y or (z is not None and z > a.esik):
                    isaret = []
                    if y:
                        ad = ", ".join(
                            f"{zh}/{tr} {yon}"
                            for zh, tr, yon in r["yer_degistirme"][i - 1]
                        )
                        isaret.append(f"ÇAPA {ad}")
                    if u:
                        isaret.append("REPLİK")
                    if z is not None and z > a.esik:
                        isaret.append(f"z={z:.1f}")
                    print(f"   ¶{i:<4} " + "  ".join(isaret))
            for bas, son in r["kaymalar"]:
                print(f"  ⚠ ¶{bas + 1}–¶{son + 1} arası kayma ({son - bas + 1} grup)")
            return 0

    if not supheli:
        print("kayma bulunamadı.")
        return 0

    print(
        f"\n{'bölüm':>6}{'grup':>7}{'kayan':>7}{'oran':>7}{'replik':>8}"
        f"{'çapa':>6}{'kesin':>7}  aralıklar"
    )
    print("─" * 72)
    for r in sorted(supheli, key=lambda x: -x["kayan_grup"] / max(1, x["grup"])):
        aralik = ", ".join(f"¶{a_ + 1}–{b + 1}" for a_, b in r["kaymalar"])
        pay = r["kayan_grup"] / max(1, r["grup"])
        print(
            f"{r['bolum']:>6}{r['grup']:>7}{r['kayan_grup']:>7}"
            f"{pay:>7.0%}{r['uyusmazlik']:>8}"
            f"{len(r['yer_degistirme']):>6}{r['kesin']:>7}  {aralik[:30]}"
        )
    print(
        f"\n{len(supheli)} bölümde şüphe var. "
        f"Bu bölümlerin EŞLEŞMEYEN sonuçlarına güvenmeyin."
    )
    return 1


# ------------------------------------------------------------------ test


def kendini_dene() -> int:
    """Sentetik hizalamalarla; depo gerektirmez."""

    def par(n, uzun=60, replik=None):
        out = []
        for i in range(n):
            g = (
                '"bu bir replik cümlesidir efendim" '
                if (replik and i in replik)
                else "anlatı "
            )
            out.append(g + "x" * uzun)
        return out

    def bire_bir(n):
        return [([i], [i]) for i in range(n)]

    basarisiz = 0

    # 1) temiz hizalama -> kayma yok
    k = par(20)
    h = par(20)
    r = bolumu_denetle(k, h, bire_bir(20))
    if r["kaymalar"]:
        print("HATA: temiz hizalamada kayma bulundu")
        basarisiz += 1

    # 2) tek bir gercek birlesme -> kayma SAYILMAZ (dizi cok kisa)
    k = par(20)
    h = par(20)
    h[7] = "anlatı " + "x" * 130
    r = bolumu_denetle(k, h, bire_bir(20))
    if r["kaymalar"]:
        print("HATA: tek sapma kayma sayıldı")
        basarisiz += 1

    # 3) 8. paragraftan sonra replik kayması -> yakalanmali
    k = par(20, replik={8, 10, 12, 14, 16})
    h = par(20, replik={9, 11, 13, 15, 17})
    r = bolumu_denetle(k, h, bire_bir(20), k_dil="tr", h_dil="tr")
    if not r["kaymalar"]:
        print("HATA: replik kayması yakalanmadı")
        basarisiz += 1

    # 4) uzun bir uzunluk sapmasi dizisi -> yakalanmali
    k = par(20)
    h = par(20)
    for i in range(8, 15):
        h[i] = "anlatı " + "x" * 200
    r = bolumu_denetle(k, h, bire_bir(20))
    if not r["kaymalar"]:
        print("HATA: uzunluk kayması yakalanmadı")
        basarisiz += 1

    # 5) Bolum 4 sekli: sayilar TUTUYOR ama icerik kaymis
    k = par(12, replik={4, 6, 8, 10})
    h = par(12, replik={5, 7, 9, 11})
    r = bolumu_denetle(k, h, bire_bir(12), k_dil="tr", h_dil="tr")
    if r["kaynak_par"] != r["hedef_par"]:
        print("HATA: test kurulumu bozuk")
        basarisiz += 1
    if not r["kaymalar"]:
        print("HATA: eşit sayıda paragrafla kayma yakalanmadı")
        basarisiz += 1

    # 6) CAPA YER DEGISTIRME. Ad ¶5'te yalniz kaynakta, ¶6'da yalniz
    #    hedefte -- kaybolmamis, kaymis. Uzunluklar ve replikler kasten
    #    temiz: diger iki sinyal susarken bunun konusmasi gerekir.
    k = par(12)
    h = par(12)
    k[5] = "anlatı 克莱恩 " + "x" * 50
    h[6] = "anlatı Klein " + "x" * 50
    r = bolumu_denetle(k, h, bire_bir(12), sozluk={"克莱恩": "Klein"})
    if 5 not in r["yer_degistirme"]:
        print("HATA: çapa yer değiştirmesi yakalanmadı")
        basarisiz += 1
    elif r["yer_degistirme"][5][0][2] != "hedef geride":
        print("HATA: kayma yönü yanlış")
        basarisiz += 1

    # 7) Ad IKI tarafta da ayni grupta -> yer degistirme YOK.
    k = par(12)
    h = par(12)
    k[5] = "anlatı 克莱恩 " + "x" * 50
    h[5] = "anlatı Klein " + "x" * 50
    r = bolumu_denetle(k, h, bire_bir(12), sozluk={"克莱恩": "Klein"})
    if r["yer_degistirme"]:
        print("HATA: hizalı çapa yer değiştirme sayıldı")
        basarisiz += 1

    # 8b) YON CELISKISI. Ad ZH-yalniz {4,6}, TR-yalniz {5,7} -> her bosluk
    #     bir cift uretir, yonler karisir. Hicbiri bildirilmemeli.
    k = par(12)
    h = par(12)
    for i in (4, 6):
        k[i] = "anlatı 克莱恩 " + "x" * 50
    for i in (5, 7):
        h[i] = "anlatı Klein " + "x" * 50
    r = bolumu_denetle(k, h, bire_bir(12), sozluk={"克莱恩": "Klein"})
    if r["yer_degistirme"]:
        print("HATA: yön çelişkili çapa elenmedi")
        basarisiz += 1

    # 9) Sozluk verilmezse davranis eskisiyle birebir ayni kalmali.
    r = bolumu_denetle(par(12), par(12), bire_bir(12))
    if r["yer_degistirme"] or r["kaymalar"]:
        print("HATA: sözlüksüz çağrı davranışı değişti")
        basarisiz += 1

    print("kendini-dene:", "geçti" if not basarisiz else f"{basarisiz} HATA")
    return 1 if basarisiz else 0


if __name__ == "__main__":
    sys.exit(ana())
