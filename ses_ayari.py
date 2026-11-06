#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ses_ayari.py -- eski bolumlerin sicil ayari: donem tabani + gotik doruklar.

Iki olculebilir sorun (3 Kas olcumu, lint register sayaci):
  - donem tabani 23-33 ve 62-72'de dusuk (2.0 ve ~1/1000; 34-61 ortalamasi 4.7)
  - gotik doruklar harcanmamis (71: sablon 7'ye izin verdi, 2 harcandi)
Kitap bastan okunmaz; yalniz gereken yerlere dokunulur.

ADIMLAR
    taban   Model YOK. Anlati cumlelerinde (diyalog ve ic ses haric) donem
            karsiligi olan cagdas sozcuk: durum->vaziyet, bilgi->malumat,
            ayrinti->teferruat, sorusturma->tahkikat, onem->ehemmiyet
            (lint-kurallari.yml > donem_uyumu > ozdes). Ek uyumu betikle
            cevrilir (durumda -> vaziyette, bilgiyi -> malumati). Bolum basina
            4-6 aday, bolume yayilmis; bolumu 34-61 duzeyine (--hedef)
            tasimaya yetecek kadar. Varsayilan bolumler: 23-33, 62-72.
    doruk   Sablonun "Gotik sozcuk tahsisi" bolumundeki doruk ¶ araliklari
            (yalniz harcama izni verilenler; 'ac', 'sade' denenler degil).
            Yalniz o gruplar ZH+TR, butceyle Claude'a gider (bir bolum
            ~3-5k token): doruk basina 1-3 sozcuk onerir. Sablonu olan ve
            tahsis bolumu bulunan bolumler (fiilen 33'ten itibaren).
    inceleme  Ikisi sonra'nin inceleme bicimine: [ ] kabul [ ] ret [ ] hep.
    --kararlar  Isaretlenenler birebir eslesmeyle uygulanir (sayi 1 olmali),
            once yedek: yedek/<tarih>/ses_ayari-<saat>/; 'hep' karar defterine.

Ciktilar Reports/ses_ayari/Ch_N/ altinda. inceleme.md bir kez yazilir;
isaretlerinizi korumak icin yeniden yazmaz (--yeniden ile yazar).

Kullanim:
    ses_ayari.py 23-33,62-72                taban adaylari + doruk girdileri, inceleme
    ses_ayari.py 33-72 --otomatik           doruk gecisini claude -p ile de yurut
    ses_ayari.py 62-72 --yalniz taban       yalniz bir adim
    ses_ayari.py 62-72 --kararlar [--kuru]  isaretlileri uygula
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIKLER))
sys.path.insert(0, str(BETIKLER / "harita"))

import donem_denetle as D  # noqa: E402
import sonra as S  # noqa: E402
from turkce import tr_desen  # noqa: E402

KOK = S.KOK
RAPOR = Path(os.environ.get("LOTM_SES_RAPOR") or BETIKLER / "Reports" / "ses_ayari")
YEDEK = Path(os.environ.get("LOTM_YEDEK") or KOK / "yedek")
ISTEM = S.ISTEMLER / "lotm_ses_ayari_doruk.md"
TABAN_VARSAYILAN = "23-33,62-72"
HEDEF = 4.7   # 34-61 donem ortalamasi (/1000), 3 Kas olcumu
EN_AZ, EN_COK = 4, 6
SESLI = "aeıioöuüâîû"
INCE = set("eiöüîê")
YUVARLAK = set("ouöü")
SERT = set("fstkçşhp")
YALIN = {"yaklaşık"}


# ------------------------------------------------------------------ ek uyumu

def son_sesli(s: str) -> str:
    for c in reversed(s.lower()):
        if c in SESLI:
            return c
    return "a"


