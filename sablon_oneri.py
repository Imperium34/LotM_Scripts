#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sablon_oneri.py -- sablon sohbetinin onerilerini (F / G / H) isler.

    sablon.py N oneriler    sohbet.md -> Reports/sablon/Ch_N/oneriler.md
    sablon.py N incele      oneriler.md'yi inceleme sayfasinda acar (k / r / e)
    sablon.py N --kararlar  kabul edilenleri uygular

Maddeler (inceleme_sunucu'nun ### K<n> bicimi; ¶ alani '-'):
    EKLE      F satiri, words.md'de basligin sonuna eklenir
    DEGISTIR  F satiri, words.md'deki ✗ satirinin yerine (tam eslesme, count == 1)
    AD        H secenegi (F satiri bicimi); ayni adin iki secenegi birden kabul edilemez
    YANKI     G girisi -> Echo_Notes.md, siradaki numarayla; Donmus'taki her
              tirnakli dize yayimlanmis metinde aynen gecmeli.

Hicbiri bolum yayimlanip 'sonra N --kararlar' islenmeden yazilmaz (21 Kas,
kullanici: sablonda ya da ceviride degisen karsilik iki dosyada duzeltilmesin).
EKLE/DEGISTIR/AD satirinin Turkcesi de yayimlanmis metinde aranir; yoksa madde
uygulanmaz ve ✓ bir kez, oneriler.md'de duzeltilir. oneriler.md kurulurken
sablonun bugunku A karsiligi farkliysa 'Dikkat: sablonda simdi' yazilir.
    BILGI     kod blogu disindaki notlar (celiski, kusur raporu): yalniz okunur.

Degistirme isareti modelden modele degisir: satir sonunda '← DEĞİŞTİRME: neden',
'← replacement', ya da kategori basliginda '←' (altindaki her satir degistirme).
Ayristirici '←'ya bakar; istem tek bicimi ister (sablon.istem_kur).

Uygulananlar oneriler_uygulandi.json'a yazilir (ayni madde iki kez uygulanmaz).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIKLER))

import lotm  # noqa: E402

KOK = BETIKLER.parent
KELIMELER = KOK / "Tools" / "words.md"
YANKI = KOK / "Tools" / "Voice_Maps" / "Echo_Notes.md"
BOLUMLER = KOK / "Imperium34.github.io" / "_chapters"
SONRA = BETIKLER / "Reports" / "sonra"
ISARET = "oneriler_uygulandi.json"
KUTULAR = "[ ] kabul   [ ] ret   [ ] hep"

F_SATIRI = re.compile(r"^- \*\*(.+?)\*\* — (.+?) \(([^)]*)\)")
OK = re.compile(r"\s*←\s*(?:(?:DEĞİŞTİR\w*|değiştir\w*|replacement|REPLACEMENT)\s*:?\s*)?(.*)$")


def tek(s: str) -> str:
    return s.replace("\n", " ⏎ ")


def coz(s: str) -> str:
    return s.replace(" ⏎ ", "\n")


def bolumler(sohbet: str) -> dict:
    """sablon.BASLIKLAR'a gore: {'F': metin, 'G': ..., 'H': ...}."""
    import sablon as SB
    adlar = dict(zip(SB.BASLIKLAR, ["makbuz", "F", "G", "H", "bosluk"]))
    out, ad = {}, None
    for s in sohbet.splitlines():
        if s.strip() in adlar:
            ad = adlar[s.strip()]
            out[ad] = []
        elif ad:
            out[ad].append(s)
    return {k: "\n".join(v) for k, v in out.items()}


def kod_ve_not(metin: str) -> tuple:
    """(kod bloklarinin satirlari, blok disindaki madde/paragraflar)."""
    kod, disari, ic = [], [], False
    for s in metin.splitlines():
        if s.strip().startswith("```"):
            ic = not ic
            continue
        (kod if ic else disari).append(s)
    notlar, atla = [], False
    for s in disari:
        if re.match(r"\*\*Terfi edilmeyecekler", s.strip(), re.I):
            atla = True
            continue
        if s.strip().startswith("**") and s.strip().endswith(("**", ":**")) and not s.startswith("- "):
            atla = False
            notlar.append(s.strip())
            continue
        if atla or not s.strip() or s.strip().lower() == "yok":
            continue
        if s.startswith("- ") or not notlar:
            notlar.append(s.strip())
        else:
            notlar[-1] += " " + s.strip()
    return kod, notlar


def baslik_adi(s: str) -> str:
    return re.sub(r"^#+\s*", "", OK.sub("", s)).strip()


def f_satirlari(kod: list) -> list:
    """[(baslik, satir, degistirme_mi, neden)]."""
    out, baslik, bas_degis = [], "", False
    for s in kod:
        if re.match(r"^#+ ", s):
            baslik, bas_degis = baslik_adi(s), "←" in s
            continue
        if not s.startswith("- "):
            if out and s.strip() and not s.startswith("#"):
                b, sat, d, n = out[-1]
                out[-1] = (b, sat + " " + s.strip(), d, n)
            continue
        neden = ""
        degis = bas_degis
        if "←" in s:
            degis = True
            neden = OK.search(s).group(1).strip()
            s = s[: s.index("←")].rstrip()
        out.append((baslik, s.rstrip(), degis, neden))
    return out


def anahtarlar(satir: str) -> set:
    m = F_SATIRI.match(satir)
    if not m:
        return set()
    return {k.strip() for k in re.split(r"[/、,]", m.group(3)) if k.strip()}


def kalin(satir: str) -> str:
    m = re.match(r"^- \*\*(.+?)\*\*", satir)
    return m.group(1).strip() if m else ""


def ingilizce(satir: str) -> str:
    m = F_SATIRI.match(satir)
    return m.group(2).strip().lower() if m else ""


def kelime_basliklari(kelimeler: str) -> set:
    return {baslik_adi(s) for s in kelimeler.splitlines() if re.match(r"^#+ ", s)}


def eski_bul(yeni: str, kelimeler: str) -> tuple:
    """(eski satir ya da None, aciklama). Sirayla: ayni kalin Turkce, ortak
    Cince anahtar, ayni Ingilizce; ilk tek eslesen asama kazanir."""
    satirlar = [s for s in kelimeler.splitlines() if s.startswith("- **")]
    asamalar = [
        ("aynı Türkçe", [s for s in satirlar if kalin(s) and kalin(s) == kalin(yeni)]),
        ("ortak Çince anahtar", [s for s in satirlar if anahtarlar(s) & anahtarlar(yeni)]),
        ("aynı İngilizce", [s for s in satirlar if ingilizce(s) and ingilizce(s) == ingilizce(yeni)]),
    ]
    for ad, es in asamalar:
        if len(es) == 1:
            return es[0], ad
        if len(es) > 1:
            return None, f"{ad}: {len(es)} satır eşleşiyor, hangisi belirsiz"
    return None, "words.md'de eşleşen satır yok"


def g_girisleri(kod: list) -> list:
    """[(baslik, blok metni)] -- '### # · <baslik>' ile baslayan bloklar."""
    out = []
    for s in kod:
        if s.startswith("### "):
            out.append([s.rstrip()])
        elif out:
            out[-1].append(s.rstrip())
    girisler = []
    for b in out:
        while b and not b[-1].strip():
            b.pop()
        baslik = re.sub(r"^### #?\d*\s*·\s*", "", b[0]).strip()
        girisler.append((baslik, "\n".join(b)))
    return girisler


def h_secenekleri(metin: str) -> list:
    """H: her ad icin kod blogunda '## <baslik>' + iki F satiri (ilki sablonun varsayilani)."""
    kod, _ = kod_ve_not(metin)
    return f_satirlari(kod)


def madde(k: int, sinif: str, kural: str, eski: str, yeni: str, neden: str = "",
          kaynak: str = "", dikkat: list | None = None) -> str:
    s = [f"### K{k} · ¶- · {sinif} · {kural}", KUTULAR, f"✗ {tek(eski)}", f"✓ {tek(yeni)}"]
    if neden:
        s.append(f"Neden: {neden}")
    if kaynak:
        s.append(f"Kaynak: {kaynak}")
    s += [f"Dikkat: {d}" for d in (dikkat or [])]
    return "\n".join(s)


def oneriler_kur(no: int, sohbet: str, kelimeler: str, yanki: str,
                 sablon: str = "", zh_tsv: str = "", bolum: str = "") -> str:
    """bolum: yayimlanmis metin (varsa); F/H satirlarinin Turkcesi orada aranir."""
    b = bolumler(sohbet)

    def baglam(satir: str) -> list:
        d = []
        sk = sablon_karsiligi(satir, sablon, zh_tsv)
        if sk and kucuk(sk.rstrip("-")) not in kucuk(kalin(satir)):
            d.append(f"şablonda şimdi: '{sk}'")
        if bolum and not metinde_mi(satir, bolum):
            d.append(f"'{kalin(satir)}' yayımlanmış {no}'da geçmiyor: ✓'yi metne göre düzeltin")
        return d
    basliklar = kelime_basliklari(kelimeler)
    yanki_basliklari = {re.sub(r"^### #\d+\s*·\s*", "", s).strip().lower()
                        for s in yanki.splitlines() if re.match(r"^### #\d+", s)}
    k = 0
    katmanlar = []

    # 1. words.md (F)
    kod, f_notlar = kod_ve_not(b.get("F", ""))
    bloklar = []
    for baslik, satir, degis, neden in f_satirlari(kod):
        k += 1
        dikkat = baglam(satir)
        if not F_SATIRI.match(satir):
            dikkat.append("satır '- **Türkçe** — English (中文); not _N_' biçiminde değil")
        if baslik not in basliklar:
            dikkat.append(f"words.md'de '{baslik}' başlığı yok: uygulanmaz, ✓'yi düzenleyin ya da başlığı açın")
        if degis:
            eski, acik = eski_bul(satir, kelimeler)
            if eski is None:
                dikkat.append(f"değiştirilecek satır bulunamadı ({acik}): uygulanmaz")
            bloklar.append(madde(k, "DEGISTIR", baslik, eski or "(eşleşme yok)", satir,
                                 neden or "değiştirme", "sohbet.md F", dikkat))
        else:
            eski, acik = eski_bul(satir, kelimeler)
            if eski is not None or "belirsiz" in acik:
                dikkat.append(f"words.md'de zaten var ({acik}): {eski or ''}".rstrip(": "))
            bloklar.append(madde(k, "EKLE", baslik, "(yeni satır)", satir, "", "sohbet.md F", dikkat))
    katmanlar.append(("1. words.md (F)", bloklar))

    # 2. Ad kararlari (H)
    bloklar = []
    for baslik, satir, _, _ in h_secenekleri(b.get("H", "")):
        k += 1
        dikkat = baglam(satir) + ([] if baslik in basliklar else [f"words.md'de '{baslik}' başlığı yok"])
        bloklar.append(madde(k, "AD", baslik, "(yeni satır)", satir,
                             "aynı adın tek seçeneğini kabul edin", "sohbet.md H", dikkat))
    katmanlar.append(("2. Ad kararları (H)", bloklar))

    # 3. Yanki defteri (G)
    kod, g_notlar = kod_ve_not(b.get("G", ""))
    bloklar = []
    for baslik, blok in g_girisleri(kod):
        k += 1
        dikkat = ["Echo_Notes'ta aynı başlık var"] if baslik.lower() in yanki_basliklari else []
        bloklar.append(madde(k, "YANKI", baslik, "(yeni giriş)", blok,
                             "Donmuş dizeler yayımlanmış metinde aranarak eklenir",
                             "sohbet.md G", dikkat))
    katmanlar.append(("3. Yankı defteri (G)", bloklar))

    # 4. Notlar
    bloklar = []
    for kaynak, notlar in (("F", f_notlar), ("G", g_notlar)):
        for n in notlar:
            if n.startswith("**") and n.rstrip().endswith(("**", ":**")):
                continue  # ara baslik
            k += 1
            bloklar.append(madde(k, "BILGI", f"sohbet.md {kaynak}", "", n, "yalnız okunur; kabul = okundu",
                                 f"sohbet.md {kaynak}"))
    katmanlar.append(("4. Notlar", bloklar))

    ust = [f"# {no}. bölüm — şablon önerileri", "",
           f"Kaynak: `Reports/sablon/Ch_{no}/sohbet.md`. ✓ satırı düzenlenebilir (e).",
           f"Uygula: `./calistir.sh sablon {no} --kararlar` (sayfada A). Hepsi bölüm yayımlanıp "
           f"`sonra {no} --kararlar` işlendikten sonra yazılır; words.md satırının Türkçesi ve Yankı "
           f"girişinin Donmuş dizeleri yayımlanmış metinde aranır, yoksa madde bekler. Şablonda ya da "
           f"bölümde bir karşılığı değiştirdiyseniz ✓'yi burada bir kez düzeltin (e).", ""]
    for ad, bl in katmanlar:
        ust += [f"## {ad} ({len(bl)})", ""] + [x for b_ in bl for x in (b_, "")]
    return "\n".join(ust).rstrip() + "\n"


# ------------------------------------------------------------------ bolume karsi

def kucuk(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower().replace("’", "'")


def metinde_mi(satir: str, bolum: str) -> bool:
    """F satirinin Turkcesi (kalin kisim, ' / ' secenekleri) yayimlanmis bolumde
    geciyor mu? Ekler icin son sozcugun son iki harfi esnek ('cagir-' govdedir),
    sozler arasinda iki sozcuge kadar ara olabilir."""
    tr = kalin(satir)
    if not tr:
        return True
    metin = kucuk(bolum)
    for secenek in [x.strip() for x in tr.split(" / ") if x.strip()]:
        sozler = kucuk(secenek).rstrip(".").split()
        if not sozler:
            continue
        son = sozler[-1].rstrip("-")
        sozler[-1] = son[: max(3, len(son) - 2)] if len(son) > 4 else son
        # 'kalemle, fincanla cin cagirmiyorsunuz': sozler arasinda iki sozcuge kadar ara
        desen = r"\W+(?:\w+\W+){0,2}".join(re.escape(w) for w in sozler)
        if re.search(desen, metin):
            return True
    return False


def sablon_karsiligi(satir: str, sablon: str, zh_tsv: str) -> str:
    """Satirin Cince anahtarlarina sablonun A.1/A.2'sinde dusen Turkce hucre ('' yoksa)."""
    keys = anahtarlar(satir)
    if not keys or not sablon:
        return ""
    ingler = [s.split("\t")[0].strip() for s in zh_tsv.splitlines()
              if "\t" in s and not s.startswith("#") and keys & set(s.split("\t")[1].strip().split("/"))]
    for r in sablon.splitlines():
        h = [c.strip() for c in r.strip().strip("|").split("|")]
        if r.startswith("|") and len(h) >= 2 and any(i and i in h[0] for i in ingler):
            return h[1]
    return ""


def bolum_durumu(no: int) -> tuple:
    """(yayimlanip sonra kararlari islendi mi, bolum metni)."""
    yol = BOLUMLER / f"{no:04d}.md"
    hazir = yol.exists() and (SONRA / f"Ch_{no}" / "5_kararlar.json").exists()
    return hazir, (yol.read_text(encoding="utf-8") if yol.exists() else "")


# ------------------------------------------------------------------ uygulama

def maddeleri_oku(metin: str) -> list:
    out = []
    for blok in re.split(r"\n(?=### K\d+ )", metin)[1:]:
        h = re.match(r"### K(\d+) · ¶\S+ · (\S+) · (.*)", blok)
        kutu = re.search(r"\[(.)\] kabul\s+\[(.)\] ret", blok)
        if not (h and kutu):
            continue

        def satir(on):
            m = re.search(rf"^{on} ?(.*)$", blok, re.M)
            return coz(m.group(1)) if m else ""
        out.append({"k": int(h.group(1)), "sinif": h.group(2), "kural": h.group(3).strip(),
                    "eski": satir("✗"), "yeni": satir("✓"),
                    "kabul": kutu.group(1) in "xX✓✔", "ret": kutu.group(2) in "xX✓✔"})
    return out


def kimlik(m: dict) -> str:
    return hashlib.sha1(f"{m['sinif']}|{m['kural']}|{m['yeni']}".encode()).hexdigest()[:12]


def basliga_ekle(metin: str, baslik: str, satir: str) -> str | None:
    """Basligin bolumunun sonuna (bir sonraki basliktan once) ekler."""
    satirlar = metin.split("\n")
    i = next((j for j, s in enumerate(satirlar) if re.match(r"^#+ ", s) and baslik_adi(s) == baslik), None)
    if i is None:
        return None
    j = i + 1
    while j < len(satirlar) and not re.match(r"^#+ ", satirlar[j]):
        j += 1
    son = j - 1
    while son > i and not satirlar[son].strip():
        son -= 1
    satirlar.insert(son + 1, satir)
    return "\n".join(satirlar)


def donmus_eksik(blok: str, bolum: str) -> list:
    m = re.search(r"^- \*\*Donmuş:\*\*(.*)$", blok, re.M)
    if not m:
        return ["Donmuş satırı yok"]
    norm = lambda s: s.replace("’", "'").replace("‘", "'")  # noqa: E731
    metin = norm(bolum)
    eksik = []
    for d in re.findall(r"\"([^\"]+)\"|“([^”]+)”", m.group(1)):
        d = norm((d[0] or d[1]).strip()).rstrip("-").rstrip(".")
        if d and d not in metin:
            eksik.append(d)
    return eksik


def kararlar(no: int, klasor: Path) -> int:
    yol = klasor / "oneriler.md"
    if not yol.exists():
        print(f"HATA: {yol} yok: once ./calistir.sh sablon {no} oneriler")
        return 1
    ms = maddeleri_oku(yol.read_text(encoding="utf-8"))
    isaret = klasor / ISARET
    kayit = json.loads(isaret.read_text(encoding="utf-8")) if isaret.exists() else {"uygulandi": {}}
    yapilan = kayit["uygulandi"]
    kelimeler = KELIMELER.read_text(encoding="utf-8")
    yanki = YANKI.read_text(encoding="utf-8")
    k0, y0 = kelimeler, yanki
    say = {"eklendi": 0, "değişti": 0, "yankı": 0, "bekliyor": 0, "reddedildi": 0, "uygulanamadı": 0}
    sorunlar = []

    adlar: dict = {}
    for m in ms:
        if m["sinif"] == "AD" and m["kabul"]:
            adlar.setdefault(m["kural"] + "|" + ingilizce(m["yeni"]), []).append(m["k"])
    cift = {k for v in adlar.values() if len(v) > 1 for k in v}

    yayimli, bolum = bolum_durumu(no)

    for m in ms:
        if m["ret"]:
            say["reddedildi"] += 1
            continue
        if not m["kabul"] or m["sinif"] == "BILGI" or kimlik(m) in yapilan:
            continue
        if not yayimli:
            say["bekliyor"] += 1
            continue
        if m["sinif"] in ("EKLE", "AD", "DEGISTIR") and not metinde_mi(m["yeni"], bolum):
            sorunlar.append(f"K{m['k']}: '{kalin(m['yeni'])}' yayımlanmış {no}'da geçmiyor (✓'yi düzeltin)")
            say["uygulanamadı"] += 1
            continue
        if m["sinif"] in ("EKLE", "AD"):
            if m["k"] in cift:
                sorunlar.append(f"K{m['k']}: aynı adın iki seçeneği kabul edilmiş")
                say["uygulanamadı"] += 1
                continue
            yeni = basliga_ekle(kelimeler, m["kural"], m["yeni"])
            if yeni is None:
                sorunlar.append(f"K{m['k']}: words.md'de '{m['kural']}' başlığı yok")
                say["uygulanamadı"] += 1
                continue
            kelimeler = yeni
            say["eklendi"] += 1
        elif m["sinif"] == "DEGISTIR":
            n = kelimeler.split("\n").count(m["eski"])
            if n != 1:
                sorunlar.append(f"K{m['k']}: eski satır words.md'de {n} kez (1 olmalı)")
                say["uygulanamadı"] += 1
                continue
            satirlar = kelimeler.split("\n")
            satirlar[satirlar.index(m["eski"])] = m["yeni"]
            kelimeler = "\n".join(satirlar)
            say["değişti"] += 1
        elif m["sinif"] == "YANKI":
            eksik = donmus_eksik(m["yeni"], bolum)
            if eksik:
                sorunlar.append(f"K{m['k']} ({m['kural']}): Donmuş dize yayımlanmış {no}'da yok: "
                                + ", ".join(f"'{e}'" for e in eksik) + " (✓'yi düzeltin)")
                say["uygulanamadı"] += 1
                continue
            sira = max([int(x) for x in re.findall(r"^### #(\d+)", yanki, re.M)] or [0]) + 1
            blok = re.sub(r"^### #?\d*\s*·", f"### #{sira} ·", m["yeni"], count=1)
            blok = re.sub(r"^(### .*)\n(?!\n)", r"\1\n\n", blok, count=1)
            yanki = yanki.rstrip("\n") + "\n\n" + blok + "\n"
            say["yankı"] += 1
        yapilan[kimlik(m)] = f"K{m['k']} {m['sinif']} {m['kural']}"

    if kelimeler != k0 or yanki != y0:
        yedek = lotm.yedek_klasoru(f"sablon-oneri-{no}")
        yedek.mkdir(parents=True, exist_ok=True)
        if kelimeler != k0:
            shutil.copy2(KELIMELER, yedek / KELIMELER.name)
            lotm.atomik_yaz(KELIMELER, kelimeler)
        if yanki != y0:
            shutil.copy2(YANKI, yedek / YANKI.name)
            lotm.atomik_yaz(YANKI, yanki)
        print(f"yedek: {yedek}")
    lotm.atomik_yaz(isaret, json.dumps(kayit, ensure_ascii=False, indent=1) + "\n")
    for s in sorunlar:
        print("  " + s)
    if say["bekliyor"]:
        print(f"  {say['bekliyor']} madde bekliyor: {no} yayımlanıp 'sonra {no} --kararlar' "
              f"işlenince yeniden: ./calistir.sh sablon {no} --kararlar")
    print(f"words.md: {say['eklendi']} eklendi, {say['değişti']} değişti · Echo_Notes: {say['yankı']} eklendi, "
          f"{say['bekliyor']} bekliyor · {say['uygulanamadı']} uygulanamadı, {say['reddedildi']} ret")
    return 0
