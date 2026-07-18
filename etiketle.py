#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etiketle.py -- sozluk.yml'e kaynak / mudahale / metinde / denetim alanlarini yazar.

Tasarim ilkesi: kurallar tek yerde, elle yazilmis deger yok. Veri degisirse
yeniden calistirilir, diff denetim kaydidir.

  ruamel.yaml kullanilir cunku PyYAML'in safe_dump'i "# ---" bolum basliklarini
  siler, anahtarlari alfabetik siralar ve uzun aciklama/cevirmen_notu
  dizelerini yeniden sarar. Dosya anlamca ayni kalir ama diff okunamaz hale
  gelir, yani neyin degistigini goremezsiniz.

Kullanim:
    python3 etiketle.py --sozluk sozluk.yml --rapor rapor.tsv \
        --cikti sozluk_etiketli.yml
    python3 etiketle.py --sozluk sozluk.yml --rapor rapor.tsv --yerinde
"""

import argparse
import re
import sys
from collections import defaultdict

try:
    from ruamel.yaml import YAML
    from ruamel.yaml.scalarstring import PlainScalarString
except ImportError:
    print("HATA: ruamel.yaml gerekli.  pip install ruamel.yaml", file=sys.stderr)
    sys.exit(1)


# =====================================================================
# KURALLAR -- hepsi burada, baska hicbir yerde deger yok
# =====================================================================

# Tarayici bulmus olsa da metinde GECMEDIGI kabul edilenler.
# Catastrophe: tek eslesme cins isim ("bring catastrophe to others"),
# Mertebe adi degil. Sozlukteki 66 degeri de ayni yanlis pozitiften geliyordu.
METINDE_YOK_ZORLA = {"Catastrophe"}

# Kisa adi baska bir Mertebe adinin icinde gecen terimler. Tarayicinin
# bulduğu bolum bunlar icin guvenilmez (ornek: "Hunter" -> "Demon Hunter").
# Bu adlar icin bolum numarasi hic yazilmaz.
ALT_DIZE_RISKI = {"Alchemist", "Calamity", "Death", "Demon", "Hunter", "Warlock"}

# Elle belirlenmis bolum numaralari. Hunter'in gercek gecisi, Criminal /
# Prisoner / Warrior / Hunter'in birlikte sayildigi pasaj.
BOLUM_ELLE = {"Hunter": 279}

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

def ingilizce_ayikla(ham):
    m = re.search(r"\(([^)]*)\)", str(ham or ""))
    return m.group(1).strip() if m else None


def rapor_oku(yol):
    """rapor.tsv -> {terim: {"guven":..., "bolum": int|None}}"""
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
                "guvenilir": p[ix.get("guvenilir_mi", 0)].strip() == "evet"
                if "guvenilir_mi" in ix
                else True,
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
    kaydirilmis = []
    blok = False
    for satir in satirlar:
        if satir.startswith("  mertebeler:"):
            blok = True
            kaydirilmis.append(satir)
            continue
        if blok:
            if satir.strip() == "":
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
            if not onceki_dolu.lstrip().startswith("#") and sonuc and sonuc[-1].strip() != "":
                sonuc.append("")
        sonuc.append(satir)
        if satir.strip() != "":
            onceki_dolu = satir
    return "\n".join(sonuc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sozluk", default="sozluk.yml")
    ap.add_argument("--rapor", default="rapor.tsv")
    ap.add_argument("--cikti", default="sozluk_etiketli.yml")
    ap.add_argument("--yerinde", action="store_true", help="dosyanin uzerine yaz")
    args = ap.parse_args()

    rapor = rapor_oku(args.rapor)

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096          # uzun dizeleri sarma
    # Kok liste sifir girintide olmali; mertebeler bloklari ise kaynak
    # dosyadaki gibi 4 bosluk. ruamel tek bir kural uyguladigi icin ikisi
    # ayni anda ayarlanamaz -- mertebeler bloklari metin gecisinde kaydirilir.
    yaml.indent(mapping=2, sequence=2, offset=0)

    with open(args.sozluk, "r", encoding="utf-8") as f:
        veri = yaml.load(f)

    degisiklikler = []
    sayac = defaultdict(int)

    for girdi in veri:
        ad = girdi["terim"]
        kategori = girdi.get("kategori", "")
        mertebeler = girdi.get("mertebeler")

        # ---------------------------------------------------------- YOLLAR
        if mertebeler:
            yok_var = False
            for m in mertebeler:
                eng = ingilizce_ayikla(m.get("isim"))
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

                # -------- bolum numarasi: yalnizca ileri, yalnizca guvenli
                if not durum:
                    continue
                mevcut = m.get("bolum_siniri")
                if eng in BOLUM_ELLE:
                    yeni = BOLUM_ELLE[eng]
                    if mevcut != yeni:
                        degisiklikler.append(
                            f"  bolum(elle)    {ad} S{m['seviye']}: {eng} {mevcut} -> {yeni}"
                        )
                        m["bolum_siniri"] = yeni
                        sayac["bolum_elle"] += 1
                    continue
                if eng in ALT_DIZE_RISKI:
                    sayac["bolum_atlandi_altdize"] += 1
                    continue
                tarayici = rapor.get(eng, {}).get("bolum")
                if tarayici and mevcut and tarayici > mevcut:
                    degisiklikler.append(
                        f"  bolum          {ad} S{m['seviye']}: {eng} {mevcut} -> {tarayici}"
                    )
                    m["bolum_siniri"] = tarayici
                    sayac["bolum_guncellendi"] += 1

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
            girdi["denetim"] = "denetlenmedi"
            sayac["denetim_bekliyor"] += 1

        # eski alan artik iki eksene bolundu
        if "kanon_durumu" in girdi:
            del girdi["kanon_durumu"]
            sayac["kanon_durumu_kaldirildi"] += 1

    import io
    tampon = io.StringIO()
    yaml.dump(veri, tampon)

    hedef = args.sozluk if args.yerinde else args.cikti
    with open(hedef, "w", encoding="utf-8") as f:
        f.write(bosluk_duzelt(tampon.getvalue()))

    print(f"Yazildi: {hedef}\n")
    print("--- DEGISIKLIKLER ---")
    for s in degisiklikler:
        print(s)
    print("\n--- SAYIM ---")
    for k in sorted(sayac):
        print(f"  {k}: {sayac[k]}")


if __name__ == "__main__":
    main()