def ek_cevir(eski_kok: str, yeni_kok: str, ek: str) -> str | None:
    """'durum'+'da' -> 'te' (vaziyet+te). Cevrilemeyen (fiil yapan) ek: None.

    Yalniz isim ekleri: cogul, iyelik, hal, ek-fiil, -ki, -ken, -li, -siz.
    Eski kok sesliyle bitip yeni kok unsuzle bitiyorsa kaynastirma harfi duser
    (bilgi-si -> malumat-i, bilgi-yle -> malumat-la, bilgi-nin -> malumat-in).
    """
    if not ek:
        return ""
    if eski_kok in YALIN:  # zarf: ek almaz ("yaklasik" -> "takriben")
        return None
    if re.match(r"l[ae][nşt]|s[ae]|s[ae]l|c[ıiuü]|ş", ek):  # bilgilendir, onemse-, durumsal, bilgici
        return None
    if eski_kok[-1] in SESLI and yeni_kok[-1] not in SESLI:
        if ek[0] == "y":
            ek = ek[1:]
        elif ek[0] in "ns" and len(ek) > 1 and ek[1] in SESLI and not re.match(r"s[ıiuü]z", ek):
            ek = ek[1:]
        if not ek:
            return ""
    # Degismez parcalar: sondaki -ki ve -ken.
    kuyruk = ""
    m = re.search(r"(ki|ken)$", ek)
    if m and len(ek) > len(m.group(1)):
        ek, kuyruk = ek[:m.start()], m.group(1)
    out, onceki_s, onceki_c = [], son_sesli(yeni_kok), yeni_kok[-1]
    for c in ek:
        if c in "ae":
            c = "e" if onceki_s in INCE else "a"
        elif c in "ıiuü":
            ince, yuv = onceki_s in INCE, onceki_s in YUVARLAK
            c = {(True, True): "ü", (True, False): "i", (False, True): "u", (False, False): "ı"}[(ince, yuv)]
        elif c in "dt" and onceki_c not in SESLI:  # eksik-ti -> noksan-di, durum-da -> vaziyet-te
            c = "t" if onceki_c in SERT else "d"
        elif c in "cç" and onceki_c not in SESLI:
            c = "ç" if onceki_c in SERT else "c"
        if c in SESLI:
            onceki_s = c
        onceki_c = c
        out.append(c)
    return "".join(out) + kuyruk


def buyuk_bas(s: str) -> str:
    return ("İ" if s[0] == "i" else s[0].upper()) + s[1:]


# ------------------------------------------------------------------ taban

TIRNAK = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”|‘[^’\n]*’|«[^»\n]*»")


def anlati_maskesi(blok: str) -> str:
    """Diyalog (tirnak ici) ve ic ses (_italik_) bosluga cevrilir; konumlar korunur."""
    for d in (TIRNAK, D.IC_SES):
        blok = d.sub(lambda m: " " * len(m.group()), blok)
    return blok


def taban_adaylari(metin: str, kural: dict, donmus: list, sablon: str = "") -> list:
    """Her anlati eslesmesi: {"p", "eski", "yeni", "cagdas", "donem"} (cumle duzeyinde)."""
    out = []
    for p, blok in enumerate(D.bloklar(metin), 1):
        mask = anlati_maskesi(blok)
        for cagdas, donem in kural["ozdes"].items():
            d = re.compile(rf"(?<![{D.HARF}])(?!(?:{'|'.join(tr_desen(x) for x in kural['ozdes_istisna']) or '_'}))"
                           rf"({tr_desen(cagdas)})([{D.HARF}]*)")
            for m in d.finditer(mask):
                ek = ek_cevir(cagdas, donem, m.group(2).lower())
                if ek is None:
                    continue
                cumle = D.cumle(blok, m.start(), m.end()).lstrip("_\"”’» ")
                if any(f in cumle or cumle in f for f in donmus) or (len(cumle) > 20 and cumle in sablon):
                    continue
                sozcuk = blok[m.start():m.end()]
                yeni_s = donem + ek
                if sozcuk[0].isupper():
                    yeni_s = buyuk_bas(yeni_s)
                yeni = cumle.replace(sozcuk, yeni_s, 1)
                if cumle.count(sozcuk) != 1 or metin.count(cumle) != 1:
                    continue  # birebir eslesme kurali: tek gecmeli
                out.append({"p": p, "eski": cumle, "yeni": yeni, "cagdas": cagdas, "donem": donem,
                            "sozcuk": sozcuk, "yeni_sozcuk": yeni_s})
    return out


