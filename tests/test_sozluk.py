# -*- coding: utf-8 -*-
"""
Etiket ayirma ve Terim kayitlari.

'Turkce (English)' ayirmasinin dort ayri kopyasi vardi, dort farkli
davranisla. Tek tanim kaldi; bu testler onun sozlesmesi.
"""

import pytest


@pytest.mark.parametrize("ham,beklenen", [
    ("Çırak (Seer)", "Çırak"),
    ("Kutsayan Amon (Melekler Kralı)", "Kutsayan Amon"),
    ("Sıradışı", "Sıradışı"),
    ("", ""),
    (None, ""),
])
def test_parantezsiz(ham, beklenen):
    import lotm
    assert lotm.parantezsiz(ham) == beklenen


@pytest.mark.parametrize("ham,beklenen", [
    ("Çırak (Seer)", "Seer"),
    ("Gizem Avcısı (Mystery Pryer / Pugilist)", "Mystery Pryer / Pugilist"),
    ("Sıradışı", None),
    (None, None),
])
def test_ingilizce_ayikla(ham, beklenen):
    import lotm
    assert lotm.ingilizce_ayikla(ham) == beklenen


@pytest.mark.parametrize("ham,beklenen", [
    ("Blasphemer Amon (King of Angels)", ["Blasphemer Amon", "King of Angels"]),
    ("Historical Void / Fog of History", ["Historical Void", "Fog of History"]),
    ("Pugilist / Gladiator", ["Pugilist", "Gladiator"]),
    ("Seer", ["Seer"]),
    ("", []),
])
def test_etiket_temizle(ham, beklenen):
    import lotm
    assert lotm.etiket_temizle(ham) == beklenen


def test_varyantlar():
    import lotm
    assert lotm.varyantlar("Grave Digger") >= {"Grave Digger", "GraveDigger",
                                               "Grave-Digger"}
    assert lotm.varyantlar("Wind-Blessed") >= {"Wind-Blessed", "Wind Blessed",
                                               "WindBlessed"}
    assert "Fool" in lotm.varyantlar("The Fool")
    assert all(len(v) >= 3 for v in lotm.varyantlar("The Fool"))


# ------------------------------------------------------------------ Terim

def test_mertebe_terimi_alanlari(lotm_modulu, sozluk_dosyasi):
    lotm = lotm_modulu
    s = lotm.sozluk_yukle(sozluk_dosyasi)
    cirak = next(t for t in s.terimler if t.tr == "Çırak")
    assert cirak.en == "Seer"
    assert cirak.zh == "占卜家"
    assert cirak.yol == "Görücü"
    assert cirak.seviye == 9
    assert cirak.bolum_siniri == 3
    assert cirak.mertebe_mi
    assert cirak.yer == "Görücü S9"


def test_cok_adli_mertebede_en_ilk_ad_ama_arama_ikisini_de_gorur(
        lotm_modulu, sozluk_dosyasi):
    """
    'en' tek bir kanonik ada indirgenir; tarama ise ikinci adi da
    gormelidir. Migrasyondan once bu bilgi kayboluyordu.
    """
    lotm = lotm_modulu
    s = lotm.sozluk_yukle(sozluk_dosyasi)
    gizem = next(t for t in s.terimler if t.tr == "Gizem Avcısı")
    assert gizem.en == "Mystery Pryer"
    assert "Mystery Pryer / Pugilist" in gizem.en_ham


def test_ust_duzey_parantez_ici_ad_aramada_kalir(lotm_modulu, sozluk_dosyasi):
    lotm = lotm_modulu
    s = lotm.sozluk_yukle(sozluk_dosyasi)
    amon = next(t for t in s.terimler if t.tr == "Kutsayan Amon")
    assert amon.en == "Blasphemer Amon"
    assert "King of Angels" in amon.arama_adaylari()


