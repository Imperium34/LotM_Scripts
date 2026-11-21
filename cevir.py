#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cevir.py -- bolumu Claude ile cevirir: sablon denetimi -> ceviri -> bolum
dosyasi -> (istenirse) sonra hatti.

UST DUZEY SORU: "Sablonu hazir bir bolumu tek komutla taslak hâline getir."

once.py ile sonra.py'nin arasindaki eksik halka. Eskiden ceviri elle,
Gemini'ye yapistirilarak yapiliyordu; 31 Ekim karsilastirmalarindan sonra
cevirmen Claude (claude -p). Adimlar:

    denetim   once.py N: sablon (Tools/Schemas/Ch_N.md) var mi, HATA yok mu.
              HATA varsa durulur (--zorla ile gecilir, onerilmez).
    girdi     Reports/ceviri/Ch_N/girdi.md: sablon + ¶ numarali
              ZH/EN hizali metin (harita/gruplar: sablondaki ¶ numaralari
              bunlardir) + gorev blogu. --haritalar ile Klein.md de eklenir
              (sablonun C bolumu zaten bolumdeki sesleri tasir). Sabit
              Cekirdek (lotm.cekirdek_istem(): en yeni Tools/Prompts/
              lotm_system_prompt_vX.Y.md) mesaja girmez, --system-prompt-file
              ile sistem istemi olarak gider (1 Kas'tan beri tek yol).
    ceviri    motorlar.calistir (varsayilan claude -p; --motor codex|antigravity)
              -> cikti_ham.md (+ .motor etiketi claude disi motorda). Girdi degismediyse ve cikti
              varsa model yeniden calismaz (--yeniden ile zorlanir).
    kontrol   Cince harf, baslik, DURUM NOTU, paragraf orani, cift taslak
              (baslik ya da ilk paragraf iki kez). Sert bir sorun varsa
              bolum dosyasi yazilmaz.
    yazim     _chapters/00NN.md (front matter + metin). DURUM NOTU bolume
              girmez, Reports/ceviri/Ch_N/durum_notu.md'ye gider; "Yeni tik"
              satirlari Tools/tikler.md'ye eklenir. [BELIRSIZ]/[ONERI]
              etiketleri metinde kalir (yayim_denetle ve pre-commit yayini
              engeller, sonra'nin okumasi onlari gorur). Var olan bolumun
              ustune yalniz --uzerine-yaz ile yazilir, once yedek alinir
              (LotM/yedek/<tarih>/cevir-<saat>/).
    tarih     takvim_ata kuru calisir; yalniz bu bolumun tarihi degisiyorsa
              --yaz ile tarih verilir, baska bir bolume dokunacaksa yazilmaz.
    sonra     --sonra ile: sonra.py N --otomatik (bolum zinciri + gecisler).

Kullanim:
    cevir.py 70                    cevir, bolumu yaz, sonraki adimi soyle
    cevir.py 70 --sonra            ayni, ardindan sonra --otomatik
    cevir.py 70 --hazirla          yalniz girdi.md (sohbete elle yapistirmak icin)
    cevir.py 70 --kuru             cevir ama bolum dosyasina/tikler.md'ye yazma
    cevir.py 70 --yeniden          cikti varsa da yeniden cevir
    cevir.py 70 --uzerine-yaz      var olan 0070.md'nin ustune (yedekli)
    cevir.py 70 --motor codex      claude yerine codex/antigravity (LOTM_MOTOR_CEVIR ayni)
    --model M, --sure SN, --haritalar, --zorla

Ortam: LOTM_CLAUDE / LOTM_CODEX / LOTM_AGY (komutlar, motorlar.py), LOTM_MOTOR_CEVIR,
LOTM_CEVIRI_RAPOR (rapor klasoru), LOTM_CEKIRDEK (cekirdek istem yolu), LOTM_TIKLER (tik defteri).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIKLER))
sys.path.insert(0, str(BETIKLER / "harita"))

KOK = Path(os.environ.get("LOTM_KOK") or BETIKLER.parent)
import lotm  # noqa: E402  (ortak: yedek_klasoru, cekirdek_istem)
import sonra  # noqa: E402  (yaz_degisirse)
import motorlar as M  # noqa: E402  (claude/codex/antigravity cagrilari)
SITE = KOK / "Imperium34.github.io"
BOLUMLER = SITE / "_chapters"
SABLONLAR = Path(os.environ.get("LOTM_SABLONLAR") or KOK / "Tools" / "Schemas")
HARITALAR = KOK / "Tools" / "Voice_Maps"
RAPOR = Path(os.environ.get("LOTM_CEVIRI_RAPOR") or BETIKLER / "Reports" / "ceviri")
TIKLER = Path(os.environ.get("LOTM_TIKLER") or KOK / "Tools" / "tikler.md")

