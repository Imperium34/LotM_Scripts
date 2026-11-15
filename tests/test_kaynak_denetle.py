# -*- coding: utf-8 -*-
"""kaynak_denetle.py -- ZH N ile EN N ayni metin mi? Sinyaller, kabul tablosu, CLI.

Gercek derlem gerekmez: sentetik bolumler dogrudan tara(zh=, en=, ciftler=)'e
ya da lotm'un yukleyicilerine (monkeypatch) verilir.

Sentetik derlem: 60 bolum; her bolumde havuzdan 14 "ozel ad" (ZH'de ad, EN'de
onun karsiligi) ve bolum boyuna gore degisen dolgu. Havuz (300 ad) buyuk
oldugundan iki farkli bolumun ad kumeleri neredeyse hic kesismez: dogru cift
kosinus ~1, yanlis cift ~0 -- gercek romandaki ayrimin (0.6 vs 0.05) yapay hali.
"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kaynak_denetle as K  # noqa: E402
import lotm  # noqa: E402

N = 60
HAVUZ = 300
_CJK = [chr(0x4E00 + i * 7) for i in range(60)]  # 60 farkli harf; ikili birlesim = 3600 ad


def _ad_zh(i):
    return _CJK[i // 60 % 60] + _CJK[i % 60]


def _ad_en(i):
    return "nom" + chr(97 + i // 26 % 26) + chr(97 + i % 26)


CIFTLER = [([_ad_zh(i)], [_ad_en(i)]) for i in range(HAVUZ)]


def _bolum_ad_kumesi(no):
    return random.Random(no).sample(range(HAVUZ), 14)


def zh_bolum(no, kume=None, uzunluk=None):
    kume = _bolum_ad_kumesi(no) if kume is None else kume
    uzunluk = uzunluk or 900 + (no * 37) % 120
    n_par = 40
    par = [f"第{no}章 试验"]
    for k in range(n_par):
        ad = _ad_zh(kume[k]) if k < len(kume) else ""
        par.append(ad + "的" * (uzunluk // n_par))
    return lotm.Bolum(no, "\n".join(par) + "\n", "zh", par[0])


def en_bolum(no, kume=None, uzunluk=None, oran=3.5):
    kume = _bolum_ad_kumesi(no) if kume is None else kume
    uzunluk = uzunluk or 900 + (no * 37) % 120
    n_par = 40
    kelime = max(1, int(oran * uzunluk / n_par / 5))
    par = [f"Chapter {no}: Test"]
    for k in range(n_par):
        ad = _ad_en(kume[k]) + " " if k < len(kume) else ""
        par.append(ad + " ".join(["word"] * kelime))
    return lotm.Bolum(no, "\n\n".join(par) + "\n", "en", par[0])


@pytest.fixture
def korpus():
    zh = {n: zh_bolum(n) for n in range(1, N + 1)}
    en = {n: en_bolum(n) for n in range(1, N + 1)}
    return zh, en


def _tara(zh, en, **kw):
    return K.tara(range(1, N + 1), ciftler=CIFTLER, zh=zh, en=en, **kw)


@pytest.fixture
def cli(monkeypatch, korpus, capsys):
    """main()'i sentetik derlemle calistirir; (kod, cikti) doner."""
    zh, en = korpus
    monkeypatch.setattr(lotm, "bolumler_zh", lambda: list(zh.values()))
    monkeypatch.setattr(lotm, "bolumler_en", lambda: list(en.values()))
    monkeypatch.setattr(lotm, "ANA_HIKAYE_SONU", N)
    monkeypatch.setattr(lotm, "BILINEN_EKSIK", {})
    monkeypatch.setattr(K, "terim_ciftleri", lambda: CIFTLER)
    monkeypatch.setattr(K, "KABUL", {})

    def calistir(*argv):
        kod = K.main(list(argv))
        return kod, capsys.readouterr().out

    return calistir


# --------------------------------------------------------------- tarama

def test_normal_derlem_bulgusuz(korpus):
    assert _tara(*korpus, zayif=True) == []


def test_ad_kumeleri_gercekten_ayrik():
    """Sentetik veri varsayimi: iki bolumun ad kumeleri neredeyse kesismiyor;
    aksi halde icerik testleri bos bir garantiye dayanir."""
    a, b = set(_bolum_ad_kumesi(3)), set(_bolum_ad_kumesi(40))
    assert len(a & b) <= 2


def test_en_cok_kisa_bayrakli(korpus):
    zh, en = korpus
    en[30] = en_bolum(30, oran=1.0)
    b = _tara(zh, en)
    assert [x.no for x in b] == [30]
    assert "uzunluk oranı" in b[0].neden and b[0].sinyal.z_uzunluk < -K.ESIK


