#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ses_haritasi.py -- bir bolumu (ya da bir sahneyi) ilgilendiren ses haritasi
girislerini cikarir.

Haritalar butun halde ~860 KB (Side_Character_Maps 313 KB, Klein.md 89 KB);
ne sablon adimina ne sadakat gecisine tamami verilebilir. Bu betik:
  - karakteri metinde adiyla bulur (once: Ingilizce kaynak, sonra: Turkce
    bolum ya da partinin TR metni; sozlukte karakterlerin Cincesi yok),
  - o bolumun asamasini secer (basliktaki "Aşama 1 — Hoca (24–136)" satirlari;
    Klein icin Klein.md §3'teki A1–A6 araliklari),
  - Kapsam'i bu bolumu kapsayan girisleri alir (Kapsam'da bolum numarasi
    yoksa giris geneldir ve alinir).

Iki bicim:
  tam   (once.py -> Reports/once/Ch_N/ses_haritasi.md): Tarz, asama, girislerin
        Yap/Yapma/Ayar satirlari. Sablon adiminda kullanilir.
  kisa  (sonra.py sadakat partisi): yalniz asama satiri ve girislerin
        Yap/Yapma'si, karakter basina kirpilmis; Ses_Kararlari.md basa eklenir.
        Amac sadakatin yerellestirmeyi hata saymamasi, uslup denetimi degil.

Kullanim:
    ses_haritasi.py 74                 tam bicim, Ingilizce kaynaktan
    ses_haritasi.py 10 --tr --kisa     kisa bicim, yayimlanmis Turkce bolumden
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIKLER))
KOK = Path(os.environ.get("LOTM_KOK") or BETIKLER.parent)
HARITALAR = Path(os.environ.get("LOTM_HARITALAR") or KOK / "Tools" / "Voice_Maps")
YAN = HARITALAR / "Side_Character_Maps.md"
KLEIN = HARITALAR / "Klein.md"
KARARLAR = HARITALAR / "Ses_Kararlari.md"
# sablon oneri HARITA maddeleri (23 Kas): haritaya islenene kadar burada bekler
KUYRUK = HARITALAR / "Harita_Kuyrugu.md"
BOLUMLER = KOK / "Imperium34.github.io" / "_chapters"

ARALIK = re.compile(r"(\d{1,4})\s*[–-]\s*(\d{1,4})|(?<![\d.])(\d{1,4})(?![\d.]|\. Aşama)")
GENEL = re.compile(r"tüm|bütün|her aşama|tüm dönem", re.I)
KURAL_KODU = re.compile(r"(?<![\wÇĞİÖŞÜçğıöşü])[A-ZÇĞİÖŞÜ]{1,4}\d+(?:\.\d+)*(?![\w])")
# Ad aranirken atlanan basllik sozcukleri (toplu haritalar, unvanlar).
DURAK = {"Toplu", "Harita", "Ahalisi", "Üyeler", "The", "Old", "Bay", "Bayan", "Sihirli", "Ayna",
         "Gece", "Şahinleri", "Tingen", "Backlund", "Şubesi", "Destek", "Personeli", "Müfreze",
         "Eskortu", "Ebedî", "Tanrıçası", "Koramiral", "Ulu", "Rahibi", "Şehri", "Şehir", "Gümüş",
         "Kulübü", "Kehanet", "Çevresi", "Elçisi", "Reisi", "Tarikatı", "Yolcuları", "Melek",
         "Kader", "Yılanı", "Gizem", "Kraliçesi", "Asılmış", "Adam", "Güneş", "Hokkabaz", "Magician",
         "Moon", "Hermit", "Judgment", "Temperance", "Ay", "Keşiş", "Yargı", "İtidal", "Kibir",
         "Hikmet", "Gözü", "Adil", "Sır", "Hâdimi", "Hood", "Smith", "White", "Hall", "Wall",
         "Berg", "Wilson", "Lee", "Gustav", "Moretti", "Mitchell", "Simone", "Edwards", "Stanton"}


