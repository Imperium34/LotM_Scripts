# -*- coding: utf-8 -*-
"""ses_haritasi.py -- kapsam araliklari, ad anahtarlari, giris ayristirma."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ses_haritasi as H  # noqa: E402


def test_kapsam():
    assert H.kapsar("24–136 · kendisi, geçmişi", 30) is True
    assert H.kapsar("24–136 · kendisi", 200) is False
    assert H.kapsar("Tüm aşamalar · Klein, Cohen", 30) is None
    assert H.kapsar("4.–6. Aşama · replik", 1200, {4: (1166, 1351), 5: (1352, 1380), 6: (1381, 1390)}) is True
    assert H.kapsar("4.–6. Aşama · replik", 30, {4: (1166, 1351), 5: (1352, 1380), 6: (1381, 1390)}) is False
    assert H.kapsar("25 ¶12 örneği", 25) is True  # ¶ numarasi bolum sayilmaz


def test_anahtarlar():
    assert set(H.anahtarlar("Old Neil (İhtiyar Neil) `kaynak: metin`")) >= {"Old Neil", "İhtiyar Neil", "Neil"}
    a = H.anahtarlar("Melissa'nın Arkadaşları: Selena Wood ve Elizabeth (Toplu Harita)")
    assert "Melissa" not in a and "Selena" in a and "Elizabeth" in a
    assert "Gece" not in H.anahtarlar("Tingen Gece Şahinleri — Müfreze (Toplu Harita)")
    assert H.anahtarlar("Susie (Audrey'nin köpeği) `kaynak: metin`") == ["Susie"]
    assert "Fors" not in H.anahtarlar("Dorian Gray Abraham (Fors'un hocası) `kaynak: metin`")


def test_girisler():
    gov = ("**Tarz:** x\n\n##### DUN1.1 — Sakin cümle\n\n**Kapsam:** Tüm aşamalar\n"
           "**Yap:** Cümleleri sakin kur.\n**Yapma:** Üç nokta serpiştirme.\n**Ayar:** _\"Pekâlâ.\"_\n\n"
           "##### DUN1.2 — Soru\n\n**Kapsam:** 24–136\n**Yap:** Soruyla yönlendir.\n")
    g = H.girisler(gov)
    assert [(x["kod"], x["kapsam"]) for x in g] == [("DUN1.1", "Tüm aşamalar"), ("DUN1.2", "24–136")]
    assert g[0]["yapma"] == "Üç nokta serpiştirme."


def test_varsayilan_sicil(tmp_path, monkeypatch):
    yan = tmp_path / "Side_Character_Maps.md"
    yan.write_text("# Baslik\n\n**Varsayılan sicil:** Sade modern değildir.\n\n## 3. Bolum\n\n"
                   "### Roselle Gustav (Günlükler) `kaynak: metin | sicil: modern`\n\n**Tarz:** x\n\n"
                   "### Audrey Hall (Adalet) `kaynak: metin`\n\n**Tarz:** y\n", encoding="utf-8")
    monkeypatch.setattr(H, "YAN", yan)
    assert H.varsayilan_sicil() == "Sade modern değildir."
    assert H.modern_basliklar() == {"Roselle Gustav (Günlükler)"}


def test_kapsar_kural_kodu_ve_genel_ilk_bolum():
    import ses_haritasi as SH
    # 'M1' / '(K2)' sayi degil; ilk bolumu genel olan Kapsam geneldir
    assert SH.kapsar("bütün aşamalar · muhatap yok M1 — İç ses", 82) is None
    assert SH.kapsar("bütün aşamalar · iç ses · mesafe tamamen kapandığında (K2)", 82) is None
    assert SH.kapsar("Arrodes'le bütün konuşmalar · replik · en saf hâli 1390", 82) is None
    assert SH.kapsar("1345–1346 · replik M5 — Esir alan akran", 5) is False
    assert SH.kapsar("561–1366 · replik", 600) is True
    assert SH.kapsar("4.–6. Aşama · replik", 82, {4: (1166, 1351), 5: (1352, 1380), 6: (1381, 1394)}) is False
