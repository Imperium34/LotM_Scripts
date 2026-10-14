# -*- coding: utf-8 -*-
"""ayrilmis.py -- ayrilmis sozcuk dizini ve carpisma aramasi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ayrilmis as A  # noqa: E402
import lotm  # noqa: E402


def _k(tr, en=None, zh=None, notu="", kategori="words.md › Objects"):
    return lotm.Terim(tr=tr, en=en, zh=zh, kategori=kategori, cevirmen_notu=notu)


def test_yasak_notlari_ayiklanir():
    # words.md'nin gercek not bicimleri
    terimler = [
        _k("kâhin", notu='fortune-teller (占卜者); "falcı" kullanılmaz _48_'),
        _k("ibadet", notu='Mass (弥撒); "ayin" 仪式\'e ayrılı olduğu için kullanılamaz _50_'),
        _k("gümüş kutu", notu='small silver case (银制小箱); "sandık", "çanta" değil _50_'),
        _k("kehanet gök haritası",
           notu='star chart (占卜星盘); İng. çeviri "astrolabe" der, "usturlap" kullanılmaz _40_'),
        _k("Tanrı'ya minnettarım", notu='Thank God (感谢神); "şükür/hamd" Kadir-i Mutlak grubu kiliselerine ayrılı'),
        _k("Hokkabaz", notu='The Magician (魔术师) — "Büyücü" KULLANILMAZ'),
    ]
    yasak = {k.kelime for t in terimler for k in A.yasak_kayitlari(t)}
    assert yasak == {"falcı", "ayin", "sandık", "çanta", "usturlap", "şükür", "hamd", "Büyücü"}


def test_zayif_degil_yalniz_onundeki_tirnagi_yasaklar():
    # '"gümüş bıçak" (çakı değil)': izinli bicim yasaklanmaz; "değilse" iz degil.
    terimler = [
        _k("gümüş Ayin hançeri",
           notu='ritual dagger (仪式银匕); aynı nesne anlatıda 银制小刀 olarak geçtiğinde '
                '"gümüş bıçak" (çakı değil) _51_'),
        _k("kurtçuk", notu='maggot (蛆虫); Zaman Kurtçuğu ile aynı baş kelime, teyit bekliyor '
                          '(değilse "sürfe") _55_'),
        _k("şömine", notu='fireplace (壁炉); İng. çeviri "chimney" der, "baca" değil'),
    ]
    yasak = {k.kelime for t in terimler for k in A.yasak_kayitlari(t)}
    assert yasak == {"baca"}


def test_kayitlar_turleri_ve_tek_kelime_kurali():
    mertebe = lotm.Terim(tr="Gemici", en="Seafarer", zh="航海家", kategori="Aşkın Yolları",
                         yol="Denizci Yolu", seviye=7)
    kavram = lotm.Terim(tr="Ayin", en="Ritual", zh="仪式", kategori="Temel Kavramlar",
                        eski_karsiliklar=["ritüel"])
    kelimeler = [
        _k("kanepe", "sofa", "沙发"),
        _k("kabul salonu", "reception lobby", "接待厅"),  # cok kelimeli: dizine girmez
        _k("整个人", notu="çoğunlukla düşer"),               # Turkce degil: girmez
    ]
    sal = [{"cince": "厄难", "turkce": "Şeamet", "tur": "salahiyet"}]
    ks = A.kayitlar([mertebe, kavram], kelimeler, sal)
    tur = {(k.kelime, k.tur) for k in ks}
    assert tur == {("Gemici", "mertebe"), ("ritüel", "eski"), ("Şeamet", "salahiyet"),
                   ("Ayin", "kavram"), ("kanepe", "kelime")}
    assert next(k for k in ks if k.kelime == "Gemici").sahip == "Denizci Yolu 7"


def test_icerenler_ekli_bicim_uzun_once_ve_buyuk_harf():
    ks = [
        A.Ayrilmis("Gizem Avcısı", "mertebe", "Gizem Avcısı Yolu 9"),
        A.Ayrilmis("Avcı", "mertebe", "Avcı Yolu 9"),
        A.Ayrilmis("Gemici", "mertebe", "Denizci Yolu 7"),
        A.Ayrilmis("Ay", "mertebe", "Aktar Yolu 0"),
        A.Ayrilmis("falcı", "yasak", "kâhin", not_='"falcı" kullanılmaz'),
    ]
    metin = "Gizem Avcısı, Gemicinin ay ışığında falcıya gittiğini gördü."
    bulunan = [(metin[a:b], k.kelime) for k, (a, b) in A.icerenler(metin, ks)]
    assert bulunan == [("Gizem Avcısı", "Gizem Avcısı"), ("Gemicinin", "Gemici"),
                       ("falcıya", "falcı")]


def test_dizin_yol_sirasi_ve_bolumler():
    ks = [A.Ayrilmis(ad, "mertebe", f"Denizci Yolu {s}", en)
          for ad, s, en in [("Gemici", 7, "Seafarer"), ("Denizci", 9, "Sailor")]]
    ks.append(A.Ayrilmis("falcı", "yasak", "kâhin", not_='"falcı" kullanılmaz'))
    md = A.dizin_md(ks)
    assert "- **Denizci Yolu:** 9 Denizci (Sailor) · 7 Gemici (Seafarer)" in md
    assert '- **falcı** — "falcı" kullanılmaz  ·  madde: kâhin' in md
    assert md.index("## 1.") < md.index("## 2.")
