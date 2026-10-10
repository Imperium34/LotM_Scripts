# -*- coding: utf-8 -*-
"""
yayim_denetle -- kapi adaylarinda cumle basi ve words.md maskesi.

Gercek bulgulardan: "Kusura bakmayın" (Kusur), "Kadın erkek" (Kadı),
"Ölümünün" (Ölüm) cumle basinda buyuk harf almis siradan kelimelerdi;
"Savaşçı ve Deniz Tavernası" bir meyhane adiydi.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lotm  # noqa: E402
import yayim_denetle as Y  # noqa: E402


def _kayitlar(*terimler):
    return Y.kayitlari_kur(lotm.Sozluk(list(terimler), veri={}))


def _bolum(no, metin):
    return SimpleNamespace(no=no, metin=metin, kaynak=f"{no:04d}.md")


def _adaylar(kayitlar, bolumler, maske=()):
    kapi = Y.denetle(kayitlar, bolumler, maske=maske).kapi
    return {(no, k.tr) for _g, no, _d, k, _c in kapi}


KADI = lotm.Terim(tr="Kadı", en="Arbiter", kategori="Arabulucu Yolu", bolum_siniri=674)
KUSUR = lotm.Terim(tr="Kusur", en="Error", kategori="Kapkaççı Yolu", bolum_siniri=1152)
OLUM = lotm.Terim(tr="Ölüm", en="Death", kategori="İlahlar", bolum_siniri=931)
SAVASCI = lotm.Terim(tr="Savaşçı", en="Warrior", kategori="Savaşçı Yolu", bolum_siniri=138)


def test_cumle_basindaki_siradan_kelime_aday_degil():
    bolumler = [
        _bolum(25, "Piskopos kapıyı açtı. Kadın erkek sıraya girdi. Bir kadın ağladı."),
        _bolum(5, 'Konuştu. "Kusura bakmayın," dedi. Hiç kusuru yoktu.'),
        _bolum(46, '"Ölümünün üzerinden beş gün geçmiş." Bu ölüm tuhaftı.'),
    ]
    assert _adaylar(_kayitlar(KADI, KUSUR, OLUM), bolumler) == set()


def test_eleme_envanteri_etkilemez():
    # Kucuk harfle de yazilan gercek terim: cumle basindaki "İksiri" envantere girer
    iksir = lotm.Terim(tr="İksir", en="Potion", kategori="Temel Kavramlar", bolum_siniri=0)
    bolumler = [_bolum(28, "Sessizlik. İksiri içtikten sonra bir iksir daha istedi.")]
    b = Y.denetle(_kayitlar(iksir), bolumler)
    assert b.envanter["İksir"] == [28] and b.kapi == []


def test_kesme_ozel_ad_isaretidir_cumle_basinda_bile():
    bolumler = [
        _bolum(28, "Güney Kıtası'nda Ölüm'e tapan pek çok tarikatçı vardır."),   # cumle ici
        _bolum(30, "Sessizlik oldu. Ölüm'ün kilisesi yıkılmıştı. Her ölüm acıdır."),  # basta, kesmeli
    ]
    assert _adaylar(_kayitlar(OLUM), bolumler) == {(28, "Ölüm"), (30, "Ölüm")}


def test_kucuk_harfle_hic_gecmeyen_terim_cumle_basinda_da_aday():
    # "kadı" / "kadın" metinde kucuk harfle yoksa buyuk harf konumdan gelmiyor olabilir
    bolumler = [_bolum(25, "Salon doldu. Kadı yerine oturdu.")]
    assert _adaylar(_kayitlar(KADI), bolumler) == {(25, "Kadı")}


def test_words_md_uzun_adi_icindeki_terimi_ortuyor():
    bolumler = [_bolum(7, "Pelikan Sokağı'nda yer alan Savaşçı ve Deniz Tavernasından içeri yollayın.")]
    k = _kayitlar(SAVASCI)
    assert _adaylar(k, bolumler) == {(7, "Savaşçı")}                      # maskesiz
    maske = [lotm.desen_kur("Savaşçı ve Deniz Tavernası")]
    assert _adaylar(k, bolumler, maske=maske) == set()                     # maskeli


def test_cumle_basi_deseni():
    for onceki, beklenen in [('konuştu. "', True), ("dedi.\n\n", True), ("_", True),
                             ("bir şey ", False), ("Güney Kıtası'nda ", False)]:
        assert bool(Y.CUMLE_BASI.search(onceki)) is beklenen, onceki


AYIN = lotm.Terim(tr="Ayin", en="Ritual", kategori="Temel Kavramlar", bolum_siniri=22,
                  eski_karsiliklar=["ritüel"])
AYIN_ILMI = lotm.Terim(tr="Ayin İlmi", en="Ritualistic Magic", kategori="Temel Kavramlar",
                       bolum_siniri=33)


def test_gecisten_once_yeni_bicim_bakilacak():
    # Lint'teki eski Ritual kuralinin "yeni kelime gecisten once" uyarisinin
    # yerini alan denetim: harf duyarsiz, daha uzun terimin icindeki sayilmaz.
    bolumler = [
        _bolum(9, "Hazırlık sürdü. Bu ayinlerinde dikkatli ol."),       # erken, kucuk harf
        _bolum(10, "Ayin İlmi'nin bir tezahürü."),                    # uzun terimin parcasi
        _bolum(30, "Ayin bitti."),                                     # gecisten sonra
    ]
    erken = Y.denetle(_kayitlar(AYIN, AYIN_ILMI), bolumler).erken_yeni
    assert [(no, bulunan) for no, _d, _k, bulunan, _c in erken] == [(9, "ayinlerinde")]


def test_eski_bicim_gecise_gore_ayrilir():
    # Eskiden bu ayrim main()'deydi; testten erisilemiyordu.
    bolumler = [
        _bolum(9, "Bir ritüel yaptılar."),     # gecisten once: donemin kelimesi
        _bolum(40, "Yine ritüel yaptılar."),   # gecisten sonra: eskimis
    ]
    b = Y.denetle(_kayitlar(AYIN), bolumler)
    assert [v[0] for v in b.gecis_oncesi] == [9]
    assert [v[0] for v in b.eskimis] == [40]


def test_gecissiz_terimin_eski_bicimi_her_yerde_eskimis():
    olagan = lotm.Terim(tr="Sıradışı", en="Beyonder", kategori="Kavramlar",
                        eski_karsiliklar=["olağanüstü"])          # bolum_siniri yok
    b = Y.denetle(_kayitlar(olagan), [_bolum(2, "Bir olağanüstü gördü.")])
    assert [v[0] for v in b.eskimis] == [2] and b.gecis_oncesi == []
