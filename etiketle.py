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

BU SURUMDE KALKAN ELLE LISTE
----------------------------
ALT_DIZE_RISKI artik sozlukten TURETILIYOR. Bir Ingilizce ad baska bir
adin icinde tam kelime olarak geciyorsa ("Hunter" -> "Demon Hunter"),
tarayicinin buldugu bolum o ad icin guvenilmezdir. Bu iliski zaten
sozlukte yaziyor; elle liste tutmak ayni bilgiyi ikinci kez yazmakti.

Ayrica rapor.tsv'nin 'guvenilir_mi' sutunu artik gercekten okunuyor.
searcher.py terimin metinde kucuk harfle de gectigini tespit ediyordu
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

# Turetilen alt dize listesine EK olarak elle eklenecekler. Turetme
# yalnizca sozlukteki adlar arasindaki iliskiyi gorur; metinde gecip
# sozlukte olmayan bir uzun ad varsa buraya yazin.
EK_ALT_DIZE_RISKI = set()

# Elle belirlenmis bolum numaralari. Hunter'in gercek gecisi, Criminal /
# Prisoner / Warrior / Hunter'in birlikte sayildigi pasaj.
BOLUM_ELLE = {
    "Hunter": 279,
    "Berzah Bekçisi": 19,
    "İlahların Metruk Diyarı": 137,
    "Kâhin": 21,
    "Yağmacı": 21,
    "Çırak": 21,
}

# Tazim ismi denetiminden gelen mudahale degerleri (girdi adina gore).
MUDAHALE = {
    "Ebedi Yanan Güneş": "birlestirme",
    "Kotar": "tamamlama",
    "Hakiki Hâlık": "degistirme",
    "Kadim Şeytaniçe": "degistirme",
    "Kadim Şeytaniçe (Tam Tazim İsmi)": "degistirme",
    "İlim ve Hikmetin İlahı": "degistirme",
    "Batınî Bilge": "ozgun",
    "Prangalı İlah": "ozgun",
    "Tahayyül Meleği Âdem (Melekler Kralı)": "ozgun",
}

