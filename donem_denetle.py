#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
donem_denetle.py -- Viktorya/gotik dokuya oturmayan cagdas sozcuklerin
ADAY listesi. Karar vermez: sonra.py --donem bu listeyi donem gecisine
(Tools/Prompts/lotm_donem_denetimi.md) verir, model ayiklar.

Sozcukler lint/lint-kurallari.yml > donem_uyumu'ndadir:
    alinti  D.1  cagdas alinti / yenilik (detay, enerji, profesyonel...)
    agiz    D.2  gundelik-argo agiz, cagdas kalip (falan, olay yeri...)
    ozdes   D.3  donem karsiligi varken cagdas varsayilan (cekirdek §4.1-A):
                 durum/vaziyet gibi; tek tek degil, bolum sayimi

Atlananlar:
    - Klein'in ic sesi (_italik_): Dunya'dan gelen biri, cagdas sozcuk serbest.
      (Dunya anilari italik degilse betik ayiramaz; model ayirir.)
    - words.md §XII Frozen Lines (rubai dahil): dondurulmus satir.
    - Front matter (baslik sablonun karari).
Dipnot yok: yazarin 注 notlari cevrilmez, Turkcede ayiklanacak bir sey yok.

Paragraf numarasi okuma gecisinin ¶'sidir (front matter haric, bos satirla
ayrilan blok), birlestirme ayni numarayi kullanir.

Kullanim:
    python3 donem_denetle.py 72            adaylar + yogunluk
    python3 donem_denetle.py 62-72 --ozet  bolum basina tek satir
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIKLER))
sys.path.insert(0, str(BETIKLER / "lint"))
KOK = Path(os.environ.get("LOTM_KOK") or BETIKLER.parent)
BOLUMLER = KOK / "Imperium34.github.io" / "_chapters"
KURALLAR = BETIKLER / "lint" / "lint-kurallari.yml"
KELIMELER = Path(os.environ.get("LOTM_KELIMELER") or KOK / "Tools" / "words.md")

import lotm  # noqa: E402
from turkce import tr_desen  # noqa: E402

AILE = {"alinti": "D.1", "agiz": "D.2", "ozdes": "D.3"}
IC_SES = re.compile(r"_[^_\n]{3,}_")  # sozluk_lint.IC_SES ile ayni
HARF = "A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîûÊê"
# 5 harften kisa kokler yalniz sesliyle ya da unsuz+sesliyle devam ederse
# sayilir (sozluk_lint._KISA_EK gibi): "baya" bayat'i saymaz.
KISA_EK = r"(?:[aeıioöuüâîû][%s]*|[ysnldtmc][aeıioöuüâîû][%s]*)?" % (HARF, HARF)


def kurallar(yol: Path = KURALLAR) -> dict:
    import yaml
    d = (yaml.safe_load(yol.read_text(encoding="utf-8")) or {}).get("donem_uyumu") or {}
    liste = lambda v: v.split() if isinstance(v, str) else list(v or [])  # noqa: E731
    return {"alinti": liste(d.get("alinti")), "agiz": liste(d.get("agiz")),
            "istisna": liste(d.get("istisna")), "ozdes": dict(d.get("ozdes") or {}),
            "ozdes_istisna": liste(d.get("ozdes_istisna"))}


def desen(kokler: list, istisna: list = ()) -> re.Pattern | None:
    """Kok + ek, Turkce harf duyarsiz (tr_desen), sapka duyarli. Cok sozcuklu
    girisler ('olay yeri') son sozcuge ek alabilir."""
    if not kokler:
        return None
    parcalar = []
    for k in sorted(kokler, key=len, reverse=True):
        ek = KISA_EK if len(k) < 5 else f"[{HARF}]*"
        parcalar.append(tr_desen(k) + ek)
    on = ""
    if istisna:
        on = "(?!(?:" + "|".join(tr_desen(x) for x in istisna) + "))"
    return re.compile(rf"(?<![{HARF}]){on}(?:" + "|".join(parcalar) + rf")(?![{HARF}])")


def bloklar(metin: str) -> list:
    """sonra.tr_bloklari ile ayni ¶ duzeni."""
    if metin.startswith("---"):
        son = metin.find("\n---", 3)
        if son != -1:
            metin = metin[son + 4:]
    return [b.strip() for b in re.split(r"\n\s*\n", metin) if b.strip()]


def donmus_satirlar(yol: Path = KELIMELER) -> list:
    """words.md §XII'deki kalin satirlar; ' / ' ile bolunmus dizeler ayri."""
    if not yol.exists():
        return []
    t = yol.read_text(encoding="utf-8")
    m = re.search(r"^# XII\..*?$(.*?)(?=^# [IVXL]+\.|\Z)", t, re.M | re.S)
    if not m:
        return []
    out = []
    # Kalin anahtar + aciklamadaki tirnakli dizeler (rubai: anahtar son dize,
    # dort dizenin tamami tirnakta).
    parcalar = re.findall(r"^- \*\*(.+?)\*\*", m.group(1), re.M)
    parcalar += re.findall(r"\"([^\"\n]{8,}?)\"", m.group(1))
    for kalin in parcalar:
        for parca in re.split(r"\s*/\s*", kalin):
            parca = parca.strip(" .…;!?\"'")
            if len(parca) >= 8:
                out.append(parca)
    return out


