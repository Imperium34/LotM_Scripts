#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
okuma.py -- coklu bolum okuma gecisi + hedefe donuk Cince gerceklik kontrolu
-> tek birlesik inceleme.md (sonra.py'nin Ch_N/ hattina dokunmaz).

UST DUZEY FARK:
  - sonra.py tam hatti (zincir + donem + ses_ayari + sadakat + duzeltme + triyaj
    + birlestir) tek tek bolum basina kurar.
  - okuma.py yalniz okuma gecisini paralel olarak bolum basina 1 cagriyla yurutur
    (onbellek Reports/okuma/Ch_N/), kirpilmis sablon + Yanki Defteri verir,
    birlestirme modeli cagirmadan Python ile ayristirir, varsayilan olarak yalniz
    aday duzeltmeler ve SADAKAT? sorulari icin hizali Cince gerceklik kontrolu
    yapar (--zh-kontrol-yok ile kapanir) ve butun bolumleri tek
    Reports/okuma/<aralik>/inceleme.md dosyasinda birlestirir.

YANKI DEFTERI + SABLON:
  - Yayimlanmis bolumlerde eski sablon yerine yalniz Yanki Defteri verilir.
  - Yayimlanmamis bolumlerde Yanki Defteri + kirpilmis sablon (A.1/A.2 Turkce
    terimleri + B Dondurulan satirlar + D Hitap tablosu; --tam-sablon ile tam).
  - Yanki secimi Kurulum/Odeme/Donmus bolum eslesmesine ek olarak surekli
    ('ileride'/'her'/'boyunca') girislerin Donmus ifadelerini metinde arar.

Kullanim:
    ./calistir.sh okuma 1-20                     girdileri hazirla + durum / hazirsa inceleme
    ./calistir.sh okuma 1-20 --otomatik          paralel okuma + ZH kontrol + tek inceleme.md
    ./calistir.sh okuma 1-20 --otomatik --zh-kontrol-yok   yalniz TR okuma
    ./calistir.sh okuma 1-20 --otomatik --cift-okuma       iki motorla okuma
    ./calistir.sh incele --okuma 1-20            tek inceleme.md'yi tarayicida ac
    ./calistir.sh okuma 1-20 --kararlar [--kuru] isaretlileri butun bolumlere uygula
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIKLER))

import motorlar  # noqa: E402
import sonra as S  # noqa: E402
from turkce import tr_kucult  # noqa: E402

RAPOR = Path(os.environ.get("LOTM_OKUMA_RAPOR") or BETIKLER / "Reports" / "okuma")
ZH_KONTROL_VARSAYILAN = os.environ.get("LOTM_ZH_KONTROL", "1") not in ("", "0")
UYGULANDI = "uygulandi.json"
KARARLAR_ISLENDI = "kararlar.json"

YANKI_SUREKLI = re.compile(r"ileride|boyunca|her\b|sonraki|tekrar", re.I)
YANKI_ALINTI = re.compile(r"\"([^\"]{2,120})\"|'([^']{2,120})'|“([^”]{2,120})”|‘([^’]{2,120})’|_([^_]{2,120})_|«([^»]{2,120})»")
YANKI_DURAK = {"ve", "ile", "bir", "bu", "şu", "da", "de", "ama", "fakat", "ya", "veya",
               "gibi", "için", "daha", "çok", "en", "ne", "ben", "sen", "biz", "siz", "onlar",
               "evet", "hayır", "yok", "var", "kötü", "iyi", "kısa", "uzun", "eski", "yeni",
               "söz", "sözcük", "bölüm", "örnek", "tekrar", "tüm", "hep"}
YANKI_KISA_OZEL = {"Biz", "Bizler", "Kaptan", "O'"}

ZH_KONTROL_ISTEM = """# Gizemlerin Efendisi — Okuma Sonrası Çince Gerçeklik Kontrolü

Sana bir bölümün **yalnızca** okuma geçişinde işaretlenen cümleleri, her birinin hizalı Çince (ZH) ve Türkçe (TR) paragrafı ile varsa Yankı Defteri verilir. Yeni bulgu arama; bütün bölümü baştan denetleme.

Görevin iki parçadır:

1. **Aday düzeltmeleri (`M1`, `M2`, …) denetle:**
   Okuma geçişi Çinceyi görmeden üslup/akıcılık önerisi verdi. Her aday için `✓` önerisinin Çince metindeki anlamı, dereceyi, kipliği, olguyu ya da Yankı Defteri'ndeki dondurulmuş ifadeyi bozup bozmadığına bak:
   - `ONAY`: Anlam, derece ve Yankı korunuyor; öneri güvenli. (`zh_not` kısa olabilir ya da boş.)
   - `UYARI`: Öneri Çincedeki bir ayrıntıyı, vurguyu, belirsizliği ya da nüansı kaydırıyor veya eksik bırakıyor. `zh_not`'ta Çincede ne yazdığını tek cümleyle yaz; mümkünse anlamı koruyan küçük bir `yeni` öner (yoksa `null`).
   - `RET`: `✗` metni aslında Çinceye sadık (ya da kasıtlı yankı/deyim); okumanın önerisi metni bozuyor ya da gereksiz. `zh_not`'ta nedenini Çinceye dayanarak tek cümleyle yaz.

2. **`SADAKAT?` sorularını (`S1`, `S2`, …) çöz:**
   Okuma geçişi anlamdan şüphelendiği yerleri işaretledi. Hizalı Çinceye bak:
   - Gerçek bir anlam kayması, düşme, ekleme ya da yanlış özne/terim varsa `sorun: true` yaz; `eski` bölümdeki TR'den **harfi harfine** (tam bir kez geçecek kadar), `yeni` en küçük düzeltme, `kural` kısa örüntü adı (`sadakat A anlam kayması`, `sadakat A düşmüş ayrıntı`, `sadakat D özne` vb.), `neden` ise `ZH ...:` ile başlayan tek cümle olsun.
   - Çinceyle uyumluysa `sorun: false` ve kısa bir `neden` yaz (`eski`/`yeni` null).

## ÇIKTI

Yalnızca tek bir JSON bloğu. Öncesinde ya da sonrasında açıklama yok.

```json
{
  "inceleme": [
    {"id": "M1", "karar": "ONAY", "zh_not": "", "yeni": null},
    {"id": "M2", "karar": "UYARI", "zh_not": "ZH 微微: 'hafifçe' kaynakta var, düşerse ton sertleşir.", "yeni": null}
  ],
  "sadakat": [
    {"id": "S1", "sorun": true, "kural": "sadakat A anlam kayması", "eski": "...", "yeni": "...", "neden": "ZH ...: ..."},
    {"id": "S2", "sorun": false, "kural": "", "eski": null, "yeni": null, "neden": "ZH ile uyumlu."}
  ]
}
```
"""


# ------------------------------------------------------------------ etiket & yardimci

def aralik_etiketi(nolar: list[int]) -> str:
    """[1, 2, 3, 7, 9, 10] -> '1-3,7,9-10'; [42] -> 'Ch_42'."""
    sirali = sorted(set(nolar))
    if not sirali:
        return "bos"
    if len(sirali) == 1:
        return f"Ch_{sirali[0]}"
    parcalar, bas, son = [], sirali[0], sirali[0]
    for n in sirali[1:]:
        if n == son + 1:
            son = n
        else:
            parcalar.append(f"{bas}-{son}" if bas != son else str(bas))
            bas = son = n
    parcalar.append(f"{bas}-{son}" if bas != son else str(bas))
    return ",".join(parcalar)


def zh_kontrol_acik(ac: bool, yok: bool, ortam: bool | None = None) -> bool:
    if yok:
        return False
    if ac:
        return True
    return ZH_KONTROL_VARSAYILAN if ortam is None else ortam


