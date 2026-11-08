#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etiketle.py -- sozluk.yml'e kaynak / mudahale / metinde / denetim alanlarini yazar.

Tasarim ilkesi: kurallar tek yerde, elle yazilmis deger yok. Veri degisirse
yeniden calistirilir, diff denetim kaydidir.

  Yukleme ve yazma artik lotm.sozluk_yukle(bicim_koru=True) uzerinden.
  ruamel gerekiyor cunku PyYAML'in safe_dump'i "# ---" bolum basliklarini
  siler, anahtarlari alfabetik siralar ve uzun aciklama/cevirmen_notu
  dizelerini yeniden sarar. Dosya anlamca ayni kalir ama diff okunamaz hale
  gelir, yani neyin degistigini goremezsiniz.

ALT DIZE ("Hunter" / "Demon Hunter") BURADA DEGIL
--------------------------------------------------
Eskiden bir Ingilizce ad baska bir adin icinde geciyorsa o terime hic
ilk_gecis yazilmiyordu (once elle ALT_DIZE_RISKI listesi, sonra sozlukten
turetilen liste). kapi_denetle artik her GECISI ayri ayri sorguluyor ve
daha uzun bir adin icindekileri saymiyor (golge_haritasi); rapordaki
'bolum' zaten bagimsiz ilk gecistir. Terimi toptan dislamak ayni kaygiyi
ikinci kez, daha kaba bicimde uyguluyordu: Beyonder, Spirit Body, God
Almighty gibi ust duzey terimlerin ilk_gecis'i hic yazilmiyordu.

rapor.tsv'nin 'guvenilir_mi' sutunu artik gercekten okunuyor.
kapi_denetle.py terimin metinde kucuk harfle de gectigini tespit ediyordu
(cins isim isareti) ve bu sutunu yaziyordu; etiketle.py sutunu ayristirip
kullanmadan atiyordu. Simdi o terimlere de bolum numarasi yazilmiyor.

Kullanim:
    python3 etiketle.py --sozluk sozluk.yml --rapor rapor.tsv \
        --cikti sozluk_etiketli.yml
    python3 etiketle.py --sozluk sozluk.yml --rapor rapor.tsv --yerinde
