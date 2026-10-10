# -*- coding: utf-8 -*-
"""
lotm.kelimeler_yukle ve words.md'nin denetleyicilere girmesi.

Ornek maddeler words.md'nin gercek satir sekillerinden alindi.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lotm  # noqa: E402

WORDS = """\
# I. Kozmoloji
## Mysticism — Working Terms
- **ruhanî varlık** — spirit body, varlık anlamında (灵体); "Ruhanî Beden" ile karıştırılmaz
- **fevkalade mahluk** — extraordinary creatures (超凡物种)
- **Epochs:** Heyûlâ Çağı (1st) → Helak Çağı (3rd)
## Sky & Zodiac
- **Başak, Yengeç, Akrep** — Virgo, Cancer, Scorpio (Roselle'in değiştirme teklifi)
## Tingen — Establishments
- **Bayan Wendy'nin dükkânı/Smyrin Fırını** — Mrs. Wendy's/Smyrin Bakery
## Loen Krallığı
- **Negan Dükü / Negan ailesi** — Başvekil Aguesid Negan'ın ağabeyi (尼根公爵). eşi Della (黛拉夫人)
## Objects
- **damga / damgalamak** — stamp (印章/盖章)
- **Ejderkanı otu (tozu)** — Ejderkanı'nın bitki/toz formu (龙血草粉末)
- **bölme** — ofisin ön salonunu ayıran bölme (隔断)
# VII. Frozen Lines
  1. **Arz ve Semanın Lütufkâr Baki Efendisi** — 仙尊
"""


@pytest.fixture
def terimler(tmp_path):
    yol = tmp_path / "words.md"
    yol.write_text(WORDS, encoding="utf-8")
    return {t.tr: t for t in lotm.kelimeler_yukle(yol)}


def test_basit_madde(terimler):
    t = terimler["fevkalade mahluk"]
    assert (t.en, t.zh) == ("extraordinary creatures", "超凡物种")
    assert t.kategori == "words.md › Mysticism — Working Terms"


def test_ingilizce_turkce_aciklamada_durur(terimler):
    assert terimler["ruhanî varlık"].en == "spirit body"
    assert terimler["bölme"].en is None and terimler["bölme"].zh == "隔断"


def test_esit_sayili_listeler_ayri_terim_olur(terimler):
    assert [terimler[k].en for k in ("Başak", "Yengeç", "Akrep")] == ["Virgo", "Cancer", "Scorpio"]
    assert terimler["Smyrin Fırını"].en == "Smyrin Bakery"


def test_esit_olmayan_listede_ikincisi_arama_adi(terimler):
    assert terimler["damga"].arama_adi == ["damgalamak"] and terimler["damga"].zh == "印章/盖章"
    assert terimler["Negan Dükü"].arama_adi == ["Negan ailesi"]
    assert terimler["Negan Dükü"].zh == "尼根公爵"          # ikinci parantez baska kisi


def test_parantez_ve_madde_olmayanlar(terimler):
    assert "Ejderkanı otu" in terimler                      # "(tozu)" atildi
    assert not any(k.startswith("Epochs") for k in terimler)
    assert not any("Baki Efendisi" in k for k in terimler)  # numarali satir


def test_sozluk_yukle_kelimelerle(tmp_path):
    pytest.importorskip("yaml")
    yml, md = tmp_path / "sozluk.yml", tmp_path / "words.md"
    yml.write_text("- terim: Aşkın\n  ingilizce: Beyonder\n  kategori: Temel Kavramlar\n",
                   encoding="utf-8")
    md.write_text(WORDS, encoding="utf-8")
    assert len(lotm.sozluk_yukle(yml).terimler) == 1
    assert len(lotm.sozluk_yukle(yml, kelimeler=md).terimler) > 1
    with pytest.raises(ValueError):
        lotm.sozluk_yukle(yml, bicim_koru=True, kelimeler=md)


def test_denetleyiciler_words_md_terimini_gorur(tmp_path, monkeypatch):
    import ceviri_denetle as C
    import toplu_denetle as TD
    yol = tmp_path / "words.md"
    yol.write_text(WORDS, encoding="utf-8")
    ts = lotm.kelimeler_yukle(yol)
    monkeypatch.setattr(lotm, "sozluk_yukle",
                        lambda *a, kelimeler=False, **k: lotm.Sozluk(ts if kelimeler else [], veri={}))
    assert C.sozlukten_adaylar("超凡物种", "tr") == ["fevkalade mahluk"]
    cikti, _ = TD.sweep_terimleri("zh", "tr", kelimeler="yalniz")
    assert "印章/盖章" in [s for s, *_ in cikti]
    assert TD.sweep_terimleri("zh", "tr", kelimeler="haric")[0] == []
    # "/" ile iki Cince bicim: ikisi de bulunur
    b = TD.HizalanmisBolum(1, "zh", "tr", "他盖章了。", "Mühürü bastı.",
                           ["他盖章了。"], ["Mühürü bastı."])
    b._sonuc = ({0: [0]}, set())       # hizalama hazir: diske yazilmaz
    ob = {1: b}
    assert len(TD.terimi_tara("印章/盖章", ["damga"], ob, "zh", "tr", duyarsiz=False)) == 1


def test_liste_basligi_terim_degildir(tmp_path):
    yol = tmp_path / "words.md"
    yol.write_text("- **Şans artırma ayini çağrısı** — 福生玄黄…, four steps, counter-clockwise:\n"
                   "  1. **Arz ve Semanın Lütufkâr Baki Efendisi** — 仙尊\n"
                   "- **kâhya** — butler (管家)\n", encoding="utf-8")
    assert [t.tr for t in lotm.kelimeler_yukle(yol)] == ["kâhya"]


def test_tek_karakterlik_cince_anahtar_aranmaz(monkeypatch):
    import toplu_denetle as TD
    ts = [lotm.Terim(tr="Kanun", zh="法", kategori="words.md › Law"),
          lotm.Terim(tr="Beşinci Birim", zh="第五组/组", kategori="words.md › Org")]
    monkeypatch.setattr(lotm, "sozluk_yukle", lambda *a, **k: lotm.Sozluk(ts, veri={}))
    cikti, atlanan = TD.sweep_terimleri("zh", "tr", kelimeler="yalniz")
    assert [s for s, *_ in cikti] == ["第五组"] and atlanan == 1


def test_kose_parantezli_tek_karakter_ve_sirali_cince(tmp_path):
    yol = tmp_path / "words.md"
    yol.write_text("- **sterlin, soli, peni** — pound, soli, pence (「镑」/苏勒/便士)\n"
                   "- **libre** — pound, weight (「磅」)\n"
                   "- **Kanun** — law (法)\n", encoding="utf-8")
    t = {x.tr: x for x in lotm.kelimeler_yukle(yol)}
    assert (t["sterlin"].zh, t["sterlin"].zh_kesin) == ("镑", True)
    assert (t["soli"].zh, t["peni"].zh) == ("苏勒", "便士")
    assert (t["libre"].zh, t["libre"].zh_kesin) == ("磅", True)
    assert (t["Kanun"].zh, t["Kanun"].zh_kesin) == ("法", False)


def test_kasitli_tek_karakter_taranir_digeri_taranmaz(monkeypatch):
    import toplu_denetle as TD
    ts = [lotm.Terim(tr="sterlin", zh="镑", zh_kesin=True, kategori="words.md › X"),
          lotm.Terim(tr="Kanun", zh="法", kategori="words.md › X")]
    monkeypatch.setattr(lotm, "sozluk_yukle", lambda *a, **k: lotm.Sozluk(ts, veri={}))
    cikti, atlanan = TD.sweep_terimleri("zh", "tr", kelimeler="yalniz")
    assert [s for s, *_ in cikti] == ["镑"] and atlanan == 1


def test_sozluk_cince_alani_kose_parantezi_okur():
    assert lotm.zh_ayikla("「镑」") == ("镑", True)
    assert lotm.zh_ayikla("印章/盖章") == ("印章/盖章", False)
    assert lotm.zh_ayikla(None) == (None, False)
