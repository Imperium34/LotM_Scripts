#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inceleme_sunucu.py -- 5_inceleme.md icin yerel inceleme sayfasi.

Tek kaynak .md dosyasidir: sayfa her tusta kutulari ve ✓ satirini dosyaya
geri yazar; 'sonra.py N --kararlar' eskisi gibi calisir, dosya elle de
duzenlenebilir (sayfa her istekte dosyayi yeniden okur).

Sayfa: bir seferde bir madde; ✗/✓ satirlari degisen sozcukler isaretli,
Neden, butun TR paragrafi ve hizali ZH paragrafi; katman suzgeci, ilerleme.
Tuslar: k kabul · r ret · h hep · e ✓'yi duzenle · → / ← gezin · u geri al ·
A (Shift+a) uygula ve sonraki bolum.

Uygulananlar (7 Kas): hattin kendisi yazdigi KESIN ve otomatik (okuma 1.6)
duzeltmeler de listenin sonunda, "0. Uygulananlar" suzgecinde gorunur;
sayaca girmez. g o duzeltmeyi geri alinacak diye isaretler (dosyada
'[x] geri al'), Uygula ✓'yi ✗'ye dondurur. Otomatik olanlarin kabul/geri
alma orani istatistige yazilir.

Uygula (7 Kas): sayfadaki dugme ya da A, o bolumun kararlarini komut
satirindaki gibi uygular ('sonra.py N --kararlar'; ses_ayari dosyasinda
'ses_ayari.py N --kararlar'), sonra kuyruktaki bir sonraki bolumu ayni
sekmede acar. Kuyruk bittiyse sunucu kapanir (sekme kapatilmaya calisilir;
tarayici izin vermezse "bitti" yazar). Isaretsiz madde varsa once sorulur.

Kuyruk: tek numara verilince o bolum + ondan sonraki, incelemesi hazir
(5_inceleme.md var) ve kararlari henuz islenmemis (5_kararlar.json yok ya da
inceleme ondan yeni) bolumler. Aralik/liste verilince yalniz onlar; islenmis
olanlar atlanir. --tek: kuyruk yok, yalniz o bolum.

Yalniz 127.0.0.1'e baglanir; harici bagimlilik yok (http.server).

Kullanim:
    ./calistir.sh incele 9                       9 ve sonraki hazir bolumler
    ./calistir.sh incele 20-25                   yalniz 20-25 (islenmisler atlanir)
    ./calistir.sh incele 9 --tek                 yalniz 9
    ./calistir.sh incele --dosya Reports/ses_ayari/Ch_72/inceleme.md --bolum 72
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIKLER))
sys.path.insert(0, str(BETIKLER / "harita"))

import sonra as S  # noqa: E402

KUTU = re.compile(r"\[(.)\] kabul(\s+)\[(.)\] ret(\s+)\[(.)\] hep")
ISARET = ("x", "X", "✓", "✔")
KILIT = threading.Lock()


# ------------------------------------------------------------------ dosya

def maddeler(metin: str) -> tuple:
    """([madde], toplu_kutu_var_mi, toplu_isaretli). Madde: k, katman, alanlar, kutular."""
    out, toplu_var, toplu = [], False, False
    for bolum in re.split(r"\n(?=## )", metin):
        baslik = bolum.split("\n", 1)[0][3:].strip()
        bas = bolum.split("\n### ", 1)[0]
        if "Bu bölümdeki işaretsiz" in bas:
            toplu_var = True
            toplu = bool(re.search(r"\[[xX✓✔]\] Bu bölümdeki işaretsiz", bas))
        for blok in re.split(r"\n(?=### K\d+ )", bolum)[1:]:
            h = re.match(r"### K(\d+) · (?:Ch_(\d+) · )?¶(\S+) · (\S+) · (.*)", blok)
            kutu = KUTU.search(blok)
            if not (h and kutu):
                continue

            def satir(on):
                m = re.search(rf"^{on} (.*)$", blok, re.M)
                return m.group(1) if m else ""
            out.append({"k": int(h.group(1)), "bolum": int(h.group(2)) if h.group(2) else None,
                        "p": h.group(3), "sinif": h.group(4), "kural": h.group(5).strip(),
                        "katman": re.sub(r"\s*\(\d+\)$", "", baslik),
                        "eski": satir("✗").replace(" ⏎ ", "\n"), "yeni": satir("✓").replace(" ⏎ ", "\n"),
                        "neden": satir("Neden:"), "kaynak": satir("Kaynak:"),
                        "ekler": [s for s in blok.splitlines()[1:]
                                  if s.startswith(("Dikkat:", "Ön:", "Sadakat:", "Okuma:", "Grup:", "Aynı değişiklik:"))],
                        "grup": int(g.group(1)) if (g := re.search(r"^Grup: K(\d+)", blok, re.M)) else None,
                        "kabul": kutu.group(1) in ISARET, "ret": kutu.group(3) in ISARET,
                        "hep": kutu.group(5) in ISARET})
    return out, toplu_var, toplu