def test_en_cok_uzun_bayrakli(korpus):
    zh, en = korpus
    en[30] = en_bolum(30, oran=10.0)
    b = _tara(zh, en)
    assert [x.no for x in b] == [30]
    assert b[0].sinyal.z_uzunluk > K.ESIK


def test_normal_uzunlukta_baska_metin_icerikle_yakalanir(korpus):
    """Uzunluk ve paragraf sayisi DOGRU, adlar baska bolumun adlari."""
    zh, en = korpus
    en[30] = en_bolum(30, kume=_bolum_ad_kumesi(50))
    b = _tara(zh, en)
    assert [x.no for x in b] == [30]
    s = b[0].sinyal
    assert abs(s.z_uzunluk) < 1 and abs(s.z_paragraf) < 1, "yalniz icerik sinyali olmali"
    assert s.icerik < K.ICERIK_DUSUK
    assert "içerik" in b[0].neden


def test_kaymis_metin_komsu_bolumu_gosterir(korpus):
    """EN 30'da 31'in metni varsa: ZH 30 ile eslesmesi dusuk, ZH 31 ile yuksek;
    neden hangi komsuya benzedigini soylemeli."""
    zh, en = korpus
    en[30] = en_bolum(30, kume=_bolum_ad_kumesi(31))
    b = _tara(zh, en)
    assert [x.no for x in b] == [30]
    assert "ZH 31" in b[0].neden


def test_icerik_sinyali_terim_yoksa_susar(korpus):
    zh, en = korpus
    en[30] = en_bolum(30, kume=_bolum_ad_kumesi(50))
    b = K.tara(range(1, N + 1), ciftler=[], zh=zh, en=en)
    assert b == [], "sozluk bos: icerik sinyali yok, uzunluk normal"


def test_kisa_terimli_bolumde_icerik_susar(korpus):
    zh, en = korpus
    zh[30] = zh_bolum(30, kume=_bolum_ad_kumesi(30)[:4])
    en[30] = en_bolum(30, kume=_bolum_ad_kumesi(50)[:4])
    assert _tara(zh, en) == []


def test_ikinci_girintili_baslik_bayrakli(korpus):
    zh, en = korpus
    m = en[12].metin + "\n  Chapter 13: Test\n\nbaska bir bolumun metni\n"
    en[12] = lotm.Bolum(12, m, "en", en[12].baslik)
    b = _tara(zh, en)
    assert [x.no for x in b] == [12]
    assert b[0].kaynak == "EN" and "13" in b[0].neden


def test_ayni_numarali_yinelenen_baslik_sayilmaz(korpus):
    """Gercek EN dosyalarinda her bolumun basligi iki kez geciyor (ikincisi
    girintili); bu karisma degil."""
    zh, en = korpus
    m = en[12].metin.replace("Chapter 12: Test\n", "Chapter 12: Test\n\n  Chapter 12: Test\n", 1)
    en[12] = lotm.Bolum(12, m, "en", en[12].baslik)
    assert _tara(zh, en) == []


def test_zh_cilt_sonu_satiri_bayrakli(korpus):
    zh, en = korpus
    zh[20] = lotm.Bolum(20, zh[20].metin + "（第一部完）\n第一部总结\n作者的话\n", "zh", None)
    b = _tara(zh, en)
    assert [x.no for x in b] == [20]
    assert b[0].kaynak == "ZH" and "cilt" in b[0].neden


def test_zh_duzyazida_gecen_toplama_sozcugu_bayrak_degil(korpus):
    zh, en = korpus
    zh[20] = lotm.Bolum(20, zh[20].metin + "克莱恩边走边总结了第三部分的经验，没有再说话。\n", "zh", None)
    assert _tara(zh, en) == []


def test_eksik_bolum_bayrakli_ama_bilinen_eksik_degil(korpus, monkeypatch):
    zh, en = korpus
    del en[9]
    monkeypatch.setattr(lotm, "BILINEN_EKSIK", {})
    assert [x.no for x in _tara(zh, en)] == [9]
    monkeypatch.setattr(lotm, "BILINEN_EKSIK", {"EN": {9: "kayitli"}})
    assert _tara(zh, en) == []


def test_siddet_siralamasi_en_kotu_once(korpus):
    zh, en = korpus
    en[10] = en_bolum(10, oran=1.5)       # orta sapma
    en[40] = en_bolum(40, oran=0.5)       # daha kotu
    b = _tara(zh, en)
    assert [x.no for x in b][:2] == [40, 10]