def zh_kontrol_istemi() -> str:
    yol = os.environ.get("LOTM_ZH_KONTROL_ISTEM")
    if yol and Path(yol).exists():
        return Path(yol).read_text(encoding="utf-8").rstrip()
    dosya = S.ISTEMLER / "lotm_okuma_zh_kontrol.md"
    if dosya.exists():
        return dosya.read_text(encoding="utf-8").rstrip()
    return ZH_KONTROL_ISTEM.rstrip()


# ------------------------------------------------------------------ yanki + kirpilmis sablon

def _yanki_ifadeleri(giris: dict) -> tuple[list[str], list[str]]:
    """(kucuk-harf genel ifadeler, buyuk/kucuk duyarli kisa ozel ifadeler)."""
    kaynak = (giris.get("donmus") or "") + " " + (giris.get("kurulum") or "")
    genel, ozel = [], []
    for m in YANKI_ALINTI.finditer(kaynak):
        parca = next(x for x in m.groups() if x is not None)
        for alt in re.split(r"\.\.\.|…|/|;", parca):
            temiz = alt.strip(" .,;:!?()[]—–-")
            if not temiz:
                continue
            if temiz in YANKI_KISA_OZEL:
                ozel.append(temiz)
                continue
            kucuk = tr_kucult(temiz)
            if kucuk in YANKI_DURAK or len(kucuk) < 5:
                continue
            genel.append(kucuk)
    return list(dict.fromkeys(genel)), list(dict.fromkeys(ozel))


def yanki_secimi_akilli(no: int, girisler: dict, bolum_metni: str, ek: tuple = ()) -> list[int]:
    """Bolume uyan Yanki girisleri:
    1) Kurulum, Odeme veya Donmus alaninda bolum numarasi gecenler + elle ekler.
    2) Surekli ('ileride'/'her'/'boyunca') girislerden, kurulumu <= no olup
       Donmus ifadelerinden biri bolum metninde gecenler.
    """
    secilen = set()
    for n, g in girisler.items():
        nolar = (S.bolum_numaralari(g.get("kurulum", ""))
                 | S.bolum_numaralari(g.get("odeme", ""))
                 | S.bolum_numaralari(g.get("donmus", "")))
        if no in nolar:
            secilen.add(n)
    secilen |= {n for n in ek if n in girisler}

    govde = S.front_matter_ayir(bolum_metni)
    govde_k = tr_kucult(govde)
    for n, g in girisler.items():
        if n in secilen:
            continue
        if not YANKI_SUREKLI.search(f"{g.get('odeme', '')} {g.get('kurulum', '')}"):
            continue
        kurulum_nolar = S.bolum_numaralari(g.get("kurulum", ""))
        if kurulum_nolar and min(kurulum_nolar) > no:
            continue
        genel, ozel = _yanki_ifadeleri(g)
        eslesti = any(re.search(r"(?<!\w)" + re.escape(p), govde_k) for p in genel)
        if not eslesti:
            eslesti = any(re.search(r"(?<!\w)" + re.escape(p), govde) for p in ozel)
        if eslesti:
            secilen.add(n)
    return sorted(secilen)


def yanki_blogu_akilli(no: int, bolum_metni: str, ek: tuple = ()) -> str:
    if not S.YANKI.exists():
        return ""
    girisler = S.yanki_girisleri(S.YANKI.read_text(encoding="utf-8"))
    secilen = yanki_secimi_akilli(no, girisler, bolum_metni, ek)
    if not secilen:
        return ""
    return (
        "<yanki_defteri>\n"
        "> Not (betik): Çok bölümlü dondurulmuş ifadeler, jestler ve yankılar. "
        "Buradaki dondurulmuş sözcükleri, tekrarları, hareketleri ve biçimleri değiştirme; "
        "1.5/1.6/1.9 bulgusu yapma.\n\n"
        + "\n\n".join(girisler[n]["blok"] for n in secilen)
        + "\n</yanki_defteri>\n\n"
    )


def _tablo_tr_terimleri(bolum_metni: str) -> list[str]:
    """A.1 / A.2 markdown tablosunun 2. (Turkce) sutunundaki terimler."""
    out, gorulen = [], set()
    for satir in bolum_metni.splitlines():
        if not satir.lstrip().startswith("|"):
            continue
        hucreler = [h.strip() for h in satir.strip().strip("|").split("|")]
        if len(hucreler) < 2:
            continue
        tr = re.sub(r"\*+", "", hucreler[1]).strip()
        if not tr or tr.startswith("-") or tr_kucult(tr) in ("türkçe", "turkce", "—", "-"):
            continue
        k = tr_kucult(tr)
        if k not in gorulen:
            gorulen.add(k)
            out.append(tr)
    return out


def _bolum_kes(metin: str, baslik_re: str) -> str:
    m = re.search(baslik_re, metin, re.M)
    if not m:
        return ""
    son = re.search(r"^(?:## |\*\*\*|---)\s*$", metin[m.end():], re.M)
    parca = metin[m.start():m.end() + son.start()] if son else metin[m.start():]
    return parca.strip()


def sablon_kirp(sablon: str) -> str:
    """Okuma gecisi icin yalniz dokunulmazlar: A.1/A.2 Turkce terimleri + B + D."""
    parcalar = []
    a_bolum = _bolum_kes(sablon, r"^## A\b.*$")
    if a_bolum:
        a12 = re.split(r"^### A\.3\b", a_bolum, flags=re.M)[0]
        terimler = _tablo_tr_terimleri(a12)
        if terimler:
            parcalar.append(
                "### A. Yerleşik ve bölüm terimleri (değiştirilemez, kısaltılmaz)\n\n"
                + " · ".join(terimler)
            )
    b_bolum = _bolum_kes(sablon, r"^## B\b.*$")
    if b_bolum:
        parcalar.append(b_bolum)
    d_bolum = _bolum_kes(sablon, r"^## D\b.*$")
    if d_bolum:
        parcalar.append(d_bolum)
    return "\n\n".join(parcalar).strip()


def sablon_blogu_okuma(b: S.Bolum, bolum_metni: str, tam_sablon: bool = False) -> str:
    """Yayimlanmis bolumde sablon yok (yalniz Yanki Defteri); yayimlanmamista kirpilmis sablon."""
    yayimli = S.yayim_tarihi_gecti(bolum_metni)
    if yayimli and not tam_sablon:
        return ""
    if not b.sablon.exists():
        return ""
    ham = b.sablon.read_text(encoding="utf-8").rstrip()
    if tam_sablon:
        govde = S.SABLON_USTUNLUK + "\n\n" + ham
    else:
        kirpik = sablon_kirp(ham)
        if not kirpik:
            return ""
        govde = S.SABLON_USTUNLUK + "\n\n" + kirpik
    return f"<bolum_sablonu>\n{govde}\n</bolum_sablonu>\n\n"


# ------------------------------------------------------------------ okuma ciktisi ayristirma

BULGU_BASLIK = re.compile(
    r"^[ \t]*(?:[-*+]\s+|#{1,6}\s+)?\*{0,2}¶(\d+)(?:\s*[–-]\s*¶?(\d+))?\s+(.+?)\*{0,2}\s*$"
)
KOD_DESEN = re.compile(r"\b(1\.(?:\d+(?:\([ivx]+\)|[ivx]+)?|M(?:\.\d+)?))\b")
MALIYET_DESEN = re.compile(r"(?:\([a-d]\)\s*·?\s*)+")
SATIR_X = re.compile(r"^(?:[-*+]\s+)?\*{0,2}✗\*{0,2}\s*(.*)$")
SATIR_V = re.compile(r"^(?:[-*+]\s+)?\*{0,2}✓\*{0,2}\s*(.*)$")
SATIR_NOT = re.compile(r"^(?:[-*+]\s+)?\*{0,2}(?:Not|Gerekçe)\*{0,2}\s*(?::|—|–|-)\s*(.*)$")


