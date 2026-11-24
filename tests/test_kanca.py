# -*- coding: utf-8 -*-
"""
kancalar/pre-commit -- gecici bir git deposunda gercek commit'lerle.

Kanca INDEX'i denetler: hatali hali sahnelenmis, duzeltmesi yalnizca calisma
agacinda olan bir bolum yine durdurulmali.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

KANCA = Path(__file__).resolve().parent.parent / "kancalar" / "pre-commit"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git yok")

TAKVIM = 'saat: "20:00:00 +0300"\ndonemler:\n  - {baslangic: 1, gunler: [çarşamba, cumartesi]}\n'


def _bolum(no, baslik, tarih, govde):
    return (f'---\nlayout: post\ntitle: "Bölüm {no}: {baslik}"\ndate: {tarih}\n---\n\n'
            f"{govde}\n")


def _git(depo, *arg):
    return subprocess.run(["git", "-C", str(depo), *arg], capture_output=True, text=True)


@pytest.fixture
def depo(tmp_path):
    d = tmp_path / "site"
    (d / "_chapters").mkdir(parents=True)
    (d / "_data").mkdir()
    (d / "_data" / "takvim.yml").write_text(TAKVIM, encoding="utf-8")
    (d / "_chapters" / "0001.md").write_text(
        _bolum(1, "Bir", "2026-09-26 20:00:00 +0300", "Klein yürüdü."), encoding="utf-8")
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "t@t")
    _git(d, "config", "user.name", "t")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "--no-verify", "-m", "ilk")
    os.symlink(KANCA, d / ".git" / "hooks" / "pre-commit")
    return d


def _commit(d, mesaj):
    _git(d, "add", "-A")
    return _git(d, "commit", "-q", "-m", mesaj)


def test_temiz_bolum_gecer(depo):
    (depo / "_chapters" / "0002.md").write_text(
        _bolum(2, "İki", "2026-09-30 20:00:00 +0300", '"Gel." dedi Klein.'), encoding="utf-8")
    r = _commit(depo, "temiz")
    assert r.returncode == 0, r.stdout + r.stderr


def test_bicim_hatasi_durdurur(depo):
    (depo / "_chapters" / "0002.md").write_text(
        _bolum(2, "İki", "2026-09-30 20:00:00 +0300", '"Gel," dedi Klein.'), encoding="utf-8")
    r = _commit(depo, "hatali")
    assert r.returncode != 0 and "B03" in r.stdout + r.stderr


def test_artik_isaret_ve_yanlis_gun_durdurur(depo):
    (depo / "_chapters" / "0002.md").write_text(
        _bolum(2, "İki", "2026-10-02 20:00:00 +0300", "[BELİRSİZ] metin."), encoding="utf-8")
    r = _commit(depo, "iki sorun")
    cikti = r.stdout + r.stderr
    assert r.returncode != 0
    assert "belirsizlik etiketi" in cikti and "cuma" in cikti


def test_index_denetlenir_calisma_agaci_degil(depo):
    yol = depo / "_chapters" / "0002.md"
    yol.write_text(_bolum(2, "İki", "2026-09-30 20:00:00 +0300", '"Gel," dedi Klein.'),
                   encoding="utf-8")
    _git(depo, "add", "-A")
    yol.write_text(_bolum(2, "İki", "2026-09-30 20:00:00 +0300", '"Gel." dedi Klein.'),
                   encoding="utf-8")                       # duzeltme SAHNELENMEDI
    r = _git(depo, "commit", "-q", "-m", "index hatali")
    assert r.returncode != 0 and "B03" in r.stdout + r.stderr


def test_bolum_disi_commit_denetlenmez(depo):
    (depo / "README.md").write_text("x", encoding="utf-8")
    r = _commit(depo, "readme")
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_bekleyen_kesin_lint_duzeltmesi_durdurur(depo):
    # Neil'in -> Neil'ın: lint-kurallari.yml'de dogru_ekler tanimli.
    (depo / "_chapters" / "0002.md").write_text(
        _bolum(2, "İki", "2026-09-30 20:00:00 +0300", "Neil'in şapkası."), encoding="utf-8")
    r = _commit(depo, "ek")
    assert r.returncode != 0
    assert "kesin duzeltme bekliyor (lint)" in r.stdout + r.stderr


def test_bekleyen_sapka_duzeltmesi_durdurur_sozluk_varsa(depo):
    (depo / "_data" / "sozluk.yml").write_text("- terim: Ay\n", encoding="utf-8")
    (depo / "_chapters" / "0002.md").write_text(
        _bolum(2, "İki", "2026-09-30 20:00:00 +0300", "Pekala, dedi Klein."), encoding="utf-8")
    r = _commit(depo, "sapka")
    assert r.returncode != 0
    assert "kesin duzeltme bekliyor (sapka)" in r.stdout + r.stderr


def test_sapka_kancasi_words_md_yonunu_duzelt_gibi_kullanir(depo, monkeypatch, tmp_path):
    # words.md 'evlat' duz yaziyor: duzelt.py dokunmaz, kanca da durmamali.
    (depo / "_data" / "sozluk.yml").write_text("- terim: Ay\n", encoding="utf-8")
    kel = tmp_path / "words.md"
    kel.write_text("- **evlat** — 小子\n", encoding="utf-8")
    monkeypatch.setenv("LOTM_KELIMELER", str(kel))
    (depo / "_chapters" / "0002.md").write_text(
        _bolum(2, "İki", "2026-09-30 20:00:00 +0300", "Gel evlat, dedi Klein."), encoding="utf-8")
    r = _commit(depo, "evlat")
    assert r.returncode == 0, r.stdout + r.stderr


def test_sapka_ve_bicim_index_sozlugunu_kullanir(depo):
    sozluk = depo / "_data" / "sozluk.yml"
    sozluk.write_text("- terim: Pekâlâ\n- terim: Denizci\n  kategori: Tarot Cemiyeti\n")
    bolum = depo / "_chapters" / "0002.md"
    govde = "Pekala, diye düşündü. 'Denizci' olduğunu söyledi."
    # B03 hatası biçim çıktısını gösterir. K06 kendi başına yalnızca uyarıdır.
    bolum.write_text(_bolum(2, "İki", "2026-09-30 20:00:00 +0300",
                            govde + '\n\n"Gel," dedi Klein.'))
    assert _git(depo, "add", "-A").returncode == 0
    sozluk.write_text("- terim: Pekala\n")
    r = _git(depo, "commit", "-q", "-m", "index glossary")
    assert r.returncode == 1
    assert "kesin duzeltme bekliyor (sapka)" in r.stdout + r.stderr
    assert "K06" in r.stdout + r.stderr
    assert _git(depo, "add", str(sozluk)).returncode == 0
    r = _git(depo, "commit", "-q", "-m", "updated glossary")
    assert r.returncode == 1 and "B03" in r.stdout + r.stderr
    assert "K06" not in r.stdout + r.stderr
    assert "kesin duzeltme bekliyor (sapka)" not in r.stdout + r.stderr
    bolum.write_text(_bolum(2, "İki", "2026-09-30 20:00:00 +0300", govde))
    assert _commit(depo, "clean chapter").returncode == 0


def test_index_sozlugu_yokken_calisma_agacindaki_sozluk_atlanir(depo):
    bolum = depo / "_chapters" / "0002.md"
    bolum.write_text(_bolum(2, "İki", "2026-09-30 20:00:00 +0300", "Pekala, dedi Klein."))
    assert _git(depo, "add", str(bolum)).returncode == 0
    (depo / "_data" / "sozluk.yml").write_text("- terim: Pekâlâ\n")
    r = _git(depo, "commit", "-q", "-m", "glossary remains unstaged")
    assert r.returncode == 0, r.stdout + r.stderr