def cumle(blok: str, bas: int, son: int) -> str:
    """Eslesmenin cumlesi (nokta/soru/unlem/uc nokta sinirinda), tek satir."""
    a = max(blok.rfind(c, 0, bas) for c in ".!?…\n")
    b = [i for i in (blok.find(c, son) for c in ".!?…\n") if i != -1]
    return re.sub(r"\s+", " ", blok[a + 1:(min(b) + 1) if b else None]).strip()


def tara(metin: str, kural: dict | None = None, donmus: list | None = None) -> list:
    """[{"p", "aile", "sozcuk", "cumle"}] -- D.1 ve D.2 adaylari."""
    kural = kural or kurallar()
    donmus = donmus_satirlar() if donmus is None else donmus
    desenler = {ad: desen(kural[ad], kural["istisna"]) for ad in ("alinti", "agiz")}
    out = []
    for p, blok in enumerate(bloklar(metin), 1):
        ic = [m.span() for m in IC_SES.finditer(blok)]
        for ad, d in desenler.items():
            if d is None:
                continue
            for m in d.finditer(blok):
                if any(a <= m.start() < b for a, b in ic):
                    continue
                c = cumle(blok, m.start(), m.end())
                if any(f in blok and blok.find(f) <= m.start() < blok.find(f) + len(f) for f in donmus):
                    continue
                out.append({"p": p, "aile": AILE[ad], "sozcuk": m.group(), "cumle": c})
    return out


def ozdes_sayim(metin: str, kural: dict | None = None) -> list:
    """[(cagdas, sayi, donem, sayi)]: anlatida (ic ses haric) iki bicimin sayisi."""
    kural = kural or kurallar()
    duz = IC_SES.sub(" ", "\n\n".join(bloklar(metin)))
    out = []
    for cagdas, donem in kural["ozdes"].items():
        a = desen([cagdas], kural["ozdes_istisna"])
        b = desen([donem])
        out.append((cagdas, len(a.findall(duz)), donem, len(b.findall(duz))))
    return out


def yogunluk(metin: str) -> dict:
    """lint register sayaci: {"donem": x, "gotik": y} / 1000 sozcuk."""
    try:
        import yaml
        import sozluk_lint as L
        kur = yaml.safe_load(KURALLAR.read_text(encoding="utf-8")) or {}
        rapor = type("R", (), {"olcumler": {}, "ekle": lambda *a, **k: None})()
        L.denetle_register(rapor, {"b": metin}, kur)
        ayr = rapor.olcumler.get("register_ayrinti", {}).get("b", {})
        return {t: v[0] for t, v in ayr.items()} | {
            "hedef_alt": (kur.get("register") or {}).get("hedef_alt", 3.0)}
    except Exception:  # yardimci olcum; yoksa blok onsuz kurulur
        return {}


def bolum_metni(no: int) -> str:
    return (BOLUMLER / f"{no:04d}.md").read_text(encoding="utf-8")


def blok(no: int, metin: str | None = None) -> str:
    """Donem gecisine <betik_adaylari> blogu."""
    metin = bolum_metni(no) if metin is None else metin
    kural = kurallar()
    adaylar = tara(metin, kural)
    y = yogunluk(metin)
    satirlar = []
    if y:
        satirlar.append(f"Yoğunluk (lint register sayacı, /1000 sözcük): dönem {y.get('donem', 0)}, "
                        f"gotik {y.get('gotik', 0)}; dönem tabanı için alt sınır {y.get('hedef_alt')}.")
    oz = ozdes_sayim(metin, kural)
    if oz:
        satirlar.append("Çağdaş varsayılan / dönem karşılığı (anlatı + diyalog, iç ses hariç): "
                        + ", ".join(f"{a} {n} / {b} {m}" for a, n, b, m in oz) + ".")
    satirlar.append("")
    if adaylar:
        satirlar.append(f"Adaylar ({len(adaylar)}; iç ses ve §XII dondurulmuş satırlar atlandı):")
        satirlar += [f"- ¶{x['p']} {x['aile']} \"{x['sozcuk']}\": {x['cumle']}" for x in adaylar]
    else:
        satirlar.append("Adaylar: betik listesinden aday yok.")
    return "<betik_adaylari>\n" + "\n".join(satirlar) + "\n</betik_adaylari>"


bolum_listesi = lotm.bolum_listesi


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Dönem uyumu adayları (çağdaş sözcükler).")
    ap.add_argument("bolum", help="N, A-B ya da N,M")
    ap.add_argument("--ozet", action="store_true", help="bölüm başına tek satır")
    a = ap.parse_args(argv)
    for no in bolum_listesi(a.bolum):
        yol = BOLUMLER / f"{no:04d}.md"
        if not yol.exists():
            print(f"YOK: {yol}")
            continue
        metin = yol.read_text(encoding="utf-8")
        if a.ozet:
            adaylar = tara(metin)
            y = yogunluk(metin)
            print(f"{no:4}  aday {len(adaylar):3}  dönem {y.get('donem', 0):5}  gotik {y.get('gotik', 0):5}  "
                  + " ".join(sorted({x['sozcuk'].lower() for x in adaylar})))
        else:
            print(f"# {no}\n{blok(no, metin)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
