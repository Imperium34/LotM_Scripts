# -*- coding: utf-8 -*-
"""cevir.py -- ayristir, kontrol_et, bolum_dosyasi, tik_ekle, tarih_ver, cekirdek tazeligi."""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cevir as C  # noqa: E402


def test_ayristir_normal_cerceveli_ve_en_dash():
    ham = "```markdown\n## Bölüm 70 – Kızıl Ay\n\nBirinci paragraf.\n\nİkinci paragraf.\n\n---\n[DURUM NOTU]\nYeni tik: yok\n```"
    p = C.ayristir(ham, 70)
    assert p["baslik"] == "Kızıl Ay" and p["baslik_no"] == 70
    assert p["govde"] == "Birinci paragraf.\n\nİkinci paragraf."
    assert p["durum_notu"].startswith("[DURUM NOTU]")


def test_ayristir_durum_notundaki_baslik_govdeyi_yutmaz():
    # Ustte baslik yok; [DURUM NOTU] icinde bolum basligi geciyor.
    ham = "Birinci paragraf.\n\nİkinci paragraf.\n\n[DURUM NOTU]\n## Bölüm 70: Not\nYeni tik: yok"
    p = C.ayristir(ham, 70)
    assert p["baslik"] is None
    assert "Birinci paragraf." in p["govde"] and "İkinci paragraf." in p["govde"]
    assert "## Bölüm 70: Not" in p["durum_notu"]


def test_ayristir_eslesmeyen_son_cerceve_kirilmaz():
    ham = "## Bölüm 70: Test\n\nMetin.\n\n[DURUM NOTU]\n```text\nornek\n```"
    p = C.ayristir(ham, 70)
    assert p["durum_notu"].endswith("```")


def test_kontrol_et_sert_ve_uyarilar():
    p = {"baslik": "Test", "baslik_no": 71,
         "govde": "İlk paragraf [BELİRSİZ: bak] ve 汉字.\n\n¶2 metin",
         "durum_notu": ""}
    sert, uyari, paragraf = C.kontrol_et(p, 70, 2)
    assert paragraf == 2
    assert any("Çince harf" in s for s in sert)
    assert any("¶ / ZH:" in s for s in sert)
    assert any("başlık numarası 71" in s for s in sert)
    assert any("DURUM NOTU yok" in u for u in uyari)
    assert any("1 [BELİRSİZ]" in u for u in uyari)


def test_kontrol_et_cift_taslak():
    # Ch82/Ch84 (agy): yarim taslak, ardindan bastan tam bolum.
    tam = "Klein kapıyı açtı ve dışarıdaki sisli sokağa uzun uzun baktı.\n\nİkinci paragraf."
    ham = f"## Bölüm 82: Ot Dükkânı\n\n{tam[:70]}\n## Bölüm 82: Ot Dükkânı\n\n{tam}\n\n[DURUM NOTU]\nyok"
    sert, _, _ = C.kontrol_et(C.ayristir(ham, 82), 82, 3)
    assert any("çift taslak" in s and "başlık satırı" in s for s in sert)
    # Baslik tekrarlanmasa da ilk paragraf iki kez.
    ham2 = f"## Bölüm 82: Ot Dükkânı\n\n{tam}\n\n{tam}\n\n[DURUM NOTU]\nyok"
    sert, _, _ = C.kontrol_et(C.ayristir(ham2, 82), 82, 4)
    assert any("ilk paragraf" in s for s in sert)
    # Normal cikti temiz.
    sert, _, _ = C.kontrol_et(C.ayristir(f"## Bölüm 82: Ot\n\n{tam}\n\n[DURUM NOTU]\nyok", 82), 82, 2)
    assert not any("çift taslak" in s for s in sert)


def test_bolum_dosyasi_tirnak_ters_egik_ve_eksik_title():
    # Tirnak ve ters egik cizgi YAML'i bozmaz.
    out = C.bolum_dosyasi('"Kızıl" \\ Ay', 70, "Govde.", None)
    assert 'title: "Bölüm 70: \\"Kızıl\\" \\\\ Ay"' in out
    # Var olan front matter'da date korunur, title yoksa eklenir.
    eski = "---\nlayout: post\ndate: 2026-10-01 20:00:00 +0300\n---\n\nEski."
    out2 = C.bolum_dosyasi("Yeni Başlık", 70, "Yeni.", eski)
    assert 'date: 2026-10-01 20:00:00 +0300' in out2
    assert 'title: "Bölüm 70: Yeni Başlık"' in out2