def metinde_bul(bolum_metni: str, aranan: str) -> tuple[str, int]:
    """Bolumde birebir ya da yalniz satir-sarim bosluk farkiyla tek eslesmeyi bulur."""
    aranan = aranan.strip()
    if not aranan:
        return "", 0
    n = bolum_metni.count(aranan)
    if n == 1:
        return aranan, 1
    if n > 1:
        return aranan, n
    esnek = re.sub(r"\s+", r"\\s+", re.escape(aranan))
    eslesmeler = list(re.finditer(esnek, bolum_metni))
    if len(eslesmeler) == 1:
        return eslesmeler[0].group(0), 1
    return aranan, len(eslesmeler)


def _paragraf_dogrula(bloklar: list[str], p: int, eski: str) -> int:
    if not eski:
        return p
    if 1 <= p <= len(bloklar) and eski in bloklar[p - 1]:
        return p
    for i, b in enumerate(bloklar, 1):
        if eski in b:
            return i
    return p


def _kural_adi(rest: str) -> tuple[str, str]:
    """(kural, temiz aciklama) — sonra.aileler() ile uyumlu."""
    kodlar = KOD_DESEN.findall(rest)
    temiz = KOD_DESEN.sub(" ", rest)
    temiz = re.sub(r"\b(?:SADAKAT\?|ŞÜPHELİ)\b", " ", temiz)
    temiz = MALIYET_DESEN.sub(" ", temiz)
    temiz = re.sub(r"[·•]+", " ", temiz)
    aciklama = S.bosluk(temiz).strip(" -—–:")
    if kodlar:
        norm = [re.sub(r"^(\d+\.\d+)([ivx]+)$", r"\1(\2)", k) for k in kodlar]
        kural = "okuma " + " + ".join(norm) + (f" {aciklama}" if aciklama else "")
    else:
        kural = f"okuma {aciklama}".strip() if aciklama else "okuma"
    return kural, aciklama


def _bulgular_bolumu(cikti: str) -> str:
    m2 = re.search(r"(?m)^(?:(?:#{1,4}\s*)|(?:\*\*))(?:\(2\)|2\.)\s*Bulgular\b.*$", cikti)
    bas = m2.end() if m2 else 0
    m3 = re.search(r"(?m)^(?:(?:#{1,4}\s*)|(?:\*\*))(?:\(3\)|3\.)\s*", cikti[bas:])
    return cikti[bas:bas + m3.start()] if m3 else cikti[bas:]


def okuma_ayristir(cikti: str, bolum_metni: str, no: int, motor: str | None = None) -> tuple[list, list, list]:
    """
    1_okuma_cikti.md -> (bulgular, sadakat_sorulari, bilgi).
    Birlestirme modeli olmadan deterministik ayristirma.
    """
    govde = _bulgular_bolumu(cikti)
    satirlar = govde.splitlines()
    bloklar_metin = S.tr_bloklari(bolum_metni)
    bloklar = []
    simdiki = None
    for s in satirlar:
        if s.strip().startswith("```"):
            continue
        m = BULGU_BASLIK.match(s)
        if m:
            if simdiki:
                bloklar.append(simdiki)
            simdiki = {"p": int(m.group(1)), "rest": m.group(3).strip().rstrip("*").strip(), "satirlar": []}
        elif simdiki is not None:
            simdiki["satirlar"].append(s)
    if simdiki:
        bloklar.append(simdiki)

    bulgular, sadakat, bilgi = [], [], []
    for bl in bloklar:
        rest = bl["rest"]
        sadakat_mi = "SADAKAT?" in rest
        supheli_mi = bool(re.search(r"\bŞÜPHELİ\b", rest))
        kural, aciklama = _kural_adi(rest)

        # Bir ¶ blogunda birden fazla ✗/✓ cifti olabilir (ornek: Ch_86 ¶2, ¶12).
        altlar, aktif, alan = [], None, None
        blok_not = []
        for s in bl["satirlar"]:
            t = re.sub(r"^(?:>\s*)+", "", s.strip()).strip()
            if not t or t.startswith("```"):
                alan = None
                continue
            if (mx := SATIR_X.match(t)):
                aktif = {"eski": [mx.group(1).strip()], "yeni": [], "not": []}
                altlar.append(aktif)
                alan = "eski"
            elif (mv := SATIR_V.match(t)):
                if aktif is None:
                    aktif = {"eski": [], "yeni": [], "not": []}
                    altlar.append(aktif)
                aktif["yeni"].append(mv.group(1).strip())
                alan = "yeni"
            elif (mn := SATIR_NOT.match(t)):
                (aktif["not"] if aktif is not None else blok_not).append(mn.group(1).strip())
                alan = "not"
            elif t.startswith("(") and (alan != "eski" or (aktif and aktif["yeni"])):
                (aktif["not"] if aktif is not None else blok_not).append(t)
                alan = "not"
            elif alan == "eski" and aktif is not None:
                aktif["eski"].append(t)
            elif alan == "yeni" and aktif is not None:
                aktif["yeni"].append(t)
            elif alan == "not":
                (aktif["not"] if aktif is not None else blok_not).append(t)
            else:
                (aktif["not"] if aktif is not None else blok_not).append(t)

        if not altlar:
            metin_n = S.bosluk(" ".join(blok_not)) or rest
            bilgi.append({"bolum": no, "p": bl["p"], "not": f"okuma ({kural}): {metin_n}"})
            continue

        for alt in altlar:
            eski_ham = " ".join(x for x in alt["eski"] if x).strip()
            yeni_ham = " ".join(x for x in alt["yeni"] if x).strip()
            # Model italik cizgilerini korumak icin satiri `...` icine aldiysa soy.
            if len(eski_ham) >= 2 and eski_ham[0] == "`" and eski_ham[-1] == "`" and "`" not in eski_ham[1:-1]:
                if eski_ham not in bolum_metni:
                    eski_ham = eski_ham[1:-1].strip()
                    if len(yeni_ham) >= 2 and yeni_ham[0] == "`" and yeni_ham[-1] == "`" and "`" not in yeni_ham[1:-1]:
                        yeni_ham = yeni_ham[1:-1].strip()
            not_ham = S.bosluk(" ".join(alt["not"] + blok_not)).strip()
            if not_ham.startswith("(") and not_ham.endswith(")") and not_ham.count("(") == 1:
                not_ham = not_ham[1:-1].strip()
            eski_tam, n_es = metinde_bul(bolum_metni, eski_ham)
            p = _paragraf_dogrula(bloklar_metin, bl["p"], eski_tam if n_es == 1 else "")

            if sadakat_mi:
                sadakat.append({
                    "bolum": no, "p": p, "kural": kural,
                    "eski": eski_tam if n_es == 1 else eski_ham,
                    "gerekce": not_ham or aciklama,
                })
                continue

            if supheli_mi or not yeni_ham:
                etiket = "ŞÜPHELİ" if supheli_mi else "önerisiz"
                parca = f"«{eski_ham[:90]}»" if eski_ham else ""
                bilgi.append({
                    "bolum": no, "p": p,
                    "not": f"okuma {etiket} ({kural}): {parca}" + (f" — {not_ham}" if not_ham else ""),
                })
                continue

            if n_es != 1 or eski_tam == yeni_ham:
                sebep = "öneri metni değiştirmiyor" if eski_tam == yeni_ham else f"metinde {n_es} kez geçti"
                bilgi.append({
                    "bolum": no, "p": p,
                    "not": f"okuma ({kural}) alınmadı ({sebep}): «{eski_ham[:80]}» → «{yeni_ham[:80]}»",
                })
                continue

            madde = {
                "bolum": no, "p": p, "sinif": "KARAR", "kaynak": ["okuma"],
                "kural": kural, "eski": eski_tam, "yeni": yeni_ham,
                "neden": not_ham or aciklama or kural,
            }
            if motor:
                madde["okuma_motor"] = [motor]
            bulgular.append(madde)

    return bulgular, sadakat, bilgi


