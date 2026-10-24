#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonra.py -- ceviri bittikten SONRA, yayindan once: bir bolumun butun
denetimlerini tek komutla yurutur.

UST DUZEY SORU: "Bu bolum icin hangi denetim yapildi, hangisi bekliyor?"

Betik denetimleri zaten 'calistir.sh bolum N' zincirindeydi. Elle kalan,
model gecislerinin girdisini toplamakti: okuma gecisi icin bolum + sablon,
sadakat icin hizali ZH/TR partileri + sablon + okumanin SADAKAT? satirlari,
duzeltme icin bolum, triyaj icin zincir ciktisi. Bu betik hepsini
Reports/sonra/Ch_N/ altinda hazir dosya olarak uretir ve her calistirmada
nerede kalindigini gosterir.

ADIMLAR (sira bagimliliktan gelir)
    zincir     calistir.sh bolum N  ->  zincir.txt (renksiz) + ozet
    okuma      1_okuma_girdi.md     ->  1_okuma_cikti.md
    sadakat    2_sadakat_girdi_KK.md -> 2_sadakat_cikti_KK.md
               okuma ciktisi varsa SADAKAT? satirlari ilgili partiye girer;
               okuma sonradan biterse girdiler yeniden yazilir ve eski
               sadakat ciktilari ESKIMIS gorunur.
    duzeltme   3_duzeltme_girdi.md  ->  3_duzeltme_cikti.md
               ciktidaki tam metin bolumle karsilastirilir: 3_duzeltme_fark.diff
               (gecis bolum dosyasina yazmaz; degisiklikler birlestirmeye gider)
    triyaj     4_triyaj_girdi.md    ->  4_triyaj_cikti.md
               (otomatik kipte yalniz okuyan denetci komutlarini calistirabilir)
    birlestir  5_birlestir_girdi.md ->  5_birlestir_cikti.md (JSON)
               dort gecisin bulgulari tek listede: KESIN / KARAR / SABLON.
    son adim   KESIN duzeltmeler bolume birebir eslesmeyle uygulanir (once
               yedek: Ch_N/00NN.once-*.md, fark: 5_uygulanan.diff); geri
               kalanlar 5_inceleme.md'de kutucuklu liste olur. Isaretleyip
               '--kararlar' ile calistirinca kabul edilenler uygulanir, 'hep'
               denenler karar defterine (Tools/kararlar.md) yazilir. Defter her
               gecise verilir: verilmis bir karar bir daha sorulmaz.
               Sablonun A.2'de verdigi, bolumde kullanilan ama veride olmayan
               terimler de listelenir; isaretlenenler words.md'ye eklenir.

Iki kip:
    elle (varsayilan)  girdileri hazirlar; ciktiyi siz taze bir oturumda
                       uretip *_cikti*.md olarak kaydedersiniz.
    --otomatik         eksik ya da eskimis her ciktiyi 'claude -p' ile
                       uretir; her gecis ayri, taze bir oturumdur.
                       Komut LOTM_CLAUDE ile degistirilebilir.

DURUM: bir cikti, girdisinden yeniyse TAMAM, eskiyse ESKIMIS, yoksa
BEKLIYOR. Girdi dosyasi yalnizca icerigi degistiginde yeniden yazilir;
yani ayni komutu tekrar calistirmak tamamlanmis isi bozmaz.

Kullanim:
    sonra.py 61                        hazirla + durum
    sonra.py 61 --otomatik             eksik gecisleri claude -p ile yurut
    sonra.py 61 --otomatik okuma       yalniz okuma gecisini yurut
    sonra.py 61 --kararlar             5_inceleme.md'deki isaretli kararlari uygula
    sonra.py 61 --kuru                 bolume ve deftere yazmadan dene
    sonra.py 61 --bastan               uygulamadan sonra hatti bastan kur
    sonra.py 61 --zincir-yeniden       betik zincirini zorla yeniden calistir
    sonra.py 61 --parti-boyu 9000      sadakat partisi (ZH+TR karakter, varsayilan 6000)
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIKLER))
KOK = Path(os.environ.get("LOTM_KOK") or BETIKLER.parent)
SITE = KOK / "Imperium34.github.io"
BOLUMLER = SITE / "_chapters"
ISTEMLER = KOK / "Tools" / "Prompts"
SABLONLAR = Path(os.environ.get("LOTM_SABLONLAR") or KOK / "Tools" / "Schemas")
RAPOR = Path(os.environ.get("LOTM_SONRA_RAPOR") or BETIKLER / "Reports" / "sonra")
# Karar defteri: kullanicinin "hep boyle" dedigi kabul/ret kararlari. Bir
# rapor degil bir karar, o yuzden Reports/'ta degil Tools/'da ve surum
# denetiminde. Her gecise ve birlestirmeye verilir; ayni soru tekrar sorulmaz.
KARARLAR = Path(os.environ.get("LOTM_KARARLAR") or KOK / "Tools" / "kararlar.md")

ISTEM = {
    "okuma": "lotm_chapter_read_pass.md",
    "sadakat": "LotM_QA_Sadakat.md",
    "duzeltme": "lotm_fixing_prompt.md",
    "triyaj": "zincir-okuma-istemi.md",
    "birlestir": "lotm_birlestirme.md",
}
MODEL_ADIMLARI = ("okuma", "sadakat", "duzeltme", "triyaj", "birlestir")
# Triyaj ayrinti komutlarini kendisi calistirabilsin: yalniz okuyan denetciler.
TRIYAJ_ARACLARI = ["Read", "Bash(python3 toplu_denetle.py:*)", "Bash(python3 bicim_denetle.py:*)",
                   "Bash(python3 ceviri_denetle.py:*)", "Bash(python3 bolum.py:*)",
                   "Bash(python3 sozluk_ara.py:*)"]