def madde_yaz(metin: str, k: int, kabul: bool, ret: bool, hep: bool, yeni: str | None) -> str:
    """K maddesinin kutularini (ve verildiyse ✓ satirini) degistirir; baska yere dokunmaz."""
    m = re.search(rf"(^### K{k} · .*?)(?=^### K\d+ |^## |\Z)", metin, re.M | re.S)
    if not m:
        raise KeyError(f"K{k} bulunamadi")
    blok = m.group(1)
    c = lambda b: "x" if b else " "  # noqa: E731
    blok = KUTU.sub(lambda x: f"[{c(kabul)}] kabul{x.group(2)}[{c(ret)}] ret{x.group(4)}[{c(hep)}] hep", blok, 1)
    if yeni is not None:
        yeni_satir = "✓ " + S.tek_satir(yeni.strip())
        blok = re.sub(r"^✓ ?.*$", lambda _: yeni_satir, blok, count=1, flags=re.M)
        x = re.search(r"^✗ (.*)$", blok, re.M)
        if x and re.search(r"^Fark: ", blok, re.M):
            fark = "Fark: " + S.kelime_farki(x.group(1), S.tek_satir(yeni.strip()))
            blok = re.sub(r"^Fark: .*$", lambda _: fark, blok, count=1, flags=re.M)
    return metin[:m.start()] + blok + metin[m.end():]


def toplu_yaz(metin: str, isaret: bool) -> str:
    return re.sub(r"\[.\] Bu bölümdeki işaretsiz", f"[{'x' if isaret else ' '}] Bu bölümdeki işaretsiz", metin, count=1)


def yaz(yol: Path, metin: str) -> None:
    S.lotm.atomik_yaz(yol, metin)


# ------------------------------------------------------------------ baglam

def farklar(a: str, b: str) -> tuple:
    """Sozcuk duzeyi isaret: ([(tur, metin)] eski icin, ... yeni icin)."""
    x, y = re.findall(r"\S+|\s+", a), re.findall(r"\S+|\s+", b)
    sx, sy = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, x, y, autojunk=False).get_opcodes():
        if op == "equal":
            sx.append(("=", "".join(x[i1:i2])))
            sy.append(("=", "".join(y[j1:j2])))
        else:
            if i2 > i1:
                sx.append(("-", "".join(x[i1:i2])))
            if j2 > j1:
                sy.append(("+", "".join(y[j1:j2])))
    return sx, sy


class Baglam:
    """Bolumun TR paragraflari ve hizali ZH gruplari (bir kez kurulur)."""

    def __init__(self, no: int | None):
        self.bloklar, self.gruplar = [], {}
        if no is None:
            return
        yol = S.BOLUMLER / f"{no:04d}.md"
        if yol.exists():
            self.bloklar = S.tr_bloklari(yol.read_text(encoding="utf-8"))
        try:
            from gruplar import gruplar
            self.gruplar = gruplar(no, "tr")
        except Exception:  # hizalama yoksa yalniz TR gosterilir
            self.gruplar = {}

    def bul(self, madde: dict) -> dict:
        tr, zh, grup = "", "", None
        parca = S.bosluk(madde["eski"])[:40]
        if madde["p"].isdigit() and 1 <= int(madde["p"]) <= len(self.bloklar):
            tr = self.bloklar[int(madde["p"]) - 1]
        if parca and parca not in S.bosluk(tr):
            tr = next((b for b in self.bloklar if parca in S.bosluk(b)), tr)
        ara = parca if len(parca) >= 8 else S.bosluk(tr)[:40]
        if len(ara) >= 8:
            for k, g in self.gruplar.items():
                if ara in S.bosluk(g["TR"]):
                    grup, zh = k, g["ZH"]
                    break
        return {"tr": tr, "zh": zh, "hizalama_grup": grup}


# ------------------------------------------------------------------ sunucu

# ------------------------------------------------------------------ kuyruk

