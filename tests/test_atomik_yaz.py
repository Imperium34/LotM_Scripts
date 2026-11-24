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


def test_bolum_yazarlari_ayni_klasor_kilidini_paylasir(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    monkeypatch.setenv("LOTM_YEDEK", str(tmp_path / "yedek"))
    klasor = tmp_path / "bolumler"
    klasor.mkdir()
    takma = tmp_path / "takma"
    takma.symlink_to(klasor, target_is_directory=True)
    yol = klasor / "0001.md"
    yol.write_bytes(b"original\r\n")
    ilk_kilitte, surdur, ikinci_kilit_deniyor = Event(), Event(), Event()
    replace = os.replace
    flock = lotm.fcntl.flock

    def bekle(kaynak, hedef):
        if hedef == yol:
            ilk_kilitte.set()
            assert surdur.wait(5)
        replace(kaynak, hedef)

    def kilitle(fd, kip):
        if ilk_kilitte.is_set():
            ikinci_kilit_deniyor.set()
        return flock(fd, kip)

    monkeypatch.setattr(lotm.os, "replace", bekle)
    monkeypatch.setattr(lotm.fcntl, "flock", kilitle)
    anlik = {yol: yol.read_bytes()}
    with ThreadPoolExecutor(2) as havuz:
        ilk = havuz.submit(lotm.bolumleri_yaz, klasor, anlik, {yol: b"bir"}, etiket="test")
        assert ilk_kilitte.wait(5)
        ikinci = havuz.submit(lotm.bolumleri_yaz, takma, anlik, {yol: b"iki"}, etiket="test")
        try:
            assert ikinci_kilit_deniyor.wait(5)
            assert not ikinci.done()
        finally:
            surdur.set()
        yedek = ilk.result(timeout=5)
        with pytest.raises(lotm.BolumYazmaHatasi, match=r"değişti: .*0001.md"):
            ikinci.result(timeout=5)
    assert yol.read_bytes() == b"bir"
    assert (yedek / yol.name).read_bytes() == b"original\r\n"
    assert len(list((tmp_path / "yedek").rglob(yol.name))) == 1


@pytest.mark.parametrize("editor", [True, False])
def test_yarida_kesilen_yazim_yedekleri_ve_yazilanlari_korur(tmp_path, monkeypatch, editor):
    yedek = tmp_path / "yedek"
    monkeypatch.setenv("LOTM_YEDEK", str(yedek))
    ilk, ikinci = (tmp_path / ad for ad in ("0001.md", "0002.md"))
    anlik = {ilk: b"one\r\n", ikinci: b"two\r\n"}
    for yol, veri in anlik.items():
        yol.write_bytes(veri)
    fsync = os.fsync
    replace = os.replace

    def kaydet(fd):
        fsync(fd)
        if editor and ilk.read_bytes() == b"yeni":
            ikinci.write_bytes(b"editor")

    def degistir(kaynak, hedef):
        if not editor and hedef == ikinci:
            raise OSError("disk arızası")
        replace(kaynak, hedef)

    monkeypatch.setattr(lotm.os, "fsync", kaydet)
    monkeypatch.setattr(lotm.os, "replace", degistir)
    with pytest.raises(lotm.BolumYazmaHatasi, match=r"yazılan dosyalar: .*0001.md; yedek:"):
        lotm.bolumleri_yaz(tmp_path, anlik, {ilk: b"yeni", ikinci: b"yeni"}, etiket="test")
    assert ilk.read_bytes() == b"yeni"
    assert ikinci.read_bytes() == (b"editor" if editor else anlik[ikinci])
    assert {p.name: p.read_bytes() for p in yedek.rglob("*.md")} == {
        p.name: veri for p, veri in anlik.items()}
