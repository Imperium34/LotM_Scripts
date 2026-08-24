# -*- coding: utf-8 -*-
"""
Uctan uca: searcher -> etiketle -> denetci2.

Tek tek dogru calisan betikler zincir halinde yanlis calisabilir; asil
kirilgan yer aralarindaki SOZLESME (rapor.tsv anahtarlari, bolum
numaralarinin anlami). Buradaki testler o sozlesmeyi tutar.
"""

import subprocess
import sys

import pytest
from conftest import BETIKLER, en_korpus

EN_BOLUMLER = [
    (1, "The Grey Fog", [
        "Klein opened his eyes in an unfamiliar study.",
        "He had no idea what a Beyonder was at that moment.",
    ]),
    (2, "A Letter", [
        "\"A Beyonder cannot ignore the hunger of the potion,\" Benson said.",
        "The Seer Pathway was only a rumour to him then.",
    ]),
    (21, "The Clown", [
        "The Clown watched from the balcony without speaking.",
        "A Hunter would have moved already, Klein thought.",
    ]),
]

TR_BOLUMLER = {
    1: "Klein gözlerini tanımadığı bir çalışma odasında açtı.\n\n"
       "O anda bir Sıradışı'nın ne olduğu hakkında hiçbir fikri yoktu.\n",
    2: "\"Bir Olağanüstü, iksirin açlığını görmezden gelemez,\" dedi Benson.\n\n"
       "Görücü Yolu o zamanlar onun için bir söylentiden ibaretti.\n",
    21: "Kâhin balkondan sessizce izliyordu.\n\n"
        "Bir Avcı çoktan harekete geçerdi, diye düşündü Klein.\n",
}


@pytest.fixture
def dolu_depo(depo, sozluk_dosyasi):
    (depo / "Source/LotM_Volumes/Volume_1_Clown.txt").write_text(
        en_korpus(EN_BOLUMLER), encoding="utf-8")
    for no, govde in TR_BOLUMLER.items():
        (depo / f"Imperium34.github.io/_chapters/bolum-{no:03d}.md").write_text(
            f"---\nbolum: {no}\n---\n{govde}", encoding="utf-8")
    return depo


def _calistir(betik, *args, kok):
    import os
    ortam = dict(os.environ, LOTM_KOK=str(kok))
    return subprocess.run(
        [sys.executable, str(BETIKLER / betik), *map(str, args)],
        capture_output=True, text=True, env=ortam)


def test_zincir_bastan_sona(dolu_depo, tmp_path):
    sozluk = dolu_depo / "Imperium34.github.io/_data/sozluk.yml"
    rapor = tmp_path / "rapor.tsv"

    s = _calistir("searcher.py", "--sozluk", sozluk,
                  "--kaynak", dolu_depo / "Source/LotM_Volumes",
                  "--rapor", rapor, kok=dolu_depo)
    assert s.returncode == 0, s.stderr
    assert rapor.exists()

    e = _calistir("etiketle.py", "--sozluk", sozluk, "--rapor", rapor,
                  "--yerinde", kok=dolu_depo)
    assert e.returncode == 0, e.stderr

    import yaml
    yaml.safe_load(sozluk.read_text(encoding="utf-8"))  # bozulmadi mi

    d = _calistir("denetci2.py", "--sozluk", sozluk,
                  "--bolumler", dolu_depo / "Imperium34.github.io/_chapters",
                  "--envanter", kok=dolu_depo)
    assert d.returncode == 0, d.stderr
    assert "ESKIMIS KARSILIKLAR" in d.stdout


def test_rapor_anahtarlari_etiketle_ile_ortusur(dolu_depo, tmp_path):
    """
    SOZLESME: searcher'in yazdigi 'terim' sutunu, etiketle'nin aradigi
    anahtarla ayni olmali. arama_adi kullanan terimlerde eskiden
    ayrisiyordu ve o terimler sessizce hic etiketlenmiyordu.
    """
    sozluk = dolu_depo / "Imperium34.github.io/_data/sozluk.yml"
    rapor = tmp_path / "rapor.tsv"
    _calistir("searcher.py", "--sozluk", sozluk,
              "--kaynak", dolu_depo / "Source/LotM_Volumes",
              "--rapor", rapor, kok=dolu_depo)

    satirlar = rapor.read_text(encoding="utf-8").strip().split("\n")
    basliklar = satirlar[0].split("\t")
    ix = basliklar.index("terim")
    rapor_anahtarlari = {s.split("\t")[ix] for s in satirlar[1:]}

    sys.path.insert(0, str(BETIKLER))
    import lotm
    beklenen = {t.anahtar for t in lotm.sozluk_yukle(sozluk).terimler
                if t.anahtar and t.arama_adaylari()}
    assert beklenen <= rapor_anahtarlari, \
        f"raporda eksik anahtarlar: {beklenen - rapor_anahtarlari}"


