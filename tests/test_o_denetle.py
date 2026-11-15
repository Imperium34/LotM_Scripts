# -*- coding: utf-8 -*-
"""
o_denetle.py testleri: "o + sozcuk" tikinin olcutu. Hizalama gruplari
(o_denetle.gruplar) sentetik gruplarla degistirilir; gercek korpus gerekmez.

Testler MEVCUT davranisi anlatir. Davranisin tuhaf gorunen yanlari
(ters tirnak sonrasi buyuk O gibi) ilgili testin yorumunda isaretlidir.
"""

import pytest

import o_denetle as O


def grup(monkeypatch, bolumler):
    """bolumler: {no: {para_no: (tr, zh)}}"""
    def sahte(no, ikinci="en"):
        assert ikinci == "tr"
        return {p: {"TR": tr, "ZH": zh} for p, (tr, zh) in bolumler.get(no, {}).items()}
    monkeypatch.setattr(O, "gruplar", sahte)


def test_zhde_na_yoksa_o_sozcuk_bulgu(monkeypatch):
    grup(monkeypatch, {5: {1: ("Karşısında o tekinsiz manzara vardı.", "他看着诡异的景象。")}})
    (p, parca), = O.bulgular(5)
    assert p == 1
    assert "o tekinsiz" in parca and parca.startswith("…") and parca.endswith("…")


def test_zhde_na_varsa_sayilmaz(monkeypatch):
    grup(monkeypatch, {5: {1: ("Karşısında o tekinsiz manzara vardı.", "他看着那诡异的景象。")}})
    assert O.bulgular(5) == []


@pytest.mark.parametrize("tr", ["o zaman gitti", "o kadar yorgundu", "O sırada kapı açıldı",
                                "Gece o hâlde yattı", "bana o da geldi"])
def test_sabit_kaliplar_sayilmaz(monkeypatch, tr):
    grup(monkeypatch, {5: {1: (tr, "他走了")}})
    assert O.bulgular(5) == []


def test_sabit_kume_beklenen_sozcukleri_icerir():
    assert {"zaman", "kadar", "sırada", "hâlde", "bana", "onu"} <= O.SABIT


def test_cumle_basinda_O_sozcuk_bulgu_sayilir(monkeypatch):
    grup(monkeypatch, {5: {
        1: ("O tekinsiz manzara vardı.", "景象"),                     # metnin basi
        2: ("Gitti. O tekinsiz manzara vardı.", "景象"),              # nokta sonrasi
        3: ('Dedi ki: "O tekinsiz manzara vardı."', "景象"),          # duz tirnak sonrasi
        4: ("Gitti! O tekinsiz manzara vardı.", "景象"),
    }})
    assert [p for p, _ in O.bulgular(5)] == [1, 2, 3, 4]


def test_cumle_ortasinda_buyuk_O_ilah_zamiri_atlanir(monkeypatch):
    grup(monkeypatch, {5: {1: ("Sonra O tekinsiz varlık geldi.", "景象")}})
    assert O.bulgular(5) == []


def test_cumle_ortasinda_kucuk_o_yine_bulgu(monkeypatch):
    grup(monkeypatch, {5: {1: ("Sonra o tekinsiz varlık geldi.", "景象")}})
    assert len(O.bulgular(5)) == 1


def test_kapanis_egri_tirnagi_cumle_sonu_sayilmaz(monkeypatch):
    # MEVCUT davranis: sonu ” olan cumleden sonraki "O sozcuk" cumle basi sayilmaz
    # ('.!?…"“_' icinde ” yok), yani ilah zamiri gibi atlanir. Metinde egri tirnak
    # kullaniliyorsa bu bir kacak olabilir; kod degistirilmedi.
    grup(monkeypatch, {5: {1: ("“Git.” O tekinsiz varlık geldi.", "景象")}})
    assert O.bulgular(5) == []


def test_kelimenin_icindeki_o_eslesmez(monkeypatch):
    grup(monkeypatch, {5: {1: ("Bugün do tekinsiz, kuvvetlio tekinsiz", "景象")}})
    assert O.bulgular(5) == []