"""

import argparse
import re
import sys
from collections import defaultdict

import lotm


# =====================================================================
# KURALLAR -- hepsi burada, baska hicbir yerde deger yok
# =====================================================================

# Tarayici bulmus olsa da metinde GECMEDIGI kabul edilenler.
# Catastrophe: tek eslesme cins isim ("bring catastrophe to others"),
# Mertebe adi degil. Sozlukteki 66 degeri de ayni yanlis pozitiften geliyordu.
METINDE_YOK_ZORLA = {"Catastrophe"}

# Elle belirlenmis kapilar: {Ingilizce ya da Turkce ad: bolum}. Yalnizca
# sozlukte bolum_siniri BOSSA yazilir; doluysa sozluk kazanir ve cikti
# fazlalik/celiski olarak bildirir. Su an bos -- kararlarin hepsi sozlukte.
BOLUM_ELLE = {}

# Tazim ismi denetiminden gelen mudahale degerleri (girdi adina gore).
MUDAHALE = {
    "Ebedî Yanan Güneş": "birlestirme",
    "Kotar": "tamamlama",
    "Hakiki Hâlık / Mütereddi Hâlık": "degistirme",
    "İlksel Şerbânû": "ozgun",
    "İlksel Şerbânû (Tam Tazim İsmi)": "degistirme",
    "İlim ve Hikmetin İlahı": "degistirme",
    "Batınî Bilge": "ozgun",
    "Prangalı İlah": "ozgun",
    "Tahayyül Meleği Âdem (Melekler Beyi)": "ozgun",
    "Zeval Hâkimi": "tamamlama",
    "Nizamın İnhilali": "tamamlama",
}

# Kaynagi LotM metni olmayan girdiler.
KAYNAK_ELLE = {
    "İlksel Şerbânû (Tam Tazim İsmi)": "metin_coi",
    "Halas Meleği Amon": "metin_coi",
    "Halas Meleği Gehrman Sparrow": "metin_coi",
    "Yarı Kadir-i Mutlak Âdem (Âdem ve Hakiki Hâlık'ın birleşimi sonrası)": "metin_coi",
    "Sihirli Ayna Arrodes": "metin_coi",
    "Ebedî Gece Tanrıçası (Sermedi Zulmet)": "yazar_beyani",
    "Mukadderat Halkası": "metin",
    "İstikbal Tanrıçası": "metin",
    "Müphem Sis": "metin",
    "Engizisyon": "metin",
    "Ulûhiyet ve Beşeriyet": "metin",
    "Aşkın Hasletlerin Korunumu Kanunu": "metin",
    "Şirazesini Yitirmek (Şirazeden Çıkmak)": "metin",
    "Yıldızlı Gökkubbe": "metin",
    "Dimağ Beden": "metin",
    "Sterlin, Soli ve Peni": "metin",
    "Kara Kehanet": "metin",
    "Ay saati": "metin",
}

# Book 2 WeChat gonderisinden gelen Tarot Kulubu tazim isimleri.
# Fors'un girdisi hem S1 (yazar_beyani) hem S2 (metin_coi) iceriyor;
# bolunene kadar 'karma'.
TAROT_YAZAR_BEYANI = {
    "Adalet (Justice)",
    "Asılmış Adam (The Hanged Man)",
    "Güneş (The Sun)",
    "Yıldız (The Star)",
    "Ay (The Moon)",
    "Keşiş (The Hermit)",
    "Yargı (Judgment)",
    "İtidal (Temperance)",
}
TAROT_KARMA = {"Hokkabaz (The Magician)"}

TAZIM_KATEGORILERI = {"İlahlar ve Ulu Eskiler", "Tarot Kulübü"}


# =====================================================================


# Bu betigin yazdigi alanlar. DEGISIKLIKLER bolumu bunlarin calismadan
# ONCEKI ve SONRAKI degerlerini karsilastirir; elle tutulan bir liste
# degil. Eskiden degisiklik satirlari kod icinde tek tek ekleniyordu:
# metinde=false her calismada "degisti" diye listeleniyor, kaynak/mudahale/
# denetim degisiklikleri ise hic gorunmuyordu (Ay saati metin ->
# bilinmiyor dususu yalnizca diff'te fark edilebiliyordu).
IZLENEN = ("metinde", "kaynak", "mudahale", "denetim", "ilk_gecis", "bolum_siniri")


def _dugumler(veri):
    """[(etiket, dugum)] -- her ust duzey girdi ve her mertebesi."""
    for girdi in veri:
        ad = girdi.get("terim")
        yield ad, girdi
        for m in girdi.get("mertebeler") or []:
            yield f"{ad} S{m.get('seviye')}: {lotm.parantezsiz(m.get('isim'))}", m


def anlik(veri) -> list:
    return [(etiket, {a: d.get(a) for a in IZLENEN}) for etiket, d in _dugumler(veri)]


def fark(once, sonra) -> list:
    """Iki anlik goruntu arasindaki alan degisiklikleri, okunur satirlar."""
    satirlar = []
    for (etiket, a), (_e, b) in zip(once, sonra):
        for alan in IZLENEN:
            if a[alan] != b[alan]:
                satirlar.append(f"  {alan:<13} {etiket}: {a[alan]} -> {b[alan]}")
    return satirlar


def rapor_oku(yol):
    """rapor.tsv -> {terim: {"guven":..., "bolum": int|None, "guvenilir": bool}}"""
    kayit = {}
    with open(yol, "r", encoding="utf-8") as f:
        basliklar = f.readline().rstrip("\n").split("\t")
        ix = {ad: i for i, ad in enumerate(basliklar)}
        for satir in f:
            p = satir.rstrip("\n").split("\t")
            if len(p) < len(basliklar):
                continue
            terim = p[ix["terim"]]
            bolum = p[ix["bolum"]].strip()
            kayit[terim] = {
                "guven": p[ix["guven"]].strip(),
                "bolum": int(bolum) if bolum.isdigit() else None,
                "guvenilir": (
                    p[ix["guvenilir_mi"]].strip() == "evet"
                    if "guvenilir_mi" in ix
                    else True
                ),
            }
    return kayit


def metinde_mi(eng, rapor):
    if eng in METINDE_YOK_ZORLA:
        return False
    k = rapor.get(eng)
    if k is None:
        return None  # raporda yok; karar verilemez
    return k["guven"] != "yok"


def bosluk_duzelt(metin):
    """
    ruamel, girdiler arasindaki bos satiri o girdinin ESKI son anahtarina
    baglar. Yeni alanlar eklenince bos satir onlarin ustunde kalir ve alanlar
    bir sonraki girdiye aitmis gibi gorunur. Burada bos satir asagi tasinir.
    """
    satirlar = metin.split("\n")

    # mertebeler bloklarini kaynak dosyadaki 4 boslukluk girintiye kaydir.
    # Yapilmazsa diff 220 mertebe satirini "degismis" gosterir ve gercek
    # degisiklikler kaybolur.
    #
    # DIKKAT -- blok yorumla bitmez. ruamel bir yorumu kendinden onceki
    # anahtara baglar. Son mertebeye yeni alan eklendiginde ("metinde",
    # "kaynak") o alanlar yorumdan SONRA yazilir:
    #
    #       bolum_siniri: 90
    #                            <- bos
    #     # --- Kavramlar ---    <- girdiler arasi bolum basligi
    #                            <- bos
    #       metinde: true        <- hâlâ ayni mertebeye ait
    #
    # Eski surum yorumu gorunce blogu kapatiyordu, bu yuzden "metinde" ve
    # "kaynak" kaydirilmadan kaliyor, kardeslerinden iki bosluk geride
    # duruyor ve dosya AYRISTIRILAMAZ hale geliyordu. Yorum ve bos satirlar
    # artik blogu bitirmiyor; yalnizca girintisi blogun disina cikan
    # gercek bir icerik satiri bitiriyor.
    kaydirilmis = []
    blok = False
    for satir in satirlar:
        if satir.startswith("  mertebeler:"):
            blok = True
            kaydirilmis.append(satir)
            continue
        if blok:
            if satir.strip() == "" or satir.lstrip().startswith("#"):
                kaydirilmis.append(satir)
                continue
            if satir.startswith("  - ") or satir.startswith("    "):
                kaydirilmis.append("  " + satir)
                continue
            blok = False
        kaydirilmis.append(satir)
    satirlar = kaydirilmis

    # DIKKAT -- ayni yapiskanlik MERTEBE duzeyinde de olur: "metinde"/
    # "kaynak" bir mertebeye eklendiginde, o mertebe bir Yol girdisinin SON
    # mertebesiyse ve hemen ardindan bir bolum basligi yorumu geliyorsa
    # (orn. "# --- Kavramlar ---"), ruamel o yorumu (ve etrafindaki bos
    # satirlari) yine ESKI son anahtara yapistirir. Veri BOZULMAZ (YAML
    # girinti agacina gore hala dogru mertebeye baglidir), ama ham metinde
    # yeni alanlar yorumun ALTINDA, bir sonraki girdinin icine sizmis gibi
    # kalir ve "DIFF'I OKUYUN" adimini anlamsizlastirir. Cozum tek bir
    # SATIR SILME degil, YER DEGISTIRME: yeni-alan calisan satirlari,
    # aralarina giren bos-satir/yorum blogunun ONUNE tasimak. Bu alan
    # adlari YALNIZCA bir oncekinin devami olarak gecer, hicbir zaman
    # kendi basina bir blok ACMAZ -- yani boyle bir blok bu satirlarin
    # hemen ardindan geliyorsa bu HER ZAMAN yapiskanlik belirtisidir,
    # mesru bir bicimlendirme degil; sabit 2 boslukla sinirlamak yerine
    # herhangi bir girintide (mertebe ICI dahil) eslesir.
    yeni_alan = re.compile(r"^\s*(kaynak|mudahale|denetim|metinde|ilk_gecis):")
    ara_blok = re.compile(r"^\s*$|^\s*#")

    cikti = []
    i, n = 0, len(satirlar)
    while i < n:
        satir = satirlar[i]
        if ara_blok.match(satir):
            j = i
            while j < n and ara_blok.match(satirlar[j]):
                j += 1
            k = j
            while k < n and yeni_alan.match(satirlar[k]):
                k += 1
            if k > j:
                # [j, k) yeni-alan satirlari [i, j) blogunun HEMEN
                # ardindan geliyor -- yapiskanlik belirtisi. Once yeni
                # alanlari, sonra bloklu (bos/yorum) kismi yaz.
                cikti.extend(satirlar[j:k])
                cikti.extend(satirlar[i:j])
                i = k
                continue
            cikti.extend(satirlar[i:j])
            i = j
            continue
        cikti.append(satir)
        i += 1
    satirlar = cikti

    metin = "\n".join(satirlar)

    # her ust duzey girdiden once tam olarak bir bos satir; ama bolum
    # basligi yorumlari girdiye bitisik kalsin
    sonuc = []
    onceki_dolu = None
    for satir in metin.split("\n"):
        if satir.startswith("- terim:") and onceki_dolu is not None:
            if (
                not onceki_dolu.lstrip().startswith("#")
                and sonuc
                and sonuc[-1].strip() != ""
            ):
                sonuc.append("")
        sonuc.append(satir)
        if satir.strip() != "":
            onceki_dolu = satir
    return "\n".join(sonuc)


def dogrula(metin, beklenen_girdi_sayisi):
    """
    Yazmadan ONCE uretilen metni ayristirmayi dene.

    bosluk_duzelt dump edilmis metin uzerinde girinti cerrahisi yapiyor.
    Bir kez sessizce bozdu: yorum satiri mertebeler blogunu erken
    kapatiyor, kalan alanlar kaydirilmadan kaliyor ve dosya
    ayristirilamaz hale geliyordu -- ustelik --yerinde ile YERINE
    yaziliyordu. Kaybi git'ten geri almak mumkun ama once fark edilmesi
    gerekiyor.

    Ucuz kontrol, pahali hata: ayristirilamiyorsa ya da girdi sayisi
    tutmuyorsa hicbir sey yazilmaz.
    """
    import yaml as _pyyaml

    try:
        veri = _pyyaml.safe_load(metin)
    except _pyyaml.YAMLError as e:
        return f"uretilen YAML ayristirilamadi: {e}"
    if not isinstance(veri, list):
        return f"kok oge liste degil: {type(veri).__name__}"
    if len(veri) != beklenen_girdi_sayisi:
        return (
            f"girdi sayisi degisti: {beklenen_girdi_sayisi} -> "
            f"{len(veri)} (bicimlendirme girdileri birlestirmis olabilir)"
        )
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sozluk", default=None)
    ap.add_argument("--rapor", default="rapor.tsv")
    ap.add_argument("--cikti", default="sozluk_etiketli.yml")
    ap.add_argument("--yerinde", action="store_true", help="dosyanin uzerine yaz")
    args = ap.parse_args()

    rapor = rapor_oku(args.rapor)

    try:
        sozluk = lotm.sozluk_yukle(args.sozluk, bicim_koru=True)
    except (FileNotFoundError, OSError) as e:
        sys.exit(f"HATA: {e}")

    sayac = defaultdict(int)
    elle_gereksiz, elle_celiski, kapi_sonrasi = [], [], []
    # bekleyen: turetilemedigi icin "bilinmiyor" yazilan alanlar -- is listesi.
    # kullanilan_elle: elle tablolarda GERCEKTEN eslesen anahtarlar; eslesmeyen
    # anahtar yeniden adlandirilmis bir girdiyi gosterir (bkz. rapor sonu).
    bekleyen, kullanilan_elle = [], set()

    once = anlik(sozluk.veri)

    for girdi in sozluk.veri:
        ad = girdi["terim"]
        kategori = girdi.get("kategori", "")
        mertebeler = girdi.get("mertebeler")

        # ---------------------------------------------------------- YOLLAR
        if mertebeler:
            yok_var = False
            for m in mertebeler:
                eng = lotm.ingilizce_ayikla(m.get("isim"))
                if not eng:
                    continue
                # cok adli mertebelerde ilk ad esas alinir
                eng = eng.split("/")[0].strip()
                tr = lotm.parantezsiz(m.get("isim"))

                durum = metinde_mi(eng, rapor)
                if durum is None:
                    sayac["mertebe_raporda_yok"] += 1
                    continue

                m["metinde"] = durum
                m["kaynak"] = "metin" if durum else "yazar_beyani"
                sayac["mertebe_etiketlendi"] += 1
                if not durum:
                    yok_var = True
                    continue

                # -------- bolum numaralari: KAPI insanin, ILK GECIS aracin
                mevcut = m.get("bolum_siniri")
                tarayici = rapor.get(eng, {}).get("bolum")

                if eng in BOLUM_ELLE or tr in BOLUM_ELLE:
                    yeni = BOLUM_ELLE.get(eng, BOLUM_ELLE.get(tr))
                    if mevcut is None:
                        m["bolum_siniri"] = yeni
                        sayac["kapi_elle_yazildi"] += 1
                    elif mevcut == yeni:
                        # Deger zaten YAML'de; kodda tutmaya gerek yok.
                        elle_gereksiz.append(f"{eng} ({yeni})")
                    else:
                        # YAML ile kod celisiyor: YAML kazanir, cunku
                        # editoryal karar orada yasar.
                        elle_celiski.append(
                            f"{eng}: sozluk={mevcut}, BOLUM_ELLE={yeni}"
                        )

                if not rapor.get(eng, {}).get("guvenilir", True):
                    # kapi_denetle.py'nin cins isim isareti: terim metinde
                    # kucuk harfle de geciyorsa bulunan bolum bir sey
                    # bildirmez.
                    sayac["ilk_gecis_atlandi_cins_isim"] += 1
                    continue

                if tarayici and m.get("ilk_gecis") != tarayici:
                    m["ilk_gecis"] = tarayici
                    sayac["ilk_gecis_yazildi"] += 1

                # KAPI'ya DOKUNULMAZ. Eskiden burada
                #     if tarayici > mevcut: m["bolum_siniri"] = tarayici
                # vardi. Kapi "ad ilk nerede geciyor" degil "nerede
                # ACIKLANIYOR" demek; ikisi cogu terimde farkli ve karari
                # cevirmen veriyor. Arac kendi bulgusunu ilk_gecis'e yazar,
                # celiskiyi yayim_denetle gosterir.
                if mevcut and tarayici and tarayici > mevcut:
                    kapi_sonrasi.append(
                        f"{ad} S{m['seviye']} {eng}: kapi={mevcut}, "
                        f"ilk_gecis={tarayici}"
                    )

            girdi["kaynak"] = "karma" if yok_var else "metin"
            sayac["yol_" + girdi["kaynak"]] += 1
            continue

        # -------------------------------------------------- UST DUZEY GIRDI
        # ust_durum: tarayici bu terimi Ingilizce metinde buldu mu.
        # None = hic bakilamadi (Ingilizce ad yok ya da raporda yok).
        # "metinde" alani YALNIZCA mertebe alt girdilerine yaziliyor
        # (m["metinde"]), ust duzey girdiye degil -- kaynak karari bu
        # yuzden girdi["metinde"]'ye degil buradaki yerel degere bakar.
        ust_durum = None
        eng = lotm.parantezsiz(girdi.get("ingilizce")) or None
        if eng:
            durum = metinde_mi(eng, rapor)
            ust_durum = durum
            if durum is None:
                sayac["ust_raporda_yok"] += 1
            else:
                sayac["ust_etiketlendi"] += 1
                tarayici = rapor.get(eng, {}).get("bolum")
                guvenilir = rapor.get(eng, {}).get("guvenilir", True)
                mevcut = girdi.get("bolum_siniri")

                # KAPI: yalnizca BOLUM_ELLE'deki elle karar ve yalnizca
                # deger BOSSA yazilir -- mertebe kolundakiyle ayni kural.
                if eng in BOLUM_ELLE or ad in BOLUM_ELLE:
                    yeni = BOLUM_ELLE.get(eng, BOLUM_ELLE.get(ad))
                    if mevcut is None:
                        girdi["bolum_siniri"] = yeni
                        sayac["kapi_elle_yazildi"] += 1
                    elif mevcut == yeni:
                        elle_gereksiz.append(f"{eng} ({yeni})")
                    else:
                        elle_celiski.append(
                            f"{eng}: sozluk={mevcut}, BOLUM_ELLE={yeni}"
                        )

                # ilk_gecis: TURETILEN, serbestce guncellenir.
                if (
                    durum
                    and tarayici
                    and guvenilir
                    and girdi.get("ilk_gecis") != tarayici
                ):
                    girdi["ilk_gecis"] = tarayici
                    sayac["ilk_gecis_yazildi"] += 1

                # KAPI'ya DOKUNULMAZ; yalnizca insana bildir.
                if mevcut is not None and tarayici and tarayici > mevcut and guvenilir:
                    kapi_sonrasi.append(
                        f"{ad} {eng}: kapi={mevcut}, ilk_gecis={tarayici}"
                    )
        else:
            sayac["ust_ingilizce_yok"] += 1

        if ad in KAYNAK_ELLE:
            girdi["kaynak"] = KAYNAK_ELLE[ad]
            kullanilan_elle.add(ad)
        elif ad in TAROT_YAZAR_BEYANI:
            girdi["kaynak"] = "yazar_beyani"
            kullanilan_elle.add(ad)
        elif ad in TAROT_KARMA:
            girdi["kaynak"] = "karma"
            kullanilan_elle.add(ad)
        elif ust_durum is True:
            # Tarayici terimi metinde buldu: "metin" TURETILMIS bir deger.
            girdi["kaynak"] = "metin"
        else:
            # Kanit yok. Eskiden yine "metin" yaziliyordu -- terimin LotM
            # metninden geldigi iddiasi, hicbir sey dogrulamadan. Yanlis
            # bir deger, dogru bir degerden ayirt edilemiyordu.
            girdi["kaynak"] = "bilinmiyor"
            sayac["kaynak_bilinmiyor"] += 1
            bekleyen.append(f"  kaynak    {ad}")

        if ad in MUDAHALE:
            girdi["mudahale"] = MUDAHALE[ad]
            kullanilan_elle.add(ad)
            girdi["denetim"] = "tamam"
            sayac["denetim_tamam"] += 1
        elif kategori in TAZIM_KATEGORILERI:
            # tazim ismi denetiminden gecti, sapma bulunmadi
            girdi["mudahale"] = "ceviri"
            girdi["denetim"] = "tamam"
            sayac["denetim_tamam"] += 1
        else:
            # Kavram/orgut girdisi: ortada uyarlanacak bir TAZIM ISMI yok,
            # aciklama zaten cevirmenin kendi nesri. "ceviri" burada
            # uydurma degil, girdinin turunden TURETILMIS bir deger.
            #
            # denetim "tamam" BILEREK: tazim ismi denetimi bu girdilere
            # uygulanmaz, aciklama nesri cevirmenin kendisidir. Sitedeki
            # "Denetlenmedi" rozeti (denetim == 'denetlenmedi') bu yuzden
            # bu girdilerde cikmaz. Eskiden sayac "denetim_bekliyor"
            # diyordu ve yorum alanin "bekliyor" olmasi gerektigini
            # soyluyordu; dosya ile ozet celisiyordu. Karar "tamam".
            girdi["mudahale"] = "ceviri"
            girdi["denetim"] = "tamam"
            sayac["denetim_tamam_kavram"] += 1

        # eski alan artik iki eksene bolundu
        if "kanon_durumu" in girdi:
            del girdi["kanon_durumu"]
            sayac["kanon_durumu_kaldirildi"] += 1

    hedef = args.sozluk if args.yerinde else args.cikti

    try:
        sozluk.yaz(
            hedef,
            duzeltici=bosluk_duzelt,
            dogrulayici=lambda metin: dogrula(metin, len(sozluk.veri)),
        )
    except lotm.YazmaReddedildi as e:
        sys.exit(f"HATA: {e}\nHicbir sey yazilmadi ({hedef} dokunulmadi).")

    print(f"Yazildi: {hedef}\n")
    if elle_celiski:
        print("--- BOLUM_ELLE ILE SOZLUK CELISIYOR (sozluk kazandi) ---")
        for x in elle_celiski:
            print(f"  {x}")
        print()
    if elle_gereksiz:
        print("--- BOLUM_ELLE ARTIK GEREKSIZ ---")
        print("  Bu degerler sozluk.yml'de zaten ayni. Kapiyi arac artik")
        print("  ezmedigi icin kodda tutmaya gerek yok; BOLUM_ELLE'den")
        print("  silebilirsiniz.")
        for x in elle_gereksiz:
            print(f"  {x}")
        print()
    if kapi_sonrasi:
        print("--- ILK GECIS KAPIDAN SONRA ---")
        print("  Ad, kapidan SONRA ilk kez geciyor. Ya kapi fazla erken,")
        print("  ya tarayici bagimsiz ilk gecisi kaciriyor. Kapi degismedi.")
        for x in kapi_sonrasi[:20]:
            print(f"  {x}")
        print()

    degisiklikler = fark(once, anlik(sozluk.veri))
    print(f"--- DEGISIKLIKLER ({len(degisiklikler)}) ---")
    for satir in degisiklikler:
        print(satir)
    if not degisiklikler:
        print("  yok -- sozluk zaten guncel")
    if bekleyen:
        print(f"\n--- TURETILEMEDI: ELLE KARAR BEKLIYOR ({len(bekleyen)}) ---")
        print("  Bu alanlara deger YAZILMADI ('bilinmiyor'). Eskiden buraya")
        print("  makul gorunen bir varsayilan konuyordu ve yanlis bir deger")
        print("  dogru bir degerden ayirt edilemiyordu.")
        for satir in sorted(bekleyen)[:40]:
            print(satir)
        if len(bekleyen) > 40:
            print(f"  ... {len(bekleyen) - 40} tane daha")

    oksuz = sorted(
        (set(MUDAHALE) | set(KAYNAK_ELLE) | TAROT_YAZAR_BEYANI | TAROT_KARMA)
        - kullanilan_elle
    )
    if oksuz:
        print(f"\n--- ELLE TABLODA KARSILIGI OLMAYAN ANAHTAR ({len(oksuz)}) ---")
        print("  Bu adlar sozlukte YOK. Girdi yeniden adlandirildiysa karar")
        print("  sessizce dusmus, girdi varsayilana kaymis demektir --")
        print("  tablolar ada gore anahtarlaniyor. Adi guncelleyin ya da")
        print("  satiri silin.")
        for ad in oksuz:
            print(f"  {ad}")

    print("\n--- SAYIM ---")
    for k in sorted(sayac):
        print(f"  {k}: {sayac[k]}")


if __name__ == "__main__":
    main()
