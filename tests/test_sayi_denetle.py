# -*- coding: utf-8 -*-
"""sayi_denetle.py -- Cince miktar cikarma, Turkce sayi ayristirma, bulgular ve CLI.

Gercek derlem gerekmez: gruplar() sentetik gruplarla degistirilir.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sayi_denetle as S  # noqa: E402


def _zh(metin, turler=S.TURLER):
    """[(tur, deger)] -- belirtec/konum karsilastirmasini testlerden uzak tutar."""
    return [(t, d) for t, _, d, _ in S.cince_miktarlar(metin, turler)]


# ------------------------------------------------------------ Cince cikarici

@pytest.mark.parametrize("metin, beklenen", [
    ("花7便士买了1磅羔羊肉", [("para", 7)]),                 # 1 (磅) yok sayilir
    ("一共用了25铜便士", [("para", 25)]),
    ("他有两万镑", [("para", 20000)]),
    ("三十二苏勒", [("para", 32)]),
    ("五镑", [("para", 5)]),
    ("1349年的事", [("tarih", 1349)]),
    ("一一八四年", [("tarih", 1184)]),                        # rakam rakam okunan yil
    ("六月的雨", [("tarih", 6)]),
    ("27日", [("tarih", 27)]),
    ("才二十岁", [("yas", 20)]),
    ("第三步", [("sira", 3)]),
    ("序列九", [("sira", 9)]),
    ("序列7", [("sira", 7)]),
    ("七点半", [("saat", 7)]),
    ("下午两点", [("saat", 2)]),
    ("五点四十分", [("saat", 5)]),
    ("四个人", [("sayi", 4)]),
    ("三十分钟", [("sayi", 30)]),
    ("十分钟", [("sayi", 10)]),                               # 十分 durdurma listesinde ama 钟 ile sayi
    ("八磅面包", [("sayi", 8)]),
    ("1200万吨", [("rakam", 12000000)]),
    ("编号2-049", [("rakam", -1)]),
    ("三十发子弹", [("sayi", 30)]),
])
def test_miktar_cikarilir(metin, beklenen):
    assert _zh(metin) == beklenen


@pytest.mark.parametrize("metin", [
    # deger 1: tanimlik
    "一张桌子", "一个人", "1磅肉", "第一次", "第一时间",
    # yaklasiklik
    "三四次", "两三个", "四五十分钟", "十几个", "二十多个", "数百人", "几十个", "三十来岁",
    "一千多年", "百分之五", "四分之一便士",
    # sayi olmayan sozcukler
    "环顾四周", "一点点", "一些人", "一下", "一样", "一起", "一直", "一切", "一旦",
    "十分高兴", "万分感谢", "千万不要", "万一", "百姓", "三三两两", "乱七八糟", "七上八下",
    "五颜六色", "十字路口", "万物", "五官", "三点一线",
    # serbest karsiliklari cok olan kucuk sayilar
    "两人", "两个", "两步", "三人", "第二天",
])
def test_sayi_olmayan_ya_da_atlananlar(metin):
    assert _zh(metin) == []


def test_tur_suzgeci():
    assert _zh("花7便士，二十岁", ("yas",)) == [("yas", 20)]


# ------------------------------------------------------------- Turkce ayristirici

@pytest.mark.parametrize("metin, beklenen", [
    ("yedi peni", {7}),
    ("on iki", {12}),
    ("yirmi üç", {23}),
    ("yüz elli", {150}),
    ("iki yüz", {200}),
    ("bin üç yüz kırk dokuz", {1349}),
    ("on bin", {10000}),
    ("yedi buçuk", {7}),
    ("ikisi", {2}), ("üçünü", {3}), ("beşer", {5}), ("yedide", {7}),
    ("ikinci", {2}), ("üçüncü", {3}), ("onuncu", {10}), ("dördüncü", {4}),
    ("25'inde", {25}),
    ("1.250 Sterlin", {1250}),
    ("1349", {1349}),
    ("11:55", {11, 55}),
    ("iki yüz Sterlinlik", {200}),
    ("altı librelik", {6}),
    ("yirmi beşindeydi", {25}),
    ("gece on birle sabah", {11}),
    ("iki üç gün", {2, 3}),            # yan yana iki sayi: birlestirilmez
    ("yüzde elli", {50}),
    ("III. George", {3}),
    ("1,5 peni", {1, 5}),
])
def test_turkce_sayilar(metin, beklenen):
    assert S.turkce_sayilar(metin) == beklenen


@pytest.mark.parametrize("metin", [
    "birlikte", "onlar", "onu", "ona", "yüzü", "yüzüne", "binmek", "bindi", "kırık", "elleri",
    "masanın altında", "altın", "altından", "yediğimiz", "ikiz", "beşik", "ikindi",
    "biri", "I.", "yarım", "çeyrek",
])
def test_sayi_gibi_gorunen_ama_degil(metin):
    assert S.turkce_sayilar(metin) == set()


def test_bir_tek_basina_bir():
    # 1 ZH tarafinda hic aranmaz; yine de on bir / bin bir gibi birlesiklerde gerekli
    assert S.turkce_sayilar("bir") == {1}


def test_belirsiz_alti_comert():
    # "alti" hem 6 hem "alt yani": ikisini ayirmak mumkun degil; 6 sayilir (bkz. docstring)
    assert S.turkce_sayilar("masanın altı") == {6}


def test_turkce_para_yalniz_birim_yanindakiler():
    t = "Yedi kişi geldi. Klein iki soli bir peni verdi."
    assert S.turkce_para(t) == {2, 1}
    assert S.turkce_para_listesi("yedi peni") == [7]
    assert S.turkce_para("yedi kişi geldi") == set()
    # birim sona konmus sayim ve binlik nokta cumleyi bolmez
    assert S.turkce_para("en fazla dört, kenarda altı peni") == {4, 6}
    assert S.turkce_para("800 ile 1.000 Sterlin") == {800, 1000}


def test_turkce_aylar():
    assert S.turkce_aylar("27 Haziran'da ve temmuz gelince") == [6, 7]


# ----------------------------------------------------------------- bulgular

def _grup(monkeypatch, tr_zh):
    """tr_zh: [(zh, tr)] -> gruplar() yerine gecer, ¶ 1'den baslar."""
    g = {i: {"ZH": z, "TR": t} for i, (z, t) in enumerate(tr_zh, 1)}
    monkeypatch.setattr(S, "gruplar", lambda no, ikinci="en": g)
    return g


