# -*- coding: utf-8 -*-
"""lotm.desen_kur -- belirtisiz tamlamanin cogulu (pazar mektebi -> pazar mektepleri)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lotm  # noqa: E402


@pytest.mark.parametrize("terim, metin", [
    ("pazar mektebi", "pazar mektepleri"),
    ("pazar mektebi", "Kilise'nin pazar mekteplerinde hocalık"),
    ("pazar mektebi", "pazar mektebine"),              # korunur: tekil
    ("gaz lambası", "gaz lambaları"),
    ("gaz lambası", "gaz lambalarını söndürdü"),
    ("gaz lambası", "gaz lambasının"),                 # korunur
    ("cep saati", "cep saatlerinden"),
    ("öküzdişi şakayığı tozu", "öküzdişi şakayığı tozları"),
    ("Şeref Makamı", "Şeref Makamları"),
    ("güz çiğdemi özü", "güz çiğdemi özleri"),
    ("Ebedî Gece Tanrıçası Kilisesi", "Ebedî Gece Tanrıçası Kiliseleri'nin"),
])
def test_cogul_tamlama_eslesir(terim, metin):
    assert lotm.desen_kur(terim, harf_duyarli=False).search(metin)


@pytest.mark.parametrize("terim, metin", [
    ("cep saati", "cep saatçileri"),      # baska kelime
    ("gaz lambası", "gaz lamba"),         # iyeliksiz tamlama yok
    ("iki tekerlekli fayton", "iki tekerlekli faytonlar ve"),  # etkilenmez, zaten eslesir
])
def test_yan_etki_yok(terim, metin):
    beklenen = terim == "iki tekerlekli fayton"
    assert bool(lotm.desen_kur(terim, harf_duyarli=False).search(metin)) is beklenen


def test_tek_kelimede_uygulanmaz():
    # "idadi"nin -i'si kokun kendisi; tek kelimede cogul alternatifi uretilmez
    assert lotm._tamlama_koku("idadi") is not None           # sekil olarak uyar
    assert "idadl[ae]r" not in lotm._govde("idadi")           # ama kullanilmaz


@pytest.mark.parametrize("terim, metin", [
    ("tevdi etmek", "tevdi etti"),
    ("tevdi etmek", "tevdi ettiği işin"),
    ("tevdi etmek", "tevdi edildi"),
    ("havale etmek", "havale ettiği"),
    ("damgalamak", "damgaladı"),
    ("görülmek", "dava görüldü"),
    ("muhakeme edilmek", "muhakeme edildi"),
    ("Şirazesini Yitirmek", "şirazesini yitirdi"),
])
def test_mastar_terim_cekimli_eslesir(terim, metin):
    assert lotm.desen_kur(terim, harf_duyarli=False).search(metin)


@pytest.mark.parametrize("terim, metin", [
    ("ekmek", "ekler"),              # isim: kok kisa, genisletilmez
    ("taze ekmek", "taze elbise"),   # cok kelimeli ama hafif fiil degil
    ("parmak", "parlak"),
])
def test_isim_mastar_benzeri_genisletilmez(terim, metin):
    assert not lotm.desen_kur(terim, harf_duyarli=False).search(metin)


@pytest.mark.parametrize("terim, metin", [
    ("mühür", "sözleşmedeki mühre göz attı"),
    ("mühür", "Henüz bir mührü olmadığı için"),
    ("mühür", "mührünü bastı"),
    ("mühür", "mühürler"),                       # korunur: unsuz oncesi dusmez
    ("kayıt", "kaydını tuttu"),
    ("Rüzgâr Şehri", "Rüzgâr Şehirleri'nin"),    # tamlama cogulu + geri gelen unlu
    ("Rüzgâr Şehri", "Rüzgâr Şehri'nde"),        # korunur
])
def test_unlu_dusmesi(terim, metin):
    assert lotm.desen_kur(terim, harf_duyarli=False).search(metin)


def test_unlu_dusmesi_kapali_liste():
    # listede olmayan kelime genisletilmez: "kurum" "kurma" ile eslesmemeli
    assert not lotm.desen_kur("kurum", harf_duyarli=False).search("kurma zamanı")
    assert lotm._dusmus_desen("kurum") is None


@pytest.mark.parametrize("terim, metin", [
    ("aslî üye", "Babam Gece Şahinleri'nin bir aslî üyesiydi"),
    ("aslî üye", "aslî üyeydi"),
    ("aslî üye", "aslî üyesiyim"),
    ("aslî üye", "aslî üyeyken"),
    ("aslî üye", "aslî üyesiymiş"),
    ("aslî üye", "aslî üyesiydim"),
    ("Kâhin", "Kâhindi"),                    # korunur: unsuzden sonra y yok
    ("aslî üye", "aslî üyesidir"),           # korunur
])
def test_ekfiil(terim, metin):
    assert lotm.desen_kur(terim, harf_duyarli=False).search(metin)


@pytest.mark.parametrize("terim, metin", [
    ("Haz", "Haziran"),
    ("Bard", "bardak"),
    ("Yol", "Yolcu"),
])
def test_ekfiil_kirpik_eslesme_uretmez(terim, metin):
    assert not lotm.desen_kur(terim).search(metin)


@pytest.mark.parametrize("terim, metin", [
    ("libre", "on iki adet altı librelik top"),
    ("libre", "Gözleri dolaptaki bir librelik kuzu etine takıldı"),
    ("Sterlin", "iki yüz Sterlinlik bir iş"),
    ("Sterlin", "10 Sterlinlik ücret"),
    ("Sterlin", "otuz Sterlinliği vardı"),
])
def test_sayidan_sonra_olcu_eki(terim, metin):
    assert lotm.desen_kur(terim, harf_duyarli=False).search(metin)


@pytest.mark.parametrize("terim, metin", [
    ("İmparator", "Solomon İmparatorluğu"),     # sayi yok: baska kelime
    ("Aşkın", "Aşkınlık onu değiştirdi"),
    ("libre", "librelik bir şey"),              # sayi yok
])
def test_olcu_eki_sayisiz_eslesmez(terim, metin):
    assert not lotm.desen_kur(terim, harf_duyarli=False).search(metin)


@pytest.mark.parametrize("terim, metin", [
    ("vahiy", "ilahların ve ruhların vahyi"),
    ("vahiy", "vahye kulak verdi"),
    ("vahiy", "vahiyler"),                       # korunur: unsuz oncesi dusmez
])
def test_unlu_dusmesi_vahiy(terim, metin):
    assert lotm.desen_kur(terim, harf_duyarli=True).search(metin)


@pytest.mark.parametrize("metin", [
    "kızıl ayı simgeleyen bir daire",
    "Tanrıça'yı yalnızca iki mum simgeliyor",
    "bunun simgelediği şey",
    "iksirin simgesel anlamı",
    "simgeler",                                  # korunur: cogul
])
def test_turetme_simge(metin):
    assert lotm.desen_kur("simge", harf_duyarli=True).search(metin)


@pytest.mark.parametrize("terim, metin", [
    ("işaret", "işaretleyen"),                   # -lA- kapali liste: listede olmayan isim turemez
    ("simge", "simgecilik"),                     # yalniz kayitli turevler
])
def test_turetme_kapali_liste(terim, metin):
    assert not lotm.desen_kur(terim, harf_duyarli=True).search(metin)


def test_ozel_ad_tamlamasi_ilk_kelime_iyelik():
    d = lotm.desen_kur("Kontluk Polis Müdüriyeti", harf_duyarli=True)
    assert d.search("Awwa Kontluğu Polis Müdüriyeti, Loen Krallığı")
    assert d.search("Kontluk Polis Müdüriyeti'nden")       # korunur
    assert not d.search("dedi ki kontluğu Polis Müdüriyeti")  # onunde ozel ad yok


@pytest.mark.parametrize("terim, metin, eslesir", [
    ("arama çubuğu", "Arama Çubuğu Kehaneti'ne başvurdu", True),   # ozel ad icinde
    ("koyu kızıllık", "Koyu kızıllık usulca soldu.", True),        # korunur: cumle basi
    ("dolunay yağı", "Dolunay Yağı'nı aldı", False),               # imla kaymasi kalir
    ("dolunay yağı", "Dolunay Yağı şişesini", False),
])
def test_duyarsiz_ozel_ad_icindeki_ortak_isim(terim, metin, eslesir):
    assert bool(lotm.desen_kur(terim, harf_duyarli=False).search(metin)) is eslesir


def test_duyarli_dal_degismez():
    # yayim_denetle / hazirla duyarli dalda kucuk harfli bicimi bilerek sorar
    assert not lotm.desen_kur("arama çubuğu", harf_duyarli=True).search("Arama Çubuğu Kehaneti")
    assert not lotm.desen_kur("baston", harf_duyarli=True).search("Baston elindeydi.")


@pytest.mark.parametrize("terim, metin", [
    ("asıl Klein", "Asıl Klein'ın bariz bir not tutma alışkanlığı vardı."),
    ("Gri sislerin fevkindeki esrarlı Hükümdar", "sen gri sislerin fevkindeki esrarlı Hükümdarsın,"),
    ("Talihe hükmeden Sarı ve Siyahın Kralı", "sen talihe hükmeden Sarı ve Siyahın Kralısın."),
])
def test_yalniz_ilk_harf_degisen_bicim(terim, metin):
    assert lotm.desen_kur(terim, harf_duyarli=False).search(metin)


def test_duyarli_dal_degismez():
    # Yeni bicimler yalniz duyarsiz dalda; duyarli arama terimi oldugu gibi ister
    assert not lotm.desen_kur("asıl Klein", harf_duyarli=True).search("Asıl Klein")


@pytest.mark.parametrize("terim, metin", [
    ("grimsi beyaz sis", "grimsi beyaz bir sise sarılı"),
    ("habis ruh", "hatta habis bir ruha dönüşebilir"),
    ("yarım boy silindir şapka", "yarım boy bir silindir şapka"),
    ("iki tekerlekli fayton", "iki tekerlekli bir fayton geçiyordu"),
])
def test_araya_bir_girer(terim, metin):
    assert lotm.desen_kur(terim, harf_duyarli=False).search(metin)


@pytest.mark.parametrize("terim, metin", [
    ("habis ruh", "habis bir iki ruh"),      # yalniz tek "bir"
    ("habis ruh", "habisbir ruh"),           # kelime siniri korunur
    ("gaz lambası", "gaz birlambası"),
])
def test_bir_disinda_ara_kelime_yok(terim, metin):
    assert not lotm.desen_kur(terim, harf_duyarli=False).search(metin)
