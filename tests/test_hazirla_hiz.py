# -*- coding: utf-8 -*-
"""
hazirla.py hiz iyilestirmeleri: her kestirme, eski (yavas) tanimla AYNI sonucu vermeli.
Yanlis negatif sessiz kacirma demektir; bu yuzden her sinama referans uygulamayla karsilastirilir.
"""

import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hazirla as H  # noqa: E402
import lotm  # noqa: E402


def _t(tr, en=None, zh=None, kategori="Temel Kavramlar", **kw):
    return lotm.Terim(tr=tr, en=en, zh=zh, kategori=kategori, **kw)


class _B:
    def __init__(self, no, metin):
        self.no, self.metin = no, metin


# ------------------------------------------------------------ Korpus sayimi


def _eski_kucuk_sozcukler(metinler):
    kucuk, orta = Counter(), Counter()
    for m in metinler:
        kucuk.update(w.rstrip("'-") for w in H._KUCUK_SOZCUK.findall(m))
        orta.update(H._IYELIK.sub("", w.rstrip("-")) for w in H.Korpus._ORTA.findall(m))
    return kucuk, orta


def test_orta_hizli_esdeger_rastgele():
    parcalar = ["a", "b", "Foo", "Bar", "Mr.", "Mrs.", "Dr.", "St.", "Prof.", "Capt.", "Lt.",
                "x,", "y;", ".", "'s", "-", "  ", " ", "\n", "Rev.", "Col.", "Gen.", "Mx.",
                "Ms.", "xMr.", "Foo-bar", "Q'", "é", "É"]
    rnd = random.Random(7)
    for _ in range(20000):
        m = "".join(rnd.choice(parcalar) + rnd.choice(["", " ", " ", "  "])
                    for _ in range(rnd.randint(1, 10)))
        assert H._orta_sozcukler(m) == H.Korpus._ORTA.findall(m), repr(m)


def test_orta_ust_uste_binen_on_ek_sayilmaz():
    # "a Foo Bar": Bar'in on-eki ("o") Foo eslesmesinin icinde kalir.
    assert H._orta_sozcukler("a Foo Bar") == H.Korpus._ORTA.findall("a Foo Bar") == ["Foo"]
    for m in ("Mr. Vannas came", "x Dr. Glacis, Bieber", "see Mrs. Glacis and St. John", "Mr.Vannas"):
        assert H._orta_sozcukler(m) == H.Korpus._ORTA.findall(m), m
    assert H._orta_sozcukler("Mr. Vannas came") == ["Vannas"]  # unvan noktasindan sonra


def test_kucuk_sozcukler_eskisiyle_ayni_sayimlar():
    metinler = ["He said that Angelica's coat, and Mr. Glacis' hat -- ok well-known x- y'",
                "the Old Neil spoke; then Fool-ish. don't Don't a-b-"]
    k = H.kucuk_sozcukler(iter(metinler))
    eski_k, eski_o = _eski_kucuk_sozcukler(metinler)
    assert dict(k.kucuk) == dict(eski_k) and dict(k.orta) == dict(eski_o)


# ------------------------------------------------------- en_isabetleri


def _eski_en_isabetleri(en, terimler):
    ham = {}
    for t in terimler:
        if not t.tr:
            continue
        bayrak = 0 if H.harf_duyarli_mi(t) else re.IGNORECASE
        araliklar = set()
        for aday in H.arama_adlari(t):
            if len(aday) < 4:
                continue
            d = re.compile(r"(?<![\w-])" + re.escape(aday) + r"(?:e?s)?(?![\w-])", bayrak)
            araliklar.update(m.span() for m in d.finditer(en))
        if araliklar:
            ham[id(t)] = araliklar
    hepsi = {a for s in ham.values() for a in s}
    out = {}
    for k, araliklar in ham.items():
        kalan = sorted((a, b) for a, b in araliklar
                       if not any(a2 <= a and b <= b2 and (b2 - a2) > (b - a) for a2, b2 in hepsi))
        if kalan:
            out[k] = kalan
    return out


def test_en_isabetleri_eskisiyle_ayni():
    terimler = [
        _t("Kehanet", "Divination"),
        _t("Kehanet Kulübü", "Divination Club"),
        _t("Kehanet Yöntemi", "Divination method"),
        _t("Ölüm", "Death", kategori="İlahlar ve Yüce Kadimler"),
        _t("Ölüm Meleği", "Death Angel", kategori="İlahlar ve Yüce Kadimler"),
        _t("Kelvin", "Kelvin degree"),
        _t("Sis", "Fog of History", kategori="İlahlar ve Yüce Kadimler"),
    ]
    metinler = [
        "Divination Club met. Divination method works; divination is fine. DIVINATIONS too. "
        "Death Angel saw death. Death, Death Angels. kelvin degree and KELVIN DEGREE. "
        "Fog of History.",
        # IGNORECASE'in ASCII harfe esledigi ASCII-disi karakterler: sinama kapanmali.
        "Divinatıon DIVİNATION Kelvin degree Divſnation Kelvin degree Death Angel",
        "Hic gecmiyor.",
    ]
    for en in metinler:
        assert H.en_isabetleri(en, terimler) == _eski_en_isabetleri(en, terimler), en