def test_eksik_para_bildirilir(monkeypatch):
    _grup(monkeypatch, [("他花了7便士。", "Sekiz peni harcadı.")])
    b = S.bulgular(5)
    assert [(x.p, x.tur, x.deger, x.belirtec) for x in b] == [(1, "para", 7, "7便士")]
    assert "7便士" in b[0].zh and "peni" in b[0].tr


def test_dogru_para_bildirilmez(monkeypatch):
    _grup(monkeypatch, [("他花了7便士。", "Yedi peni harcadı.")])
    assert S.bulgular(5) == []


def test_para_iki_grup_sonra_bulunursa_bildirilmez(monkeypatch):
    bos = ("他笑了。", "Güldü.")
    _grup(monkeypatch, [("他花了7便士。", "Harcadı."), bos, ("别的。", "Yedi peni."), bos, bos])
    assert S.bulgular(5) == []


def test_para_pencere_disinda_bildirilir(monkeypatch):
    bos = ("他笑了。", "Güldü.")
    _grup(monkeypatch, [("他花了7便士。", "Harcadı."), bos, bos, ("别的。", "Yedi peni."), bos])
    assert [x.p for x in S.bulgular(5)] == [1]


def test_para_degeri_birimin_yaninda_aranir(monkeypatch):
    # "yedi" pencerede var ama para degil: sekiz peni yazilmis, yedi kisi baska is
    _grup(monkeypatch, [("他花了7便士。", "Yedi kişi geldi. Sekiz peni harcadı.")])
    assert [x.deger for x in S.bulgular(5)] == [7]


def test_ayni_tutar_iki_kez_ama_bir_kez_yazilmis(monkeypatch):
    _grup(monkeypatch, [("7便士……又是7便士。", "Yedi peni, sonra yine.")])
    assert len(S.bulgular(5)) == 1  # her TR sayisi bir ZH miktarini karsilar


def test_ayni_grupta_tekrarlanan_deger_bir_kez_aranir(monkeypatch):
    _grup(monkeypatch, [("序列7及序列7之上。", "Mertebe 7 ve üstü.")])
    assert S.bulgular(5) == []


def test_tanimlik_bir_yoksayilir(monkeypatch):
    _grup(monkeypatch, [("他看见一张桌子。", "Masayı gördü."), ("他看见一张桌子。", "Bir masa gördü.")])
    assert S.bulgular(5) == []


def test_yaklasiklik_yoksayilir(monkeypatch):
    _grup(monkeypatch, [("他试了三四次，二十多个人。", "Birkaç kez denedi, kalabalıktı.")])
    assert S.bulgular(5) == []


