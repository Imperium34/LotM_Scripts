# -*- coding: utf-8 -*-
"""once.py -- hazirlik bayatligi, sablon_denetle cokme/ozet denetimi, Ch_N_zh.tsv."""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import once  # noqa: E402


def _kur(tmp_path, monkeypatch):
    t = tmp_path
    hazirlik = t / "hazirlik"
    hazirlik.mkdir()
    sablonlar = t / "Schemas"
    sablonlar.mkdir()
    rapor = t / "once"
    veri = t / "sozluk.yml"
    veri.write_text("x: 1\n", encoding="utf-8")
    # Hazirlik dosyalari guncel: calistir.sh cagrilmasin.
    (hazirlik / "Ch_77_terimler.md").write_text("terimler\n", encoding="utf-8")
    (hazirlik / "ayrilmis_dizin.md").write_text("dizin\n", encoding="utf-8")
    (sablonlar / "Ch_77.md").write_text("# Sablon 77\n", encoding="utf-8")

    monkeypatch.setattr(once, "HAZIRLIK", hazirlik)
    monkeypatch.setattr(once, "SABLONLAR", sablonlar)
    monkeypatch.setattr(once, "RAPOR", rapor)
    monkeypatch.setattr(once, "VERILER", [veri])
    # ses_haritasi istege bagli; testte bos metin donerek dis bagimlilik olmasin
    import ses_haritasi as SH
    monkeypatch.setattr(SH, "kaynak_metni", lambda no, tr=False: "")
    return {"t": t, "hazirlik": hazirlik, "sablonlar": sablonlar, "rapor": rapor, "veri": veri}


def test_sablon_denetle_cokerken_eski_rapor_gizlemez(tmp_path, monkeypatch, capsys):
    d = _kur(tmp_path, monkeypatch)
    denetim = d["rapor"] / "Ch_77" / "sablon_denetimi.md"
    denetim.parent.mkdir(parents=True)
    denetim.write_text("# Eski\n\n_0 HATA, 0 UYARI._\n", encoding="utf-8")
    # Sablon denetimden yeni olsun ki yeniden calissin
    os.utime(denetim, (1000, 1000))

    def sahte_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 2, "", "Traceback: patladi")

    monkeypatch.setattr(once.subprocess, "run", sahte_run)
    assert once.main(["77"]) == 1
    assert "HATA: sablon denetimi calismadi" in capsys.readouterr().out
    # Eski rapor bozulmadi ve gecici dosya birakilmadi
    assert "0 HATA" in denetim.read_text(encoding="utf-8")
    assert not denetim.with_name(denetim.name + ".yeni").exists()


def test_bozuk_ozet_satiri_temiz_sayilmaz(tmp_path, monkeypatch, capsys):
    d = _kur(tmp_path, monkeypatch)
    denetim = d["rapor"] / "Ch_77" / "sablon_denetimi.md"
    denetim.parent.mkdir(parents=True)
    denetim.write_text("# Bozuk rapor (ozet yok)\n", encoding="utf-8")
    # Denetim sablon ve veriden yeni: yeniden calismadan dogrudan okunur
    gelecek = max(p.stat().st_mtime for p in [d["sablonlar"] / "Ch_77.md", d["veri"]]) + 10
    os.utime(denetim, (gelecek, gelecek))

    assert once.main(["77"]) == 1
    out = capsys.readouterr().out
    assert "özet satırı okunamadı" in out and "TEMIZ" not in out


def test_zh_yan_dosyasi_bayatlik_tetikler_ve_sablonlar_iletilir(tmp_path, monkeypatch):
    d = _kur(tmp_path, monkeypatch)
    denetim = d["rapor"] / "Ch_77" / "sablon_denetimi.md"
    denetim.parent.mkdir(parents=True)
    denetim.write_text("_0 HATA, 0 UYARI._\n", encoding="utf-8")
    t0 = max(p.stat().st_mtime for p in [d["sablonlar"] / "Ch_77.md", d["veri"]]) + 10
    os.utime(denetim, (t0, t0))

    zh_yan = d["sablonlar"] / "Ch_77_zh.tsv"
    zh_yan.write_text("symbol\t象征\n", encoding="utf-8")
    os.utime(zh_yan, (t0 + 20, t0 + 20))

    cagrilar = []

    def sahte_run(cmd, **kw):
        cagrilar.append(cmd)
        cikti = Path(cmd[cmd.index("--cikti") + 1])
        cikti.write_text("# Denetim\n\n_0 HATA, 1 UYARI._\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(once.subprocess, "run", sahte_run)
    assert once.main(["77"]) == 0
    assert len(cagrilar) == 1
    cmd = cagrilar[0]
    assert "--sablonlar" in cmd and cmd[cmd.index("--sablonlar") + 1] == str(d["sablonlar"])
    assert "1 UYARI" in (d["rapor"] / "Ch_77" / "DURUM.md").read_text(encoding="utf-8")


def test_hata_varsa_cikis_1(tmp_path, monkeypatch):
    d = _kur(tmp_path, monkeypatch)

    def sahte_run(cmd, **kw):
        cikti = Path(cmd[cmd.index("--cikti") + 1])
        cikti.write_text("# Denetim\n\n_2 HATA, 0 UYARI._\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(once.subprocess, "run", sahte_run)
    assert once.main(["77"]) == 1
    assert "HATA      sablon_denetimi.md — 2 HATA, 0 UYARI" in (
        d["rapor"] / "Ch_77" / "DURUM.md").read_text(encoding="utf-8")
