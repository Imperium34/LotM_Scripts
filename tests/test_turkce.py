# -*- coding: utf-8 -*-
"""
turkce.py ve onu kullanan her yer.

Her vaka ya uc tuzaktan birinin kendisi (lower / casefold / IGNORECASE)
ya da o tuzagin belirli bir betikte urettigi somut hata. Depo gerektirmez.
"""

import re
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
# lint/ betikleri gercek depoda alt klasorde, duz bir kopyada kokte.
for yol in (KOK, KOK / "lint"):
    sys.path.insert(0, str(yol))

import turkce as T  # noqa: E402


# ------------------------------------------------------------ turkce.py


@pytest.mark.parametrize("girdi, beklenen", [
    ("IŞIK", "ışık"),
    ("Işık", "ışık"),
    ("İyi", "iyi"),
    ("I\u0307yi", "iyi"),        # ayrisik yazilmis İ
    ("Ayin İlmi", "ayin ilmi"),
    ("", ""),
    (None, ""),
])
def test_tr_kucult(girdi, beklenen):
    assert T.tr_kucult(girdi) == beklenen


def test_tr_kucult_uzunlugu_korur():
    s = "Işık İhtiyar Neil'ı gördü."
    assert len(T.tr_kucult(s)) == len(s)


@pytest.mark.parametrize("girdi, beklenen", [
    ("ışık", "Işık"), ("iyi", "İyi"), ("kanepe", "Kanepe"), ("", ""),
])
def test_tr_buyut(girdi, beklenen):
    assert T.tr_buyut(girdi) == beklenen


@pytest.mark.parametrize("desen, metin, eslesir", [
    ("ışık", "Işık", True),
    ("ışık", "IŞIK", True),
    ("ışık", "işik", False),     # IGNORECASE burada True verirdi
    ("Ayin", "ayın", False),     # lotm.desen_kur notundaki Bolum 9 vakasi
    ("Ayin", "AYİN", True),
    ("sıra", "sira", False),
    ("a.b", "axb", False),       # harf olmayanlar kacislanir
    ("straße", "STRASSE", False),  # cok karakterli buyuk harf: cokmez
])
def test_tr_desen(desen, metin, eslesir):
    assert bool(re.fullmatch(T.tr_desen(desen), metin)) is eslesir


def test_ignorecase_gercekten_yanlis():
    # Bu test Python'un davranisini belgeler: degisirse turkce.py'nin
    # gerekcesi de degismis demektir.
    assert re.fullmatch("Ayin", "ayın", re.IGNORECASE)


# ------------------------------------------------------------ lotm


def test_lotm_tek_tanim():
    import lotm
    assert lotm.tr_kucult is T.tr_kucult
    assert lotm._tr_kucult is T.tr_kucult
    assert lotm.tr_buyut is T.tr_buyut


def test_sozluk_ara_dile_gore_kucultur():
    import lotm
    s = lotm.Sozluk([
        lotm.Terim(tr="Demir Haç", en="Iron Cross"),
        lotm.Terim(tr="ışık", en="light"),
    ], veri={})
    # Eskiden tek Turkce kucultme Ingilizceye de uygulaniyordu:
    # "Iron" -> "ıron", yazilan "iron" bulunmuyordu.
    assert [t.tr for t in s.ara("iron")] == ["Demir Haç"]
    assert [t.tr for t in s.ara("IŞIK")] == ["ışık"]


def test_desen_kur_ayin_ayini_bulmaz():
    import lotm
    assert not lotm.desen_kur("Ayin", harf_duyarli=False).search("haziran ayının")
    assert lotm.desen_kur("Ayin", harf_duyarli=False).search("ayinin sonunda")


# ------------------------------------------------------------ kapanis_denetle


def test_izinli_ortme_i_ile_ii_ayirir():
    import kapanis_denetle as K
    assert K.izinli_araliklari("haziran ayının", ["ayin"]) == []
    assert K.izinli_araliklari("Işık yandı", ["ışık"]) == [(0, 4)]


# ------------------------------------------------------------ sozluk_lint


@pytest.fixture
def lint():
    pytest.importorskip("yaml")
    import sozluk_lint
    return sozluk_lint


def test_diyakritik_gruplama_ii_birlestirir(lint):
    # "İlâveten" ile "ilaveten" ayni kelimenin iki yazimi: tek grupta
    # raporlanmali. Kucultme diyakritik atmadan SONRA yapilsaydi "İ" once
    # "I"ya, sonra "ı"ya inerdi ve iki ayri gruba duserdi.
    rapor = lint.Rapor()
    lint.denetle_diyakritik(rapor, {"1.md": "İlâveten geldi. ilaveten gitti."}, {})
    assert len(rapor.bulgular) == 1
    assert "ilaveten" in rapor.bulgular[0].bulunan


def test_cumle_basi_i_diyakritik_sanilmaz(lint):
    rapor = lint.Rapor()
    lint.denetle_diyakritik(rapor, {"1.md": "Işık söndü. ışık yandı. hâlâ."}, {})
    assert not rapor.bulgular


def test_yasakli_i_ile_ii_ayirir(lint):
    kurallar = {"yasakli": [{"bicim": "sira", "yerine": "sıra"}]}
    temiz, kirli = lint.Rapor(), lint.Rapor()
    lint.denetle_yasakli(temiz, {"1.md": "Sıra ona geldi."}, kurallar)
    lint.denetle_yasakli(kirli, {"1.md": "Sira ona geldi."}, kurallar)
    assert not temiz.bulgular
    assert len(kirli.bulgular) == 1


# ------------------------------------------------------------ ceviri_denetle


def test_kesif_govdesi_cumle_basini_ayirmaz():
    import ceviri_denetle as C
    assert C._kok("Işık") == C._kok("ışık")
    assert C._kok("İhtiyar") == C._kok("ihtiyar")
    assert C._kok("Iron", "en") == C._kok("iron", "en")


# ------------------------------------------------------------ yayim_denetle


@pytest.mark.parametrize("metin, eslesir", [
    ("Sıra", True), ("sira", False), ("AŞKIN", True), ("aşkin", False),
    ("İksir", True), ("POTION", True),
])
def test_ipucu(metin, eslesir):
    import yayim_denetle as Y
    assert bool(Y.IPUCU_RE.search(metin)) is eslesir


# ------------------------------------------------------------ sapka


def test_sapka_buyuk_harf_bicimi():
    import sapka
    assert sapka.bicimler("imkan") == [("imkan", "imkân"), ("İmkan", "İmkân")]


def test_diyakritik_esadlilari_rapor_etmez(lint, capsys):
    rapor = lint.Rapor()
    lint.denetle_diyakritik(rapor, {"1.md": "sekiz adet banknot; eski bir âdet. "
                                             "Resmi baş aşağıydı; resmî bir üye."}, {})
    assert not rapor.bulgular
    assert "2 eşadlı çift atlandı" in capsys.readouterr().err
    rapor = lint.Rapor()
    lint.denetle_diyakritik(rapor, {"1.md": "İlâveten geldi. ilaveten gitti."}, {})
    assert len(rapor.bulgular) == 1   # gercek yazim farki hala raporlanir
