# -*- coding: utf-8 -*-
"""
lotm.desen_kur -- tembel vekil + on suzgec + kucultulmus desen.

Vekil (lotm._Desen) re.Pattern ile ayni sonucu vermeli; on suzgec GEREKLI
kosul olmali (yanlis eksik = denetleyicide sessiz kacirma); desen ayni
EK blogunu tekrar tekrar tasimamali (derleme suresi buna bagli).
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lotm  # noqa: E402

# (terim, harf_duyarli, metin): desen metinde eslesmeli
ORNEKLER = [
    ("Kâhin", True, "Kâhin'i gördü"),
    ("Kâhin", True, "Kâhini gördü"),
    ("Kâhin", False, "Kâhin geldi"),
    ("Kâhin", False, "kâhinler toplandı"),
    ("Kontluk Polis Müdüriyeti", True, "Awwa Kontluğu Polis Müdüriyeti'ne gitti"),
    ("Kontluk Polis Müdüriyeti", False, "Awwa Kontluğu Polis Müdüriyeti"),
    ("mühür", False, "mührü kırdı"),
    ("mühür", False, "mühre baktı"),
    ("kayıt", False, "kaydı sildi"),
    ("kayıt", False, "kayıtlar"),
    ("pazar mektebi", False, "pazar mektepleri"),
    ("pazar mektebi", False, "Pazar mektebi'nde"),
    ("Rüzgâr Şehri", False, "Rüzgâr Şehirleri'nde"),
    ("Rüzgâr Şehri", True, "Rüzgâr Şehri"),
    ("işaret etmek", False, "işaret etti"),
    ("işaret etmek", False, "işaret edildi"),
    ("işaret etmek", False, "işaret ederek"),
    ("et-", False, "edildi"),
    ("et-", False, "etti"),
    ("simge", True, "simgeliyor"),
    ("simge", True, "simgeleyen"),
    ("simge", True, "simgesel bir şey"),
    ("Sterlin", True, "iki yüz Sterlinlik ücret"),
    ("Sterlin", True, "5 Sterlinlik"),
    ("Sterlin", False, "üç sterlinlik"),
    ("Işık", False, "ışığı söndürdü"),
    ("Işık", False, "Işığı"),
    ("İnsan", False, "insanlar geldi"),
    ("İnsan", False, "İnsanlar"),
    ("ılık su", False, "ılık suyu içti"),
    ("iyi niyet", False, "iyi bir niyet"),
    ("Arama Çubuğu Kehaneti", False, "Arama Çubuğu Kehaneti'ne başvurdu"),
    ("arama çubuğu", False, "Arama Çubuğu Kehaneti'ne başvurdu"),
    ("arama çubuğu", False, "arama çubuğunu aldı"),
    ("şirazesini yitirmek", False, "şirazesini yitirdi"),
    ("gaz lambası", False, "gaz lambalarını söndürdü"),
    ("cep saati", False, "cep saatlerinden"),
    ("Klein", True, "Klein'ın gözleri"),
    ("sis", True, "sisler"),
]

# (terim, harf_duyarli, metin): eslesmemeli (vekil de derlenmis desen de)
OLMAYANLAR = [
    ("Ayin", False, "haziran ayının"),
    ("Kâhin", True, "kâhinler"),
    ("cep saati", False, "cep saatçileri"),
    ("Kâhin", True, ""),
    ("simge", True, "bambaşka bir metin"),
]


def _gercek(terim, hd):
    return re.compile(lotm.desen_kur(terim, hd).pattern)


@pytest.mark.parametrize("terim, hd, metin", ORNEKLER)
def test_ornek_eslesir_ve_on_suzgec_izin_verir(terim, hd, metin):
    d = lotm.desen_kur(terim, hd)
    assert _gercek(terim, hd).search(metin), "ornegin kendisi yanlis"
    assert d.olabilir_mi(metin)  # gerekli kosul: eslesen metin elenemez
    assert d.search(metin)


@pytest.mark.parametrize("terim, hd, metin", OLMAYANLAR)
def test_olmayan_vekilde_de_olmaz(terim, hd, metin):
    assert not lotm.desen_kur(terim, hd).search(metin)
    assert not _gercek(terim, hd).search(metin)


METINLER = [
    "",
    "Kâhin'i ve kâhinleri, KÂHİN, iki yüz Sterlinlik ücret; sterlin.",
    "Awwa Kontluğu Polis Müdüriyeti'ne gitti. Mührü kırdı, kaydı sildi.",
    "pazar mektepleri; Rüzgâr Şehirleri; işaret etti; edildi; simgeliyor.",
    "hiçbiri yok burada, düz bir cümle",
]


@pytest.mark.parametrize("terim, hd", [
    ("Kâhin", True), ("Kâhin", False), ("Sterlin", True), ("mühür", False),
    ("pazar mektebi", False), ("et-", False), ("simge", True),
    ("Kontluk Polis Müdüriyeti", False), ("olmayan bir terim", True),
])
@pytest.mark.parametrize("metin", METINLER)
def test_vekil_derlenmis_desenle_ayni_sonucu_verir(terim, hd, metin):
    d, g = lotm.desen_kur(terim, hd), _gercek(terim, hd)
    for pos, endpos in ((0, len(metin)), (3, len(metin)), (0, max(len(metin) - 4, 0)), (5, 20)):
        a, b = d.search(metin, pos, endpos), g.search(metin, pos, endpos)
        assert (a and a.span()) == (b and b.span())
        assert [m.span() for m in d.finditer(metin, pos, endpos)] == [
            m.span() for m in g.finditer(metin, pos, endpos)
        ]
        assert d.findall(metin, pos, endpos) == g.findall(metin, pos, endpos)
        a, b = d.match(metin, pos, endpos), g.match(metin, pos, endpos)
        assert (a and a.span()) == (b and b.span())
        a, b = d.fullmatch(metin, pos, endpos), g.fullmatch(metin, pos, endpos)
        assert (a and a.span()) == (b and b.span())
    assert d.sub("<>", metin) == g.sub("<>", metin)
    assert d.sub("<>", metin, count=1) == g.sub("<>", metin, 1)
    assert d.subn("<>", metin) == g.subn("<>", metin)
    assert d.split(metin) == g.split(metin)
    assert d.split(metin, maxsplit=1) == g.split(metin, 1)


def test_eslesmeyen_metinde_derlenmez_ve_sonuclar_aynidir():
    d = lotm._Desen("Zırzopçu", True, lotm._ipuclari("Zırzopçu", True))
    metin = "bambaşka bir metin"
    assert d.search(metin) is None and d.match(metin) is None and d.fullmatch(metin) is None
    assert list(d.finditer(metin)) == [] and d.findall(metin) == []
    assert d.sub("x", metin) is metin
    assert d.subn("x", metin) == (metin, 0)
    assert d.split(metin) == [metin]
    assert not d.derlendi_mi()
    assert d.pattern and not d.derlendi_mi()  # .pattern derlemeden hazir
    assert d.search("Zırzopçu geldi")
    assert d.derlendi_mi()


def test_diger_ozellikler_derlenmis_desene_gecer():
    d = lotm._Desen("Kâhin", True, lotm._ipuclari("Kâhin", True))
    assert d.groups == 0 and d.flags == re.compile(d.pattern).flags
    assert d.derlendi_mi()


def test_oneleme_ortam_degiskeni_suzgeci_kapatir(monkeypatch):
    kur = lambda: lotm._Desen("Zırzopçu", True, lotm._ipuclari("Zırzopçu", True))
    d = kur()
    assert d.ipucu and not d.olabilir_mi("alakasiz")
    monkeypatch.setenv("LOTM_ONELEME", "0")
    d2 = kur()
    assert d2.olabilir_mi("alakasiz")
    assert d2.search("alakasiz") is None
    assert d2.derlendi_mi()  # suzgec kapali: hep derler


def test_ipuclari_turetimi():
    f = lotm._ipuclari
    assert f("Kâhin", True) == ("Kâhi",)
    assert f("Kâhin", False) == ("kâhi",)
    assert f("Kontluk Polis Müdüriyeti", True) == ("Kontlu", "Poli", "Müdüriye")
    # duzensiz son kelime: fiil kokunun / dusmus unlunun / tamlama kokunun payi
    assert f("işaret etmek", True) == ("işare",)  # 'etmek' -> 'e' bir harf, atilir
    assert f("mühür", True) == ("müh",)  # dusmus: kelime[:-2]
    assert f("pazar mektebi", True) == ("paza", "mekte")
    assert f("a", True) == ()  # 2 harften kisa onek yok
    assert f("", False) == ()
    # harf duyarsizda katlanmis: buyuk/kucuk bicimlerin hepsi tek ipucuna iner
    assert f("Işık", False) == ("ışı",)
    # baglama bagli kucultme: suzgec yok
    assert f("ΣΟΦΟΣ", False) == ()


def test_katlama_harf_harfinedir():
    assert lotm._katla("İIıi") == "iııi"
    assert lotm._katla("Kâhin") == "kâhin"


def test_uc_kelimelik_duyarsiz_desen_kucuk():
    # Eskiden 16 kopya (bicim basina ayri); ortak kuyruklar toplandi.
    d = lotm.desen_kur("Arama Çubuğu Kehaneti", harf_duyarli=False)
    assert d.pattern.count(lotm.EK) <= 6
    # tek kelime, 4 bicim: EK iki kez (ana dal + olcu)
    assert lotm.desen_kur("Kâhin", harf_duyarli=False).pattern.count(lotm.EK) <= 2


def test_govde_eski_imzasiyla_calisir():
    assert lotm._govde("Kâhin").endswith(lotm.EK)
    assert lotm._govde("Kâhin", olcu=True).endswith(lotm.OLCU_EKI + lotm.EK)
