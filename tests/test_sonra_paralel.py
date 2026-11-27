# -*- coding: utf-8 -*-
"""sonra.py bolum ici paralellik (27 Kas): bagimsiz cagrilar ayni anda,
sadakat okumadan, birlestir hepsinden sonra; ciktilar sirali kosuyla ayni."""

import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sonra as S  # noqa: E402


class SahteBolum:
    """bolum_isle'nin kullandigi yuzey: her gecis tek girdi/cikti (sadakat 2 parti)."""

    def __init__(self, klasor: Path):
        self.no = 99
        self.klasor = klasor
        self.dosya = klasor / "0099.md"
        self.dosya.write_text("metin\n", encoding="utf-8")
        self.sadakat_okumalari = None

    def _cift(self, ad, govde="girdi"):
        g = self.klasor / f"{ad}_girdi.md"
        S.yaz_degisirse(g, govde + "\n")
        return [(g, self.klasor / f"{ad}_cikti.md")]

    def zincir_calistir(self, zorla):
        pass

    def zincir_ozeti(self):
        return []

    def okuma(self):
        return self._cift("1_okuma")

    def donem(self):
        return self._cift("1b_donem")

    def duzeltme(self):
        return self._cift("3_duzeltme")

    def triyaj(self):
        return self._cift("4_triyaj")

    def duzeltme_farki(self):
        c = self.klasor / "3_duzeltme_cikti.md"
        return "fark var" if c.exists() else None

    def sadakat(self, okumalar):
        # sadakat girdisi okuma ciktisini tasir: bu cagri aninda hazir olmali
        self.sadakat_okumalari = [p.read_text(encoding="utf-8") for p in okumalar]
        ciftler = []
        for i in (1, 2):
            g = self.klasor / f"2_sadakat_girdi_{i:02d}.md"
            S.yaz_degisirse(g, "|".join(self.sadakat_okumalari) + f" parti {i}\n")
            ciftler.append((g, self.klasor / f"2_sadakat_cikti_{i:02d}.md"))
        return ciftler, None

    def birlestir(self, sadakat, okuma):
        govde = "\n".join(sorted(p.name + ":" + p.read_text(encoding="utf-8").strip()
                                 for p in self.klasor.glob("*_cikti*.md")))
        return self._cift("5_birlestir", govde)

    def son_adim(self, kuru, kesin_yok, anlik=None):
        return "son adim tamam"


def kos(tmp_path, monkeypatch, ic_paralel, gecikme=0.05, hata=()):
    klasor = tmp_path / f"p{ic_paralel}"
    klasor.mkdir()
    b = SahteBolum(klasor)
    monkeypatch.setattr(S, "Bolum", lambda no, boy, ek=(): b)
    monkeypatch.setattr(S, "ikinci_motor", lambda *x, **k: "codex")
    monkeypatch.setattr(S, "motor_sec", lambda adim, sec=None: "claude")
    S.HIZ_GORULDU.clear()
    olaylar, kilit = [], threading.Lock()
    ayni_anda = {"simdi": 0, "en_cok": 0}

    def sahte_yurut(girdi, cikti, model, sure, araclar=None, motor="claude"):
        with kilit:
            ayni_anda["simdi"] += 1
            ayni_anda["en_cok"] = max(ayni_anda["en_cok"], ayni_anda["simdi"])
            olaylar.append(("bas", cikti.name, time.monotonic()))
        time.sleep(gecikme * (3 if "okuma" in cikti.name else 1))
        with kilit:
            ayni_anda["simdi"] -= 1
            olaylar.append(("son", cikti.name, time.monotonic()))
        if cikti.name in hata:
            return False
        cikti.write_text(f"{cikti.name} <- {girdi.read_text(encoding='utf-8').strip()}"
                         f" araclar={araclar}\n", encoding="utf-8")
        return True

    monkeypatch.setattr(S, "yurut", sahte_yurut)
    a = SimpleNamespace(parti_boyu=6000, yanki="", kararlar=False, bastan=False, kuru=False,
                        kesin_yok=False, zincir_yeniden=False, motor=[], model=None, sure=30,
                        ic_paralel=ic_paralel)
    otomatik = list(S.MODEL_ADIMLARI) + ["donem"]
    k, kisa = S.bolum_isle(99, a, otomatik, {}, cift=True, donem=True, cift_okuma=True)
    return k, kisa, klasor, olaylar, ayni_anda["en_cok"], b


def zaman(olaylar, tur, ad):
    return next(t for e, n, t in olaylar if e == tur and n == ad)


def icerik(klasor):
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(klasor.iterdir())
            if p.name != "DURUM.md" and p.name != "0099.md"}


