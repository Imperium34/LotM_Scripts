# -*- coding: utf-8 -*-
"""
capa.py -- sozluk terimlerinden capa.

Bolum 5: kisa replikler ("Beleş mi?") hizalamayi uc paragraf kaydirmisti.
ZH ¶46'da 磅/便士/苏勒, TR ¶49'da libre/peni/soli var; rakamlar Turkcede
yaziyla yazildigi icin sayi capasi burada ise yaramiyordu.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import capa  # noqa: E402
import lotm  # noqa: E402

ZH = ["那算了。", "这真是的！", "不想做占卜家的驯兽师不是好小丑？",
      "周明瑞在市场花7便士买了1磅羔羊肉，一共用了25铜便士，也就是2苏勒1便士。",
      "钱还真不禁花啊。"]
TR = ["\"Beleş mi?\"", "\"...Hayır.\"", "\"Kalsın o zaman.\"", "_Hay anasını!_", "_Soytarı mı?_",
      "Zhou Mingrui pazarda bir libre kuzu eti için yedi peni harcadı; toplam iki soli ve bir peniye tekabül ediyordu.",
      "Ne kadar harcarsan harca, iki yakan bir araya gelmiyor."]

PARA = [lotm.Terim(tr="libre", zh="磅", zh_kesin=True),
        lotm.Terim(tr="peni", zh="便士"), lotm.Terim(tr="soli", zh="苏勒")]


def test_sozluk_terimi_capa_uretir():
    capalar = capa.capa_bul(ZH, TR, {}, terimler=capa.capalari_kur(PARA))
    assert (3, 5) in capalar


def test_terimsiz_capa_yok():
    # rakamlar Turkcede yaziyla: sayi capasi da cikmaz
    assert capa.capa_bul(ZH, TR, {}, terimler=()) == []


def test_eleme_kurallari():
    kur = capa.capalari_kur([
        lotm.Terim(tr="Kanun", zh="法"),                 # tek karakter, kasitsiz
        lotm.Terim(tr="top", zh="火炮"),                 # Turkce cok kisa
        lotm.Terim(tr="damga", zh="印章/盖章"),           # iki bicim, ikisi de capa
    ])
    assert [z for z, *_ in kur] == ["印章", "盖章"]


def test_bilesik_haric_ve_morfoloji():
    kur = capa.capalari_kur([lotm.Terim(tr="ruhanî varlık", zh="灵体"),
                             lotm.Terim(tr="Astral İzdüşüm", zh="星灵体"),
                             lotm.Terim(tr="pazar mektebi", zh="周日学校")])
    d = {z: (zd, td) for z, _t, zd, td in kur}
    assert not d["灵体"][0].search("你的星灵体")          # bilesigin icinde sayilmaz
    assert d["周日学校"][1].search("pazar mekteplerinde")  # tamlama cogulu


def test_anahtar_iki_yonde_de_calisir(monkeypatch):
    # Varsayilan degeri test etmez: o bir karardir, olcumle degisir.
    monkeypatch.setattr(capa, "terim_capalari", lambda: capa.capalari_kur(PARA))
    monkeypatch.setattr(capa, "TERIM_CAPALARI", False)
    assert capa.capa_bul(ZH, TR, {}) == []
    monkeypatch.setattr(capa, "TERIM_CAPALARI", True)
    assert (3, 5) in capa.capa_bul(ZH, TR, {})


def test_sik_ya_da_esit_olmayan_terim_capa_olmaz():
    # 便士 ZH'de 3, TR'de 2 kez: esit degil -> yalniz basina capa uretmez
    yalniz_peni = capa.capalari_kur([lotm.Terim(tr="peni", zh="便士")])
    assert capa.capa_bul(ZH, TR, {}, terimler=yalniz_peni) == []
    # esit ama sik (3 = 3 > TERIM_EN_COK): yine yok
    zh = ["手杖。", "手杖。", "手杖。", "别的。"]
    tr = ["Baston.", "Baston.", "Baston.", "Başka."]
    kur = capa.capalari_kur([lotm.Terim(tr="baston", zh="手杖")])
    assert capa.capa_bul(zh, tr, {}, terimler=kur) == []


def test_ingilizce_kaynakta_taranmaz():
    en = ["Forget it.", "Seriously!", "Not a good clown?",
          "He bought 1 pound of lamb for 7 pence.", "Money goes fast."]
    assert capa.capa_bul(en, TR, {}, terimler=capa.capalari_kur(PARA)) == []


def test_grup_anlaminda_capa_dogru_1e2yi_bozmaz(monkeypatch):
    import bolum as B
    # Gercek yapi 1:2: ZH[1] = TR[1] + TR[2]; capa ikinci Turkce paragrafta.
    zh = ["甲" * 40, "乙" * 80, "丙" * 40]
    tr = ["a" * 100, "b" * 95, "c" * 105, "d" * 100]
    dogru = [([0], [0]), ([1], [1, 2]), ([2], [3])]
    assert B.hizala(zh, tr, set()) == dogru              # uzunluk tek basina dogru
    monkeypatch.setattr(B, "CAPA_GRUP", 0)
    assert B.hizala(zh, tr, {(1, 2)}) != dogru            # 1:1 odulu bozuyor
    monkeypatch.setattr(B, "CAPA_GRUP", 1)
    assert B.hizala(zh, tr, {(1, 2)}) == dogru            # grup odulu korur


def test_grup_anlaminda_capa_1e1i_hala_destekler(monkeypatch):
    import bolum as B
    zh, tr = ["甲" * 40] * 3, ["a" * 100] * 3
    for mod in (0, 1):
        monkeypatch.setattr(B, "CAPA_GRUP", mod)
        assert B.hizala(zh, tr, {(1, 1)}) == [([0], [0]), ([1], [1]), ([2], [2])]
