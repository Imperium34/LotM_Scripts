# -*- coding: utf-8 -*-
"""
kapanis_denetle'nin SESSIZ iki davranisi.

Ikisi de bozuldugunda ciktiyi bos birakmaz, YANLIS birakir: biri her
bolumde yanlis alarm uretir, digeri gercek bir ihlali kacirir. Bir
denetleyicide bu ikisi, hic calismamaktan daha pahalidir -- ilki araci
gormezden gelmeyi ogretir, ikincisi guven verir.
"""

import pytest

from kapanis_denetle import denetle

# Bolum 44'un kendi notu: ¶15'te "silindir" yasaktir (altipatlarin
# parcasi "top"tur) ama ¶22'deki "silindir sapka" DOGRUDUR. Ayni bolumde
# ayni dize hem yasak hem zorunlu. Maskeleme olmadan her calistirmada
# yanlis alarm cikar.
RAPOR = """\
## A. TERİMLER VE ÖZEL ADLAR

### A.1 Yerleşik terimler (değiştirilemez)

| İngilizce | Türkçe | Kullanım notu |
|---|---|---|
| Fool | Soytarı | ¶90 |
| half top hat | yarım boy ipek silindir şapka | ¶22 |

### A.2 Bu bölümde karara bağlanan özel adlar

| İngilizce | Türkçe | Etiket | Not |
|---|---|---|---|
| Quint | Kent | [TEREDDÜT] | karar verilmedi |
| Midnight Poem | Geceyarısı Şiiri | [YENİ] | ¶5 |

### A.3 Metne eklenmeyecek

- ¶15: **"silindir" yasaktır** (altıpatların parçası "top"tur). ¶22'deki
  şapka için "silindir şapka" ise doğrudur; iki kelime aynı bölümde iki
  ayrı işte çalışır.
- ¶90: **"Aptal", "Deli" yasaktır** — Soytarı kullanılır.
- ¶10: müfreze için **"takım", "ekip" yasaktır.**

## B. DONDURULAN SATIRLAR

| İngilizce | Türkçe (dondurulmuş) | Bölümdeki geçiş sayısı | Not |
|---|---|---|---|
| Everyone dies | Ben dahil herkes ölecek. | 1 (¶92) | el yazması |
"""


def _hatalar(ceviri):
    return [m for s, m in denetle(RAPOR, ceviri) if s == "HATA"]


def test_izinli_terim_yasak_dizeyi_maskeler():
    """
    "silindir şapka" geçiyor, çıplak "silindir" geçmiyor: alarm OLMAMALI.
    Maskeleme kalkarsa bu bölüm her seferinde yanlış alarm verir.
    """
    ceviri = (
        "Klein yarım boy ipek silindir şapka takmıştı. Soytarı resmi vardı.\n"
        "El yazmasında şöyle yazıyordu: Ben dahil herkes ölecek."
    )
    assert not any("silindir" in h for h in _hatalar(ceviri))


def test_ciplak_yasak_dize_maskeden_sonra_yakalanir():
    """Maskeleme yasağı KÖRLEŞTİRMEMELİ: izinli terim dışındaki geçiş hatadır."""
    ceviri = (
        "Klein yarım boy ipek silindir şapka takmıştı; altıpatlarının "
        "silindiri döndü. Ben dahil herkes ölecek."
    )
    assert any("silindir" in h for h in _hatalar(ceviri))


def test_buyuk_harfli_yasak_kucuk_harfliyi_yakalamaz():
    """
    "Aptal" Soytarı'nın yasak eşanlamlısı; küçük "aptal" sıradan sıfattır
    ("yüzünün aptallaştığını gördü"). Harf duyarlılığı kalkarsa araç
    olağan Türkçeyi ihlal sayar.
    """
    ceviri = "Adamın yüzünün aptallaştığını gördü. Ben dahil herkes ölecek."
    assert not any("Aptal" in h for h in _hatalar(ceviri))


def test_buyuk_harfli_yasak_kendi_bicimini_yakalar():
    ceviri = "Kartta Soytarı değil Aptal yazıyordu. Ben dahil herkes ölecek."
    assert any("Aptal" in h for h in _hatalar(ceviri))


