#!/usr/bin/env python3
"""
takvim_denetle.py -- bolum basliklari ve yayin tarihleri.

Iki hata elle yakalanmadan yayina cikmisti: iki bolume ayni ad verilmisti,
bir bolumun tarihi takvime uymuyordu (ikincisi ancak yayindan sonra fark
edildi). Bu betik ikisini de on madde basliginda (front matter) denetler.

TAKVIM
------
Her carsamba ve cumartesi bir bolum. Bolum N'nin tarihi, bolum N-1'den
sonraki ILK carsamba/cumartesi olmalidir (carsamba -> cumartesi 3 gun,
cumartesi -> carsamba 4 gun), saat de ayni.

  hata    : baslik bicimi / numara uyusmuyor, ayni ad iki bolumde,
            tarih yok ya da okunamiyor, carsamba/cumartesi degil,
            tarih bir oncekinden sonra degil (ayni gun ya da geri)
  uyari   : bir ya da daha cok slot atlanmis (ara verilmis olabilir),
            saat/saat dilimi alisilmis olandan farkli

GECMIS
------
Yayinlanmis bir bolumun tarihini sonradan degistirmek, ne zaman ciktigini
yanlis gosterir. Bilinen gecmis bu yuzden duzeltilmez, KABUL EDILIR:

  --baslangic N   takvim kurallari (gun, slot, saat, saat dilimi) N'den
                  itibaren; oncekiler yalnizca baslik ve sira denetimine girer
  --istisna 20,…  N'den sonra bilinen, kabul edilmis sapmalar (20: sali
                  cikti). Sonraki bolum yine ona gore denetlenir.

Kullanim:
    python3 takvim_denetle.py                  butun bolumler
    python3 takvim_denetle.py --bolum 47       yalnizca 47'yi ilgilendirenler
                                               + 47 icin beklenen tarih
    python3 takvim_denetle.py --baslangic 12   slot kurali 12'den itibaren

Cikis kodu: hata varsa 1.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import lotm
from turkce import tr_kucult

GUNLER = {2: "çarşamba", 5: "cumartesi"}          # datetime.weekday()
GUN_ADI = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]
_DOSYA = re.compile(r"^(\d+)\.md$")
_BASLIK = re.compile(r"^Bölüm\s+(\d+)\s*:\s*(.*\S)\s*$")
_SAPKA = str.maketrans("âîûÂÎÛ", "aiuAIU")


@dataclass
class Kunye:
    no: int
    dosya: str
    baslik: str | None
    tarih_ham: str | None
    tarih: datetime | None = None


def on_madde(metin: str) -> dict:
    """'---' arasindaki 'anahtar: deger' satirlari (tirnaklar atilir)."""
    satirlar = metin.split("\n")
    if not satirlar or satirlar[0].strip() != "---":
        return {}
    out = {}
    for s in satirlar[1:]:
        if s.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", s)
        if m:
            deger = m.group(2).strip()
            if len(deger) >= 2 and deger[0] == deger[-1] and deger[0] in "\"'":
                deger = deger[1:-1]
            out[m.group(1)] = deger
    return out


def tarih_oku(ham: str | None) -> datetime | None:
    if not ham:
        return None
    for bicim in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M %z",
                  "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(ham.strip(), bicim)
        except ValueError:
            continue
    return None


def kunyeler(klasor) -> list:
    out = []
    for p in sorted(Path(klasor).iterdir()):
        m = _DOSYA.match(p.name)
        if not m:
            continue
        om = on_madde(p.read_text(encoding="utf-8"))
        k = Kunye(int(m.group(1)), p.name, om.get("title"), om.get("date"))
        k.tarih = tarih_oku(k.tarih_ham)
        out.append(k)
    return sorted(out, key=lambda k: k.no)


def sonraki_slot(d: datetime) -> datetime:
    """d'den SONRAKI ilk carsamba ya da cumartesi, ayni saatte."""
    x = d + timedelta(days=1)
    while x.weekday() not in GUNLER:
        x += timedelta(days=1)
    return x


def ad_anahtari(ad: str) -> str:
    """Karsilastirma icin: harf buyuklugu, sapka ve noktalama farki yok."""
    return re.sub(r"[^\w]+", " ", tr_kucult(ad).translate(_SAPKA)).strip()


def _dilim_esitle(ks: list) -> list:
    """
    Saat dilimi yazilmamis tarihlere (2026-09-26 20:00:00) digerlerinin en
    sik dilimini verir; yoksa naive ile aware karsilastirilamaz ve betik
    duser. Doner: dilimi eklenen bolum numaralari (uyari icin).
    """
    dilimler = Counter(k.tarih.tzinfo for k in ks if k.tarih and k.tarih.tzinfo)
    if not dilimler:
        return []
    olagan = dilimler.most_common(1)[0][0]
    eklenen = []
    for k in ks:
        if k.tarih and k.tarih.tzinfo is None:
            k.tarih = k.tarih.replace(tzinfo=olagan)
            eklenen.append(k.no)
    return eklenen


