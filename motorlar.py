#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
motorlar.py -- butun model cagrilari (claude / codex / antigravity) buradan gecer.

sonra.py (yurut), cevir.py, zincir_oku.py, ses_ayari.py bu modulu kullanir.
Yeni bir betikten:

    import motorlar as M
    motor = M.motor_sec("adim", {"adim": "codex"})   # LOTM_MOTOR_ADIM da olur
    s = M.calistir(metin, motor, model=None, sure=1800, cwd=klasor)
    if s.ok: ... s.metin ...       # s.motor: gercekte kosan motor (geri dusme sonrasi)

Motorlar:
    claude       'claude -p' (LOTM_CLAUDE); girdi stdin'den. Model/efor:
                 LOTM_MODEL (opus), LOTM_EFOR (high). araclar -> --allowedTools.
    codex        'codex exec' (LOTM_CODEX); stdin'den okur, son cevabi
                 --output-last-message dosyasina yazar, -s read-only.
                 LOTM_CODEX_EFOR (high), LOTM_CODEX_MODEL.
    antigravity  'agy' (LOTM_AGY); stdin okumaz, istem -p='...' bayragina yapisik.
                 Girdi 128 KB arguman sinirini asabildigi icin gecici dosyaya
                 yazilir, -p ona isaret eder, sonra silinir. Efor model adinda;
                 --effort yalniz LOTM_AGY_EFOR verilirse. LOTM_AGY_MODEL.
                 Arac izni ayarlanamaz: araclar istenirse claude'a duser.

Kota: KOTA_DOLU bu surecte kotasi dolan motorlar (LOTM_KOTA_DOLU ile ebeveynden
gelir). Kotasi dolan motor bir daha cagrilmaz. Basilan 'HATA' / 'KOTA <motor>'
satirlarini sonra.py'nin paralel ebeveyni kosu.log'da arar: degistirmeyin.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent

# Model ve efor sabit, Claude Code'un o makinedeki varsayilani (/model) hatti
# degistirmesin. "opus" takma adi en yeni Opus'a cozulur. Bos dize = bayrak hic verilmez.
VARSAYILAN_MODEL = os.environ.get("LOTM_MODEL", "opus")
VARSAYILAN_EFOR = os.environ.get("LOTM_EFOR", "high")


def claude_komutu(
    model: str | None, araclar: list | None = None, efor: str | None = None
) -> list:
    komut = shlex.split(os.environ.get("LOTM_CLAUDE", "claude -p --output-format text"))
    model = model or VARSAYILAN_MODEL
    efor = VARSAYILAN_EFOR if efor is None else efor
    if model:
        komut += ["--model", model]
    if efor:
        komut += ["--effort", efor]
    if araclar:
        komut += ["--allowedTools", ",".join(araclar)]
    return komut


def claude_calistir(komut: list, girdi: str, sure: int, cwd: Path):
    """subprocess.run; CLI --effort'u tanimiyorsa (eski surum) bir kez onsuz dener."""
    p = subprocess.run(
        komut, input=girdi, capture_output=True, text=True, timeout=sure, cwd=cwd
    )
    if p.returncode != 0 and "--effort" in komut and "effort" in p.stderr.lower():
        print(
            "  UYARI: claude --effort'u tanimadi, efor bayragi olmadan yeniden deneniyor "
            "(Claude Code'u guncelleyin ya da LOTM_EFOR= ile kapatin)",
            flush=True,
        )
        i = komut.index("--effort")
        komut = komut[:i] + komut[i + 2 :]
        p = subprocess.run(
            komut, input=girdi, capture_output=True, text=True, timeout=sure, cwd=cwd
        )
    return p


# Gecis basina motor (3 Kas): LOTM_MOTOR_<ADIM>=codex ya da sonra --motor sadakat=codex.
MOTORLAR = ("claude", "codex", "antigravity")
MOTOR_KOMUTU = {
    "codex": ("LOTM_CODEX", "codex exec"),
    "antigravity": (
        "LOTM_AGY",
        "agy --output-format text --disable-slash-commands --mode plan",
    ),
}
# agy'de efor model adinda (gemini-4-neon-high, claude-opus-5-5-high...), bu yuzden
# --effort varsayilan olarak verilmez; LOTM_AGY_EFOR yalniz acikca istenirse eklenir.
AGY_EFOR = os.environ.get("LOTM_AGY_EFOR", "")
AGY_MODEL = os.environ.get(
    "LOTM_AGY_MODEL", ""
)  # bos: agy'nin varsayilani ('agy models')
CODEX_EFOR = os.environ.get("LOTM_CODEX_EFOR", "high")
CODEX_MODEL = os.environ.get("LOTM_CODEX_MODEL", "")  # bos: codex'in varsayilani

