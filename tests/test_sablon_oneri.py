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


SOHBET = """## Tarama makbuzu
yok

## F — words.md teklifleri
```md
## Ritual Supplies

- **Cullen** — Cullen (卡伦); teyit bekliyor _89_
```

_Terfi edilmeyecekler:_
- 'fırfır': tek geçişlik.
- **Demirkan Salibi Tarikatı** sozluk.yml'de: `cince` alanına 铁血十字团 eklenmeli.

## G — Yankı defteri teklifleri
yok

## H — Ad kararları
Cullen (卡伦): iki seçenek.
```md
## Ritual Supplies
- **Cullen** — Cullen (卡伦); İngilizce ad korunur; "Callan" yazılmaz _89_
- **Callan** — Cullen (卡伦); istisna; "Cullen" yazılmaz _89_
```

## Ses haritası boşlukları
yok
"""


def test_notlar_kutusuz_ve_f_deki_ad_h_de_sorulmaz():
    md = O.oneriler_kur(89, SOHBET, KELIMELER, "")
    assert "BILGI" not in md and "· AD ·" not in md
    assert md.count("### K") == 1  # yalniz F satiri
    assert "## sozluk.yml'ye elle işlenecek (1)" in md and "铁血十字团" in md
    assert "- (F) 'fırfır': tek geçişlik." in md
    assert "ad sorusu olarak sorulmadı: Cullen, Callan" in md
    assert O.maddeleri_oku(md)[0]["sinif"] == "EKLE"


BOSLUK = """- **Chris** · YENİ · eksik giriş: haritada girişi yok; ¶66 ve ¶69'dan çıkarıldı.
  - Yap: Kısa, resmî, muamelat avukatı dili.
  - Ayar: 87 ¶66: Klein'a ilk selamı.
- **Elizabeth** · ELZ1.1 · çelişki: harita "Rol yapamaz" diyor, ¶52 yarı doğru hikâye anlatıyor.
- Klein, Benson: yok.
- **Dunn:** haritadan.
"""


def test_bosluk_maddeleri_ve_kuyruk():
    m = O.bosluk_maddeleri(BOSLUK)
    assert [a for a, _ in m] == ["Chris", "Elizabeth"]
    assert m[0][1].count("\n") == 2
    q = O.kuyruga_ekle("", "Chris", 87, m[0][1])
    q = O.kuyruga_ekle(q, "Elizabeth", 87, m[1][1])
    q = O.kuyruga_ekle(q, "Chris", 90, "- **Chris** · CHR1.1 · eksik kural: x")
    assert q.startswith("# Ses haritası kuyruğu")
    assert O.kuyruk_sayisi(q) == 3 and q.count("### Chris") == 1
    chris = q.split("### Chris")[1].split("###")[0]
    assert "- [87] **Chris**" in chris and "- [90] **Chris**" in chris and "  - Yap:" in chris


def test_harita_maddesi_oneride():
    s = SOHBET.replace("## Ses haritası boşlukları\nyok", "## Ses haritası boşlukları\n" + BOSLUK)
    md = O.oneriler_kur(87, s, KELIMELER, "", kuyruk=2)
    ms = [x for x in O.maddeleri_oku(md) if x["sinif"] == "HARITA"]
    assert [x["kural"] for x in ms] == ["Chris", "Elizabeth"] and "  - Ayar:" in ms[0]["yeni"]
    assert "kuyruğunda 2 giriş bekliyor" in md
    assert "kuyruğunda" not in O.oneriler_kur(87, s, KELIMELER, "", kuyruk=0)


def test_ses_haritasi_kuyruk_girisleri(tmp_path):
    import ses_haritasi as SH
    k = tmp_path / "Harita_Kuyrugu.md"
    k.write_text("# Ses haritası kuyruğu\n\n### Chris\n\n- [87] **Chris** · YENİ · eksik giriş: x\n\n"
                 "### Leonard Mitchell\n\n- [88] **Leonard Mitchell** · LEO1.1 · eksik kural: y\n",
                 encoding="utf-8")
    eski, SH.KUYRUK = SH.KUYRUK, k
    try:
        g = SH.kuyruk_girisleri("Chris said hello.")
        assert [a for a, _ in g] == ["Chris"]
    finally:
        SH.KUYRUK = eski