CJK = re.compile(r"[㐀-鿿豈-﫿]")
BASLIK = re.compile(r"^#{1,3}\s*Bölüm\s+(\d+)\s*[:：—–-]\s*(.+?)\s*$", re.M)
DURUM = re.compile(r"^\s*>?\s*\**\[DURUM NOTU\]\**", re.M)


def cekirdek_yolu() -> Path:
    """En yeni cekirdek istem (lotm.cekirdek_istem; LOTM_CEKIRDEK ayni)."""
    try:
        return lotm.cekirdek_istem()
    except FileNotFoundError as e:
        sys.exit(f"HATA: {e}")


def hizali_kaynak(no: int) -> tuple:
    """(¶ numarali ZH/EN metin, grup sayisi, ZH uzunlugu)."""
    from gruplar import gruplar
    g = gruplar(no, "en")
    if not g:
        sys.exit(f"HATA: {no}. bolumun ZH/EN metni bulunamadi")
    parcalar = [f"¶{k}\nZH: {v['ZH']}\nEN: {v['EN']}" for k, v in g.items()]
    return "\n\n".join(parcalar), len(g), sum(len(v["ZH"]) for v in g.values())


def gorev_blogu(no: int) -> str:
    return (
        "## GÖREV (bu çalıştırma)\n\n"
        f"Aşağıda {no}. bölümün Çince metni ve İngilizce referansı, ¶ numaralı hizalama "
        "gruplarıyla verilmiştir. Şablondaki ¶ numaraları bu gruplardır. Bölüm tek parça "
        "hâlinde gelir.\n\n"
        "Çıktı biçimi, bir betik tarafından okunacağı için kesindir:\n"
        f"1. İlk satır: `## Bölüm {no}: <Türkçe başlık>` (başlık şablonda verildiyse aynen).\n"
        "2. Boş satır, ardından bitmiş Türkçe metin. Her paragraf boş satırla ayrılır. "
        "¶ işareti, Çince, İngilizce, açıklama, önsöz yok.\n"
        "3. En sonda tek bir `[DURUM NOTU]` bloğu (§11).\n\n"
        "Dosya okuma ya da araç kullanma; gereken her şey bu mesajdadır. Yalnızca çeviriyi yaz.\n"
    )


# 21 Kas: agy (gemini) iki kez (Ch82, Ch84) once yarim kalan bir taslak, ardindan
# bastan tam bolumu yazdi. Yalniz claude disi motorlara, mesajin sonuna eklenir.
TEK_KOPYA_NOTU = (
    "\n---\nÖnemli: Bölümü önce baştan sona bitir ve kontrol et, cevabı ancak ondan "
    "sonra yaz. Cevapta bölüm yalnız bir kez ve tam olarak yer alsın: yarım bir taslak "
    "bırakıp baştan yeniden başlama.\n"
)


def cift_taslak(govde: str, no: int) -> str | None:
    """Govdede ikinci bir kopya baslıyorsa (baslik satiri ya da ilk paragraf tekrar) aciklama."""
    m = BASLIK.search(govde)
    if m and int(m.group(1)) == no:
        return f"başlık satırı (`{m.group(0).strip()}`) metinde ikinci kez geçiyor"
    ilk = next((b.strip() for b in re.split(r"\n\s*\n", govde) if b.strip()), "")
    if len(ilk) >= 40 and govde.count(ilk) > 1:
        return f"ilk paragraf metinde ikinci kez geçiyor (`{ilk[:50]}…`)"
    return None


def girdi_kur(no: int, sablon: Path, haritalar: bool) -> tuple:
    """Cekirdek mesaja girmez, --system-prompt-file ile gider."""
    cekirdek = cekirdek_yolu()
    kaynak, grup, zh_boy = hizali_kaynak(no)
    parcalar = ["# BÖLÜM AÇILIŞ ŞABLONU", "", sablon.read_text(encoding="utf-8").rstrip(), ""]
    if haritalar:
        k = HARITALAR / "Klein.md"
        if k.exists():
            parcalar += ["---", "", "# SES HARİTASI: Klein (tam)", "",
                         k.read_text(encoding="utf-8").rstrip(), ""]
    parcalar += ["---", "", gorev_blogu(no), "<kaynak>", kaynak, "</kaynak>", ""]
    return "\n".join(parcalar), cekirdek, grup, zh_boy


