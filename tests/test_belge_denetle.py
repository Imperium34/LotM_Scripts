# -*- coding: utf-8 -*-
"""belge_denetle -- ornek satirlarinda eski kelime, Klein'a ozel isaret, K/N kimlikleri."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import belge_denetle as BD  # noqa: E402

KURAL = """varyantlar:
  - {kavram: R, dogru: ayin, yanlis: [ritüel], istisna: ["şans art[ıi]rma"], ogrenme_bolumu: 28, kesin_gecis: true}
"""


def _kurallar(tmp_path):
    yol = tmp_path / "k.yml"
    yol.write_text(KURAL, encoding="utf-8")
    return BD.kesin_kurallar(yol)


def test_yalniz_ornekte_aranir(tmp_path):
    k = _kurallar(tmp_path)
    metin = ("Kural metni 'ritüel' kelimesini anabilir.\n"
             '- **Örnek:** _"Sen o ritüeli kitaptan okuduğun gibi yaparsan..."_\n'
             'Düz yazıda _"ritüelin bedeli"_ bir alıntı.\n')
    b = BD.ornek_denetle("Side.md", metin, k, klein_mi=False)
    assert [n for _a, n, _m in b] == [2, 3]


def test_sabit_ad_istisnasi(tmp_path):
    k = _kurallar(tmp_path)
    metin = '- **Örnek:** _"Şu dört adımlık şans artırma ritüelini yaparken..."_\n'
    assert BD.ornek_denetle("Klein.md", metin, k, klein_mi=True) == []


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


def test_denetlenmedi_isareti_sayilir(tmp_path, capsys, monkeypatch):
    yol = tmp_path / "Klein.md"
    yol.write_text("- **Örnek:** _\"a\"_ — *x* · ZH denetlenmedi\n- **Örnek:** _\"b\"_\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["belge_denetle.py", "--kurallar", str(tmp_path / "yok.yml"), str(yol)])
    assert BD.main() == 0
    assert "1 örnek Çinceyle denetlenmedi (satır 1)" in capsys.readouterr().out


def test_bolum_harfli_kimlikler():
    klein = ("##### K5.1 — a\n**Gerekçe:** → N-K5.1\n"
             "##### M7 — Yakınlar\n**Gerekçe:** → N-M7\n"
             "##### M0.3 — Biz\n**Gerekçe:** → N-M0.3\n")
    notlar = "**N-K5.1.** x\n**N-M7.** y\n**N-M0.3.** z\n**N-M0 (genel).** w\n**N-M4.** yetim\n"
    b = BD.kimlik_denetle(klein, notlar)
    assert not any(a == "hata" for a, _d, _m in b)
    yetim = [m for a, _d, m in b if a == "uyari"]
    assert len(yetim) == 1 and "N-M4" in yetim[0]
