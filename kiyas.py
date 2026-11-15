#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kiyas.py -- "Betikleri degistirdim; gercek korpustaki cikti degisti mi?"

Birim testler (tests/) yalniz sentetik veriyle kosar; "gercek veride cikti
oldugu gibi kaldi" sorusunu yalniz bu betik yanitlar. Performans
yeniden yazimlarinda tek guvence bir at-hoc betikti (denek.py); burada kalici
ve testli hali var.

Is akisi:
    ./calistir.sh kiyas --taban-yaz     betikleri degistirmeden ONCE: tabani al
    ... betikleri degistir ...
    ./calistir.sh kiyas                 ayni komutlari yeniden kos, farki raporla

Her adim gercek veriyle (LOTM_KOK) bir komut kosar; stdout, stderr, cikis kodu
ve urettigi dosyalar Reports/kiyas/taban/<adim>/ altina yazilir. Karsilastirma
bayt bayt; tek istisna yol normallestirmesi (betik klasoru, cikti klasoru,
proje koku yer tutucuya cevrilir) ve asagidaki kucuk NORMALLESTIRICI tablosu
(kosudan kosuya degisen satirlar: gecen sure, onbellek ilk kosuda yazdirdigi
satirlar).

ADIM TABLOSU VE SALT-OKUNUR KURALI
----------------------------------
Her adim YALNIZ {CIKTI} klasorune yazan bir komut olmalidir (bulgu dosyalari
--bulgular / --cikti / --rapor ile oraya yonlendirilir). Siteye, Tools/'a,
tabanlara (lint/*-taban.tsv) yazan, kanca kuran, ya da bir model cagiran adim
EKLENMEZ: bu betik rutin olarak, hic dusunmeden kosulur. --uygula, --yaz,
--otomatik gibi bayraklar bu yuzden tabloda gecmez. Tek kabul edilmis yan
etki: toplu_denetle.py betikler klasorundeki .hizalama_onbellek/'i doldurur
(ilk kosu yavas, sonrakiler hizli; onbellek icerik adresli, sonucu degistirmez).

Bolum numaralari koda gomulu degildir: tabani alirken veriden secilir (en son
yayimlanmis bolum N, kaynakta varsa N+1, ortada bir ornek bolum, son 10 bolum)
ve COZULMUS komut satirlari tabanla birlikte adimlar.json'a yazilir. Karsilastirma
tabandaki komutlari aynen kosar; arada yeni bolum yayimlansa bile. Girdisi
olmayan adim (ornegin sablon Ch_N.md yok) tabandan notla birlikte cikarilir.

VERI PARMAK IZI
---------------
Cikti kodun oldugu kadar veriye de baglidir. Taban, girdilerin parmak izini de
saklar (site _data/*.yml ve _chapters/*.md, words.md, Voice_Maps, Prompts,
Schemas: icerik ozeti; Source/'taki buyuk dosyalar: boyut+mtime). Karsilastirmada
parmak izi degismisse hangi girdilerin degistigi (gruplanmis) basta yazilir:
alttaki farklar koddan degil veriden gelebilir. Yine de karsilastirma yapilir.

Cikis kodu: 0 hepsi ayni, 1 fark var (FARKLI/YENI/EKSIK), 2 taban yok ya da
kullanim hatasi.

Kullanim:
    kiyas.py                     karsilastir (tum adimlar)
    kiyas.py takvim lint         yalniz bu adimlar
    kiyas.py --taban-yaz         tabani al (var olani --uzerine-yaz olmadan ezmez)
    kiyas.py --liste             adimlari ve komutlarini goster
    kiyas.py --seri              adimlar tek tek (dogru sureler icin)
    kiyas.py --isci N            paralel adim sayisi (varsayilan cekirdegin yarisi, en cok 8)
    kiyas.py --sure SN           adim basina zaman asimi (varsayilan 900)
LOTM_KIYAS cikti kokunu degistirir (varsayilan: <betikler>/Reports/kiyas).
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lotm  # noqa: E402

ZAMAN_ASIMI = "ZAMAN-ASIMI"
YER_TUTUCULAR = ("BETIK", "CIKTI", "KOK", "KELIMELER")

# Kosudan kosuya degisen satirlar: adim -> [(akim, regex, yerine)]. "*" tum adimlar,
# akim: stdout | stderr | dosya | hepsi. Regex satir bazli (re.M); yerine "" ise
# eslesen satir (sonundaki satir sonuyla) silinir. Tum akimi yok saymak yerine
# yalniz dalgali satir elenir ki gercek bir fark yine yakalansin.
NORMALLESTIRICI = {
    # Hizalama onbellegi soguksa "12 bolum hizalanacak..." yazar, sicakken yazmaz.
    "*": [("stderr", r"^\d+ bolum hizalanacak.*\n", "")],
    # hazirla_dogrula gecen saniyeyi stderr'e yazar ("64: 4s"); terim sayisi gibi
    # yanindaki bilgi kalsin diye yalniz "<sayi>s" belirteci "Ns" yapilir.
    "dogrula": [("stderr", r"(?<![\w.])\d+s\b", "Ns")],
}


# ------------------------------------------------------------------ yollar

def kiyas_koku() -> Path:
    """LOTM_KIYAS ya da <betikler>/Reports/kiyas. Cagri aninda okunur (testler ayarlar)."""
    return Path(os.environ.get("LOTM_KIYAS") or lotm.BETIK_KOK / "Reports" / "kiyas")


def eslemeler(cikti: Path | None = None) -> list:
    """[(gercek yol, '<YER>')] -- en uzun yol once, ki ic ice yollar dogru yer tutucuya donussun."""
    adaylar = []
    if cikti is not None:
        adaylar.append((cikti, "<CIKTI>"))
    adaylar += [(lotm.BETIK_KOK, "<BETIK>"), (lotm.KOK, "<KOK>")]
    cikis = []
    for yol, ad in adaylar:
        for s in {str(yol), str(Path(yol).resolve())}:
            if s and s != "/":
                cikis.append((s, ad))
    return sorted(cikis, key=lambda x: -len(x[0]))


def yol_normallestir(veri: bytes, esle: list) -> bytes:
    for yol, ad in esle:
        veri = veri.replace(yol.encode(), ad.encode())
    return veri


def yer_tutucu_ac(arg: str, cikti: Path) -> str:
    """Saklanan komuttaki {BETIK} {CIKTI} {KOK} {KELIMELER}'i bu kosunun yollarina cevirir."""
    deger = {"BETIK": lotm.BETIK_KOK, "CIKTI": cikti, "KOK": lotm.KOK, "KELIMELER": lotm.KELIMELER}
    for ad, yol in deger.items():
        arg = arg.replace("{" + ad + "}", str(yol))
    return arg


# ------------------------------------------------------------------ adim tablosu

def _gore(yol) -> str:
    """Yolu tasinabilir yazar: {KOK}/... (proje kokunun altindaysa)."""
    yol = Path(yol)
    try:
        return "{KOK}/" + yol.relative_to(lotm.KOK).as_posix()
    except ValueError:
        return str(yol)


def yayimlanmis_bolumler() -> list:
    return sorted(int(p.stem) for p in lotm.BOLUMLER_TR.glob("*.md") if re.fullmatch(r"\d+", p.stem))


def adim_tablosu() -> tuple:
    """(adimlar, notlar). adimlar: {ad: {"komut": [...], "gerekli": [...]}}.

    komut: betik klasorunden kosulan argumanlar (yorumlayici hariç); yer tutuculu.
    gerekli: yoksa adimin tabandan cikarilacagi girdi dosyalari."""
    notlar = []
    bolumler = yayimlanmis_bolumler()
    if not bolumler:
        raise SystemExit("kiyas: yayimlanmis bolum yok, adim secilemez")
    n = bolumler[-1]
    sema = lotm.KOK / "Tools" / "Schemas"

    def sablonlu(c):
        return (sema / f"Ch_{c}.md").exists() and c in bolumler

    orta = n // 2
    for c in range(orta, 0, -1):  # sablonu olan en yakin orta bolum
        if sablonlu(c):
            orta = c
            break
    site, soz = _gore(lotm.SITE), _gore(lotm.SOZLUK_YOLU)
    bol = site + "/_chapters"
    ch = [_gore(p) for p in sorted(lotm.BOLUMLER_TR.glob("*.md"))]
    belge = [_gore(p) for p in sorted((lotm.KOK / "Tools" / "Voice_Maps").glob("*.md"))
             + sorted((lotm.KOK / "Tools" / "Prompts").glob("*.md"))]
    kel = "{KELIMELER}"
    a = {
        "kontrol": ["lotm.py", "kontrol"],
        "takvim": ["takvim_denetle.py"],
        "denetim": ["yayim_denetle.py", "--sozluk", soz, "--bolumler", bol,
                    "--kurallar", "lint/lint-kurallari.yml", "--bulgular", "{CIKTI}/b_denetim.tsv", "--envanter"],
        "denetim_hepsi": ["yayim_denetle.py", "--sozluk", soz, "--bolumler", bol, "--hepsi"],
        "lint": ["lint/sozluk_lint.py", "--sozluk", soz, "--kurallar", "lint/lint-kurallari.yml",
                 "--kaynak", "--bulgular", "{CIKTI}/b_lint.tsv", *ch],
        "lint_duzelt": ["lint/sozluk_lint.py", "--duzelt", "--kurallar", "lint/lint-kurallari.yml", *ch],
        "bicim": ["bicim_denetle.py", "--bolumler", bol, "--sozluk", soz, "--taban", "lint/bicim-taban.tsv",
                  "--bulgular", "{CIKTI}/b_bicim.tsv"],
        "sapka": ["lint/sapka.py", "--sozluk", soz, "--kelimeler", kel, "--taban", "lint/sapka-taban.tsv", *ch],
        "sapka_belge": ["lint/sapka.py", "--sozluk", soz, "--kelimeler", kel, "--taban", "lint/sapka-taban.tsv", *belge],
        "sapka_kesif": ["lint/sapka.py", "--kesif", *ch],
        "toplu": ["toplu_denetle.py", "--kaynak", "ikisi", "--bulgular", "{CIKTI}/b_toplu.tsv"],
        "toplu_ayrinti": ["toplu_denetle.py", "--kaynak", "ikisi", "--ayrinti", "Ruhaniyet"],
        "belgeler": ["belge_denetle.py", "--sozluk", soz, "--bulgular", "{CIKTI}/b_belgeler.tsv", *belge],
        "ciltler": ["ciltler_yaz.py", "--denetle"],
        "duzelt_kuru": ["duzelt.py"],
        "duzelt_son": ["duzelt.py", "sapka", "lint", "bicim", "--bolum", str(n)],
        "hizalama_son": ["hizalama_denetle.py", str(n)],
        "toplu_son": ["toplu_denetle.py", "--kaynak", "ikisi", "--bolum", str(n)],
        "toplu_orta": ["toplu_denetle.py", "--kaynak", "ikisi", "--bolum", str(orta)],
        "bicim_son": ["bicim_denetle.py", str(n), "--bolumler", bol, "--sozluk", soz, "--taban", "lint/bicim-taban.tsv"],
        "o_son": ["o_denetle.py", str(n)],
        "sayi_son": ["sayi_denetle.py", str(n)],
        "sayi_aralik": ["sayi_denetle.py", f"1-{n}"],  # tum bolumleri dener (~8 sn)
        "kapanis_son": ["kapanis_denetle.py", f"{{KOK}}/Tools/Schemas/Ch_{n}.md", "--bolum", str(n)],
        "sablon_son": ["sablon_denetle.py", f"{{KOK}}/Tools/Schemas/Ch_{n}.md", "--bolum", str(n)],
        "sablon_orta": ["sablon_denetle.py", f"{{KOK}}/Tools/Schemas/Ch_{orta}.md", "--bolum", str(orta)],
        "ceviri_ruh": ["ceviri_denetle.py", "灵性", "--kaynak", "zh"],
        "hazirla_orta": ["hazirla.py", str(orta), "--notlar", "--cikti", "{CIKTI}/hazirla_orta.md"],
        "ayrilmis": ["ayrilmis.py", "--cikti", "{CIKTI}/ayrilmis.md"],
        "dogrula": ["hazirla_dogrula.py", f"{max(1, n - 9)}-{n}", "--cikti", "{CIKTI}/dogrula.md"],
        "tarama": ["kapi_denetle.py", "--sozluk", soz, "--kaynak", _gore(lotm.KAYNAK_EN),
                   "--rapor", "{CIKTI}/rapor.tsv"],
    }
    if lotm.bolum_al(n + 1, "zh") is not None:  # N+1 kaynakta varsa: sıradaki bölümün hazırlığı
        a["hazirla_siradaki"] = ["hazirla.py", str(n + 1), "--notlar", "--cikti", "{CIKTI}/hazirla_siradaki.md"]
    else:
        notlar.append(f"hazirla_siradaki: {n + 1}. bolum kaynakta yok")
    # kaynak: argumansiz tarama; betik baska bir calismada yazildi, yoksa
    # (eski kurulum) adim tabandan cikarilir ve not dusulur.
    if (lotm.BETIK_KOK / "kaynak_denetle.py").exists():
        a["kaynak"] = ["kaynak_denetle.py"]
    else:
        notlar.append("kaynak: kaynak_denetle.py yok, adim tabandan cikarildi")
    adimlar = {}
    for ad, komut in a.items():
        # girdi dosyasi: ilk arguman betik; sablon/kapanis adimlarinda ek olarak Ch_N.md
        gerekli = ["{BETIK}/" + komut[0]] + [x for x in komut if x.startswith("{KOK}/Tools/Schemas/")]
        adimlar[ad] = {"komut": komut, "gerekli": gerekli}
    for ad in [x for x in adimlar if x.startswith(("sablon_", "kapanis_"))]:
        sab = [g for g in adimlar[ad]["gerekli"] if g.startswith("{KOK}")]
        if sab and not Path(yer_tutucu_ac(sab[0], Path("."))).exists():
            notlar.append(f"{ad}: sablon yok ({sab[0].replace('{KOK}/', '')}), adim tabandan cikarildi")
            del adimlar[ad]
    notlar.append(f"secilen bolumler: son={n}, orta={orta}, dogrula={max(1, n - 9)}-{n}")
    return adimlar, notlar


# ------------------------------------------------------------------ parmak izi

def _ozet(yol: Path) -> str:
    h = hashlib.sha1()
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return "h:" + h.hexdigest()[:16]


def parmak_al() -> dict:
    """Girdilerin parmak izi: {grup: {goreli_yol: ozet}}."""
    kok, site = lotm.KOK, lotm.SITE
    gruplar = {}

    def topla(grup, dosyalar, taban, kaba=False):
        d = gruplar.setdefault(grup, {})
        for p in dosyalar:
            if p.is_file():
                st = p.stat()
                d[p.relative_to(taban).as_posix()] = f"b:{st.st_size}:{int(st.st_mtime)}" if kaba else _ozet(p)

    topla("site/_data", sorted((site / "_data").glob("*.yml")), site)
    topla("site/_chapters", sorted((site / "_chapters").glob("*.md")), site)
    topla("words.md", [lotm.KELIMELER], lotm.KELIMELER.parent)
    tools = kok / "Tools"
    topla("Tools/Voice_Maps", sorted((tools / "Voice_Maps").glob("*")), tools)
    topla("Tools/Prompts", sorted((tools / "Prompts").glob("*")), tools)  # yalniz ust duzey
    topla("Tools/Schemas", sorted((tools / "Schemas").glob("*")), tools)
    kaynak = kok / "Source"
    buyuk = [p for p in sorted(kaynak.rglob("*")) if p.is_file() and p.stat().st_size >= 1 << 20]
    topla("Source (boyut+mtime)", buyuk, kaynak, kaba=True)
    return gruplar


def parmak_farki(eski: dict, yeni: dict) -> list:
    """[(grup, eklenen, silinen, degisen)] -- yalniz fark olan gruplar; her biri dosya adi listesi."""
    cikis = []
    for g in sorted(set(eski) | set(yeni)):
        a, b = eski.get(g, {}), yeni.get(g, {})
        ek, sil = sorted(set(b) - set(a)), sorted(set(a) - set(b))
        deg = sorted(k for k in set(a) & set(b) if a[k] != b[k])
        if ek or sil or deg:
            cikis.append((g, ek, sil, deg))
    return cikis


def parmak_yaz_rapor(fark: list) -> list:
    satir = ["!" * 72, "VERI DEGISMIS: tabandan beri girdiler degisti; asagidaki farklar koddan degil",
             "veriden gelebilir.", ""]
    for g, ek, sil, deg in fark:
        parca = []
        for ad, liste in (("yeni", ek), ("silinen", sil), ("degisen", deg)):
            if liste:
                ornek = ", ".join(liste[:4]) + (f", ... (+{len(liste) - 4})" if len(liste) > 4 else "")
                parca.append(f"{len(liste)} {ad} [{ornek}]")
        satir.append(f"  {g}: " + "; ".join(parca))
    satir.append("!" * 72)
    return satir


# ------------------------------------------------------------------ calistirma

def adim_kos(ad: str, adim: dict, hedef: Path, sure: int) -> dict:
    """Tek adimi kosar, yol-normallestirilmis ciktiyi hedef/<ad>/ altina yazar. {"sure","kod"} doner."""
    klasor = hedef / ad
    shutil.rmtree(klasor, ignore_errors=True)
    dosya = klasor / "dosya"
    dosya.mkdir(parents=True)
    env = dict(os.environ, LOTM_KOK=str(lotm.KOK), LOTM_KELIMELER=str(lotm.KELIMELER),
               LOTM_SAPKA_TABAN=str(lotm.BETIK_KOK / "lint" / "sapka-taban.tsv"),
               PYTHONDONTWRITEBYTECODE="1",
               PYTHONHASHSEED="0")  # kume sirasi kosudan kosuya degismesin
    komut = [sys.executable, *(yer_tutucu_ac(x, dosya) for x in adim["komut"])]
    t = time.perf_counter()
    # Yeni oturum: zaman asiminda torunlar da oldurulsun, boru acik kalip beklemeyelim.
    p = subprocess.Popen(komut, env=env, cwd=lotm.BETIK_KOK, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = p.communicate(timeout=sure)
        kod = str(p.returncode)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = p.communicate()
        kod = ZAMAN_ASIMI
    dt = time.perf_counter() - t
    esle = eslemeler(dosya)
    (klasor / "stdout.txt").write_bytes(yol_normallestir(out, esle))
    (klasor / "stderr.txt").write_bytes(yol_normallestir(err, esle))
    (klasor / "kod.txt").write_text(kod + "\n")
    for f in dosya.rglob("*"):
        if f.is_file():
            f.write_bytes(yol_normallestir(f.read_bytes(), esle))
    return {"sure": round(dt, 2), "kod": kod}


def hepsini_kos(adimlar: dict, hedef: Path, isci: int, sure: int) -> dict:
    hedef.mkdir(parents=True, exist_ok=True)
    adlar = list(adimlar)

    def is_(ad):
        gerekli = [yer_tutucu_ac(g, hedef) for g in adimlar[ad].get("gerekli", [])]
        eksik = [g for g in gerekli if not Path(g).exists()]
        if eksik:
            return ad, {"eksik": eksik}
        return ad, adim_kos(ad, adimlar[ad], hedef, sure)

    with ThreadPoolExecutor(max(1, isci)) as ex:
        return dict(ex.map(is_, adlar))


# ------------------------------------------------------------------ karsilastirma

def normallestir(ad: str, akim: str, veri: bytes) -> bytes:
    """Adim tablosundaki dalgali satirlari eler (yol normallestirmesi diske yazilirken yapildi)."""
    kurallar = NORMALLESTIRICI.get("*", []) + NORMALLESTIRICI.get(ad, [])
    metin = veri.decode("utf-8", "surrogateescape")
    for kapsam, rx, yerine in kurallar:
        if kapsam in (akim, "hepsi"):
            metin = re.sub(rx, yerine, metin, flags=re.M)
    return metin.encode("utf-8", "surrogateescape")


def adim_dosyalari(klasor: Path) -> dict:
    """{ad: yol}: stdout.txt, stderr.txt, kod.txt ve dosya/ altindakiler."""
    d = {k: klasor / k for k in ("stdout.txt", "stderr.txt", "kod.txt") if (klasor / k).exists()}
    for f in sorted((klasor / "dosya").rglob("*")) if (klasor / "dosya").exists() else []:
        if f.is_file():
            d["dosya/" + f.relative_to(klasor / "dosya").as_posix()] = f
    return d


def adim_karsilastir(ad: str, taban: Path, son: Path) -> list:
    """[(dosya, 'FARKLI'|'tabanda yok'|'sonda yok', diff_satirlari)] -- bos liste = ayni."""
    a, b = adim_dosyalari(taban / ad), adim_dosyalari(son / ad)
    farklar = []
    for k in sorted(set(a) | set(b)):
        if k not in a:
            farklar.append((k, "tabanda yok", []))
        elif k not in b:
            farklar.append((k, "sonda yok", []))
        else:
            akim = {"stdout.txt": "stdout", "stderr.txt": "stderr"}.get(k, "dosya")
            x = normallestir(ad, akim, a[k].read_bytes())
            y = normallestir(ad, akim, b[k].read_bytes())
            if x != y:
                dif = list(difflib.unified_diff(
                    x.decode("utf-8", "replace").splitlines(), y.decode("utf-8", "replace").splitlines(),
                    "taban", "son", lineterm="", n=1))
                farklar.append((k, "FARKLI", dif))
    return farklar


def _sn(s) -> str:
    return f"{s:6.1f}s" if isinstance(s, (int, float)) else "     - "


def karsilastir(adimlar: dict, taban: Path, son: Path, sonuc_taban: dict, sonuc_son: dict,
                secilen: list, diff_satiri: int = 8) -> tuple:
    """(rapor_satirlari, fark_var_mi)."""
    satir, fark_var = [], False
    ayrinti = []
    for ad in secilen:
        s = sonuc_son.get(ad, {})
        t = sonuc_taban.get(ad, {})
        if "eksik" in s:
            durum, notu, fl = "EKSIK", "girdi yok: " + ", ".join(s["eksik"]), []
        elif not (taban / ad).exists():
            durum, notu, fl = "YENI", "tabanda sonucu yok", []
        else:
            fl = adim_karsilastir(ad, taban, son)
            notu = ""
            if s.get("kod") == ZAMAN_ASIMI:
                # Zaman asimi ayni sonuc sayilmaz: ikisi de takilmis olsa bile "ayni" demek yaniltir.
                durum = "FARKLI"
                notu = "ZAMAN ASIMI (adim bitmedi)"
            else:
                durum = "FARKLI" if fl else "AYNI"
        fark_var |= durum != "AYNI"
        satir.append(f"  {durum:<7} {ad:<18} {_sn(s.get('sure'))}  (taban {_sn(t.get('sure')).strip()})"
                     + (f"  {notu}" if notu else ""))
        for dosya, tur, dif in fl:
            ayrinti.append(f"--- {ad} / {dosya}: {tur}")
            ayrinti += ["    " + x for x in dif[:diff_satiri]]
            if len(dif) > diff_satiri:
                ayrinti.append(f"    ... (+{len(dif) - diff_satiri} satir)")
            if tur == "FARKLI":
                ayrinti.append(f"    tamami (normallestiricisiz): diff -u {taban / ad / dosya} "
                               f"{son / ad / dosya}")
    if ayrinti:
        satir += ["", "FARKLAR", *ayrinti]
    return satir, fark_var


# ------------------------------------------------------------------ ana

def _json_yaz(yol: Path, veri) -> None:
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _secim(adimlar: dict, adlar: list):
    yok = [x for x in adlar if x not in adimlar]
    if yok:
        print(f"kiyas: bilinmeyen adim: {', '.join(yok)} (bakin: kiyas.py --liste)")
        return None
    return adlar or list(adimlar)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gercek korpusta cikti degisti mi? (taban ile kiyas)")
    ap.add_argument("adimlar", nargs="*", help="yalniz bu adimlar (karsilastirmada)")
    ap.add_argument("--taban-yaz", action="store_true", help="tabani al")
    ap.add_argument("--uzerine-yaz", action="store_true", help="var olan tabanin ustune yaz")
    ap.add_argument("--liste", action="store_true", help="adimlari goster")
    ap.add_argument("--seri", action="store_true", help="adimlar tek tek (dogru sureler)")
    ap.add_argument("--isci", type=int, default=max(1, min(8, (os.cpu_count() or 2) // 2)))
    ap.add_argument("--sure", type=int, default=900, help="adim basina zaman asimi (sn)")
    a = ap.parse_args(argv)

    kok = kiyas_koku()
    taban, son = kok / "taban", kok / "son"
    isci = 1 if a.seri else a.isci

    if a.liste:
        if (taban / "adimlar.json").exists():
            veri = json.loads((taban / "adimlar.json").read_text(encoding="utf-8"))
            adimlar, notlar, kaynak = veri["adimlar"], veri.get("notlar", []), "taban"
        else:
            (adimlar, notlar), kaynak = adim_tablosu(), "simdiki veriden cozuldu (taban yok)"
        print(f"{len(adimlar)} adim ({kaynak}):")
        for ad, v in adimlar.items():
            print(f"  {ad:<18} {' '.join(v['komut'])[:150]}")
        for n in notlar:
            print(f"  not: {n}")
        return 0

    if a.taban_yaz:
        if a.adimlar:
            print("kiyas: --taban-yaz tum adimlari alir (adim adi verilemez)")
            return 2
        if (taban / "adimlar.json").exists() and not a.uzerine_yaz:
            print(f"kiyas: taban zaten var: {taban}\n"
                  "  Degisiklikten sonra tabani ezmek degisikligi sessizce kabul etmek olur.\n"
                  "  Bilerek yeniden almak icin: kiyas.py --taban-yaz --uzerine-yaz")
            return 2
        adimlar, notlar = adim_tablosu()
        gecici = kok / "taban.yeni"  # yarida kalirsa eski taban bozulmasin
        shutil.rmtree(gecici, ignore_errors=True)
        t = time.perf_counter()
        sonuc = hepsini_kos(adimlar, gecici, isci, a.sure)
        toplam = time.perf_counter() - t
        eksik = [ad for ad, s in sonuc.items() if "eksik" in s]
        if eksik:
            print(f"kiyas: girdisi yok, taban alinamadi: {', '.join(eksik)}")
            shutil.rmtree(gecici, ignore_errors=True)
            return 2
        _json_yaz(gecici / "adimlar.json", {"adimlar": adimlar, "notlar": notlar})
        _json_yaz(gecici / "parmak.json", parmak_al())
        _json_yaz(gecici / "sonuc.json", {"adimlar": sonuc, "isci": isci, "toplam": round(toplam, 1),
                                          "zaman": time.strftime("%Y-%m-%d %H:%M:%S")})
        shutil.rmtree(taban, ignore_errors=True)
        gecici.rename(taban)
        print(f"taban alindi: {taban} ({len(adimlar)} adim, {toplam:.1f} sn, isci={isci})")
        for n in notlar:
            print(f"  not: {n}")
        for ad, s in sonuc.items():
            if s["kod"] == ZAMAN_ASIMI:
                print(f"  UYARI: {ad} zaman asimina ugradi; tabanda 'bitmedi' olarak kayitli")
        return 0

    if not (taban / "adimlar.json").exists():
        print(f"kiyas: taban yok: {taban}\n  once: kiyas.py --taban-yaz   (betikleri degistirmeden ONCE)")
        return 2
    veri = json.loads((taban / "adimlar.json").read_text(encoding="utf-8"))
    adimlar = veri["adimlar"]
    secilen = _secim(adimlar, a.adimlar)
    if secilen is None:
        return 2
    sonuc_taban = json.loads((taban / "sonuc.json").read_text(encoding="utf-8"))["adimlar"]
    shutil.rmtree(son, ignore_errors=True)
    t = time.perf_counter()
    sonuc = hepsini_kos({k: adimlar[k] for k in secilen}, son, isci, a.sure)
    toplam = time.perf_counter() - t
    yeni_parmak = parmak_al()
    _json_yaz(son / "parmak.json", yeni_parmak)
    _json_yaz(son / "sonuc.json", {"adimlar": sonuc, "isci": isci, "toplam": round(toplam, 1)})
    cikti = []
    pf = parmak_farki(json.loads((taban / "parmak.json").read_text(encoding="utf-8")), yeni_parmak)
    if pf:
        cikti += parmak_yaz_rapor(pf) + [""]
    satir, fark_var = karsilastir(adimlar, taban, son, sonuc_taban, sonuc, secilen)
    cikti += [f"kiyas: {len(secilen)} adim, {toplam:.1f} sn ({'seri' if isci == 1 else f'{isci} isci, sureler sisik'})"] + satir
    print("\n".join(cikti))
    print("\nFARK VAR (cikis 1)" if fark_var else "\nHEPSI AYNI")
    return 1 if fark_var else 0


if __name__ == "__main__":
    sys.exit(main())