yaz_degisirse = sonra.yaz_degisirse


def sistem_argumanlari(sistem: Path) -> list:
    """Claude Code'un kendi (kodlama) sistem isteminin YERINE cekirdek; araclar
    da kapali: ceviri dosya okumaz."""
    return ["--system-prompt-file", str(sistem), "--tools", ""]


def claude_komutu(model: str | None, sistem: Path) -> list:
    """motorlar.claude_komutu (model + efor sabit) + cekirdek sistem istemi."""
    return M.claude_komutu(model) + sistem_argumanlari(sistem)


def motor_adi(motor: str, model: str | None) -> str:
    """tikler.md ve DURUM.md icin: hangi motor/model cevirdi."""
    if motor == "claude":
        return model or os.environ.get("LOTM_MODEL", M.VARSAYILAN_MODEL)
    if motor == "codex":
        m = os.environ.get("LOTM_CODEX_MODEL", M.CODEX_MODEL)
    else:
        m = os.environ.get("LOTM_AGY_MODEL", M.AGY_MODEL)
    return f"{motor}/{m}" if m else motor


def ayristir(ham: str, no: int | None = None) -> dict:
    """Ham ciktidan baslik, govde, durum notu."""
    metin = ham.strip()
    # Model bazen butun ciktiyi ```markdown ... ``` ile sarar.
    cerceve = re.fullmatch(r"```[a-zA-Z0-9_-]*[ \t]*\r?\n(.*?)\r?\n```", metin, re.S)
    if cerceve:
        metin = cerceve.group(1).strip()
    d = DURUM.search(metin)
    ust = metin[:d.start()] if d else metin
    m = BASLIK.search(ust)
    # Baslik yalniz metnin basinda (kisa onsoz varsa ondan hemen sonra) kabul edilir;
    # govde ortasinda ya da DURUM NOTU'ndaki baslik metni yutmasin.
    if m and len(ust[:m.start()].strip()) >= 300:
        m = None
    baslik = m.group(2).strip() if m else None
    if m:
        metin = metin[m.end():]
        d = DURUM.search(metin)
    notu = metin[d.start():].strip() if d else ""
    govde = (metin[:d.start()] if d else metin).strip()
    # Durum notundan once kalan yatay cizgiyi at.
    govde = re.sub(r"\n+-{3,}\s*$", "", govde).strip()
    return {"baslik": baslik, "baslik_no": int(m.group(1)) if m else None,
            "govde": govde, "durum_notu": notu}


def kontrol_et(p: dict, no: int, grup: int) -> tuple:
    """(sert sorunlar, uyarilar, paragraf)."""
    sert, uyari = [], []
    if not p["govde"]:
        sert.append("çeviri metni boş")
    cjk = CJK.findall(p["govde"])
    if cjk:
        sert.append(f"metinde {len(cjk)} Çince harf var (kaynak sızmış olabilir)")
    if re.search(r"^¶\d+|^(ZH|EN):", p["govde"], re.M):
        sert.append("metinde ¶ / ZH: / EN: satırı var")
    if p["baslik"] is None:
        uyari.append("başlık satırı yok (`## Bölüm N: …`); front matter'a başlıksız yazıldı")
    elif p["baslik_no"] != no:
        sert.append(f"başlık numarası {p['baslik_no']}, beklenen {no}")
    if not p["durum_notu"]:
        uyari.append("DURUM NOTU yok: çıktı kesilmiş olabilir, sonu elle kontrol edin")
    paragraf = len([b for b in re.split(r"\n\s*\n", p["govde"]) if b.strip()])
    oran = paragraf / grup if grup else 1
    if oran < 0.7 or oran > 1.5:
        uyari.append(f"paragraf sayısı {paragraf}, kaynak grubu {grup} (oran {oran:.2f}): "
                     "eksik ya da birleşmiş paragraf olabilir")
    cift = cift_taslak(p["govde"], no)
    if cift:
        sert.append(f"çift taslak olabilir: {cift}. Ham çıktıda baştaki yarım kopyayı "
                    f"elle silip `cevir {no}`'i yeniden çalıştırın (model çağrılmaz)")
    etiket = len(re.findall(r"\[BELİRSİZ(?:\]|:)|\[ÖNERİ:", p["govde"]))
    if etiket:
        uyari.append(f"{etiket} [BELİRSİZ]/[ÖNERİ] etiketi metinde (sonra'da çözülür)")
    return sert, uyari, paragraf


