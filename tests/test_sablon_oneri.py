# -*- coding: utf-8 -*-
"""sablon_oneri: F satirlarinin degistirme isaretleri ve words.md'ye uygulama."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sablon_oneri as O  # noqa: E402

KELIMELER = """# Words

## Ritual Supplies

- **gümüş bıçak** — silver dagger (银匕) _51_
- **mum** — candle (蜡烛) _5_

## Period Vocabulary

- **yanılsama** — illusion (幻影) _72_
"""


def test_isaret_bicimleri():
    kod = [
        "## Ritual Supplies",
        "- **gümüş bıçak** — silver dagger (银匕/银制小刀) _51_   ← DEĞİŞTİRME: anahtar eklendi",
        "- **mum** — candle (蜡烛/白蜡烛) _5_ ← replacement",
        "- **kâse** — bowl (碗) _86_",
        "## Period Vocabulary ← DEĞİŞTİRME",
        "- **yanılsama** — illusion (幻影/幻象) _72_",
    ]
    s = O.f_satirlari(kod)
    assert [x[2] for x in s] == [True, True, False, True]
    assert s[0][3] == "anahtar eklendi" and "←" not in s[0][1]
    assert s[3][0] == "Period Vocabulary"


def test_eski_bul_ve_ekle():
    eski, _ = O.eski_bul("- **gümüş bıçak** — silver dagger (银匕/银制小刀) _51_", KELIMELER)
    assert eski == "- **gümüş bıçak** — silver dagger (银匕) _51_"
    eski, _ = O.eski_bul("- **gümüş hançer** — silver dagger (银匕) _51_", KELIMELER)  # Cince anahtardan
    assert eski.startswith("- **gümüş bıçak**")
    yeni = O.basliga_ekle(KELIMELER, "Ritual Supplies", "- **kâse** — bowl (碗) _86_")
    assert yeni.index("**kâse**") < yeni.index("## Period") and yeni.index("**mum**") < yeni.index("**kâse**")
    assert O.basliga_ekle(KELIMELER, "Yok Böyle", "x") is None


def test_donmus():
    blok = '### # · x\n- **Donmuş:** "kara yeşil", "aşındır-"\n'
    assert O.donmus_eksik(blok, "kara yeşil leke aşındırdı") == []
    assert O.donmus_eksik(blok, "yeşil") == ["kara yeşil", "aşındır"]


def test_metinde_mi():
    b = "Kardeşim, niye gidip kalemle, fincanla cin çağırmıyorsunuz?"
    assert O.metinde_mi("- **kalemle cin çağırma** — x (笔仙) _85_", b)
    assert not O.metinde_mi("- **kalemle ruh çağırma** — x (笔仙) _85_", b)
    assert O.metinde_mi("- **ruh çağırma / cin çağırma** — x (笔仙) _85_", b)


if __name__ == "__main__":
    for ad, f in list(globals().items()):
        if ad.startswith("test_"):
            f()
    print("tamam")
