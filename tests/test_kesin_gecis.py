# -*- coding: utf-8 -*-
"""
Kesin gecis: ritüel -> ayin (33), mistisizm -> İlm-i Esrar (18).

Ses ayrimi yerine tek bir bolumde temiz gecis. lint ve toplu_denetle ayni
kurali okur.
"""

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
for yol in (KOK, KOK / "lint"):
    sys.path.insert(0, str(yol))

import sozluk_lint as L  # noqa: E402

KURAL = {"varyantlar": [{
    "kavram": "Ritual (仪式)", "dogru": "ayin", "yanlis": ["ritüel"],
    "istisna": ["şans art[ıi]rma"], "harf_duyarsiz": True,
    "ogrenme_bolumu": 33, "kesin_gecis": True,
}]}


def _bulgular(dosyalar, kural=KURAL):
    r = L.Rapor()
    L.denetle_varyant(r, dosyalar, kural)
    return [(b.dosya, b.agirlik, b.mesaj.split("\n")[0]) for b in r.bulgular]


def test_gecisten_once_her_seste_serbest():
    assert _bulgular({"0009.md": 'Ritüel onu tüketmişti. "Ritüeller düzenlerler," dedi Dunn. _O ritüel..._'}) == []


def test_gecisten_sonra_her_seste_hata():
    b = _bulgular({"0040.md": 'Ritüel bitti. "Bir ritüel," dedi Neil. _Şu ritüel..._'})
    assert len(b) == 3 and all(a == "hata" for _d, a, _m in b)


def test_istisna_gecisten_sonra_da_gecerli():
    assert _bulgular({"0040.md": "Şans artırma ritüelini hatırladı."}) == []


def test_yeni_kelime_gecisten_once_uyari():
    b = _bulgular({"0029.md": "Ayinin hazırlığı sürüyordu."})
    assert b and b[0][1] == "uyari" and "gecisten ONCE" in b[0][2]
    assert _bulgular({"0033.md": "Ayin İlmi'nin bir tezahürü."}) == []   # gecis bolumunde serbest


def test_kesin_gecis_yoksa_eski_ses_kurali_aynen():
    eski = {"varyantlar": [dict(KURAL["varyantlar"][0], kesin_gecis=False)]}
    b = _bulgular({"0009.md": "Ritüel onu tüketmişti."}, eski)
    assert b and b[0][1] == "hata" and "anlatici" in b[0][2]


import toplu_denetle as TD  # noqa: E402


def _v(bolum, bulunan):
    return {"bolum": bolum, "bulunan_dar": bulunan, "bulunan": bulunan, "tip": "hizali"}


def test_toplu_gecisten_onceki_eski_bicim_terk_edilmis_sayilmaz():
    vuruslar = [_v(9, ["ritüel"]), _v(20, ["ritüel"]), _v(33, ["Ayin"]), _v(40, ["ritüel"])]
    sayim = {"ritüel": 3, "Ayin": 1}
    g, s = TD.eski_ozeti(vuruslar, sayim, {"ritüel"}, (33, {"ritüel"}))
    assert g == {"ritüel"} and s == {"ritüel": 1}            # yalniz bolum 40
    g, s = TD.eski_ozeti(vuruslar[:3], {"ritüel": 2, "Ayin": 1}, {"ritüel"}, (33, {"ritüel"}))
    assert g == set()                                          # temiz: uyari yok
    g, s = TD.eski_ozeti(vuruslar, sayim, {"ritüel"})          # kural yok: eski davranis
    assert s == {"ritüel": 3}


def test_toplu_lint_kuralini_okur(tmp_path):
    yol = tmp_path / "lint-kurallari.yml"
    yol.write_text("varyantlar:\n"
                   "  - {kavram: R, dogru: ayin, yanlis: [ritüel], ogrenme_bolumu: 33, kesin_gecis: true}\n"
                   "  - {kavram: M, dogru: İlm-i Esrar, yanlis: [mistisizm], ogrenme_bolumu: 18}\n",
                   encoding="utf-8")
    assert TD.kesin_gecisler(yol) == {"ayin": (33, {"ritüel"})}   # kesin olmayan alinmaz
    assert TD.kesin_gecisler(tmp_path / "yok.yml") == {}


def test_uc_arac_ayni_okuyucuyu_kullanir(tmp_path):
    import lotm
    yol = tmp_path / "k.yml"
    yol.write_text("varyantlar:\n  - {dogru: ayin, yanlis: [ritüel], ogrenme_bolumu: 33, kesin_gecis: true}\n",
                   encoding="utf-8")
    assert lotm.kesin_gecisler(yol) == TD.kesin_gecisler(yol) == {"ayin": (33, {"ritüel"})}