# Kaynagi LotM metni olmayan girdiler.
KAYNAK_ELLE = {
    "Kadim Şeytaniçe (Tam Tazim İsmi)": "metin_coi",
    "Halas Meleği Amon": "metin_coi",
    "Yarı Kadir-i Mutlak Âdem (Yarı Yüce Kadim)": "metin_coi",
    "Sihirli Ayna Arrodes": "metin_coi",
    "Ebedi Gece Tanrıçası (Sermedi Zulmet)": "yazar_beyani",
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

TAZIM_KATEGORILERI = {"İlahlar ve Yüce Kadimler", "Tarot Kulübü"}


# =====================================================================


def alt_dize_riski_turet(sozluk) -> set:
    """
    Ingilizce adi baska bir adin icinde TAM KELIME olarak gecen terimler.

    'Hunter' hem kendi basina hem 'Demon Hunter' icinde gecer; tarayici
    ikisini ayirt edemedigi icin buldugu bolum guvenilmezdir. Iliski
    sozlukte zaten yazili, o yuzden turetiliyor.
    """
    adlar = {t.en for t in sozluk.terimler if t.en}
    riskli = set()
    for kisa in adlar:
        desen = re.compile(r"(?<!\w)" + re.escape(kisa) + r"(?!\w)")
        for uzun in adlar:
            if uzun != kisa and desen.search(uzun):
                riskli.add(kisa)
                break
    return riskli | EK_ALT_DIZE_RISKI


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

    cikti = []
    yeni_alan = re.compile(r"^  (kaynak|mudahale|denetim):")
    for i, satir in enumerate(satirlar):
        if satir.strip() == "":
            j = i + 1
            while j < len(satirlar) and satirlar[j].strip() == "":
                j += 1
            if j < len(satirlar) and yeni_alan.match(satirlar[j]):
                continue
        cikti.append(satir)

    metin = "\n".join(cikti)

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

    alt_dize = alt_dize_riski_turet(sozluk)

    degisiklikler = []
    sayac = defaultdict(int)
    elle_gereksiz, elle_celiski, kapi_sonrasi = [], [], []

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

                durum = metinde_mi(eng, rapor)
                if durum is None:
                    sayac["mertebe_raporda_yok"] += 1
                    continue

                m["metinde"] = durum
                m["kaynak"] = "metin" if durum else "yazar_beyani"
                sayac["mertebe_etiketlendi"] += 1
                if not durum:
                    yok_var = True
                    degisiklikler.append(f"  metinde=false  {ad} S{m['seviye']}: {eng}")

                # -------- bolum numaralari: KAPI insanin, ILK GECIS aracin
                if not durum:
                    continue
                mevcut = m.get("bolum_siniri")
                tarayici = rapor.get(eng, {}).get("bolum")

                if eng in BOLUM_ELLE:
                    yeni = BOLUM_ELLE[eng]
                    if mevcut is None:
                        m["bolum_siniri"] = yeni
                        degisiklikler.append(
                            f"  kapi(elle)     {ad} S{m['seviye']}: {eng} -> {yeni}"
                        )
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

                if eng in alt_dize and not tarayici:
                    # Terim metinde yalnizca daha uzun bir adin icinde
                    # geciyor; bagimsiz gecisi yok.
                    sayac["ilk_gecis_atlandi_altdize"] += 1
                    continue
                if not rapor.get(eng, {}).get("guvenilir", True):
                    # searcher.py'nin cins isim isareti: terim metinde
                    # kucuk harfle de geciyorsa bulunan bolum bir sey
                    # bildirmez.
                    sayac["ilk_gecis_atlandi_cins_isim"] += 1
                    continue

                if tarayici and m.get("ilk_gecis") != tarayici:
                    degisiklikler.append(
                        f"  ilk_gecis      {ad} S{m['seviye']}: "
                        f"{eng} {m.get('ilk_gecis')} -> {tarayici}"
                    )
                    m["ilk_gecis"] = tarayici
                    sayac["ilk_gecis_yazildi"] += 1

                # KAPI'ya DOKUNULMAZ. Eskiden burada
                #     if tarayici > mevcut: m["bolum_siniri"] = tarayici
                # vardi. Kapi "ad ilk nerede geciyor" degil "nerede
                # ACIKLANIYOR" demek; ikisi cogu terimde farkli ve karari
                # cevirmen veriyor. Arac kendi bulgusunu ilk_gecis'e yazar,
                # celiskiyi denetci2 gosterir.
                if mevcut and tarayici and tarayici > mevcut:
                    kapi_sonrasi.append(
                        f"{ad} S{m['seviye']} {eng}: kapi={mevcut}, "
                        f"ilk_gecis={tarayici}"
                    )

            girdi["kaynak"] = "karma" if yok_var else "metin"
            sayac["yol_" + girdi["kaynak"]] += 1
            continue

        # -------------------------------------------------- UST DUZEY GIRDI
        if ad in KAYNAK_ELLE:
            girdi["kaynak"] = KAYNAK_ELLE[ad]
        elif ad in TAROT_YAZAR_BEYANI:
            girdi["kaynak"] = "yazar_beyani"
        elif ad in TAROT_KARMA:
            girdi["kaynak"] = "karma"
        else:
            girdi["kaynak"] = "metin"

        if ad in MUDAHALE:
            girdi["mudahale"] = MUDAHALE[ad]
            girdi["denetim"] = "tamam"
            sayac["denetim_tamam"] += 1
        elif kategori in TAZIM_KATEGORILERI:
            # tazim ismi denetiminden gecti, sapma bulunmadi
            girdi["mudahale"] = "ceviri"
            girdi["denetim"] = "tamam"
            sayac["denetim_tamam"] += 1
        else:
            # kavram/orgut girdileri: aciklama zaten cevirmenin kendi nesri
            girdi["mudahale"] = "ceviri"
            girdi["denetim"] = "tamam"
            sayac["denetim_bekliyor"] += 1

        # eski alan artik iki eksene bolundu
        if "kanon_durumu" in girdi:
            del girdi["kanon_durumu"]
            sayac["kanon_durumu_kaldirildi"] += 1

    hedef = args.sozluk if args.yerinde else args.cikti

    import io

    tampon = io.StringIO()
    sozluk._yaml.dump(sozluk.veri, tampon)
    metin = bosluk_duzelt(tampon.getvalue())

    hata = dogrula(metin, len(sozluk.veri))
    if hata:
        sys.exit(f"HATA: {hata}\nHicbir sey yazilmadi ({hedef} dokunulmadi).")

    from pathlib import Path

    Path(hedef).write_text(metin, encoding="utf-8")

    print(f"Yazildi: {hedef}\n")
    if alt_dize:
        print(
            f"Alt dize riski turetildi ({len(alt_dize)}): "
            f"{', '.join(sorted(alt_dize))}\n"
        )
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

    print("--- DEGISIKLIKLER ---")
    for s in degisiklikler:
        print(s)
    print("\n--- SAYIM ---")
    for k in sorted(sayac):
        print(f"  {k}: {sayac[k]}")


if __name__ == "__main__":
    main()
