# -*- coding: utf-8 -*-
"""sablon.py -- beceri kesfi, istem_kur, cikti_kurtar, --kopyala, uretim, bayrak denetimi."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import motorlar as M  # noqa: E402
import sablon as SB  # noqa: E402


def _ortam_kur(tmp_path, monkeypatch, no=86):
    kok = tmp_path / "LotM"
    tools = kok / "Tools"
    prompts = tools / "Prompts"
    haritalar = tools / "Voice_Maps"
    sablonlar = tools / "Schemas"
    site = kok / "Imperium34.github.io"
    hazirlik = tmp_path / "hazirlik"
    once_r = tmp_path / "once"
    rapor = tmp_path / "sablon"
    yedek = tmp_path / "yedek"
    for d in (prompts, haritalar, sablonlar, site / "_chapters", hazirlik, once_r / f"Ch_{no}", rapor):
        d.mkdir(parents=True, exist_ok=True)

    cekirdek = prompts / "lotm_system_prompt_v5.1.md"
    cekirdek.write_text("CEKIRDEK\n", encoding="utf-8")
    for parca in SB.BECERI_PARCALARI:
        (prompts / f"lotm_chapter_template_v5_{parca}.md").write_text(f"{parca}\n", encoding="utf-8")
    (haritalar / "Echo_Notes.md").write_text("# Echo\n", encoding="utf-8")
    (haritalar / "Schema.md").write_text("# Schema\n", encoding="utf-8")
    (haritalar / "Klein.md").write_text("# Klein\n", encoding="utf-8")
    (haritalar / "Side_Character_Maps.md").write_text("# Side\n", encoding="utf-8")
    kelimeler = tools / "words.md"
    kelimeler.write_text("# Words\n", encoding="utf-8")
    (hazirlik / f"Ch_{no}_terimler.md").write_text("# Terimler\n", encoding="utf-8")
    (hazirlik / "ayrilmis_dizin.md").write_text("# Dizin\n", encoding="utf-8")
    (once_r / f"Ch_{no}" / "ses_haritasi.md").write_text("# Ses\n", encoding="utf-8")

    monkeypatch.setattr(SB, "KOK", kok)
    monkeypatch.setattr(SB, "TOOLS", tools)
    monkeypatch.setattr(SB, "PROMPTS", prompts)
    monkeypatch.setattr(SB, "HARITALAR", haritalar)
    monkeypatch.setattr(SB, "SITE", site)
    monkeypatch.setattr(SB, "SABLONLAR", sablonlar)
    monkeypatch.setattr(SB, "KELIMELER", kelimeler)
    monkeypatch.setattr(SB, "HAZIRLIK", hazirlik)
    monkeypatch.setattr(SB, "ONCE", once_r)
    monkeypatch.setattr(SB, "RAPOR", rapor)
    monkeypatch.setenv("LOTM_CEKIRDEK", str(cekirdek))
    monkeypatch.setenv("LOTM_YEDEK", str(yedek))
    monkeypatch.setattr(SB, "kaynak_metni", lambda n: "¶1\nZH: 你好\nEN: Hello")
    return {
        "kok": kok, "prompts": prompts, "sablonlar": sablonlar,
        "hazirlik": hazirlik, "once": once_r, "rapor": rapor, "yedek": yedek,
    }


def _tam_sohbet() -> str:
    return "\n\n".join(f"{b}\nyok" for b in SB.BASLIKLAR) + "\n"


def test_beceri_dosyalari_en_yeni_surumu_secer_ve_old_atlar(tmp_path):
    prompts = tmp_path / "Prompts"
    old_dir = prompts / "old"
    old_dir.mkdir(parents=True)
    for v in ("5", "6.1", "6.2"):
        for p in SB.BECERI_PARCALARI:
            (prompts / f"lotm_chapter_template_v{v}_{p}.md").write_text(f"v{v}-{p}\n", encoding="utf-8")
    # old/ altindaki daha yuksek surum numarasi bile secilmemeli.
    for p in SB.BECERI_PARCALARI:
        (old_dir / f"lotm_chapter_template_v99_{p}.md").write_text("eski\n", encoding="utf-8")

    secilen = SB.beceri_dosyalari(prompts)
    assert [p.name for p in secilen] == [
        "lotm_chapter_template_v6.2_SKILL.md",
        "lotm_chapter_template_v6.2_sartname.md",
        "lotm_chapter_template_v6.2_sohbet_ciktilari.md",
    ]


def test_eksik_basliklar_tam_satir_eslesmesi_ister():
    tam = _tam_sohbet()
    assert SB.eksik_basliklar(tam) == []
    # Baslik sonunda ekstra metin varsa sablon_oneri.bolumler bunu yakalamaz: eksik sayilmali.
    bozuk = tam.replace("## F — words.md teklifleri", "## F — words.md teklifleri (3)")
    assert SB.eksik_basliklar(bozuk) == ["## F — words.md teklifleri"]


def test_cikti_kurtar_tsv_tek_basina_ve_en_yeni_dosya(tmp_path):
    klasor = tmp_path / "Ch_86"
    klasor.mkdir()
    # Ch_86.md zaten var; yalniz Ch_86_zh.tsv eksik ve iki scratchpad'de bulunuyor.
    (klasor / "Ch_86.md").write_text("# Sablon\n", encoding="utf-8")
    oturum = "11111111-2222-3333-4444-555555555555"
    eski = tmp_path / "claude-a" / "proj" / oturum / "scratchpad" / "Ch_86_zh.tsv"
    yeni = tmp_path / "claude-b" / "proj" / oturum / "scratchpad" / "Ch_86_zh.tsv"
    eski.parent.mkdir(parents=True)
    yeni.parent.mkdir(parents=True)
    eski.write_text("eski\t旧\n", encoding="utf-8")
    yeni.write_text("yeni\t新\n", encoding="utf-8")
    os.utime(eski, (1000, 1000))
    os.utime(yeni, (2000, 2000))

    kurtarilan = SB.cikti_kurtar(klasor, oturum, 86, tmp_kok=tmp_path)
    assert kurtarilan == ["Ch_86_zh.tsv"]
    assert (klasor / "Ch_86_zh.tsv").read_text(encoding="utf-8") == "yeni\t新\n"
    # Bos ya da glob karakterli oturum kimligi hic arama yapmaz.
    assert SB.cikti_kurtar(klasor, "", 86, tmp_kok=tmp_path) == []
    assert SB.cikti_kurtar(klasor, "?", 86, tmp_kok=tmp_path) == []


def test_kopyala_istem_bozmaz_mtime_tazeler_ve_eski_tsv_kaldirir(tmp_path, monkeypatch, capsys):
    d = _ortam_kur(tmp_path, monkeypatch, no=86)
    klasor = d["rapor"] / "Ch_86"
    klasor.mkdir(parents=True)
    (klasor / "istem.md").write_text("ORIJINAL ISTEM\n", encoding="utf-8")
    (klasor / "sohbet.md").write_text(_tam_sohbet(), encoding="utf-8")
    (klasor / "oturum.txt").write_text("abc-123\n", encoding="utf-8")
    cikti = klasor / "Ch_86.md"
    cikti.write_text("# Yeni Sablon\n", encoding="utf-8")
    # Ciktinin mtime'i cok eski olsun (sohbette once duzenlenmis).
    os.utime(cikti, (1000, 1000))

    # Tools/Schemas'ta onceki sablon ve eski zh.tsv dursun.
    (d["sablonlar"] / "Ch_86.md").write_text("# Eski Sablon\n", encoding="utf-8")
    (d["sablonlar"] / "Ch_86_zh.tsv").write_text("eski\t旧\n", encoding="utf-8")

    once_cagrilari = []

    def sahte_run(cmd, **kw):
        once_cagrilari.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "TEMIZ sablon_denetimi.md", "")

    monkeypatch.setattr(SB.subprocess, "run", sahte_run)
    assert SB.main(["86", "--kopyala"]) == 0
    out = capsys.readouterr().out

    # once.py yalniz son denetim icin 1 kez cagrildi; hazirlik / istem.md dokunulmadi.
    assert len(once_cagrilari) == 1
    assert "--sadece-hazirlik" not in once_cagrilari[0]
    assert (klasor / "istem.md").read_text(encoding="utf-8") == "ORIJINAL ISTEM\n"
    # Hedefin mtime'i tazelendi (1000 degil), eski zh.tsv yedeklenip kaldirildi.
    hedef = d["sablonlar"] / "Ch_86.md"
    assert hedef.read_text(encoding="utf-8") == "# Yeni Sablon\n"
    assert hedef.stat().st_mtime > 1000
    assert not (d["sablonlar"] / "Ch_86_zh.tsv").exists()
    assert "eski Ch_86_zh.tsv kaldirildi" in out
    assert list(d["yedek"].rglob("Ch_86_zh.tsv"))


def test_uret_write_ve_edit_izni_verir_ve_eski_oturumu_yedekler(tmp_path, monkeypatch):
    d = _ortam_kur(tmp_path, monkeypatch, no=86)
    klasor = d["rapor"] / "Ch_86"
    klasor.mkdir(parents=True)
    (klasor / "sohbet.md").write_text("ESKI SOHBET\n", encoding="utf-8")
    (klasor / "oturum.txt").write_text("eski-oturum\n", encoding="utf-8")

    once_cagrilari = []

    def sahte_run(cmd, **kw):
        once_cagrilari.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "TEMIZ", "")

    yakalanan = {}

    def sahte_calistir(metin, motor, **kw):
        yakalanan.update(kw)
        (klasor / "Ch_86.md").write_text("# Uretilen\n", encoding="utf-8")
        (klasor / "Ch_86_zh.tsv").write_text("a\t甲\n", encoding="utf-8")
        return M.Sonuc(True, metin=_tam_sohbet(), motor="claude")

    monkeypatch.setattr(SB.subprocess, "run", sahte_run)
    monkeypatch.setattr(M, "calistir", sahte_calistir)

    assert SB.main(["86"]) == 0
    # Step 1 --sadece-hazirlik, Step 4 tam denetim
    assert "--sadece-hazirlik" in once_cagrilari[0]
    assert "--sadece-hazirlik" not in once_cagrilari[1]
    # Write ve Edit her ikisi de izinli; Skill ve --add-dir yok
    araclar = yakalanan["araclar"]
    assert any(a.startswith("Write(//") for a in araclar)
    assert any(a.startswith("Edit(//") for a in araclar)
    assert "Skill" not in araclar
    assert "--add-dir" not in yakalanan["ek_argumanlar"]
    istem = (klasor / "istem.md").read_text(encoding="utf-8")
    assert "Tools/Prompts/old/" in istem
    assert "~/.claude/skills" not in istem
    # Eski oturum yedeklendi
    yedek_sohbetler = list(d["yedek"].rglob("sohbet.md"))
    assert len(yedek_sohbetler) == 1
    assert yedek_sohbetler[0].read_text(encoding="utf-8") == "ESKI SOHBET\n"
    assert (d["sablonlar"] / "Ch_86.md").read_text(encoding="utf-8") == "# Uretilen\n"
    assert (d["sablonlar"] / "Ch_86_zh.tsv").read_text(encoding="utf-8") == "a\t甲\n"


def test_step1_hazirlik_hatasinda_bayat_dokumle_devam_etmez(tmp_path, monkeypatch, capsys):
    _ortam_kur(tmp_path, monkeypatch, no=86)
    # Ch_86_terimler.md zaten diskte var (bayat), ama once.py 1 donuyor.
    monkeypatch.setattr(
        SB.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "HATA: hazirlik uretilemedi", "boom"),
    )
    assert SB.main(["86", "--kuru"]) == 1
    out = capsys.readouterr().out
    assert "HATA: hazirlik" in out and "boom" in out


def test_cakisan_bayraklar_reddedilir(capsys):
    for argv in (
        ["86", "devam", "--kararlar"],
        ["86", "--kuru", "--kopyala"],
        ["86", "--yeniden"],
        ["86", "--kararlar", "--uzerine-yaz"],
        ["86", "oneriler", "--uzerine-yaz"],
    ):
        with pytest.raises(SystemExit) as e:
            SB.main(argv)
        assert e.value.code == 2
        capsys.readouterr()


def test_incele_oneriler_yoksa_ipucu_verir(tmp_path, monkeypatch, capsys):
    _ortam_kur(tmp_path, monkeypatch, no=86)
    assert SB.main(["86", "incele"]) == 1
    assert "sablon 86 oneriler" in capsys.readouterr().out
