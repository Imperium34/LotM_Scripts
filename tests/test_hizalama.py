# -*- coding: utf-8 -*-
"""
Paragraf hizalamasi (bolum.hizala).

bolum.py'nin docstring'i neden kural degil hizalama kullanildigini
anlatiyor: konusma etiketi bazen tirnakla birlestirilir, bazen
birlestirilmez, ve karar cevirmenindir. Buradaki testler hizalayicinin
o kararlari VERIDEN cikarabildigini dogrular.
"""

import pytest


def _grup_tipleri(gruplar):
    return [(len(a), len(b)) for a, b in gruplar]


def test_ayni_uzunluktaki_metinler_birebir_hizalanir():
    import bolum
    a = ["Birinci paragraf burada.", "Ikinci paragraf biraz daha uzun.",
         "Ucuncu."]
    b = ["First paragraph here.", "Second paragraph is a bit longer.",
         "Third."]
    assert _grup_tipleri(bolum.hizala(a, b)) == [(1, 1), (1, 1), (1, 1)]


def test_birlestirilmis_paragraf_2_1_olarak_cozulur():
    """
    Kaynakta konusma etiketi ayri paragrafta, hedefte tirnakla
    birlestirilmis. Hizalayici bunu "neden" oldugunu bilmeden bulmali.
    """
    import bolum
    a = ["Klein basini kaldirdi ve sordu:",
         "\"Bu ayin bedeli ne kadar olacak?\"",
         "Audrey defterini kapatti ve pencereye dogru dondu."]
    b = ["Klein looked up and asked, \"How much will this ritual cost?\"",
         "Audrey closed her notebook and turned toward the window."]
    tipler = _grup_tipleri(bolum.hizala(a, b))
    assert (2, 1) in tipler, f"birlestirme bulunamadi: {tipler}"


def test_bolunmus_paragraf_1_2_olarak_cozulur():
    import bolum
    a = ["Klein looked up and asked, \"How much will this ritual cost?\"",
         "Audrey closed her notebook."]
    b = ["Klein basini kaldirdi ve sordu:",
         "\"Bu ayin bedeli ne kadar olacak?\"",
         "Audrey defterini kapatti."]
    assert (1, 2) in _grup_tipleri(bolum.hizala(a, b))


def test_tum_indisler_tam_bir_kez_kullanilir():
    """Hicbir paragraf dusmemeli, hicbiri iki kez sayilmamali."""
    import bolum
    a = [f"Kaynak paragraf numara {i}, biraz dolgu metni." for i in range(9)]
    b = [f"Target paragraph number {i}, with some filler." for i in range(7)]
    gruplar = bolum.hizala(a, b)
    ia = [i for g, _ in gruplar for i in g]
    ib = [i for _, g in gruplar for i in g]
    assert sorted(ia) == list(range(len(a)))
    assert sorted(ib) == list(range(len(b)))


def test_sira_korunur():
    import bolum
    a = [f"Paragraf {i} icin yeterince uzun bir metin." for i in range(6)]
    b = [f"Paragraph {i} with enough text to match." for i in range(6)]
    gruplar = bolum.hizala(a, b)
    ia = [i for g, _ in gruplar for i in g]
    assert ia == sorted(ia)


def test_bos_taraf_cokmez():
    import bolum
    assert bolum.hizala([], []) == []
    gruplar = bolum.hizala(["tek paragraf"], [])
    assert [i for g, _ in gruplar for i in g] == [0]


def test_sirayla_kisa_tarafta_bos_liste_verir():
    """
    sirayla() tek tarafli eslesmeleri BOS LISTE ile bildirir; ic_ice()
    ona gore atlar. hizala()'nin savunma amacli geri dusmesi de artik
    bunu kullaniyor (eskiden max(n,m) kadar indis uretip kisa tarafta
    IndexError veriyordu).
    """
    import bolum
    gruplar = bolum.sirayla(["a", "b", "c"], ["x"])
    assert gruplar[1][1] == []
    assert gruplar[2][1] == []
    for _, ib in gruplar:
        for i in ib:
            assert i < 1


def test_paragraflar_bos_satirla_ayrilan_metni_boler():
    import bolum
    metin = "Birinci.\n\nIkinci satiri\ndevam ediyor.\n\nUcuncu."
    p = bolum.paragraflar(metin)
    assert len(p) == 3
    assert p[1] == "Ikinci satiri devam ediyor."


def test_paragraflar_bos_satirsiz_cince_metni_satir_satir_boler():
    """Cince ham metinde her paragraf tek satirdir, arada bos satir yoktur."""
    import bolum
    metin = "第一行。\n第二行。\n第三行。"
    assert len(bolum.paragraflar(metin)) == 3


def test_paragraflar_baslik_satirini_atar(lotm_modulu):
    """
    SART: EN tarafta bolum adi IKI KEZ gecer (clean_html hem baslik
    ogesinden hem govdeden alir), ZH tarafta _ayir 第…章 satirini govdeye
    dahil eder. Temizlenmezse hizalayici sabit bir ofsetle basliyor.
    """
    import bolum
    lotm = lotm_modulu
    metin = "Chapter 5: The Club\n\nChapter 5: The Club\n\nGercek govde.\n"
    p = bolum.paragraflar(metin, lotm.EN_BASLIK)
    assert p == ["Gercek govde."]
