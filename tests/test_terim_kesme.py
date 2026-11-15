# -*- coding: utf-8 -*-
"""Terim kesmesi (çekirdek v5.5 'Dünya terimlerine gelen ek')."""
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
for yol in (KOK, KOK / "lint"):
    sys.path.insert(0, str(yol))

import sozluk_lint as L  # noqa: E402

K = {"terim_kesme": {"duzelt": True,
                     "kokler": ["Ruhaniyet", "Mertebe", "Aşkın", "Ayin", "Kâhin", "Uykusuz", "Firaset"]}}


def _uygula(metin, kurallar=K):
    out = metin
    for a, b, yeni, _ in sorted(L.metin_onergeleri(metin, kurallar), reverse=True):
        out = out[:a] + yeni + out[b:]
    return out


def test_eksik_kesme_eklenir():
    assert _uygula("ve Ruhaniyetini topladı.") == "ve Ruhaniyet'ini topladı."
    assert _uygula("bulunduğun Mertebenin iksiri") == "bulunduğun Mertebe'nin iksiri"
    assert _uygula("aynı Mertebedeki iksirler") == "aynı Mertebe'deki iksirler"
    assert _uygula("standart bir Aşkınsın.") == "standart bir Aşkın'sın."
    assert _uygula("yeni Aşkınımız, Kâhinimiz.") == "yeni Aşkın'ımız, Kâhin'imiz."
    assert _uygula("eskiden bir Uykusuzdu.") == "eskiden bir Uykusuz'du."


def test_cogul_kesmesi_silinir_cogul_dokunulmaz():
    assert _uygula("o Ayin'lerde ve Ayin'lerin") == "o Ayinlerde ve Ayinlerin"
    assert _uygula("Aşkınlar ve Aşkınların") == "Aşkınlar ve Aşkınların"


def test_dokunulmayanlar():
    for s in ("bu Yol'un ve Mertebe'nin",      # zaten doğru
              "Kâhinlik ona göre değildi",     # cümle başı
              "o bir Kâhinlikti.",             # yapım eki
              "eski Ayin Kehaneti yapıldı",    # bileşik adın içi
              "Ayini bitirdi.",                # cümle başı
              "dedi. \"Ruhaniyetini topla\""):  # tırnaklı cümle başı
        assert _uygula(s) == s, s


def test_duzelt_kapali_ise_onerge_yok_ama_rapor_var():
    k = {"terim_kesme": {"kokler": ["Ruhaniyet"]}}
    assert L.metin_onergeleri("ve Ruhaniyetini topladı.", k) == []
    r = L.Rapor()
    L.denetle_terim_kesme(r, {"0007.md": "ve Ruhaniyetini topladı."}, k)
    assert [(b.kural, b.bulunan) for b in r.bulgular] == [("terim-kesme", "Ruhaniyetini")]
    assert "Ruhaniyet'ini" in r.bulgular[0].mesaj


def test_varyant_ile_cakisma_tek_degisiklik():
    k = dict(K, varyantlar=[{"kavram": "Firaset + ek", "dogru": "Firaset'i",
                             "yanlis": ["Firaseti"], "duzelt": {"Firaseti": "Firaset'i"}}])
    yeni, oner = L.duzeltme_plani("herkesin Firaseti açıktı.", k)
    assert yeni == "herkesin Firaset'i açıktı." and len(oner) == 1


def test_istisna_ifadesi_korunur():
    k = {"terim_kesme": {"duzelt": True, "kokler": ["Ayin"], "istisna": ["sihir Ayini"]}}
    assert _uygula("bir sürü ilginç sihir Ayini de bilir.", k) == "bir sürü ilginç sihir Ayini de bilir."
    assert _uygula("yalnızca Ayini karıştırıp", k) == "yalnızca Ayin'i karıştırıp"