UYGULANDI = "5_uygulandi.json"
KELIMELER = Path(os.environ.get("LOTM_KELIMELER") or KOK / "Tools" / "words.md")
YERLESTIRILECEK = "# Yerleştirilecek (sonra.py)"

ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Zincirde dikkat isteyen satirlar: kirmizi uyarilar, atlanan adimlar,
# coken betikler. Bicim raporunun basligi ve sifir ozeti degil.
DIKKAT = re.compile(r"HATA|ATLANDI|✗|YOK:|Traceback|Error")
SESSIZ = re.compile(r"=== HATA ===|HATA toplam: 0\b")


# ------------------------------------------------------------------ yardimci

def yaz_degisirse(yol: Path, metin: str) -> bool:
    """Icerik ayniysa dokunmaz: mtime korunur, cikti ESKIMIS gorunmez."""
    if yol.exists() and yol.read_text(encoding="utf-8") == metin:
        return False
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(metin, encoding="utf-8")
    return True


def durum(girdi: Path, cikti: Path) -> str:
    if not cikti.exists() or not cikti.read_text(encoding="utf-8").strip():
        return "BEKLIYOR"
    if girdi.exists() and girdi.stat().st_mtime > cikti.stat().st_mtime:
        return "ESKIMIS"
    return "TAMAM"


