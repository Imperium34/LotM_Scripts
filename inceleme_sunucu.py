#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inceleme_sunucu.py -- 5_inceleme.md icin yerel inceleme sayfasi.

Tek kaynak .md dosyasidir: sayfa her tusta kutulari ve ✓ satirini dosyaya
geri yazar; 'sonra.py N --kararlar' eskisi gibi calisir, dosya elle de
duzenlenebilir (sayfa her istekte dosyayi yeniden okur).

Sayfa: bir seferde bir madde; ✗/✓ satirlari degisen sozcukler isaretli,
Neden, butun TR paragrafi ve hizali ZH paragrafi; katman suzgeci, ilerleme.
Tuslar: k kabul · r ret · h hep · e ✓'yi duzenle · → / ← gezin · u geri al.

Yalniz 127.0.0.1'e baglanir; harici bagimlilik yok (http.server).

Kullanim:
    ./calistir.sh incele 9                       Reports/sonra/Ch_9/5_inceleme.md
    ./calistir.sh incele --dosya Reports/ses_ayari/Ch_72/inceleme.md --bolum 72
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
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
            h = re.match(r"### K(\d+) · ¶(\S+) · (\S+) · (.*)", blok)
            kutu = KUTU.search(blok)
            if not (h and kutu):
                continue

            def satir(on):
                m = re.search(rf"^{on} (.*)$", blok, re.M)
                return m.group(1) if m else ""
            out.append({"k": int(h.group(1)), "p": h.group(2), "sinif": h.group(3), "kural": h.group(4).strip(),
                        "katman": re.sub(r"\s*\(\d+\)$", "", baslik),
                        "eski": satir("✗").replace(" ⏎ ", "\n"), "yeni": satir("✓").replace(" ⏎ ", "\n"),
                        "neden": satir("Neden:"), "kaynak": satir("Kaynak:"),
                        "ekler": [s for s in blok.splitlines()[1:]
                                  if s.startswith(("Dikkat:", "Ön:", "Sadakat:"))],
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
        blok = re.sub(r"^✓ .*$", lambda _: yeni_satir, blok, count=1, flags=re.M)
        x = re.search(r"^✗ (.*)$", blok, re.M)
        if x and re.search(r"^Fark: ", blok, re.M):
            fark = "Fark: " + S.kelime_farki(x.group(1), S.tek_satir(yeni.strip()))
            blok = re.sub(r"^Fark: .*$", lambda _: fark, blok, count=1, flags=re.M)
    return metin[:m.start()] + blok + metin[m.end():]


def toplu_yaz(metin: str, isaret: bool) -> str:
    return re.sub(r"\[.\] Bu bölümdeki işaretsiz", f"[{'x' if isaret else ' '}] Bu bölümdeki işaretsiz", metin, count=1)


def yaz(yol: Path, metin: str) -> None:
    gecici = yol.with_name(yol.name + ".gecici")
    gecici.write_text(metin, encoding="utf-8")
    os.replace(gecici, yol)


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
        if len(parca) >= 8:
            for k, g in self.gruplar.items():
                if parca in S.bosluk(g["TR"]):
                    grup, zh = k, g["ZH"]
                    break
        return {"tr": tr, "zh": zh, "grup": grup}


# ------------------------------------------------------------------ sunucu

def uygulama(yol: Path, baglam: Baglam):
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
            ms, toplu_var, toplu = maddeler(yol.read_text(encoding="utf-8"))
            for m in ms:
                m["fark_eski"], m["fark_yeni"] = farklar(m["eski"], m["yeni"])
                m.update(baglam.bul(m))
            return {"dosya": str(yol), "maddeler": ms, "toplu_var": toplu_var, "toplu": toplu}

        def do_GET(self):
            if self.path == "/":
                self.gonder(200, SAYFA.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/api/maddeler":
                self.json_gonder(self.durum())
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
                with KILIT:
                    metin = yol.read_text(encoding="utf-8")
                    if self.path == "/api/madde":
                        metin = madde_yaz(metin, int(veri["k"]), bool(veri["kabul"]), bool(veri["ret"]),
                                          bool(veri["hep"]), veri.get("yeni"))
                    elif self.path == "/api/toplu":
                        metin = toplu_yaz(metin, bool(veri["isaret"]))
                    else:
                        return self.json_gonder({"hata": "yok"}, 404)
                    yaz(yol, metin)
            except Exception as e:  # noqa: BLE001
                return self.json_gonder({"hata": f"{type(e).__name__}: {e}"}, 400)
            self.json_gonder(self.durum())
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
</style></head><body>
<header><strong id="baslik">İnceleme</strong><select id="suzgec"></select>
<span id="sayac"></span><div class="ilerleme"><div id="cubuk" style="width:0"></div></div>
<label id="topluK" hidden><input type="checkbox" id="toplu"> 4. katmanda işaretsizlerin hepsi: ret</label></header>
<main><div id="kart" class="kart">Yükleniyor…</div><div class="liste" id="liste"></div>
<p class="tuslar">k kabul · r ret · h hep · e ✓ satırını düzenle (Ctrl+Enter kaydet, Esc vazgeç) · → / ← sonraki / önceki ·
n sıradaki işaretsiz · u geri al. Her tuş dosyaya hemen yazılır.</p><p id="hata" class="uyari"></p></main>
<script>
let veri=null, sira=0, gecmis=[], duzenle=false;
const $=id=>document.getElementById(id);
const esc=s=>(s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function gorunen(){const f=$("suzgec").value;return veri.maddeler.filter(m=>!f||m.katman===f)}
async function al(){const r=await fetch("/api/maddeler");veri=await r.json();kur()}
async function gonder(yol,govde){const r=await fetch(yol,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(govde)});
 const j=await r.json(); if(j.hata){$("hata").textContent=j.hata;return false} $("hata").textContent="";veri=j;kur();return true}
function kur(){
 const katmanlar=[...new Set(veri.maddeler.map(m=>m.katman))], s=$("suzgec"), eski=s.value;
 s.innerHTML='<option value="">Hepsi</option>'+katmanlar.map(k=>`<option ${k===eski?"selected":""}>${esc(k)}</option>`).join("");
 $("baslik").textContent=veri.dosya.split("/").slice(-2).join("/");
 $("topluK").hidden=!veri.toplu_var; $("toplu").checked=veri.toplu;
 const g=gorunen(), bitti=g.filter(m=>m.kabul||m.ret).length;
 $("sayac").textContent=`${bitti}/${g.length}`; $("cubuk").style.width=(g.length?100*bitti/g.length:0)+"%";
 if(sira>=g.length) sira=Math.max(0,g.length-1); goster();
}
function parcalar(p){return p.map(([t,s])=>t==="="?esc(s):`<b class="d">${esc(s)}</b>`).join("")}
function goster(){
 const g=gorunen(), m=g[sira];
 $("liste").innerHTML=g.map((x,i)=>`<span class="${x.kabul?"k":x.ret?"r":""} ${i===sira?"su":""}" data-i="${i}">K${x.k}</span>`).join("");
 if(!m){$("kart").textContent="Bu süzgeçte madde yok.";return}
 let tr=esc(m.tr); const ip=esc((m.eski||"").slice(0,60)); if(ip&&tr.includes(ip)) tr=tr.replace(ip,`<mark>${ip}</mark>`);
 $("kart").innerHTML=`<div class="ust"><span>K${m.k}</span><span>¶${esc(m.p)}${m.grup?` · hizalama ¶${m.grup}`:""}</span>
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
 gecmis.push({k:m.k,kabul:m.kabul,ret:m.ret,hep:m.hep,yeni:m.yeni});
 const yeni=Object.assign({k:m.k,kabul:m.kabul,ret:m.ret,hep:m.hep},degisim);
 return gonder("/api/madde",yeni);
}
async function eylem(a){
 const g=gorunen(), m=g[sira]; if(!m) return;
 if(a==="k"){if(await isle(m,{kabul:!m.kabul,ret:false})&&!m.kabul) ileri()}
 else if(a==="r"){if(await isle(m,{ret:!m.ret,kabul:false})&&!m.ret) ileri()}
 else if(a==="h") await isle(m,{hep:!m.hep});
 else if(a==="e"){duzenle=true;goster()}
}
function ileri(){const g=gorunen(); if(sira<g.length-1) sira++; goster()}
function sonrakiBos(){const g=gorunen(); for(let i=1;i<=g.length;i++){const j=(sira+i)%g.length; if(!g[j].kabul&&!g[j].ret){sira=j;break}} goster()}
document.addEventListener("click",e=>{const a=e.target.dataset.a; if(a) eylem(a);
 const i=e.target.dataset.i; if(i!==undefined){sira=+i;duzenle=false;goster()}});
$("suzgec").addEventListener("change",()=>{sira=0;kur()});
$("toplu").addEventListener("change",e=>gonder("/api/toplu",{isaret:e.target.checked}));
document.addEventListener("keydown",async e=>{
 if(duzenle){ if(e.key==="Escape"){duzenle=false;goster()}
  else if(e.key==="Enter"&&(e.ctrlKey||e.metaKey)){const m=gorunen()[sira];duzenle=false;await isle(m,{yeni:$("duz").value})}
  return}
 if(e.target.tagName==="SELECT") return;
 const t=e.key;
 if(t==="k"||t==="r"||t==="h"||t==="e"){e.preventDefault();eylem(t)}
 else if(t==="ArrowRight"){sira=Math.min(sira+1,gorunen().length-1);goster()}
 else if(t==="ArrowLeft"){sira=Math.max(sira-1,0);goster()}
 else if(t==="n") sonrakiBos();
 else if(t==="u"){const o=gecmis.pop(); if(o) await gonder("/api/madde",o)}
});
al();
</script></body></html>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="5_inceleme.md için yerel inceleme sayfası.")
    ap.add_argument("no", nargs="?", type=int, help="bölüm (Reports/sonra/Ch_N/5_inceleme.md)")
    ap.add_argument("--dosya", type=Path, help="başka bir inceleme dosyası (ör. ses_ayari)")
    ap.add_argument("--bolum", type=int, help="--dosya ile: bağlam için bölüm numarası")
    ap.add_argument("--port", type=int, default=0, help="varsayılan: boş bir port")
    ap.add_argument("--acma", action="store_true", help="tarayıcıyı açma")
    a = ap.parse_args(argv)
    if a.dosya:
        yol, no = a.dosya.resolve(), a.bolum
        if no is None:
            m = re.search(r"Ch_(\d+)", str(yol))
            no = int(m.group(1)) if m else None
    elif a.no is not None:
        yol, no = S.RAPOR / f"Ch_{a.no}" / "5_inceleme.md", a.no
    else:
        ap.error("bölüm numarası ya da --dosya verin")
    if not yol.exists():
        print(f"YOK: {yol}")
        return 1
    print("bağlam kuruluyor (hizalama)...", flush=True)
    baglam = Baglam(no)
    sunucu = ThreadingHTTPServer(("127.0.0.1", a.port), uygulama(yol, baglam))
    adres = f"http://127.0.0.1:{sunucu.server_address[1]}/"
    print(f"İnceleme sayfası: {adres}\n  dosya: {yol}\n  kapatmak için Ctrl+C", flush=True)
    if not a.acma:
        threading.Timer(0.5, lambda: webbrowser.open(adres)).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nkapandı")
    return 0


if __name__ == "__main__":
    sys.exit(main())