def taban_sec(adaylar: list, gerekli: int, blok_sayisi: int) -> list:
    """Bolume yayilmis 'gerekli' kadar aday: hedef ¶'lere en yakin, ayni cumle
    bir kez, ayni donem sozcugu en cok iki kez."""
    if gerekli <= 0 or not adaylar:
        return []
    secilen, kullanim = [], {}
    hedefler = [blok_sayisi * (i + 0.5) / gerekli for i in range(gerekli)]
    kalan = list(adaylar)
    for h in hedefler:
        kalan.sort(key=lambda a: abs(a["p"] - h))
        for a in kalan:
            if kullanim.get(a["donem"], 0) >= 2 or any(a["eski"] == s["eski"] for s in secilen):
                continue
            if any(abs(a["p"] - s["p"]) < 2 for s in secilen):
                continue
            secilen.append(a)
            kullanim[a["donem"]] = kullanim.get(a["donem"], 0) + 1
            kalan.remove(a)
            break
    return sorted(secilen, key=lambda a: a["p"])


def taban(no: int, metin: str, sablon: str, hedef: float) -> tuple:
    """(secilen maddeler, not)."""
    kural = D.kurallar()
    y = D.yogunluk(metin)
    donem = y.get("donem", 0.0)
    sozcuk = len(D.IC_SES.sub(" ", "\n".join(D.bloklar(metin))).split())
    if donem >= hedef:
        return [], f"dönem {donem}/1000 ≥ hedef {hedef}: taban adayı yok"
    gerekli = min(EN_COK, max(EN_AZ, math.ceil((hedef - donem) * sozcuk / 1000)))
    adaylar = taban_adaylari(metin, kural, D.donmus_satirlar(), sablon)
    secilen = taban_sec(adaylar, gerekli, len(D.bloklar(metin)))
    sonra_d = donem + len(secilen) * 1000 / max(sozcuk, 1)
    return secilen, (f"dönem {donem} → ~{sonra_d:.1f}/1000 (hedef {hedef}); "
                     f"{len(adaylar)} anlatı adayı, {len(secilen)} seçildi")


# ------------------------------------------------------------------ doruk

