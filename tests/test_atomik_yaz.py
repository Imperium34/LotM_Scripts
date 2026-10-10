# -*- coding: utf-8 -*-
"""lotm.atomik_yaz -- veri yazan her betigin ortak, yarim dosya birakmayan yazicisi."""

import os
import stat

import pytest

import lotm


def _mod(yol):
    return stat.S_IMODE(os.stat(yol).st_mode)


def test_str_utf8_ve_satir_sonlari_korunur(tmp_path):
    yol = tmp_path / "a.md"
    lotm.atomik_yaz(yol, "şapka\r\nâlem\n")
    assert yol.read_bytes() == "şapka\r\nâlem\n".encode("utf-8")


def test_bytes_oldugu_gibi(tmp_path):
    yol = tmp_path / "a.md"
    lotm.atomik_yaz(yol, b"\xef\xbb\xbfx")
    assert yol.read_bytes() == b"\xef\xbb\xbfx"


def test_var_olan_dosyanin_izinleri_korunur(tmp_path):
    # mkstemp gecici dosyayi 0600 acar; korunmazsa bolum dosyalari
    # yalnizca sahibine okunur kalirdi.
    yol = tmp_path / "0045.md"
    yol.write_text("eski", encoding="utf-8")
    os.chmod(yol, 0o644)
    lotm.atomik_yaz(yol, "yeni")
    assert yol.read_text(encoding="utf-8") == "yeni" and _mod(yol) == 0o644


def test_yeni_dosya_umaska_uyar(tmp_path):
    eski = os.umask(0o022)
    try:
        lotm.atomik_yaz(tmp_path / "yeni.md", "x")
    finally:
        os.umask(eski)
    assert _mod(tmp_path / "yeni.md") == 0o644


def test_sembolik_baglantinin_hedefi_yazilir(tmp_path):
    hedef = tmp_path / "gercek.yml"
    hedef.write_text("eski", encoding="utf-8")
    bag = tmp_path / "bag.yml"
    bag.symlink_to(hedef)
    lotm.atomik_yaz(bag, "yeni")
    assert bag.is_symlink() and hedef.read_text(encoding="utf-8") == "yeni"


def test_hata_olursa_eski_dosya_ve_klasor_temiz_kalir(tmp_path, monkeypatch):
    yol = tmp_path / "sozluk.yml"
    yol.write_text("eski", encoding="utf-8")

    def patla(*_a):
        raise OSError("disk dolu")

    monkeypatch.setattr(lotm.os, "replace", patla)
    with pytest.raises(OSError, match="disk dolu"):
        lotm.atomik_yaz(yol, "yeni")
    assert yol.read_text(encoding="utf-8") == "eski"
    assert [p.name for p in tmp_path.iterdir()] == ["sozluk.yml"]   # gecici dosya kalmadi
