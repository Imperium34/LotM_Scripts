# -*- coding: utf-8 -*-
"""fark.py ve lotm.bulgulari_yaz -- "son calistirmadan beri ne degisti?"."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fark as F  # noqa: E402
import lotm  # noqa: E402


def test_yazilan_dosya_anahtara_gore_sirali_tekil_ve_temiz(tmp_path):
    yol = tmp_path / "b" / "lint.tsv"
    lotm.bulgulari_yaz(yol, [
        (("varyant", "0002.md", "Yaratıcı"), "[0002.md:7] ikinci"),
        (("varyant", "0001.md", "a\tb\nc"), "[0001.md:3] satır\nkırık"),
        (("varyant", "0002.md", "Yaratıcı"), "[0002.md:9] tekrar, yazılmaz"),
    ])
    assert yol.read_text(encoding="utf-8").splitlines() == [
        "varyant\t0001.md\ta b c\t[0001.md:3] satır kırık",
        "varyant\t0002.md\tYaratıcı\t[0002.md:7] ikinci",
    ]
    assert F.oku(yol) == {
        "varyant\t0001.md\ta b c": "[0001.md:3] satır kırık",
        "varyant\t0002.md\tYaratıcı": "[0002.md:7] ikinci",
    }


def test_karsilastirma_anahtara_bakar_gorunume_degil():
    # Ayni anahtar, farkli satir numarasi (gorunum): degisiklik DEGIL.
    onceki = {"B03\t0005.md\talinti": "[0005.md:10] ...", "B10\t0005.md\tx": "[0005.md:12] ..."}
    simdiki = {"B03\t0005.md\talinti": "[0005.md:14] ...", "B11\t0006.md\ty": "[0006.md:3] ..."}
    yeni, giden = F.karsilastir(onceki, simdiki)
    assert [a for a, _ in yeni] == ["B11\t0006.md\ty"]
    assert [a for a, _ in giden] == ["B10\t0005.md\tx"]


def _calistir(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["fark.py", *map(str, argv)])
    return F.main()


def test_ilk_kayit_sonra_fark_ve_saklama(tmp_path, monkeypatch, capsys):
    simdiki = tmp_path / "bulgular" / "bicim.tsv"
    lotm.bulgulari_yaz(simdiki, [(("a",), "eski bulgu"), (("b",), "kalan")])
    assert _calistir(monkeypatch, simdiki) == 0
    assert "ilk kayit (2 bulgu)" in capsys.readouterr().out
    assert (tmp_path / "son" / "bicim.tsv").exists()          # bir sonraki icin saklandi

    lotm.bulgulari_yaz(simdiki, [(("b",), "kalan"), (("c",), "yeni bulgu")])
    _calistir(monkeypatch, simdiki)
    cikti = capsys.readouterr().out
    assert "+1 yeni, -1 giden" in cikti
    assert "+ yeni bulgu" in cikti and "- eski bulgu" in cikti and "kalan" not in cikti

    _calistir(monkeypatch, simdiki)                            # ayni sonuc tekrar
    assert "degisiklik yok (2 bulgu)" in capsys.readouterr().out


def test_kaydetme_onceki_kaydi_degistirmez(tmp_path, monkeypatch, capsys):
    simdiki = tmp_path / "bulgular" / "lint.tsv"
    lotm.bulgulari_yaz(simdiki, [(("a",), "bir")])
    _calistir(monkeypatch, simdiki)
    lotm.bulgulari_yaz(simdiki, [(("a",), "bir"), (("b",), "iki")])
    _calistir(monkeypatch, simdiki, "--kaydetme")
    _calistir(monkeypatch, simdiki, "--kaydetme")
    assert capsys.readouterr().out.count("+1 yeni") == 2       # "onceki" ilerlemedi


def test_bos_bulgu_dosyasi_gecerli(tmp_path, monkeypatch, capsys):
    simdiki = tmp_path / "bulgular" / "takvim.tsv"
    lotm.bulgulari_yaz(simdiki, [])
    _calistir(monkeypatch, simdiki)
    _calistir(monkeypatch, simdiki)
    assert "degisiklik yok (0 bulgu)" in capsys.readouterr().out


def test_bicim_anahtari_satir_numarasi_icermez(tmp_path):
    """Ust boslukta bir paragraf eklemek bulgulari 'yeni' yapmamali."""
    import bicim_denetle as B

    def bulgular(govde):
        yol = tmp_path / "0007.md"
        yol.write_text('---\ntitle: "Bölüm 7: X"\n---\n\n' + govde, encoding="utf-8")
        _p, b, _t = B.dosyayi_denetle(yol, None)
        return {b_.anahtar() for b_ in b}

    once = bulgular('"Gel," dedi.\n')
    sonra = bulgular('Yeni bir paragraf eklendi.\n\n"Gel," dedi.\n')
    assert once and once <= sonra