def cift_okuma_birlestir(listeler: list[tuple[str, list, list, list]]) -> tuple[list, list, list]:
    """Birden cok okuma motorunun ciktilarini birlestirir (tek motor varsa motor etiketi eklemez)."""
    if len(listeler) == 1:
        _, b, s, g = listeler[0]
        for x in b:
            x.pop("okuma_motor", None)
        return b, s, g

    bulgular, sadakat, bilgi = [], [], []
    gorulen_sadakat, gorulen_bilgi = set(), set()

    for motor, bs, ss, gs in listeler:
        for d in bs:
            d = dict(d, okuma_motor=[motor])
            eslesen = next((x for x in bulgular if x["bolum"] == d["bolum"] and x["eski"] == d["eski"]), None)
            if eslesen is None:
                bulgular.append(d)
            elif S.bosluk(eslesen["yeni"]) == S.bosluk(d["yeni"]):
                eslesen["okuma_motor"] = sorted(set(eslesen.get("okuma_motor", [])) | {motor})
                if d["neden"] and d["neden"] not in eslesen["neden"]:
                    eslesen["neden"] = f"{eslesen['neden']} / {d['neden']}"
            else:
                not_sec = f"seçenek: ¶{d['p']}'deki öteki okuyucuyla aynı cümleye farklı öneri"
                if not_sec not in eslesen["neden"]:
                    eslesen["neden"] = f"{eslesen['neden']} — {not_sec}"
                d["neden"] = f"{d['neden']} — {not_sec}"
                bulgular.append(d)

        for s in ss:
            anahtar = (s["bolum"], s["p"], S.bosluk(s["eski"])[:40])
            if anahtar not in gorulen_sadakat:
                gorulen_sadakat.add(anahtar)
                sadakat.append(s)

        for g in gs:
            anahtar = (g["bolum"], g["p"], g["not"][:60])
            if anahtar not in gorulen_bilgi:
                gorulen_bilgi.add(anahtar)
                bilgi.append(g)

    bulgular.sort(key=lambda d: (d["bolum"], d.get("p") or 0))
    return bulgular, sadakat, bilgi


# ------------------------------------------------------------------ Cince gerceklik kontrolu

def _gruplari_yukle(no: int) -> dict:
    sys.path.insert(0, str(BETIKLER / "harita"))
    from gruplar import gruplar as _gruplar
    return {k: g for k, g in (_gruplar(no, "tr") or {}).items()
            if isinstance(g.get("TR"), str) and g["TR"].strip()
            and isinstance(g.get("ZH"), str)}


def _hizali_baglam(gruplar: dict, bloklar: list[str], p: int, eski: str) -> str:
    if not gruplar:
        return "(hizalama yok)"
    k = S.grup_bul({"no": p, "x": S.bosluk(eski)}, gruplar, bloklar)
    if k is None or not gruplar[k]["ZH"].strip():
        return "(hizalama grubu bulunamadı)"
    return f"hizalama ¶{k}\nZH: {gruplar[k]['ZH']}\nTR: {gruplar[k]['TR']}"


def zh_girdi_kur(no: int, bolum_metni: str, bulgular: list, sadakat: list, yanki: str) -> str | None:
    """Yalniz aday bulgular + SADAKAT? sorulari icin hizali ZH+TR kontrol girdisi."""
    if not bulgular and not sadakat:
        return None
    try:
        gruplar = _gruplari_yukle(no)
    except Exception:
        return None
    if not gruplar:
        return None
    bloklar = S.tr_bloklari(bolum_metni)
    parcalar = [zh_kontrol_istemi(), "---"]
    if yanki:
        parcalar.append(yanki.rstrip())
    if bulgular:
        satirlar = []
        for i, d in enumerate(bulgular, 1):
            satirlar.append(
                f"### M{i} · ¶{d['p']} · {d['kural']}\n"
                f"✗ {S.tek_satir(d['eski'])}\n"
                f"✓ {S.tek_satir(d['yeni'])}\n"
                f"Neden: {d['neden']}\n"
                f"{_hizali_baglam(gruplar, bloklar, d['p'], d['eski'])}"
            )
        parcalar.append("<adaylar>\n" + "\n\n".join(satirlar) + "\n</adaylar>")
    else:
        parcalar.append("<adaylar>\n(aday düzeltme yok)\n</adaylar>")

    if sadakat:
        satirlar = []
        for i, s in enumerate(sadakat, 1):
            satirlar.append(
                f"### S{i} · ¶{s['p']} · SADAKAT?\n"
                f"✗ {S.tek_satir(s['eski'])}\n"
                f"Gerekçe: {s['gerekce']}\n"
                f"{_hizali_baglam(gruplar, bloklar, s['p'], s['eski'])}"
            )
        parcalar.append("<sadakat_sorulari>\n" + "\n\n".join(satirlar) + "\n</sadakat_sorulari>")
    else:
        parcalar.append("<sadakat_sorulari>\n(SADAKAT? sorusu yok)\n</sadakat_sorulari>")
    return "\n\n".join(parcalar) + "\n"


def _zh_json_nesnesi(alanlar: list) -> dict:
    nesne = dict(alanlar)
    if len(nesne) != len(alanlar):
        raise ValueError("yinelenen JSON alanı")
    return nesne


def zh_sonuc_uygula(no: int, bolum_metni: str, bulgular: list, sadakat: list,
                    zh_cikti: str) -> tuple[list, list]:
    """ZH kontrol JSON'unu bulgulara uygular; (guncel bulgular, ek bilgi) dondurur."""
    ek_bilgi = []
    hata = None
    try:
        ham = zh_cikti.strip()
        cerceve = re.fullmatch(r"```(?:json)?[^\S\n]*\n(.*?)\n```", ham, re.S)
        veri = json.loads(cerceve[1] if cerceve else ham, object_pairs_hook=_zh_json_nesnesi)
        if not isinstance(veri, dict):
            raise ValueError("JSON nesne değil")
    except ValueError as e:
        hata = f"ZH kontrol çıktısı JSON okunamadı ({e})"
        veri = {}
        ek_bilgi.append({"bolum": no, "p": None, "not": hata})

    satirlar = veri.get("inceleme", [])
    if not isinstance(satirlar, list) or any(
        not isinstance(x, dict) or not isinstance(x.get("id"), str) for x in satirlar
    ):
        hata = "ZH kontrol karar listesi biçimsiz"
        satirlar = []
    inc_harita = {}
    for x in satirlar:
        inc_harita.setdefault(x["id"].strip(), []).append(x)

    try:
        gruplar = _gruplari_yukle(no)
    except Exception:
        gruplar = {}
    bloklar = S.tr_bloklari(bolum_metni)
    for i, d in enumerate(bulgular, 1):
        sonuclar = inc_harita.get(f"M{i}", [])
        neden = hata
        if not neden:
            if _hizali_baglam(gruplar, bloklar, d["p"], d["eski"]).startswith("("):
                neden = "ZH kontrol: kullanılabilir hizalama yok"
            elif len(sonuclar) != 1:
                neden = "ZH kontrol: " + ("yinelenen karar" if sonuclar else "karar eksik")
        if not neden:
            sonuc = sonuclar[0]
            karar = sonuc.get("karar")
            if karar is None or (isinstance(karar, str) and not karar.strip()):
                neden = "ZH kontrol: karar eksik"
            elif not isinstance(karar, str):
                neden = "ZH kontrol: karar biçimsiz"
            elif karar.strip().upper() not in ("ONAY", "UYARI", "RET"):
                neden = f"ZH kontrol: bilinmeyen karar ({karar})"
            elif any(sonuc.get(alan) is not None and not isinstance(sonuc[alan], str)
                     for alan in ("zh_not", "yeni")):
                neden = "ZH kontrol: karar biçimsiz"
        if neden:
            d.update(sinif="KARAR", zh_engel=True, dikkat=neden)
            continue
        karar = karar.strip().upper()
        zh_not = (sonuc.get("zh_not") or "").strip()
        zh_yeni = (sonuc.get("yeni") or "").strip()
        if karar == "ONAY":
            if zh_not:
                d["neden"] = f"{d['neden']} — ZH: {zh_not}"
        elif karar == "UYARI":
            d.update(sinif="KARAR", zh_engel=True)
            ek = f"ZH uyarı: {zh_not}" if zh_not else "ZH uyarı"
            if zh_yeni and zh_yeni != d["yeni"]:
                ek += f" (ZH önerisi: «{zh_yeni}»)"
            d["neden"] = f"{d['neden']} — {ek}"
            d["dikkat"] = f"ZH kontrol uyarı: {zh_not or 'Çince nüans farkı'}"
        elif karar == "RET":
            d.update(sinif="KARAR", zh_engel=True)
            d["neden"] = f"{d['neden']} — ZH ret: {zh_not}" if zh_not else f"{d['neden']} — ZH ret"
            d["dikkat"] = f"ZH kontrol ret: {zh_not or 'Çinceye göre değişiklik gerekmiyor'}"

    sad_satirlar = veri.get("sadakat")
    sad_harita = {x["id"].strip(): x for x in sad_satirlar
                  if isinstance(x, dict) and isinstance(x.get("id"), str)
                  and isinstance(x.get("sorun"), bool)
                  and all(x.get(alan) is None or isinstance(x[alan], str)
                          for alan in ("eski", "yeni", "kural", "neden"))} if isinstance(sad_satirlar, list) else {}
    for i, s in enumerate(sadakat, 1):
        cozum = sad_harita.get(f"S{i}")
        if not cozum:
            ek_bilgi.append({"bolum": no, "p": s["p"],
                             "not": f"okuma SADAKAT?: «{s['eski'][:90]}» — {s['gerekce']}"})
            continue
        if not cozum.get("sorun"):
            ek_bilgi.append({"bolum": no, "p": s["p"],
                             "not": f"SADAKAT? çözüldü (ZH uyumlu): «{s['eski'][:70]}» — {cozum.get('neden', '')}"})
            continue
        eski_ham = (cozum.get("eski") or s["eski"] or "").strip()
        yeni_ham = (cozum.get("yeni") or "").strip()
        eski_tam, n_es = metinde_bul(bolum_metni, eski_ham)
        if not yeni_ham or n_es != 1 or eski_tam == yeni_ham:
            ek_bilgi.append({
                "bolum": no, "p": s["p"],
                "not": f"SADAKAT? sorun var ama metne oturtulamadı (eşleşme {n_es}): "
                       f"«{eski_ham[:70]}» — {cozum.get('neden', '')}",
            })
            continue
        kural = (cozum.get("kural") or "sadakat A anlam kayması").strip()
        p = _paragraf_dogrula(bloklar, s["p"], eski_tam)
        bulgular.append({
            "bolum": no, "p": p, "sinif": "KARAR",
            "kaynak": ["okuma", "zh_kontrol"],
            "kural": kural, "eski": eski_tam, "yeni": yeni_ham,
            "neden": (cozum.get("neden") or s["gerekce"]).strip(),
            "zh_engel": True,
        })

    bulgular.sort(key=lambda d: (d["bolum"], d.get("p") or 0))
    return bulgular, ek_bilgi


