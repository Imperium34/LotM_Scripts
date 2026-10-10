# -*- coding: utf-8 -*-
"""takvim_denetle / takvim_ata -- baslik tekrari, _data/takvim.yml'e gore tarihler."""

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import takvim_ata as A  # noqa: E402
import takvim_denetle as T  # noqa: E402

CAR_CMT = """\
saat: "20:00:00 +0300"
donemler:
  - baslangic: {bas}
    gunler: [çarşamba, cumartesi]
{ek}"""


def _takvim(tmp_path, bas=1, ek="", metin=None):
    yol = tmp_path / "takvim.yml"
    yol.write_text(metin if metin is not None else CAR_CMT.format(bas=bas, ek=ek), encoding="utf-8")
    return T.takvim_oku(yol)


def _klasor(tmp_path, bolumler):
    klasor = tmp_path / "_chapters"
    klasor.mkdir(exist_ok=True)
    for no, baslik, tarih in bolumler:
        satirlar = ["---", "layout: post"]
        if baslik is not None:
            satirlar.append(f'title: "{baslik}"')
        if tarih is not None:
            satirlar.append(f"date: {tarih}")
        (klasor / f"{no:04d}.md").write_text("\n".join(satirlar + ["---", "", "metin"]),
                                             encoding="utf-8")
    (klasor / "index.md").write_text("---\ntitle: x\n---\n", encoding="utf-8")
    return T.kunyeler(klasor)


def _denetle(tmp_path, bolumler, **kw):
    takvim = _takvim(tmp_path, **kw)
    return T.denetle(_klasor(tmp_path, bolumler), takvim)


def _mesajlar(bulgu, agirlik=None):
    return [(n, m) for a, n, m, _ilgili in bulgu if agirlik in (None, a)]