def test_kapi_ilk_gecisi_gosterir_guveni_degil(dolu_depo, tmp_path):
    """
    'Beyonder' bolum 1'de ipucusuz (orta), bolum 2'de 'potion' ile
    (yuksek) geciyor. Kapi ILK gecis olmali; eskiden guven kazaniyordu ve
    numara ileri kaydiriliyordu.
    """
    sozluk = dolu_depo / "Imperium34.github.io/_data/sozluk.yml"
    rapor = tmp_path / "rapor.tsv"
    _calistir("searcher.py", "--sozluk", sozluk,
              "--kaynak", dolu_depo / "Source/LotM_Volumes",
              "--rapor", rapor, kok=dolu_depo)

    satirlar = rapor.read_text(encoding="utf-8").strip().split("\n")
    basliklar = satirlar[0].split("\t")
    ix = {ad: i for i, ad in enumerate(basliklar)}
    kayit = {s.split("\t")[ix["terim"]]: s.split("\t") for s in satirlar[1:]}

    beyonder = kayit["Beyonder"]
    assert beyonder[ix["bolum"]] == "1", "kapi ilk gecis degil"
    assert beyonder[ix["kanit_bolum"]] == "2"
    assert beyonder[ix["guven"]] == "yuksek"


def test_ceviri_ara_yayimlanmis_metinden_karsilik_cikarir(dolu_depo):
    """
    ceviri_ara.py sozluge degil YAYIMLANMIS metne bakar: bolum 2'de
    eskimis 'Olağanüstü' kullanilmis ve gorulmeli.
    """
    r = _calistir("ceviri_ara.py", "Beyonder", kok=dolu_depo)
    assert r.returncode == 0, r.stderr
    assert "Sıradışı" in r.stdout
    assert "Olağanüstü" in r.stdout


def test_denetci_eskimis_karsiligi_bulur(dolu_depo):
    d = _calistir("denetci2.py", "--sozluk",
                  dolu_depo / "Imperium34.github.io/_data/sozluk.yml",
                  "--bolumler", dolu_depo / "Imperium34.github.io/_chapters",
                  kok=dolu_depo)
    assert "Olağanüstü" in d.stdout
    assert "Falcı" not in d.stdout or "Kâhin" in d.stdout


# ------------------------------------------------- alt dize / golgeleme

GOLGE_SOZLUK = """\
- terim: Avcı
  ingilizce: Hunter
  kategori: Yollar
- terim: Şeytan Avcısı
  ingilizce: Demon Hunter
  kategori: Yollar
"""

GOLGE_BOLUMLER = [
    (1, "Only Long", ["A Demon Hunter walked into the hall."]),
    (2, "Also Long", ["Another Demon Hunter appeared at the gate."]),
    (7, "Standalone", ["The Hunter drew his blade and waited."]),
]