def test_hepsi_zayif_katmani_ayirir(korpus):
    """esik ile esik*ZAYIF_CARPAN arasi yalniz zayif=True ile gelir."""
    zh, en = korpus
    en[30] = en_bolum(30, oran=3.5 * 1.25)   # birkac sapma, esigin altinda
    s = K.sinyalleri_hesapla(zh, en, [30], CIFTLER)[30]
    esik = abs(s.z_uzunluk) / 0.8          # z = 0.8 x esik: zayif bantta
    assert _tara(zh, en, esik=esik) == []
    zayif = _tara(zh, en, esik=esik, zayif=True)
    assert [x.no for x in zayif] == [30] and zayif[0].zayif


# --------------------------------------------------------------- KABUL tablosu + CLI

def test_cli_normal_cikis_0(cli):
    kod, cikti = cli()
    assert kod == 0
    assert "YENİ bayraklı bölüm yok" in cikti and "BİLİNEN" not in cikti


def test_cli_yeni_bulgu_cikis_1(cli, korpus):
    zh, en = korpus
    en[30] = en_bolum(30, oran=1.0)
    kod, cikti = cli()
    assert kod == 1
    assert "YENİ (1)" in cikti and "30" in cikti and "BİLİNEN" not in cikti


def test_kabul_girisi_bulguyu_bilinene_tasir(cli, korpus, monkeypatch):
    zh, en = korpus
    en[30] = en_bolum(30, oran=1.0)
    monkeypatch.setattr(K, "KABUL", {30: ("EN", "ceviri yarim: dogrulandi")})
    kod, cikti = cli()
    assert kod == 0
    assert "BİLİNEN (1)" in cikti and "ceviri yarim: dogrulandi" in cikti
    assert "YENİ bayraklı bölüm yok" in cikti
    assert "ESKİMİŞ" not in cikti


def test_kabul_girisi_baska_bolumu_gizlemez(cli, korpus, monkeypatch):
    zh, en = korpus
    en[30] = en_bolum(30, oran=1.0)
    en[31] = en_bolum(31, oran=9.0)
    monkeypatch.setattr(K, "KABUL", {30: ("EN", "dogrulandi")})
    kod, cikti = cli()
    assert kod == 1 and "YENİ (1)" in cikti and "BİLİNEN (1)" in cikti


def test_eskimis_kabul_girisi_uyarir(cli, monkeypatch):
    monkeypatch.setattr(K, "KABUL", {7: ("EN", "eskiden yarimdi")})
    kod, cikti = cli()
    assert kod == 0
    assert "ESKİMİŞ giriş: 7" in cikti and "eskiden yarimdi" in cikti


def test_eskimis_uyarisi_aralik_disindakini_anmaz(cli, monkeypatch):
    monkeypatch.setattr(K, "KABUL", {7: ("EN", "x")})
    _, cikti = cli("20-22")
    assert "ESKİMİŞ" not in cikti


def test_aralik_modu_bayraksiz_bolumleri_de_basar(cli):
    kod, cikti = cli("10-12")
    satirlar = [s for s in cikti.splitlines() if s.strip()]
    assert [s.split()[0] for s in satirlar] == ["10", "11", "12"]
    assert all("BAYRAK" not in s for s in satirlar)
    assert "oran" in satirlar[0] and "içerik" in satirlar[0]
    assert kod == 0


def test_aralik_modu_bayrakliyi_neden_ile_basar(cli, korpus):
    zh, en = korpus
    en[11] = en_bolum(11, oran=1.0)
    kod, cikti = cli("10-12")
    assert "BAYRAK" in cikti and "-> " in cikti
    assert kod == 1


def test_aralik_modu_bilinen_bayragi_cikis_0(cli, korpus, monkeypatch):
    zh, en = korpus
    en[11] = en_bolum(11, oran=1.0)
    monkeypatch.setattr(K, "KABUL", {11: ("EN", "dogrulandi")})
    kod, cikti = cli("10-12")
    assert "(bilinen)" in cikti and kod == 0


@pytest.mark.parametrize("argv", [["--esik"], ["--esik", "abc"], ["abc"], ["5-3"],
                                  ["1", "2"], ["--yok"]])
def test_kullanim_hatasi_cikis_2(cli, argv):
    kod, _ = cli(*argv)
    assert kod == 2


def test_esik_secenegi_duyarliligi_degistirir(cli, korpus):
    zh, en = korpus
    en[30] = en_bolum(30, oran=3.5 * 1.4)
    assert cli("--esik", "0.5")[0] == 1
    assert cli("--esik", "1000")[0] == 0