def _t(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")


# ------------------------------------------------------------ takvim_oku

def test_takvim_oku_donem_ve_istisna(tmp_path):
    t = _takvim(tmp_path, bas=13, ek='istisnalar:\n  20: "salı çıktı"\n')
    assert t.donem(12) is None and t.donem(13).gunler == {2, 5}
    assert t.takvimde(13) and not t.takvimde(20) and not t.takvimde(12)


@pytest.mark.parametrize("metin, parca", [
    ('saat: "20:00:00 +0300"\ndonemler:\n  - {baslangic: 1, gunler: [cuma]}\nbaslangic: 3\n',
     "taninmayan anahtar"),
    ('saat: 20:00:00\ndonemler:\n  - {baslangic: 1, gunler: [cuma]}\n', "tirnak"),
    ('saat: "20:00:00 +0300"\ndonemler:\n  - {baslangic: 1, gunler: [cumaa]}\n', "gun adi"),
    ('saat: "20:00:00 +0300"\ndonemler:\n  - {baslangic: 1, gunler: [cuma]}\nistisnalar:\n  20: ""\n',
     "gerekce"),
    ('saat: "20:00:00 +0300"\ndonemler:\n  - {baslangic: 5, gunler: [cuma]}\n'
     '  - {baslangic: 2, gunler: [cuma]}\n', "artan"),
    ('saat: "20:00:00 +0300"\n', "en az bir donem"),
])
def test_takvim_oku_gecersizi_reddeder(tmp_path, metin, parca):
    with pytest.raises(T.TakvimHatasi, match=parca):
        _takvim(tmp_path, metin=metin)


def test_sonraki_gun(tmp_path):
    t = _takvim(tmp_path)
    d = t.donem(1)
    assert T.sonraki_gun(_t("2026-10-03 20:00:00 +0300"), d).strftime("%Y-%m-%d %a") == "2026-10-07 Wed"
    assert T.sonraki_gun(_t("2026-10-07 20:00:00 +0300"), d).strftime("%Y-%m-%d") == "2026-10-10"


def test_sonraki_gun_arayi_atlar(tmp_path):
    t = _takvim(tmp_path, ek='aralar:\n  - {bas: 2026-10-07, bit: 2026-10-10, neden: "tatil"}\n')
    assert T.sonraki_gun(_t("2026-10-03 20:00:00 +0300"), t.donem(1), t).strftime("%Y-%m-%d") == "2026-10-14"


# --------------------------------------------------------------- denetle

def test_duzgun_takvim_temiz(tmp_path):
    assert _denetle(tmp_path, [
        (44, "Bölüm 44: Bir", "2026-09-26 20:00:00 +0300"),   # cumartesi
        (45, "Bölüm 45: İki", "2026-09-30 20:00:00 +0300"),   # carsamba
        (46, "Bölüm 46: Portre", "2026-10-03 20:00:00 +0300"),  # cumartesi
    ]) == []


def test_ayni_ad_iki_bolumde(tmp_path):
    hatalar = _mesajlar(_denetle(tmp_path, [
        (44, "Bölüm 44: Portre", "2026-09-26 20:00:00 +0300"),
        (45, "Bölüm 45: portre", "2026-09-30 20:00:00 +0300"),   # harf farki sayilmaz
    ]), "hata")
    assert {n for n, _ in hatalar} == {44, 45}
    assert all("aynı ad" in m for _, m in hatalar)


def test_sapka_farki_da_ayni_ad(tmp_path):
    assert any("aynı ad" in m for _, m in _mesajlar(_denetle(tmp_path, [
        (1, "Bölüm 1: Hâkim", "2026-09-26 20:00:00 +0300"),
        (2, "Bölüm 2: Hakim", "2026-09-30 20:00:00 +0300"),
    ]), "hata"))


def test_yanlis_gun_ve_erken_tarih(tmp_path):
    b = _denetle(tmp_path, [
        (45, "Bölüm 45: A", "2026-09-30 20:00:00 +0300"),   # carsamba
        (46, "Bölüm 46: B", "2026-10-02 20:00:00 +0300"),   # CUMA
    ])
    hatalar = _mesajlar(b, "hata")
    assert any("cuma" in m and n == 46 for n, m in hatalar)
    assert any("ilk yayın günü 2026-10-03" in m for _, m in hatalar)
    # sira bulgusu bir onceki bolume baglidir (--bolum N bununla secer)
    assert any(a == "hata" and n == 46 and ilgili == 45 for a, n, _m, ilgili in b)


def test_atlanan_gun_uyari(tmp_path):
    b = _denetle(tmp_path, [
        (45, "Bölüm 45: A", "2026-09-30 20:00:00 +0300"),
        (46, "Bölüm 46: B", "2026-10-07 20:00:00 +0300"),   # 10-03 atlanmis
    ])
    assert _mesajlar(b, "hata") == []
    assert any("1 yayın günü atlanmış" in m for _, m in _mesajlar(b, "uyari"))


def test_ara_atlanmis_sayilmaz_ama_arada_yayin_hata(tmp_path):
    ara = 'aralar:\n  - {bas: 2026-10-03, bit: 2026-10-03, neden: "bayram"}\n'
    assert _denetle(tmp_path, [
        (45, "Bölüm 45: A", "2026-09-30 20:00:00 +0300"),
        (46, "Bölüm 46: B", "2026-10-07 20:00:00 +0300"),
    ], ek=ara) == []
    h = _mesajlar(_denetle(tmp_path, [
        (45, "Bölüm 45: A", "2026-09-30 20:00:00 +0300"),
        (46, "Bölüm 46: B", "2026-10-03 20:00:00 +0300"),
    ], ek=ara), "hata")
    assert any(n == 46 and "bayram" in m for n, m in h)


def test_numara_bicim_sira_saat(tmp_path):
    b = _denetle(tmp_path, [
        (44, "Bölüm 44: A", "2026-09-26 20:00:00 +0300"),
        (45, "Bölüm 46: B", "2026-09-26 20:00:00 +0300"),   # numara yanlis, ayni gun
        (46, "C", "2026-10-03 21:00:00 +0300"),             # bicim yok, saat farkli
        (47, "Bölüm 47: D", None),                          # tarih yok
    ])
    h = _mesajlar(b, "hata")
    assert any(n == 45 and "numara 46" in m for n, m in h)
    assert any(n == 45 and "sonra değil" in m for n, m in h)
    assert any(n == 46 and "biçimi" in m for n, m in h)
    assert any(n == 47 and "tarih yok" in m for n, m in h)
    assert any(n == 46 and "saat" in m for n, m in _mesajlar(b, "uyari"))


def test_ilk_donemden_once_gun_kurali_yok(tmp_path):
    bolumler = [
        (1, "Bölüm 1: A", "2026-01-03 20:00:00 +0300"),     # toplu acilis
        (2, "Bölüm 2: B", "2026-01-10 20:00:00 +0300"),
        (3, "Bölüm 3: C", "2026-01-14 20:00:00 +0300"),
    ]
    assert _mesajlar(_denetle(tmp_path, bolumler, bas=1), "uyari")
    assert _mesajlar(_denetle(tmp_path, bolumler, bas=3), "uyari") == []


def test_saat_dilimsiz_tarih_dusurmez_uyari_verir(tmp_path):
    b = _denetle(tmp_path, [
        (44, "Bölüm 44: A", "2026-09-26 20:00:00 +0300"),
        (45, "Bölüm 45: B", "2026-09-30 20:00:00"),          # dilim yok
        (46, "Bölüm 46: C", "2026-10-03 20:00:00 +0300"),
    ])
    assert _mesajlar(b, "hata") == []
    assert any(n == 45 and "saat dilimi yok" in m for n, m in _mesajlar(b, "uyari"))


def test_gecmis_ve_istisna(tmp_path):
    bolumler = [
        (1, "Bölüm 1: A", "2026-01-09"),                         # cuma, dilimsiz
        (2, "Bölüm 2: B", "2026-05-03"),                         # pazar, 4 ay ara
        (12, "Bölüm 12: C", "2026-06-20 21:00:00 +0300"),
        (13, "Bölüm 13: D", "2026-06-24 20:00:00 +0300"),
        (14, "Bölüm 14: E", "2026-06-27 20:00:00 +0300"),
        (20, "Bölüm 20: F", "2026-07-07 20:00:00 +0300"),        # sali
        (21, "Bölüm 21: G", "2026-07-08 20:00:00 +0300"),        # 20'ye gore dogru gun
    ]
    assert _mesajlar(_denetle(tmp_path, bolumler, bas=13,
                              ek='istisnalar:\n  20: "salı çıktı"\n'), "hata") == []
    # istisna olmadan 20 yakalanir
    assert any(n == 20 for n, _ in _mesajlar(_denetle(tmp_path, bolumler, bas=13), "hata"))


def test_gecmis_baslik_ve_sira_kurali_yine_gecerli(tmp_path):
    h = _mesajlar(_denetle(tmp_path, [
        (1, "Bölüm 1: Aynı", "2026-01-09"),
        (2, "Bölüm 2: Aynı", "2026-01-03"),                      # geri gidiyor
    ], bas=13), "hata")
    assert any("aynı ad" in m for _, m in h) and any("sonra değil" in m for _, m in h)


def test_beklenen_tarih_donemin_saatinde(tmp_path):
    ks = _klasor(tmp_path, [
        (44, "Bölüm 44: A", "2026-09-26 21:30:00 +0300"),   # saati yanlis
        (45, "Bölüm 45: B", None),
    ])
    # onceki bolumun saati devralinmaz
    assert T.beklenen_tarih(ks, 45, _takvim(tmp_path)) == _t("2026-09-30 20:00:00 +0300")


# ------------------------------------------------------------- takvim_ata

def test_ata_yayimlanmisa_dokunmaz_sonrakileri_zincirler(tmp_path):
    ks = _klasor(tmp_path, [
        (44, "Bölüm 44: A", "2026-09-26 20:00:00 +0300"),   # yayinda
        (45, "Bölüm 45: B", "2026-10-02 20:00:00 +0300"),   # yanlis gun
        (46, "Bölüm 46: C", None),                          # tarihsiz
    ])
    degisen, _notlar = A.plan_kur(ks, _takvim(tmp_path), _t("2026-09-27 12:00:00 +0300"))
    assert [(k.no, yeni) for k, _e, yeni in degisen] == [
        (45, _t("2026-09-30 20:00:00 +0300")),
        (46, _t("2026-10-03 20:00:00 +0300")),
    ]


def test_ata_gecmise_tarih_vermez(tmp_path):
    ks = _klasor(tmp_path, [
        (44, "Bölüm 44: A", "2026-09-26 20:00:00 +0300"),
        (45, "Bölüm 45: B", None),
    ])
    simdi = _t("2026-10-08 12:00:00 +0300")
    degisen, notlar = A.plan_kur(ks, _takvim(tmp_path), simdi)
    assert degisen[0][2] == _t("2026-10-10 20:00:00 +0300") and degisen[0][2] > simdi
    assert any("geçmişte" in n for n in notlar)


def test_ata_istisnanin_tarihini_korur(tmp_path):
    ks = _klasor(tmp_path, [
        (44, "Bölüm 44: A", "2026-09-26 20:00:00 +0300"),
        (45, "Bölüm 45: B", "2026-09-29 20:00:00 +0300"),   # sali, istisna
        (46, "Bölüm 46: C", None),
    ])
    t = _takvim(tmp_path, ek='istisnalar:\n  45: "salı"\n')
    degisen, _ = A.plan_kur(ks, t, _t("2026-09-27 12:00:00 +0300"))
    assert [(k.no, y) for k, _e, y in degisen] == [(46, _t("2026-09-30 20:00:00 +0300"))]


def test_ata_sira_bozuksa_hicbir_sey_yapmaz(tmp_path):
    ks = _klasor(tmp_path, [
        (44, "Bölüm 44: A", "2026-10-30 20:00:00 +0300"),   # gelecekte
        (45, "Bölüm 45: B", "2026-09-26 20:00:00 +0300"),   # yayinda
    ])
    with pytest.raises(T.TakvimHatasi, match="sıra bozuk"):
        A.plan_kur(ks, _takvim(tmp_path), _t("2026-10-01 12:00:00 +0300"))


def test_yeni_icerik_yalniz_tarih_satirini_degistirir(tmp_path):
    yol = tmp_path / "0045.md"
    yol.write_bytes(b'---\r\ntitle: "B"\r\ndate: 2026-10-02 20:00:00 +0300\r\n---\r\n\r\nmetin date: x\r\n')
    yeni = A.yeni_icerik(yol, _t("2026-09-30 20:00:00 +0300"))
    assert yeni == b'---\r\ntitle: "B"\r\ndate: 2026-09-30 20:00:00 +0300\r\n---\r\n\r\nmetin date: x\r\n'
    yol.write_text('---\ntitle: "B"\n---\nmetin\n', encoding="utf-8")
    assert A.yeni_icerik(yol, _t("2026-09-30 20:00:00 +0300")) == \
        b'---\ntitle: "B"\ndate: 2026-09-30 20:00:00 +0300\n---\nmetin\n'