def test_golgelenen_gecis_sayilmaz_bagimsiz_olan_sayilir(depo, tmp_path):
    """
    'Hunter' bolum 1-2'de yalnizca 'Demon Hunter' icinde geciyor; bolum
    7'de bagimsiz. Kapi 7 olmali -- 1 degil.

    Eskiden bu terime HIC bolum yazilmiyordu (once elle ALT_DIZE_RISKI
    listesi, sonra turetilen liste). Gercek calistirmada 32 terim bu
    yuzden donmustu.
    """
    (depo / "Imperium34.github.io/_data/sozluk.yml").write_text(
        GOLGE_SOZLUK, encoding="utf-8")
    (depo / "Source/LotM_Volumes/Volume_1_Clown.txt").write_text(
        en_korpus(GOLGE_BOLUMLER), encoding="utf-8")
    rapor = tmp_path / "rapor.tsv"

    r = _calistir("searcher.py",
                  "--sozluk", depo / "Imperium34.github.io/_data/sozluk.yml",
                  "--kaynak", depo / "Source/LotM_Volumes",
                  "--rapor", rapor, kok=depo)
    assert r.returncode == 0, r.stderr

    satirlar = rapor.read_text(encoding="utf-8").strip().split("\n")
    ix = {ad: i for i, ad in enumerate(satirlar[0].split("\t"))}
    kayit = {s.split("\t")[ix["terim"]]: s.split("\t") for s in satirlar[1:]}

    assert kayit["Hunter"][ix["bolum"]] == "7", "golgeli gecis kapi sayildi"
    assert kayit["Demon Hunter"][ix["bolum"]] == "1"


def test_golgede_mi():
    import sys
    sys.path.insert(0, str(BETIKLER))
    import searcher
    metin = "A Demon Hunter walked."
    bas = metin.index("Hunter")
    son = bas + len("Hunter")
    assert searcher.golgede_mi(metin, bas, son, ["Demon Hunter"])
    assert not searcher.golgede_mi("The Hunter waited.", 4, 10, ["Demon Hunter"])


def test_golge_haritasi_yalnizca_gercek_alt_dizeleri_alir():
    import sys
    sys.path.insert(0, str(BETIKLER))
    import searcher
    terimler = {
        "Hunter": {"adaylar": ["Hunter"]},
        "Demon Hunter": {"adaylar": ["Demon Hunter"]},
        "Beyonder": {"adaylar": ["Beyonder"]},
    }
    harita = searcher.golge_haritasi(terimler)
    assert harita["Hunter"] == ["Demon Hunter"]
    assert "Beyonder" not in harita
    assert "Demon Hunter" not in harita


# --------------------------------------- kapi / ilk gecis ile gurultu

SADIK_SOZLUK = """\
- terim: İlahların Metruk Diyarı
  ingilizce: Forsaken Land of the Gods
  kategori: Temel Kavramlar
  bolum_siniri: 137
  ilk_gecis: 21
"""


def test_ilk_gecisten_sonraki_kullanim_spoiler_sayilmaz(depo):
    """
    Ad bolum 21'de aniliyor, 137'de aciklaniyor. Turkce metnin 21'de adi
    kullanmasi SADAKATTIR. Bu ayrim olmadan boyle terimler her
    calistirmada sonsuza dek 'kapi adayi' olarak cikiyordu.
    """
    (depo / "Imperium34.github.io/_data/sozluk.yml").write_text(
        SADIK_SOZLUK, encoding="utf-8")
    (depo / "Imperium34.github.io/_chapters/bolum-021.md").write_text(
        "---\nbolum: 21\n---\nİlahların Metruk Diyarı'nı arayan gemi kayboldu.\n",
        encoding="utf-8")

    d = _calistir("denetci2.py", "--sozluk",
                  depo / "Imperium34.github.io/_data/sozluk.yml",
                  "--bolumler", depo / "Imperium34.github.io/_chapters",
                  kok=depo)
    assert d.returncode == 0, d.stderr
    assert "KAYNAKTA DA GECIYOR" in d.stdout
    assert "kaynakta da var   : 1" in d.stdout
    assert "kapi (yuksek)     : 0" in d.stdout


def test_ilk_gecisten_once_kullanim_hala_aday(depo):
    """Ingilizce 21'de aniyor; Turkce 5'te kullaniyorsa bu GERCEK spoiler."""
    (depo / "Imperium34.github.io/_data/sozluk.yml").write_text(
        SADIK_SOZLUK, encoding="utf-8")
    (depo / "Imperium34.github.io/_chapters/bolum-005.md").write_text(
        "---\nbolum: 5\n---\nİlahların Metruk Diyarı efsanesi anlatıldı.\n",
        encoding="utf-8")

    d = _calistir("denetci2.py", "--sozluk",
                  depo / "Imperium34.github.io/_data/sozluk.yml",
                  "--bolumler", depo / "Imperium34.github.io/_chapters",
                  kok=depo)
    assert "kapi (yuksek)     : 1" in d.stdout
    assert "kaynakta da var   : 0" in d.stdout
