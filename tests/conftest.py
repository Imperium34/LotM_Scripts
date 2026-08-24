# -*- coding: utf-8 -*-
"""
Test ortami ve sentetik veri ureticileri.

Betik klasorunun ADI teste gomulu degil: lotm.py hangisinde bulunursa o
sys.path'e eklenir. Boylece Tools -> scripts yeniden adlandirmasi testleri
bozmaz (zaten bozmamasi gerekiyordu; bu onu dogrular).
"""

import sys
from pathlib import Path

import pytest

def _betikleri_bul():
    """
    lotm.py'yi ADINA gore degil, VARLIGINA gore bulur.

    Ilk surum ("scripts", "Tools", ...) diye bir liste deniyordu -- yani
    klasor adini teste gomuyordu, tam da kacinilmasi gereken sey. Gercek
    kurulumda klasorun adi 'Scripts'ti (buyuk S) ve liste tutmadi.

    Sira:
      1. LOTM_BETIKLER ortam degiskeni (kesin cozum, her zaman kazanir)
      2. conftest.py'nin kendi klasoru (tests/ ile betikler ayni yerdeyse)
      3. yukari dogru uc seviye: her seviyede alt klasorlere bak
    """
    import os

    zorla = os.environ.get("LOTM_BETIKLER")
    if zorla:
        yol = Path(zorla).expanduser().resolve()
        if not (yol / "lotm.py").exists():
            raise RuntimeError(f"LOTM_BETIKLER'de lotm.py yok: {yol}")
        return yol

    burada = Path(__file__).resolve().parent
    if (burada / "lotm.py").exists():
        return burada

    bakilan = []
    kok = burada
    for _ in range(3):
        kok = kok.parent
        if (kok / "lotm.py").exists():
            return kok
        bakilan.append(str(kok))
        try:
            altlar = sorted(x for x in kok.iterdir() if x.is_dir())
        except OSError:
            continue
        for alt in altlar:
            if alt.name.startswith((".", "__")):
                continue
            if (alt / "lotm.py").exists():
                return alt

    raise RuntimeError(
        "lotm.py bulunamadi.\n"
        f"  conftest.py: {Path(__file__).resolve()}\n"
        f"  bakilan kokler: {', '.join(bakilan)}\n"
        "  Cozum: LOTM_BETIKLER=/betiklerin/yolu python3 -m pytest"
    )


BETIKLER = _betikleri_bul()
DEPO = BETIKLER.parent
sys.path.insert(0, str(BETIKLER))


# --------------------------------------------------------- Cince sayilar

_R = "零一二三四五六七八九"


def cn_yaz(n: int) -> str:
    """Tamsayi -> Cince rakam. Cilt ici numaralar 269'u gecmez."""
    if n < 10:
        return _R[n]
    if n < 20:
        return "十" + (_R[n - 10] if n > 10 else "")
    if n < 100:
        onlar, birler = divmod(n, 10)
        return _R[onlar] + "十" + (_R[birler] if birler else "")
    yuzler, kalan = divmod(n, 100)
    s = _R[yuzler] + "百"
    if kalan == 0:
        return s
    if kalan < 10:
        return s + "零" + _R[kalan]
    onlar, birler = divmod(kalan, 10)
    return s + _R[onlar] + "十" + (_R[birler] if birler else "")


# --------------------------------------------------------- korpus uretimi


def zh_korpus(uzunluklar, yazim_hatalari=None) -> str:
    """
    Sentetik Cince ham metin.

    uzunluklar: her cildin bolum sayisi.
    yazim_hatalari: {(cilt_ix, yerel_no): basilacak_yanlis_no}

    Numaralandirma HER CILTTE 1'den baslar -- Qidian standardi, gercek
    dosyadaki davranis.
    """
    yazim_hatalari = yazim_hatalari or {}
    satirlar = []
    for cilt_ix, adet in enumerate(uzunluklar):
        for yerel in range(1, adet + 1):
            yazilan = yazim_hatalari.get((cilt_ix, yerel), yerel)
            satirlar.append(f"第{cn_yaz(yazilan)}章 试验")
            satirlar.append(f"这是第{cilt_ix + 1}卷第{yerel}章的正文。")
            satirlar.append("")
    return "\n".join(satirlar)


def en_korpus(bolumler) -> str:
    """bolumler: [(no, baslik, [paragraf, ...])]"""
    parcalar = []
    for no, baslik, paragraflar in bolumler:
        parcalar.append(f"Chapter {no}: {baslik}")
        parcalar.append("")
        for p in paragraflar:
            parcalar.append(p)
            parcalar.append("")
    return "\n".join(parcalar)


# --------------------------------------------------------------- fixtures


@pytest.fixture
def depo(tmp_path):
    """Bos ama dogru sekilli bir proje kokü."""
    (tmp_path / "Imperium34.github.io" / "_data").mkdir(parents=True)
    (tmp_path / "Imperium34.github.io" / "_chapters").mkdir(parents=True)
    (tmp_path / "Source" / "LotM_Volumes").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def lotm_modulu(depo, monkeypatch):
    """LOTM_KOK'u tmp depoya cevrilmis lotm modulu."""
    import lotm
    monkeypatch.setattr(lotm, "KOK", depo)
    monkeypatch.setattr(lotm, "SITE", depo / "Imperium34.github.io")
    monkeypatch.setattr(lotm, "SOZLUK_YOLU",
                        depo / "Imperium34.github.io/_data/sozluk.yml")
    monkeypatch.setattr(lotm, "BOLUMLER_TR",
                        depo / "Imperium34.github.io/_chapters")
    monkeypatch.setattr(lotm, "KAYNAK_EN", depo / "Source/LotM_Volumes")
    monkeypatch.setattr(lotm, "KAYNAK_ZH",
                        depo / "Source/Lord_of_the_Mysteries_Chinese.txt")
    return lotm


SOZLUK_ORNEK = """\
# --- Yollar ---

- terim: Görücü
  ingilizce: Seer
  kategori: Yollar
  mertebeler:
    - seviye: 9
      isim: Çırak (Seer)
      bolum_siniri: 3
      cince: 占卜家
    - seviye: 8
      isim: Kâhin (Clown)
      bolum_siniri: 12
      eski_karsiliklar:
        - Falcı
    - seviye: 7
      isim: Gizem Avcısı (Mystery Pryer / Pugilist)
      bolum_siniri: 40
      arama_adi: ["Mystery Pryer"]

- terim: Avcı
  ingilizce: Hunter
  kategori: Yollar
  mertebeler:
    - seviye: 9
      isim: Avcı (Hunter)
      bolum_siniri: 20
    - seviye: 8
      isim: Değişken (Provoker)
      bolum_siniri: 90

# --- Kavramlar ---

- terim: Sıradışı
  ingilizce: Beyonder
  kategori: Kavramlar
  bolum_siniri: 3
  eski_karsiliklar:
    - Olağanüstü
  cince: 非凡者

- terim: Kutsayan Amon
  ingilizce: Blasphemer Amon (King of Angels)
  kategori: İlahlar ve Yüce Kadimler
  bolum_siniri: 500
"""


@pytest.fixture
def sozluk_dosyasi(depo):
    yol = depo / "Imperium34.github.io/_data/sozluk.yml"
    yol.write_text(SOZLUK_ORNEK, encoding="utf-8")
    return yol
