# -*- coding: utf-8 -*-
"""
kapanis_denetle.py -- sablon sozlesmesinin kabul vakalari.

Depo gerektirmez: butun sablonlar ve taslaklar burada, satir icinde.
Her vaka ya duzeltilen bir hatanin kendisi ya da korunmasi gereken eski
bir davranistir; ikincileri "korunur" diye isaretli.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kapanis_denetle as K  # noqa: E402


def sablon(a1="", a2="", a3="", b=""):
    """Yalnizca verilen bolumleri tasiyan en kucuk sablon."""
    bas = "| İngilizce | Türkçe | Not |\n| --- | --- | --- |\n"
    bas2 = "| İngilizce | Türkçe | Etiket | Not |\n| --- | --- | --- | --- |\n"
    basb = ("| İngilizce | Türkçe (dondurulmuş) | Bölümdeki geçiş sayısı | Not |\n"
            "| --- | --- | --- | --- |\n")
    return (
        f"### A.1 Yerleşik terimler (değiştirilemez)\n\n{bas}{a1}\n"
        f"### A.2 Bu bölümde karara bağlanan özel adlar\n\n{bas2}{a2}\n"
        f"### A.3 Metne eklenmeyecek\n\n{a3}\n"
        f"## B. DONDURULAN SATIRLAR\n\n{basb}{b}\n"
        "## C. AKTİF SES HARİTALARI\n"
    )


def bulgular(rapor, ceviri, seviye=None, icerir=None):
    out = K.denetle(rapor, ceviri)
    if seviye:
        out = [x for x in out if x[0] == seviye]
    if icerir:
        out = [x for x in out if icerir in x[1]]
    return out


# ------------------------------------------------------------ 1. satirlar


def test_ingilizce_ve_turkce_bolunur():
    st, = K.satirlar(
        "| x | y | z |\n|---|---|---|\n"
        "| Seer / Seer potion (¶55) | Kâhin / Kâhin iksiri | — |\n"
    )
    assert st.en == ["Seer", "Seer potion"]
    assert st.tr == [("Kâhin", False), ("Kâhin iksiri", False)]


def test_govde_tiresi_ayrilir():
    st, = K.satirlar("| x | y | z |\n|---|---|---|\n| to commission | havale et- | ¶24 |\n")
    assert st.tr == [("havale et", True)]


def test_tereddut_isaretlenir_ama_atilmaz():
    st, = K.satirlar(
        "| x | y | e | n |\n|---|---|---|---|\n| funds | ödenek | `[TEREDDÜT]` | — |\n"
    )
    assert st.tereddut


def test_eski_terimler_arayuzu_korunur():
    govde = "| x | y | z |\n|---|---|---|\n| Seer / Seer potion | Kâhin / havale et- | — |\n"
    assert K.terimler(govde) == [
        ("Seer / Seer potion", "Kâhin", "—"),
        ("Seer / Seer potion", "havale et-", "—"),
    ]


def test_sizinti_ikinci_ingilizce_bicimde_yakalanir():
    r = sablon(a1="| Seer / Seer potion | Kâhin / Kâhin iksiri | — |\n")
    hata = bulgular(r, "Elinde bir Seer potion vardı.", "HATA", "İngilizce")
    assert hata and "Seer potion" in hata[0][1]


def test_ozel_ad_sizinti_sayilmaz():
    r = sablon(a1="| Leonard / Captain Dunn | Leonard / Kaptan Dunn | — |\n")
    assert not bulgular(r, "Leonard geldi.", "HATA", "İngilizce")


def test_turkce_esadli_ingilizce_tanimlikla_yazilir():
    r = sablon(a1="| the sofa | kanepe | — |\n")
    assert not bulgular(r, "Kanepeye oturdu, sofadan geçti.", "HATA", "İngilizce")


def test_govde_maskelenir():
    # Eskiden izinli liste "havale et-" (tireli) tasiyordu ve metinde hic
    # bulunmuyordu; "ettiği" yasagi izinli terimin icinden yakalaniyordu.
    r = sablon(a1="| to commission | havale et- | — |\n",
               a3='- **"ettiği" yasak.**\n')
    assert not bulgular(r, "Kâhyanın havale ettiği iş.", "HATA", "yasak kelime")


# ------------------------------------------------------------ 2. varlik


@pytest.mark.parametrize("terim, metin, govde, beklenen", [
    ("Ray Bieber", "Ray Bieber'ın elinde", False, True),
    ("Bay Neil", "Bay Neil, siz de", False, True),
    ("Bay Neil", "Neil geldi", False, False),
    ("ruh göçü", "ruh göçüyle buraya", False, True),
    ("rol yap", "'rol yapmaya' başlamak", True, True),
    ("havale et", "havale ettiği işin", True, True),
    ("Gece Şahinleri", "Gece Şahini", False, True),      # korunur
    ("kabul salonu", "ön salona girdi", False, False),
    ("iş", "herhangi bir metin", False, None),           # dogrulanamaz
])
def test_karsilik_var_mi(terim, metin, govde, beklenen):
    assert K.karsilik_var_mi(terim, metin, govde=govde) is beklenen


def test_iki_harfli_terim_raporda_ayrica_soylenir():
    r = sablon(a2="| job | iş | `[YENİ]` | — |\n")
    satir = [m for s, m in K.denetle(r, "Metin.") if "karşılı" in m][0]
    assert "doğrulanamadı: iş" in satir


def test_uc_harfli_ad_yanlis_alarm_vermez():
    r = sablon(a1="| Ray Bieber | Ray Bieber | — |\n| Mr. Neil | Bay Neil | — |\n")
    assert not bulgular(r, "Ray Bieber'ı Bay Neil buldu.", "UYARI", "bulunamayan")


# ------------------------------------------------------------ 3. <br>


@pytest.mark.parametrize("hucre, beklenen", [
    ('"A"<br>"B"', "dize"),
    ('"paralı asker" → kesinti → "güvenlik"', "dizi"),   # korunur
    ("Hım... peki", "elle"),                              # korunur
    ('"Hım" … "peki"', "dizi"),
])
def test_kalip_turu(hucre, beklenen):
    assert K.kalip_turu(hucre) == beklenen


def test_br_hucresi_iki_ayri_satir_olarak_okunur_ve_uyarilir():
    r = sablon(b='| x | "Birinci satır"<br>"İkinci satır" | 1 | — |\n')
    assert [(k, n, t) for k, n, t in K.dondurulmus(r.split("## B.")[1])] == [
        ("Birinci satır", 1, "dize"), ("İkinci satır", 1, "dize"),
    ]
    assert bulgular(r, "Birinci satır. İkinci satır.", "UYARI", "<br>")


# ------------------------------------------------------------ 4. fiil listesi


def test_sokulmaz_istisnasi_maskelenir():
    a3 = '- **"silindir" sokulmaz.** "silindir şapka" doğrudur.\n'
    assert K.yasaklar(a3) == ["silindir"]
    assert K.istisnalar(a3) == ["silindir şapka"]
    r = sablon(a3=a3)
    assert not bulgular(r, "Silindir şapkasını taktı.", "HATA", "yasak kelime")


# ------------------------------------------------------------ 5. taninmayan


def test_taninmayan_yasak_uyarilir():
    assert K.taninmayan_yasaklar('- **"mahzen" yok**\n') == ['"mahzen" yok']
    assert K.taninmayan_yasaklar("**Örtük kalanlar**\n") == []
    r = sablon(a3='- **"mahzen" yok**\n')
    assert bulgular(r, "Metin.", "UYARI", "tanınmayan yasak")


# ------------------------------------------------------------ B, harf


def test_dondurulmus_sayi_harf_duyarlidir():
    # Bolum 47: "on küsur yıl" iki kez cumle basina dusuyordu; kalip ikinci
    # sozcukten baslayinca uc gecisin ucu de sayilir.
    metin = "On küsur yıldır. Bay Neil, on küsur yıldır. 'On küsur yıl' dedi."
    assert K.gecis_sayisi(metin, "on küsur yıl") == 1
    assert K.gecis_sayisi(metin, "küsur yıl") == 3



def test_kisa_izinli_terim_uzun_yasagi_korlestirmez():
    """
    REGRESYON: izinli karsiliklar metinden kelime sinirsiz SILINIYORDU.
    A.1'de "Ay" varken "aynalı" " nalı" oluyor, yasak hic bulunmuyordu.
    """
    r = sablon(a1="| Moon | Ay | — |\n", a3='- **"aynalı" yasaktır**\n')
    assert bulgular(r, "Klein aynalı kapıya baktı. Ay doğdu.", "HATA", "yasak kelime")
    r = sablon(a1="| cannon | top | — |\n", a3='- **"toplantı" yasaktır**\n')
    assert bulgular(r, "Bir toplantı yaptılar; top patladı.", "HATA", "yasak kelime")


@pytest.mark.parametrize("bas, son, araliklar, beklenen", [
    (0, 8, [(0, 14)], True),     # silindir <- silindir şapka
    (7, 13, [(0, 9)], True),     # ettiği <- havale et(tiği): izinli once basladi
    (0, 6, [(0, 2)], False),     # aynalı, izinli "Ay" ayni yerden ve kisa
    (5, 9, [(0, 4)], False),     # izinli aralik bitmeden baslamiyor
])
def test_izinli_icinde_mi(bas, son, araliklar, beklenen):
    assert K.izinli_icinde_mi(bas, son, araliklar) is beklenen
