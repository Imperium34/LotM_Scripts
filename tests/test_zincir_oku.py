# -*- coding: utf-8 -*-
"""
zincir_oku.py testleri: duzelticiler ve model SAHTE, her sey tmp_path'te.

zincir_oku yollarini ice aktarma aninda hesaplar (RAPOR, BILINEN, TIKLER, ISTEM
modul sabitleri); testler bunlari monkeypatch ile tmp'e yonlendirir -- betik
degistirilmeden mumkun, cunku hepsi cagri aninda okunur.

Model yerine LOTM_CLAUDE = kucuk bir kabuk betigi: argumanlarini dosyaya yazar,
stdin'i stdout'a basar. (Duz `cat` YETMEZ: sonra.claude_komutu triyaj icin
--allowedTools ekler ve cat bunu tanimaz; bkz. test_cat_tek_basina_yetmez.)
"""

import subprocess
import time

import pytest

import sonra
import zincir_oku as Z

# Fixture duzelt/calistir'i yasaklar; asillari ice aktarma aninda yakalanir.
_asil_duzelt = Z.duzelt
_asil_calistir = Z.calistir

ZINCIR = "\x1b[31m[1/10] sapka\x1b[0m\n  3 bulgu\n"


@pytest.fixture
def depo(tmp_path, monkeypatch):
    t = tmp_path
    (t / "Prompts").mkdir()
    istem = t / "Prompts" / "zincir-okuma-istemi.md"
    istem.write_text("ISTEM METNI\n", encoding="utf-8")
    bilinen = t / "bilinen.md"
    bilinen.write_text("- bilinen bulgu: X\n", encoding="utf-8")
    tikler = t / "tikler.md"
    tikler.write_text("- tik: Y\n", encoding="utf-8")
    zincir = t / "zincir.txt"
    zincir.write_text(ZINCIR, encoding="utf-8")
    args = t / "args.txt"
    sahte = t / "sahte.sh"
    sahte.write_text(f'#!/bin/sh\nprintf \'%s\\n\' "$@" > {args}\ncat\n')
    sahte.chmod(0o755)
    monkeypatch.setenv("LOTM_CLAUDE", str(sahte))
    monkeypatch.setattr(Z, "ISTEM", istem)
    monkeypatch.setattr(Z, "BILINEN", bilinen)
    monkeypatch.setattr(Z, "TIKLER", tikler)
    monkeypatch.setattr(Z, "RAPOR", t / "haftalik")
    monkeypatch.setattr(sonra, "KOTA_DOLU", {})
    # Gercek duzelticiye/git'e hicbir yoldan gidilmesin
    def yasak(*a, **k):
        raise AssertionError(f"calistirilmamaliydi: {a}")
    monkeypatch.setattr(Z, "calistir", yasak)
    monkeypatch.setattr(Z, "duzelt", yasak)
    return {"t": t, "zincir": zincir, "args": args, "bilinen": bilinen, "tikler": tikler, "istem": istem}


def bugun():
    return time.strftime("%Y-%m-%d")


def test_kuru_yol_duzeltici_calistirmaz_girdi_dogru_kurulur(depo, capsys):
    gercek_rapor = Z.BETIKLER / "Reports" / "haftalik"
    onceki = sorted(p.name for p in gercek_rapor.glob("*")) if gercek_rapor.exists() else None
    assert Z.main([str(depo["zincir"]), "--kuru"]) == 0
    girdi = (depo["t"] / "haftalik" / f"{bugun()}_girdi.md").read_text(encoding="utf-8")
    assert girdi.startswith("ISTEM METNI")
    assert "<bilinen>\n- bilinen bulgu: X\n</bilinen>" in girdi
    assert "<tikler>\n- tik: Y\n</tikler>" in girdi
    assert "kuru çalıştırma: düzeltici çalıştırılmadı" in girdi
    assert "<zincir_ciktisi>\n[1/10] sapka\n  3 bulgu\n</zincir_ciktisi>" in girdi   # ANSI atildi
    assert "\x1b" not in girdi
    # sahte model girdiyi aynen basti, o rapor oldu
    rapor = (depo["t"] / "haftalik" / f"{bugun()}.md").read_text(encoding="utf-8")
    assert rapor.startswith("ISTEM METNI") and "[1/10] sapka" in rapor
    assert f"rapor: {depo['t'] / 'haftalik' / (bugun() + '.md')}" in capsys.readouterr().out
    # gercek betik klasorundeki rapor klasoru degismedi
    assert onceki == (sorted(p.name for p in gercek_rapor.glob("*")) if gercek_rapor.exists() else None)


def test_kuru_yol_hicbir_sey_tmp_disina_yazilmaz(depo):
    t = depo["t"]
    # betik klasorunun ust duzeyi (kok dosyalar) degismemeli
    beklenen_disi = [Z.BETIKLER]
    onceki = {p: p.stat().st_mtime_ns for d in beklenen_disi for p in d.glob("*") if p.is_file()}
    Z.main([str(depo["zincir"]), "--kuru"])
    sonraki = {p: p.stat().st_mtime_ns for d in beklenen_disi for p in d.glob("*") if p.is_file()}
    assert onceki == sonraki
    yazilan = sorted(p.relative_to(t).as_posix() for p in (t / "haftalik").rglob("*"))
    assert yazilan == sorted([f"haftalik/{bugun()}.md", f"haftalik/{bugun()}_girdi.md"])