def test_bos_turkce_taraf_atlanir(monkeypatch):
    grup(monkeypatch, {5: {1: ("", "景象"), 2: ("o tekinsiz", "景象")}})
    assert [p for p, _ in O.bulgular(5)] == [2]


def test_bos_zh_tarafi_atlanir(monkeypatch):
    # ZH bos ya da yalniz bosluksa karsilastirilacak Cince yoktur; bulgu degil gurultu.
    grup(monkeypatch, {5: {1: ("o tekinsiz manzara", ""), 2: ("o tekinsiz manzara", " \n ")}})
    assert O.bulgular(5) == []


def test_birden_cok_o_ve_baglam_kesilir(monkeypatch):
    uzun = "a" * 100 + " o tekinsiz " + "b" * 100 + " o ürkütücü " + "c" * 100
    grup(monkeypatch, {5: {1: (uzun, "景象")}})
    b = O.bulgular(5)
    assert len(b) == 2
    assert all(len(parca) < 90 for _, parca in b)           # 40 once + eslesme + 30 sonra


def test_satir_sonu_baglamda_bosluga_cevrilir(monkeypatch):
    grup(monkeypatch, {5: {1: ("ilk satır\nve o tekinsiz\nson", "景象")}})
    (_, parca), = O.bulgular(5)
    assert "\n" not in parca


def test_bolum_yoksa_bos(monkeypatch):
    grup(monkeypatch, {})
    assert O.bulgular(99) == []


# ------------------------------------------------------------------ main

def test_main_arguman_yoksa_kullanim_ve_cikis_1(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["o_denetle.py"])
    assert O.main() == 1
    assert "Kullanim" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["o_denetle.py", "1", "2"])
    assert O.main() == 1


def test_main_tek_bolum_bulgusuz_de_baslik_yazar(monkeypatch, capsys):
    grup(monkeypatch, {5: {1: ("temiz metin", "他")}})
    monkeypatch.setattr("sys.argv", ["o_denetle.py", "5"])
    assert O.main() == 0
    out = capsys.readouterr().out
    assert "=== 5: 0 şüpheli" in out and "özet" not in out


def test_main_tek_bolum_bulgu_cikis_yine_0(monkeypatch, capsys):
    grup(monkeypatch, {5: {3: ("bir o tekinsiz şey", "他")}})
    monkeypatch.setattr("sys.argv", ["o_denetle.py", "5"])
    assert O.main() == 0                                      # rapor adimi
    out = capsys.readouterr().out
    assert "=== 5: 1 şüpheli" in out and "  ¶3: …" in out


def test_main_aralik_yalniz_bulgulu_bolumleri_basar_ve_ozet_verir(monkeypatch, capsys):
    grup(monkeypatch, {
        5: {1: ("temiz", "他")},
        6: {1: ("o tekinsiz", "他"), 2: ("bir o garip", "他")},
        7: {1: ("o tekinsiz", "他那")},
    })
    monkeypatch.setattr("sys.argv", ["o_denetle.py", "5-7"])
    assert O.main() == 0
    out = capsys.readouterr().out
    assert "=== 6: 2 şüpheli" in out
    assert "=== 5:" not in out and "=== 7:" not in out
    assert out.rstrip().endswith("özet: 5:0, 6:2, 7:0")


def test_main_virgullu_liste(monkeypatch, capsys):
    grup(monkeypatch, {5: {1: ("o tekinsiz", "他")}, 8: {1: ("temiz", "他")}})
    monkeypatch.setattr("sys.argv", ["o_denetle.py", "5,8"])
    O.main()
    assert capsys.readouterr().out.rstrip().endswith("özet: 5:1, 8:0")


def test_main_bozuk_aralik_ValueError(monkeypatch):
    grup(monkeypatch, {})
    monkeypatch.setattr("sys.argv", ["o_denetle.py", "9-5"])
    with pytest.raises(ValueError):
        O.main()
