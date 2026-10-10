# -*- coding: utf-8 -*-
"""
Gecis donemleri: ritüel -> Ayin, mistisizm -> İlm-i Esrar.

Tek kaynak sozluk.yml: eski_karsiliklar + bolum_siniri (bkz.
yayim_denetle.gecis_bolumu). lint bu karari artik TUTMAZ; eski
'ogrenme_bolumu' / 'kesin_gecis' anahtarlari taninmaz ve hata verir.
"""

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
for yol in (KOK, KOK / "lint"):
    sys.path.insert(0, str(yol))

import sozluk_lint as L  # noqa: E402
import toplu_denetle as TD  # noqa: E402
from yayim_denetle import SON_BOLUM, gecis_bolumu  # noqa: E402

KURAL = {"varyantlar": [{
    "kavram": "Ritual (仪式)", "dogru": "ayin", "yanlis": ["ritüel"],
    "istisna": ["şans art[ıi]rma"], "harf_duyarsiz": True,
}]}


def _bulgular(dosyalar, kural=KURAL):
    r = L.Rapor()
    L.denetle_varyant(r, dosyalar, kural)
    return [(b.dosya, b.agirlik, b.mesaj.split("\n")[0]) for b in r.bulgular]


# ------------------------------------------------------------------ lint

def test_lint_varyant_her_bolumde_her_seste_hata():
    for ad in ("0009.md", "0040.md"):
        b = _bulgular({ad: 'Ritüel bitti. "Bir ritüel," dedi Neil. _Şu ritüel..._'})
        assert len(b) == 3 and all(a == "hata" for _d, a, _m in b)


def test_lint_istisna():
    assert _bulgular({"0040.md": "Şans artırma ritüelini hatırladı."}) == []


def test_lint_gecis_anahtarlari_artik_taninmaz():
    for anahtar in ("ogrenme_bolumu", "kesin_gecis", "sadece_anlatici"):
        kural = {"varyantlar": [dict(KURAL["varyantlar"][0], **{anahtar: 33})]}
        b = _bulgular({"0040.md": "Ritüel bitti."}, kural)
        # kural atlanir (metin bulgusu yok), dosya hatasi raporlanir
        assert b == [("lint-kurallari.yml", "hata", b[0][2])]
        assert anahtar in b[0][2] and "atlandi" in b[0][2]


# ------------------------------------------------------- gecis_bolumu

class _T:
    def __init__(self, bolum_siniri):
        self.bolum_siniri = bolum_siniri


def test_gecis_bolumu_gercek_kapi():
    assert gecis_bolumu(_T(22)) == 22


def test_gecis_bolumu_kapi_yoksa_her_bolumde_eskimis():
    for deger in (None, 0, SON_BOLUM, SON_BOLUM + 1):
        assert gecis_bolumu(_T(deger)) is None


# ----------------------------------------------------------- toplu

def _v(bolum, bulunan):
    return {"bolum": bolum, "bulunan_dar": bulunan, "bulunan": bulunan, "tip": "hizali"}


def test_toplu_gecisten_onceki_eski_bicim_terk_edilmis_sayilmaz():
    vuruslar = [_v(9, ["ritüel"]), _v(20, ["ritüel"]), _v(33, ["Ayin"]), _v(40, ["ritüel"])]
    sayim = {"ritüel": 3, "Ayin": 1}
    g, s = TD.eski_ozeti(vuruslar, sayim, {"ritüel"}, 33)
    assert g == {"ritüel"} and s == {"ritüel": 1}            # yalniz bolum 40
    g, s = TD.eski_ozeti(vuruslar[:3], {"ritüel": 2, "Ayin": 1}, {"ritüel"}, 33)
    assert g == set()                                          # temiz: uyari yok
    g, s = TD.eski_ozeti(vuruslar, sayim, {"ritüel"})          # gecis yok: her yerde eskimis
    assert s == {"ritüel": 3}