def araliklar(metin: str) -> list:
    out = []
    for m in ARALIK.finditer(metin):
        if m.group(1):
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b:
                out.append((a, b))
        else:
            n = int(m.group(3))
            out.append((n, n))
    return out


def kapsar(metin: str, no: int, asamalar: dict | None = None) -> bool | None:
    """Kapsam metni bu bolumu kapsiyor mu? Bolum bilgisi yoksa None (genel).
    Kural kodlari (M1, K2, T1.3) sayi sayilmaz; ilk bolumu (· oncesi) 'butun
    asamalar' gibi genel olan ve orada sayi tasimayan Kapsam geneldir: sonraki
    sayilar ornektir ('en saf hâli 1390'). 23 Kas: M1, M6, M9, K3.3, K5.2 bu
    yuzden 82'de dusuyordu."""
    metin = KURAL_KODU.sub("", re.sub(r"¶\d+", "", metin))
    ilk = metin.split("·")[0]
    if GENEL.search(ilk) and not araliklar(ilk) and not re.search(r"\d\.\s*(?:–\s*\d\.\s*)?Aşama", ilk):
        return None
    ar = araliklar(metin)
    for m in re.finditer(r"(\d)\.\s*(?:–\s*(\d)\.\s*)?Aşama", metin):
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        for k in range(a, b + 1):
            if asamalar and k in asamalar:
                ar.append(asamalar[k])
    if not ar:
        return None
    return any(a <= no <= b for a, b in ar)


# ------------------------------------------------------------------ ayristirma

def bolumle(metin: str, seviye: str) -> list:
    """'### ' (ya da verilen) basliklarla bol: [(baslik, govde)]."""
    parcalar = re.split(rf"^{seviye} ", metin, flags=re.M)
    return [(p.split("\n", 1)[0], p.split("\n", 1)[1] if "\n" in p else "") for p in parcalar[1:]]


def girisler(govde: str) -> list:
    """##### (ya da ####) girisleri: {"kod","baslik","kapsam","yap","yapma","ayar"}."""
    out = []
    for m in re.finditer(r"^#{4,5} ([^\n]+)\n(.*?)(?=^#{3,5} |\Z)", govde, re.M | re.S):
        bas, gov = m.group(1).strip(), m.group(2)

        def alan(ad):
            a = re.search(rf"^\*\*{ad}:\*\*\s*(.*)$", gov, re.M)
            return a.group(1).strip() if a else ""
        if not (alan("Yap") or alan("Kapsam")):
            continue
        kod = re.match(r"([A-ZÇĞİÖŞÜ]+\d[\w.]*|[A-Z]\d+(?:\.\d+)?)\s*[—-]", bas)
        out.append({"kod": kod.group(1) if kod else "", "baslik": bas.split("`")[0].strip(),
                    "kapsam": alan("Kapsam"), "yap": alan("Yap"), "yapma": alan("Yapma"),
                    "ayar": alan("Ayar")})
    return out


def anahtarlar(baslik: str) -> list:
    """Basliktan metinde aranacak adlar: tam ad, parantez/egik cizgi takma adlari,
    ve unvan olmayan buyuk harfli sozcukler (Dunn, Azik, Neil...)."""
    ad = baslik.split("`")[0].strip()
    if "Toplu Harita" in ad and ":" in ad:  # "Melissa'nin Arkadaslari: Selena..." -> yalniz uyeler
        ad = ad.split(":", 1)[1]
    # "(Audrey'nin köpeği)", "(Fors'un hocası)": iyelikli parantez tanimdir, ad degil.
    ad = re.sub(r"\([^)]*'(?:nin|nın|nun|nün|un|ün|in|ın)\b[^)]*\)", "", ad)
    parcalar = [p.strip(" \"'") for p in re.split(r"[()/:,]| ve | — ", ad) if p.strip(" \"'")]
    out = set()
    for p in parcalar:
        p = re.sub(r"'(?:nin|nın|un|ün|in|ın)\b.*", "", p).strip()
        if len(p) >= 4 and not re.search(r"\b(Toplu Harita|Günlükler)\b", p) and not re.search(r"\d", p):
            out.add(p)
        for s in p.split():
            s = s.strip("'\"")
            if len(s) >= 4 and s[0].isupper() and s not in DURAK and not re.search(r"\d", s):
                out.add(s)
    return sorted(out, key=len, reverse=True)