RAKAM = {"bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8}
ARALIK = re.compile(r"¶\s?(\d+)(?:\s*[–-]\s*¶?\s?(\d+))?")
# Sablon dili serbest; cumle duzeyinde siniflanir. Olumsuz her zaman kazanir.
OLUMLU = re.compile(r"en (?:çok|fazla)|tavan|harca|bütçe|doruk|tepe|zirve|gotik kayıt|gotik bölge|almalı|"
                    r"yakışır|izinli|açık bölge|eşik|yükselti|sıçrama", re.I)
OLUMSUZ = re.compile(r"(?<![\wçğıöşü])aç(?![\wçğıöşü])|sade|orta kayıt|harcanmaz|sıfır|değil|almaz|girmez|"
                     r"yasak|yükseltilmez|düz kal|duygusal|hiç|toplam", re.I)
_R = "|".join(RAKAM)
BUTCE = re.compile(rf"en (?:çok|fazla) (bir iki|\d+|{_R})|({_R}) ila ({_R})|(tek) bir (?:gotik|sözcük|sıfat|imge|sıçrama|"
                   rf"yükselt)|(bir) sıfat yeter", re.I)
KONU = re.compile(r"gotik|harca|aç|tepe|doruk|zirve|koyu|bölge|tavan|eşik|sade|dönem|yer|¶", re.I)


def tahsis_bolumu(sablon: str) -> str:
    """Sablonun 'Gotik sozcuk tahsisi' kismi: basliktan bir sonraki konu basligina
    (gotik/doruk/bolge sozu gecmeyen kalin etiketli satir ya da # baslik)."""
    m = re.search(r"Gotik sözcük tahsisi", sablon)
    if not m:
        return ""
    bas = sablon.rfind("\n", 0, m.start()) + 1
    satirlar = sablon[bas:].splitlines()
    out = [satirlar[0]]
    for s in satirlar[1:]:
        if re.match(r"^#", s):
            break
        etiket = re.match(r"^\s{0,1}(?:- )?\*\*([^*]+)\*\*", s)
        if etiket and not KONU.search(etiket.group(1)):
            break
        out.append(s)
        if sum(len(x) for x in out) > 3000:
            break
    return "\n".join(out).strip()


def _butce(c: str) -> int | None:
    m = BUTCE.search(c)
    if not m:
        return None
    sayi = [2 if x.lower() == "bir iki" else 1 if x.lower() == "tek" else int(x) if x.isdigit()
            else RAKAM.get(x.lower(), 0) for x in m.groups() if x]
    return max(sayi) if sayi else None


def doruklar(tahsis: str) -> list:
    """[{"bas", "son", "butce", "cumle"}]: harcama izni verilen araliklar.

    Cumle araligi ve olumlu bir soz tasiyorsa doruktur; yalniz aralik tasiyorsa
    bekler, ardindan gelen araliksiz olumlu cumle ("burada en fazla bir")
    onu doruk yapar. Baska bir dorugun icindeki aralik ayri sayilmaz, butcesi
    (daha ozel oldugu icin) dis doruga gecer."""
    adaylar, bekleyen, son = [], [], []
    for c in re.split(r"(?<=[.;])\s+|\n", tahsis.replace("**", "")):
        c = c.strip(" -")
        if not c:
            continue
        araliklar = [(int(a), int(b or a)) for a, b in ARALIK.findall(c)]
        butce, olumsuz, olumlu = _butce(c), OLUMSUZ.search(c), OLUMLU.search(c)
        if not araliklar:
            if olumlu and not olumsuz:
                hedef = bekleyen or son
                for d in hedef:
                    d["butce"] = butce or d["butce"]
                    if d not in adaylar:
                        adaylar.append(d)
            bekleyen, son = [], son if not olumsuz else []
            continue
        yeni = [{"bas": a, "son": b, "butce": butce or 3, "cumle": re.sub(r"\s+", " ", c)}
                for a, b in araliklar if a <= b <= a + 30]
        if olumsuz:
            bekleyen, son = [], []
        elif olumlu:
            adaylar += yeni
            bekleyen, son = [], yeni
        else:
            bekleyen, son = yeni, []
    out = []
    for d in sorted(adaylar, key=lambda d: (d["bas"], -(d["son"] - d["bas"]))):
        dis = next((o for o in out if o["bas"] <= d["bas"] and d["son"] <= o["son"]), None)
        if dis:
            dis["butce"] = min(dis["butce"], d["butce"])
            continue
        out.append(d)
    return out


def gotik_say(metin: str) -> list:
    """Bir parcadaki gotik sozcukler (lint register sayaci, sapkasiz)."""
    try:
        import yaml
        import sozluk_lint as L
        kur = (yaml.safe_load(D.KURALLAR.read_text(encoding="utf-8")) or {}).get("register") or {}
        desen = L.register_deseni(kur.get("gotik", "").split(), kur.get("istisna", "").split())
        return desen.findall(L.diyakritiksiz(L.tr_kucult(metin)))
    except Exception:
        return []


def cekirdek_parcasi() -> str:
    """Cekirdek istemin §1.1-1.3 ve §4.1'i (en yeni surum)."""
    yollar = sorted(S.ISTEMLER.glob("lotm_system_prompt_v[0-9]*.md"),
                    key=lambda p: [int(x) for x in re.findall(r"\d+", p.stem)])
    yollar = [p for p in yollar if re.fullmatch(r"lotm_system_prompt_v[\d.]+", p.stem)]
    if not yollar:
        return ""
    t = yollar[-1].read_text(encoding="utf-8")
    out = []
    for bas, son in ((r"^### 1\.1 ", r"^---|^## 2\."), (r"^### 4\.1 ", r"^### 4\.2 ")):
        m = re.search(bas, t, re.M)
        if m:
            n = re.search(son, t[m.end():], re.M)
            out.append(t[m.start():m.end() + (n.start() if n else 3000)].strip())
    return f"<cekirdek kaynak=\"{yollar[-1].name}\">\n" + "\n\n".join(out) + "\n</cekirdek>"


def doruk_girdisi(no: int, sablon: str) -> tuple:
    """(girdi metni ya da None, not)."""
    tahsis = tahsis_bolumu(sablon)
    if not tahsis:
        return None, "şablonda gotik tahsis bölümü yok"
    dl = doruklar(tahsis)
    if not dl:
        return None, "şablon doruk tahsis etmiyor (bölüm aç)"
    from gruplar import gruplar as _gruplar
    g = _gruplar(no, "tr")
    if not g:
        return None, "hizalama kurulamadı (ZH ya da TR yok)"
    parcalar, harcanabilir = [], 0
    for i, d in enumerate(dl, 1):
        nolar = [k for k in range(d["bas"], d["son"] + 1) if k in g]
        if not nolar:
            continue
        tr = " ".join(g[k]["TR"] for k in nolar)
        harcanan = gotik_say(tr)
        kalan = max(0, d["butce"] - len(harcanan))
        harcanabilir += kalan
        parcalar.append(
            f"<doruk no=\"{i}\" aralik=\"¶{d['bas']}–¶{d['son']}\" butce=\"{d['butce']}\" "
            f"harcanan=\"{len(harcanan)}\" kalan=\"{kalan}\">\n"
            f"Şablon: {d['cumle']}\n"
            f"Harcanmış gotik sözcükler (betik sayacı): {', '.join(harcanan) or 'yok'}\n\n"
            + S.hizali_metin(g, nolar) + "\n</doruk>")
    if not parcalar:
        return None, "doruk ¶'leri hizalamada yok"
    if not harcanabilir:
        return None, f"{len(parcalar)} doruk, bütçe zaten harcanmış"
    metin = (f"{ISTEM.read_text(encoding='utf-8').rstrip()}\n\n---\n\n"
             f"{S.kararlar_blogu()}{cekirdek_parcasi()}\n\n"
             f"<gotik_tahsis bolum=\"{no}\">\n{tahsis}\n</gotik_tahsis>\n\n" + "\n\n".join(parcalar) + "\n")
    return metin, f"{len(parcalar)} doruk, harcanabilir {harcanabilir} sözcük"


def doruk_maddeleri(cikti: str, metin: str) -> tuple:
    """Model JSON'u -> inceleme maddeleri, bilgi. 'eski' bolumde tam bir kez gecmeli."""
    try:
        veri = S.json_ayikla(cikti)
    except (ValueError, KeyError) as e:
        return [], [{"p": None, "not": f"doruk çıktısı JSON değil ({e})"}]
    bloklar = D.bloklar(metin)
    maddeler, bilgi = [], []
    for d in veri.get("doruklar", []):
        if d.get("uyum") == "uyumsuz":
            bilgi.append({"p": None, "not": f"doruk {d.get('aralik')}: şablon aralığı metinle uyuşmuyor — "
                                            f"{d.get('not', '')}"})
        for o in d.get("oneriler", []):
            eski, yeni = o.get("eski") or "", o.get("yeni") or ""
            n = metin.count(eski) if eski else 0
            if n != 1 or eski == yeni:
                bilgi.append({"p": None, "not": f"doruk {d.get('aralik')}: öneri bölümde {n} kez geçiyor, "
                                                f"alınmadı: «{eski[:60]}» → «{yeni[:60]}»"})
                continue
            p = next((i for i, b in enumerate(bloklar, 1) if eski in b), None)
            maddeler.append({"p": p, "sinif": "KARAR", "kaynak": ["ses_ayari doruk"],
                             "kural": f"ses_ayari gotik doruk {d.get('aralik', '')}".strip(),
                             "eski": eski, "yeni": yeni, "neden": o.get("neden", "")})
    for b in veri.get("bilgi", []) or []:
        bilgi.append({"p": None, "not": b if isinstance(b, str) else json.dumps(b, ensure_ascii=False)})
    return maddeler, bilgi


# ------------------------------------------------------------------ bolum

def bolum_isle(no: int, a, otomatik: bool) -> str:
    dosya = S.BOLUMLER / f"{no:04d}.md"
    if not dosya.exists():
        return f"YOK: {dosya.name}"
    klasor = RAPOR / f"Ch_{no}"
    klasor.mkdir(parents=True, exist_ok=True)
    inceleme = klasor / "inceleme.md"
    if a.kararlar:
        return kararlari_isle(no, dosya, klasor, a.kuru)
    if (klasor / "uygulandi.json").exists():
        return "uygulanmış (uygulandi.json); yeniden kurmak için klasörü taşıyın"
    metin = dosya.read_text(encoding="utf-8")
    sablon_yol = S.SABLONLAR / f"Ch_{no}.md"
    sablon = sablon_yol.read_text(encoding="utf-8") if sablon_yol.exists() else ""
    notlar, maddeler, bilgi, bekliyor = [], [], [], False

    if "taban" in a.adimlar and no in a.taban_bolumleri:
        secilen, n = taban(no, metin, sablon, a.hedef)
        notlar.append(f"taban: {n}")
        for s in secilen:
            maddeler.append({"p": s["p"], "sinif": "KARAR", "kaynak": ["ses_ayari taban"],
                             "kural": f"ses_ayari dönem tabanı {s['cagdas']}→{s['donem']}",
                             "eski": s["eski"], "yeni": s["yeni"],
                             "neden": f"anlatı; «{s['sozcuk']}» → «{s['yeni_sozcuk']}» (betik, ek uyumu otomatik)"})
    if "doruk" in a.adimlar:
        girdi_metni, n = doruk_girdisi(no, sablon) if sablon else (None, "şablon yok")
        notlar.append(f"doruk: {n}")
        if girdi_metni:
            girdi, cikti = klasor / "doruk_girdi.md", klasor / "doruk_cikti.md"
            S.yaz_degisirse(girdi, girdi_metni)
            if otomatik and S.durum(girdi, cikti) != "TAMAM":
                S.yurut(girdi, cikti, a.model, a.sure)
            d = S.durum(girdi, cikti)
            notlar.append(f"doruk: {d} {girdi.name} -> {cikti.name}")
            if d == "TAMAM":
                m, b = doruk_maddeleri(cikti.read_text(encoding="utf-8"), metin)
                maddeler += m
                bilgi += b
            else:
                bekliyor = True

    durum_md = "\n".join([f"# {no}. bölüm — ses ayarı", ""] + [f"- {x}" for x in notlar]) + "\n"
    (klasor / "DURUM.md").write_text(durum_md, encoding="utf-8")
    if bekliyor:
        return "; ".join(notlar) + " — inceleme doruk çıktısını bekliyor"
    if inceleme.exists() and not a.yeniden:
        return "; ".join(notlar) + " — inceleme.md zaten var (işaretler korunur; --yeniden)"
    if not maddeler and not bilgi:
        return "; ".join(notlar) + " — öneri yok"
    maddeler.sort(key=lambda d: d.get("p") or 0)
    ic = S.inceleme_yaz(no, [], maddeler, bilgi, kuru=False)
    ic = (ic.replace(f"# {no}. bölüm — inceleme", f"# {no}. bölüm — ses ayarı incelemesi", 1)
            .replace(f"`./calistir.sh sonra {no} --kararlar`", f"`python3 ses_ayari.py {no} --kararlar`"))
    inceleme.write_text(ic, encoding="utf-8")
    return "; ".join(notlar) + f" — {len(maddeler)} madde -> {inceleme}"


def kararlari_isle(no: int, dosya: Path, klasor: Path, kuru: bool) -> str:
    inceleme = klasor / "inceleme.md"
    if not inceleme.exists():
        return "YOK: inceleme.md"
    if (klasor / "uygulandi.json").exists():
        return "zaten uygulanmış (uygulandi.json)"
    secimler = S.inceleme_oku(inceleme.read_text(encoding="utf-8"))
    asil = dosya.read_text(encoding="utf-8")
    metin, uygulanan, bulunamayan, defter = asil, [], [], []
    for s in secimler:
        if s["kabul"]:
            if metin.count(s["eski"]) == 1:
                metin = metin.replace(s["eski"], s["yeni"], 1)
                uygulanan.append(s["k"])
            else:
                bulunamayan.append(s["k"])
        if s["hep"] and (s["kabul"] or s["ret"]):
            defter.append(f"- {'kabul' if s['kabul'] else 'ret'} · {s['kural']} — örnek: "
                          f"«{S.tek_satir(s['eski'])}» → «{S.tek_satir(s['yeni'])}» ({no}. bölüm ¶{s['p']})")
    sonuc = (f"{len(uygulanan)} uygulandı, {len(defter)} kalıcı karar"
             + (f"; metinde bulunamayan: {', '.join('K%d' % k for k in bulunamayan)}" if bulunamayan else ""))
    if kuru:
        return "kuru: " + sonuc
    if uygulanan:
        yedek = YEDEK / time.strftime("%Y-%m-%d") / f"ses_ayari-{time.strftime('%H%M%S')}"
        yedek.mkdir(parents=True, exist_ok=True)
        (yedek / dosya.name).write_text(asil, encoding="utf-8")
        dosya.write_text(metin, encoding="utf-8")
        S.fark_yaz(asil, metin, klasor / "uygulanan.diff", dosya.name)
        sonuc += f"; yedek {yedek}"
    if defter:
        with S.KARARLAR.open("a", encoding="utf-8") as f:
            f.write("\n".join(defter) + "\n")
    (klasor / "uygulandi.json").write_text(json.dumps(
        {"zaman": time.strftime("%Y-%m-%d %H:%M"), "uygulanan": uygulanan}, ensure_ascii=False),
        encoding="utf-8")
    return sonuc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Eski bölümlerin sicil ayarı: dönem tabanı + gotik doruklar.")
    ap.add_argument("bolum", help="N, A-B ya da N,M (örnek: 23-33,62-72)")
    ap.add_argument("--yalniz", choices=("taban", "doruk"), help="yalnız bir adım")
    ap.add_argument("--taban-bolumleri", default=TABAN_VARSAYILAN,
                    help=f"taban adımının çalışacağı bölümler (varsayılan {TABAN_VARSAYILAN})")
    ap.add_argument("--hedef", type=float, default=HEDEF, help=f"dönem yoğunluğu hedefi (/1000, {HEDEF})")
    ap.add_argument("--otomatik", action="store_true", help="doruk geçişini claude -p ile yürüt")
    ap.add_argument("--kararlar", action="store_true", help="inceleme.md'de işaretlenenleri uygula")
    ap.add_argument("--kuru", action="store_true", help="--kararlar: bölüme ve deftere yazma")
    ap.add_argument("--yeniden", action="store_true", help="var olan inceleme.md'nin üzerine yaz")
    ap.add_argument("--model")
    ap.add_argument("--sure", type=int, default=900)
    a = ap.parse_args(argv)
    try:
        nolar = S.bolum_listesi(a.bolum)
        a.taban_bolumleri = set(S.bolum_listesi(a.taban_bolumleri))
    except ValueError as e:
        ap.error(str(e))
    a.adimlar = (a.yalniz,) if a.yalniz else ("taban", "doruk")
    ozet = []
    for no in nolar:
        try:
            s = bolum_isle(no, a, a.otomatik)
        except Exception as e:  # noqa: BLE001 -- bir bolum digerlerini durdurmasin
            s = f"HATA: {type(e).__name__}: {e}"
        print(f"{no:4}  {s}", flush=True)
        ozet.append(f"{no:4}  {s}")
    if len(nolar) > 1:
        RAPOR.mkdir(parents=True, exist_ok=True)
        (RAPOR / "OZET.md").write_text(f"# ses_ayari ({time.strftime('%Y-%m-%d %H:%M')})\n\n"
                                       + "\n".join(ozet) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