# Varsayilan motorlar (3 Kas): sadakat codex, cunku ceviriyi Claude yapiyor ve
# her model kendi kaymasini dogal bulur. Codex yoksa claude'a duser.
VARSAYILAN_MOTOR = {
    "okuma": "claude",
    "donem": "antigravity",
    "sadakat": "antigravity",
    "duzeltme": "antigravity",
    "triyaj": "claude",
    "birlestir": "claude",
}


def ikinci_motor(birinci: str) -> str:
    """Cift sadakatte ikinci okuyucu. LOTM_MOTOR_SADAKAT2 / --motor sadakat2=... ile secilir."""
    m = os.environ.get("LOTM_MOTOR_SADAKAT2")
    if m and m != birinci:
        return m
    return "claude" if birinci != "claude" else "codex"


def cikti_motoru(cikti: Path, varsayilan: str) -> str:
    """2_sadakat_cikti_01.claude.md -> claude; ekisiz ad varsayilan motorundur."""
    m = re.match(r".*_\d+\.([a-z]+)\.md$", cikti.name)
    return m.group(1) if m and m.group(1) in MOTORLAR else varsayilan


def motor_sec(adim: str, secimler: dict | None = None) -> str:
    m = (
        (secimler or {}).get(adim)
        or os.environ.get(f"LOTM_MOTOR_{adim.upper()}")
        or VARSAYILAN_MOTOR.get(adim, "claude")
    )
    if m in MOTOR_KOMUTU and not shutil.which(
        shlex.split(os.environ.get(*MOTOR_KOMUTU[m]))[0]
    ):
        print(f"  UYARI: {adim} icin {m} bulunamadi, claude ile calisiyor", flush=True)
        m = "claude"
    if m not in MOTORLAR:
        raise SystemExit(f"bilinmeyen motor: {m} ({', '.join(MOTORLAR)})")
    return m


def codex_komutu(son_mesaj: Path) -> list:
    komut = shlex.split(os.environ.get("LOTM_CODEX", "codex exec"))
    komut += [
        "-",
        "--output-last-message",
        str(son_mesaj),
        "-s",
        "read-only",
        "-c",
        f"model_reasoning_effort={CODEX_EFOR}",
    ]
    if CODEX_MODEL:
        komut += ["-m", CODEX_MODEL]
    return komut


def agy_komutu(girdi_dosyasi: Path) -> list:
    komut = shlex.split(os.environ.get(*MOTOR_KOMUTU["antigravity"]))
    if AGY_EFOR:
        komut += ["--effort", AGY_EFOR]
    if AGY_MODEL:
        komut += ["--model", AGY_MODEL]
    istem = (
        f"{girdi_dosyasi} dosyasını baştan sona eksiksiz oku (uzunsa parça parça) ve "
        "içindeki görevi yap. Cevap olarak yalnız görevin istediği çıktıyı yaz; "
        "dosyayı okuduğunu anlatma, başka dosya açma, hiçbir şeyi değiştirme."
    )
    return komut + [f"-p={istem}"]


# Arac gerektirmeyen gecislere eklenen not (8 Kas; sonra.yurut ekler). Codex
# oturumlarinin cogu AGENTS.md ve bolum dosyasini diskte ariyordu.
DOSYA_ARAMA_NOTU = (
    "\n\n---\nNot: Bu iş için gereken her şey bu mesajda (bölüm metni, şablon, "
    "defter). AGENTS.md'yi, bölüm dosyasını ya da başka bir dosyayı diskte arama "
    "veya açma; doğrudan bu girdiye göre cevap ver.\n"
)

# KOTA       oturum/kullanim kotasi doldu; o motorun kalan cagrilari atlanir.
# HIZ_SINIRI gecici hiz siniri / asiri yuk (sonra'nin paralel kipi paralelligi dusurur).
KOTA = re.compile(
    r"session limit|usage limit|weekly limit|hit your [\w ]{0,20}limit|limit reached|quota",
    re.I,
)
HIZ_SINIRI = re.compile(
    r"rate.?limit|too many requests|\b429\b|\b529\b|overloaded", re.I
)
# Bu surecte kotasi dolan motorlar: {motor: hata metni}. Paralel kipte ebeveyn
# LOTM_KOTA_DOLU=claude,codex ile alt sureclere de bildirir.
KOTA_DOLU = {
    m: "ebeveyn surecte kota doldu"
    for m in (os.environ.get("LOTM_KOTA_DOLU") or "").split(",")
    if m
}


@dataclass
class Sonuc:
    ok: bool
    metin: str = ""
    hata: str = ""
    kota: bool = False
    motor: str = "claude"  # gercekte kosan motor (antigravity+araclar -> claude)