def gecis_sayisi(anahtar: list, metin: str) -> int:
    return max((len(re.findall(rf"(?<![\wÇĞİÖŞÜçğıöşü]){re.escape(a)}(?![a-zçğıöşü])", metin))
                for a in anahtar), default=0)


def yan_karakterler(no: int, metin: str, esik: int = 2) -> list:
    """[(baslik, sayi, tarz, asama satiri, uygun girisler)], en cok gecenden."""
    if not YAN.exists():
        return []
    out = []
    for baslik, gov in bolumle(YAN.read_text(encoding="utf-8"), "###"):
        n = gecis_sayisi(anahtarlar(baslik), metin)
        if n < esik:
            continue
        bas_gov = re.split(r"^#{4,5} ", gov, maxsplit=1, flags=re.M)[0]
        tarz = (re.search(r"^\*\*Tarz:\*\*\s*(.*)$", bas_gov, re.M) or [None, ""])[1]
        asama = [s.strip("- ").strip() for s in re.findall(r"^- \*\*Aşama.*$", bas_gov, re.M)
                 if kapsar(s.split("—", 1)[-1].split(":")[0], no)]
        uygun = [g for g in girisler(gov) if kapsar(g["kapsam"], no) is not False]
        out.append((baslik.split("`")[0].strip(), n, tarz, asama, uygun))
    return sorted(out, key=lambda x: -x[1])


def varsayilan_sicil() -> str:
    """Side_Character_Maps.md basindaki '**Varsayılan sicil:**' satiri (ilk '## ' bolumunden once)."""
    if not YAN.exists():
        return ""
    bas = re.split(r"^## ", YAN.read_text(encoding="utf-8"), maxsplit=1, flags=re.M)[0]
    m = re.search(r"^\*\*Varsayılan sicil:\*\*\s*(.+)$", bas, re.M)
    return m.group(1).strip() if m else ""


def modern_basliklar() -> set:
    """Basliginda `sicil: modern` etiketi olan karakterler: varsayilan sicil onlara gecmez."""
    if not YAN.exists():
        return set()
    return {b.split("`")[0].strip() for b, _ in bolumle(YAN.read_text(encoding="utf-8"), "###")
            if re.search(r"`[^`]*\bsicil:\s*modern\b", b)}