def test_tereddut_satiri_dayatilmaz():
    """
    [TEREDDÜT] "karar senin" demek, "karar verildi" değil. Dayatmak
    verilmemiş bir kararı zorlar ve araç güvenilmez hâle gelir.
    """
    ceviri = "Bir el Gwent oynadılar. Ben dahil herkes ölecek."
    uyarilar = [m for s, m in denetle(RAPOR, ceviri) if s == "UYARI"]
    assert not any("Kent" in u for u in uyarilar)


@pytest.mark.parametrize(
    "sayi,hatali",
    [(1, False), (0, True), (2, True)],
)
def test_dondurulmus_satir_sayisi(sayi, hatali):
    ceviri = "Ben dahil herkes ölecek. " * sayi + "Soytarı resmi vardı."
    assert bool(_hatalar(ceviri)) is hatali


def test_ekip_cekip_icinde_yakalanmaz():
    """
    Bölüm 44: "omzunu geriye ÇEKİP" — düz altdize araması burada 'ekip'
    buluyordu. Sol sınır şart; sağ taraf açık kalmalı ki 'ekibi' kaçmasın.
    """
    ceviri = "Omzunu geriye çekip yumruk indirdi. Ben dahil herkes ölecek."
    assert not any("ekip" in h for h in _hatalar(ceviri))


def test_ekip_kendi_bicimiyle_yakalanir():
    ceviri = "Müfrezenin ekibi toplandı. Ben dahil herkes ölecek."
    assert any("ekip" in h for h in _hatalar(ceviri))


def test_a3_kuyrugundaki_istisna_maskeler():
    """
    A.3 maddesi yasağın yanında izinli biçimi de yazıyor:
    **"silindir" yasaktır** ... "silindir şapka" ise doğrudur.
    Kuyruktaki tırnak maskelenmezse her bölümde yanlış alarm.
    """
    ceviri = "Yarım boy ipek silindir şapka takmıştı. Ben dahil herkes ölecek."
    assert not any("silindir" in h for h in _hatalar(ceviri))


def test_cogul_terim_tekil_bicimde_bulunur():
    """"Gece Şahinleri" metinde "Gece Şahini" olarak geçebilir."""
    from kapanis_denetle import karsilik_var_mi

    assert karsilik_var_mi("Gece Şahinleri", "şair mizaçlı Gece Şahini geldi")
    assert karsilik_var_mi("terennüm etmek", "terennümü kesti, etmeyi düşündü")
    assert not karsilik_var_mi("Kehanet", "burada öyle bir sözcük yok")


def test_kalip_tarifi_hata_degil_elle():
    """
    Bölüm 42: «paralı asker → kesinti → güvenlik …» bir dize değil, bir
    KURULUŞ tarifidir; ortadaki "kesinti" aranacak metin değil, aradaki
    şeyin adıdır. Düz dize gibi aranınca her seferinde 0/4 verir.
    """
    from kapanis_denetle import kalip_turu, dizi_deseni
    import re as _re

    assert kalip_turu("paralı asker → kesinti → güvenlik …") == "elle"
    assert kalip_turu('"paralı asker" → kesinti → "güvenlik" …') == "dizi"
    assert kalip_turu('"Ben dahil herkes ölecek."') == "dize"
    assert kalip_turu('"koyulaş-"') == "govde"

    metin = "Sizin paralı askerleriniz, yok, güvenlik personeliniz döner."
    desen = dizi_deseni('"paralı asker" → kesinti → "güvenlik" …')
    assert len(_re.findall(desen, metin)) == 1


def test_uzun_sozcuk_govdesine_kadar_kirpilir():
    """"damgalamak" metinde "damgasını basmak" olarak geçebilir."""
    from kapanis_denetle import karsilik_var_mi

    assert karsilik_var_mi("damgalamak", "kendi damgasını bastıktan sonra")
    assert not karsilik_var_mi("Kehanet", "burada öyle bir sözcük yok")
