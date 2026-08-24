# -*- coding: utf-8 -*-
"""
Bolum numaralandirmasi -- projenin en sessiz hata kaynagi.

Cince okunamadigi icin buradaki bir kayma "ceviri hatasi" gibi gorunur ve
fark edilmez. lotm.py'nin modul basindaki notu bu davranisi anlatiyor;
buradaki testler o notu dogrulanabilir hale getiriyor.
"""

import pytest
from conftest import cn_yaz, zh_korpus


# --------------------------------------------------------------- cn_sayi

@pytest.mark.parametrize("metin,beklenen", [
    ("一千四百零九", 1409),
    ("二十", 20),
    ("十", 10),            # basinda rakam yoksa 1 varsayilir
    ("十五", 15),
    ("二百六十九", 269),
    ("二百零五", 205),
    ("二百一十", 210),
    ("279", 279),          # Arap rakamlari oldugu gibi gecer
    ("一", 1),
])
def test_cn_sayi_cozuluyor(metin, beklenen):
    import lotm
    assert lotm.cn_sayi(metin) == beklenen


@pytest.mark.parametrize("metin", ["", None, "试验", "abc", "第章"])
def test_cn_sayi_cozulemeyince_none(metin):
    """
    None donmeli, patlamamali: cagiran taraf o satiri baslik saymasin diye.
    """
    import lotm
    assert lotm.cn_sayi(metin) is None


def test_cn_yaz_ve_cn_sayi_tersi(cn_yaz_araligi=270):
    """Test yardimcisinin kendisi dogru mu -- yoksa korpus anlamsiz olur."""
    import lotm
    for n in range(1, cn_yaz_araligi):
        assert lotm.cn_sayi(cn_yaz(n)) == n, f"{n} -> {cn_yaz(n)}"


# ------------------------------------------------------- cilt sinirlari

WIKI_UZUNLUKLARI = [213, 269, 250, 214, 204, 116, 87, 41]


def test_cilt_tablosu_uzunluklari_wiki_ile_tutuyor():
    import lotm
    for (no, ad, bas, son), beklenen in zip(lotm.CILTLER, WIKI_UZUNLUKLARI):
        assert son - bas + 1 == beklenen, f"cilt {no} ({ad})"


def test_cilt_tablosu_bitisik_ve_bosluksuz():
    import lotm
    for onceki, sonraki in zip(lotm.CILTLER, lotm.CILTLER[1:]):
        assert sonraki[2] == onceki[3] + 1, f"cilt {onceki[0]}/{sonraki[0]}"
    assert lotm.CILTLER[0][2] == 1
    assert lotm.CILTLER[-1][3] == lotm.ANA_HIKAYE_SONU


def test_ciltlere_bol_sinirlari_buluyor(lotm_modulu):
    lotm = lotm_modulu
    ham = lotm._ayir(zh_korpus([3, 4, 2]), lotm.ZH_BASLIK, "zh", lotm.cn_sayi)
    ciltler = lotm._ciltlere_bol(ham)
    assert [len(c) for c in ciltler] == [3, 4, 2]


def test_tekrar_eden_numara_cilt_siniri_uretmez(lotm_modulu):
    """
    Ham metindeki iki yazim hatasi (cilt 3'te ikinci 230, cilt 8'de ikinci
    6) tekrar uretir ama AZALMA uretmez. Sinir olcutu kesin azalma oldugu
    icin tespit bozulmaz -- lotm.py'nin dayandigi tam olarak bu.
    """
    lotm = lotm_modulu
    # 5 bolumluk bir ciltte 4. bolum yanlislikla "3" yaziliyor
    metin = zh_korpus([5, 3], yazim_hatalari={(0, 4): 3})
    ham = lotm._ayir(metin, lotm.ZH_BASLIK, "zh", lotm.cn_sayi)
    ciltler = lotm._ciltlere_bol(ham)
    assert [len(c) for c in ciltler] == [5, 3], "tekrar sinir sanildi"