# ------------------------------------------------------------------ tek bolum kosusu

def bolum_calistir(no: int, a, otomatik: bool, zh_kontrol: bool, cift_okuma: bool,
                   motor_secimleri: dict) -> tuple[int, str]:
    """Tek bolumun okuma (+ opsiyonel cift okuma + ZH kontrol) onbellegini kurar/yurutur."""
    b = S.Bolum(no, parti_boyu=6000)
    if not b.dosya.exists():
        print(f"YOK: {b.dosya}")
        return 1, f"YOK: {b.dosya.name}"
    klasor = RAPOR / f"Ch_{no}"
    klasor.mkdir(parents=True, exist_ok=True)
    bolum_metni = b.dosya.read_text(encoding="utf-8")

    yanki = yanki_blogu_akilli(no, bolum_metni)
    sablon = sablon_blogu_okuma(b, bolum_metni, tam_sablon=a.tam_sablon)
    girdi = klasor / "girdi.md"
    cikti = klasor / "cikti.md"
    metin = (
        f"{S.istem('okuma')}\n\n---\n\n"
        f"{S.kararlar_blogu()}"
        f"{yanki}"
        f"{sablon}"
        f"{b.o_blogu()}"
        f"{b.durum_blogu()}"
        f"<bolum>\n{bolum_metni.rstrip()}\n</bolum>\n"
    )
    S.yaz_defter_haric(girdi, metin, cikti)

    motor1 = motorlar.motor_sec("okuma", motor_secimleri)
    motor2 = motorlar.ikinci_motor(motor1, motor_secimleri, "okuma") if cift_okuma else None
    hedefler = [(cikti, motor1)]
    if cift_okuma and motor2:
        hedefler.append((klasor / f"cikti.{motor2}.md", motor2))

    hata = False
    acik = {m.partition("=")[0] for m in getattr(a, "motor", [])}
    if otomatik:
        for c_yol, mt in hedefler:
            degisti = (("okuma" in acik and c_yol == cikti) or ("okuma2" in acik and c_yol != cikti)) \
                and c_yol.exists() and motorlar.etiket_oku(c_yol) != mt
            if S.durum(girdi, c_yol) != "TAMAM" or degisti:
                if not S.yurut(girdi, c_yol, a.model, a.sure, None, mt):
                    hata = True

    if not all(S.durum(girdi, c_yol) == "TAMAM" for c_yol, _ in hedefler):
        durumlar = ", ".join(f"{c.name}:{S.durum(girdi, c)}" for c, _ in hedefler)
        return (1 if hata else 0), f"okuma bekliyor ({durumlar})"

    # Okuma bitti; ZH kontrol gerekiyorsa kur / yurut.
    listeler = []
    for c_yol, mt in hedefler:
        gercek_m = motorlar.cikti_motoru(c_yol, "") or motorlar.etiket_oku(c_yol) or mt
        bs, ss, gs = okuma_ayristir(c_yol.read_text(encoding="utf-8"), bolum_metni, no, gercek_m)
        listeler.append((gercek_m, bs, ss, gs))
    bulgular, sadakat, _ = cift_okuma_birlestir(listeler)

    zh_not = "zh kapalı"
    if zh_kontrol:
        zh_girdi = klasor / "zh_girdi.md"
        zh_cikti = klasor / "zh_cikti.md"
        zh_metin = zh_girdi_kur(no, bolum_metni, bulgular, sadakat, yanki)
        if zh_metin is None:
            zh_girdi.unlink(missing_ok=True)
            zh_cikti.unlink(missing_ok=True)
            zh_not = "zh atlandı (bulgu/hizalama yok)"
        else:
            S.yaz_degisirse(zh_girdi, zh_metin)
            zh_motor = motorlar.motor_sec("zh", motor_secimleri)
            if otomatik:
                degisti = "zh" in acik and zh_cikti.exists() and motorlar.etiket_oku(zh_cikti) != zh_motor
                if S.durum(zh_girdi, zh_cikti) != "TAMAM" or degisti:
                    if not S.yurut(zh_girdi, zh_cikti, a.model, a.sure, None, zh_motor):
                        hata = True
            zh_not = f"zh {S.durum(zh_girdi, zh_cikti)}"

    return (1 if hata else 0), f"okuma TAMAM ({len(bulgular)} aday, {len(sadakat)} SADAKAT?) · {zh_not}"


# ------------------------------------------------------------------ tek inceleme.md kurma

