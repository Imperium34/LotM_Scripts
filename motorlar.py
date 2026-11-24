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
    codex        'codex exec --ephemeral' (LOTM_CODEX); stdin'den okur, son cevabi
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


def _komut_bol(ortam_adi: str, varsayilan: str) -> list:
    """Ortam degiskenini komut listesine boler; bos dize varsa varsayilana doner."""
    ham = os.environ.get(ortam_adi)
    return shlex.split(ham if ham and ham.strip() else varsayilan)


def claude_komutu(
    model: str | None, araclar: list | None = None, efor: str | None = None
) -> list:
    komut = _komut_bol("LOTM_CLAUDE", "claude -p --output-format text")
    model = model or os.environ.get("LOTM_MODEL", VARSAYILAN_MODEL)
    efor = os.environ.get("LOTM_EFOR", VARSAYILAN_EFOR) if efor is None else efor
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
    "codex": ("LOTM_CODEX", "codex exec --ephemeral"),
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

# Varsayilan motorlar: okuma/triyaj/birlestir claude; donem/sadakat/duzeltme
# antigravity; cift sadakatte ikinci okuyucu (sadakat2) codex. Secilen CLI
# yoksa claude'a duser.
VARSAYILAN_MOTOR = {
    "okuma": "claude",
    "donem": "antigravity",
    "sadakat": "antigravity",
    "sadakat2": "codex",
    "okuma2": "codex",
    "zh": "antigravity",
    "duzeltme": "antigravity",
    "triyaj": "claude",
    "birlestir": "claude",
}


def _komut_var(motor: str) -> bool:
    if motor not in MOTOR_KOMUTU:
        return True
    return bool(shutil.which(_komut_bol(*MOTOR_KOMUTU[motor])[0]))


def ikinci_motor(birinci: str, secimler: dict | None = None, adim: str = "sadakat") -> str:
    """Cift sadakat / cift okumada ikinci okuyucu. --motor <adim>2=... /
    LOTM_MOTOR_<ADIM>2 / VARSAYILAN_MOTOR['<adim>2'] (ikisi de codex)."""
    anahtar = f"{adim}2"
    m = (
        (secimler or {}).get(anahtar)
        or os.environ.get(f"LOTM_MOTOR_{anahtar.upper()}")
        or VARSAYILAN_MOTOR.get(anahtar)
    )
    if m:
        if m not in MOTORLAR:
            raise SystemExit(f"bilinmeyen motor: {m} ({', '.join(MOTORLAR)})")
        if not _komut_var(m):
            print(
                f"  UYARI: {anahtar} icin {m} bulunamadi, baska motor seciliyor",
                flush=True,
            )
            m = None
    if m and m != birinci:
        return m
    return "claude" if birinci != "claude" else "codex"


def cikti_motoru(cikti: Path, varsayilan: str) -> str:
    """2_sadakat_cikti_01.claude.md / 1_okuma_cikti.codex.md -> motor; ekisiz ad varsayilan motorundur."""
    m = re.match(r".*\.([a-z]+)\.md$", cikti.name)
    return m.group(1) if m and m.group(1) in MOTORLAR else varsayilan


def motor_sec(adim: str, secimler: dict | None = None) -> str:
    m = (
        (secimler or {}).get(adim)
        or os.environ.get(f"LOTM_MOTOR_{adim.upper()}")
        or VARSAYILAN_MOTOR.get(adim, "claude")
    )
    if m in MOTOR_KOMUTU and not _komut_var(m):
        print(f"  UYARI: {adim} icin {m} bulunamadi, claude ile calisiyor", flush=True)
        m = "claude"
    if m not in MOTORLAR:
        raise SystemExit(f"bilinmeyen motor: {m} ({', '.join(MOTORLAR)})")
    return m


def codex_komutu(son_mesaj: Path) -> list:
    komut = _komut_bol("LOTM_CODEX", "codex exec --ephemeral")
    efor = os.environ.get("LOTM_CODEX_EFOR", CODEX_EFOR)
    model = os.environ.get("LOTM_CODEX_MODEL", CODEX_MODEL)
    komut += [
        "-",
        "--output-last-message",
        str(son_mesaj),
        "-s",
        "read-only",
        "-c",
        f"model_reasoning_effort={efor}",
    ]
    if model:
        komut += ["-m", model]
    return komut


def agy_komutu(girdi_dosyasi: Path) -> list:
    komut = _komut_bol(*MOTOR_KOMUTU["antigravity"])
    efor = os.environ.get("LOTM_AGY_EFOR", AGY_EFOR)
    model = os.environ.get("LOTM_AGY_MODEL", AGY_MODEL)
    if efor:
        komut += ["--effort", efor]
    if model:
        komut += ["--model", model]
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
    r"session limit|usage limit|weekly limit|hit your [\w -]{0,20}limit|limit reached|quota|out of (?:usage )?credits",
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
    oturum: str | None = None,
) -> Sonuc:
    """Taze bir oturum. model, ek_argumanlar ve oturum yalniz claude icindir.

    oturum: claude oturumuna verilecek UUID (--session-id); sonradan
    'claude --resume <oturum>' ile ayni cwd'den sohbet olarak surdurulur.

    gecici: gecici dosyalarin oneki (<gecici>.codex-son, <gecici>.agy-girdi.md);
    verilmezse cwd'de tempfile. kota: KOTA_DOLU yerine kullanilacak sozluk."""
    if motor not in MOTORLAR:
        raise ValueError(f"bilinmeyen motor: {motor} ({', '.join(MOTORLAR)})")
    if motor == "antigravity" and araclar:
        print(
            "  UYARI: antigravity arac izni ayarlanamiyor, bu gecis claude ile",
            flush=True,
        )
        motor = "claude"
    kota = KOTA_DOLU if kota is None else kota
    if motor in kota:
        print(f"  ATLANDI {motor}: (kota dolu: {kota[motor]})", flush=True)
        return Sonuc(False, hata=kota[motor], kota=True, motor=motor)
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
                claude_komutu(model, araclar)
                + (["--session-id", oturum] if oturum else [])
                + list(ek_argumanlar or []),
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
        stderr_t, stdout_t = p.stderr.strip(), p.stdout.strip()
        hata = (stderr_t or stdout_t)[-400:]
        birlesik = "\n".join(x for x in (stdout_t, stderr_t) if x)
        dolu = bool(KOTA.search(birlesik))
        if dolu and not KOTA.search(hata):
            hata = stdout_t[-400:]
        elif not dolu and HIZ_SINIRI.search(birlesik) and not HIZ_SINIRI.search(hata):
            hata = stdout_t[-400:]
        print(f"  HATA (cikis {p.returncode}): {hata}")
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