def klein_asamalari(metin: str) -> dict:
    """Klein.md §3: {1: (1, 25), 2: (26, 219), ...}."""
    out = {}
    for m in re.finditer(r"^#### A(\d) — .*\((\d+)–(\d+)\)", metin, re.M):
        out[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
    return out


MASKE_ANAHTAR = {"Soytarı": ["Soytarı"], "Dünya": ["Dünya Beyefendi", "The World"],
                 "Sherlock Moriarty": ["Sherlock"], "Gehrman Sparrow": ["Gehrman"],
                 "Dwayne Dantès": ["Dwayne", "Dantès", "Dantes"], "Merlin Hermes": ["Merlin"]}


def klein(no: int, metin: str) -> tuple:
    """(asama satiri, uygun girisler, maskeler [(ad, girisler)])."""
    if not KLEIN.exists():
        return "", [], []
    t = KLEIN.read_text(encoding="utf-8")
    asm = klein_asamalari(t)
    asama = next((m.group(0)[5:] for m in re.finditer(r"^#### A\d — .*$", t, re.M)
                  if kapsar(m.group(0), no)), "")
    maske_bas = t.find("### Klein'ın Maskeleri")
    govde = t[:maske_bas] if maske_bas != -1 else t
    uygun = []
    for baslik, gov in bolumle(govde, "###"):
        if "Açık Maddeler" in baslik:
            continue
        for g in girisler(gov):
            k = kapsar(g["kapsam"] + " " + g["baslik"], no, asm)
            if k is not False:
                uygun.append(g)
    maskeler = []
    if maske_bas != -1:
        for baslik, gov in bolumle(t[maske_bas:], "###"):
            ad = baslik.split("`")[0].strip()
            if ad in MASKE_ANAHTAR and gecis_sayisi(MASKE_ANAHTAR[ad], metin) >= 2:
                maskeler.append((ad, [g for g in girisler(gov) if kapsar(g["kapsam"], no, asm) is not False]))
    return asama, uygun, maskeler


# ------------------------------------------------------------------ bicimler

# Sadakat partisinde once bunlar: ses kararinin yanlis bulgu dogurdugu konular.
SADAKAT_ILGI = re.compile(r"sadakat|ünlem|hitap|küfür|küfre|argo|duraks|üç nokta|\"[^\"]{3,30}\"", re.I)


def kirp(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= n:
        return s
    i = s.rfind(". ", 0, n)
    return (s[:i + 1] if i > n // 2 else s[:n].rsplit(" ", 1)[0] + " …")


def kuyruk_girisleri(metin: str) -> list:
    """[(karakter, girisler metni)] -- Harita_Kuyrugu.md'de metinde gecen karakterler."""
    if not KUYRUK.exists():
        return []
    out = []
    for baslik, gov in bolumle(KUYRUK.read_text(encoding="utf-8"), "###"):
        ad = baslik.split("`")[0].strip()
        anahtar = anahtarlar(ad) or [ad]
        if gov.strip() and gecis_sayisi(anahtar, metin) >= 1:
            out.append((ad, gov.strip()))
    return out


def tam(no: int, metin: str) -> str:
    asama, kg, maskeler = klein(no, metin)
    out = [f"# {no}. bölüm — ses haritası özeti", "",
           "ses_haritasi.py: metinde geçen karakterler, bu bölümün aşaması ve Kapsam'ı bu bölümü "
           "kapsayan girişler. Tam gerekçe ve örnekler haritanın kendisinde.", ""]
    vs = varsayilan_sicil()
    if vs:
        out += ["## Varsayılan sicil (yan karakterler)", vs, ""]
    out += ["## Klein", f"**Aşama:** {asama or '?'}", ""]
    for g in kg:
        out += [f"- **{g['baslik']}** ({g['kapsam']})", f"  Yap: {g['yap']}"]
        out += [f"  Yapma: {g['yapma']}"] if g["yapma"] else []
        # 23 Kas: Klein'in Ayar ornekleri de (82'de Klein.md tam okununca kurallarin
        # uygulanmasini degistiren bunlardi); ~4–5 KB
        out += [f"  Ayar: {g['ayar']}"] if g["ayar"] else []
    for ad, gl in maskeler:
        out += ["", f"### Maske: {ad}"]
        for g in gl:
            out += [f"- **{g['baslik']}** ({g['kapsam']})", f"  Yap: {g['yap']}"]
            out += [f"  Yapma: {g['yapma']}"] if g["yapma"] else []
            out += [f"  Ayar: {g['ayar']}"] if g["ayar"] else []
    modern = modern_basliklar()
    for baslik, n, tarz, asm, gl in yan_karakterler(no, metin):
        out += ["", f"## {baslik} (×{n})", f"**Tarz:** {tarz}"]
        out += ["**Sicil:** modern (varsayılan sicil geçmez)"] if baslik in modern else []
        out += [f"**Aşama:** {a}" for a in asm]
        for g in gl:
            out += [f"- **{g['baslik']}** ({g['kapsam']})", f"  Yap: {g['yap']}"]
            out += [f"  Yapma: {g['yapma']}"] if g["yapma"] else []
            out += [f"  Ayar: {g['ayar']}"] if g["ayar"] else []
    kuyruk = kuyruk_girisleri(metin)
    if kuyruk:
        out += ["", "## Kuyruktaki harita notları (haritaya henüz işlenmedi; [N] = öneren bölüm)"]
        for ad, gov in kuyruk:
            out += ["", f"### {ad}", gov]
    return "\n".join(out).rstrip() + "\n"


def kisa(no: int, metin: str, sinir: int = 6000, kararlar: bool = True) -> str:
    """Sadakat partisi icin: sabit ses kararlari + partide konusan karakterler.
    'sinir' karakter (~1.5–2k token) asilirsa az gecen karakterler dusurulur."""
    parcalar = []
    if kararlar and KARARLAR.exists():
        parcalar.append(KARARLAR.read_text(encoding="utf-8").strip())
    vs = varsayilan_sicil()
    vs_blok = f"**Varsayılan sicil (yan karakterler):** {vs}" if vs else ""
    if vs_blok:
        parcalar.append(vs_blok)
    asama, kg, maskeler = klein(no, metin)
    k = [f"Klein — {asama}"] if asama else []
    # Sadakate yalniz yanlis bulgu doguran konular: kufur/argo takvimi, duraksama.
    k += [f"- {g['kod'] or g['baslik']}: {kirp(g['yap'], 220)}" for g in kg
          if re.search(r"küfür|küfre|argo|\blan\b|hassiktir|üç nokta|duraks|internet dil",
                       g["yap"] + g["yapma"] + g["baslik"], re.I)]
    for ad, gl in maskeler:
        k.append(f"Maske {ad}: " + " · ".join(kirp(g["yap"], 160) for g in gl[:3]))
    if k:
        parcalar.append("\n".join(k))
    # Varsayilan sicil butceden sayilmaz: eklenmesi karakter dusurmesin.
    kalan = sinir - sum(len(p) for p in parcalar) + len(vs_blok)
    modern = modern_basliklar()
    for baslik, n, tarz, asm, gl in yan_karakterler(no, metin, esik=1):
        bas = [f"{baslik} — " + (asm[0] if asm else kirp(tarz, 200))
               + (" [sicil: modern, varsayılan sicil geçmez]" if baslik in modern else "")]
        sirali = sorted(gl, key=lambda g: not SADAKAT_ILGI.search(g["yap"] + g["baslik"]))
        satirlar = [f"- {g['kod']}: {kirp(g['yap'], 200)}" + (f" Yapma: {kirp(g['yapma'], 120)}" if g["yapma"] else "")
                    for g in sirali[:4]]
        # Sigmazsa karakteri dusurmek yerine once giris sayisini azalt (4 -> 2 -> 1).
        for k in (4, 2, 1):
            metin_blok = "\n".join(bas + satirlar[:k])
            if len(metin_blok) <= kalan:
                break
        else:
            continue
        parcalar.append(metin_blok)
        kalan -= len(metin_blok)
    return "\n\n".join(parcalar)


def kaynak_metni(no: int, tr: bool) -> str:
    if tr:
        yol = BOLUMLER / f"{no:04d}.md"
        return yol.read_text(encoding="utf-8") if yol.exists() else ""
    import lotm
    b = lotm.bolum_sozlugu(lotm.bolumler_en()).get(no)
    return b.metin if b else ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bölümü ilgilendiren ses haritası girişleri.")
    ap.add_argument("no", type=int)
    ap.add_argument("--tr", action="store_true", help="karakterleri yayımlanmış Türkçe bölümde ara")
    ap.add_argument("--kisa", action="store_true", help="sadakat için kısa biçim")
    a = ap.parse_args(argv)
    metin = kaynak_metni(a.no, a.tr)
    if not metin:
        print(f"YOK: {a.no}. bölümün {'Türkçesi' if a.tr else 'İngilizcesi'}")
        return 1
    print(kisa(a.no, metin) if a.kisa else tam(a.no, metin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