def birlesik_inceleme_kur(nolar: list[int], etiket: str, zh_kontrol: bool, cift_okuma: bool,
                          motor_secimleri: dict, kuru: bool, kesin_yok: bool,
                          yeniden: bool = False, anlik: dict | None = None) -> tuple[int, str]:
    hedef_klasor = RAPOR / etiket
    hedef_klasor.mkdir(parents=True, exist_ok=True)
    inceleme = hedef_klasor / (S.INCELEME_ONIZLEME if kuru else "inceleme.md")
    isaret = hedef_klasor / UYGULANDI

    if isaret.exists() and not (yeniden or kuru):
        return 0, f"donuk: {inceleme} hazir (yeniden kurmak icin --yeniden; kararlar icin --kararlar)"

    motor1 = motorlar.motor_sec("okuma", motor_secimleri)
    motor2 = motorlar.ikinci_motor(motor1, motor_secimleri, "okuma") if cift_okuma else None

    tum_uygulanan, tum_karar, tum_bilgi, bekleyen = [], [], [], []
    degisen_dosyalar: dict[int, tuple[Path, str, str]] = {}
    if anlik is None:
        yollar = [S.BOLUMLER / f"{no:04d}.md" for no in nolar]
        anlik = {yol: S.lotm.dosya_anlik(yol) for yol in yollar}

    for no in nolar:
        b = S.Bolum(no, parti_boyu=6000)
        veri = anlik[b.dosya]
        if veri is None:
            tum_bilgi.append({"bolum": no, "p": None, "not": f"bölüm dosyası yok: {b.dosya.name}"})
            continue
        klasor = RAPOR / f"Ch_{no}"
        girdi, cikti = klasor / "girdi.md", klasor / "cikti.md"
        hedefler = [(cikti, motor1)]
        if cift_okuma and motor2:
            hedefler.append((klasor / f"cikti.{motor2}.md", motor2))
        if not all(S.durum(girdi, c) == "TAMAM" for c, _ in hedefler):
            bekleyen.append(f"Ch_{no} (okuma)")
            continue

        asil = veri.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        listeler = []
        for c_yol, mt in hedefler:
            gercek_m = motorlar.cikti_motoru(c_yol, "") or motorlar.etiket_oku(c_yol) or mt
            bs, ss, gs = okuma_ayristir(c_yol.read_text(encoding="utf-8"), asil, no, gercek_m)
            listeler.append((gercek_m, bs, ss, gs))
        bulgular, sadakat, bilgi = cift_okuma_birlestir(listeler)

        zh_girdi, zh_cikti = klasor / "zh_girdi.md", klasor / "zh_cikti.md"
        if zh_kontrol and zh_girdi.exists():
            if not zh_cikti.exists() or zh_girdi.stat().st_mtime > zh_cikti.stat().st_mtime:
                bekleyen.append(f"Ch_{no} (zh)")
                continue
            bulgular, ek_bilgi = zh_sonuc_uygula(no, asil, bulgular, sadakat, zh_cikti.read_text(encoding="utf-8"))
            bilgi += ek_bilgi
        else:
            if zh_kontrol:
                for d in bulgular:
                    d.update(sinif="KARAR", zh_engel=True,
                             dikkat="ZH kontrol: kullanılabilir hizalama yok")
            for s in sadakat:
                bilgi.append({"bolum": no, "p": s["p"],
                              "not": f"okuma SADAKAT?: «{s['eski'][:90]}» — {s['gerekce']}"})

        # Ayni cumleye birden fazla aday dusuyorsa hicbiri otomatik uygulanmasin.
        eski_say = {}
        for d in bulgular:
            eski_say[d["eski"]] = eski_say.get(d["eski"], 0) + 1
        for d in bulgular:
            if not d.get("zh_engel") and eski_say[d["eski"]] == 1 and S.otomatige_uygun(d):
                d["sinif"], d["otomatik"] = "KESIN", True

        yeni, uygulanan, karar = S.uygula(asil, bulgular, kesin_yok=kesin_yok)
        for d in karar:
            d.pop("otomatik", None)
        if uygulanan:
            degisen_dosyalar[no] = (b.dosya, asil, yeni)
        tum_uygulanan.extend(uygulanan)
        tum_karar.extend(karar)
        tum_bilgi.extend(bilgi)

    if bekleyen:
        return 0, f"inceleme bekliyor ({len(bekleyen)} eksik: {', '.join(bekleyen[:6])}" \
                  + ("..." if len(bekleyen) > 6 else "") + ")"

    ic = S.inceleme_yaz(etiket, tum_uygulanan, tum_karar, tum_bilgi, kuru=kuru, onizleme=kuru)
    if not kuru:
        ic = S.inceleme_katmanla(ic).replace(f"`./calistir.sh sonra {etiket} --kararlar`",
                                               f"`./calistir.sh okuma {etiket} --kararlar`")
    if kuru:
        S.lotm.atomik_yaz(inceleme, ic)
        return 0, f"kuru: {len(tum_uygulanan)} otomatik uygulanirdi, {len(tum_karar)} karar -> {inceleme}"

    if anlik:
        try:
            S.lotm.bolumleri_yaz(S.BOLUMLER, anlik,
                                 {yol: yeni for yol, _, yeni in degisen_dosyalar.values()},
                                 etiket=f"okuma-{etiket}")
        except S.lotm.BolumYazmaHatasi as e:
            return 1, f"HATA: {e}"
    S.lotm.atomik_yaz(inceleme, ic)
    if degisen_dosyalar:
        fark_satir = []
        for no, (dosya, asil, yeni) in sorted(degisen_dosyalar.items()):
            fark_satir.extend(difflib.unified_diff(
                asil.strip().splitlines(), yeni.strip().splitlines(),
                f"{dosya.name} (simdiki)", f"{dosya.name} (okuma)", lineterm="", n=0))
        (hedef_klasor / "uygulanan.diff").write_text(
            "\n".join(fark_satir) + ("\n" if fark_satir else ""), encoding="utf-8")

    isaret.write_text(json.dumps({
        "zaman": time.strftime("%Y-%m-%d %H:%M"),
        "bolumler": nolar,
        "uygulanan": len(tum_uygulanan),
        "karar": len(tum_karar),
    }, ensure_ascii=False), encoding="utf-8")
    return 0, (f"{len(tum_uygulanan)} otomatik uygulandi ({len(degisen_dosyalar)} bolum), "
               f"{len(tum_karar)} karar bekliyor -> {inceleme}")


# ------------------------------------------------------------------ --kararlar

