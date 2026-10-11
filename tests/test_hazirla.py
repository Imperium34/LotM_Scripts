# -*- coding: utf-8 -*-
"""hazirla.py -- ceviriden once: bolumde gecen yerlesmis terimler."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hazirla as H  # noqa: E402
import lotm  # noqa: E402


def _t(tr, en=None, zh=None, kategori="Temel Kavramlar", **kw):
    return lotm.Terim(tr=tr, en=en, zh=zh, kategori=kategori, **kw)


def test_cince_eslesme_okuma_sirasi_ve_bilesik_haric():
    terimler = [
        _t("Astral Beden", "Astral Projection", "星灵体"),
        _t("Ruhani Beden", "Spirit Body", "灵体"),
        _t("Kâhin", "Seer", "占卜家", kategori="Kâhin Yolu"),
    ]
    hepsi = sorted({t.zh for t in terimler}, key=len, reverse=True)
    zh = "克莱恩是占卜家。他看见了星灵体。灵体很淡。"
    e = H.terimleri_bul(zh, None, terimler, hepsi)
    assert [(x.terim.tr, x.sayi) for x in e] == [("Kâhin", 1), ("Astral Beden", 1), ("Ruhani Beden", 1)]


def test_cincesi_olmayan_terim_ingilizceden_bulunur_harf_kurali_ile():
    terimler = [
        _t("Kehanet", "Divination"),                              # Temel Kavramlar: duyarsiz
        _t("Ölüm", "Death", kategori="İlahlar ve Yüce Kadimler"),  # ozel ad: duyarli
    ]
    en = "Klein studied divination. Nobody feared death."
    e = H.terimleri_bul(None, en, terimler, [])
    assert [(x.terim.tr, x.nasil) for x in e] == [("Kehanet", "en")]


def test_sozluk_kaydi_words_md_kaydina_tercih_edilir():
    terimler = [
        _t("Sıradışı", "Beyonder", "非凡者", kategori="words.md › X"),
        _t("Sıradışı", "Beyonder", "非凡者"),
    ]
    e = H.terimleri_bul("一个非凡者", None, terimler, ["非凡者"])
    assert len(e) == 1 and e[0].terim.kategori == "Temel Kavramlar"


def test_salahiyet_yalniz_baglaminda_sayilir():
    kayitlar = [{"cince": "力量", "turkce": "Kudret"}, {"cince": "死亡", "turkce": "Mevt"}]
    zh = "他用尽了力量。祂掌握了死亡权柄。"
    baglamli, siradan = H.salahiyetleri_bul(zh, kayitlar, ["力量", "死亡"])
    assert [k["turkce"] for k, _n, _i in baglamli] == ["Mevt"]
    assert [k["turkce"] for k, _n, _i in siradan] == ["Kudret"]


def test_aday_adlar_iyelik_satir_sonu_ve_bilinenler():
    # Cumle basindaki tek buyuk harfli kelime bilerek aday sayilmaz (orada
    # her kelime buyuk harflidir); adaylar cumle ortasindan gelir.
    en = ("He saw Angelica's coat. He met Angelica and Old Neil at the Berserk Sea.\n\n"
          "First Divination Requester\n\nChapter 2: Klein's day. Klein Moretti waved.")
    bilinen = {"klein", "moretti", "old neil"}
    adaylar = dict(H.aday_adlar(en, bilinen, en_kucuk=1))
    assert adaylar.get("Angelica") == 2                 # iyelik ayni ad
    assert "Berserk Sea" in adaylar and "First Divination Requester" in adaylar
    assert not any("Chapter" in a for a in adaylar)    # satir sonu obegi bolmez
    assert "Klein Moretti" not in adaylar and "Klein" not in adaylar


def test_yaz_kapi_icermez_ve_eski_karsiligi_yasaklar():
    t = _t("Ayin", "Ritual", "仪式", bolum_siniri=22, eski_karsiliklar=["ritüel"],
           ham={"aciklama": "Bir tören.", "mudahale": "ceviri"})
    e = H.Eslesme(t, "zh", 2, 0, yayim=[30, 40])
    md = H.yaz(10, "仪式", None, [e], [], [], 53)
    assert "KULLANILMAZ (eski karşılık): ritüel" in md
    assert "yayımlanmış 2 bölümde (son: 40)" in md
    assert "22" not in md                                # bolum_siniri yazilmaz
    assert "yalnız Çince" in md



def test_salahiyet_tirnakli_ve_de_ile():
    kayitlar = [{"cince": "死亡", "turkce": "Mevt"}, {"cince": "秘密", "turkce": "Sır"}]
    zh = "祂拥有部分“死亡”权柄，也是秘密的象征。"
    baglamli, siradan = H.salahiyetleri_bul(zh, kayitlar, ["死亡", "秘密"])
    assert sorted(k["turkce"] for k, _n, _i in baglamli) == ["Mevt", "Sır"] and not siradan