def test_en_isabetleri_ayni_metinde_onbellek_ikinci_cagri_ayni():
    terimler = [_t("Kehanet", "Divination"), _t("Kehanet Kulübü", "Divination Club")]
    en = "Divination Club and divination."
    ilk = H.en_isabetleri(en, terimler)
    assert H.en_isabetleri(en, terimler) == ilk == _eski_en_isabetleri(en, terimler)
    # baska metin: onbellek eskiyi tasimamali
    assert H.en_isabetleri("Nothing here.", terimler) == {}


# --------------------------------------------- yayim onbellegi


def _eski_yayim(terim, bolumler, haric, kardesler):
    duyarli = H.harf_duyarli_mi(terim)
    desenler = [lotm.desen_kur(b, harf_duyarli=duyarli) for b in H.yayim_bicimleri(terim, kardesler)]
    return sorted(b.no for b in bolumler
                  if b.no is not None and b.no != haric and any(d.search(b.metin) for d in desenler))


# Cekim, iyelik, yumusama, unlu dusmesi, mastar/fiil, olcu: her satir (terim, eslesen metin).
_ORNEKLER = [
    ("kaşlarının arası", "Kaşlarımın arasında bir ağrı vardı."),
    ("gaz lambası", "Eski gaz lambaları yanıyordu, gaz lambasını söndürdü."),
    ("cep saati", "Cep saatleri ve cep saatim."),
    ("Rüzgâr Şehri", "Rüzgâr Şehirleri ve Rüzgâr Şehri'nde."),
    ("mühür", "mührü açtı, mühre baktı."),
    ("kayıt", "kaydı aldı, kayıtlar."),
    ("tevdi etmek", "tevdi ettiğini, tevdi edildi."),
    ("işaret et-", "işaret etti, işaret edilen."),
    ("dürt-", "dürtüp geçti."),
    ("Kâhin", "Bir Kâhin'in elleri."),
    ("simge", "simgeleyen ve simgesel bir şey."),
    ("İmparator", "İmparatorun tahtı."),
    ("Awwa Kontluğu Polis Müdüriyeti", "Awwa Kontluğu Polis Müdüriyeti binası"),
    ("Kontluk Polis Müdüriyeti", "Awwa Kontluğu Polis Müdüriyeti binası"),
    ("altı librelik top", "altı librelik top"),
    ("libre", "altı librelik top"),
    ("beden", "bedenler ve bedeni."),
    ("ağız", "ağzı açık, ağızlar."),
    ("kutu", "kutular, kutuyu aldı."),
]


def test_yayim_kullanimi_eskisiyle_ayni_ve_onbellek_gecersizlenir():
    terimler = [_t(t) for t, _m in _ORNEKLER]
    kardesler = H.harf_kardesleri(terimler)
    bol = [_B(40 + i, m) for i, (_t_, m) in enumerate(_ORNEKLER)] + [_B(None, "libre"), _B(90, "")]
    for _ in range(2):  # ikinci tur onbellekten
        es = [H.Eslesme(t, "zh", 1, 0) for t in terimler]
        H.yayim_kullanimi(es, bol, 41, kardesler)
        for e in es:
            assert e.yayim == _eski_yayim(e.terim, bol, 41, kardesler), e.terim.tr
    # ayni liste, baska haric: onbellek haric'i tekrar uygular
    es = [H.Eslesme(t, "zh", 1, 0) for t in terimler]
    H.yayim_kullanimi(es, bol, 44, kardesler)
    for e in es:
        assert e.yayim == _eski_yayim(e.terim, bol, 44, kardesler)
    # korpus degisti (ayni liste nesnesi, yeni metin): eski sonuc tasinmamali
    bol[0] = _B(40, "tamamen baska")
    es = [H.Eslesme(t, "zh", 1, 0) for t in terimler]
    H.yayim_kullanimi(es, bol, 55, kardesler)
    for e in es:
        assert e.yayim == _eski_yayim(e.terim, bol, 55, kardesler)


def test_bilesik_deseni_onbellegi_liste_degisince_yenilenir():
    zh = "星灵体和灵体"
    a = H._bilesik_deseni("灵体", ["星灵体", "灵体"])
    assert [m.start() for m in a.finditer(zh)] == [4]
    b = H._bilesik_deseni("灵体", ["灵体"])  # baska liste: bilesik yok
    assert [m.start() for m in b.finditer(zh)] == [1, 4]
    ayni = ["星灵体", "灵体"]
    assert H._bilesik_deseni("灵体", ayni) is H._bilesik_deseni("灵体", ayni)