def kararlari_isle(etiket: str, nolar: list[int], kuru: bool, dosya: Path | None = None) -> str:
    inceleme = dosya or (RAPOR / etiket / "inceleme.md")
    if inceleme.resolve().name == S.INCELEME_ONIZLEME or not inceleme.exists():
        return f"YOK: uygulanabilir inceleme: {inceleme}"
    inc_metin = inceleme.read_text(encoding="utf-8")
    secimler = S.inceleme_oku(inc_metin)
    onceki = S.uygulanan_oku(inc_metin)
    varsayilan_no = nolar[0] if len(nolar) == 1 else None

    # Bolumlere ayir
    sec_by_b: dict[int, list] = {}
    for s in secimler:
        bno = s.get("bolum") or varsayilan_no
        if bno is None:
            continue
        sec_by_b.setdefault(bno, []).append(s)
    uyg_by_b: dict[int, list] = {}
    for u in onceki:
        bno = u.get("bolum") or varsayilan_no
        if bno is None:
            continue
        uyg_by_b.setdefault(bno, []).append(u)
    oto_by_b: dict[int, list] = {}
    for u in onceki:
        if u["otomatik"] and u["geri"] is not None:
            bno = u.get("bolum") or varsayilan_no
            if bno is not None:
                oto_by_b.setdefault(bno, []).append({
                    "k": f"O{u['i']}", "kural": u["kural"], "sinif": "KARAR",
                    "kabul": not u["geri"], "ret": bool(u["geri"]),
                })

    uygulanan, bulunamayan, celiskili, defter = [], [], [], []
    geri_alinan, geri_yok = [], []
    degisen: dict[int, tuple[Path, str]] = {}
    anlik = {}

    for bno in sorted(set(sec_by_b) | set(uyg_by_b)):
        yol = S.BOLUMLER / f"{bno:04d}.md"
        anlik[yol] = S.lotm.dosya_anlik(yol)
        if anlik[yol] is None:
            continue
        asil = anlik[yol].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        metin = asil
        degisti = False
        for u in uyg_by_b.get(bno, []):
            if not u["geri"]:
                continue
            if u["yeni"] and metin.count(u["yeni"]) == 1:
                metin = metin.replace(u["yeni"], u["eski"], 1)
                geri_alinan.append(f"U{u['i']}")
                degisti = True
            elif not (u["eski"] and metin.count(u["eski"]) == 1 and u["yeni"] not in metin):
                geri_yok.append(f"U{u['i']}")
        for s in sec_by_b.get(bno, []):
            if s["kabul"] and s["ret"]:
                celiskili.append(f"K{s['k']}")
                continue
            if s["kabul"]:
                if s["eski"] == s["yeni"]:
                    pass
                elif metin.count(s["eski"]) == 1:
                    metin = metin.replace(s["eski"], s["yeni"], 1)
                    uygulanan.append(f"K{s['k']}")
                    degisti = True
                else:
                    bulunamayan.append(f"K{s['k']}")
            if s["hep"] and (s["kabul"] or s["ret"]):
                hukum = "kabul" if s["kabul"] else "ret"
                defter.append(f"- {hukum} · {s['kural']} — örnek: «{S.tek_satir(s['eski'])}» → "
                              f"«{S.tek_satir(s['yeni'])}» ({bno}. bölüm ¶{s['p']})")
        if degisti and metin != asil:
            degisen[bno] = (yol, metin)

    if not kuru:
        if anlik:
            try:
                S.lotm.bolumleri_yaz(S.BOLUMLER, anlik, dict(degisen.values()),
                                     etiket=f"okuma-kararlar-{etiket}")
            except S.lotm.BolumYazmaHatasi as e:
                return f"HATA: {e}"
        for bno in sorted(set(sec_by_b) | set(oto_by_b)):
            S.istatistik_kaydet(S.ISTATISTIK, bno, sec_by_b.get(bno, []) + oto_by_b.get(bno, []), "okuma")
            S.motor_kaydet(S.MOTOR_IST, bno, sec_by_b.get(bno, []), "okuma")
        if defter:
            eski_defter = S.KARARLAR.read_text(encoding="utf-8") if S.KARARLAR.exists() else ""
            var = {(m.group(1), m.group(3), m.group(4)) for m in
                   map(S.DEFTER_SATIRI.match, eski_defter.splitlines()) if m}
            defter = [d for d in defter if not ((m := S.DEFTER_SATIRI.match(d))
                                                and (m.group(1), m.group(3), m.group(4)) in var)]
        if defter:
            S.KARARLAR.parent.mkdir(parents=True, exist_ok=True)
            bas = "" if S.KARARLAR.exists() else (
                "# Karar defteri\n\nsonra.py'nin inceleme adımında 'hep' denen kararlar. "
                "Her geçişe verilir; elle düzenlenebilir.\n\n")
            with S.KARARLAR.open("a", encoding="utf-8") as f:
                f.write(bas + "\n".join(defter) + "\n")
        (inceleme.parent / KARARLAR_ISLENDI).write_text(json.dumps({
            "zaman": time.strftime("%Y-%m-%d %H:%M"),
            "uygulanan": len(uygulanan), "bolumler": sorted(degisen),
            "defter": len(defter), "bulunamayan": bulunamayan, "celiskili": celiskili,
            "geri_alinan": geri_alinan, "geri_alinamayan": geri_yok,
        }, ensure_ascii=False), encoding="utf-8")

    sonuc = (f"{len(uygulanan)} karar uygulandi ({len(degisen)} bolum), "
             f"{len(defter)} kalici karar deftere yazildi"
             + (f", {len(geri_alinan)} uygulanan geri alindi" if geri_alinan else "")
             + (f"; metinde bulunamayan: {', '.join(bulunamayan)}" if bulunamayan else "")
             + (f"; çelişkili (kabul+ret): {', '.join(celiskili)}" if celiskili else "")
             + (f"; geri alinamayan: {', '.join(geri_yok)}" if geri_yok else ""))
    return ("kuru: " if kuru else "") + sonuc


# ------------------------------------------------------------------ paralel kosu

def paralel_kos(nolar: list[int], a, argv: list[str]) -> tuple[int, dict[int, tuple[int, str]], dict]:
    temel, atla = [], False
    for x in argv:
        if atla:
            atla = False
            continue
        if x in ("--paralel", "--ad", "--dosya"):
            atla = True
            continue
        if x.startswith(("--paralel=", "--ad=", "--dosya=")) or x in ("--yeniden", "--bastan", "--sadece-bolum"):
            continue
        temel.append(x)
    if a.no in temel:
        i = temel.index(a.no)
        temel = temel[:i] + temel[i + 1:]

    print(f"Paralel okuma: {len(nolar)} bolum, ayni anda {a.paralel}"
          + (" (oto: hiz sinirinda duser)" if getattr(a, "paralel_oto", False) else "")
          + ", gunlukler Reports/okuma/Ch_N/kosu.log", flush=True)

    ortam = dict(os.environ, LOTM_OKUMA_COCUK="1")
    bekleyen, kosan, sonuc = list(nolar), {}, {}
    sinir, yeniden_set, kota = a.paralel, set(), dict(S.KOTA_DOLU)
    try:
        while bekleyen or kosan:
            while bekleyen and len(kosan) < sinir:
                no = bekleyen.pop(0)
                klasor = RAPOR / f"Ch_{no}"
                klasor.mkdir(parents=True, exist_ok=True)
                (klasor / "OZET.txt").unlink(missing_ok=True)
                gunluk = (klasor / "kosu.log").open("w", encoding="utf-8")
                p = subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), str(no), "--sadece-bolum"] + temel,
                    stdout=gunluk, stderr=subprocess.STDOUT, cwd=BETIKLER, env=ortam)
                kosan[no] = (p, gunluk, time.time())
                print(f"  {time.strftime('%H:%M:%S')} basladi {no}", flush=True)
            time.sleep(1.5)
            for no, (p, gunluk, bas) in list(kosan.items()):
                if p.poll() is None:
                    continue
                gunluk.close()
                del kosan[no]
                oz = RAPOR / f"Ch_{no}" / "OZET.txt"
                kisa = (oz.read_text(encoding="utf-8").strip().split("\t", 1)[-1] if oz.exists()
                        else f"HATA: cikis {p.returncode}, bkz. Ch_{no}/kosu.log")
                yeni_kota, hiz = S.gunluk_sorunu(RAPOR / f"Ch_{no}" / "kosu.log")
                if yeni_kota.keys() - kota.keys():
                    kota.update(yeni_kota)
                    ortam["LOTM_KOTA_DOLU"] = ",".join(kota)
                    print(f"  {time.strftime('%H:%M:%S')} KOTA DOLU: "
                          + "; ".join(f"{m}: {s}" for m, s in yeni_kota.items()), flush=True)
                if getattr(a, "paralel_oto", False) and no not in yeniden_set and hiz:
                    sinir = max(1, sinir - 1)
                    yeniden_set.add(no)
                    bekleyen.append(no)
                    print(f"  {time.strftime('%H:%M:%S')} hiz siniri {no}: ayni anda artik {sinir}, "
                          "bolum kuyrugun sonunda yeniden denenecek", flush=True)
                    if sinir == 1 and len(kosan) == 0:
                        time.sleep(60)
                    continue
                sonuc[no] = (p.returncode, kisa)
                print(f"  {time.strftime('%H:%M:%S')} bitti   {no} ({(time.time() - bas) / 60:.1f} dk): {kisa}",
                      flush=True)
    except KeyboardInterrupt:
        for p, gunluk, _ in kosan.values():
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
            gunluk.close()
        print("\nDurduruldu; yarim kalan gecisler bir sonraki calistirmada BEKLIYOR gorunur.")
        return 130, sonuc, kota

    kod = max([0] + [k for k, _ in sonuc.values()])
    return kod, sonuc, kota


