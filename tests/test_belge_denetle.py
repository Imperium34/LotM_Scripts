# -*- coding: utf-8 -*-
"""belge_denetle -- ornek satirlarinda eski kelime, Klein'a ozel isaret, K/N kimlikleri."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import belge_denetle as BD  # noqa: E402
import lotm  # noqa: E402

SOZLUK = """\
- terim: Ayin
  ingilizce: Ritual
  eski_karsiliklar: ["ritüel"]
  kategori: Temel Kavramlar
  bolum_siniri: 22

- terim: Sıradışı
  ingilizce: Beyonder
  eski_karsiliklar: ["Olağanüstü"]
  kategori: Kavramlar
"""


def _sozluk(tmp_path):
    yol = tmp_path / "sozluk.yml"
    yol.write_text(SOZLUK, encoding="utf-8")
    return yol


def _kurallar(tmp_path):
    return BD.gecis_kurallari(lotm.sozluk_yukle(_sozluk(tmp_path)))


def test_kurallar_sozlukten_gelir(tmp_path):
    k = _kurallar(tmp_path)
    # bolum_siniri olmayan terimin gecisi yok: eski bicimi her yerde eskimis,
    # o yayim_denetle'nin isi, ornek denetimine girmez.
    assert [(kavram, bolum, dogru) for kavram, bolum, dogru, _e in k] == [("Ritual", 22, "Ayin")]


def test_yalniz_ornekte_aranir(tmp_path):
    k = _kurallar(tmp_path)
    metin = ("Kural metni 'ritüel' kelimesini anabilir.\n"
             '- **Örnek:** _"Sen o ritüeli kitaptan okuduğun gibi yaparsan..."_\n'
             'Düz yazıda _"ritüelin bedeli"_ bir alıntı.\n')
    b = BD.ornek_denetle("Side.md", metin, k, klein_mi=False)
    assert [n for _a, n, _m in b] == [2, 3]
    assert all(a == "uyari" and "22." in m for a, _n, m in b)


def test_tamamdir_yalniz_klein(tmp_path):
    metin = '- **Örnek:** _"Tamamdır!" diye bağırdı._\n'
    assert BD.ornek_denetle("Klein.md", metin, [], klein_mi=True) == []
    b = BD.ornek_denetle("Side.md", metin, [], klein_mi=False)
    assert b and b[0][0] == "hata"


def test_kimlikler():
    klein = ("#### Kural 5: Para\n##### K5.1 — Maddi zemin\n**Gerekçe:** → N-K5.1\n"
             "##### K5.2 — Mikyas\n**Gerekçe:** → N-K5.2\n")
    notlar = "### N-K5 — Para\n**N-K5.1.** ...\n**N-K9.3.** eski not\n"
    b = BD.kimlik_denetle(klein, notlar)
    assert ("hata", "Klein.md", "“→ N-K5.2” atfı var ama notlarda N-K5.2 yok") in b
    assert any(a == "uyari" and "N-K9.3 yetim" in m for a, _d, m in b)
    assert not any("N-K5 " in m and "yetim" in m for _a, _d, m in b)   # bolum notu gecerli


def _main(tmp_path, monkeypatch, *ek):
    # --klein/--notlar acikca verilir: verilmezse main() GERCEK
    # Voice_Maps/Klein.md'yi okur ve test depodaki veriye baglanir.
    monkeypatch.setattr(sys, "argv", ["belge_denetle.py",
                                      "--klein", str(tmp_path / "yok-klein.md"),
                                      "--notlar", str(tmp_path / "yok-notlar.md"), *ek])
    return BD.main()


def test_denetlenmedi_isareti_sayilir(tmp_path, capsys, monkeypatch):
    yol = tmp_path / "Klein.md"
    yol.write_text("- **Örnek:** _\"a\"_ — *x* · ZH denetlenmedi\n- **Örnek:** _\"b\"_\n", encoding="utf-8")
    assert _main(tmp_path, monkeypatch, "--sozluk", str(_sozluk(tmp_path)), str(yol)) == 0
    assert "1 örnek Çinceyle denetlenmedi (satır 1)" in capsys.readouterr().out


def test_main_ornekteki_eski_kelimeyi_bulur(tmp_path, capsys, monkeypatch):
    yol = tmp_path / "Side.md"
    yol.write_text('- **Örnek:** _"O ritüeli bitirdik."_\n', encoding="utf-8")
    assert _main(tmp_path, monkeypatch, "--sozluk", str(_sozluk(tmp_path)), str(yol)) == 0
    assert "örnekte “ritüeli” [Ritual]" in capsys.readouterr().out


def test_sozluk_yoksa_sessiz_gecmez(tmp_path, capsys, monkeypatch):
    yol = tmp_path / "Side.md"
    yol.write_text('- **Örnek:** _"O ritüeli bitirdik."_\n', encoding="utf-8")
    _main(tmp_path, monkeypatch, "--sozluk", str(tmp_path / "yok.yml"), str(yol))
    assert "sözlük yok" in capsys.readouterr().err


def test_bolum_harfli_kimlikler():
    klein = ("##### K5.1 — a\n**Gerekçe:** → N-K5.1\n"
             "##### M7 — Yakınlar\n**Gerekçe:** → N-M7\n"
             "##### M0.3 — Biz\n**Gerekçe:** → N-M0.3\n")
    notlar = "**N-K5.1.** x\n**N-M7.** y\n**N-M0.3.** z\n**N-M0 (genel).** w\n**N-M4.** yetim\n"
    b = BD.kimlik_denetle(klein, notlar)
    assert not any(a == "hata" for a, _d, _m in b)
    yetim = [m for a, _d, m in b if a == "uyari"]
    assert len(yetim) == 1 and "N-M4" in yetim[0]