class Kip:
    """Hangi inceleme dosyasi, nasil uygulanir, ne zaman 'islenmis' sayilir."""

    def __init__(self, ad: str, dosya_yolu: Path | None = None):
        self.ad = ad
        self.dosya_yolu = dosya_yolu
        if ad == "ses_ayari":
            import ses_ayari as A
            self.kok, self.dosya, self.betik, self.isaret = A.RAPOR, "inceleme.md", "ses_ayari.py", "uygulandi.json"
        elif ad == "sablon":  # sablon onerileri (sablon_oneri.py)
            import sablon as SB
            self.kok, self.dosya, self.betik, self.isaret = SB.RAPOR, "oneriler.md", "sablon.py", "oneriler_uygulandi.json"
        elif ad == "okuma":  # coklu okuma (okuma.py): tek inceleme.md
            import okuma as O
            self.kok, self.dosya, self.betik, self.isaret = O.RAPOR, "inceleme.md", "okuma.py", O.KARARLAR_ISLENDI
        else:
            self.kok, self.dosya, self.betik, self.isaret = S.RAPOR, "5_inceleme.md", "sonra.py", S.KARARLAR_ISLENDI

    def yol(self, no) -> Path:
        if self.ad == "okuma":
            if self.dosya_yolu is not None:
                return self.dosya_yolu
            return self.kok / str(no) / self.dosya
        return self.kok / f"Ch_{no}" / self.dosya

    def islenmis(self, no) -> bool:
        inc = self.yol(no)
        isaret = inc.parent / self.isaret
        if not inc.exists():
            return False
        if not isaret.exists():
            # 7 Kas'tan once islenenlerin isareti yok: karar istatistiginde satiri
            # varsa ve inceleme hem oturum basindaki istatistikten hem de ilk
            # 5_kararlar.json'dan (paylasilan TSV'nin baska bolumle guncellenmesi
            # yeni incelemeyi islenmis saymasin diye) eskiyse islenmis.
            if self.ad != "sonra" or no not in self.istatistikte() or self._ist_mtime is None:
                return False
            en_eski = self._en_eski_isaret()
            sinir = min(self._ist_mtime, en_eski) if en_eski is not None else self._ist_mtime
            return sinir >= inc.stat().st_mtime
        # sonra / okuma: inceleme sonradan yeniden isaretlendiyse yine bekliyor say.
        return self.ad == "ses_ayari" or isaret.stat().st_mtime >= inc.stat().st_mtime

    def _en_eski_isaret(self) -> float | None:
        if not hasattr(self, "_en_eski"):
            zamanlar = [p.stat().st_mtime for p in self.kok.glob(f"Ch_*/{self.isaret}") if p.is_file()]
            self._en_eski = min(zamanlar) if zamanlar else None
        return self._en_eski

    def istatistikte(self) -> set:
        if not hasattr(self, "_ist"):
            self._ist = set()
            self._ist_mtime = None
            if S.ISTATISTIK.exists():
                self._ist_mtime = S.ISTATISTIK.stat().st_mtime
                self._ist = {int(p[0]) for p in S.guncel_istatistik(S.ISTATISTIK)
                             if p[-1] in ("", "sonra")}
        return self._ist

    def hazirlar(self, sonra_: int) -> list:
        """sonra_'dan buyuk, incelemesi hazir ve islenmemis bolumler (sirali)."""
        if self.ad == "okuma":
            return []
        out = []
        for k in self.kok.glob("Ch_*"):
            m = re.fullmatch(r"Ch_(\d+)", k.name)
            if m and int(m.group(1)) > sonra_ and self.yol(int(m.group(1))).exists() \
                    and not self.islenmis(int(m.group(1))):
                out.append(int(m.group(1)))
        return sorted(out)

    def uygula(self, no) -> tuple:
        """(basarili mi, cikti) -- komut satirindaki --kararlar."""
        if self.ad == "okuma":
            cmd = [sys.executable, str(BETIKLER / self.betik), str(no), "--kararlar",
                   "--dosya", str(self.yol(no))]
        else:
            cmd = [sys.executable, str(BETIKLER / self.betik), str(no), "--kararlar"]
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=BETIKLER, timeout=600)
        cikti = (p.stdout.strip().splitlines() or [""])[-1] if p.returncode == 0 else \
            (p.stderr or p.stdout).strip()[-600:]
        return p.returncode == 0, cikti


class Oturum:
    """Sunucunun o an gosterdigi bolum ve kuyrugun geri kalani. Baglam
    (hizalama) bir sonraki bolum icin arka planda onceden kurulur."""

    def __init__(self, kip: Kip | None, kuyruk: list, yol: Path | None = None):
        self.kip, self.kuyruk = kip, list(kuyruk)
        self.no = self.kuyruk.pop(0) if self.kuyruk else None
        self.yol = yol or (kip.yol(self.no) if kip and self.no is not None else None)
        self._baglam, self._baglam_kilit = {}, threading.Lock()
        self.bitti, self.uygulananlar = False, []
        self.baglam = self.baglam_al(self.no if isinstance(self.no, int) else None)
        self.onden_kur()

    def baglam_al(self, no):
        if not isinstance(no, int):
            no = None
        with self._baglam_kilit:
            if no not in self._baglam:
                self._baglam[no] = Baglam(no)
            return self._baglam[no]

    def onden_kur(self):
        if self.kuyruk and isinstance(self.kuyruk[0], int):
            sonraki = self.kuyruk[0]
            threading.Thread(target=self.baglam_al, args=(sonraki,), daemon=True).start()

    def ilerle(self) -> bool:
        while self.kuyruk:
            no = self.kuyruk.pop(0)
            if self.kip.yol(no).exists() and not self.kip.islenmis(no):
                self.no, self.yol = no, self.kip.yol(no)
                self.baglam = self.baglam_al(no if isinstance(no, int) else None)
                self.onden_kur()
                return True
        self.no = None
        self.bitti = True
        return False


def yazilanlar(metin: str) -> list:
    """Hattin bolume zaten yazdigi duzeltmeler, sayfa icin madde bicimiyle."""
    out = []
    for u in S.uygulanan_oku(metin):
        out.append({"k": f"U{u['i']}", "i": u["i"], "tur": "uyg", "bolum": u.get("bolum"),
                    "p": u["p"], "sinif": "UYGULANDI",
                    "kural": u["kural"], "katman": "0. Uygulananlar", "kaynak": u["kaynak"],
                    "otomatik": u["otomatik"], "geri": bool(u["geri"]), "geri_var": u["geri"] is not None,
                    "eski": u["eski"], "yeni": u["yeni"], "neden": "", "ekler": [],
                    "kabul": False, "ret": False, "hep": False})
    return out


def isaretsiz(metin: str) -> int:
    """--kararlar'da hicbir sey olmayacak maddeler (4. katman toplu ret isaretliyse o katman haric)."""
    ms, _, toplu = maddeler(metin)
    karar = {m["k"]: m for m in ms}

    def bos(m):
        o = karar.get(m.get("grup"))
        return not (m["kabul"] or m["ret"]) and not (o and (o["kabul"] or o["ret"]))
    return sum(1 for m in ms if bos(m) and not (toplu and m["katman"].startswith("4.")))