# ------------------------------------------------------------------ ana

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Coklu bolum okuma gecisi + Cince gerceklik kontrolu -> tek inceleme.md.")
    ap.add_argument("no", metavar="BOLUM",
                    help="bolum numarasi, aralik ya da liste: 61, 1-20, 1,3,10-15")
    ap.add_argument("--otomatik", action="store_true",
                    help="eksik/eskimis okuma ve ZH kontrol ciktilarini modelle uret")
    ap.add_argument("--zh-kontrol", action="store_true",
                    help="aday duzeltmeler ve SADAKAT? icin hizali Cince kontrolu (varsayilan acik)")
    ap.add_argument("--zh-kontrol-yok", action="store_true",
                    help="Cince gerceklik kontrolunu atla (LOTM_ZH_KONTROL=0 ayni)")
    ap.add_argument("--cift-okuma", action="store_true",
                    help="okumayi ikinci bir motorla da (varsayilan codex) ayri calistir")
    ap.add_argument("--kesin-yok", action="store_true",
                    help="otomatik (okuma 1.6) uygulama yapma, hepsini inceleme.md'ye koy")
    ap.add_argument("--tam-sablon", action="store_true",
                    help="yayimlanmis bolumlerde de tam sablon ver (varsayilan: yayimlanmista yalniz Yanki, yenide kirpilmis)")
    ap.add_argument("--kararlar", action="store_true",
                    help="inceleme.md'de isaretlenen kararlari ilgili bolumlere uygula")
    ap.add_argument("--kuru", action="store_true",
                    help="inceleme_onizleme.md yaz, bolum dosyasina ve deftere yazma")
    ap.add_argument("--yeniden", action="store_true",
                    help="var olan inceleme.md/uygulandi.json'u yenile")
    ap.add_argument("--bastan", action="store_true",
                    help="Ch_N onbellegini temizleyip bastan kur (ve incelemeyi yenile)")
    ap.add_argument("--ad", default=None, metavar="ETIKET",
                    help="inceleme klasor adi (varsayilan: aralik, ornek 1-20)")
    ap.add_argument("--dosya", type=Path, default=None,
                    help="--kararlar icin ozel inceleme.md yolu")
    ap.add_argument("--motor", action="append", default=[], metavar="ADIM=MOTOR",
                    help="adim basina motor: okuma=..., okuma2=..., zh=... (claude|codex|antigravity)")
    ap.add_argument("--model")
    ap.add_argument("--sure", type=int, default=1800)
    ap.add_argument("--paralel", default=os.environ.get("LOTM_PARALEL") or "oto", metavar="N|oto")
    ap.add_argument("--sadece-bolum", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.kuru and a.bastan:
        ap.error("--kuru ile --bastan birlikte kullanılamaz")

    try:
        nolar = S.bolum_listesi(a.no)
    except ValueError as e:
        if a.kararlar and (a.dosya or (RAPOR / a.no / "inceleme.md").exists()):
            nolar = []
        else:
            ap.error(str(e))
    try:
        a.paralel, a.paralel_oto = S.paralel_sayisi(a.paralel, max(1, len(nolar)))
    except ValueError:
        ap.error(f"--paralel {a.paralel}: bir sayi ya da 'oto' olmali")

    motor_secimleri = {}
    for m in a.motor:
        adim, _, mt = m.partition("=")
        if adim not in ("okuma", "okuma2", "zh") or mt not in motorlar.MOTORLAR:
            ap.error(f"--motor {m}: adim (okuma, okuma2, zh), motor {motorlar.MOTORLAR}")
        motor_secimleri[adim] = mt

    etiket = a.ad or (a.dosya.parent.name if a.dosya else (aralik_etiketi(nolar) if nolar else a.no))

    if a.kararlar:
        sonuc = kararlari_isle(etiket, nolar, a.kuru, dosya=a.dosya)
        print(sonuc)
        return int(sonuc.startswith(("YOK:", "HATA:")))

    zh_kontrol = zh_kontrol_acik(a.zh_kontrol, a.zh_kontrol_yok)
    cift_okuma = a.cift_okuma or S.CIFT_OKUMA

    if a.sadece_bolum:
        k, kisa = bolum_calistir(nolar[0], a, a.otomatik, zh_kontrol, cift_okuma, motor_secimleri)
        if os.environ.get("LOTM_OKUMA_COCUK"):
            (RAPOR / f"Ch_{nolar[0]}" / "OZET.txt").write_text(f"{k}\t{kisa}\n", encoding="utf-8")
        print(kisa)
        return k

    hedef_isaret = RAPOR / etiket / UYGULANDI
    if hedef_isaret.exists() and not (a.yeniden or a.bastan or a.kuru):
        print(f"{etiket} incelemesi zaten hazir ({hedef_isaret.read_text(encoding='utf-8')}).")
        print(f"  inceleme: {RAPOR / etiket / 'inceleme.md'}")
        print(f"  tarayici: ./calistir.sh incele --okuma {etiket}")
        print(f"  kararlar: ./calistir.sh okuma {etiket} --kararlar")
        print(f"  yeniden:  ./calistir.sh okuma {a.no} --yeniden")
        return 0

    if a.bastan:
        for no in nolar:
            k = RAPOR / f"Ch_{no}"
            for ad in ("girdi.md", "cikti.md", "zh_girdi.md", "zh_cikti.md"):
                (k / ad).unlink(missing_ok=True)
            for ek in k.glob("cikti.*.md"):
                ek.unlink(missing_ok=True)

    yollar = [S.BOLUMLER / f"{no:04d}.md" for no in nolar]
    anlik = {yol: S.lotm.dosya_anlik(yol) for yol in yollar}

    # Otomatik kipte motor araclari kontrolu
    otomatik = a.otomatik
    if otomatik:
        gereken = {motorlar.motor_sec("okuma", motor_secimleri)}
        if cift_okuma:
            gereken.add(motorlar.ikinci_motor(motorlar.motor_sec("okuma", motor_secimleri), motor_secimleri, "okuma"))
        if zh_kontrol:
            gereken.add(motorlar.motor_sec("zh", motor_secimleri))
        if "claude" in gereken and not shutil.which(motorlar.claude_komutu(None)[0]):
            print(f"YOK: '{motorlar.claude_komutu(None)[0]}' komutu bulunamadi; yalniz girdiler hazirlaniyor.")
            otomatik = False

    if len(nolar) > 1 and a.paralel > 1 and otomatik:
        kod, ozet_map, kota = paralel_kos(nolar, a, argv if argv is not None else sys.argv[1:])
        if kod == 130:
            return 130
        ozetler = [f"{no:4}  {ozet_map.get(no, (1, 'yok'))[1]}" for no in nolar]
    else:
        kod, ozetler, kota = 0, [], S.KOTA_DOLU
        for no in nolar:
            print(f"=== {no}. bolum ===", flush=True)
            try:
                k, kisa = bolum_calistir(no, a, otomatik, zh_kontrol, cift_okuma, motor_secimleri)
            except Exception as e:  # noqa: BLE001
                k, kisa = 1, f"HATA: {type(e).__name__}: {e}"
            kod = max(kod, k)
            ozetler.append(f"{no:4}  {kisa}")
            print(f"  {kisa}", flush=True)

    inc_kod, inc_ozet = birlesik_inceleme_kur(
        nolar, etiket, zh_kontrol, cift_okuma, motor_secimleri,
        kuru=a.kuru, kesin_yok=a.kesin_yok or S.KESIN_YOK,
        yeniden=a.yeniden or a.bastan, anlik=anlik,
    )
    kod = max(kod, inc_kod)

    rapor = (
        f"# Okuma ({etiket}, {time.strftime('%Y-%m-%d %H:%M')})\n\n"
        + "\n".join(ozetler)
        + f"\n\n## Birleşik inceleme\n{inc_ozet}\n"
        + S.kota_notu(kota)
    )
    (RAPOR / etiket).mkdir(parents=True, exist_ok=True)
    (RAPOR / etiket / "OZET.md").write_text(rapor, encoding="utf-8")
    print(f"\n{'=' * 60}\n{rapor}")
    if (RAPOR / etiket / "inceleme.md").exists():
        print(f"İnceleme sayfası: ./calistir.sh incele --okuma {etiket}")
    return kod


if __name__ == "__main__":
    sys.exit(main())