def calistir(
    metin: str,
    motor: str = "claude",
    model: str | None = None,
    sure: int = 1800,
    araclar: list | None = None,
    cwd: Path = BETIKLER,
    ek_argumanlar: list | None = None,
    gecici: Path | None = None,
    kota: dict | None = None,
) -> Sonuc:
    """Taze bir oturum. model ve ek_argumanlar yalniz claude icindir.

    gecici: gecici dosyalarin oneki (<gecici>.codex-son, <gecici>.agy-girdi.md);
    verilmezse cwd'de tempfile. kota: KOTA_DOLU yerine kullanilacak sozluk."""
    kota = KOTA_DOLU if kota is None else kota
    if motor in kota:
        print(f"  ATLANDI {motor}: (kota dolu: {kota[motor]})", flush=True)
        return Sonuc(False, hata=kota[motor], kota=True, motor=motor)
    if motor == "antigravity" and araclar:
        print(
            "  UYARI: antigravity arac izni ayarlanamiyor, bu gecis claude ile",
            flush=True,
        )
        motor = "claude"
    if gecici is None:
        fd, ad = tempfile.mkstemp(prefix=".motor-", dir=cwd)
        os.close(fd)
        os.unlink(ad)
        gecici = Path(ad)
    son = gecici.with_name(gecici.name + ".codex-son")
    try:
        if motor == "codex":
            son.unlink(missing_ok=True)
            p = subprocess.run(
                codex_komutu(son),
                input=metin,
                capture_output=True,
                text=True,
                timeout=sure,
                cwd=cwd,
            )
        elif motor == "antigravity":
            agy_girdi = gecici.with_name(gecici.name + ".agy-girdi.md")
            agy_girdi.write_text(metin, encoding="utf-8")
            try:
                p = subprocess.run(
                    agy_komutu(agy_girdi.resolve()),
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=sure,
                    cwd=cwd,
                )
            finally:
                try:
                    agy_girdi.unlink(missing_ok=True)
                except OSError:
                    pass
        else:
            p = claude_calistir(
                claude_komutu(model, araclar) + list(ek_argumanlar or []),
                metin,
                sure,
                cwd,
            )
    except FileNotFoundError:
        print(
            f"  HATA: {motor} komutu bulunamadi (LOTM_CLAUDE / LOTM_CODEX / LOTM_AGY ile verin)"
        )
        return Sonuc(False, hata="komut bulunamadi", motor=motor)
    except subprocess.TimeoutExpired:
        son.unlink(missing_ok=True)
        print(f"  HATA: {sure} sn icinde bitmedi")
        return Sonuc(False, hata="zaman asimi", motor=motor)
    cevap = p.stdout
    if motor == "codex":
        cevap = son.read_text(encoding="utf-8") if son.exists() else ""
        son.unlink(missing_ok=True)
    if p.returncode != 0 or not cevap.strip():
        hata = (p.stderr or p.stdout).strip()[-400:]
        print(f"  HATA (cikis {p.returncode}): {hata}")
        dolu = bool(KOTA.search(hata))
        if dolu:
            kota[motor] = hata.replace("\n", " ⏎ ")[-160:]
            # Ebeveyn (paralel kip) bu satiri arar.
            print(f"  KOTA {motor}: {kota[motor]}", flush=True)
        return Sonuc(False, hata=hata, kota=dolu, motor=motor)
    return Sonuc(True, metin=cevap, motor=motor)


def motor_etiketi_yaz(cikti: Path, motor: str) -> None:
    """<cikti>.motor: claude disi motorun yazdigini iz birakir; claude ise silinir."""
    yan = cikti.with_name(cikti.name + ".motor")
    if motor != "claude":
        yan.write_text(motor + "\n", encoding="utf-8")
    else:
        yan.unlink(missing_ok=True)


def etiket_oku(cikti: Path) -> str:
    """motor_etiketi_yaz'in tersi: sidecar yoksa claude."""
    yan = cikti.with_name(cikti.name + ".motor")
    return yan.read_text(encoding="utf-8").strip() if yan.exists() else "claude"


__all__ = [
    "VARSAYILAN_MODEL",
    "VARSAYILAN_EFOR",
    "claude_komutu",
    "claude_calistir",
    "MOTORLAR",
    "MOTOR_KOMUTU",
    "AGY_EFOR",
    "AGY_MODEL",
    "CODEX_EFOR",
    "CODEX_MODEL",
    "VARSAYILAN_MOTOR",
    "ikinci_motor",
    "cikti_motoru",
    "motor_sec",
    "codex_komutu",
    "agy_komutu",
    "DOSYA_ARAMA_NOTU",
    "KOTA",
    "HIZ_SINIRI",
    "KOTA_DOLU",
    "Sonuc",
    "calistir",
    "motor_etiketi_yaz",
    "etiket_oku",
]
