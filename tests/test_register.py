"""lint register sayaci: tam kok, kisa kok + ek, istisnalar (3 Kas)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lint"))
import sozluk_lint as L  # noqa: E402


def say(kokler, metin, istisna=()):
    d = L.register_deseni(kokler, istisna)
    return d.findall(L.diyakritiksiz(L.tr_kucult(metin)))


def test_kirpma_yok():
    # eskiden ilk 6 harf: bendeniz -> benden, gaye -> gayet
    assert say(["bendeniz"], "Benden ne istiyorsun?") == []
    assert say(["gaye"], "Gayet iyi.", ["gayet"]) == []
    assert say(["gaye"], "Gayesi buydu.") == ["gayesi"]


def test_kisa_kok_ek_ister():
    assert say(["baki"], "Bakım yaptı, bakır kap.") == []
    assert say(["baki"], "Baki kalan, bakidir.") == ["baki", "bakidir"]
    assert say(["nail"], "Nailon çorap.", ["nailon"]) == []  # sesliyle devam: istisna gerekir


def test_sapka_ve_buyuk_harf():
    assert say(["sükûnet"], "Sükunetini korudu.") == ["sukunetini"]


def test_istisna():
    assert say(["lisan"], "Lisans aldı, lisanı bozuk.", ["lisans"]) == ["lisanı"]
    assert say(["muhafaza"], "Muhafazakar bir adam.", ["muhafazakar"]) == []