def test_arama_adi_adaylari_ezer_ama_anahtari_ezmez(lotm_modulu, sozluk_dosyasi):
    """
    ANAHTAR kanonik Ingilizce addir, arama_adi degil.

    Eskiden searcher.py raporu arama_adi[0] ile anahtarliyor, etiketle.py
    ise parantez icindeki adla ariyordu; ikisi farkli oldugunda terim
    'raporda yok' sayilip sessizce hic etiketlenmiyordu.
    """
    lotm = lotm_modulu
    s = lotm.sozluk_yukle(sozluk_dosyasi)
    gizem = next(t for t in s.terimler if t.tr == "Gizem Avcısı")
    assert gizem.arama_adaylari() == ["Mystery Pryer"] or \
        set(gizem.arama_adaylari()) >= {"Mystery Pryer"}
    assert gizem.anahtar == "Mystery Pryer" == gizem.en


def test_yol_girdisinin_kendisi_de_terim(lotm_modulu, sozluk_dosyasi):
    lotm = lotm_modulu
    s = lotm.sozluk_yukle(sozluk_dosyasi)
    assert any(t.tr == "Görücü" and not t.mertebe_mi for t in s.terimler)


def test_kardesler_kendini_icermez(lotm_modulu, sozluk_dosyasi):
    lotm = lotm_modulu
    s = lotm.sozluk_yukle(sozluk_dosyasi)
    for t in s.terimler:
        assert t.tr not in t.kardesler_tr


def test_ara_uc_dilde_de_bulur(lotm_modulu, sozluk_dosyasi):
    lotm = lotm_modulu
    s = lotm.sozluk_yukle(sozluk_dosyasi)
    assert any(t.tr == "Sıradışı" for t in s.ara("Beyonder"))
    assert any(t.tr == "Sıradışı" for t in s.ara("sıradışı"))
    assert any(t.tr == "Sıradışı" for t in s.ara("非凡者"))


def test_tek_kelime_ozelligi(lotm_modulu, sozluk_dosyasi):
    lotm = lotm_modulu
    s = lotm.sozluk_yukle(sozluk_dosyasi)
    assert next(t for t in s.terimler if t.tr == "Çırak").tek_kelime
    assert not next(t for t in s.terimler if t.tr == "Gizem Avcısı").tek_kelime


def test_kardesler_en_ingilizce_ve_kendisi_haric(sozluk_dosyasi):
    import lotm
    t = {x.tr: x for x in lotm.sozluk_yukle(sozluk_dosyasi).terimler}
    # cok adli mertebe: iki adi da kendisidir, kardes sayilmaz
    assert t["Gizem Avcısı"].kardesler_en == ["Seer", "Clown"]
    assert t["Çırak"].kardesler_en == ["Clown", "Mystery Pryer", "Pugilist"]


def test_kapi_kardes_ipucu_ingilizce_metinde_calisir(sozluk_dosyasi):
    """
    REGRESYON: kapi_denetle Turkce kardes adlarini ("Gizem Avcısı")
    Ingilizce metinde ariyordu; ipucu hic tutmuyordu.
    """
    import kapi_denetle as K
    terimler = K.terimleri_topla(sozluk_dosyasi)
    metin = "He was a Clown now. Next would come the Mystery Pryer, said Dunn."
    konum = metin.index("Clown")
    assert K.guven("Clown", terimler["Clown"], metin, konum) == K.YUKSEK
    assert K.guven("Clown", terimler["Clown"], "He was a Clown now.", 8) == K.ORTA



def test_ara_eski_karsiligi_ve_arama_adini_bulur(sozluk_dosyasi):
    """Terk edilmis bir bicimi aramak, yerine gecen terimi bulmali."""
    import lotm
    s = lotm.sozluk_yukle(sozluk_dosyasi)
    assert [t.tr for t in s.ara("olağanüstü")] == ["Sıradışı"]   # eski_karsiliklar
    assert [t.tr for t in s.ara("Falcı")] == ["Kâhin"]           # mertebe eski karsiligi
    assert [t.tr for t in s.ara("Mystery Pryer")] == ["Gizem Avcısı"]