def denetle(ks: list, baslangic: int = 1, istisna=()):
    """Doner: [(agirlik, bolum_no, mesaj)] -- agirlik 'hata' | 'uyari'."""
    bulgu = []
    istisna = set(istisna)

    def takvimde(k):
        return k.no >= baslangic and k.no not in istisna

    for no in [n for n in _dilim_esitle(ks) if takvimde(next(x for x in ks if x.no == n))]:
        k = next(x for x in ks if x.no == no)
        bulgu.append(("uyari", no, f"tarihte saat dilimi yok ({k.tarih_ham!r}); "
                                   f"{k.tarih:%z} varsayıldı -- ekleyin"))

    # --- basliklar
    adlar = defaultdict(list)
    for k in ks:
        if not k.baslik:
            bulgu.append(("hata", k.no, "başlık yok"))
            continue
        m = _BASLIK.match(k.baslik)
        if not m:
            bulgu.append(("hata", k.no, f"başlık biçimi 'Bölüm N: Ad' değil: {k.baslik!r}"))
            continue
        if int(m.group(1)) != k.no:
            bulgu.append(("hata", k.no, f"başlıktaki numara {m.group(1)}, dosya {k.no}"))
        adlar[ad_anahtari(m.group(2))].append((k.no, m.group(2)))
    for grup in adlar.values():
        if len(grup) > 1:
            nolar = ", ".join(str(n) for n, _ in grup)
            for n, ad in grup:
                bulgu.append(("hata", n, f"aynı ad birden çok bölümde ({nolar}): {ad!r}"))

    # --- tarihler
    tarihli = [k for k in ks if k.tarih]
    for k in ks:
        if not k.tarih_ham:
            bulgu.append(("hata", k.no, "tarih yok"))
        elif not k.tarih:
            bulgu.append(("hata", k.no, f"tarih okunamadı: {k.tarih_ham!r}"))
        elif takvimde(k) and k.tarih.weekday() not in GUNLER:
            bulgu.append(("hata", k.no, f"{k.tarih:%Y-%m-%d} bir {GUN_ADI[k.tarih.weekday()]}; "
                                        f"çarşamba ya da cumartesi olmalı"))

    saat = Counter(k.tarih.strftime("%H:%M:%S %z") for k in tarihli)
    if saat:
        olagan = saat.most_common(1)[0][0]
        for k in tarihli:
            if takvimde(k) and k.tarih.strftime("%H:%M:%S %z") != olagan:
                bulgu.append(("uyari", k.no, f"saat {k.tarih:%H:%M:%S %z}, alışılmış olan {olagan}"))

    for onceki, k in zip(tarihli, tarihli[1:]):
        if k.tarih <= onceki.tarih:
            bulgu.append(("hata", k.no, f"tarih ({k.tarih:%Y-%m-%d}) bölüm {onceki.no}'dan "
                                        f"({onceki.tarih:%Y-%m-%d}) sonra değil"))
            continue
        if not takvimde(k) or k.no != onceki.no + 1:
            continue
        beklenen = sonraki_slot(onceki.tarih)
        if k.tarih.date() < beklenen.date():
            bulgu.append(("hata", k.no, f"tarih {k.tarih:%Y-%m-%d}; bölüm {onceki.no}'dan sonraki "
                                        f"ilk slot {beklenen:%Y-%m-%d} ({GUN_ADI[beklenen.weekday()]})"))
        elif k.tarih.date() > beklenen.date():
            atlanan, x = 0, beklenen
            while x.date() < k.tarih.date():
                atlanan += 1
                x = sonraki_slot(x)
            bulgu.append(("uyari", k.no, f"{atlanan} slot atlanmış: beklenen {beklenen:%Y-%m-%d}, "
                                         f"yazılan {k.tarih:%Y-%m-%d} (ara mı verildi?)"))
    return bulgu


def beklenen_tarih(ks: list, no: int) -> datetime | None:
    """Bolum no icin: bir onceki bolumden sonraki ilk slot."""
    onceki = [k for k in ks if k.no < no and k.tarih]
    return sonraki_slot(onceki[-1].tarih) if onceki else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--klasor", default=None, help="varsayilan: lotm.BOLUMLER_TR")
    ap.add_argument("--bolum", type=int, default=None, help="yalnizca bu bolumu ilgilendirenler")
    ap.add_argument("--baslangic", type=int, default=1,
                    help="takvim kurallari bu bolumden itibaren (oncesi: yalniz baslik/sira)")
    ap.add_argument("--istisna", default="",
                    help="kabul edilmis sapmalar, virgulle: '20' ya da '20,31'")
    a = ap.parse_args()

    ks = kunyeler(a.klasor or lotm.BOLUMLER_TR)
    if not ks:
        print("bölüm dosyası bulunamadı", file=sys.stderr)
        return 1
    istisna = {int(x) for x in a.istisna.replace(" ", "").split(",") if x}
    bulgu = denetle(ks, a.baslangic, istisna)

    if a.bolum is not None:
        # N'yi ilgilendiren: kendi bulgulari + N+1'in N'ye gore tarih bulgusu
        bulgu = [b for b in bulgu if b[1] == a.bolum
                 or (b[1] == a.bolum + 1 and "bölüm " + str(a.bolum) in b[2])]
        bek = beklenen_tarih(ks, a.bolum)
        bu = next((k for k in ks if k.no == a.bolum), None)
        if bek:
            durum = ""
            if bu and bu.tarih:
                durum = "  ✓" if bu.tarih.date() == bek.date() else f"  (yazılan: {bu.tarih:%Y-%m-%d})"
            print(f"  bölüm {a.bolum} için beklenen tarih: "
                  f"{bek:%Y-%m-%d %H:%M:%S %z} ({GUN_ADI[bek.weekday()]}){durum}")

    hata = [b for b in bulgu if b[0] == "hata"]
    uyari = [b for b in bulgu if b[0] == "uyari"]
    for agirlik, no, mesaj in sorted(bulgu, key=lambda b: (b[1], b[0])):
        print(f"  {'!!' if agirlik == 'hata' else ' *'} {no:04d}.md  {mesaj}")
    kapsam = f"bölüm {a.bolum}" if a.bolum is not None else f"{len(ks)} bölüm"
    print(f"  başlık/tarih: {len(hata)} hata, {len(uyari)} uyarı ({kapsam})")
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