def test_model_komutu_triyaj_izinleriyle_kurulur(depo):
    Z.main([str(depo["zincir"]), "--kuru", "--model", "sonnet"])
    args = depo["args"].read_text().split("\n")
    assert "--model" in args and args[args.index("--model") + 1] == "sonnet"
    izinler = args[args.index("--allowedTools") + 1]
    assert izinler == ",".join(sonra.TRIYAJ_ARACLARI) and "Read" in izinler.split(",")


def test_defterler_yoksa_yer_tutucu_yazilir(depo):
    depo["bilinen"].unlink()
    depo["tikler"].unlink()
    Z.main([str(depo["zincir"]), "--kuru"])
    girdi = (depo["t"] / "haftalik" / f"{bugun()}_girdi.md").read_text(encoding="utf-8")
    assert girdi.count("(defter yok)") == 2


def test_model_basarisizsa_cikis_1_girdi_hazir_rapor_yok(depo, capsys, monkeypatch):
    kotu = depo["t"] / "kotu.sh"
    kotu.write_text("#!/bin/sh\ncat >/dev/null\necho patladi >&2\nexit 1\n")
    kotu.chmod(0o755)
    monkeypatch.setenv("LOTM_CLAUDE", str(kotu))
    assert Z.main([str(depo["zincir"]), "--kuru"]) == 1
    cikti = capsys.readouterr().out
    assert "okuma yapilamadi" in cikti and "_girdi.md" in cikti
    assert (depo["t"] / "haftalik" / f"{bugun()}_girdi.md").exists()
    assert not (depo["t"] / "haftalik" / f"{bugun()}.md").exists()


def test_kuru_degilse_duzelt_cagrilir_ciktisi_modele_gider(depo, monkeypatch):
    monkeypatch.setattr(Z, "duzelt", lambda: "DUZELTME OZETI: 2 dosya")
    assert Z.main([str(depo["zincir"])]) == 0
    girdi = (depo["t"] / "haftalik" / f"{bugun()}_girdi.md").read_text(encoding="utf-8")
    assert "<uygulanan_duzeltmeler>\nDUZELTME OZETI: 2 dosya\n</uygulanan_duzeltmeler>" in girdi
    assert "kuru çalıştırma" not in girdi


def test_duzelt_yalniz_haftalik_adimlari_uygular_takvim_haric(depo, monkeypatch):
    cagrilar = []

    def kayit(komut, cwd=Z.BETIKLER):
        cagrilar.append((komut, cwd))
        return "ciktisi" if "duzelt.py" in komut else ""
    monkeypatch.setattr(Z, "calistir", kayit)
    monkeypatch.setattr(Z, "duzelt", _asil_duzelt)
    metin = Z.duzelt()
    komut, cwd = cagrilar[0]
    assert komut[:2] == ["python3", "duzelt.py"] and komut[-2:] == ["--uygula", "--evet"]
    assert komut[2:-2] == Z.HAFTALIK_ADIMLAR and "takvim" not in komut
    assert cwd == Z.BETIKLER
    assert [c[0][:3] for c in cagrilar[1:]] == [["git", "diff", "--stat"]] * 2
    assert cagrilar[1][1] == Z.SITE and cagrilar[2][1] == Z.KOK / "Tools"
    assert "ciktisi" in metin and metin.count("(değişiklik yok)") == 2


def test_calistir_ansi_atar_stderr_ekler(tmp_path):
    out = _asil_calistir(["sh", "-c", "printf '\\033[1mkalin\\033[0m'; echo hata >&2"], tmp_path)
    assert out == "kalin\nhata"


def test_calistir_basarisiz_cikis_kodunu_yazar(tmp_path):
    out = _asil_calistir(["sh", "-c", "echo sorun >&2; exit 2"], tmp_path)
    assert "sorun" in out and "(çıkış kodu: 2)" in out


def test_eksik_zincir_veya_istemde_duzelt_cagrilmaz(depo, capsys):
    # Fixture duzelt()'i yasakliyor; cagrilsa AssertionError atar.
    assert Z.main([str(depo["t"] / "olmayan.txt")]) == 1
    assert "zincir çıktısı yok" in capsys.readouterr().out
    depo["istem"].unlink()
    assert Z.main([str(depo["zincir"])]) == 1
    assert "istem yok" in capsys.readouterr().out


def test_cat_tek_basina_yetmez_allowedtools_yuzunden(tmp_path, monkeypatch):
    # Proje notu "LOTM_CLAUDE=cat model cagirmadan girdi uretir" der; zincir_oku'nun
    # okuma gecisi araclar verdigi icin --allowedTools eklenir ve cat bunu tanimaz.
    monkeypatch.setenv("LOTM_CLAUDE", "cat")
    komut = sonra.claude_komutu(None, sonra.TRIYAJ_ARACLARI)
    assert komut[0] == "cat" and "--allowedTools" in komut
    p = subprocess.run(komut, input="x", capture_output=True, text=True)
    assert p.returncode != 0