def grup_yaz(metin: str, k: int, kabul: bool, ret: bool, hep: bool, yeni: str | None) -> str:
    """K'yi yazar; K bir grubun onderiyse, onderin onceki kararini tasiyan (ya da bos)
    izleyenler de ayni kabul/ret'i alir. Elle farkli isaretlenen izleyene dokunulmaz."""
    ms, _, _ = maddeler(metin)
    onceki = next((m for m in ms if m["k"] == k), None)
    metin = madde_yaz(metin, k, kabul, ret, hep, yeni)
    if onceki is None:
        return metin
    for m in ms:
        if m.get("grup") == k and (m["kabul"], m["ret"]) in ((False, False), (onceki["kabul"], onceki["ret"])):
            metin = madde_yaz(metin, m["k"], kabul, ret, m["hep"], None)
    return metin


def uygulama(oturum, baglam: Baglam | None = None, kapat=None):
    """oturum: Oturum ya da (eski cagri) inceleme dosyasinin yolu."""
    if not isinstance(oturum, Oturum):
        yol = oturum
        oturum = Oturum.__new__(Oturum)
        oturum.kip, oturum.kuyruk, oturum.no, oturum.yol = None, [], None, Path(yol)
        oturum.baglam, oturum.bitti, oturum.uygulananlar, oturum._baglam = baglam or Baglam(None), False, [], {}
        oturum._baglam_kilit = threading.Lock()

    class Isleyici(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def gonder(self, kod: int, govde: bytes, tur: str):
            self.send_response(kod)
            self.send_header("Content-Type", tur)
            self.send_header("Content-Length", str(len(govde)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(govde)

        def json_gonder(self, veri, kod=200):
            self.gonder(kod, json.dumps(veri, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def durum(self):
            yol, baglam = oturum.yol, oturum.baglam
            metin = yol.read_text(encoding="utf-8")
            ms, toplu_var, toplu = maddeler(metin)
            for m in ms:
                m["fark_eski"], m["fark_yeni"] = farklar(m["eski"], m["yeni"])
                b = oturum.baglam_al(m["bolum"]) if m.get("bolum") is not None else baglam
                m.update(b.bul(m))
            for u in yazilanlar(metin):
                u["fark_eski"], u["fark_yeni"] = farklar(u["eski"], u["yeni"])
                b = oturum.baglam_al(u["bolum"]) if u.get("bolum") is not None else baglam
                u.update(b.bul(dict(u, eski=u["yeni"])))  # bolumde artik ✓ duruyor
                ms.append(u)
            return {"dosya": str(yol), "maddeler": ms, "toplu_var": toplu_var, "toplu": toplu,
                    "bolum": oturum.no, "kuyruk": list(oturum.kuyruk), "isaretsiz": isaretsiz(metin),
                    "uygulanabilir": oturum.kip is not None and oturum.no is not None,
                    "uygulananlar": list(oturum.uygulananlar)}

        def do_GET(self):
            if self.path == "/":
                self.gonder(200, SAYFA.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/api/maddeler":
                with KILIT:
                    veri = self.durum()
                self.json_gonder(veri)
            else:
                self.gonder(404, b"yok", "text/plain")

        def do_POST(self):
            # Yalniz ayni kokenden: baska bir sitenin sayfasi bu porta yazamasin.
            koken = self.headers.get("Origin", "")
            if koken and not re.match(r"^http://(127\.0\.0\.1|localhost):\d+$", koken):
                return self.json_gonder({"hata": "koken reddedildi"}, 403)
            uzunluk = int(self.headers.get("Content-Length") or 0)
            try:
                veri = json.loads(self.rfile.read(uzunluk) or b"{}")
                if self.path == "/api/uygula":
                    return self.uygula()
                with KILIT:
                    yol = oturum.yol
                    metin = yol.read_text(encoding="utf-8")
                    if self.path == "/api/madde":
                        kabul, ret = bool(veri["kabul"]), bool(veri["ret"])
                        if kabul and ret:
                            return self.json_gonder({"hata": "kabul ve ret aynı anda seçilemez"}, 400)
                        metin = grup_yaz(metin, int(veri["k"]), kabul, ret,
                                         bool(veri["hep"]), veri.get("yeni"))
                    elif self.path == "/api/geri":
                        metin = S.geri_yaz(metin, int(veri["i"]), bool(veri["geri"]))
                    elif self.path == "/api/toplu":
                        metin = toplu_yaz(metin, bool(veri["isaret"]))
                    else:
                        return self.json_gonder({"hata": "yok"}, 404)
                    yaz(yol, metin)
                    yanit = self.durum()
            except Exception as e:  # noqa: BLE001
                return self.json_gonder({"hata": f"{type(e).__name__}: {e}"}, 400)
            self.json_gonder(yanit)

        def uygula(self):
            with KILIT:
                if oturum.bitti:
                    return self.json_gonder({"bitti": True, "uygulananlar": list(oturum.uygulananlar)})
                if oturum.kip is None or oturum.no is None:
                    return self.json_gonder({"hata": "bu dosya buradan uygulanamaz (komut satirindan --kararlar)"}, 400)
                no = oturum.no
                no_ad = f"{no}. bölüm" if isinstance(no, int) else str(no)
                tamam, cikti = oturum.kip.uygula(no)
                if not tamam:
                    return self.json_gonder({"hata": f"{no_ad} uygulanamadı: {cikti}"}, 500)
                oturum.uygulananlar.append(f"{no}: {cikti}")
                print(f"  uygulandı {no}: {cikti}", flush=True)
                if oturum.ilerle():
                    veri = self.durum()
                    veri["sonuc"] = f"{no_ad}: {cikti}"
                    return self.json_gonder(veri)
                son_uyg = list(oturum.uygulananlar)
            self.json_gonder({"bitti": True, "sonuc": f"{no_ad}: {cikti}",
                              "uygulananlar": son_uyg})
            if kapat:
                threading.Timer(1.0, kapat).start()
    return Isleyici


SAYFA = r"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>İnceleme</title>
<style>
:root{--bg:#f7f5f0;--fg:#1f1d1a;--soluk:#6b665e;--kart:#fff;--cizgi:#ddd6c8;--eski:#f6d5d0;--yeni:#d3ecd2;
--kabul:#2f7d32;--ret:#b23a2e;--hep:#6a4fb3;--vurgu:#8a5a00}
@media (prefers-color-scheme:dark){:root{--bg:#1b1a18;--fg:#ece8e0;--soluk:#a39d92;--kart:#25231f;--cizgi:#3a3630;
--eski:#5a2a24;--yeni:#21452a;--kabul:#6cc070;--ret:#ec7b6d;--hep:#a68cf0;--vurgu:#e0b050}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--cizgi);padding:10px 16px;display:flex;
gap:12px;align-items:center;flex-wrap:wrap;z-index:2}
header .ilerleme{flex:1;min-width:160px;height:8px;background:var(--cizgi);border-radius:4px;overflow:hidden}
header .ilerleme div{height:100%;background:var(--kabul)}
select,button{font:inherit;color:inherit;background:var(--kart);border:1px solid var(--cizgi);border-radius:6px;padding:4px 10px;cursor:pointer}
main{max-width:1100px;margin:0 auto;padding:16px}
.kart{background:var(--kart);border:1px solid var(--cizgi);border-radius:10px;padding:16px 18px}
.ust{color:var(--soluk);font-size:14px;display:flex;gap:10px;flex-wrap:wrap}
.kural{font-weight:600;margin:6px 0 12px}
.satir{padding:8px 10px;border-radius:6px;margin:6px 0;white-space:pre-wrap}
.satir b{font-weight:400}.sx .d{background:var(--eski);text-decoration:line-through}.sy .d{background:var(--yeni)}
.etiket{display:inline-block;width:1.4em;color:var(--soluk)}
.neden{margin:12px 0;padding:10px;border-left:3px solid var(--vurgu)}
.ek{color:var(--vurgu);font-size:14px}
.baglam{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
@media (max-width:760px){.baglam{grid-template-columns:1fr}}
.baglam div{font-size:15px;color:var(--soluk);border-top:1px solid var(--cizgi);padding-top:8px;white-space:pre-wrap}
.baglam mark{background:var(--eski);color:var(--fg)}
.kutular{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}
.kutular button.acik.kabul{background:var(--kabul);color:#fff;border-color:var(--kabul)}
.kutular button.acik.ret{background:var(--ret);color:#fff;border-color:var(--ret)}
.kutular button.acik.hep{background:var(--hep);color:#fff;border-color:var(--hep)}
textarea{width:100%;min-height:90px;font:inherit;background:var(--bg);color:var(--fg);border:1px solid var(--cizgi);border-radius:6px;padding:8px}
.tuslar{color:var(--soluk);font-size:13px;margin-top:14px}
.liste{margin-top:16px;display:flex;flex-wrap:wrap;gap:4px}
.liste span{font-size:12px;padding:2px 6px;border-radius:4px;border:1px solid var(--cizgi);cursor:pointer}
.liste .k{background:var(--kabul);color:#fff}.liste .r{background:var(--ret);color:#fff}.liste .su{outline:2px solid var(--vurgu)}
.uyari{color:var(--ret)}
.liste .u{border-style:dashed}.liste .u.o{border-color:var(--vurgu)}.liste .u.g{background:var(--ret);color:#fff}
.rozet{font-size:13px;color:var(--vurgu);cursor:pointer;text-decoration:underline dotted}
.kutular button.acik.geri{background:var(--ret);color:#fff;border-color:var(--ret)}
</style></head><body>
<header><strong id="baslik">İnceleme</strong><select id="suzgec"></select><select id="bolumSuzgec" hidden></select>
<span id="sayac"></span><span id="uygRozet" class="rozet" hidden></span><div class="ilerleme"><div id="cubuk" style="width:0"></div></div>
<label id="topluK" hidden><input type="checkbox" id="toplu"> 4. katmanda işaretsizlerin hepsi: ret</label>
<button id="uygula" hidden title="Shift+A">Uygula ve sonraki bölüm (A)</button><span id="kuyruk"></span></header>
<main><div id="kart" class="kart">Yükleniyor…</div><div class="liste" id="liste"></div>
<p class="tuslar">k kabul · r ret · h hep · e ✓ satırını düzenle (Ctrl+Enter kaydet, Esc vazgeç) · → / ← sonraki / önceki ·
n sıradaki işaretsiz · u geri al · g uygulanmış düzeltmeyi geri alınacak diye işaretle · A (Shift+a) kararları uygula ve sıradaki bölümü aç. Her tuş dosyaya hemen yazılır.</p>
<p id="sonuc" class="ek"></p><p id="hata" class="uyari"></p></main>
<script>
let veri=null, sira=0, gecmis=[], duzenle=false, isleniyor=false;
const $=id=>document.getElementById(id);
const esc=s=>(s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function gorunen(){const f=$("suzgec").value, b=$("bolumSuzgec").value;return veri.maddeler.filter(m=>(!f||m.katman===f)&&(!b||String(m.bolum)===b))}
const karar=m=>m.tur!=="uyg";
async function al(){
 try{const r=await fetch("/api/maddeler");veri=await r.json();kur()}
 catch(e){$("hata").textContent=`Sunucuya erişilemedi: ${e}`}
}
async function gonder(yol,govde){
 if(isleniyor) return false;
 isleniyor=true;
 try{
  const r=await fetch(yol,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(govde)});
  const j=await r.json(); if(j.hata){$("hata").textContent=j.hata;return false} $("hata").textContent="";veri=j;kur();return true;
 }catch(e){$("hata").textContent=`İstek başarısız: ${e}`;return false}
 finally{isleniyor=false}
}
function kur(){
 const katmanlar=[...new Set(veri.maddeler.map(m=>m.katman))], s=$("suzgec"), eski=s.value;
 const bolumler=[...new Set(veri.maddeler.map(m=>m.bolum).filter(b=>b!==null&&b!==undefined))].sort((a,b)=>a-b);
 const bs=$("bolumSuzgec"), eskiB=bs.value;
 bs.hidden=bolumler.length<2;
 if(bolumler.length>=2){bs.innerHTML='<option value="">Tüm bölümler</option>'+bolumler.map(b=>`<option value="${b}" ${String(b)===eskiB?"selected":""}>Ch_${b}</option>`).join("")}
 else{bs.value=""}
 const uyg=veri.maddeler.filter(m=>!karar(m)), oto=uyg.filter(m=>m.otomatik).length, geri=uyg.filter(m=>m.geri).length;
 $("uygRozet").hidden=!uyg.length;
 $("uygRozet").textContent=`uygulanan ${uyg.length}${oto?` (${oto} otomatik)`:""}${geri?` · ${geri} geri alınacak`:""}`;
 s.innerHTML='<option value="">Hepsi</option>'+katmanlar.map(k=>`<option ${k===eski?"selected":""}>${esc(k)}</option>`).join("");
 $("baslik").textContent=veri.dosya.split("/").slice(-2).join("/");
 $("uygula").hidden=!veri.uygulanabilir;
 $("uygula").textContent=veri.kuyruk&&veri.kuyruk.length?`Uygula ve ${veri.kuyruk[0]}. bölüme geç (A)`:"Uygula ve bitir (A)";
 $("kuyruk").textContent=veri.kuyruk&&veri.kuyruk.length?`sırada: ${veri.kuyruk.join(", ")}`:"";
 $("topluK").hidden=!veri.toplu_var; $("toplu").checked=veri.toplu;
 const g=gorunen().filter(karar), bitti=g.filter(m=>m.kabul||m.ret).length;
 $("sayac").textContent=`${bitti}/${g.length}`; $("cubuk").style.width=(g.length?100*bitti/g.length:0)+"%";
 const tum=gorunen().length; if(sira>=tum) sira=Math.max(0,tum-1); goster();
}
function parcalar(p){return p.map(([t,s])=>t==="="?esc(s):`<b class="d">${esc(s)}</b>`).join("")}
function goster(){
 const g=gorunen(), m=g[sira];
 $("liste").innerHTML=g.map((x,i)=>{
  const bt=x.bolum!=null?`Ch_${x.bolum} ¶${x.p}`:`¶${x.p}`;
  return karar(x)?`<span class="${x.kabul?"k":x.ret?"r":""} ${i===sira?"su":""}" data-i="${i}" title="${esc(bt)}">K${x.k}</span>`
   :`<span class="u ${x.otomatik?"o":""} ${x.geri?"g":""} ${i===sira?"su":""}" data-i="${i}" title="${esc(bt)} · ${x.otomatik?"otomatik":"kesin"}">${x.k}</span>`;
 }).join("");
 if(!m){$("kart").textContent="Bu süzgeçte madde yok.";return}
 let tr=esc(m.tr); const ip=esc(((karar(m)?m.eski:m.yeni)||"").slice(0,60));
 if(ip&&tr.includes(ip)) tr=tr.replace(ip,()=>`<mark>${ip}</mark>`);
 const bRozet=m.bolum!=null?`<span><strong>Ch_${m.bolum}</strong></span>`:"";
 if(!karar(m)){$("kart").innerHTML=`<div class="ust"><span>${m.k}</span>${bRozet}<span>¶${esc(m.p)}${m.hizalama_grup?` · hizalama ¶${m.hizalama_grup}`:""}</span>
 <span>${m.otomatik?"otomatik uygulandı":"kesin, uygulandı"}</span><span>${esc(m.kaynak)}</span><span>${sira+1}/${g.length}</span></div>
 <div class="kural">${esc(m.kural)}</div>
 <div class="satir sx"><span class="etiket">✗</span>${parcalar(m.fark_eski)}</div>
 <div class="satir sy"><span class="etiket">✓</span>${parcalar(m.fark_yeni)}</div>
 <div class="kutular">${m.geri_var?`<button class="geri ${m.geri?"acik":""}" data-a="g">${m.geri?"geri alınacak (g)":"geri al (g)"}</button>`
  :`<span class="ek">Bu dosya eski biçimde; geri almak için yedekten dönün.</span>`}</div>
 <div class="baglam"><div><strong>TR</strong>\n${tr||"(paragraf bulunamadı)"}</div><div><strong>ZH</strong>\n${esc(m.zh)||"(hizalama yok)"}</div></div>`;return}
 $("kart").innerHTML=`<div class="ust"><span>K${m.k}</span>${bRozet}<span>¶${esc(m.p)}${m.hizalama_grup?` · hizalama ¶${m.hizalama_grup}`:""}</span>
 <span>${esc(m.katman)}</span><span>${esc(m.kaynak)}</span><span>${sira+1}/${g.length}</span></div>
 <div class="kural">${esc(m.kural)}</div>
 <div class="satir sx"><span class="etiket">✗</span>${parcalar(m.fark_eski)}</div>
 ${duzenle?`<textarea id="duz">${esc(m.yeni)}</textarea>`:`<div class="satir sy"><span class="etiket">✓</span>${parcalar(m.fark_yeni)}</div>`}
 <div class="neden">${esc(m.neden)}</div>${m.ekler.map(e=>`<div class="ek">${esc(e)}</div>`).join("")}
 <div class="kutular"><button class="kabul ${m.kabul?"acik":""}" data-a="k">kabul (k)</button>
 <button class="ret ${m.ret?"acik":""}" data-a="r">ret (r)</button><button class="hep ${m.hep?"acik":""}" data-a="h">hep (h)</button>
 <button data-a="e">düzenle (e)</button></div>
 <div class="baglam"><div><strong>TR</strong>\n${tr||"(paragraf bulunamadı)"}</div><div><strong>ZH</strong>\n${esc(m.zh)||"(hizalama yok)"}</div></div>`;
 if(duzenle){const t=$("duz");t.focus();t.setSelectionRange(t.value.length,t.value.length)}
}
async function isle(m,degisim){
 const onceki={k:m.k,kabul:m.kabul,ret:m.ret,hep:m.hep,yeni:m.yeni};
 const yeni=Object.assign({k:m.k,kabul:m.kabul,ret:m.ret,hep:m.hep},degisim);
 if(await gonder("/api/madde",yeni)){gecmis.push({yol:"/api/madde",govde:onceki});return true}
 return false;
}
async function eylem(a){
 if(isleniyor) return;
 const g=gorunen(), m=g[sira]; if(!m) return;
 if(!karar(m)){
  if(a==="g"&&m.geri_var){
   const onceki={i:m.i,geri:m.geri};
   if(await gonder("/api/geri",{i:m.i,geri:!m.geri})) gecmis.push({yol:"/api/geri",govde:onceki});
  }
  return;
 }
 if(a==="k"){if(await isle(m,{kabul:!m.kabul,ret:false})&&!m.kabul) ileri()}
 else if(a==="r"){if(await isle(m,{ret:!m.ret,kabul:false})&&!m.ret) ileri()}
 else if(a==="h") await isle(m,{hep:!m.hep});
 else if(a==="e"){duzenle=true;goster()}
}
let uyguluyor=false;
async function uygula(){
 if(!veri||!veri.uygulanabilir||uyguluyor) return;
 const bas=typeof veri.bolum==="number"?`${veri.bolum}. bölümde`:`${veri.bolum} için`;
 if(veri.isaretsiz&&!confirm(`${bas} ${veri.isaretsiz} işaretsiz madde var; uygulanmayacaklar (kutusu boş kalır). Yine de uygulansın mı?`)) return;
 uyguluyor=true; $("uygula").disabled=true; $("sonuc").textContent=`${veri.bolum} uygulanıyor…`;
 try{
  const r=await fetch("/api/uygula",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
  const j=await r.json();
  if(j.hata){$("hata").textContent=j.hata;$("sonuc").textContent="";return}
  $("hata").textContent=""; $("sonuc").textContent=j.sonuc||"";
  if(j.bitti){
   document.querySelector("main").innerHTML=`<div class="kart"><strong>Bitti.</strong><p>${(j.uygulananlar||[]).map(esc).join("<br>")}</p><p class="tuslar">Sunucu kapandı; bu sekmeyi kapatabilirsiniz.</p></div>`;
   document.querySelector("header").hidden=true; setTimeout(()=>window.close(),1500); return}
  veri=j; sira=0; gecmis=[]; duzenle=false; $("suzgec").value=""; $("bolumSuzgec").value=""; kur(); window.scrollTo(0,0);
 }catch(e){$("hata").textContent=`Uygulama başarısız: ${e}`;$("sonuc").textContent=""}
 finally {uyguluyor=false; $("uygula").disabled=false}
}
$("uygula").addEventListener("click",uygula);
function ileri(){const g=gorunen(); if(sira<g.length-1) sira++; goster()}
function sonrakiBos(){const g=gorunen(); for(let i=1;i<=g.length;i++){const j=(sira+i)%g.length; if(karar(g[j])&&!g[j].kabul&&!g[j].ret){sira=j;break}} goster()}
$("uygRozet").addEventListener("click",()=>{$("suzgec").value="0. Uygulananlar";sira=0;kur()});
document.addEventListener("click",e=>{const a=e.target.dataset.a; if(a) eylem(a);
 const i=e.target.dataset.i; if(i!==undefined){sira=+i;duzenle=false;goster()}});
$("suzgec").addEventListener("change",()=>{sira=0;kur()});
$("bolumSuzgec").addEventListener("change",()=>{sira=0;kur()});
$("toplu").addEventListener("change",e=>gonder("/api/toplu",{isaret:e.target.checked}));
document.addEventListener("keydown",async e=>{
 if(duzenle){ if(e.key==="Escape"){duzenle=false;goster()}
  else if(e.key==="Enter"&&(e.ctrlKey||e.metaKey)){const m=gorunen()[sira];duzenle=false;await isle(m,{yeni:$("duz").value})}
  return}
 if(e.ctrlKey||e.metaKey||e.altKey) return;
 if(e.target.tagName==="SELECT") return;
 const t=e.key;
 if(t==="k"||t==="r"||t==="h"||t==="e"||t==="g"){e.preventDefault();eylem(t)}
 else if(t==="ArrowRight"){sira=Math.max(0,Math.min(sira+1,gorunen().length-1));goster()}
 else if(t==="ArrowLeft"){sira=Math.max(sira-1,0);goster()}
 else if(t==="n") sonrakiBos();
 else if(t==="u"){const o=gecmis.pop(); if(o) await gonder(o.yol,o.govde)}
 else if(t==="A"){e.preventDefault();uygula()}
});
al();
</script></body></html>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="5_inceleme.md için yerel inceleme sayfası.")
    ap.add_argument("no", nargs="?", help="bölüm, aralık ya da liste: 9, 20-25, 20,22,24")
    ap.add_argument("--okuma", metavar="ARALIK",
                    help="okuma.py'nin tek inceleme.md dosyasını aç (ör. 1-20 ya da etiket)")
    ap.add_argument("--dosya", type=Path, help="başka bir inceleme dosyası (ör. ses_ayari, okuma)")
    ap.add_argument("--bolum", type=int, help="--dosya ile: bağlam için bölüm numarası")
    ap.add_argument("--tek", action="store_true", help="kuyruk yok: yalnız bu bölüm")
    ap.add_argument("--port", type=int, default=0, help="varsayılan: boş bir port")
    ap.add_argument("--acma", action="store_true", help="tarayıcıyı açma")
    a = ap.parse_args(argv)
    if a.dosya and a.dosya.resolve().name == S.INCELEME_ONIZLEME:
        ap.error("önizleme dosyasında karar işlenemez")
    if a.okuma:
        import okuma as O
        etiket = a.okuma
        yol = O.RAPOR / etiket / "inceleme.md"
        if not yol.exists():
            try:
                etiket = O.aralik_etiketi(S.lotm.bolum_listesi(a.okuma))
                yol = O.RAPOR / etiket / "inceleme.md"
            except ValueError:
                pass
        if not yol.exists():
            print(f"YOK: {yol}")
            return 1
        kip = Kip("okuma", dosya_yolu=yol.resolve())
        oturum = Oturum(kip, [etiket], yol=yol.resolve())
        no = None
    elif a.dosya:
        yol, no = a.dosya.resolve(), a.bolum
        if not yol.exists():
            print(f"YOK: {yol}")
            return 1
        if no is None:
            m = re.search(r"Ch_(\d+)", str(yol))
            no = int(m.group(1)) if m else None
        kip = None
        for ad in ("ses_ayari", "sonra", "sablon"):
            k = Kip(ad)
            if no is not None and k.yol(no).resolve() == yol:
                kip = k
        if kip is None:
            try:
                import okuma as O
                if O.RAPOR.resolve() in yol.parents and yol.name == "inceleme.md":
                    kip = Kip("okuma", dosya_yolu=yol)
            except Exception:
                pass
        if kip is not None and kip.ad == "okuma":
            oturum = Oturum(kip, [yol.parent.name], yol=yol)
        else:
            kuyruk = [no] + ([] if a.tek or kip is None else kip.hazirlar(no)) if no is not None else []
            oturum = Oturum(kip, kuyruk, yol=yol) if kuyruk else None
            if oturum is None:
                oturum = yol
    elif a.no is not None:
        try:
            nolar = S.lotm.bolum_listesi(a.no)
        except ValueError as e:
            ap.error(str(e))
        kip = Kip("sonra")
        if len(nolar) == 1:
            kuyruk = nolar + ([] if a.tek else kip.hazirlar(nolar[0]))
        else:
            kuyruk = [n for n in nolar if kip.yol(n).exists() and not kip.islenmis(n)]
            atlanan = [n for n in nolar if n not in kuyruk]
            if atlanan:
                print(f"atlandı (inceleme yok ya da kararları işlenmiş): {', '.join(map(str, atlanan))}")
            if not kuyruk:
                print("incelenecek bölüm yok.")
                return 1
        if not kip.yol(kuyruk[0]).exists():
            print(f"YOK: {kip.yol(kuyruk[0])}")
            return 1
        print("bağlam kuruluyor (hizalama)...", flush=True)
        oturum = Oturum(kip, kuyruk)
        yol = oturum.yol
    else:
        ap.error("bölüm numarası ya da --dosya verin")
    if not Path(yol).exists():
        print(f"YOK: {yol}")
        return 1
    if not isinstance(oturum, Oturum):
        print("bağlam kuruluyor (hizalama)...", flush=True)
    sunucu = ThreadingHTTPServer(("127.0.0.1", a.port), None)
    sunucu.RequestHandlerClass = uygulama(oturum, Baglam(no) if not isinstance(oturum, Oturum) else None,
                                          kapat=sunucu.shutdown)
    adres = f"http://127.0.0.1:{sunucu.server_address[1]}/"
    sira = f"\n  sırada: {', '.join(map(str, oturum.kuyruk))}" if isinstance(oturum, Oturum) and oturum.kuyruk else ""
    print(f"İnceleme sayfası: {adres}\n  dosya: {yol}{sira}\n  kapatmak için Ctrl+C", flush=True)
    if not a.acma:
        threading.Timer(0.5, lambda: webbrowser.open(adres)).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nkapandı")
        return 0
    if isinstance(oturum, Oturum) and oturum.uygulananlar:
        print("uygulananlar:\n  " + "\n  ".join(oturum.uygulananlar))
    print("bitti, sunucu kapandı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