def bosluk(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def front_matter_ayir(metin: str) -> str:
    """Front matter haric govde."""
    if metin.startswith("---"):
        son = metin.find("\n---", 3)
        if son != -1:
            return metin[son + 4:]
    return metin


def tr_bloklari(metin: str) -> list:
    """Okuma gecisinin ¶ duzeni: front matter haric, bos satirla ayrilan bloklar."""
    govde = front_matter_ayir(metin)
    return [b.strip() for b in re.split(r"\n\s*\n", govde) if b.strip()]


def istem(ad: str) -> str:
    return (ISTEMLER / ISTEM[ad]).read_text(encoding="utf-8").rstrip()


def kararlar_blogu() -> str:
    """Karar defteri, gecislere verilecek bicimde; defter yoksa bos dize."""
    if not KARARLAR.exists() or not KARARLAR.read_text(encoding="utf-8").strip():
        return ""
    return (
        "<onceki_kararlar>\n"
        "Çevirmenin daha önce verdiği kalıcı kararlar. 'ret' satırındaki örüntüyü bulgu olarak "
        "yazma; 'kabul' satırındaki örüntü zaten onaylı bir düzeltmedir.\n\n"
        f"{KARARLAR.read_text(encoding='utf-8').strip()}\n"
        "</onceki_kararlar>\n\n"
    )


# ------------------------------------------------------------------ duzeltme farki

def duzeltilmis_bolum(cikti: str) -> str | None:
    """
    Duzeltme gecisinin (1) parcasi: front matter'dan baslayan tam metin.
    Cogu zaman ```markdown cercevesinde gelir; cerceve yoksa ilk '---'dan
    (2) basligina kadar alinir.
    """
    m = re.search(r"```(?:markdown|md)?\n(---\n.*?)\n```", cikti, re.S)
    if m:
        return m.group(1).strip() + "\n"
    i = cikti.find("---\n")
    if i == -1:
        return None
    j = re.search(r"\n\**\(2\)", cikti[i:])
    return cikti[i:i + j.start() if j else None].strip() + "\n"


def fark_yaz(asil: str, yeni: str, yol: Path, ad: str) -> int:
    """Birlesik fark; degisen paragraf sayisini dondurur."""
    import difflib
    a, b = asil.strip().splitlines(), yeni.strip().splitlines()
    satirlar = list(difflib.unified_diff(a, b, f"{ad} (simdiki)", f"{ad} (duzeltme)",
                                         lineterm="", n=0))
    yol.write_text("\n".join(satirlar) + ("\n" if satirlar else ""), encoding="utf-8")
    return sum(1 for s in satirlar if s.startswith("-") and not s.startswith("---"))


# ------------------------------------------------------------------ birlestirme

def json_ayikla(cikti: str):
    """Birlestirme ciktisindaki JSON: ```json cercevesi ya da ilk { ... son }."""
    import json
    m = re.search(r"```json\s*\n(.*?)\n```", cikti, re.S)
    ham = m.group(1) if m else cikti[cikti.find("{"):cikti.rfind("}") + 1]
    return json.loads(ham)


def uygula(metin: str, duzeltmeler: list) -> tuple:
    """
    KESIN duzeltmeleri birebir eslesmeyle uygular: 'eski' metinde tam bir kez
    gecmeli (yayimlanmis bolum duzeltmelerindeki kural). Gecmeyen ya da
    birden fazla gecen KARAR'a duser; sebebi 'not'a yazilir.
    """
    uygulanan, karar = [], []
    for d in duzeltmeler:
        if d.get("sinif") != "KESIN":
            karar.append(d)
            continue
        n = metin.count(d["eski"]) if d.get("eski") else 0
        if n != 1 or d["eski"] == d.get("yeni"):
            d = dict(d, sinif="KARAR",
                     neden=(d.get("neden", "") + f" [otomatik uygulanmadı: metinde {n} kez]").strip())
            karar.append(d)
            continue
        metin = metin.replace(d["eski"], d["yeni"], 1)
        uygulanan.append(d)
    return metin, uygulanan, karar


def tek_satir(s: str) -> str:
    return s.replace("\n", " ⏎ ")


def inceleme_yaz(no: int, uygulanan: list, karar: list, bilgi: list, kuru: bool,
                 terimler: list | None = None) -> str:
    out = [f"# {no}. bölüm — inceleme", ""]
    if kuru:
        out += ["_Kuru çalıştırma: bölüm dosyasına hiçbir şey yazılmadı._", ""]
    out += [f"## Uygulananlar ({len(uygulanan)})", ""]
    for d in uygulanan:
        out += [f"- ¶{d.get('p') or '?'} · {d.get('kural', '')} ({', '.join(d.get('kaynak', []))})",
                f"  ✗ {tek_satir(d['eski'])}", f"  ✓ {tek_satir(d['yeni'])}"]
    out += ["", f"## Kararınızı bekleyenler ({sum(d.get('sinif') != 'SABLON' for d in karar)})", "",
            "Her maddede bir kutuyu [x] yapın; ✓ satırını isterseniz değiştirin. 'hep' kararı",
            "karar defterine yazar, aynı örüntü bir daha sorulmaz. Sonra:",
            f"`./calistir.sh sonra {no} --kararlar`", ""]
    # SABLON maddeleri ayri bolumde: metin icin degil sablon icin geri bildirim.
    # Numaralar iki bolumde de K1'den devam eder; --kararlar hepsini ayni okur.
    metin_k = [d for d in karar if d.get("sinif") != "SABLON"]
    sablon_k = [d for d in karar if d.get("sinif") == "SABLON"]
    for i, d in enumerate(metin_k + sablon_k, 1):
        if i == len(metin_k) + 1:
            out += [f"## Şablon geri bildirimi ({len(sablon_k)})", "",
                    "Dondurulmuş ya da öngörülmüş satırlar. Kabul, yalnız bu bölümün metnini değiştirir;",
                    "kalıp başka bölümlerde de geçiyorsa şablona/sözlüğe ayrıca işlenmeli.", ""]
        out += [f"### K{i} · ¶{d.get('p') or '?'} · {d.get('sinif', 'KARAR')} · {d.get('kural', '')}",
                f"✗ {tek_satir(d.get('eski', ''))}",
                f"✓ {tek_satir(d.get('yeni', ''))}",
                f"Neden: {d.get('neden', '')}",
                f"Kaynak: {', '.join(d.get('kaynak', []))}",
                "[ ] kabul   [ ] ret   [ ] hep", ""]
    out += terimler_yaz(terimler or [])
    if bilgi:
        out += [f"## Bilgi ({len(bilgi)})", ""]
        out += [f"- ¶{x.get('p') or '-'}: {x.get('not', '')}" for x in bilgi]
    return "\n".join(out).rstrip() + "\n"


def terimler_yaz(terimler: list) -> list:
    """Sablonun A.2'de verdigi, bolumde kullanilan, veride olmayan terimler."""
    if not terimler:
        return []
    out = [f"## Veriye eklenecek terimler ({len(terimler)})", "",
           "Şablonun bu bölüm için verdiği yeni karşılıklar; metinde geçiyor ama sözlükte ya da",
           "words.md'de yok. İşaretlenen words.md'nin sonundaki 'Yerleştirilecek' bölümüne yazılır;",
           "Türkçe ya da İngilizceyi işaretlemeden önce düzeltebilirsiniz. Çincesini sonra ekleyin.", ""]
    for i, t in enumerate(terimler, 1):
        etiket = " · ".join(e for e in ("GEÇİCİ" if t.get("gecici") else "",
                                        "TEREDDÜT" if t.get("tereddut") else "") if e)
        out += [f"### T{i} · {t['tr']} ← {t['en']}" + (f" · {etiket}" if etiket else ""),
                "[ ] words.md'ye ekle", ""]
    return out


def terimler_oku(metin: str) -> list:
    """Isaretlenmis terimler: [{"tr", "en"}]."""
    out = []
    for blok in re.split(r"\n(?=### T\d+ )", metin)[1:]:
        m = re.match(r"### T\d+ · (.+?) ← (.+?)(?: · (?:GEÇİCİ|TEREDDÜT).*)?$", blok.splitlines()[0])
        k = re.search(r"\[(.)\] words\.md'ye ekle", blok)
        if m and k and k.group(1).strip().lower() in ("x", "✓", "✔"):
            out.append({"tr": m.group(1).strip(), "en": m.group(2).strip()})
    return out


def kelimelere_ekle(yol: Path, terimler: list, no: int) -> None:
    """words.md'nin sonundaki 'Yerleştirilecek' bolumune ekler (yoksa acar)."""
    metin = yol.read_text(encoding="utf-8") if yol.exists() else ""
    if YERLESTIRILECEK not in metin:
        metin = metin.rstrip() + (
            f"\n\n{YERLESTIRILECEK}\n\n"
            "sonra.py'nin inceleme adımında eklenen terimler. Yükleyici bölüme bakmaz; "
            "yerine taşıyın ve Çincesini parantezle ekleyin.\n")
    satirlar = [f"- **{t['tr']}** — {t['en']}; {no}. bölümün şablonundan (Çincesi eklenmeli) _{no}_"
                for t in terimler]
    yol.write_text(metin.rstrip() + "\n" + "\n".join(satirlar) + "\n", encoding="utf-8")


def inceleme_oku(metin: str) -> list:
    """Isaretlenmis kararlar: [{"k", "p", "kural", "eski", "yeni", "kabul", "ret", "hep"}]."""
    out = []
    for blok in re.split(r"\n(?=### K\d+ )", metin)[1:]:
        bas = re.match(r"### K(\d+) · ¶(\S+) · (\S+) · (.*)", blok)
        x = re.search(r"^✗ (.*)$", blok, re.M)
        v = re.search(r"^✓ (.*)$", blok, re.M)
        kutu = re.search(r"\[(.)\] kabul\s+\[(.)\] ret\s+\[(.)\] hep", blok)
        if not (bas and x and v and kutu):
            continue
        isaret = [c.strip().lower() in ("x", "✓", "✔") for c in kutu.groups()]
        out.append({"k": int(bas.group(1)), "p": bas.group(2), "kural": bas.group(4).strip(),
                    "eski": x.group(1).replace(" ⏎ ", "\n"), "yeni": v.group(1).replace(" ⏎ ", "\n"),
                    "kabul": isaret[0], "ret": isaret[1], "hep": isaret[2]})
    return out


# ------------------------------------------------------------------ SADAKAT?

def sadakat_sorulari(okuma: str) -> list:
    """
    Okuma ciktisindaki SADAKAT? bulgulari: [{"no": ¶, "x": ✗ metni, "ham": blok}].
    Blok, '¶N  SADAKAT?' satirindan bir sonraki ¶ satirina ya da bos satira kadar.
    """
    satirlar = okuma.splitlines()
    out = []
    i = 0
    while i < len(satirlar):
        m = re.match(r"\s*¶(\d+)\s+SADAKAT\?", satirlar[i])
        if not m:
            i += 1
            continue
        blok = [satirlar[i]]
        i += 1
        while i < len(satirlar) and satirlar[i].strip() and not re.match(r"\s*¶\d+\s", satirlar[i]):
            blok.append(satirlar[i])
            i += 1
        x = []
        icinde = False
        for s in blok[1:]:
            t = s.strip()
            if t.startswith("✗"):
                icinde = True
                x.append(t[1:].strip())
            elif t.startswith(("Gerekçe", "✓")):
                icinde = False
            elif icinde:
                x.append(t)
        out.append({"no": int(m.group(1)), "x": bosluk(" ".join(x)), "ham": "\n".join(blok)})
    return out


def grup_bul(soru: dict, gruplar: dict, bloklar: list) -> int | None:
    """
    Okuma ¶'si TR blok numarasidir, sadakat ¶'si hizalama grubu; ikisi
    ayni degil. Once ✗ metniyle, olmazsa ¶'nin TR blogunun basiyla aranir.
    """
    trler = {k: bosluk(g["TR"]) for k, g in gruplar.items()}
    adaylar = []
    if soru["x"]:
        adaylar.append(soru["x"].rstrip("…").strip()[:60])
    if 1 <= soru["no"] <= len(bloklar):
        adaylar.append(bosluk(bloklar[soru["no"] - 1])[:60])
    for aday in adaylar:
        if len(aday) < 12:
            continue
        for k, tr in trler.items():
            if aday in tr:
                return k
    return None


# ------------------------------------------------------------------ partiler

def partile(gruplar: dict, boy: int) -> list:
    """Grup sinirinda boler; son parti cok kucukse oncekine katilir."""
    partiler, simdiki, uzunluk = [], [], 0
    for k, g in gruplar.items():
        n = len(g["ZH"]) + len(g["TR"])
        if simdiki and uzunluk + n > boy:
            partiler.append(simdiki)
            simdiki, uzunluk = [], 0
        simdiki.append(k)
        uzunluk += n
    if simdiki:
        if partiler and uzunluk < boy * 0.3:
            partiler[-1].extend(simdiki)
        else:
            partiler.append(simdiki)
    return partiler


def hizali_metin(gruplar: dict, nolar: list) -> str:
    return "\n\n".join(f"¶{k}\nZH: {gruplar[k]['ZH']}\nTR: {gruplar[k]['TR']}" for k in nolar)


# ------------------------------------------------------------------ adimlar

class Bolum:
    def __init__(self, no: int, parti_boyu: int):
        self.no = no
        self.klasor = RAPOR / f"Ch_{no}"
        self.dosya = BOLUMLER / f"{no:04d}.md"
        self.sablon = SABLONLAR / f"Ch_{no}.md"
        self.parti_boyu = parti_boyu
        self.zincir = self.klasor / "zincir.txt"

    def sablon_blogu(self, etiket: str) -> str:
        if not self.sablon.exists():
            return f"<{etiket}>\n(şablon yok: {self.sablon.name})\n</{etiket}>"
        return f"<{etiket}>\n{self.sablon.read_text(encoding='utf-8').rstrip()}\n</{etiket}>"

    # -- zincir
    def zincir_calistir(self, zorla: bool) -> None:
        kaynaklar = [p for p in (self.dosya, self.sablon) if p.exists()]
        if (not zorla and self.zincir.exists()
                and all(p.stat().st_mtime <= self.zincir.stat().st_mtime for p in kaynaklar)):
            print("zincir: bolum ve sablon degismemis, onceki cikti kullaniliyor "
                  "(zorlamak icin --zincir-yeniden)")
            return
        print(f"zincir: calistir.sh bolum {self.no} ...")
        p = subprocess.run(
            ["bash", str(BETIKLER / "calistir.sh"), "bolum", str(self.no)],
            capture_output=True, text=True, cwd=BETIKLER,
        )
        cikti = ANSI.sub("", p.stdout + (("\n" + p.stderr) if p.stderr.strip() else ""))
        self.klasor.mkdir(parents=True, exist_ok=True)
        self.zincir.write_text(cikti, encoding="utf-8")

    def zincir_ozeti(self) -> list:
        if not self.zincir.exists():
            return ["(zincir ciktisi yok)"]
        return [s.rstrip() for s in self.zincir.read_text(encoding="utf-8").splitlines()
                if DIKKAT.search(s) and not SESSIZ.search(s)]

    # -- okuma
    def okuma(self) -> list:
        girdi = self.klasor / "1_okuma_girdi.md"
        metin = (
            f"{istem('okuma')}\n\n---\n\n"
            f"{kararlar_blogu()}"
            f"{self.sablon_blogu('bolum_sablonu')}\n\n"
            f"<bolum>\n{self.dosya.read_text(encoding='utf-8').rstrip()}\n</bolum>\n"
        )
        yaz_degisirse(girdi, metin)
        return [(girdi, self.klasor / "1_okuma_cikti.md")]

    # -- sadakat
    def sadakat(self) -> tuple:
        sys.path.insert(0, str(BETIKLER / "harita"))
        from gruplar import gruplar as _gruplar  # bolum.py'nin ¶ duzeni

        gruplar = _gruplar(self.no, "tr")
        if not gruplar:
            raise SystemExit(f"sadakat: {self.no}. bolum hizalanamadi (ZH ya da TR yok)")
        okuma_cikti = self.klasor / "1_okuma_cikti.md"
        sorular = (sadakat_sorulari(okuma_cikti.read_text(encoding="utf-8"))
                   if okuma_cikti.exists() else None)
        bloklar = tr_bloklari(self.dosya.read_text(encoding="utf-8"))
        yerli, yersiz = {}, []
        for s in sorular or []:
            k = grup_bul(s, gruplar, bloklar)
            if k is None:
                yersiz.append(s)
            else:
                yerli.setdefault(k, []).append(s)

        partiler = partile(gruplar, self.parti_boyu)
        ciftler = []
        for i, nolar in enumerate(partiler, 1):
            parcalar = [istem("sadakat"), "---", f"Parti {i}/{len(partiler)}: ¶{nolar[0]}–¶{nolar[-1]}",
                        f"<aligned>\n{hizali_metin(gruplar, nolar)}\n</aligned>",
                        self.sablon_blogu("chapter_template")]
            if kararlar_blogu():
                parcalar.append(kararlar_blogu().rstrip())
            if sorular is None:
                parcalar.append("<okuma_bulgulari>\n(okuma geçişi henüz yapılmadı)\n</okuma_bulgulari>")
            else:
                satirlar = [f"(okuma ¶{s['no']} → hizalama ¶{k})\n{s['ham']}"
                            for k in nolar for s in yerli.get(k, [])]
                if yersiz:
                    satirlar.append(
                        "Yeri bulunamayanlar: yalnızca cümle bu partideyse cevaplayın.\n"
                        + "\n\n".join(s["ham"] for s in yersiz))
                parcalar.append("<okuma_bulgulari>\n"
                                + ("\n\n".join(satirlar) or "Bu partide SADAKAT? yok.")
                                + "\n</okuma_bulgulari>")
            girdi = self.klasor / f"2_sadakat_girdi_{i:02d}.md"
            yaz_degisirse(girdi, "\n\n".join(parcalar) + "\n")
            ciftler.append((girdi, self.klasor / f"2_sadakat_cikti_{i:02d}.md"))
        # Parti sayisi azaldiysa artakalan eski girdiler kafa karistirmasin.
        for eski in self.klasor.glob("2_sadakat_girdi_*.md"):
            if eski not in [g for g, _ in ciftler]:
                eski.unlink()
        not_ = None
        if sorular is not None:
            not_ = f"{len(sorular)} SADAKAT? ({len(yersiz)} tanesinin yeri bulunamadi)"
        return ciftler, not_

    # -- duzeltme
    def duzeltme(self) -> list:
        girdi = self.klasor / "3_duzeltme_girdi.md"
        metin = f"{istem('duzeltme')}\n\n---\n\n{self.dosya.read_text(encoding='utf-8').rstrip()}\n"
        yaz_degisirse(girdi, metin)
        return [(girdi, self.klasor / "3_duzeltme_cikti.md")]

    def duzeltme_farki(self) -> str | None:
        """Duzeltme ciktisindaki tam metni bolumle karsilastirir -> 3_duzeltme_fark.diff."""
        cikti = self.klasor / "3_duzeltme_cikti.md"
        if not cikti.exists():
            return None
        yeni = duzeltilmis_bolum(cikti.read_text(encoding="utf-8"))
        if yeni is None:
            return "duzeltilmis metin ciktida bulunamadi"
        n = fark_yaz(self.dosya.read_text(encoding="utf-8"), yeni,
                     self.klasor / "3_duzeltme_fark.diff", self.dosya.name)
        return f"{n} paragraf degisti -> 3_duzeltme_fark.diff" if n else "metin degismedi"

    # -- birlestir
    def birlestir(self) -> list:
        """Butun gecislerin bulgulari tek listeye: KESIN / KARAR / SABLON + bilgi."""
        k = self.klasor

        def oku(ad):
            p = k / ad
            return p.read_text(encoding="utf-8").strip() if p.exists() else "(yok)"

        sadakat = "\n\n".join(f"<!-- {p.name} -->\n{p.read_text(encoding='utf-8').strip()}"
                              for p in sorted(k.glob("2_sadakat_cikti_*.md"))) or "(yok)"
        duz = oku("3_duzeltme_cikti.md")
        dokum = duz[duz.find("(2)"):] if "(2)" in duz else duz  # tam metin tekrar verilmez
        metin = (
            f"{istem('birlestir')}\n\n---\n\n"
            f"{kararlar_blogu()}"
            f"{self.sablon_blogu('bolum_sablonu')}\n\n"
            f"<bolum>\n{self.dosya.read_text(encoding='utf-8').rstrip()}\n</bolum>\n\n"
            f"<okuma>\n{oku('1_okuma_cikti.md')}\n</okuma>\n\n"
            f"<sadakat>\n{sadakat}\n</sadakat>\n\n"
            f"<duzeltme_fark>\n{oku('3_duzeltme_fark.diff')}\n</duzeltme_fark>\n\n"
            f"<duzeltme_dokum>\n{dokum}\n</duzeltme_dokum>\n\n"
            f"<triyaj>\n{oku('4_triyaj_cikti.md')}\n</triyaj>\n"
        )
        girdi = k / "5_birlestir_girdi.md"
        yaz_degisirse(girdi, metin)
        return [(girdi, k / "5_birlestir_cikti.md")]

    # -- sablonun yeni terimleri
    def yeni_terimler(self) -> list:
        """
        Sablonun A.2 satirlari (yeni karar) arasindan: Turkcesi bolumde gecen,
        ne Turkcesi ne Ingilizcesi sozlukte/words.md'de olanlar. Bunlar veriye
        girmezse bir sonraki sablon ayni karari yeniden verir.
        """
        if not self.sablon.exists():
            return []
        import sablon_denetle as SD
        kay = SD.yukle(self.no)
        bolum = SD.tr_kucult(self.dosya.read_text(encoding="utf-8"))
        # Sozluk alanlarinin hepsi terim dizinine girmiyor (Mertebe merdiveninin
        # 'bolgesel' adlari gibi); karar verilmis her bicim ham metinde de aranir.
        veri = [m for ad, m in kay._metin_kucuk.items() if "words" in str(ad) or "sozluk" in str(ad)]
        out, gorulen = [], set()
        for st in SD.sablon_satirlari(self.sablon.read_text(encoding="utf-8")):
            if st.bolum != "A.2" or not st.tr or not st.en:
                continue
            trler = [SD.tr_norm(t) for t in st.tr if SD.tr_norm(t) not in ("", "aynen")]
            if not trler or any(t in kay.tr_dizin for t in trler):
                continue
            if any(t in m for t in trler for m in veri):
                continue
            if any(SD.en_norm(e) in kay.en_dizin for e in st.en):
                continue
            # Gecme denetimi govdeyle: ekli bicimler de sayilsin (Levha -> Levhası).
            if not any(re.search(r"(?<!\w)" + re.escape(t[:max(4, len(t) - 2)]), bolum) for t in trler):
                continue
            tr = re.sub(r"\s*\[[^\]]*\]", "", st.tr[0]).strip()
            # Ozel adlar: A.2'deki kucuk harfli sozcuk tercihleri (fikir, yontem)
            # bolume ozgu uslup kararidir, veriye tasinmaz.
            if not tr[:1].isupper():
                continue
            if tr.lower() in gorulen:
                continue
            gorulen.add(tr.lower())
            out.append({"tr": tr, "en": st.en[0], "gecici": SD.gecici_mi(st), "tereddut": st.tereddut})
        return out

    # -- son adim: uygula
    def son_adim(self, kuru: bool) -> str:
        import json
        cikti = self.klasor / "5_birlestir_cikti.md"
        try:
            veri = json_ayikla(cikti.read_text(encoding="utf-8"))
        except (ValueError, KeyError) as e:
            return f"HATA: 5_birlestir_cikti.md JSON olarak okunamadi ({e})"
        asil = self.dosya.read_text(encoding="utf-8")
        yeni, uygulanan, karar = uygula(asil, veri.get("duzeltmeler", []))
        inceleme = self.klasor / "5_inceleme.md"
        try:
            terimler = self.yeni_terimler()
        except Exception as e:  # terim listesi yardimci; hat onun yuzunden durmasin
            terimler = []
            veri.setdefault("bilgi", []).append({"p": None, "not": f"yeni terim listesi kurulamadı: {e}"})
        inceleme.write_text(inceleme_yaz(self.no, uygulanan, karar, veri.get("bilgi", []), kuru,
                                         terimler), encoding="utf-8")
        if kuru:
            return f"kuru: {len(uygulanan)} uygulanirdi, {len(karar)} karar -> 5_inceleme.md"
        if uygulanan:
            damga = time.strftime("%Y%m%d-%H%M%S")
            (self.klasor / f"{self.dosya.stem}.once-{damga}.md").write_text(asil, encoding="utf-8")
            self.dosya.write_text(yeni, encoding="utf-8")
            fark_yaz(asil, yeni, self.klasor / "5_uygulanan.diff", self.dosya.name)
        (self.klasor / UYGULANDI).write_text(json.dumps(
            {"zaman": time.strftime("%Y-%m-%d %H:%M"), "uygulanan": len(uygulanan),
             "karar": len(karar)}, ensure_ascii=False), encoding="utf-8")
        return f"{len(uygulanan)} kesin duzeltme uygulandi, {len(karar)} karar bekliyor -> 5_inceleme.md"

    def kararlari_isle(self, kuru: bool) -> str:
        """5_inceleme.md'de isaretlenenleri uygular; 'hep' olanlari karar defterine yazar."""
        inceleme = self.klasor / "5_inceleme.md"
        if not inceleme.exists():
            return "YOK: 5_inceleme.md (once hattin sonuna kadar calistirin)"
        secimler = inceleme_oku(inceleme.read_text(encoding="utf-8"))
        metin = self.dosya.read_text(encoding="utf-8")
        uygulanan, bulunamayan, defter = [], [], []
        for s in secimler:
            if s["kabul"]:
                if metin.count(s["eski"]) == 1:
                    metin = metin.replace(s["eski"], s["yeni"], 1)
                    uygulanan.append(s["k"])
                else:
                    bulunamayan.append(s["k"])
            if s["hep"] and (s["kabul"] or s["ret"]):
                hukum = "kabul" if s["kabul"] else "ret"
                defter.append(f"- {hukum} · {s['kural']} — örnek: «{tek_satir(s['eski'])}» → "
                              f"«{tek_satir(s['yeni'])}» ({self.no}. bölüm ¶{s['p']})")
        terimler = terimler_oku(inceleme.read_text(encoding="utf-8"))
        if not kuru:
            if terimler:
                kelimelere_ekle(KELIMELER, terimler, self.no)
            if uygulanan:
                self.dosya.write_text(metin, encoding="utf-8")
            if defter:
                bas = "" if KARARLAR.exists() else (
                    "# Karar defteri\n\nsonra.py'nin inceleme adımında 'hep' denen kararlar. "
                    "Her geçişe verilir; elle düzenlenebilir.\n\n")
                with KARARLAR.open("a", encoding="utf-8") as f:
                    f.write(bas + "\n".join(defter) + "\n")
        sonuc = (f"{len(uygulanan)} karar uygulandi, {len(defter)} kalici karar deftere yazildi, "
                 f"{len(terimler)} terim words.md'ye eklendi"
                 + (f"; metinde bulunamayan: {', '.join('K%d' % k for k in bulunamayan)}"
                    if bulunamayan else ""))
        return ("kuru: " if kuru else "") + sonuc

    # -- triyaj
    def triyaj(self) -> list:
        girdi = self.klasor / "4_triyaj_girdi.md"
        zincir = self.zincir.read_text(encoding="utf-8") if self.zincir.exists() else "(yok)"
        metin = (
            f"{istem('triyaj')}\n\n---\n\n"
            f"Not: aşağıdaki çıktı tam zincir (hepsi) değil, `./calistir.sh bolum {self.no}` "
            f"zinciridir. Üzerinde çalışılan bölüm {self.no}; henüz yayımlanmadı.\n\n"
            f"<calistir_ciktisi>\n{zincir.rstrip()}\n</calistir_ciktisi>\n"
        )
        yaz_degisirse(girdi, metin)
        return [(girdi, self.klasor / "4_triyaj_cikti.md")]


# ------------------------------------------------------------------ otomatik

def claude_komutu(model: str | None, araclar: list | None = None) -> list:
    komut = shlex.split(os.environ.get("LOTM_CLAUDE", "claude -p --output-format text"))
    if model:
        komut += ["--model", model]
    if araclar:
        komut += ["--allowedTools", ",".join(araclar)]
    return komut


def yurut(girdi: Path, cikti: Path, model: str | None, sure: int,
          araclar: list | None = None) -> bool:
    """Taze bir oturum: girdi stdin'den, cevap ciktiya. Hata olursa cikti yazilmaz."""
    print(f"  claude: {girdi.name} -> {cikti.name} ...", flush=True)
    try:
        p = subprocess.run(claude_komutu(model, araclar), input=girdi.read_text(encoding="utf-8"),
                           capture_output=True, text=True, timeout=sure, cwd=BETIKLER)
    except FileNotFoundError:
        print("  HATA: claude komutu bulunamadi (LOTM_CLAUDE ile verin)")
        return False
    except subprocess.TimeoutExpired:
        print(f"  HATA: {sure} sn icinde bitmedi")
        return False
    if p.returncode != 0 or not p.stdout.strip():
        print(f"  HATA (cikis {p.returncode}): {p.stderr.strip()[:300]}")
        return False
    cikti.write_text(p.stdout, encoding="utf-8")
    return True


# ------------------------------------------------------------------ ana

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bolum sonrasi denetim hatti.")
    ap.add_argument("no", type=int)
    ap.add_argument("--otomatik", nargs="*", choices=MODEL_ADIMLARI, metavar="ADIM",
                    help="eksik/eskimis ciktilari claude -p ile uret; adim verilmezse hepsi")
    ap.add_argument("--kararlar", action="store_true",
                    help="5_inceleme.md'de isaretlenen kararlari uygula, 'hep'leri deftere yaz")
    ap.add_argument("--kuru", action="store_true", help="bolum dosyasina ve deftere yazma")
    ap.add_argument("--bastan", action="store_true",
                    help="uygulama yapilmis olsa da hatti bastan kur (gecisler yeniden)")
    ap.add_argument("--zincir-yeniden", action="store_true")
    # 6000 ZH+TR karakter: yaklasik 20-25 grup, bir bolum 2-4 parti.
    ap.add_argument("--parti-boyu", type=int, default=6000)
    ap.add_argument("--model")
    ap.add_argument("--sure", type=int, default=1800, help="gecis basina zaman asimi (sn)")
    a = ap.parse_args(argv)

    b = Bolum(a.no, a.parti_boyu)
    if not b.dosya.exists():
        print(f"YOK: {b.dosya}")
        return 1
    b.klasor.mkdir(parents=True, exist_ok=True)
    isaret = b.klasor / UYGULANDI

    if a.kararlar:
        print(b.kararlari_isle(a.kuru))
        return 0
    # Kesin duzeltmeler uygulandiktan sonra bolum degisir; hat yeniden
    # kurulsa her gecis ESKIMIS gorunur ve bastan calisirdi. Isaret varken
    # hat donuktur: yalniz kararlar kalir.
    if isaret.exists() and not a.bastan:
        print(f"{a.no}. bolumde kesin duzeltmeler uygulanmis ({isaret.read_text(encoding='utf-8')}).")
        print(f"  kalan kararlar: {b.klasor / '5_inceleme.md'}")
        print(f"  isledikten sonra: ./calistir.sh sonra {a.no} --kararlar")
        print(f"  hatti bastan kurmak icin: ./calistir.sh sonra {a.no} --bastan")
        return 0
    if isaret.exists():
        isaret.unlink()

    otomatik = None if a.otomatik is None else (a.otomatik or list(MODEL_ADIMLARI))
    if otomatik and not shutil.which(claude_komutu(None)[0]):
        print(f"YOK: '{claude_komutu(None)[0]}' komutu. Claude Code kurulu degil ya da PATH'te degil:")
        print("  curl -fsSL https://claude.ai/install.sh | bash   (sonra bir kez 'claude' ile giris)")
        print("  fish: fish_add_path ~/.local/bin")
        print("  ya da LOTM_CLAUDE ile baska bir komut verin. Simdilik yalniz girdiler hazirlaniyor.")
        otomatik = None

    b.zincir_calistir(a.zincir_yeniden)

    sonuc, notlar = {}, {}
    for adim in MODEL_ADIMLARI:
        if adim == "sadakat":
            ciftler, notlar["sadakat"] = b.sadakat()
        elif adim == "birlestir":
            onceki = [c for ad in ("okuma", "sadakat", "duzeltme", "triyaj") for _, c in sonuc[ad]]
            if not all(c.exists() for c in onceki):
                sonuc[adim] = []
                notlar[adim] = "onceki gecisler bitince kurulur"
                continue
            ciftler = b.birlestir()
        else:
            ciftler = getattr(b, adim)()
        if otomatik and adim in otomatik:
            araclar = TRIYAJ_ARACLARI if adim == "triyaj" else None
            for girdi, cikti in ciftler:
                if durum(girdi, cikti) != "TAMAM":
                    yurut(girdi, cikti, a.model, a.sure, araclar)
        if adim == "duzeltme":
            notlar[adim] = b.duzeltme_farki()
        # Sira onemli: okuma burada biterse sadakat girdileri ayni turda
        # onun SADAKAT? satirlariyla kurulur.
        sonuc[adim] = ciftler

    son = None
    if sonuc["birlestir"] and durum(*sonuc["birlestir"][0]) == "TAMAM":
        son = b.son_adim(a.kuru)

    # --- rapor
    ozet = b.zincir_ozeti()
    satirlar = [f"# {a.no}. bölüm — yayın sonrası hattı", "",
                f"Klasör: {b.klasor}", "", "## Betik zinciri",
                f"zincir.txt — {'temiz' if not ozet else f'{len(ozet)} dikkat satırı'}"]
    satirlar += [f"    {s}" for s in ozet]
    satirlar += ["", "## Model geçişleri"]
    for adim in MODEL_ADIMLARI:
        for girdi, cikti in sonuc[adim]:
            satirlar.append(f"{durum(girdi, cikti):9} {adim:9} {girdi.name}  ->  {cikti.name}")
        if notlar.get(adim):
            satirlar.append(f"{'':9} {adim if not sonuc[adim] else '':9} {notlar[adim]}")
    if son:
        satirlar += ["", "## Son adım", son]
    if not (b.klasor / "1_okuma_cikti.md").exists():
        satirlar += ["", "Not: sadakat girdileri okuma çıktısı olmadan kuruldu; "
                         "1_okuma_cikti.md kaydedildikten sonra yeniden çalıştırın."]
    if not otomatik and not son:
        satirlar += ["", "Elle: her *_girdi*.md dosyasını taze bir oturuma verin, cevabı aynı "
                         "numaralı *_cikti*.md olarak kaydedin, sonra bu komutu yeniden çalıştırın.",
                     f"Otomatik: ./calistir.sh sonra {a.no} --otomatik [adım...]"]
    rapor = "\n".join(satirlar) + "\n"
    (b.klasor / "DURUM.md").write_text(rapor, encoding="utf-8")
    print()
    print(rapor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
