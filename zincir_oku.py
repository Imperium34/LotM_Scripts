#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zincir_oku.py -- 'calistir.sh hepsi --otomatik'in ikinci yarisi: zincir
ciktisini bir modele okutur, kesin duzeltmeleri betiklerle uygular.

UST DUZEY SORU: "Bu haftaki tam zincirde yeni ne var, ne duzeltildi?"

Iki is, bu sirayla:
    duzeltme   YALNIZ deterministik duzelticiler: sapka.py --uygula (GUVENLI
               bolumu; ELLE'ye dokunmaz) bolumlere ve belgelere (ses haritalari
               + istemler: model ornekleri taklit eder, eski yazim oradan
               yeni bolume sizar), ciltler_yaz.py (ciltler.yml gerideyse). Model metin yazmaz. Her sey commit'siz kalir:
               'git diff' ile okuyup siz commit'lersiniz.
    okuma      Tools/Prompts/zincir-okuma-istemi.md + Tools/bilinen.md +
               uygulanan duzeltmeler + zincir ciktisi -> claude -p ->
               Reports/haftalik/<tarih>.md. Model yalniz okuyan denetcileri
               calistirabilir (sonra.py triyajiyla ayni izinler).

Bilinen defteri (Tools/bilinen.md): "bu bulgu bilinen / yanlis pozitif"
dediginiz maddeler. Elle yazilir; rapor her seferinde yalniz deftere ve
fark.py'nin "yeni"lerine gore konusur. Eskiden istemin icindeki elle
tutulan anlik goruntu bu isi yapiyordu ve bir ayda bayatladi.

Kullanim:
    zincir_oku.py Reports/haftalik/2026-10-26_zincir.txt
    zincir_oku.py <cikti> --kuru       duzelticileri calistirma, yalniz oku
    zincir_oku.py <cikti> --model opus
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIKLER))

import sonra  # noqa: E402  (claude_komutu, yurut, TRIYAJ_ARACLARI)

KOK = Path(os.environ.get("LOTM_KOK") or BETIKLER.parent)
SITE = KOK / "Imperium34.github.io"
SOZLUK = SITE / "_data" / "sozluk.yml"
BOLUMLER = SITE / "_chapters"
KELIMELER = Path(os.environ.get("LOTM_KELIMELER") or KOK / "Tools" / "words.md")
ISTEM = KOK / "Tools" / "Prompts" / "zincir-okuma-istemi.md"
BELGE_KLASORLERI = [KOK / "Tools" / "Voice_Maps", KOK / "Tools" / "Prompts"]
BILINEN = Path(os.environ.get("LOTM_BILINEN") or KOK / "Tools" / "bilinen.md")
RAPOR = Path(os.environ.get("LOTM_HAFTALIK") or BETIKLER / "Reports" / "haftalik")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def calistir(komut: list, cwd: Path = BETIKLER) -> str:
    p = subprocess.run(komut, capture_output=True, text=True, cwd=cwd)
    return ANSI.sub("", p.stdout + (("\n" + p.stderr) if p.stderr.strip() else "")).strip()


def duzelt() -> str:
    """Deterministik duzelticiler; ne yaptiklarinin ozeti."""
    out = []
    bolumler = sorted(str(p) for p in BOLUMLER.glob("*.md"))
    kel = ["--kelimeler", str(KELIMELER)] if KELIMELER.exists() else []
    s = calistir(["python3", "lint/sapka.py", "--sozluk", str(SOZLUK), *kel, "--uygula", *bolumler])
    # sapka'nin ozeti son satirlarda; listenin tamami zincir ciktisinda zaten var.
    out.append("sapka --uygula (GÜVENLİ), bölümler:\n" + "\n".join(s.splitlines()[-4:]))
    # calistir.sh adim_belgeler ile ayni klasorler.
    belgeler = sorted(str(p) for d in BELGE_KLASORLERI for p in d.glob("*.md"))
    if belgeler:
        s = calistir(["python3", "lint/sapka.py", "--sozluk", str(SOZLUK), *kel, "--uygula", *belgeler])
        out.append("sapka --uygula (GÜVENLİ), belgeler:\n" + "\n".join(s.splitlines()[-4:]))
    c = subprocess.run(["python3", "ciltler_yaz.py", "--denetle"], capture_output=True,
                       text=True, cwd=BETIKLER)
    if c.returncode != 0:
        out.append("ciltler_yaz: " + calistir(["python3", "ciltler_yaz.py"]))
    else:
        out.append("ciltler_yaz: güncel, yazılmadı")
    fark = calistir(["git", "diff", "--stat"], cwd=SITE)
    out.append("site git diff --stat:\n" + (fark or "(değişiklik yok)"))
    fark = calistir(["git", "diff", "--stat", "--", "Voice_Maps", "Prompts"], cwd=KOK / "Tools")
    out.append("Tools git diff --stat (belgeler):\n" + (fark or "(değişiklik yok)"))
    return "\n\n".join(out)


def girdi_metni(zincir: str, duzeltmeler: str) -> str:
    bilinen = BILINEN.read_text(encoding="utf-8").strip() if BILINEN.exists() else "(defter yok)"
    return (f"{ISTEM.read_text(encoding='utf-8').rstrip()}\n\n---\n\n"
            f"<bilinen>\n{bilinen}\n</bilinen>\n\n"
            f"<uygulanan_duzeltmeler>\n{duzeltmeler}\n</uygulanan_duzeltmeler>\n\n"
            f"<zincir_ciktisi>\n{ANSI.sub('', zincir).rstrip()}\n</zincir_ciktisi>\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="hepsi ciktisini oku, kesin duzeltmeleri uygula")
    ap.add_argument("zincir", type=Path, help="calistir.sh hepsi ciktisi")
    ap.add_argument("--kuru", action="store_true", help="duzelticileri calistirma")
    ap.add_argument("--model")
    ap.add_argument("--sure", type=int, default=1800)
    a = ap.parse_args(argv)

    RAPOR.mkdir(parents=True, exist_ok=True)
    tarih = time.strftime("%Y-%m-%d")
    duzeltmeler = "(kuru çalıştırma: düzeltici çalıştırılmadı)" if a.kuru else duzelt()
    print(duzeltmeler)
    girdi = RAPOR / f"{tarih}_girdi.md"
    cikti = RAPOR / f"{tarih}.md"
    girdi.write_text(girdi_metni(a.zincir.read_text(encoding="utf-8"), duzeltmeler), encoding="utf-8")
    if not sonra.yurut(girdi, cikti, a.model, a.sure, sonra.TRIYAJ_ARACLARI):
        print(f"okuma yapilamadi; girdi hazir: {girdi}")
        return 1
    print(f"rapor: {cikti}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