def yeni_tikler(notu: str) -> list:
    out = []
    for m in re.finditer(r"Yeni tik:\s*(.+)", notu):
        s = m.group(1).strip().strip("*").strip()
        if s and not re.fullmatch(r"[\"'`]?yok[\"'`.]?", s, re.I):
            out.append(s)
    return out


def tik_ekle(no: int, tikler: list, model: str | None) -> int:
    """Yeni tikleri Tools/tikler.md'ye ekler (ayni bolum + metin varsa atlar); eklenen sayisi."""
    if not tikler:
        return 0
    TIKLER.parent.mkdir(parents=True, exist_ok=True)
    if not TIKLER.exists():
        TIKLER.write_text(
            "# Çevirmen tik defteri\n\n"
            "cevir.py, her çevirinin DURUM NOTU'ndaki \"Yeni tik\" satırını buraya ekler.\n"
            "Bir kalıp iki üç bölümde tekrar ederse çekirdeğin §2/§3/§5 tablosuna işlenir "
            "(ya da bir denetleyiciye dönüşür) ve buradaki satırın başına ✓ konur.\n\n",
            encoding="utf-8")
    eski = TIKLER.read_text(encoding="utf-8")
    var = set()
    for satir in eski.splitlines():
        m = re.match(r"^- (?:✓\s*)?(\d+)\s*·[^·]*·[^·]*·\s*(.+?)\s*$", satir)
        if m:
            var.add((int(m.group(1)), m.group(2)))
    yeni = [t for t in tikler if (no, t) not in var and not var.add((no, t))]
    if not yeni:
        return 0
    m_ad = model or os.environ.get("LOTM_MODEL", M.VARSAYILAN_MODEL)
    satirlar = [f"- {no} · {datetime.now():%Y-%m-%d} · {m_ad} · {t}" for t in yeni]
    with TIKLER.open("a", encoding="utf-8") as f:
        f.write("\n".join(satirlar) + "\n")
    return len(yeni)


def _front_matter(metin: str | None) -> str | None:
    if metin and metin.startswith("---"):
        son = metin.find("\n---", 3)
        if son > 0:
            return metin[: son + 4]
    return None


def bolum_dosyasi(baslik: str | None, no: int, govde: str, eski: str | None) -> str:
    # Var olan dosyanin front matter'i (tarih dahil) korunur, yalniz baslik yenilenir.
    fm = _front_matter(eski)
    if fm is None:
        fm = "---\nlayout: post\ntitle: \"\"\n---"
    if baslik:
        temiz = baslik.replace("\\", "\\\\").replace('"', '\\"')
        satir = f'title: "Bölüm {no}: {temiz}"'
        if re.search(r"^title:.*$", fm, re.M):
            fm = re.sub(r"^title:.*$", lambda _: satir, fm, count=1, flags=re.M)
        else:
            fm = fm[:-3].rstrip("\n") + "\n" + satir + "\n---"
    return f"{fm}\n\n{govde}\n"


def yedekle(yol: Path) -> Path:
    hedef = lotm.yedek_klasoru("cevir")
    hedef.mkdir(parents=True, exist_ok=True)
    shutil.copy2(yol, hedef / yol.name)
    return hedef / yol.name