def test_yeni_tikler_ve_tik_ekle_tekrar_yazmaz(tmp_path, monkeypatch):
    tik_dosya = tmp_path / "alt" / "tikler.md"
    monkeypatch.setattr(C, "TIKLER", tik_dosya)
    notu = "[DURUM NOTU]\n- Yeni tik: yok\n- Yeni tik: **fazla sıfat**\n- Yeni tik: fazla sıfat\n"
    tikler = C.yeni_tikler(notu)
    assert tikler == ["fazla sıfat", "fazla sıfat"]
    assert C.tik_ekle(70, tikler, "opus") == 1
    assert C.tik_ekle(70, tikler, "opus") == 0
    assert tik_dosya.read_text(encoding="utf-8").count("fazla sıfat") == 1


def test_tarih_ver_takvim_hatasini_bildirir(tmp_path, monkeypatch):
    sahte = tmp_path / "takvim_ata.py"
    sahte.write_text("import sys; sys.stderr.write('bozuk takvim\\n'); sys.exit(2)\n", encoding="utf-8")
    monkeypatch.setattr(C, "BETIKLER", tmp_path)
    sonuc = C.tarih_ver(tmp_path / "0070.md")
    assert "HATA" in sonuc and "bozuk takvim" in sonuc


def test_cekirdek_guncellenince_taze_bozulur(tmp_path, monkeypatch):
    sablonlar, bolumler, rapor = tmp_path / "sch", tmp_path / "ch", tmp_path / "rapor"
    sablonlar.mkdir()
    bolumler.mkdir()
    (sablonlar / "Ch_70.md").write_text("# Sablon\n", encoding="utf-8")
    cekirdek = tmp_path / "lotm_system_prompt_v5.0.md"
    cekirdek.write_text("CEKIRDEK v1", encoding="utf-8")
    once = tmp_path / "once.py"
    once.write_text("print('sablon_denetimi.md: 0 HATA')\n", encoding="utf-8")
    takvim = tmp_path / "takvim_ata.py"
    takvim.write_text("print('')\n", encoding="utf-8")
    sayac = tmp_path / "sayac"
    sahte_claude = tmp_path / "claude"
    sahte_claude.write_text(
        f"#!/bin/sh\ncat >/dev/null\necho x >> '{sayac}'\n"
        "printf '## Bölüm 70: Deneme\\n\\nParagraf bir.\\n\\n[DURUM NOTU]\\nYeni tik: yok\\n'\n",
        encoding="utf-8",
    )
    sahte_claude.chmod(0o755)
    monkeypatch.setattr(C, "BETIKLER", tmp_path)
    monkeypatch.setattr(C, "SABLONLAR", sablonlar)
    monkeypatch.setattr(C, "BOLUMLER", bolumler)
    monkeypatch.setattr(C, "RAPOR", rapor)
    monkeypatch.setattr(C, "TIKLER", tmp_path / "tikler.md")
    monkeypatch.setattr(C, "hizali_kaynak", lambda no: ("¶1\nZH: 你好\nEN: Hi", 1, 2))
    monkeypatch.setenv("LOTM_CEKIRDEK", str(cekirdek))
    monkeypatch.setenv("LOTM_CLAUDE", str(sahte_claude))
    monkeypatch.setenv("LOTM_YEDEK", str(tmp_path / "yedek"))

    assert C.main(["70", "--kuru"]) == 0
    assert len(sayac.read_text().splitlines()) == 1
    # Ayni girdi ve cekirdek: model yeniden calismaz.
    assert C.main(["70", "--kuru"]) == 0
    assert len(sayac.read_text().splitlines()) == 1
    # Cekirdek yenilenince taze bozulur ve model tekrar calisir.
    yeni_zaman = time.time() + 10
    os.utime(cekirdek, (yeni_zaman, yeni_zaman))
    assert C.main(["70", "--kuru"]) == 0
    assert len(sayac.read_text().splitlines()) == 2