def test_surekli_numaralandirma_etiketten_degil_siradan_turer(lotm_modulu, depo):
    """
    'Etiket yalnizca cilt sinirini bulmak icindir.' Yazim hatasi olan
    bolum bile dogru surekli numarayi almali.
    """
    lotm = lotm_modulu
    uzunluklar = [u for _, _, bas, son in
                  [(c[0], c[1], c[2], c[3]) for c in lotm.CILTLER]
                  for u in [son - bas + 1]]
    # gercek cilt uzunluklari + cilt 3'te 231 yerine ikinci kez 230
    metin = zh_korpus(uzunluklar, yazim_hatalari={(2, 231): 230})
    depo.joinpath("Source/Lord_of_the_Mysteries_Chinese.txt").write_text(
        metin, encoding="utf-8")

    bolumler = lotm.bolumler_zh()
    nolar = [b.no for b in bolumler]

    assert nolar == list(range(1, lotm.ANA_HIKAYE_SONU + 1))
    assert len(set(nolar)) == len(nolar), "surekli numarada tekrar var"

    # cilt 3, yerel 231 -> surekli 483 - 1 + 231 = 713
    sozluk = lotm.bolum_sozlugu(bolumler)
    assert 713 in sozluk
    assert "第二百三十章" in sozluk[713].baslik, "yazim hatali etiket beklenen yerde degil"


def test_yerel_numaralar_ciltler_arasi_tekrar_eder(lotm_modulu, depo):
    """surekli=False tani icindir; tek basina bolumu TANIMLAMAZ."""
    lotm = lotm_modulu
    depo.joinpath("Source/Lord_of_the_Mysteries_Chinese.txt").write_text(
        zh_korpus([3, 3]), encoding="utf-8")
    ham = lotm.bolumler_zh(surekli=False)
    assert [b.no for b in ham] == [1, 2, 3, 1, 2, 3]


# ----------------------------------------------------------- bolume ayirma

def test_ayir_baslik_satirini_govdeye_dahil_eder(lotm_modulu):
    lotm = lotm_modulu
    metin = "Chapter 1: Bir\n\ngovde bir\n\nChapter 2: Iki\n\ngovde iki\n"
    b = lotm._ayir(metin, lotm.EN_BASLIK, "test")
    assert [x.no for x in b] == [1, 2]
    assert b[0].metin.startswith("Chapter 1")
    assert "govde iki" not in b[0].metin


def test_bolum_sozlugu_ilk_kaydi_tutar(lotm_modulu):
    lotm = lotm_modulu
    B = lotm.Bolum
    d = lotm.bolum_sozlugu([B(1, "ilk", "a"), B(1, "ikinci", "b"),
                            B(None, "numarasiz", "c")])
    assert d[1].metin == "ilk"
    assert None not in d


def test_cilt_bul(lotm_modulu):
    lotm = lotm_modulu
    assert lotm.cilt_bul(1)[1] == "Clown"
    assert lotm.cilt_bul(713)[0] == 3
    assert lotm.cilt_bul(1394)[0] == 8
    assert lotm.cilt_bul(99999) is None


def test_metin_oku_kodlamalari(lotm_modulu, tmp_path):
    """
    utf-8-sig BOM'lu ve BOM'suzu birlikte cozer; gb18030 GBK/GB2312 ust
    kumesi. Eski surum yalnizca ILK SATIRA bakarak karar veriyordu.
    """
    lotm = lotm_modulu
    icerik = "第一章 试验\n正文在这里。\n"

    duz = tmp_path / "utf8.txt"
    duz.write_bytes(icerik.encode("utf-8"))
    assert lotm.metin_oku(duz) == icerik

    bomlu = tmp_path / "bom.txt"
    bomlu.write_bytes(b"\xef\xbb\xbf" + icerik.encode("utf-8"))
    assert lotm.metin_oku(bomlu) == icerik

    gbk = tmp_path / "gbk.txt"
    gbk.write_bytes(icerik.encode("gb18030"))
    assert lotm.metin_oku(gbk) == icerik

    # ASCII bir satirla baslayan GBK dosyasi -- eski tespiti kandiran hal
    karma = "Chapter 1\n" + icerik
    hileli = tmp_path / "hileli.txt"
    hileli.write_bytes(karma.encode("gb18030"))
    assert lotm.metin_oku(hileli) == karma
