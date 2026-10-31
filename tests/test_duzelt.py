# -*- coding: utf-8 -*-
"""
Kesin duzeltmeler: sozluk_lint onergeleri, sapka belge korumasi, words.md
dondurulmus satirlari, duzelt.py'nin kuru / yazan / geri alan akisi.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
for yol in (KOK, KOK / "lint"):
    sys.path.insert(0, str(yol))

import sapka  # noqa: E402
import sozluk_lint as SL  # noqa: E402

KURALLAR = {
    "varyantlar": [
        {"kavram": "Firaset", "dogru": "Firaset'i",
         "yanlis": ["Firaseti", "Firasetini", "Firasetin"],
         "duzelt": {"Firaseti": "Firaset'i", "Firasetini": "Firaset'ini",
                    "Firasetin": "Firaset'in"}},
        {"kavram": "Chaos", "dogru": "Heyûlâ", "yanlis": ["Kaos Çağı"]},
        {"kavram": "Intersea", "dogru": "Ortadeniz", "yanlis": ["Orta Deniz"],
         "duzelt": True, "istisna": ["Orta Deniz Ticaret"]},
    ],
    "yasakli": [
        {"bicim": "tabi ki", "yerine": "tabii ki"},
        {"bicim": "cehliyet", "yerine": "cehalet"},
        {"bicim": "kendimce", "yerine": "bence", "duzelt": False},
    ],
    "ozel_adlar": {
        "Neil": {"dogru_ekler": ["ın", "a", "ı", "dan", "da"]},
        "Melissa": {"dogru_ekler": ["ın", "a", "ı", "dan", "da"]},
        "Benson": {},
    },
}


def _plan(metin):
    return SL.duzeltme_plani(metin, KURALLAR)[0]


def test_varyant_yalniz_duzelt_anahtari_olan_kural_ve_her_bicim_kendi_ekiyle():
    yeni = _plan("Firasetini açtı, Firasetiydi; Firasetin gücü. Kaos Çağı'nda.")
    assert yeni == "Firaset'ini açtı, Firaset'iydi; Firaset'in gücü. Kaos Çağı'nda."


def test_varyant_istisnasi_yalniz_kendi_gecisini_susturur():
    assert _plan("Orta Deniz Ticaret Şirketi; Orta Deniz'de") == \
        "Orta Deniz Ticaret Şirketi; Ortadeniz'de"


def test_tam_kelime_kurali_turemis_kelimeyi_yakalamaz():
    r = SL.Rapor()
    k = {"varyantlar": [{"kavram": "Creator", "dogru": "Yaradan", "yanlis": ["Yaratıcı"],
                         "tam_kelime": True}]}
    SL.denetle_varyant(r, {"1.md": "Yaratıcılık ve Yaratıcı'nın eli. EnYaratıcı"}, k)
    assert [b.bulunan for b in r.bulgular] == ["Yaratıcı"]


def test_kaynastirma_farki_da_duzelir():
    k = {"ozel_adlar": {"Melissa": {"dogru_ekler": ["nın", "ya", "yı", "dan", "da"]},
                        "Klein": {"dogru_ekler": ["ın", "a", "ı", "dan", "da"]}}}
    assert SL.duzeltme_plani("Melissa'ın, Melissa'e, Melissa'den. Klein'nın", k)[0] == \
        "Melissa'nın, Melissa'ya, Melissa'dan. Klein'ın"


def test_ozel_ad_adaylari_turkce_ve_kucuk_harfli_kelimeleri_eler():
    metin = ("Smith'in evi. Smith'e gitti. Smith'ten döndü. Adam'ın adam. "
             "Basiret'i açtı. Basiret'in gücü. Basiret'te. Neil'ın. Neil'a. Neil'ı. "
             "Angelica'nın, Angelica'nın, Angelica'yı.")
    k = {"ozel_adlar": {"Neil": {"dogru_ekler": ["ın", "a", "ı", "dan", "da"]}}}
    ad = SL.ozel_ad_adaylari({"1.md": metin}, k, turkce={"Basiret"})
    assert [a[0] for a in ad] == ["Angelica", "Smith"]
    assert SL.ek_onerisi("Smith", ad[1][3]) == (["in", "e", "i", "ten", "te"], "metinden")
    assert SL.ek_onerisi("Angelica", ad[0][3])[0] == ["nın", "ya", "yı", "dan", "da"]


def test_yasakli_buyuk_harf_korunur_ve_cok_kelimede_sag_sinir_var():
    yeni = _plan("Tabi ki geldi. Ona tabi kimseler. Cehliyetini gördü. Kendimce.")
    assert yeni == "Tabii ki geldi. Ona tabi kimseler. Cehaletini gördü. Kendimce."


def test_yasakli_rapor_da_tabi_kimseyi_yakalamaz():
    r = SL.Rapor()
    SL.denetle_yasakli(r, {"1.md": "Ona tabi kimseler. tabi ki."}, KURALLAR)
    assert [b.bulunan for b in r.bulgular] == ["tabi ki"]


def test_ek_uyumu_tanimli_adda_duzelir():
    yeni = _plan("Neil'in, Neil’e, Neil'den. Melissa'in, Melissa'den. Benson'in.")
    # Benson'un dogru_ekler'i yok: cogunluk tahmini, rapor kalir.
    assert yeni == "Neil'ın, Neil’a, Neil'dan. Melissa'ın, Melissa'dan. Benson'in."


def test_baslik_duzelir_front_matterin_geri_kalani_degismez():
    ham = ('---\nlayout: post\ntitle: "Bölüm 50: İhtiyar Neil\'in Firaseti"\n'
           'date: 2026-10-17 20:00:00 +0300\n---\n\nNeil\'e baktı.\n')
    yeni = _plan(ham)
    assert yeni == ('---\nlayout: post\ntitle: "Bölüm 50: İhtiyar Neil\'ın Firaset\'i"\n'
                    'date: 2026-10-17 20:00:00 +0300\n---\n\nNeil\'a baktı.\n')


def test_rapor_mesaji_bicime_ozel_hedefi_gosterir():
    r = SL.Rapor()
    SL.denetle_varyant(r, {"1.md": "Firasetini"}, KURALLAR)
    assert "“Firasetini” → “Firaset'ini”" in r.bulgular[0].mesaj


def test_sapka_belgede_ornek_satirina_dokunmaz():
    liste = {"pekala": "pekâlâ"}
    metin = "| pekala | pekâlâ |\nPekala, dedi.\n"
    yeni, n = sapka.cevir_belge(metin, liste)
    assert yeni == "| pekala | pekâlâ |\nPekâlâ, dedi.\n" and n == 1
    # Bolumde koruma yok: ayni paragrafta iki yazim tutarsizliktir.
    assert sapka._cevir("pekala ve pekâlâ", liste)[0] == "pekâlâ ve pekâlâ"


def test_sapka_plan_yazmaz(tmp_path):
    f = tmp_path / "1.md"
    f.write_text("pekala", encoding="utf-8")
    out = sapka.plan({f: "pekala"}, {"pekala": "pekâlâ"})
    assert out == {f: ("pekâlâ", 1)} and f.read_text(encoding="utf-8") == "pekala"


def test_sozluk_gocu_dondurulmus_satirlara_dokunmaz(tmp_path):
    kel = tmp_path / "words.md"
    kel.write_text(
        "# X. Gündelik\n- **pekala** — okay\n"
        "- **sabit** — dondurulmuş; pekala\n"
        "# XII. Frozen Lines\n- **Pekala dedi rubai** — 28 ¶25\n"
        "# Yerleştirilecek\n- **pekala** — x\n", encoding="utf-8")
    sapka.sozluk_gocu(None, kel, {"pekala": "pekâlâ"}, True, False)
    assert kel.read_text(encoding="utf-8") == (
        "# X. Gündelik\n- **pekâlâ** — okay\n"
        "- **sabit** — dondurulmuş; pekala\n"
        "# XII. Frozen Lines\n- **Pekala dedi rubai** — 28 ¶25\n"
        "# Yerleştirilecek\n- **pekâlâ** — x\n")


# ------------------------------------------------------------ duzelt.py


def _kok(tmp_path):
    bol = tmp_path / "Imperium34.github.io/_chapters"
    bol.mkdir(parents=True)
    (tmp_path / "Imperium34.github.io/_data").mkdir()
    (tmp_path / "Imperium34.github.io/_data/sozluk.yml").write_text(
        "- terim: Firaset\n", encoding="utf-8")
    (tmp_path / "Tools").mkdir()
    (tmp_path / "Tools/words.md").write_text("# I\n", encoding="utf-8")
    (bol / "0001.md").write_text(
        '---\nlayout: post\ntitle: "Bölüm 1: Kızıl"\n---\n\nKlein\'in pekala dediği.\n',
        encoding="utf-8")
    (bol / "0002.md").write_text(
        '---\nlayout: post\ntitle: "Bölüm 2: Ay"\n---\n\nTemiz.\n', encoding="utf-8")
    return tmp_path


def _duzelt(kok, *arg):
    env = {**os.environ, "LOTM_KOK": str(kok), "NO_COLOR": "1"}
    env.pop("LOTM_KELIMELER", None)
    return subprocess.run([sys.executable, str(KOK / "duzelt.py"), "sapka", "lint", *arg],
                          capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)


def test_duzelt_kuru_yazmaz_fark_gosterir(tmp_path):
    kok = _kok(tmp_path)
    f = kok / "Imperium34.github.io/_chapters/0001.md"
    once = f.read_bytes()
    r = _duzelt(kok)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "[-Klein'in-]{+Klein'ın+}" in r.stdout
    assert "[-pekala-]{+pekâlâ+}" in r.stdout
    assert f.read_bytes() == once
    assert not (kok / "yedek").exists()


def test_duzelt_etkilesimsiz_uygula_evet_ister(tmp_path):
    kok = _kok(tmp_path)
    r = _duzelt(kok, "--uygula")
    assert r.returncode == 1 and "--evet" in r.stdout
    assert "pekala" in (kok / "Imperium34.github.io/_chapters/0001.md").read_text("utf-8")


def test_duzelt_yedekler_yazar_geri_alir(tmp_path):
    kok = _kok(tmp_path)
    f = kok / "Imperium34.github.io/_chapters/0001.md"
    once = f.read_text("utf-8")
    r = _duzelt(kok, "--uygula", "--evet")
    assert r.returncode == 0, r.stdout + r.stderr
    assert f.read_text("utf-8") == once.replace("Klein'in", "Klein'ın").replace("pekala", "pekâlâ")
    yedekler = list((kok / "yedek").glob("*/duzelt-*"))
    assert len(yedekler) == 1
    y = yedekler[0] / "Imperium34.github.io/_chapters/0001.md"
    assert y.read_text("utf-8") == once
    # degismeyen dosya yedeklenmez
    assert not (yedekler[0] / "Imperium34.github.io/_chapters/0002.md").exists()
    # ikinci calistirma: yapacak bir sey yok
    assert _duzelt(kok).returncode == 0
    env = {**os.environ, "LOTM_KOK": str(kok)}
    g = subprocess.run([sys.executable, str(KOK / "duzelt.py"), "--geri-al",
                        str(yedekler[0].relative_to(kok))], capture_output=True, text=True, env=env)
    assert g.returncode == 0, g.stdout + g.stderr
    assert f.read_text("utf-8") == once


def test_duzelt_okunduktan_sonra_degisen_dosyaya_yazmaz(tmp_path, monkeypatch):
    kok = _kok(tmp_path)
    monkeypatch.setenv("LOTM_KOK", str(kok))
    import importlib
    import lotm
    importlib.reload(lotm)
    import duzelt as D
    importlib.reload(D)
    try:
        c = D.Calisma()
        f = (kok / "Imperium34.github.io/_chapters/0001.md").resolve()
        D.adim_sapka(c, [f])
        f.write_text("editorde kaydedildi", encoding="utf-8")
        assert D.yaz(c, c.degisenler()) is None
        assert f.read_text("utf-8") == "editorde kaydedildi"
        c.temizle()
    finally:
        monkeypatch.delenv("LOTM_KOK")
        importlib.reload(lotm)