def test_paralel_ciktilar_siraliyla_ayni_ve_bagimliliklar_korunur(tmp_path, monkeypatch):
    k1, kisa1, k1_klasor, _, en_cok1, _ = kos(tmp_path, monkeypatch, 1)
    k4, kisa4, k4_klasor, olay, en_cok4, b = kos(tmp_path, monkeypatch, 4)
    assert (k1, kisa1) == (k4, kisa4) == (0, "son adim tamam")
    assert icerik(k1_klasor) == icerik(k4_klasor)
    assert en_cok1 == 1 and 1 < en_cok4 <= 4
    # sadakat iki okuyucunun ciktisini da gordu
    assert len(b.sadakat_okumalari) == 2
    okuma_sonu = max(zaman(olay, "son", n) for n in ("1_okuma_cikti.md", "1_okuma_cikti.codex.md"))
    for n in ("2_sadakat_cikti_01.md", "2_sadakat_cikti_02.codex.md"):
        assert zaman(olay, "bas", n) >= okuma_sonu
    # duzeltme okumayi beklemez
    assert zaman(olay, "bas", "3_duzeltme_cikti.md") < okuma_sonu
    # birlestir en son
    assert zaman(olay, "bas", "5_birlestir_cikti.md") >= max(t for e, n, t in olay
                                                            if e == "son" and "birlestir" not in n)
    # triyaj araclari yalniz triyaja gider (gec baglanan lambda olmasin)
    assert "araclar=None" in (k4_klasor / "1_okuma_cikti.md").read_text(encoding="utf-8")
    assert "araclar=None" not in (k4_klasor / "4_triyaj_cikti.md").read_text(encoding="utf-8")
    durum = (k4_klasor / "DURUM.md").read_text(encoding="utf-8")
    sira = [durum.index(f"\nTAMAM     {ad}") for ad in
            ("okuma", "donem", "sadakat", "duzeltme", "triyaj", "birlestir")]
    assert sira == sorted(sira)  # rapor eski adim sirasinda
    assert "fark var" in durum


def test_basarisiz_okuma_sadakati_okumasiz_kurar_birlestir_beklemede(tmp_path, monkeypatch):
    k, kisa, klasor, _, _, b = kos(tmp_path, monkeypatch, 4, hata=("1_okuma_cikti.codex.md",))
    assert k == 1
    assert len(b.sadakat_okumalari) == 1
    assert not (klasor / "5_birlestir_cikti.md").exists()
    assert "onceki gecisler bitince" in (klasor / "DURUM.md").read_text(encoding="utf-8")


def test_hiz_siniri_gorulunce_kalan_cagrilar_sirayla():
    c = S.Cagrilar(3)
    S.HIZ_GORULDU.clear()
    kosan, en_cok, kilit = [0], [0], threading.Lock()

    def is_(ok=True):
        with kilit:
            kosan[0] += 1
            en_cok[0] = max(en_cok[0], kosan[0])
        time.sleep(0.02)
        with kilit:
            kosan[0] -= 1
        return ok

    try:
        S.HIZ_GORULDU.set()
        for i in range(4):
            c.ekle("sadakat", Path(f"c{i}"), is_)
        assert en_cok[0] == 1
        c.ekle("okuma", Path("kotu"), lambda: is_(False))
        assert c.bekle({"okuma"}) == {Path("kotu")}
        assert c.bekle() == {Path("kotu")}
    finally:
        c.kapat()
        S.HIZ_GORULDU.clear()


def test_ic_paralel_sayisi():
    assert S.ic_paralel_sayisi("oto") == S.IC_PARALEL_OTO
    assert S.ic_paralel_sayisi("oto", cocuk=True) == S.IC_PARALEL_COCUK
    assert S.ic_paralel_sayisi("1") == 1 and S.ic_paralel_sayisi(6) == 6
    for bozuk in ("0", "x", "-2"):
        with pytest.raises(ValueError):
            S.ic_paralel_sayisi(bozuk)


def test_yurut_hiz_sinirini_isaretler(tmp_path, monkeypatch):
    girdi = tmp_path / "g.md"
    girdi.write_text("x", encoding="utf-8")
    S.HIZ_GORULDU.clear()
    monkeypatch.setattr(S.motorlar, "calistir",
                        lambda *x, **k: S.motorlar.Sonuc(False, hata="429 Too Many Requests"))
    assert not S.yurut(girdi, tmp_path / "c.md", None, 30)
    assert S.HIZ_GORULDU.is_set()
    S.HIZ_GORULDU.clear()
    monkeypatch.setattr(S.motorlar, "calistir",
                        lambda *x, **k: S.motorlar.Sonuc(False, hata="usage limit", kota=True))
    assert not S.yurut(girdi, tmp_path / "c.md", None, 30)
    assert not S.HIZ_GORULDU.is_set()


def test_cift_varsayilan_yalniz_otomatikte():
    # (bayrak, tek, otomatik, ortam) -> acik mi
    assert S.cift_acik(False, False, ["okuma"], None) is True
    assert S.cift_acik(False, False, None, None) is False  # elle kip: ikinci cikti beklenmesin
    assert S.cift_acik(False, False, ["okuma"], False) is False  # LOTM_CIFT_*=0
    assert S.cift_acik(False, False, None, True) is True  # LOTM_CIFT_*=1
    assert S.cift_acik(True, False, None, False) is True
    assert S.cift_acik(True, True, ["okuma"], True) is False  # --tek-* her seyi ezer
