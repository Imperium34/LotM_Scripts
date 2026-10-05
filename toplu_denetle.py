#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
toplu_denetle.py -- ceviri_denetle.py'yi sozlugun TAMAMI icin calistirir.

UST DUZEY SORU: "Hangi terimlerde yayimlanan metin sozlukten sapiyor?"

ceviri_denetle.py tek terim sorar; bu betik ayni soruyu 381 terime birden
sorar ve sonucu ESLESMEME ORANINA gore siralar. Listenin basi
'eski_karsiliklar' geri doldurma sirasidir: kaydi tutulmamis bir karsilik
kullandiginiz yerler.

NEDEN DONGU TERS CEVRILDI
-------------------------
ceviri_denetle.tara() her cagrida (a) butun bolumleri diskten okur,
(b) her bolumu paragraflara boler, (c) Gale-Church hizalamasini yeniden
kurar. Hizalama O(n*m) dinamik programlama; 42 bolum icin kabul edilebilir,
381 terim x 42 bolum icin degil.

Oysa hizalama TERIMDEN BAGIMSIZDIR. Ayni bolum cifti hangi terim icin
hizalanirsa hizalansin ayni sonucu verir. Bu yuzden burada dongu ters:

    her bolum icin BIR KEZ hizala  ->  butun terimleri o hizalamaya sor

42 hizalama, 381*42 degil. Terim basina kalan is yalnizca bir regex
taramasi, ki o da once ham bolum metninde ucuz bir on elemeden geciyor.