def test_sira_sirayla_eslesir(monkeypatch):
    _grup(monkeypatch, [("第二张牌。", "İkinci kart.")])
    assert S.bulgular(5) == []
    _grup(monkeypatch, [("第三张牌。", "İkinci kart.")])
    assert [(x.tur, x.deger) for x in S.bulgular(5)] == [("sira", 3)]


def test_durdurma_listesi(monkeypatch):
    _grup(monkeypatch, [("他环顾四周，十分高兴，千万小心，百姓们一起走。", "Etrafa baktı.")])
    assert S.bulgular(5) == []


def test_ay_adi_sayilir(monkeypatch):
    _grup(monkeypatch, [("六月的雨。", "Haziran yağmuru.")])
    assert S.bulgular(5) == []
    _grup(monkeypatch, [("六月的雨。", "Temmuz yağmuru.")])
    assert [(x.tur, x.deger) for x in S.bulgular(5)] == [("tarih", 6)]


def test_saat_24_saatli_yazim(monkeypatch):
    _grup(monkeypatch, [("五点四十分。", "Saat 17:40'a gelindiğinde.")])
    assert S.bulgular(5) == []


def test_yarim_saat(monkeypatch):
    _grup(monkeypatch, [("过去三十分钟。", "Yarım saat geçti.")])
    assert S.bulgular(5) == []
    _grup(monkeypatch, [("过去三十分钟。", "Bir süre geçti.")])
    assert len(S.bulgular(5)) == 1


def test_yil_rakami(monkeypatch):
    _grup(monkeypatch, [("1349年。", "1348 yılında.")])
    assert [(x.tur, x.deger) for x in S.bulgular(5)] == [("tarih", 1349)]
    _grup(monkeypatch, [("1349年。", "1349 yılında.")])
    assert S.bulgular(5) == []


def test_tur_filtresi(monkeypatch):
    _grup(monkeypatch, [("他花了7便士，1349年。", "Hiçbir şey.")])
    assert {x.tur for x in S.bulgular(5)} == {"para", "tarih"}
    assert {x.tur for x in S.bulgular(5, ("tarih",))} == {"tarih"}


def test_tr_olmayan_grup_atlanir(monkeypatch):
    _grup(monkeypatch, [("他花了7便士。", "")])
    assert S.bulgular(5) == []


def test_bolum_yoksa_bos(monkeypatch):
    monkeypatch.setattr(S, "gruplar", lambda no, ikinci="en": {})
    assert S.bulgular(999) == []


def test_ters_yon_yalniz_istenince(monkeypatch):
    _grup(monkeypatch, [("他笑了。", "1349 yılında güldü.")])
    assert S.bulgular(5) == []
    assert [(x.tur, x.deger) for x in S.bulgular(5, ("ters",))] == [("ters", 1349)]
    _grup(monkeypatch, [("1349年他笑了。", "1349 yılında güldü.")])
    assert S.bulgular(5, ("ters",)) == []


# ---------------------------------------------------------------------- CLI

def test_cli_bulguda_bile_sifir(monkeypatch, capsys):
    _grup(monkeypatch, [("他花了7便士。", "Sekiz peni harcadı.")])
    assert S.main(["5"]) == 0
    out = capsys.readouterr().out
    assert "=== 5: 1 sayı uyuşmazlığı" in out and "¶1 [para] 7便士 (7)" in out


def test_cli_aralik_ozeti(monkeypatch, capsys):
    _grup(monkeypatch, [("他花了7便士。", "Sekiz peni harcadı.")])
    assert S.main(["5-6"]) == 0
    assert "özet: 5:1, 6:1" in capsys.readouterr().out


def test_cli_tur_ve_ayrinti(monkeypatch, capsys):
    _grup(monkeypatch, [("他花了7便士。", "Sekiz peni harcadı.")])
    assert S.main(["5", "--tur", "rakam"]) == 0
    assert "0 sayı uyuşmazlığı" in capsys.readouterr().out
    assert S.main(["5", "--ayrinti"]) == 0
    assert "TR ¶1: Sekiz peni" in capsys.readouterr().out


def test_cli_bolum_yoksa_tek_satir(monkeypatch, capsys):
    monkeypatch.setattr(S, "gruplar", lambda no, ikinci="en": {})
    assert S.main(["999"]) == 0
    assert "atlandı" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [[], ["abc"], ["5", "--tur", "yok"], ["5", "--bilinmeyen"], ["5", "6"],
                                  ["5", "--tur"]])
def test_cli_kullanim_hatasi_1(argv, capsys):
    assert S.main(argv) == 1