def tarih_ver(dosya: Path) -> str:
    """takvim_ata kuru; yalniz bu dosya degisiyorsa yaz."""
    ata = [sys.executable, str(BETIKLER / "takvim_ata.py")]
    p = subprocess.run(ata, capture_output=True, text=True, cwd=BETIKLER)
    if p.returncode != 0:
        hata = (p.stderr or p.stdout).strip()[:200]
        return f"takvim: HATA (cikis {p.returncode}) {hata}"
    degisen = [Path(x).name for x in re.findall(r"^\s+(\S+\.md)\s+.*->", p.stdout, re.M)]
    if not degisen:
        return "takvim: değişiklik yok"
    if degisen != [dosya.name]:
        return (f"takvim: yazılmadı, başka bölümler de değişecekti ({', '.join(degisen)}); "
                "./calistir.sh takvim ile bakın")
    q = subprocess.run(ata + ["--yaz"], capture_output=True, text=True, cwd=BETIKLER)
    satir = [s.strip() for s in p.stdout.splitlines() if dosya.name in s]
    return f"takvim: {satir[0] if satir else 'tarih yazıldı'}" if q.returncode == 0 else \
        f"takvim: HATA {q.stderr.strip()[:200]}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bolumu Claude ile cevir.")
    ap.add_argument("no", type=int)
    ap.add_argument("--hazirla", action="store_true", help="yalniz girdi.md")
    ap.add_argument("--kuru", action="store_true", help="bolum dosyasina yazma")
    ap.add_argument("--yeniden", action="store_true", help="cikti varsa da yeniden cevir")
    ap.add_argument("--uzerine-yaz", action="store_true", help="var olan bolumun ustune (yedekli)")
    ap.add_argument("--sonra", action="store_true", help="ardindan sonra.py N --otomatik")
    # 1 Kasim: cekirdek sistem istemi olarak gider (ch69'da B'deki dondurulmus satiri
    # yalniz boyle verilen ceviri tuttu; bkz. Reports/ceviri/Ch_69/karsilastirma.md).
    # Eski --duz (cekirdek mesajin basinda) 7 Kas'ta kaldirildi.
    ap.add_argument("--haritalar", action="store_true", help="Klein.md'yi de ekle")
    ap.add_argument("--zorla", action="store_true", help="sablon HATA verse de cevir")
    # Varsayilan model ve efor sonra.py'de (LOTM_MODEL, LOTM_EFOR): opus, high.
    ap.add_argument("--model", default=os.environ.get("LOTM_CEVIRI_MODEL") or None)
    ap.add_argument("--sure", type=int, default=1800, help="model zaman asimi, sn")
    ap.add_argument("--motor", choices=M.MOTORLAR, default=None,
                    help="ceviri motoru (varsayilan claude; LOTM_MOTOR_CEVIR ayni). --model yalniz "
                         "claude icin; codex/antigravity LOTM_CODEX_MODEL / LOTM_AGY_MODEL")
    a = ap.parse_args(argv)
    no = a.no

    sablon = SABLONLAR / f"Ch_{no}.md"
    hedef = BOLUMLER / f"{no:04d}.md"
    klasor = RAPOR / f"Ch_{no}"
    girdi, ham = klasor / "girdi.md", klasor / "cikti_ham.md"
    durum = [f"# {no}. bölüm — çeviri", ""]

    # 1. denetim
    if not sablon.exists():
        print(f"BEKLIYOR: {sablon} yok. Önce şablon: ./calistir.sh once {no}")
        return 1
    p = subprocess.run([sys.executable, str(BETIKLER / "once.py"), str(no)],
                       capture_output=True, text=True, cwd=BETIKLER)
    ozet = next((s for s in p.stdout.splitlines() if "sablon_denetimi.md" in s), "").strip()
    print(f"şablon: {ozet or '(denetim özeti yok)'}")
    if p.returncode != 0 and not a.zorla:
        print(p.stdout[-1500:])
        print(f"DUR: şablon denetimi HATA verdi (Reports/once/Ch_{no}/sablon_denetimi.md). "
              "Düzeltin ya da --zorla.")
        return 1
    durum.append(f"- Şablon: {ozet}")

    # 2. girdi
    metin, cekirdek, grup, zh_boy = girdi_kur(no, sablon, a.haritalar)
    degisti = yaz_degisirse(girdi, metin)
    durum.append(f"- Çekirdek: {cekirdek.name}; kaynak {grup} grup, {zh_boy} ZH harfi; "
                 f"girdi {len(metin) // 1000} KB")
    print(f"girdi: {girdi} ({len(metin) // 1000} KB, {grup} grup)"
          + ("" if degisti else " — değişmedi"))
    if zh_boy > 20000:
        print("  UYARI: bölüm uzun; tek çağrıda kesilebilir, DURUM NOTU'nu kontrol edin")
    if a.hazirla:
        print(f"--hazirla: model çalıştırılmadı. Elle yapıştırırken çekirdeği ayrıca verin: {cekirdek}")
        return 0

    # 3. ceviri
    motor = M.motor_sec("cevir", {"cevir": a.motor} if a.motor else None)
    en_yeni_girdi = max(girdi.stat().st_mtime, cekirdek.stat().st_mtime)
    taze = (ham.exists() and bool(ham.read_text(encoding="utf-8").strip())
            and ham.stat().st_mtime >= en_yeni_girdi
            and M.etiket_oku(ham) == motor)
    if taze and not a.yeniden:
        print(f"çeviri: {ham.name} güncel, model çalıştırılmadı (--yeniden ile zorlanır)")
    else:
        if motor == "claude":
            komut = claude_komutu(a.model, cekirdek)
            if not shutil.which(komut[0]):
                print(f"YOK: '{komut[0]}' komutu (LOTM_CLAUDE ile verin). girdi.md hazır.")
                return 1
            print(f"çeviri: {' '.join(komut[:8])} ...", flush=True)
            gonder, ek = metin, sistem_argumanlari(cekirdek)
        else:
            # codex/agy'de sistem istemi bayragi yok: cekirdek mesajin basina.
            print(f"  UYARI: {motor} sistem istemi almıyor; çekirdek ({cekirdek.name}) "
                  "girdinin başına eklendi", flush=True)
            gonder = (cekirdek.read_text(encoding="utf-8").rstrip() + "\n\n---\n\n" + metin
                      + TEK_KOPYA_NOTU)
            ek = None
            print(f"çeviri: {motor_adi(motor, a.model)} ...", flush=True)
        t0 = time.time()
        q = M.calistir(gonder, motor, a.model, a.sure, cwd=klasor, ek_argumanlar=ek, gecici=ham)
        if not q.ok:
            return 1
        motor = q.motor
        lotm.atomik_yaz(ham, q.metin)
        M.motor_etiketi_yaz(ham, motor)
        print(f"  {time.time() - t0:.0f} sn, {len(q.metin) // 1000} KB")
    motor = M.etiket_oku(ham)
    if motor != "claude":
        durum.append(f"- Motor: {motor_adi(motor, a.model)} (çekirdek girdinin başında, sistem istemi değil)")

    # 4. kontrol
    parca = ayristir(ham.read_text(encoding="utf-8"), no)
    sert, uyari, paragraf = kontrol_et(parca, no, grup)
    (klasor / "durum_notu.md").write_text(parca["durum_notu"] + "\n", encoding="utf-8")
    durum.append(f"- Çıktı: {paragraf} paragraf, başlık: {parca['baslik'] or '(yok)'}")
    durum += [f"- SERT: {s}" for s in sert] + [f"- Uyarı: {u}" for u in uyari]
    for s in sert:
        print(f"  SERT: {s}")
    for u in uyari:
        print(f"  uyarı: {u}")

    # 5. yazim
    kod = 0
    if sert:
        durum.append(f"- Bölüm dosyası YAZILMADI; ham çıktı {ham}")
        print("DUR: bölüm dosyası yazılmadı, ham çıktıya bakın.")
        kod = 1
    elif a.kuru:
        durum.append("- --kuru: bölüm dosyası yazılmadı")
        print(f"--kuru: {hedef.name} yazılmadı; metin {ham}")
    else:
        eski = hedef.read_text(encoding="utf-8") if hedef.exists() else None
        if eski is not None and not a.uzerine_yaz:
            durum.append(f"- {hedef.name} zaten var; yazılmadı (--uzerine-yaz)")
            print(f"DUR: {hedef.name} zaten var. Üzerine yazmak için --uzerine-yaz (yedek alınır).")
            kod = 1
        else:
            if eski is not None:
                y = yedekle(hedef)
                durum.append(f"- Yedek: {y}")
                print(f"  yedek: {y}")
            hedef.parent.mkdir(parents=True, exist_ok=True)
            lotm.atomik_yaz(hedef, bolum_dosyasi(parca["baslik"], no, parca["govde"], eski))
            durum.append(f"- Yazıldı: {hedef}")
            print(f"yazıldı: {hedef}")
            eski_fm = _front_matter(eski) or ""
            if not re.search(r"^date:", eski_fm, re.M):
                t = tarih_ver(hedef)
                durum.append(f"- {t}")
                print(f"  {t}")
            tikler = yeni_tikler(parca["durum_notu"])
            eklenen = tik_ekle(no, tikler, motor_adi(motor, a.model))
            if eklenen:
                durum.append(f"- {eklenen} yeni tik → {TIKLER.name}")
                print(f"  {eklenen} yeni tik → {TIKLER}")

    (klasor / "DURUM.md").write_text("\n".join(durum) + "\n", encoding="utf-8")
    if kod:
        return kod

    # 6. sonra
    if a.sonra and not a.kuru:
        print(f"\nsonra: ./calistir.sh sonra {no} --otomatik", flush=True)
        args = [sys.executable, str(BETIKLER / "sonra.py"), str(no), "--otomatik"]
        if a.model:
            args += ["--model", a.model]
        return subprocess.run(args, cwd=BETIKLER).returncode
    if not a.kuru:
        print(f"\nSıradaki: ./calistir.sh sonra {no} --otomatik")
    return 0


if __name__ == "__main__":
    sys.exit(main())
