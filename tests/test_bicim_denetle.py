# -*- coding: utf-8 -*-
"""bicim_denetle -- yayin oncesi tek sert kapi: cekirdek kurallar, taban, duzeltme."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bicim_denetle as B  # noqa: E402

FM = '---\nlayout: post\ntitle: "Bölüm 7: X"\n---\n\n'


def _bulgular(tmp_path, govde, ad="0007.md"):
    yol = tmp_path / ad
    yol.write_text(FM + govde, encoding="utf-8")
    _p, bulgular, _t = B.dosyayi_denetle(yol, None)
    return [(b.kod, b.duzey) for b in bulgular], bulgular


def _hatalar(tmp_path, govde):
    kodlar, _ = _bulgular(tmp_path, govde)
    return sorted({k for k, d in kodlar if d == B.HATA})


# ----------------------------------------------------------- tirnak (B01)

def test_cok_paragrafli_replik_gecerli(tmp_path):
    govde = '"Birinci paragraf,\n\n"ikinci paragraf.\n\n"Son paragraf." dedi.\n'
    assert "B01" not in _hatalar(tmp_path, govde)


def test_kapanmamis_replik_hata(tmp_path):
    govde = '"Kapanmadı.\n\nAnlatı devam etti.\n'
    assert "B01" in _hatalar(tmp_path, govde)


def test_bolum_acik_replikle_bitiyor(tmp_path):
    kodlar, bulgular = _bulgular(tmp_path, 'Klein konuştu.\n\n"Açık kaldı.\n')
    assert any(b.kod == "B01" and "bitiyor" in b.mesaj for b in bulgular)


# ------------------------------------------------------------ replik kurallari

def test_virgulle_kapanan_replik(tmp_path):
    assert "B03" in _hatalar(tmp_path, '"Gel," dedi.\n')
    assert "B03" not in _hatalar(tmp_path, '"Gel." dedi.\n')


def test_mektup_hitabi_virgulle_kapanabilir(tmp_path):
    assert "B03" not in _hatalar(tmp_path, 'Kâğıdın en üstüne yazdı.\n\n"Muhterem Hocam,"\n\nDevam etti.\n')
    assert "B03" in _hatalar(tmp_path, '"Ne var ki,"\n')


def test_k03_tarih_ve_kapi_numarasi_sayilmaz():
    import bicim_denetle as B
    assert B._RAKAM_TARIH_SONRA.match(" Mayıs. Bay Azik")
    assert B._RAKAM_TARIH_SONRA.match("'sinde yani")
    assert B._RAKAM_TARIH_ONCE.search("Hatta ayın ")
    assert B._RAKAM_ADRES_SONRA.match(" Nergis Sokağı'nın kapısında")
    assert not B._RAKAM_ADRES_SONRA.match(" soli kira ve")
    assert not B._RAKAM_TARIH_SONRA.match(" soli kira")
    assert B._RAKAM_TARIH_ONCE.search("Tuzdiyarı Sokağı ")
    assert B._RAKAM_NUMARA_SONRA.match(" numaraya gitti")
    assert B._RAKAM_ISTISNA.match(" damla kan")


def test_k06_replik_acilisi_tirnakli_ad_degil():
    import bicim_denetle as B
    d = B.kod_adi_deseni()
    if d is None:
        return
    assert d.search("Belki 'Seyirci' iksirinin formülü")
    assert not d.search('"Seyirci\'nin dediği doğru."')


def test_atiftan_sonra_iki_nokta(tmp_path):
    assert "B04" in _hatalar(tmp_path, 'Klein konuştu: "Gel."\n')


def test_italik_kapanisi_ve_tirnakli_ic_ses(tmp_path):
    assert "B06" in _hatalar(tmp_path, "Klein _düşündü_bunu.\n")
    assert "B06" in _hatalar(tmp_path, "Tek _italik açık kaldı.\n")
    assert "B07" in _hatalar(tmp_path, '_"Bu bir iç ses."_\n')
    assert _hatalar(tmp_path, "_Bu bir iç ses._ Klein yürüdü.\n") == []


def test_ilah_zamiri(tmp_path):
    assert "B08" in _hatalar(tmp_path, "Herkes Onun adını andı.\n")
    assert "B08" not in _hatalar(tmp_path, "Herkes O'nun adını andı.\n")


# ------------------------------------------------------------------ taban

def test_taban_yaz_kapsam_disini_korur(tmp_path):
    """
    REGRESYON: --taban-yaz tabanin tamamini simdiki bulgularla yaziyordu;
    tek bolum ya da --kod ile calistirmak geri kalan gecmisi silerdi.
    """
    taban = tmp_path / "taban.tsv"
    taban.write_text(
        "0005.md\tK01\teski kabul\n"
        "0007.md\tB03\teski b03\n"
        "0007.md\tK01\tyedi k01\n",
        encoding="utf-8",
    )
    yeni = [B.Bulgu("B03", B.HATA, "0007.md", 3, "m", "yeni b03")]
    korunan = B.taban_yaz(taban, yeni, ["0007.md"], {"B03"})
    satirlar = taban.read_text(encoding="utf-8").splitlines()
    assert korunan == 2
    assert satirlar == ["0005.md\tK01\teski kabul", "0007.md\tK01\tyedi k01",
                        "0007.md\tB03\tyeni b03"]


def test_taban_yaz_kodsuz_taranan_dosyanin_tamamini_yeniler(tmp_path):
    taban = tmp_path / "taban.tsv"
    taban.write_text("0007.md\tK01\teski\n0008.md\tK01\tsekiz\n", encoding="utf-8")
    B.taban_yaz(taban, [], ["0007.md"])
    assert taban.read_text(encoding="utf-8") == "0008.md\tK01\tsekiz\n"


# ---------------------------------------------------------------- duzeltme

def test_duzelt_uygula_yalniz_guvenliyi_yazar_satirlari_korur(tmp_path, capsys):
    yol = tmp_path / "0007.md"
    yol.write_text(
        FM
        + '"Gel," dedi Klein. Bir sterlin\nverdi , sonra durdu.\n\n'
        + '"Ne var ki," dedi Neil, "bizim işimiz."\n',
        encoding="utf-8",
    )
    yazilan = B.duzelt([yol], None, set(), None, uygula=True)
    sonuc = yol.read_text(encoding="utf-8")
    assert yazilan == 3
    assert '"Gel." dedi Klein. Bir Sterlin\nverdi, sonra durdu.' in sonuc   # satir kirilimi kaldi
    assert '"Ne var ki," dedi Neil, "bizim işimiz."' in sonuc            # atif repligi boluyor: ELLE
    assert sonuc.startswith(FM)