Kullanim:
    toplu_denetle.py                        EN -> TR, butun sozluk
    toplu_denetle.py --kaynak zh            Cinceden (yalnizca cince'si olanlar)
    toplu_denetle.py --bolum 1-42
    toplu_denetle.py --en-az 3              3'ten az gecisi olanlari atla
    toplu_denetle.py --format tsv > kuyruk.tsv
    toplu_denetle.py --ayrinti "Aşkın"      tek terimin eslesmeyenlerini yaz
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict

import lotm
import bolum as B
import ceviri_denetle as CD
import hizalama_denetle as HD
import capa as _capa

_CAPA_SOZLUGU = _capa.sozluk_yukle()


# --------------------------------------------------------------- hizalama


def hizalama_onbellegi(kaynak: str, hedef: str, aralik):
    """
    Ortak bolumleri BIR KEZ hizalar.

    Doner: {bolum_no: (k_ham, k_par, h_par, nereye)}
      k_ham   ham kaynak metin -- terim basina ucuz on eleme icin
      nereye  {kaynak paragraf indisi: [hedef paragraf indisleri]}
      kayan   hizalamanin kaydigi kaynak paragraf indisleri

    KAYAN NEDEN GEREKLI: hizalama kaydiginda ESLESMEYEN listesi sessizce
    curur -- terim kaynakta var, karsilik hedefte var, ama ikisi ayni gruba
    dusmedigi icin "eslesmedi" gorunur ve bir ceviri hatasindan ayirt
    edilemez. Turkce'nin paragraf teamulu Cince'ninkinden farkli (anlati ile
    ardindan gelen replik cogu zaman tek paragrafta birlesiyor) ve BU TEAMUL
    KENDI ICINDE DE TUTARLI DEGIL: Bolum 16 birlestiriyor, Bolum 40
    birlestirmiyor. Yani kaynaga bakan hicbir kural bunu onceden bilemez ve
    hizalayici kimi yerde kacinilmaz olarak kayacaktir.
    Cozum kaymayi ortadan kaldirmak degil, KARANTINAYA ALMAK.
    """
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
        sys.exit("kaynak ve hedefte ortak bolum yok")

    k_baslik = B.KAYNAKLAR[kaynak][2]
    h_baslik = B.KAYNAKLAR[hedef][2]

    onbellek = {}
    for i, no in enumerate(ortak, 1):
        print(f"\rhizalaniyor: {i}/{len(ortak)} (bolum {no})", end="", file=sys.stderr)
        k_ham = k_bolumler[no].metin
        k_par = B.paragraflar(k_ham, k_baslik)
        h_par = B.paragraflar(h_bolumler[no].metin, h_baslik)
        capalar = set(_capa.capa_bul(k_par, h_par, _CAPA_SOZLUGU))
        gruplar = B.hizala(k_par, h_par, capalar)
        nereye, grup_no = {}, {}
        for g, (ia, ib) in enumerate(gruplar):
            for j in ia:
                nereye[j] = ib
                grup_no[j] = g

        rapor = HD.bolumu_denetle(k_par, h_par, gruplar, k_dil=kaynak, h_dil=hedef)
        supheli_gruplar = {
            g for bas, son in rapor["kaymalar"] for g in range(bas, son + 1)
        }
        kayan = {j for j, g in grup_no.items() if g in supheli_gruplar}

        onbellek[no] = (k_ham, k_par, h_par, nereye, kayan)
    print(
        f"\r{len(ortak)} bolum hizalandi ({ortak[0]}-{ortak[-1]}).{' ' * 20}",
        file=sys.stderr,
    )
    return onbellek


# --------------------------------------------------------------- terimler


def harf_duyarli_mi(t) -> bool:
    """
    Harf duyarliligi TERIM BASINA, kategoriye gore belirlenir.

    Iki hata tipi ayni eksende oturuyor ve tek bir kuresel bayrakla ikisi
    birden cozulmuyor:

      DUYARLI olursa -> kavram terimleri kacar. LotM'un Ingilizcesi
          "mysticism" ve "ritual" gibi kavramlari cogu yerde KUCUK harfle
          yaziyor; sozlukte ise "Mysticism" olarak duruyorlar. Duyarli
          arama bunlari hic bulamaz ve terim taramada YOK gorunur --
          gorunmeyen bir yanlis negatif.

      DUYARSIZ olursa -> Mertebe adlari gurultuye bogulur. Mertebe adlari
          ozel isimdir ve Ingilizcede daima buyuk harfle yazilir, ama
          karsiliklari gunluk kelimelerdir: Judge, Reader, Criminal,
          Demon, Mother, Death. Duyarsiz arama metindeki her "judge"i,
          her "mother"i vurus sayar; "Şeytan / Demon" 1 gecisten 10
          gecise cikar ve dokuzu curuktur.

    Ayrim kategoride: yalnizca 'Temel Kavramlar' ortak isimlerden olusur
    (mysticism, ritual, potion, sequence, divination). Diger her kategori --
    Mertebeler, Ilahlar, Organizasyonlar, Cografya -- ozel isimdir ve
    Ingilizcede daima buyuk harfle yazilir. Ilk surumde olcut 'bool(t.yol)'
    idi, yani yalnizca mertebeler duyarliydi; bu, adi ayni zamanda ortak
    isim olan ILAHLARI acikta biraktigi icin "Ölüm / Death" metindeki her
    "death"i vurus sayiyordu.
    """
    return t.kategori != "Temel Kavramlar"


def sweep_terimleri(kaynak: str, hedef: str, en_kisa: int = 4, kelimeler: str = "dahil"):
    """
    Sozlukten (sorgu, terim, adaylar, duyarli) uretir.

    ceviri_denetle.sozlukten_adaylar() serbest metinle arama yapar; burada
    kayda ZATEN sahibiz, o yuzden dogrudan alanlari kullaniyoruz. Aday
    listesi guncel karsilik + eski_karsiliklar'dir: birincisi "hâlâ
    kullaniliyor mu", ikincisi "geride kaldi mi" sorusunu yanitlar.
    arama_adi verilmisse karsilik olarak O kullanilir -- cok kelimeli ve
    fiilimsi terimlerde ("Şirazesini Yitirmek") degismeyen sey ifadenin
    kendisi degil govdedir ("şiraze").
    """
    # kelimeler: "dahil" (sozluk + words.md), "haric" (yalniz sozluk),
    # "yalniz" (yalniz words.md). words.md maddeleri lotm.kelimeler_yukle'den
    # gelir; kategorileri "words.md › ..." ile baslar.
    sozluk = lotm.sozluk_yukle(kelimeler=(kelimeler != "haric"))
    cikti, atlanan, tekrar = [], 0, set()
    for t in sozluk.terimler:
        kelime_mi = t.kategori.startswith(lotm.KELIME_KATEGORI)
        if kelimeler == "yalniz" and not kelime_mi:
            continue
        sorgu = {"en": t.en, "zh": t.zh, "tr": t.tr}.get(kaynak)
        # Tek karakterlik Cince anahtar aranamaz: 法 (Kanun) 魔法'in, 令
        # (Ferman) 命令'in, 组 (Beşinci Birim'in ikinci bicimi) her "grup"un
        # icinde gecer; Kanun 146 gecisin 130'unu eslesmeyen gosteriyordu.
        # Bu parcalar atilir; hic parca kalmazsa terim atlananlara sayilir.
        # Kose parantezle yazilmis tek karakter (「镑」) kasitlidir, kalir.
        if kaynak == "zh" and sorgu:
            sorgu = "/".join(p for p in sorgu.split("/")
                             if len(p.strip()) > 1 or t.zh_kesin) or None
        # Ingilizce: en_arama_adi verilmisse metinde ARANAN adlar onlardir
        # (bkz. lotm.Terim). Eskiden yalnizca etiket aranirdi; "Heart and
        # Mind Body" metinde hic gecmedigi icin Dimağ Beden tabloda hic
        # gorunmuyordu. Birden cok ad " / " ile birlestirilir; terimi_tara
        # ayirip her birini arar (etiketin kendisindeki "/" gibi).
        if kaynak == "en" and t.en_arama_adi:
            sorgu = " / ".join(a.strip() for a in t.en_arama_adi if a and a.strip())
        if not sorgu or len(sorgu.strip()) < (1 if kaynak == "zh" else en_kisa):
            atlanan += 1
            continue
        sorgu = sorgu.strip()

        # Tarot Cemiyeti'nde 'terim' kod adi, 'ingilizce' ise uyenin gercek
        # adidir (Yıldız / Leonard Mitchell). Bu yonde taranamaz: Turkce
        # metin de "Leonard Mitchell" diyor, dolayisiyla %100 eslesmeme
        # cikar ve bu bir ceviri hatasi degildir.
        if (
            kaynak == "en"
            and hedef == "tr"
            and t.kategori == "Tarot Cemiyeti"
            and lotm.tr_kucult(sorgu) not in lotm.tr_kucult(t.tr)
        ):
            atlanan += 1
            continue

        anahtar = (t.tr, sorgu)
        if anahtar in tekrar:  # sozlukteki birebir tekrar kayitlar
            continue
        tekrar.add(anahtar)

        if hedef == "tr":
            # GUNCEL ve ESKI karsiliklar ayri tutulur. arama_adi ayni
            # karsiligin cekim varyantlaridir ("gökkubbe", "yıldızlı
            # gökkubbe"), eski_karsiliklar ise BASKA bir kelimedir
            # ("ritüel" -> "ayin"). Ikisi tek listede toplanirsa
            # "birden fazla karsilik var" uyarisi, terkedilmis bir
            # karsilik ile ayni kelimenin iki yazilisini ayirt edemez.
            guncel = t.tr_bicimleri()
            eski = list(t.eski_karsiliklar or [])
            adaylar = guncel + eski
        elif hedef == "en":
            adaylar = [t.en] if t.en else []
        else:
            adaylar = [t.zh] if t.zh else []
        adaylar = list(dict.fromkeys(a for a in adaylar if a))
        if adaylar:
            cikti.append(
                (
                    sorgu,
                    t,
                    adaylar,
                    harf_duyarli_mi(t),
                    set(eski) if hedef == "tr" else set(),
                )
            )
    return cikti, atlanan


# --------------------------------------------------------------- tarama


def kaynak_deseni(sorgu, kaynak, duyarsiz):
    """
    Terimin kaynak dildeki arama deseni. terimi_tara ile Cince bilesik
    ipucu (bkz. ceviri_denetle.zh_bilesik_ipuclari) AYNI deseni kullanmali;
    ipucu desenin bulmadigi bir gecise bakarsa sozlukte zaten kayitli
    bilesikleri de "eksik" diye raporlar.
    """
    if kaynak in ("en", "zh"):
        # "A / B" -> A veya B. words.md'nin Cince alani da boyle gelebilir
        # ("印章/盖章"). Hem en_arama_adi listesi hem etiketin kendi
        # "/" alternatifleri ("Historical Void / Fog of History"); eskiden
        # butun dize tek parca aranip hic bulunmuyordu.
        #
        # desen_kur_kaynak EN icin "sorgu.islower()" ise kendiliginden
        # IGNORECASE aciyor. Duyarli istedigimizde bunu geri almak gerekiyor,
        # aksi hâlde kucuk harfli bir Mertebe adi sessizce duyarsiz taraniyor;
        # bayrak bu yuzden tek tek desenlerden degil duyarsiz'dan gelir.
        parcalar = [p.strip() for p in sorgu.split("/") if p.strip()]
        return re.compile(
            "|".join(f"(?:{CD.desen_kur_kaynak(p, kaynak, duyarsiz).pattern})" for p in parcalar),
            re.IGNORECASE if duyarsiz else 0,
        )
    return CD.desen_kur_kaynak(sorgu, kaynak, duyarsiz)


def terimi_tara(sorgu, adaylar, onbellek, kaynak, hedef, duyarsiz, desen=None):
    """Tek terim, onceden hizalanmis bolumler uzerinde. tara()'nin ucuzu."""
    desen = desen or kaynak_deseni(sorgu, kaynak, duyarsiz)
    vuruslar = []
    for no, (k_ham, k_par, h_par, nereye, kayan) in onbellek.items():
        if not desen.search(k_ham):  # on eleme: bolumlerin cogu eler
            continue
        for i, p in enumerate(k_par):
            if not desen.search(p):
                continue
            # Kayit ceviri_denetle.vurus_kur ile kurulur (sema tek yerde).
            #
            # KOMSU PENCERESI. Turkce paragraf yapisi bilerek Cince'den
            # farkli kuruluyor (okur icin bolme/birlestirme); hizalama her
            # zaman kusursuz olamaz ve karsilik cogu zaman hemen yandaki
            # paragrafta durur. Hedef bu yuzden +-1 Turkce paragrafla
            # genisletilir, ama DAR ve GENIS ayri tutulur: yalnizca komsuda
            # bulunan bir karsilik "eslesti" sayilmaz, 'komsu' kovasina
            # duser (bkz. ozetle). Yanlis bir karsiligi komsudaki dogru bir
            # gecisin arkasina saklamamak icin.
            ib = list(nereye.get(i, []))
            komsu = []
            if ib:
                komsu = [j for j in (min(ib) - 1, max(ib) + 1)
                         if 0 <= j < len(h_par) and j not in ib]
            vuruslar.append(
                CD.vurus_kur(no, p, h_par, ib + komsu, ib_dar=ib,
                             genis="komsu" if komsu else None, kayan=i in kayan)
            )
    if vuruslar:
        CD.siniflandir(vuruslar, adaylar, hedef, kesif=False)
    return vuruslar


def ozetle(vuruslar):
    """
    Dort kova:
      eslesti     karsilik hizalanan Turkce paragrafta
      komsu       hizalanan paragrafta YOK, hemen yandakinde VAR. Buyuk
                  olasilikla paragraf yapisi farki; ama komsudaki gecis
                  baska bir cumleye de ait olabilir, bu yuzden eslesti
                  sayilmaz ve ayri listelenir. Orana girmez.
      karantina   hizalamasi kaymis bolgede ve komsuda da yok. Hakkinda
                  hicbir sey soylenemez -- ne dogru ne yanlis.
      eslesmeyen  saglam bolgede, ne hizalanan paragrafta ne komsusunda.
                  Gercek bulgu.
    Hicbir kovaya girmeyen: tek tarafli (kaynak paragrafin hedefi yok).

    Doner: (sayim, eslesmeyen, karantina, tek_tarafli, komsu)
    """
    sayim = defaultdict(int)
    eslesmeyen, karantina, komsu, tek_tarafli = [], [], [], 0
    for v in vuruslar:
        if v["tip"] == "tek_tarafli":
            tek_tarafli += 1
        elif v["bulunan_dar"]:
            for ad in v["bulunan_dar"]:
                sayim[ad] += 1
        elif v["bulunan"]:
            komsu.append(v)
            for ad in v["bulunan"]:
                sayim[ad] += 1
        elif v.get("kayan"):
            karantina.append(v)
        else:
            eslesmeyen.append(v)
    return dict(sayim), eslesmeyen, karantina, tek_tarafli, komsu


# --------------------------------------------------------------- cikti


def _ad(k) -> str:
    """Tablodaki ad; words.md maddeleri '·' ile baslar."""
    kelime = str(k.get("kategori", "")).startswith(lotm.KELIME_KATEGORI)
    return ("·" if kelime else "") + k["terim"]


def satir_yaz(kayitlar, genislik=100):
    print(f"\n{'─' * genislik}")
    print(
        f"{'terim':<28}{'geçiş':>6}{'eşleşmeyen':>12}{'oran':>7}{'krntn':>7}{'komşu':>7}  karşılıklar"
    )
    print("─" * genislik)
    for k in kayitlar:
        # Terk edilmis karsilik varsa ONCE o yazilir ve basina isaret konur.
        # Eskiden isaret dizenin SONUNA ekleniyordu ve satir kirpilinca ilk
        # kaybolan oydu: komsu sutunu eklenince "İlm-i Esrar" satirinda
        # "mistisizm"den sonraki "⚠ eski" artik gorunmuyordu.
        eski = k.get("eski_gorulen") or set()
        sirali = sorted(k["sayim"].items(), key=lambda kv: (kv[0] not in eski, -kv[1]))
        kars = ("⚠ " if eski else "") + ", ".join(f"{a}×{n}" for a, n in sirali[:3])
        # 'krntn' basligi vardi ama degeri hic yazilmiyordu; karsiliklar bir
        # sutun sola kayip krntn'in altina dusuyordu.
        print(
            f"{_ad(k)[:27]:<28}{k['toplam']:>6}{len(k['eslesmeyen']):>12}"
            f"{k['oran']:>7.0%}{len(k.get('karantina', [])):>7}"
            f"{len(k.get('komsu', [])):>7}  {kars[: genislik - 69]}"
        )


def ayrinti_yaz(kayit, ust=15, arka_plan=None, elenen=None):
    yer = f"   [{kayit['kategori']}]" if str(kayit.get("kategori", "")).startswith(lotm.KELIME_KATEGORI) else ""
    print(f"\n{'═' * 72}\n{kayit['terim']}  ←  {kayit['sorgu']}{yer}\n{'═' * 72}")
    print(
        f"{kayit['toplam']} geçiş, {len(kayit['eslesmeyen'])} eşleşmeyen, "
        f"{len(kayit['karantina'])} karantina (hizalama kaymış), "
        f"{len(kayit.get('komsu', []))} komşuda, "
        f"{kayit['tek_tarafli']} hizalanamayan"
    )
    CD.zh_elenen_yaz(elenen)
    if kayit["sayim"]:
        for a, n in sorted(kayit["sayim"].items(), key=lambda kv: -kv[1]):
            print(f"  {a}: {n}")
    # Eslesmeyende DAR metin gosterilir: hizalanan paragraf. Komsular
    # zaten aranmis ve orada da yok.
    desen = kayit.get("desen")
    zh_mi = kayit.get("kaynak") == "zh" and desen is not None
    for v in kayit["eslesmeyen"][:ust]:
        ozet = re.sub(r"\s+", " ", v["hedef_metin_dar"])[:110]
        # Cince pencere: ayni dizi (占卜家) tekrar ediyorsa eslesmeme buyuk
        # olasilikla sozlukte eksik bir bilesikten gelir, ceviriden degil.
        pen = f"〔{CD.zh_pencere(v['kaynak_metin'], desen)}〕 " if zh_mi else ""
        print(f"  [bölüm {v['bolum']}] {pen}{ozet or '(hedef paragraf boş)'}")
    if len(kayit["eslesmeyen"]) > ust:
        print(f"  ... {len(kayit['eslesmeyen']) - ust} tane daha")
    if zh_mi and kayit["eslesmeyen"]:
        CD.zh_bilesik_yaz(CD.zh_bilesik_raporu(kayit["eslesmeyen"], desen, arka_plan,
                                               dil=kayit.get("hedef", "tr")))
    if kayit.get("komsu"):
        print("  komşuda bulunanlar (paragraf yapısı farkı mı, başka cümle mi?):")
        for v in kayit["komsu"][:ust]:
            ozet = re.sub(r"\s+", " ", v["hedef_metin_dar"])[:70] or "(boş)"
            print(f"  [bölüm {v['bolum']}] {', '.join(v['bulunan'])}  <- hizalanan: {ozet}")


def bilesik_ipucu_yaz(kayitlar, en_az=3, pay=0.25):
    """
    Tablo sonrasi: eslesmeyenleri sozlukte KAYITLI OLMAYAN bir Cince
    bilesikte yogunlasan terimler. Bunlar ceviri hatasi degil sozluk
    eksigi olabilir; once bakilmalari gerekir, cunku oranlari yanilticidir
    (kehanet <- 占卜: 39 eslesmeyenin cogu dogru cevrilmis 占卜家 / 占卜师).

    Esik: en cok gecen dizi en az 'en_az' eslesmeyende VE eslesmeyenlerin
    en az 'pay' kadarinda. Hedef metinde kesif yapilmaz (her terim icin
    pahali); ayrinti icin --ayrinti.
    """
    satirlar = []
    for k in kayitlar:
        if k.get("kaynak") != "zh" or not k["eslesmeyen"] or k.get("desen") is None:
            continue
        ipuclari = CD.zh_bilesik_ipuclari(k["eslesmeyen"], k["desen"], en_az=en_az)[:3]
        if not ipuclari or ipuclari[0][1] < pay * len(k["eslesmeyen"]):
            continue
        kapsanan = {id(v) for _d, _n, vs in ipuclari for v in vs}
        satirlar.append((k, ipuclari, len(kapsanan)))
    if not satirlar:
        return
    print("\nEşleşmeyenleri sözlükte kayıtlı olmayan bir Çince bileşikte yoğunlaşan terimler")
    print("(oranları yanıltıcı olabilir; ayrıntı için --ayrinti \"<terim>\"):")
    for k, ipuclari, kapsanan in sorted(satirlar, key=lambda s: -s[2]):
        dokum = ", ".join(f"{d}×{n}" for d, n, _vs in ipuclari)
        print(f"  {_ad(k)} ← {k['sorgu']}: {dokum}  "
              f"({len(k['eslesmeyen'])} eşleşmeyenin {kapsanan}'i)")


def tsv_yaz(kayitlar):
    print("terim\tsorgu\ttoplam\teslesmeyen\toran\ttek_tarafli\tkomsu\tkarsiliklar")
    for k in kayitlar:
        kars = "|".join(f"{a}:{n}" for a, n in k["sayim"].items())
        print(
            f"{k['terim']}\t{k['sorgu']}\t{k['toplam']}\t"
            f"{len(k['eslesmeyen'])}\t{k['oran']:.3f}\t{k['tek_tarafli']}\t"
            f"{len(k.get('komsu', []))}\t{kars}"
        )


# --------------------------------------------------------------- ana


def kesin_gecisler(yol=None) -> dict:
    """lotm.kesin_gecisler (lint ve yayim_denetle ile ayni okuma)."""
    return lotm.kesin_gecisler(yol)


def eski_ozeti(vuruslar, sayim, eski, gecis=None):
    """
    (eski_gorulen, eski_sayim). Kesin gecis varsa yalnizca gecis
    bolumunden itibaren bulunan eski bicimler sayilir.
    """
    if not gecis:
        g = {a for a in sayim if a in eski}
        return g, {a: sayim[a] for a in g}
    kesit = gecis[0]
    sonra = defaultdict(int)
    for v in vuruslar:
        if v.get("bolum") is not None and v["bolum"] >= kesit:
            for ad in (v.get("bulunan_dar") or v.get("bulunan") or []):
                if ad in eski:
                    sonra[ad] += 1
    return set(sonra), dict(sonra)


def isleri_kur(kaynak: str, hedef: str, kelimeler: str = "dahil"):
    """
    Taranacak terimler: [(kaynak, sorgu, terim, adaylar, duyarli, eski)].

    kaynak "ikisi" ise her terim EN IYI anahtariyla taranir: Cincesi
    (tek karakterlik parcalar atildiktan sonra) varsa Cince, yoksa
    Ingilizce. Cince anahtar kesindir; Ingilizce yalnizca Cincesi
    girilmemis terimler icin devreye girer. Boylece zincir tek bir
    tablo uretir, ayni terim iki kez gorunmez.

    Doner: (isler, atlanan) -- atlanan, hicbir anahtarla taranamayanlar.
    """
    if kaynak != "ikisi":
        liste, atlanan = sweep_terimleri(kaynak, hedef, kelimeler=kelimeler)
        return [(kaynak, *x) for x in liste], atlanan
    zh, _ = sweep_terimleri("zh", hedef, kelimeler=kelimeler)
    en, _ = sweep_terimleri("en", hedef, kelimeler=kelimeler)
    zh_anahtar = {(t.tr, t.kategori) for _s, t, *_ in zh}
    en_kalan = [x for x in en if (x[1].tr, x[1].kategori) not in zh_anahtar]
    # Hic taranamayan: ne Cince ne Ingilizce anahtari olan. Ayni filtreyle
    # sozlugu bir kez daha sayariz; sweep'in kendi "atlanan"i tek dil icindir.
    taranan = zh_anahtar | {(t.tr, t.kategori) for _s, t, *_ in en_kalan}
    tum = {(t.tr, t.kategori) for t in lotm.sozluk_yukle(kelimeler=(kelimeler != "haric")).terimler
           if kelimeler != "yalniz" or t.kategori.startswith(lotm.KELIME_KATEGORI)}
    isler = [("zh", *x) for x in zh] + [("en", *x) for x in en_kalan]
    return _tekillestir(isler), len(tum - taranan)


def _tekillestir(isler: list) -> list:
    """
    Ayni Turkce terim hem sozlukte hem words.md'de varsa tabloda iki kez
    cikiyordu ("Asılmış Adam" sozlukten Ingilizceyle, "·Asılmış Adam"
    words.md'den Cinceyle). Terim basina TEK satir kalir: Cince anahtarla
    taranan once gelir (kesin), esitlikte sozluk words.md'ye tercih edilir.
    """
    def oncelik(is_):
        kaynak, _s, t, *_ = is_
        return (kaynak != "zh", t.kategori.startswith(lotm.KELIME_KATEGORI))
    secilen = {}
    for is_ in sorted(isler, key=oncelik):
        secilen.setdefault(lotm.tr_kucult(is_[2].tr), is_)
    return [is_ for is_ in isler if secilen[lotm.tr_kucult(is_[2].tr)] is is_]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sozlugun tamamini yayimlanmis metne karsi tarar."
    )
    ap.add_argument(
        "--kaynak", choices=("zh", "en", "ikisi"), default="en",
        help="ikisi: Cincesi olan terim Cince, olmayan Ingilizce anahtarla (zincir bunu kullanir)",
    )
    ap.add_argument("--hedef", choices=("tr", "en", "zh"), default="tr")
    ap.add_argument("--bolum", default=None, help="'1-200' ya da '279'")
    ap.add_argument(
        "--en-az",
        type=int,
        default=1,
        dest="en_az",
        help="bu sayidan az gecisi olan terimleri atla",
    )
    ap.add_argument(
        "--harf-duyarsiz",
        action="store_true",
        dest="duyarsiz",
        help="kategori kararını ezip her terimi duyarsız tara",
    )
    ap.add_argument(
        "--ayrinti", default=None, help="tek terimin eslesmeyenlerini ayrintili yaz"
    )
    ap.add_argument(
        "--kelimeler", choices=("dahil", "haric", "yalniz"), default="dahil",
        help="words.md maddeleri: dahil (varsayilan), haric, ya da yalniz onlar",
    )
    ap.add_argument("--format", choices=("tablo", "tsv"), default="tablo")
    ap.add_argument("--kurallar", default=None,
                    help="lint-kurallari.yml (kesin_gecis icin); varsayilan: lint/ altinda")
    ap.add_argument("--genislik", type=int, default=None)
    a = ap.parse_args()

    import shutil

    genislik = a.genislik or shutil.get_terminal_size((100, 40)).columns

    if a.kaynak == a.hedef:
        sys.exit("kaynak ve hedef ayni olamaz")

    terimler, atlanan = isleri_kur(a.kaynak, a.hedef, a.kelimeler)
    kullanilan = sorted({k for k, *_ in terimler})
    onbellekler = {k: hizalama_onbellegi(k, a.hedef, CD.bolum_araligi(a.bolum))
                   for k in kullanilan}
    dokum = ", ".join(f"{sum(1 for k, *_ in terimler if k == x)} {x}" for x in kullanilan)
    print(
        f"{len(terimler)} terim taranacak ({dokum})"
        f"{f'; {atlanan} tanesi anahtarı olmadığı için atlandı' if atlanan else ''}",
        file=sys.stderr,
    )

    gecisler = kesin_gecisler(a.kurallar)
    kayitlar = []
    for i, (kaynak, sorgu, t, adaylar, duyarli, eski) in enumerate(terimler, 1):
        print(f"\rtaraniyor: {i}/{len(terimler)}", end="", file=sys.stderr)
        # --harf-duyarsiz kuresel olarak zorlar; verilmezse karar kategoriye
        # birakilir (bkz. harf_duyarli_mi).
        duyarsiz = a.duyarsiz or not duyarli
        desen = kaynak_deseni(sorgu, kaynak, duyarsiz)
        vuruslar = terimi_tara(sorgu, adaylar, onbellekler[kaynak], kaynak, a.hedef, duyarsiz,
                               desen=desen)
        if len(vuruslar) < a.en_az:
            continue
        sayim, eslesmeyen, karantina, tek, komsu = ozetle(vuruslar)
        eski_g, eski_s = eski_ozeti(vuruslar, sayim, eski,
                                    gecisler.get(lotm.tr_kucult(t.tr)) if a.hedef == "tr" else None)
        kayitlar.append(
            {
                "terim": t.tr,
                "sorgu": sorgu,
                "kaynak": kaynak,
                "hedef": a.hedef,
                "desen": desen,
                "kategori": t.kategori,
                "eski_gorulen": eski_g,
                "eski_sayim": eski_s,
                "toplam": len(vuruslar),
                "sayim": sayim,
                "eslesmeyen": eslesmeyen,
                "karantina": karantina,
                "komsu": komsu,
                "tek_tarafli": tek,
                # Oran YALNIZCA saglam bolgeler uzerinden. Kaymis bolgelerden
                # gelen eslesmeyenler paydadan da cikarilir, aksi hâlde
                # hizalama hatasi ceviri hatasi gibi gorunur.
                "oran": (
                    len(eslesmeyen) / (len(vuruslar) - len(karantina))
                    if len(vuruslar) - len(karantina) > 0
                    else 0.0
                ),
            }
        )
    print(f"\r{len(kayitlar)} terim metinde geçiyor.{' ' * 20}", file=sys.stderr)

    if a.ayrinti:
        q = lotm.tr_kucult(a.ayrinti)
        bulunan = [k for k in kayitlar if q in lotm.tr_kucult(k["terim"])]
        if not bulunan:
            sys.exit(f"'{a.ayrinti}' taramada geçmiyor")
        for k in bulunan:
            arka, elenen = None, None
            if k["kaynak"] == "zh":
                ob = onbellekler["zh"]
                # Kesif icin arka plan: taranan bolumlerin butun hedef
                # paragraflari (kume paragraflari zh_bilesik_raporu'nda cikarilir).
                arka = [p for _kh, _kp, h_par, _n, _ky in ob.values() for p in h_par]
                elenen = sum((CD.zh_elenenler(p.strip(), [kh for kh, *_ in ob.values()])
                              for p in k["sorgu"].split("/") if p.strip()), Counter())
            ayrinti_yaz(k, arka_plan=arka, elenen=elenen)
        return 0

    kayitlar.sort(key=lambda k: (-k["oran"], -k["toplam"]))
    if a.format == "tsv":
        tsv_yaz(kayitlar)
    else:
        satir_yaz(kayitlar, genislik)
        bilesik_ipucu_yaz(kayitlar)
        temiz = sum(1 for k in kayitlar if not k["eslesmeyen"])
        eskiler = [k for k in kayitlar if k.get("eski_gorulen")]
        print(f"\n{temiz}/{len(kayitlar)} terim tam eşleşti. "
              f"{len(eskiler)} terimde terk edilmiş karşılık hâlâ metinde"
              + (":" if eskiler else "."))
        for k in sorted(eskiler, key=lambda k: -sum(k["eski_sayim"].values())):
            dokum = ", ".join(f"{a}×{k['eski_sayim'][a]}" for a in sorted(k["eski_gorulen"]))
            guncel = sum(n for a, n in k["sayim"].items() if a not in k["eski_gorulen"])
            print(f"  ⚠ {k['terim']}: {dokum}  (güncel karşılık: {guncel})")
        print("Listenin başı: eski_karşılık geri doldurma sırası.")
        if any(_ad(k).startswith("·") for k in kayitlar):
            print("· = words.md maddesi (yalnız onlar için: --kelimeler yalniz)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
