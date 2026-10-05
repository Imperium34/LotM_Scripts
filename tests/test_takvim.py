# -*- coding: utf-8 -*-
"""takvim_denetle -- baslik tekrari ve carsamba/cumartesi takvimi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import takvim_denetle as T  # noqa: E402


def _klasor(tmp_path, bolumler):
    for no, baslik, tarih in bolumler:
        satirlar = ["---", "layout: post"]
        if baslik is not None:
            satirlar.append(f'title: "{baslik}"')
        if tarih is not None:
            satirlar.append(f"date: {tarih}")
        (tmp_path / f"{no:04d}.md").write_text("\n".join(satirlar + ["---", "", "metin"]),
                                               encoding="utf-8")
    (tmp_path / "index.md").write_text("---\ntitle: x\n---\n", encoding="utf-8")
    return T.kunyeler(tmp_path)


def _mesajlar(bulgu, agirlik=None):
    return [(n, m) for a, n, m in bulgu if agirlik in (None, a)]


def test_duzgun_takvim_temiz(tmp_path):
    ks = _klasor(tmp_path, [
        (44, "Bölüm 44: Bir", "2026-09-26 20:00:00 +0300"),   # cumartesi
        (45, "Bölüm 45: İki", "2026-09-30 20:00:00 +0300"),   # carsamba
        (46, "Bölüm 46: Portre", "2026-10-03 20:00:00 +0300"),  # cumartesi
    ])
    assert T.denetle(ks) == []


def test_ayni_ad_iki_bolumde(tmp_path):
    ks = _klasor(tmp_path, [
        (44, "Bölüm 44: Portre", "2026-09-26 20:00:00 +0300"),
        (45, "Bölüm 45: portre", "2026-09-30 20:00:00 +0300"),   # harf farki sayilmaz
    ])
    hatalar = _mesajlar(T.denetle(ks), "hata")
    assert {n for n, _ in hatalar} == {44, 45}
    assert all("aynı ad" in m for _, m in hatalar)


def test_sapka_farki_da_ayni_ad(tmp_path):
    ks = _klasor(tmp_path, [
        (1, "Bölüm 1: Hâkim", "2026-09-26 20:00:00 +0300"),
        (2, "Bölüm 2: Hakim", "2026-09-30 20:00:00 +0300"),
    ])
    assert any("aynı ad" in m for _, m in _mesajlar(T.denetle(ks), "hata"))


def test_yanlis_gun_ve_yanlis_slot(tmp_path):
    ks = _klasor(tmp_path, [
        (45, "Bölüm 45: A", "2026-09-30 20:00:00 +0300"),   # carsamba
        (46, "Bölüm 46: B", "2026-10-02 20:00:00 +0300"),   # CUMA
    ])
    hatalar = _mesajlar(T.denetle(ks), "hata")
    assert any("cuma" in m and n == 46 for n, m in hatalar)
    assert any("ilk slot 2026-10-03" in m for _, m in hatalar)


def test_atlanan_slot_uyari(tmp_path):
    ks = _klasor(tmp_path, [
        (45, "Bölüm 45: A", "2026-09-30 20:00:00 +0300"),
        (46, "Bölüm 46: B", "2026-10-07 20:00:00 +0300"),   # 10-03 atlanmis
    ])
    b = T.denetle(ks)
    assert _mesajlar(b, "hata") == []
    assert any("1 slot atlanmış" in m for _, m in _mesajlar(b, "uyari"))


def test_numara_bicim_sira_saat(tmp_path):
    ks = _klasor(tmp_path, [
        (44, "Bölüm 44: A", "2026-09-26 20:00:00 +0300"),
        (45, "Bölüm 46: B", "2026-09-26 20:00:00 +0300"),   # numara yanlis, ayni gun
        (46, "C", "2026-10-03 21:00:00 +0300"),             # bicim yok, saat farkli
        (47, "Bölüm 47: D", None),                          # tarih yok
    ])
    b = T.denetle(ks)
    h = _mesajlar(b, "hata")
    assert any(n == 45 and "numara 46" in m for n, m in h)
    assert any(n == 45 and "sonra değil" in m for n, m in h)
    assert any(n == 46 and "biçimi" in m for n, m in h)
    assert any(n == 47 and "tarih yok" in m for n, m in h)
    assert any(n == 46 and "saat" in m for n, m in _mesajlar(b, "uyari"))


def test_baslangic_oncesi_slot_kurali_yok(tmp_path):
    ks = _klasor(tmp_path, [
        (1, "Bölüm 1: A", "2026-01-03 20:00:00 +0300"),     # toplu acilis
        (2, "Bölüm 2: B", "2026-01-10 20:00:00 +0300"),
        (3, "Bölüm 3: C", "2026-01-14 20:00:00 +0300"),
    ])
    assert _mesajlar(T.denetle(ks, baslangic=1), "uyari")
    assert _mesajlar(T.denetle(ks, baslangic=3), "uyari") == []


def test_beklenen_tarih():
    from datetime import datetime
    sat = datetime.strptime("2026-10-03 20:00:00 +0300", "%Y-%m-%d %H:%M:%S %z")
    assert T.sonraki_slot(sat).strftime("%Y-%m-%d %a") == "2026-10-07 Wed"
    wed = datetime.strptime("2026-10-07 20:00:00 +0300", "%Y-%m-%d %H:%M:%S %z")
    assert T.sonraki_slot(wed).strftime("%Y-%m-%d") == "2026-10-10"


def test_saat_dilimsiz_tarih_dusurmez_uyari_verir(tmp_path):
    ks = _klasor(tmp_path, [
        (44, "Bölüm 44: A", "2026-09-26 20:00:00 +0300"),
        (45, "Bölüm 45: B", "2026-09-30 20:00:00"),          # dilim yok
        (46, "Bölüm 46: C", "2026-10-03 20:00:00 +0300"),
    ])
    b = T.denetle(ks)
    assert _mesajlar(b, "hata") == []
    assert any(n == 45 and "saat dilimi yok" in m for n, m in _mesajlar(b, "uyari"))


def test_hic_dilim_yoksa_da_calisir(tmp_path):
    ks = _klasor(tmp_path, [
        (1, "Bölüm 1: A", "2026-09-26 20:00:00"),
        (2, "Bölüm 2: B", "2026-09-30 20:00:00"),
    ])
    assert T.denetle(ks) == []


def test_gecmis_kabul_edilir(tmp_path):
    ks = _klasor(tmp_path, [
        (1, "Bölüm 1: A", "2026-01-09"),                         # cuma, dilimsiz
        (2, "Bölüm 2: B", "2026-05-03"),                         # pazar, 4 ay ara
        (12, "Bölüm 12: C", "2026-06-20 21:00:00 +0300"),
        (13, "Bölüm 13: D", "2026-06-24 20:00:00 +0300"),
        (14, "Bölüm 14: E", "2026-06-27 20:00:00 +0300"),
        (20, "Bölüm 20: F", "2026-07-07 20:00:00 +0300"),        # sali
        (21, "Bölüm 21: G", "2026-07-08 20:00:00 +0300"),        # 20'ye gore dogru slot
    ])
    assert T.denetle(ks, baslangic=13, istisna={20}) == []
    # istisna olmadan 20 yakalanir
    assert any(n == 20 for n, _ in _mesajlar(T.denetle(ks, baslangic=13), "hata"))


def test_gecmis_baslik_ve_sira_kurali_yine_gecerli(tmp_path):
    ks = _klasor(tmp_path, [
        (1, "Bölüm 1: Aynı", "2026-01-09"),
        (2, "Bölüm 2: Aynı", "2026-01-03"),                      # geri gidiyor
    ])
    h = _mesajlar(T.denetle(ks, baslangic=13), "hata")
    assert any("aynı ad" in m for _, m in h) and any("sonra değil" in m for _, m in h)
