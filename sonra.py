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
               Yanki Defteri'nden (Tools/Voice_Maps/Echo_Notes.md) kurulumu ya
               da odemesi bu bolumde olan girisler <yanki_defteri> olarak
               girer; 'ileride' odemeli girisler --yanki N,N ile eklenir.
    duzeltme   3_duzeltme_girdi.md  ->  3_duzeltme_cikti.md
               ciktidaki tam metin bolumle karsilastirilir: 3_duzeltme_fark.diff
               (gecis bolum dosyasina yazmaz; degisiklikler birlestirmeye gider)
    triyaj     4_triyaj_girdi.md    ->  4_triyaj_cikti.md
               (otomatik kipte yalniz okuyan denetci komutlarini calistirabilir)
    birlestir  5_birlestir_girdi.md ->  5_birlestir_cikti.md (JSON)
               dort gecisin bulgulari tek listede: KESIN / KARAR / SABLON.
    son adim   KESIN duzeltmeler bolume birebir eslesmeyle uygulanir (once
               yedek: LotM/yedek/<tarih>/sonra-Ch_N-<saat>/, fark: 5_uygulanan.diff); geri
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
    sonra.py 61 --istatistik           61'in kararlarini istatistige kat, aile ozetini bas
    sonra.py 61 --bastan               uygulamadan sonra hatti bastan kur
    sonra.py 61 --zincir-yeniden       betik zincirini zorla yeniden calistir
    sonra.py 61 --parti-boyu 9000      sadakat partisi (ZH+TR karakter, varsayilan 6000)
    sonra.py 61 --yanki 14,22          sadakat'e bolum eslesmesinin disinda Yanki girisleri ekle
    sonra.py 62-65 --otomatik          coklu kip (61,63,70-72 de olur); birden cok bolumde
                                       ayni anda kac bolum kosacagi kendiliginden secilir
                                       (--paralel oto, en cok LOTM_PARALEL_UST=3; hiz sinirina
                                       takilinca duser). --paralel 1: sirayla. Biri duserse
                                       digerleri yurur, ozet Reports/sonra/COKLU.md
    sonra.py 61 --otomatik --donem-yok donem uyumu gecisini atla (7 Kas'tan beri varsayilan
                                       acik; LOTM_DONEM=0 ayni): 1b_donem_girdi.md ->
                                       1b_donem_cikti.md, aday listesi donem_denetle.py'den;
                                       bulgular birlestirmede KARAR
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
import lotm  # noqa: E402  (ortak: yedek_klasoru, bolum_listesi, cekirdek_istem)

SITE = KOK / "Imperium34.github.io"
BOLUMLER = SITE / "_chapters"
ISTEMLER = lotm.ISTEMLER
SABLONLAR = Path(os.environ.get("LOTM_SABLONLAR") or KOK / "Tools" / "Schemas")
RAPOR = Path(os.environ.get("LOTM_SONRA_RAPOR") or BETIKLER / "Reports" / "sonra")
# cevir.py'nin ciktilari (DURUM NOTU); yoksa okuma onsuz calisir.
CEVIRI = Path(os.environ.get("LOTM_CEVIRI_RAPOR") or BETIKLER / "Reports" / "ceviri")
# Karar defteri: kullanicinin "hep boyle" dedigi kabul/ret kararlari. Bir
# rapor degil bir karar, o yuzden Reports/'ta degil Tools/'da ve surum
# denetiminde. Her gecise ve birlestirmeye verilir; ayni soru tekrar sorulmaz.
KARARLAR = Path(os.environ.get("LOTM_KARARLAR") or KOK / "Tools" / "kararlar.md")
# Yanki Defteri: bolumler arasi geriye isleyen kurulum/odeme bagimliliklari.
# Sadakat gecisine yalniz o bolumu ilgilendiren girisler verilir.
YANKI = Path(os.environ.get("LOTM_YANKI") or KOK / "Tools" / "Voice_Maps" / "Echo_Notes.md")

ISTEM = {
    "okuma": "lotm_chapter_read_pass.md",
    "sadakat": "LotM_QA_Sadakat.md",
    "duzeltme": "lotm_fixing_prompt.md",
    "triyaj": "zincir-okuma-istemi.md",
    "birlestir": "lotm_birlestirme.md",
    "donem": "lotm_donem_denetimi.md",
}
MODEL_ADIMLARI = ("okuma", "sadakat", "duzeltme", "triyaj", "birlestir")
# Donem uyumu (4 Kas; 7 Kas'tan beri varsayilan acik): cagdas sozcukler
# Viktorya/gotik dokuda. Okumadan sonra ayri bir gecis olarak girer;
# --donem-yok ya da LOTM_DONEM=0 kapatir. Ciktisi bir kez olustu mu
# birlestirmeye hep verilir (kapatilinca birlestirme ESKIMIS gorunup
# yeniden kosmasin diye). Donuk (uygulanmis) bolumler zaten atlanir.
DONEM = os.environ.get("LOTM_DONEM", "1") not in ("", "0")
# Triyaj ayrinti komutlarini kendisi calistirabilsin: yalniz okuyan denetciler.
TRIYAJ_ARACLARI = ["Read", "Bash(python3 toplu_denetle.py:*)", "Bash(python3 bicim_denetle.py:*)",
                   "Bash(python3 ceviri_denetle.py:*)", "Bash(python3 bolum.py:*)",
                   "Bash(python3 sozluk_ara.py:*)"]
UYGULANDI = "5_uygulandi.json"
# --kararlar bir kez islenince (kuru degilse): ne zaman, kac karar. Engel
# degildir; inceleme sayfasi (incele) islenmis bolumu kuyrukta atlamak icin bakar.
KARARLAR_ISLENDI = "5_kararlar.json"
KELIMELER = Path(os.environ.get("LOTM_KELIMELER") or KOK / "Tools" / "words.md")
YERLESTIRILECEK = "# Yerleştirilecek (sonra.py)"
# Karar istatistigi: her islenen inceleme maddesi bir satir (bolum, K, aile,
# on-isaret, karar). Kural ailelerinin kabul oranini olcer; on-isarete ya da
# otomatige terfi bu sayilara dayanir. Karar defteri gibi Tools/'ta durur.
ISTATISTIK = Path(os.environ.get("LOTM_ISTATISTIK") or KOK / "Tools" / "karar_istatistik.tsv")
# Otomatik aileler (7 Kas): kabul orani olculmus, artik incelemeye gelmez,
# KESIN gibi birebir eslesmeyle uygulanir (5_uygulanan.diff, Uygulananlar
# listesinde "otomatik" etiketiyle; yedekten geri alinir). Yalniz okumadan
# gelen, gerekcesi tereddutsuz (OKLUK) ve onerisi saglam maddeler; boyut
# siniri (KESIN_ORAN) da gecerli. okuma 1.6: 69 karar, %93 kabul.
# Eskiden bunlar 'kabul' on-isaretli geliyordu; tusla incelemede on-isaret
# bir tus kazandiriyordu, maddeyi listeden cikarmiyordu, kaldirildi.
OTOMATIK = {"okuma 1.6"}
# Otomatige terfi esigi: --istatistik "otomatiğe hazır" der; OTOMATIK'e
# eklemek elle.
TERFI_EN_AZ, TERFI_ORAN = 40, 0.90
# Birlestirmenin gerekcesinde bu sozler varsa gecis kendisi tereddut ediyor:
# 63'teki iki ret de "noktali virgul is goruyor olabilir" diyen maddelerdi.
OKLUK = re.compile(r"olabilir|bilinçli|kasıtlı|emin değil|çevirmen seç|keser|bozar|"
                   r"ritim|ritm|tek nefes|tek soluk", re.I)

ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Zincirde dikkat isteyen satirlar: kirmizi uyarilar, atlanan adimlar,
# coken betikler. Bicim raporunun basligi ve sifir ozeti degil.
DIKKAT = re.compile(r"HATA|ATLANDI|✗|YOK:|Traceback|Error")
SESSIZ = re.compile(r"=== HATA ===|HATA toplam: 0\b")


# ------------------------------------------------------------------ yardimci

# Sablonla sozluk/words.md celisirse (sablon eski, karar sonradan degismis)
# gecisler eski terimi geri getirmesin (7 Kas; Ch_45 "kira arabasi" vs sozluk
# "kira faytonu", Ch_30 "Noterligi" vs "Katibiadilligi").
SABLON_USTUNLUK = ("> Not (betik): Bu şablonun bir satırı sözlük (`sozluk.yml`) ya da words.md ile "
                   "çelişirse sözlük ve words.md esastır; şablondaki eski biçimi önerme.")
YAYIMLANMIS_NOTU = ("> Not (betik): Bu bölüm yayımlanmış; şablonu eski. A.1 ve A.2 terim tabloları "
                    "çıkarıldı: terimlerde yalnız sözlük ve words.md esastır, şablondaki bir terimi "
                    "geri getirme ya da bulgu yapma. Şablon geri bildirimi (SABLON / Ş) yazma: bu "
                    "şablon bir daha kullanılmayacak. Ses, hitap, dondurulmuş satır ve tuzak "
                    "bölümleri geçerlidir.")


def yayim_tarihi_gecti(metin: str, simdi=None) -> bool:
    """Front matter'daki 'date:' (2026-07-07 20:00:00 +0300) simdiden onceyse True."""
    from datetime import datetime, timezone
    m = re.search(r"\A---\n.*?^date:\s*(\S+)(?:\s+(\d{1,2}:\d{2}(?::\d{2})?))?(?:\s*([+-]\d{2}:?\d{2}))?",
                  metin, re.S | re.M)
    if not m:
        return False
    gun, saat, dilim = m.group(1), m.group(2) or "00:00:00", (m.group(3) or "+0300").replace(":", "")
    if saat.count(":") == 1:
        saat += ":00"
    try:
        tarih = datetime.strptime(f"{gun} {saat} {dilim}", "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return False
    return tarih <= (simdi or datetime.now(timezone.utc))


def terim_tablolarini_at(sablon: str) -> str:
    """'### A.1' ve '### A.2' bolumlerini (bir sonraki ### ya da ## basligina kadar) cikarir."""
    return re.sub(r"^### A\.[12]\b.*?(?=^#{2,3} |\Z)", "", sablon, flags=re.M | re.S)


def yedek_al(etiket: str, *dosyalar: Path) -> Path | None:
    """Dosyalarin kopyasi LotM/yedek/<tarih>/<etiket>-<saat>/'a (lotm.yedek_klasoru)."""
    var = [d for d in dosyalar if d.exists()]
    if not var:
        return None
    hedef = lotm.yedek_klasoru(etiket)
    hedef.mkdir(parents=True, exist_ok=True)
    for d in var:
        shutil.copy2(d, hedef / d.name)
    return hedef


def paralel_sayisi(deger, bolum_sayisi: int) -> tuple:
    """--paralel degeri -> (ayni anda kac bolum, otomatik mi). ValueError: bozuk deger."""
    if str(deger).strip().lower() in ("oto", "auto", ""):
        ust = max(1, int(os.environ.get("LOTM_PARALEL_UST") or 3))
        return max(1, min(bolum_sayisi, ust)), True
    return max(1, int(deger)), False


# Iki ayri durum (7 Kas, 20-25 kosusundan: "You've hit your session limit ·
# resets 6:30am"):
#   KOTA       oturum/kullanim kotasi doldu. Saatlerce gecmez; ayni anda kosan
#              bolum sayisini dusurmek ise yaramaz. O motorun kalan cagrilari
#              hemen atlanir (BEKLIYOR kalir), oteki motor yurumeye devam eder;
#              sifirlaninca ayni komut kalanlari tamamlar.
#   HIZ_SINIRI gecici hiz siniri / asiri yuk. Otomatik paralel kipte ayni anda
#              kosan bolum sayisi bir dusurulur, bolum bir kez yeniden denenir.
KOTA = re.compile(r"session limit|usage limit|weekly limit|hit your [\w ]{0,20}limit|limit reached|quota", re.I)
HIZ_SINIRI = re.compile(r"rate.?limit|too many requests|\b429\b|\b529\b|overloaded", re.I)
# Bu surecte kotasi dolan motorlar: {motor: hata metni}. Paralel kipte ebeveyn
# LOTM_KOTA_DOLU=claude,codex ile alt sureclere de bildirir.
KOTA_DOLU = {m: "ebeveyn surecte kota doldu" for m in
             (os.environ.get("LOTM_KOTA_DOLU") or "").split(",") if m}


def yaz_degisirse(yol: Path, metin: str) -> bool:
    """Icerik ayniysa dokunmaz: mtime korunur, cikti ESKIMIS gorunmez."""
    if yol.exists() and yol.read_text(encoding="utf-8") == metin:
        return False
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(metin, encoding="utf-8")
    return True


DEFTER_BLOGU = re.compile(r"<onceki_kararlar>\n.*?</onceki_kararlar>\n\n", re.S)


def yaz_defter_haric(yol: Path, metin: str, cikti: Path) -> bool:
    """yaz_degisirse gibi; ama girdi yalnizca karar defteri blogunda degistiyse ve
    cikti hazirsa dokunmaz (8 Kas). Bir bolumun kararlarini islemek (hep) defteri
    degistirir; yoksa beklemedeki her bolumun okuma/donem/sadakat gecisleri ESKIMIS
    olup bastan kosardi. Yeni defter yine birlestirmeye gider, o da defterdeki
    ret/kabul orunturlerini uygular. LOTM_DEFTER_ESKITIR=1 eski davranis."""
    if (os.environ.get("LOTM_DEFTER_ESKITIR") != "1" and yol.exists()
            and durum(yol, cikti) == "TAMAM"
            and DEFTER_BLOGU.sub("", yol.read_text(encoding="utf-8")) == DEFTER_BLOGU.sub("", metin)):
        return False
    return yaz_degisirse(yol, metin)


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


DEFTER_SATIRI = re.compile(r"^- (kabul|ret) · (.+?) — örnek: «(.*?)» → «(.*?)»\s*(\(.*\))?\s*$")


def defter_ailesi(kural: str) -> str:
    """'okuma 1.6 aynı cümlede…' -> 'okuma 1.6'; 'sadakat A anlam kayması' -> 'sadakat A'."""
    p = kural.split()
    return " ".join(p[:2]) if len(p) >= 2 else kural


def defter_ozeti(metin: str) -> str:
    """Karar defterinin gecislere giden kisa hali (8 Kas). Defter dosyasi tam kayit
    olarak kalir; gecisler her ret'i (tekrarsiz) ve her ailenin kabul sayisini +
    en kisa ornegini gorur. Sadakat kabulleri tek seferlik anlam duzeltmeleridir,
    oruntu degildir: yalnizca sayilir. Donem kabullerinde sozcuk ciftleri kalir,
    cunku her cift ayri bir karardir. Okunamayan satirlar oldugu gibi gecer."""
    retler, kabul, diger, gorulen = {}, {}, [], set()
    for satir in metin.splitlines():
        if not satir.startswith("- "):
            continue
        m = DEFTER_SATIRI.match(satir)
        if not m:
            diger.append(satir)
            continue
        karar, kural, eski, yeni, _ = m.groups()
        anahtar = (karar, eski, yeni)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        aile = defter_ailesi(kural)
        if karar == "ret":
            retler.setdefault(aile, []).append(f"  - {kural}: «{eski}» → «{yeni}»")
        else:
            kabul.setdefault(aile, []).append((kural, eski, yeni))
    out = ["Ret (çevirmen bu değişiklikleri istemedi; aynısını ya da aynı sözcük değişikliğini başka yerde de önerme):"]
    for aile in sorted(retler):
        out += retler[aile]
    out += ["", "Kabul (aile · kaç kez · örnek):"]
    for aile in sorted(kabul):
        ornekler = kabul[aile]
        if aile.startswith("sadakat"):
            out.append(f"  - {aile} · {len(ornekler)} · tek tek anlam düzeltmeleri; örüntü değil, "
                       "ölçüt yine kaynakla karşılaştırma")
        elif aile.startswith(("dönem", "ses_ayari")):
            ciftler = sorted({f"{e} → {y}" for _, e, y in ornekler if len(e) <= 40})
            out.append(f"  - {aile} · {len(ornekler)} · " + "; ".join(ciftler))
        else:
            kural, e, y = min(ornekler, key=lambda o: len(o[1]) + len(o[2]))
            out.append(f"  - {aile} · {len(ornekler)} · {kural}: «{e}» → «{y}»")
    if diger:
        out += ["", "Diğer:"] + diger
    return "\n".join(out)


def kararlar_blogu() -> str:
    """Karar defteri, gecislere verilecek bicimde; defter yoksa bos dize.
    Varsayilan kisa ozet (defter_ozeti); LOTM_DEFTER_TAM=1 tam defteri verir."""
    if not KARARLAR.exists() or not KARARLAR.read_text(encoding="utf-8").strip():
        return ""
    ham = KARARLAR.read_text(encoding="utf-8").strip()
    govde = ham if os.environ.get("LOTM_DEFTER_TAM") == "1" else defter_ozeti(ham)
    return (
        "<onceki_kararlar>\n"
        "Çevirmenin daha önce verdiği kalıcı kararlar. 'ret' satırındaki örüntüyü bulgu olarak "
        "yazma; 'kabul' satırındaki örüntü zaten onaylı bir düzeltmedir.\n\n"
        f"{govde}\n"
        "</onceki_kararlar>\n\n"
    )


# ------------------------------------------------------------------ yanki defteri

YANKI_BASLIK = re.compile(r"^### #(\d+) · ", re.M)


def yanki_girisleri(metin: str) -> dict:
    """Echo_Notes.md -> {no: {"blok": tam metin, "kurulum": ..., "odeme": ...}}."""
    parcalar = YANKI_BASLIK.split(metin)
    out = {}
    for i in range(1, len(parcalar), 2):
        no = int(parcalar[i])
        gov = parcalar[i + 1]
        # Son girisin kuyrugu '## Kullanim' bolumunu icermesin.
        gov = re.split(r"\n## ", gov)[0].rstrip()
        baslik = re.search(r"^### #%d · .*$" % no, metin, re.M).group(0)

        def alan(ad):
            m = re.search(r"- \*\*%s:\*\* (.*)" % ad, gov)
            return m.group(1) if m else ""
        out[no] = {"blok": f"{baslik}\n{gov}", "kurulum": alan("Kurulum"),
                   "odeme": alan("Ödeme")}
    return out


def bolum_numaralari(alan: str) -> set:
    """Bir Kurulum/Odeme hucresindeki BOLUM numaralari.

    Paragraf numaralari (¶N), yil/tarih, 'CoI N' ve 'N. Asama' atilir; 'A–B'
    araligi yalniz dar ise (<=3) acilir: '115–116' iki bolumdur, '220–1165'
    bir donem tanimidir.
    """
    alan = re.sub(r"¶\d+(?:\s*[–-]\s*¶?\d+)?", " ", alan)
    alan = re.sub(r"\d{4}-\d{2}-\d{2}|\b20\d\d\b|CoI\s*\d+|\d+\.\s*Aşama", " ", alan)
    nolar = set()
    for m in re.finditer(r"(\d+)(?:\s*[–-]\s*(\d+))?", alan):
        a, b = int(m.group(1)), m.group(2)
        if b is None:
            nolar.add(a)
        elif 0 <= int(b) - a <= 3:
            nolar.update(range(a, int(b) + 1))
    return nolar


def yanki_secimi(no: int, girisler: dict, ek: tuple = ()) -> list:
    """Bu bolumu ilgilendiren giris numaralari: kurulumu ya da odemesi bu bolumde, + elle ekler."""
    secilen = {n for n, g in girisler.items()
               if no in bolum_numaralari(g["kurulum"]) or no in bolum_numaralari(g["odeme"])}
    secilen |= {n for n in ek if n in girisler}
    return sorted(secilen)


def yanki_blogu(no: int, ek: tuple = ()) -> str:
    """Sadakat gecisine <yanki_defteri>; defter yoksa ya da giris yoksa bos dize."""
    if not YANKI.exists():
        return ""
    girisler = yanki_girisleri(YANKI.read_text(encoding="utf-8"))
    secilen = yanki_secimi(no, girisler, ek)
    if not secilen:
        return ""
    return ("<yanki_defteri>\n"
            + "\n\n".join(girisler[n]["blok"] for n in secilen)
            + "\n</yanki_defteri>")


def ses_blogu(no: int, tr: str) -> str:
    """Sadakat partisine <ses_kararlari>: sabit ses/hitap kararlari + partide
    gecen karakterlerin bu bolumdeki asamasi (ses_haritasi.py --kisa). Harita
    okunamazsa bos dize; sadakat onsuz da calisir."""
    try:
        import ses_haritasi
        metin = ses_haritasi.kisa(no, tr)
    except Exception:  # yardimci blok, hat durmasin
        return ""
    return f"<ses_kararlari>\n{metin}\n</ses_kararlari>" if metin.strip() else ""


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


def alanlari_tamamla(d: dict) -> dict:
    """Modelin bos biraktigi alanlari doldurur. 66: SABLON maddesinde
    "yeni": null = metin degismez, oneri 'neden'de. eski null -> "",
    yeni null -> eski (kabul edilse de metne dokunmaz)."""
    eski = d.get("eski") or ""
    yeni = d.get("yeni")
    return dict(d, eski=eski, yeni=eski if yeni is None else yeni)


# KESIN de olsa cumlenin buyuk kismini degistiren duzeltme insana gider
# (5 Kas: 5-10'da uygulanan 246 maddenin 134'u cumlenin dortte birinden
# fazlasini yeniden yaziyordu). Oran: eski/yeni karakter benzerligi (sozcuk
# duzeyi "geldi; kapıyı" -> "geldi. Kapıyı" gibi noktalama duzeltmesini de
# buyuk sayardi). 0.85'te 5-10'un 246 maddesinden 142'si karara duser.
KESIN_ORAN = float(os.environ.get("LOTM_KESIN_ORAN") or 0.85)
KESIN_YOK = os.environ.get("LOTM_KESIN_YOK", "") not in ("", "0")


def benzerlik(eski: str, yeni: str) -> float:
    """Karakter benzerligi; buyuk-kucuk harf ve noktalama sayilmaz (noktali
    virgulu noktaya cevirmek buyuk degisiklik degildir)."""
    import difflib
    from turkce import tr_kucult

    def sade(s):
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", tr_kucult(s))).strip()
    return difflib.SequenceMatcher(None, sade(eski), sade(yeni), autojunk=False).ratio()


def uygula(metin: str, duzeltmeler: list, oran: float = KESIN_ORAN, kesin_yok: bool = False) -> tuple:
    """
    KESIN duzeltmeleri birebir eslesmeyle uygular: 'eski' metinde tam bir kez
    gecmeli (yayimlanmis bolum duzeltmelerindeki kural). Gecmeyen ya da
    birden fazla gecen KARAR'a duser; sebebi 'not'a yazilir. Cumleyi 'oran'dan
    fazla degistiren (benzerlik < oran) ve kesin_yok iken hepsi de KARAR'a duser.
    """
    uygulanan, karar = [], []
    for d in map(alanlari_tamamla, duzeltmeler):
        if d.get("sinif") != "KESIN":
            karar.append(d)
            continue
        n = metin.count(d["eski"]) if d.get("eski") else 0
        if n != 1 or d["eski"] == d.get("yeni"):
            d = dict(d, sinif="KARAR",
                     neden=(d.get("neden", "") + f" [otomatik uygulanmadı: metinde {n} kez]").strip())
            karar.append(d)
            continue
        if kesin_yok or benzerlik(d["eski"], d["yeni"]) < oran:
            neden = ("otomatik uygulama kapalı (--kesin-yok)" if kesin_yok
                     else f"büyük değişiklik, benzerlik {benzerlik(d['eski'], d['yeni']):.2f} < {oran}")
            karar.append(dict(d, sinif="KARAR", neden=(d.get("neden", "") + f" [{neden}]").strip()))
            continue
        metin = metin.replace(d["eski"], d["yeni"], 1)
        uygulanan.append(d)
    return metin, uygulanan, karar


def tek_satir(s: str) -> str:
    return s.replace("\n", " ⏎ ")


def aileler(kural: str, sinif: str = "KARAR") -> set:
    """'okuma 1.1 noktalı virgül + 1.6 tekrar' -> {'okuma 1.1', 'okuma 1.6'}.

    Alt madde harfleri (1.7ii) atilir. SABLON maddeleri ayri aile sayilir:
    sablon geri bildirimi metin kararindan baska bir sorudur.
    """
    out = {f"okuma {m}" for m in re.findall(r"(?:okuma |\+ )(\d+\.\d+|\d+\.M)", kural)}
    out |= {f"sadakat {m}" for m in re.findall(r"sadakat ([A-DŞ])\b", kural)}
    out |= {"düzeltme" for _ in re.findall(r"düzeltme", kural)}
    out |= {f"dönem {m}" for m in re.findall(r"dönem (D\.\d)", kural)}
    out = out or {kural.split(" ")[0] if kural else "?"}
    return {("SABLON " + a) if sinif == "SABLON" else a for a in out}


def bozuk_oneri(eski: str, yeni: str) -> str | None:
    """Uygulanirsa metni bozacak bir oneri mi? Sebep ya da None.

    63 K10: '; sırtım' -> '; Sırtım' (noktali virgul kalmis, harf buyumus).
    """
    eski, yeni = eski or "", yeni or ""
    for m in re.finditer(r"; (\w)", yeni):
        if m.group(1).isupper() and re.search(r"; " + re.escape(m.group(1).lower()), eski):
            return f"noktalı virgülden sonra büyük harf ('; {m.group(1)}…')"
    if yeni.strip() == eski.strip():
        return "öneri metni değiştirmiyor"
    return None


def otomatige_uygun(d: dict) -> bool:
    """KARAR madde kendiliginden uygulansin mi: butun aileleri OTOMATIK'te,
    yalniz okumadan, gerekce tereddutsuz, oneri saglam."""
    if d.get("sinif", "KARAR") != "KARAR":
        return False
    al = aileler(d.get("kural", ""))
    if not al or not al <= OTOMATIK:
        return False
    if set(d.get("kaynak", [])) - {"okuma"}:
        return False
    if OKLUK.search(d.get("neden", "")):
        return False
    return bozuk_oneri(d.get("eski", ""), d.get("yeni", "")) is None


def degisim_imzasi(eski: str, yeni: str):
    """Sozcuk duzeyinde ne degisti: ((silinen, eklenen), ...). Ekler farkli olsa da
    ayni degisiklik ayni imzayi alsin diye sozcukler ilk bes harfine (kok) iner;
    yalniz ek/kesme degisiyorsa ham sozcukler kullanilir. Degisiklik yoksa None."""
    import difflib

    def parca(kok: bool):
        temiz = lambda w: re.sub(r"[^\w]", "", w.lower())  # noqa: E731
        a = [temiz(w)[:5] if kok else w.lower() for w in eski.split()]
        b = [temiz(w)[:5] if kok else w.lower() for w in yeni.split()]
        out = []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if op != "equal":
                out.append((" ".join(a[i1:i2]), " ".join(b[j1:j2])))
        return tuple(x for x in out if x[0] != x[1])

    imza = parca(True) or parca(False)
    return imza or None


def ayni_degisiklik(maddeler: list) -> dict:
    """{izleyen sira: onder sira}. Ayni aileden, ayni sozcuk degisikligini oneren
    KARAR maddeleri (ayni terim uc paragrafta) tek soru olsun: ilki onder."""
    onder, out = {}, {}
    for i, d in enumerate(maddeler):
        if d.get("sinif", "KARAR") != "KARAR":
            continue
        imza = degisim_imzasi(d.get("eski", ""), d.get("yeni", ""))
        if not imza:
            continue
        anahtar = (frozenset(aileler(d.get("kural", ""))), imza)
        if anahtar in onder:
            out[i] = onder[anahtar]
        else:
            onder[anahtar] = i
    return out


def inceleme_yaz(no: int, uygulanan: list, karar: list, bilgi: list, kuru: bool,
                 terimler: list | None = None) -> str:
    out = [f"# {no}. bölüm — inceleme", ""]
    if kuru:
        out += ["_Kuru çalıştırma: bölüm dosyasına hiçbir şey yazılmadı._", ""]
    out += [f"## Uygulananlar ({len(uygulanan)})", ""]
    if uygulanan:
        out += ["Bunlar bölüme yazıldı. Birini geri almak için kutusunu [x] yapın; --kararlar",
                "✓'yi ✗'ye döndürür (inceleme sayfasında: g).", ""]
    for d in uygulanan:
        out += [f"- ¶{d.get('p') or '?'} · {d.get('kural', '')} ({', '.join(d.get('kaynak', []))})"
                + (" · otomatik" if d.get("otomatik") else ""),
                f"  ✗ {tek_satir(d['eski'])}", f"  ✓ {tek_satir(d['yeni'])}", f"  {GERI_KUTU}"]
    out += ["", f"## Kararınızı bekleyenler ({sum(d.get('sinif') != 'SABLON' for d in karar)})", "",
            "Her maddede bir kutuyu [x] yapın; ✓ satırını isterseniz değiştirin. 'hep' kararı",
            "karar defterine yazar, aynı örüntü bir daha sorulmaz. Sonra:",
            f"`./calistir.sh sonra {no} --kararlar`", ""]
    # SABLON maddeleri ayri bolumde: metin icin degil sablon icin geri bildirim.
    # Numaralar iki bolumde de K1'den devam eder; --kararlar hepsini ayni okur.
    metin_k = [d for d in karar if d.get("sinif") != "SABLON"]
    sablon_k = [d for d in karar if d.get("sinif") == "SABLON"]
    izleyen = ayni_degisiklik(metin_k + sablon_k)
    izleyenler = {}
    for i, o in izleyen.items():
        izleyenler.setdefault(o, []).append(i)
    for i, d in enumerate(metin_k + sablon_k, 1):
        if i == len(metin_k) + 1:
            out += [f"## Şablon geri bildirimi ({len(sablon_k)})", "",
                    "Dondurulmuş ya da öngörülmüş satırlar. Kabul, yalnız bu bölümün metnini değiştirir;",
                    "kalıp başka bölümlerde de geçiyorsa şablona/sözlüğe ayrıca işlenmeli.", ""]
        bozuk = bozuk_oneri(d.get("eski", ""), d.get("yeni", ""))
        out += [f"### K{i} · ¶{d.get('p') or '?'} · {d.get('sinif', 'KARAR')} · {d.get('kural', '')}",
                f"✗ {tek_satir(d.get('eski', ''))}",
                f"✓ {tek_satir(d.get('yeni', ''))}",
                f"Neden: {d.get('neden', '')}",
                f"Kaynak: {', '.join(d.get('kaynak', []))}"]
        sm = d.get("sadakat_motor")
        if sm:
            sm = [sm] if isinstance(sm, str) else sorted(set(sm))
            out.append(f"Sadakat: {'ikisi' if len(sm) > 1 else sm[0]}")
        if bozuk:
            out.append(f"Dikkat: {bozuk}; ✓ satırını düzeltmeden kabul etmeyin.")
        if i - 1 in izleyen:
            out.append(f"Grup: K{izleyen[i - 1] + 1} ile aynı değişiklik; kutusu boş kalırsa onun kabul/ret kararını alır.")
        elif i - 1 in izleyenler:
            out.append("Aynı değişiklik: " + ", ".join(f"K{j + 1}" for j in izleyenler[i - 1])
                       + " (kabul/ret kararınız, boş bıraktıklarınıza da geçer).")
        out += ["[ ] kabul   [ ] ret   [ ] hep", ""]
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


# ------------------------------------------------------------------ inceleme katmanlari
# 5 Kas: eski bolumlerde bolum basina 30-75 karar. Maddeler is turune gore
# katmanlanir; uzun maddelere degisen sozcukleri gosteren 'Fark:' satiri eklenir;
# dusuk oncelikli katmanin tek kutusu isaretsiz maddelerin hepsini reddeder.

KATMANLAR = [("anlam", "1. Anlam: kaynağa göre düzeltmeler",
              "Önce bunlar. Çincede olan bir şey düşmüş, eklenmiş ya da kaymış."),
             ("hizli", "2. Hızlı: küçük değişiklikler",
              "Cümlenin çoğu aynı kalıyor; Fark satırına bakmak yeter."),
             ("terim", "3. Terim ve tutarlılık kararları",
              "Bölümler arası bir karar. Bütün bölümlerdekiler bir arada: "
              "Reports/sonra/TERIM_SORULARI.md (sonra.py A-B --terim-listesi). Bir kez 'hep' ile verin."),
             ("dusuk", "4. Düşük öncelik",
              "Karakter tavrı (B), tutarlılık (C), emin olunmayan, yalnız triyajın önerdiği ve "
              "yalnız bir pekiştireci ya da dönem/gotik sözcüğü atan 'eklenmiş' maddeler.")]
TOPLU_RET = "[ ] Bu bölümdeki işaretsiz maddelerin hepsi: ret"
TERIM_DESEN = re.compile(r"terim kararı|sözlük|words\.md|bölüm boyunca|bölümler arası|"
                         r"birlikte değişmeli|yerleşik karşılık|yerleşik yerelleştirme", re.I)


def kelime_farki(eski: str, yeni: str, baglam: int = 3) -> str:
    """'… sabit [-eski-] {+yeni+} sabit …': yalniz degisen sozcukler, az baglamla."""
    import difflib
    a, b = eski.split(), yeni.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            ayni = a[i1:i2]
            if len(ayni) > 2 * baglam + 1:
                bas = ayni[:baglam] if out else []
                son = ayni[-baglam:] if i2 < len(a) else []
                out += bas + ["…"] + son
            else:
                out += ayni
            continue
        if i2 > i1:
            out.append("[-" + " ".join(a[i1:i2]) + "-]")
        if j2 > j1:
            out.append("{+" + " ".join(b[j1:j2]) + "+}")
    while out and out[-1] == "…":
        out.pop()
    return " ".join(out)


LINT_KURALLARI = Path(os.environ.get("LOTM_LINT_KURALLARI") or BETIKLER / "lint" / "lint-kurallari.yml")
SAPKASIZ = str.maketrans("âîûÂÎÛ", "aiuAIU")
_SUS = None


def sus_sozcukleri() -> list:
    """lint-kurallari.yml > eklenmis_sus + register (donem, gotik): sapkasiz, kucuk harf."""
    global _SUS
    if _SUS is None:
        try:
            import yaml
            k = lotm.yaml_yukle(LINT_KURALLARI.read_text(encoding="utf-8")) or {}  # C yukleyici
        except Exception:  # kural dosyasi yoksa ozellik sessizce kapali
            k = {}
        es, reg = k.get("eklenmis_sus") or {}, k.get("register") or {}
        ham = " ".join(str(x or "") for x in (es.get("pekistirec"), es.get("atmosfer"),
                                               reg.get("donem"), reg.get("gotik")))
        _SUS = sorted({w.replace("_", " ").translate(SAPKASIZ).lower() for w in ham.split()})
    return _SUS


def eklenen_sus(eski: str, yeni: str, en_cok: int = 3) -> str | None:
    """✗'den ✓'ye dusen sozcukler (en cok `en_cok`) bir pekistirec ya da
    donem/gotik sozcuk iceriyorsa o sozcuk; yoksa None."""
    import difflib
    a = re.findall(r"[^\W\d_]+", eski.translate(SAPKASIZ).lower())
    b = re.findall(r"[^\W\d_]+", yeni.translate(SAPKASIZ).lower())
    dusen = []
    for op, i1, i2, _, _ in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op in ("delete", "replace"):
            dusen += a[i1:i2]
    if not dusen or len(dusen) > en_cok:
        return None
    metin = " ".join(dusen)
    for w in sus_sozcukleri():
        desen = rf"(?<![^\W\d_]){re.escape(w)}" + (r"" if len(w) >= 5 else r"(?![^\W\d_])")
        if re.search(desen, metin):
            return w
    return None


def madde_katmani(blok: str) -> str:
    bas = re.match(r"### K\d+ · ¶\S+ · \S+ · (.*)", blok)
    kural = bas.group(1) if bas else ""
    neden = (re.search(r"^Neden: (.*)$", blok, re.M) or [None, ""])[1]
    kaynak = (re.search(r"^Kaynak: (.*)$", blok, re.M) or [None, ""])[1]
    x = (re.search(r"^✗ (.*)$", blok, re.M) or [None, ""])[1]
    v = (re.search(r"^✓ (.*)$", blok, re.M) or [None, ""])[1]
    if TERIM_DESEN.search(neden) or re.search(r"terim (?:kayması|karşılığı|daralması)|unvan", kural, re.I):
        return "terim"
    if (re.search(r"sadakat [BC]\b", kural) and not re.search(r"sadakat [AD]\b", kural)) \
            or re.search(r"emin değil|yerelleştirme\?", neden) or kaynak.strip() == "triyaj":
        return "dusuk"
    # 7 Kas: yalniz bir pekistirec/donem-gotik sozcugu atan "eklenmis" maddesi
    # cevirmenin atmosfer tercihi; cogunlukla ret (lint-kurallari.yml > eklenmis_sus).
    if re.search(r"sadakat A\b[^+]*(?:eklen|abart|pekiştir)", kural) and eklenen_sus(x, v):
        return "dusuk"
    if benzerlik(x, v) >= KESIN_ORAN:
        return "hizli"
    return "anlam"


def fark_ekle(blok: str) -> str:
    """Uzun maddeye ✓ satirinin ardina 'Fark:' satiri (yoksa)."""
    if re.search(r"^Fark: ", blok, re.M):
        return blok
    x = re.search(r"^✗ (.*)$", blok, re.M)
    v = re.search(r"^✓ (.*)$", blok, re.M)
    if not (x and v) or len(x.group(1)) < 50 or x.group(1) == v.group(1):
        return blok
    return blok[:v.end()] + "\nFark: " + kelime_farki(x.group(1), v.group(1)) + blok[v.end():]


def inceleme_katmanla(metin: str) -> str:
    """5_inceleme.md'nin karar maddelerini katmanlara dizer. Isaretler, ✓
    duzeltmeleri ve toplu ret kutusu korunur; tekrar uygulanabilir."""
    bolumler = re.split(r"\n(?=## )", metin)
    bas, karar_giris, maddeler, sablon, son, toplu = [], None, [], [], [], False
    for b in bolumler:
        baslik = b.split("\n", 1)[0]
        parcalar = re.split(r"\n(?=### K\d+ )", b)
        if baslik.startswith("## Şablon geri bildirimi"):
            sablon.append(b)
        elif baslik.startswith("## Kararınızı bekleyenler"):
            karar_giris = parcalar[0]
            maddeler += [m.rstrip() for m in parcalar[1:]]
        elif any(baslik.startswith("## " + ad.split(":")[0]) for _, ad, _ in KATMANLAR):
            toplu |= bool(re.search(r"\[[xX✓✔]\] Bu bölümdeki işaretsiz", parcalar[0]))
            maddeler += [m.rstrip() for m in parcalar[1:]]
        elif karar_giris is None:
            bas.append(b)
        else:
            son.append(b)
    if karar_giris is None:
        return metin
    gruplar = {k: [] for k, _, _ in KATMANLAR}
    for m in maddeler:
        gruplar[madde_katmani(m)].append(fark_ekle(m))
    not_ = "\n\nMaddeler dört katmanda"
    karar_giris = karar_giris.split(not_)[0]
    out = bas + [karar_giris.rstrip() + "\n\nMaddeler dört katmanda; numaralar değişmez, sırayla gitmek "
                 "gerekmez. 4. katmandaki tek kutu, orada işaretsiz kalan her maddeyi reddeder."]
    for k, ad, aciklama in KATMANLAR:
        if not gruplar[k]:
            continue
        g = [f"## {ad} ({len(gruplar[k])})", "", aciklama]
        if k == "dusuk":
            g.append(TOPLU_RET.replace("[ ]", "[x]") if toplu else TOPLU_RET)
        out.append("\n".join(g) + "\n\n" + "\n\n".join(gruplar[k]))
    out += [s.rstrip() for s in sablon + son]
    return "\n\n".join(x.rstrip() for x in out) + "\n"


def terim_listesi(nolar: list) -> str:
    """Bolumlerin 3. katmanini (terim kararlari) tek dosyada toplar, kurala gore."""
    gruplar = {}
    for no in nolar:
        inc = RAPOR / f"Ch_{no}" / "5_inceleme.md"
        if not inc.exists():
            continue
        for b in re.split(r"\n(?=## )", inc.read_text(encoding="utf-8")):
            if not b.startswith("## " + KATMANLAR[2][1]):
                continue
            for m in re.split(r"\n(?=### K\d+ )", b)[1:]:
                bas = re.match(r"### (K\d+) · (¶\S+) · \S+ · (.*)", m)
                kural = re.sub(r"\s+", " ", bas.group(3)).strip()
                # Ayni Cince terim farkli kural adlariyla gelir: once Nedendeki ZH'ye gore grupla.
                zh = re.search(r"ZH\s+([\u4e00-\u9fff]+)", m)
                anahtar = (f"ZH {zh.group(1)}" if zh else
                           re.sub(r"^(sadakat [A-DŞ]|okuma [\d.]+\w*|dönem D\.\d)\s*", "", kural) or kural)
                gruplar.setdefault(anahtar, []).append(
                    f"- {no}. bölüm {bas.group(2)} {bas.group(1)}\n" + "\n".join(
                        "  " + s for s in m.splitlines()[1:] if s.startswith(("✗", "✓", "Neden", "["))))
    satirlar = [f"# Terim ve tutarlılık soruları ({time.strftime('%Y-%m-%d')})", "",
                "Her bölümün 5_inceleme.md'sindeki 3. katman, kurala göre bir arada. Kararı bölüm "
                "dosyasında işaretleyin; bir kez 'hep' denen karar sonraki bölümlerde sorulmaz.", ""]
    for anahtar, ms in sorted(gruplar.items(), key=lambda kv: -len(kv[1])):
        satirlar += [f"## {anahtar} ({len(ms)})", ""] + ms + [""]
    yol = RAPOR / "TERIM_SORULARI.md"
    yol.write_text("\n".join(satirlar), encoding="utf-8")
    return f"{sum(len(v) for v in gruplar.values())} madde, {len(gruplar)} kural -> {yol}"


GERI_KUTU = "[ ] geri al"
UYG_BASI = re.compile(r"^- ¶(\S+) · (.*?) \(([^()]*)\)( · otomatik)?$")


def uygulanan_oku(metin: str) -> list:
    """'## Uygulananlar' maddeleri: [{"i", "p", "kural", "kaynak", "otomatik", "eski", "yeni",
    "geri"}]. 'geri' kutusu olmayan (7 Kas oncesi) dosyalarda geri None."""
    m = re.search(r"^## Uygulananlar.*?$(.*?)(?=^## |\Z)", metin, re.M | re.S)
    if not m:
        return []
    out, d = [], None
    for satir in m.group(1).splitlines():
        b = UYG_BASI.match(satir)
        if b:
            d = {"i": len(out) + 1, "p": b.group(1), "kural": b.group(2), "kaynak": b.group(3),
                 "otomatik": bool(b.group(4)), "eski": "", "yeni": "", "geri": None}
            out.append(d)
        elif d is not None:
            t = satir.strip()
            if t.startswith("✗ "):
                d["eski"] = t[2:].replace(" ⏎ ", "\n")
            elif t.startswith("✓ "):
                d["yeni"] = t[2:].replace(" ⏎ ", "\n")
            elif re.match(r"\[.\] geri al$", t):
                d["geri"] = t[1] in ("x", "X", "✓", "✔")
    return out


def geri_yaz(metin: str, i: int, geri: bool) -> str:
    """Uygulananlar'daki i. maddenin geri al kutusunu degistirir."""
    m = re.search(r"^## Uygulananlar.*?$(.*?)(?=^## |\Z)", metin, re.M | re.S)
    if not m:
        raise KeyError("Uygulananlar yok")
    parca, say, satirlar = m.group(1), 0, []
    bulundu = False
    for satir in parca.split("\n"):
        if UYG_BASI.match(satir):
            say += 1
        if say == i and re.match(r"\s*\[.\] geri al$", satir):
            satir = satir.replace(satir.strip(), f"[{'x' if geri else ' '}] geri al")
            bulundu = True
        satirlar.append(satir)
    if not bulundu:
        raise KeyError(f"geri al kutusu yok: {i}")
    return metin[:m.start(1)] + "\n".join(satirlar) + metin[m.end(1):]


def inceleme_oku(metin: str) -> list:
    """Isaretlenmis kararlar: [{"k", "p", "kural", "eski", "yeni", "kabul", "ret", "hep"}].
    Toplu ret kutusu isaretli bolumde, kutusu bos maddeler ret sayilir."""
    out, toplu_k = [], set()
    for bolum in re.split(r"\n(?=## )", metin):
        toplu = bool(re.search(r"\[[xX✓✔]\] Bu bölümdeki işaretsiz", bolum.split("\n### ", 1)[0]))
        for s in inceleme_oku_bolum(bolum):
            if toplu:
                toplu_k.add(s["k"])
            out.append(s)
    # Grup izleyeni bos birakildiysa onderin kabul/ret'ini alir (hep almaz: deftere bir kez yazilsin).
    # Toplu ret'ten once: onderi kabul edilen izleyen 4. katmanda kalsa da kabul edilir.
    karar = {s["k"]: s for s in out}
    for s in out:
        o = karar.get(s.get("grup"))
        if o and not (s["kabul"] or s["ret"]) and (o["kabul"] or o["ret"]):
            s["kabul"], s["ret"] = o["kabul"], o["ret"]
    for s in out:
        if s["k"] in toplu_k and not (s["kabul"] or s["ret"]):
            s["ret"] = s["toplu"] = True
    return out


def inceleme_oku_bolum(metin: str) -> list:
    out = []
    for blok in re.split(r"\n(?=### K\d+ )", metin)[1:]:
        bas = re.match(r"### K(\d+) · ¶(\S+) · (\S+) · (.*)", blok)
        x = re.search(r"^✗ (.*)$", blok, re.M)
        v = re.search(r"^✓ (.*)$", blok, re.M)
        kutu = re.search(r"\[(.)\] kabul\s+\[(.)\] ret\s+\[(.)\] hep", blok)
        if not (bas and x and v and kutu):
            continue
        isaret = [c.strip().lower() in ("x", "✓", "✔") for c in kutu.groups()]
        out.append({"k": int(bas.group(1)), "p": bas.group(2), "sinif": bas.group(3),
                    "kural": bas.group(4).strip(),
                    "on": bool(re.search(r"^Ön: ", blok, re.M)),
                    "smotor": (re.search(r"^Sadakat: (\S+)", blok, re.M) or [None, None])[1],
                    "eski": x.group(1).replace(" ⏎ ", "\n"), "yeni": v.group(1).replace(" ⏎ ", "\n"),
                    "kabul": isaret[0], "ret": isaret[1], "hep": isaret[2],
                    "grup": int(g.group(1)) if (g := re.search(r"^Grup: K(\d+)", blok, re.M)) else None})
    return out


# ------------------------------------------------------------------ istatistik

IST_BASLIK = "bolum\tk\taile\ton\tkarar"


def istatistik_kaydet(yol: Path, no: int, secimler: list) -> int:
    """Bolumun satirlarini yeniler (ayni bolum iki kez islenirse cift sayilmaz).
    Bir madde birden cok aileye dustuyse her aileye bir satir."""
    eski = yol.read_text(encoding="utf-8").splitlines()[1:] if yol.exists() else []
    kalan = [s for s in eski if s and s.split("\t")[0] != str(no)]
    yeni = []
    for s in secimler:
        karar = "kabul" if s["kabul"] else "ret" if s["ret"] else "bos"
        for a in sorted(aileler(s["kural"], s.get("sinif", "KARAR"))):
            yeni.append(f"{no}\t{s['k']}\t{a}\t{int(s.get('on', False))}\t{karar}")
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text("\n".join([IST_BASLIK] + kalan + yeni) + "\n", encoding="utf-8")
    return len(yeni)


MOTOR_BASLIK = "bolum\tk\tsinif\tkural\tsadakat\tkarar"


def motor_kaydet(yol: Path, no: int, secimler: list) -> int:
    """Cift sadakat kararlari: hangi motor buldu, kabul mu. Bolum yenilenir."""
    satir = [s for s in secimler if s.get("smotor")]
    if not satir:
        return 0
    eski = yol.read_text(encoding="utf-8").splitlines()[1:] if yol.exists() else []
    kalan = [s for s in eski if s and s.split("\t")[0] != str(no)]
    yeni = [f"{no}\t{s['k']}\t{s.get('sinif', 'KARAR')}\t{s['kural']}\t{s['smotor']}\t"
            f"{'kabul' if s['kabul'] else 'ret' if s['ret'] else 'bos'}" for s in satir]
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text("\n".join([MOTOR_BASLIK] + kalan + yeni) + "\n", encoding="utf-8")
    return len(yeni)


def motor_ozeti(yol: Path) -> str:
    """Bolum basina: ikisi / yalniz claude / yalniz codex bulgularinin kabul sayisi."""
    if not yol.exists():
        return ""
    say, bolumler = {}, set()
    for s in yol.read_text(encoding="utf-8").splitlines()[1:]:
        p = s.split("\t")
        if len(p) != 6:
            continue
        bolumler.add(p[0])
        x = say.setdefault(p[4], {"kabul": 0, "ret": 0, "bos": 0})
        x[p[5]] += 1
    n = len(bolumler) or 1
    satirlar = [f"Çift sadakat ({len(bolumler)} bölüm: {', '.join(sorted(bolumler, key=int))})",
                f"{'kim buldu':12} kabul  ret  boş  bölüm başına kabul"]
    for m in ("ikisi", "codex", "claude"):
        x = say.get(m, {"kabul": 0, "ret": 0, "bos": 0})
        satirlar.append(f"{m:12} {x['kabul']:5} {x['ret']:4} {x['bos']:4}  {x['kabul'] / n:.1f}")
    return "\n".join(satirlar)


def istatistik_ozeti(yol: Path) -> str:
    """Aile basina kabul/ret/bos, on-isareti kaldirilan ve terfi durumu."""
    if not yol.exists():
        return f"YOK: {yol}"
    say = {}
    for s in yol.read_text(encoding="utf-8").splitlines()[1:]:
        p = s.split("\t")
        if len(p) != 5:
            continue
        x = say.setdefault(p[2], {"kabul": 0, "ret": 0, "bos": 0, "kaldirilan": 0, "bolum": set()})
        x[p[4]] += 1
        x["bolum"].add(p[0])
        if p[3] == "1" and p[4] != "kabul":
            x["kaldirilan"] += 1
    satirlar = [f"{'aile':22} kabul  ret  boş  oran  ön-kaldırılan  bölüm  durum"]
    for a, x in sorted(say.items(), key=lambda kv: -(kv[1]["kabul"] + kv[1]["ret"])):
        karar = x["kabul"] + x["ret"]
        oran = x["kabul"] / karar if karar else 0
        durum = ("otomatiğe hazır" if karar >= TERFI_EN_AZ and oran >= TERFI_ORAN
                 else "") if a not in OTOMATIK else "otomatik"
        satirlar.append(f"{a:22} {x['kabul']:5} {x['ret']:4} {x['bos']:4}  {oran:4.0%}  "
                        f"{x['kaldirilan']:13} {len(x['bolum']):6}  {durum}")
    return "\n".join(satirlar)


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
    def __init__(self, no: int, parti_boyu: int, yanki_ek: tuple = ()):
        self.no = no
        self.yanki_ek = tuple(yanki_ek)
        self.klasor = RAPOR / f"Ch_{no}"
        self.dosya = BOLUMLER / f"{no:04d}.md"
        self.sablon = SABLONLAR / f"Ch_{no}.md"
        self.parti_boyu = parti_boyu
        self.zincir = self.klasor / "zincir.txt"

    def yayimlandi(self) -> bool:
        """Bolum yayimlanmis mi (front matter 'date:' simdiden once). Eski bolumun
        sablonu eski terimleri tasir; bkz. sablon_blogu. LOTM_SABLON_TAM=1 kapatir."""
        if os.environ.get("LOTM_SABLON_TAM", "") not in ("", "0") or not self.dosya.exists():
            return False
        return yayim_tarihi_gecti(self.dosya.read_text(encoding="utf-8"))

    def sablon_blogu(self, etiket: str) -> str:
        if not self.sablon.exists():
            return f"<{etiket}>\n(şablon yok: {self.sablon.name})\n</{etiket}>"
        metin = self.sablon.read_text(encoding="utf-8").rstrip()
        if self.yayimlandi():
            metin = YAYIMLANMIS_NOTU + "\n\n" + terim_tablolarini_at(metin)
        else:
            metin = SABLON_USTUNLUK + "\n\n" + metin
        return f"<{etiket}>\n{metin}\n</{etiket}>"

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
            f"{self.o_blogu()}"
            f"{self.durum_blogu()}"
            f"<bolum>\n{self.dosya.read_text(encoding='utf-8').rstrip()}\n</bolum>\n"
        )
        cikti = self.klasor / "1_okuma_cikti.md"
        yaz_defter_haric(girdi, metin, cikti)
        return [(girdi, cikti)]

    def o_blogu(self) -> str:
        """o_denetle.py'nin bulgulari okuma gecisine: betik yalniz yer gosterir,
        duzeltmeyi (ya da atlamayi) model verir. Bulgu yoksa ya da hizalama
        kurulamazsa bos dize; okuma onsuz da calisir."""
        try:
            import o_denetle
            bulgular = o_denetle.bulgular(self.no)
        except Exception:  # hizalama yok / ZH yok: yardimci adim, hat durmasin
            return ""
        if not bulgular:
            return ""
        satirlar = [f"- hizalama ¶{p}: {parca}" for p, parca in bulgular]
        return ("<o_bulgulari>\n"
                "Betik (o_denetle.py): Çincede 那 olmayan yerde \"o + sözcük\". ¶ numarası\n"
                "hizalama grubudur, okuma ¶'si değil; yeri parçadan bulun. \"o\" İngilizce\n"
                "\"the\" gibi tanımlık olarak kullanılmışsa `1.9 tanımlık o` adıyla düzeltme\n"
                "önerin (çoğu zaman \"o\" düşer); gerçekten geri gösteriyorsa yazmayın.\n"
                + "\n".join(satirlar) + "\n</o_bulgulari>\n\n")

    def durum_blogu(self) -> str:
        """Cevirmenin DURUM NOTU'su (cevir.py) okumaya: kendi bildirdigi gotik
        harcama, etiketler ve yeni tik. Elle cevrilmis bolumde dosya yoktur."""
        yol = CEVIRI / f"Ch_{self.no}" / "durum_notu.md"
        if not yol.exists() or not yol.read_text(encoding="utf-8").strip():
            return ""
        return ("<cevirmen_durum_notu>\n"
                "Çevirmenin kendi raporu, kanıt değil. Kullanımı: (1) \"harcanan gotik\n"
                "sözcükler\" listesini metinle karşılaştırın; listede olmayan ya da\n"
                "bütçeyi (gerçek doruk başına 3–5) aşan gotik sözcükler okuma 1.x bulgusudur.\n"
                "(2) \"Yeni tik\" satırındaki kalıbı bölümün geri kalanında arayın; başka\n"
                "yerlerde de varsa her birini ayrı bulgu olarak verin. (3) Etiket sayısı\n"
                "metindeki [BELİRSİZ]/[ÖNERİ] sayısıyla uyuşmuyorsa bunu Bilgi olarak yazın.\n"
                + yol.read_text(encoding="utf-8").strip() + "\n</cevirmen_durum_notu>\n\n")

    # -- donem (istege bagli)
    def donem(self) -> list:
        """Donem uyumu gecisi: bolum + sablon + betik adaylari (donem_denetle.py)."""
        import donem_denetle
        girdi = self.klasor / "1b_donem_girdi.md"
        metin = self.dosya.read_text(encoding="utf-8")
        yaz_defter_haric(girdi, (
            f"{istem('donem')}\n\n---\n\n"
            f"{kararlar_blogu()}"
            f"{self.sablon_blogu('bolum_sablonu')}\n\n"
            f"{ses_blogu(self.no, metin)}\n\n"
            f"{donem_denetle.blok(self.no, metin)}\n\n"
            f"<bolum>\n{metin.rstrip()}\n</bolum>\n"), self.klasor / "1b_donem_cikti.md")
        return [(girdi, self.klasor / "1b_donem_cikti.md")]

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
        yanki_blok = yanki_blogu(self.no, self.yanki_ek)
        ciftler = []
        for i, nolar in enumerate(partiler, 1):
            parcalar = [istem("sadakat"), "---", f"Parti {i}/{len(partiler)}: ¶{nolar[0]}–¶{nolar[-1]}",
                        f"<aligned>\n{hizali_metin(gruplar, nolar)}\n</aligned>",
                        self.sablon_blogu("chapter_template")]
            if kararlar_blogu():
                parcalar.append(kararlar_blogu().rstrip())
            if yanki_blok:
                parcalar.append(yanki_blok)
            ses = ses_blogu(self.no, " ".join(gruplar[k]["TR"] for k in nolar))
            if ses:
                parcalar.append(ses)
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
            cikti = self.klasor / f"2_sadakat_cikti_{i:02d}.md"
            yaz_defter_haric(girdi, "\n\n".join(parcalar) + "\n", cikti)
            ciftler.append((girdi, cikti))
        # Parti sayisi azaldiysa artakalan eski girdiler kafa karistirmasin.
        for eski in self.klasor.glob("2_sadakat_girdi_*.md"):
            if eski not in [g for g, _ in ciftler]:
                eski.unlink()
        not_ = None
        if sorular is not None:
            not_ = f"{len(sorular)} SADAKAT? ({len(yersiz)} tanesinin yeri bulunamadi)"
        if yanki_blok:
            n = len(YANKI_BASLIK.findall(yanki_blok))
            not_ = (not_ + "; " if not_ else "") + f"{n} yanki girisi"
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

        def motoru(p):
            m = cikti_motoru(p, "")
            if m:
                return m
            mt = p.with_name(p.name + ".motor")
            return mt.read_text(encoding="utf-8").strip() if mt.exists() else "claude"

        sadakat_dosyalari = sorted(k.glob("2_sadakat_cikti_*.md"))
        motorlar = {motoru(p) for p in sadakat_dosyalari}
        sadakat = "\n\n".join(f"<!-- {p.name} · motor: {motoru(p)} -->\n{p.read_text(encoding='utf-8').strip()}"
                              for p in sadakat_dosyalari) or "(yok)"
        if len(motorlar) > 1:
            sadakat = (
                "ÇİFT SADAKAT: aynı partiler iki ayrı model tarafından, birbirinden habersiz "
                f"okundu ({', '.join(sorted(motorlar))}; her bloğun başındaki `motor:` etiketi). "
                "Her sadakat bulgusuna `sadakat_motor` alanı ekle: aynı yer ve aynı sorun için "
                "ikisi de bulgu verdiyse tek maddede birleştir ve iki motoru da yaz "
                '(`"sadakat_motor": ["claude", "codex"]`); biri verdiyse yalnız onu. Aynı yerde '
                "farklı sorunlar ayrı maddedir. `yeni` için iki öneri farklıysa birini harfi "
                "harfine al, ötekini `neden`'e yaz. Bu modda sadakat kaynaklı madde KESIN "
                "olamaz, KARAR'dır.\n\n" + sadakat)
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
        if (k / "1b_donem_cikti.md").exists():
            metin += (
                "\n<donem>\n"
                "Dönem uyumu geçişi (çağdaş sözcükler). Bulguları okuma üslup bulguları gibidir: "
                "deftere açıkça uymadıkça KARAR, `kaynak` [\"donem\"], `kural` "
                "`dönem D.N <sözcük>` (örnek: `dönem D.1 detay`, `dönem D.2 falan`; ek yok, "
                "sözcüğün yalın hâli). Aynı cümleye başka bir geçiş de dokunuyorsa ALANLAR'daki gibi ayrı madde yazılır. "
                "ŞÜPHELİ, DÖNEM? ve (3) Bırakılan adaylar satırları `bilgi`'ye tek satır.\n\n"
                f"{oku('1b_donem_cikti.md')}\n</donem>\n")
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
    def son_adim(self, kuru: bool, kesin_yok: bool = False) -> str:
        import json
        cikti = self.klasor / "5_birlestir_cikti.md"
        try:
            veri = json_ayikla(cikti.read_text(encoding="utf-8"))
        except (ValueError, KeyError) as e:
            return f"HATA: 5_birlestir_cikti.md JSON olarak okunamadi ({e})"
        asil = self.dosya.read_text(encoding="utf-8")
        for d in veri.get("duzeltmeler", []):
            if d.get("sadakat_motor") and d.get("sinif") == "KESIN":
                d["sinif"] = "KARAR"  # cift sadakat: her bulgu kararla sayilsin
        yayimli = self.yayimlandi()
        if yayimli:
            # Eski sablona geri bildirim: o sablon bir daha kullanilmaz.
            atilan = [d for d in veri.get("duzeltmeler", []) if d.get("sinif") == "SABLON"]
            veri["duzeltmeler"] = [d for d in veri.get("duzeltmeler", []) if d.get("sinif") != "SABLON"]
            if atilan:
                veri.setdefault("bilgi", []).append(
                    {"p": None, "not": f"yayımlanmış bölüm: {len(atilan)} şablon geri bildirimi gösterilmedi"})
        for d in veri.get("duzeltmeler", []):
            if otomatige_uygun(d):
                d["sinif"], d["otomatik"] = "KESIN", True
        yeni, uygulanan, karar = uygula(asil, veri.get("duzeltmeler", []), kesin_yok=kesin_yok)
        for d in karar:  # boyut/sayi yuzunden uygulanamadiysa yine elle sorulur
            d.pop("otomatik", None)
        inceleme = self.klasor / "5_inceleme.md"
        try:
            # Yayimlanmis bolumde sablonun A.2'si eski olabilir: veriye eklenecek terim onerilmez.
            terimler = [] if yayimli else self.yeni_terimler()
        except Exception as e:  # terim listesi yardimci; hat onun yuzunden durmasin
            terimler = []
            veri.setdefault("bilgi", []).append({"p": None, "not": f"yeni terim listesi kurulamadı: {e}"})
        inceleme.write_text(inceleme_katmanla(inceleme_yaz(self.no, uygulanan, karar, veri.get("bilgi", []),
                                                            kuru, terimler)), encoding="utf-8")
        if kuru:
            return f"kuru: {len(uygulanan)} uygulanirdi, {len(karar)} karar -> 5_inceleme.md"
        if uygulanan:
            yedek_al(f"sonra-Ch_{self.no}", self.dosya)
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
        # Otomatik/kesin uygulananlardan geri alinanlar: ✓ metinde tek ise ✗'ye doner.
        geri_alinan, geri_yok = [], []
        onceki = uygulanan_oku(inceleme.read_text(encoding="utf-8"))
        for u in onceki:
            if not u["geri"]:
                continue
            if u["yeni"] and metin.count(u["yeni"]) == 1:
                metin = metin.replace(u["yeni"], u["eski"], 1)
                geri_alinan.append(u["i"])
            elif not (u["eski"] and metin.count(u["eski"]) == 1 and u["yeni"] not in metin):
                geri_yok.append(u["i"])  # ikinci --kararlar'da zaten geri alinmis olan sessiz
        # Otomatik aileler istatistikte izlensin: geri alinmayan kabul, alinan ret.
        # (Kesinler sayilmaz: oranlari incelemeden gecmis maddelerin olsun.)
        oto_secim = [{"k": f"O{u['i']}", "kural": u["kural"], "sinif": "KARAR",
                      "kabul": not u["geri"], "ret": bool(u["geri"])}
                     for u in onceki if u["otomatik"] and u["geri"] is not None]
        for s in secimler:
            if s["kabul"]:
                if metin.count(s["eski"]) == 1:
                    metin = metin.replace(s["eski"], s["yeni"], 1)
                    uygulanan.append(s["k"])
                else:
                    bulunamayan.append(s["k"])
            # Elle verilen donem reddi 'hep' olmadan da deftere gider (12 Kas; toplu ret gitmez): donem kurali sozcuge
            # ozgudur ("dönem D.1 içerik"), defter ozeti ret'i "ayni sozcuk degisikligini
            # onerme" diye verir; yoksa her yeniden kosuda ayni karsilik yine sorulur.
            donem_ret = s["ret"] and not s.get("toplu") and s["kural"].startswith("dönem ")
            if (s["hep"] and (s["kabul"] or s["ret"])) or donem_ret:
                hukum = "kabul" if s["kabul"] else "ret"
                defter.append(f"- {hukum} · {s['kural']} — örnek: «{tek_satir(s['eski'])}» → "
                              f"«{tek_satir(s['yeni'])}» ({self.no}. bölüm ¶{s['p']})")
        terimler = terimler_oku(inceleme.read_text(encoding="utf-8"))
        if not kuru:
            # Bolum ve words.md yazilmadan once (eskiden --kararlar yedeksizdi).
            yedek_al(f"sonra-kararlar-Ch_{self.no}",
                     *([self.dosya] if uygulanan or geri_alinan else []), *([KELIMELER] if terimler else []))
            istatistik_kaydet(ISTATISTIK, self.no, secimler + oto_secim)
            motor_kaydet(MOTOR_IST, self.no, secimler)
            if terimler:
                kelimelere_ekle(KELIMELER, terimler, self.no)
            if uygulanan or geri_alinan:
                self.dosya.write_text(metin, encoding="utf-8")
            if defter:
                # Ayni karar (hukum, eski, yeni) zaten defterdeyse yeniden yazilmaz:
                # --kararlar'in ikinci kez kosulmasi defterde cift satir birakiyordu.
                eski_defter = KARARLAR.read_text(encoding="utf-8") if KARARLAR.exists() else ""
                var = {(m.group(1), m.group(3), m.group(4)) for m in
                       map(DEFTER_SATIRI.match, eski_defter.splitlines()) if m}
                defter = [d for d in defter if not ((m := DEFTER_SATIRI.match(d))
                                                    and (m.group(1), m.group(3), m.group(4)) in var)]
            if defter:
                bas = "" if KARARLAR.exists() else (
                    "# Karar defteri\n\nsonra.py'nin inceleme adımında 'hep' denen kararlar. "
                    "Her geçişe verilir; elle düzenlenebilir.\n\n")
                with KARARLAR.open("a", encoding="utf-8") as f:
                    f.write(bas + "\n".join(defter) + "\n")
        if not kuru:
            import json
            (self.klasor / KARARLAR_ISLENDI).write_text(json.dumps(
                {"zaman": time.strftime("%Y-%m-%d %H:%M"), "uygulanan": len(uygulanan),
                 "defter": len(defter), "bulunamayan": bulunamayan,
                 "geri_alinan": geri_alinan, "geri_alinamayan": geri_yok}, ensure_ascii=False), encoding="utf-8")
        sonuc = (f"{len(uygulanan)} karar uygulandi, {len(defter)} kalici karar deftere yazildi, "
                 f"{len(terimler)} terim words.md'ye eklendi"
                 + (f", {len(geri_alinan)} uygulanan geri alindi" if geri_alinan else "")
                 + (f"; metinde bulunamayan: {', '.join('K%d' % k for k in bulunamayan)}"
                    if bulunamayan else "")
                 + (f"; geri alinamayan (✓ metinde tek degil): {', '.join('U%d' % i for i in geri_yok)}"
                    if geri_yok else ""))
        return ("kuru: " if kuru else "") + sonuc

    # -- triyaj
    def triyaj(self) -> list:
        girdi = self.klasor / "4_triyaj_girdi.md"
        zincir = self.zincir.read_text(encoding="utf-8") if self.zincir.exists() else "(yok)"
        metin = (
            f"{istem('triyaj')}\n\n---\n\n"
            f"Not: aşağıdaki çıktı tam zincir (hepsi) değil, `./calistir.sh bolum {self.no}` "
            f"zinciridir. Üzerinde çalışılan bölüm {self.no}; henüz yayımlanmadı. Haftalık "
            f"girdiler (`<uygulanan_duzeltmeler>`, `<bilinen>`, `<tikler>`, testler) bu kipte "
            f"verilmez: eksik oldukları raporlanmaz, Uygulananlar ve Tikler bölümleri atlanır.\n\n"
            f"<calistir_ciktisi>\n{zincir.rstrip()}\n</calistir_ciktisi>\n"
        )
        yaz_degisirse(girdi, metin)
        return [(girdi, self.klasor / "4_triyaj_cikti.md")]


# ------------------------------------------------------------------ otomatik

# Butun claude -p cagrilari (sonra, cevir, zincir_oku) buradan gecer: model ve
# efor sabit, Claude Code'un o makinedeki varsayilani (/model) hatti degistirmesin.
# "opus" takma adi en yeni Opus'a cozulur. Bos dize = bayrak hic verilmez.
VARSAYILAN_MODEL = os.environ.get("LOTM_MODEL", "opus")
VARSAYILAN_EFOR = os.environ.get("LOTM_EFOR", "high")


def claude_komutu(model: str | None, araclar: list | None = None,
                  efor: str | None = None) -> list:
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
    p = subprocess.run(komut, input=girdi, capture_output=True, text=True, timeout=sure, cwd=cwd)
    if p.returncode != 0 and "--effort" in komut and "effort" in p.stderr.lower():
        print("  UYARI: claude --effort'u tanimadi, efor bayragi olmadan yeniden deneniyor "
              "(Claude Code'u guncelleyin ya da LOTM_EFOR= ile kapatin)", flush=True)
        i = komut.index("--effort")
        komut = komut[:i] + komut[i + 2:]
        p = subprocess.run(komut, input=girdi, capture_output=True, text=True, timeout=sure, cwd=cwd)
    return p


# Gecis basina motor (3 Kas): sadakat'i ceviriyi yapan modelden FARKLI bir
# modelle okutmak icin. Varsayilan claude; LOTM_MOTOR_<ADIM>=codex (ornek:
# LOTM_MOTOR_SADAKAT=codex) ya da --motor sadakat=codex. Codex: ChatGPT
# aboneligiyle gelen 'codex exec'; stdin'den okur, son cevabi
# --output-last-message dosyasina yazar (ekrana yazdigi baslik/iz cikmaz).
MOTORLAR = ("claude", "codex")
CODEX_EFOR = os.environ.get("LOTM_CODEX_EFOR", "high")
CODEX_MODEL = os.environ.get("LOTM_CODEX_MODEL", "")  # bos: codex'in varsayilani


# Varsayilan motorlar (3 Kas): sadakat codex, cunku ceviriyi Claude yapiyor ve
# her model kendi kaymasini dogal bulur (ch70: iki motorun bulgulari yalniz
# bir yerde ortustu). Codex yoksa claude'a duser.
VARSAYILAN_MOTOR = {"sadakat": "codex"}


# Cift sadakat (3 Kas): ayni girdiyi iki motor birbirinden habersiz okur;
# ikincinin ciktisi 2_sadakat_cikti_KK.<motor>.md. birlestir her bulguya
# sadakat_motor yazar, inceleme "Sadakat: ikisi|claude|codex" satiri tasir,
# kararlar Tools/karar_motor.tsv'ye gider. Adil olsun diye sadakat kaynakli
# hicbir madde KESIN uygulanmaz: hepsi kararla sayilir.
CIFT = os.environ.get("LOTM_CIFT_SADAKAT", "") not in ("", "0")
MOTOR_IST = Path(os.environ.get("LOTM_MOTOR_IST") or KOK / "Tools" / "karar_motor.tsv")


def ikinci_motor(birinci: str) -> str:
    return "claude" if birinci == "codex" else "codex"


def cikti_motoru(cikti: Path, varsayilan: str) -> str:
    """2_sadakat_cikti_01.claude.md -> claude; ekisiz ad varsayilan motorundur."""
    m = re.match(r".*_\d+\.([a-z]+)\.md$", cikti.name)
    return m.group(1) if m and m.group(1) in MOTORLAR else varsayilan


def motor_sec(adim: str, secimler: dict | None = None) -> str:
    m = ((secimler or {}).get(adim) or os.environ.get(f"LOTM_MOTOR_{adim.upper()}")
         or VARSAYILAN_MOTOR.get(adim, "claude"))
    if m == "codex" and not shutil.which(shlex.split(os.environ.get("LOTM_CODEX", "codex exec"))[0]):
        print(f"  UYARI: {adim} icin codex bulunamadi, claude ile calisiyor", flush=True)
        m = "claude"
    if m not in MOTORLAR:
        raise SystemExit(f"bilinmeyen motor: {m} ({', '.join(MOTORLAR)})")
    return m


def codex_komutu(son_mesaj: Path) -> list:
    komut = shlex.split(os.environ.get("LOTM_CODEX", "codex exec"))
    komut += ["-", "--output-last-message", str(son_mesaj), "-s", "read-only",
              "-c", f"model_reasoning_effort={CODEX_EFOR}"]
    if CODEX_MODEL:
        komut += ["-m", CODEX_MODEL]
    return komut


# Arac gerektirmeyen gecislere stdin'de eklenen not (8 Kas). Codex okuma/duzeltme
# oturumlarinin cogu AGENTS.md ve bolum dosyasini diskte ariyor, her arama turu
# tum baglami yeniden yukluyordu. Metin uzerinde hesap (python ile sayma) serbest.
# Girdi dosyasina yazilmaz, bu yuzden gecisler ESKIMIS olmaz.
DOSYA_ARAMA_NOTU = ("\n\n---\nNot: Bu iş için gereken her şey bu mesajda (bölüm metni, şablon, "
                    "defter). AGENTS.md'yi, bölüm dosyasını ya da başka bir dosyayı diskte arama "
                    "veya açma; doğrudan bu girdiye göre cevap ver.\n")


def yurut(girdi: Path, cikti: Path, model: str | None, sure: int,
          araclar: list | None = None, motor: str = "claude") -> bool:
    """Taze bir oturum: girdi stdin'den, cevap ciktiya. Hata olursa cikti yazilmaz."""
    if motor in KOTA_DOLU:
        print(f"  ATLANDI {motor}: {girdi.name} (kota dolu: {KOTA_DOLU[motor]})", flush=True)
        return False
    print(f"  {motor}: {girdi.name} -> {cikti.name} ...", flush=True)
    son = cikti.with_name(cikti.name + ".codex-son")
    metin_girdi = girdi.read_text(encoding="utf-8")
    if not araclar and os.environ.get("LOTM_DOSYA_NOTU", "1") != "0":
        metin_girdi += DOSYA_ARAMA_NOTU
    try:
        if motor == "codex":
            son.unlink(missing_ok=True)
            p = subprocess.run(codex_komutu(son), input=metin_girdi,
                               capture_output=True, text=True, timeout=sure, cwd=BETIKLER)
        else:
            p = claude_calistir(claude_komutu(model, araclar), metin_girdi,
                                sure, BETIKLER)
    except FileNotFoundError:
        print(f"  HATA: {motor} komutu bulunamadi (LOTM_CLAUDE / LOTM_CODEX ile verin)")
        return False
    except subprocess.TimeoutExpired:
        print(f"  HATA: {sure} sn icinde bitmedi")
        return False
    metin = p.stdout
    if motor == "codex":
        metin = son.read_text(encoding="utf-8") if son.exists() else ""
        son.unlink(missing_ok=True)
    if p.returncode != 0 or not metin.strip():
        hata = (p.stderr or p.stdout).strip()[-400:]
        print(f"  HATA (cikis {p.returncode}): {hata}")
        if KOTA.search(hata):
            KOTA_DOLU[motor] = tek_satir(hata)[-160:]
            # Ebeveyn (paralel kip) bu satiri arar.
            print(f"  KOTA {motor}: {KOTA_DOLU[motor]}", flush=True)
        return False
    cikti.write_text(metin, encoding="utf-8")
    if motor != "claude":
        (cikti.with_name(cikti.name + ".motor")).write_text(motor + "\n", encoding="utf-8")
    else:
        cikti.with_name(cikti.name + ".motor").unlink(missing_ok=True)
    return True


# ------------------------------------------------------------------ ana

bolum_listesi = lotm.bolum_listesi  # eski adiyla da cagrilabilsin (ses_ayari, testler)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bolum sonrasi denetim hatti.")
    ap.add_argument("no", metavar="BOLUM",
                    help="bolum numarasi, aralik ya da liste: 61, 61-64, 61,63,70-72")
    ap.add_argument("--otomatik", nargs="*", choices=MODEL_ADIMLARI + ("donem",), metavar="ADIM",
                    help="eksik/eskimis ciktilari claude -p ile uret; adim verilmezse hepsi")
    ap.add_argument("--kararlar", action="store_true",
                    help="5_inceleme.md'de isaretlenen kararlari uygula, 'hep'leri deftere yaz")
    ap.add_argument("--kuru", action="store_true", help="bolum dosyasina ve deftere yazma")
    ap.add_argument("--istatistik", action="store_true",
                    help="kural ailelerinin kabul/ret sayilari (Tools/karar_istatistik.tsv); "
                         "no verilirse once o bolumun 5_inceleme.md'si kaydedilir")
    ap.add_argument("--bastan", action="store_true",
                    help="uygulama yapilmis olsa da hatti bastan kur (gecisler yeniden)")
    ap.add_argument("--zincir-yeniden", action="store_true")
    # 6000 ZH+TR karakter: yaklasik 20-25 grup, bir bolum 2-4 parti.
    ap.add_argument("--parti-boyu", type=int, default=6000)
    ap.add_argument("--yanki", default="", metavar="N,N",
                    help="bolum eslesmesine ek olarak sadakat gecisine verilecek Yanki Defteri "
                         "giris numaralari (odemesi 'ileride' olanlar icin; tek bolumde)")
    ap.add_argument("--model")
    ap.add_argument("--cift-sadakat", action="store_true",
                    help="sadakati iki motorla ayri ayri calistir, bulgulari kaynagiyla etiketle "
                         "(LOTM_CIFT_SADAKAT=1 ayni)")
    ap.add_argument("--donem", action="store_true",
                    help="donem uyumu gecisini ekle (varsayilan zaten acik; LOTM_DONEM=0 iken acar)")
    ap.add_argument("--donem-yok", action="store_true",
                    help="donem uyumu gecisini atla (LOTM_DONEM=0 ayni)")
    ap.add_argument("--motor", action="append", default=[], metavar="ADIM=MOTOR",
                    help="gecis basina motor, ornek: --motor sadakat=codex (claude|codex)")
    ap.add_argument("--sure", type=int, default=1800, help="gecis basina zaman asimi (sn)")
    ap.add_argument("--kesin-yok", action="store_true",
                    help="hicbir duzeltmeyi otomatik uygulama, hepsi 5_inceleme.md'ye (LOTM_KESIN_YOK=1); "
                         "eski bolum taramasi icin")
    ap.add_argument("--inceleme-yenile", action="store_true",
                    help="var olan 5_inceleme.md'leri katmanlara dizip Fark satirlari ekle "
                         "(isaretler korunur, once yedek)")
    ap.add_argument("--terim-listesi", action="store_true",
                    help="verilen bolumlerin terim kararlarini Reports/sonra/TERIM_SORULARI.md'de topla")
    ap.add_argument("--paralel", default=os.environ.get("LOTM_PARALEL") or "oto", metavar="N|oto",
                    help="coklu kipte ayni anda N bolum (ayri surecler; LOTM_PARALEL). 'oto' "
                         "(varsayilan): min(bolum sayisi, LOTM_PARALEL_UST=3), hiz sinirina "
                         "takilinca birer dusurur. 1 = sirayla. Betik zinciri once sirayla "
                         "kosar; --kararlar her zaman sirayla.")
    a = ap.parse_args(argv)
    try:
        nolar = bolum_listesi(a.no)
    except ValueError as e:
        ap.error(str(e))
    try:
        a.paralel, a.paralel_oto = paralel_sayisi(a.paralel, len(nolar))
    except ValueError:
        ap.error(f"--paralel {a.paralel}: bir sayi ya da 'oto' olmali")
    if a.yanki and len(nolar) > 1:
        ap.error("--yanki giris numaralari bolume ozgudur; tek bolumle verin")
    motor_secimleri = {}
    for m in a.motor:
        adim, _, mt = m.partition("=")
        if adim not in MODEL_ADIMLARI + ("donem",) or mt not in MOTORLAR:
            ap.error(f"--motor {m}: adim {MODEL_ADIMLARI + ('donem',)}, motor {MOTORLAR}")
        motor_secimleri[adim] = mt

    if a.inceleme_yenile:
        yedek = lotm.yedek_klasoru("inceleme")
        for no in nolar:
            inc = RAPOR / f"Ch_{no}" / "5_inceleme.md"
            if not inc.exists():
                continue
            eski = inc.read_text(encoding="utf-8")
            yeni = inceleme_katmanla(eski)
            once, sonra_ = inceleme_oku(eski), inceleme_oku(yeni)
            if sorted((s["k"], s["kabul"], s["ret"], s["hep"], s["yeni"]) for s in once) != \
                    sorted((s["k"], s["kabul"], s["ret"], s["hep"], s["yeni"]) for s in sonra_):
                print(f"{no:4}  ATLANDI: yeniden dizince isaretler degisiyordu")
                continue
            if yeni != eski:
                (yedek / f"Ch_{no}").mkdir(parents=True, exist_ok=True)
                shutil.copy2(inc, yedek / f"Ch_{no}" / inc.name)
                inc.write_text(yeni, encoding="utf-8")
            sayi = {ad: len(re.findall(r"\n### K", b)) for b in re.split(r"\n(?=## )", yeni)
                    for _, ad, _ in KATMANLAR if b.startswith("## " + ad)}
            print(f"{no:4}  " + ", ".join(f"{ad.split(':')[0]} {n}" for ad, n in sayi.items()))
        return 0
    if a.terim_listesi:
        print(terim_listesi(nolar))
        return 0
    if a.istatistik:
        for no in nolar:
            inceleme = RAPOR / f"Ch_{no}" / "5_inceleme.md"
            if inceleme.exists() and not a.kuru:
                secimler = inceleme_oku(inceleme.read_text(encoding="utf-8"))
                istatistik_kaydet(ISTATISTIK, no, secimler)
                motor_kaydet(MOTOR_IST, no, secimler)
        print(istatistik_ozeti(ISTATISTIK))
        mo = motor_ozeti(MOTOR_IST)
        if mo:
            print("\n" + mo)
        return 0

    otomatik = None if a.otomatik is None else (a.otomatik or list(MODEL_ADIMLARI) + ["donem"])
    if otomatik and not a.kararlar and not shutil.which(claude_komutu(None)[0]):
        print(f"YOK: '{claude_komutu(None)[0]}' komutu. Claude Code kurulu degil ya da PATH'te degil:")
        print("  curl -fsSL https://claude.ai/install.sh | bash   (sonra bir kez 'claude' ile giris)")
        print("  fish: fish_add_path ~/.local/bin")
        print("  ya da LOTM_CLAUDE ile baska bir komut verin. Simdilik yalniz girdiler hazirlaniyor.")
        otomatik = None
    # Sadakat motoru bir kez secilir: codex yoksa uyari her bolumde tekrarlanmasin.
    cift = a.cift_sadakat or CIFT
    if (otomatik or cift) and "sadakat" not in motor_secimleri:
        motor_secimleri["sadakat"] = motor_sec("sadakat")
    ayar = dict(otomatik=otomatik, motor_secimleri=motor_secimleri,
                cift=cift,
                donem=donem_acik(a.donem, a.donem_yok, a.otomatik))

    if len(nolar) == 1:
        k, kisa = bolum_isle(nolar[0], a, **ayar)
        if os.environ.get("LOTM_SONRA_COCUK"):  # paralel kipin alt sureci: ozet ebeveyne
            (RAPOR / f"Ch_{nolar[0]}" / "OZET.txt").write_text(f"{k}\t{kisa}\n", encoding="utf-8")
        return k
    if a.paralel > 1 and not a.kararlar:
        return paralel_kos(nolar, a, argv if argv is not None else sys.argv[1:])

    # Coklu kip: bolumler sirayla; biri dusse de digerleri yurur.
    print(f"Coklu kip: {len(nolar)} bolum ({nolar[0]}…{nolar[-1]})"
          + (f", sadakat motoru: {motor_secimleri['sadakat']}" if "sadakat" in motor_secimleri else "")
          + (" + ikincisi (cift)" if cift else ""))
    ozetler, kod = [], 0
    for no in nolar:
        print(f"\n{'=' * 24} {no}. bolum {'=' * 24}", flush=True)
        try:
            k, ozet = bolum_isle(no, a, **ayar)
        except SystemExit as e:  # sadakat hizalanamadi vb.
            k, ozet = 1, f"HATA: {e}"
            print(ozet)
        except Exception as e:  # noqa: BLE001 -- bir bolum digerlerini durdurmasin
            import traceback
            traceback.print_exc()
            k, ozet = 1, f"HATA: {type(e).__name__}: {e}"
        kod = max(kod, k)
        ozetler.append(f"{no:4}  {ozet}")
    rapor = (f"# Coklu sonra ({time.strftime('%Y-%m-%d %H:%M')})\n\n"
             f"Komut: sonra.py {' '.join(argv if argv is not None else sys.argv[1:])}\n\n"
             + "\n".join(ozetler) + "\n" + kota_notu(KOTA_DOLU))
    RAPOR.mkdir(parents=True, exist_ok=True)
    (RAPOR / "COKLU.md").write_text(rapor, encoding="utf-8")
    print(f"\n{'=' * 60}\n{rapor}-> {RAPOR / 'COKLU.md'}")
    return kod


def donem_acik(donem: bool, donem_yok: bool, otomatik_adimlar, ortam: bool | None = None) -> bool:
    """Donem gecisi bu kosuda kurulsun mu. --donem-yok her seyi ezer; sonra
    --donem, acikca istenen '--otomatik donem', en son LOTM_DONEM (varsayilan acik)."""
    if donem_yok:
        return False
    if donem or "donem" in (otomatik_adimlar or []):
        return True
    return DONEM if ortam is None else ortam


def gunluk_sorunu(gunluk: Path) -> tuple:
    """Alt surecin gunlugu: ({motor: kota metni}, gecici hiz sinirina takildi mi)."""
    try:
        metin = gunluk.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}, False
    kota = dict(re.findall(r"^\s*KOTA (\w+): (.*)$", metin, re.M))
    hiz = any(HIZ_SINIRI.search(s) and not KOTA.search(s)
              for s in metin.splitlines() if "HATA" in s)
    return kota, hiz


def kota_notu(kota: dict) -> str:
    return "".join(f"\nKOTA DOLU — {m}: {s}\n  {m} geçişleri BEKLIYOR kaldı; kota sıfırlanınca aynı komutu "
                   f"yeniden çalıştırın, biten geçişler TAMAM kalır.\n" for m, s in kota.items())


def paralel_kos(nolar: list, a, argv: list) -> int:
    """Coklu kip, ayni anda a.paralel bolum: her bolum kendi sonra.py surecinde.

    Ortak dosyalar yarismasin diye: betik zinciri (toplu_denetle onbellegi,
    duzelt'in son.diff'i) once burada sirayla kosar, alt surecler onu taze
    bulup atlar. Alt surecler yalniz kendi Ch_N/ klasorune yazar; karar
    defteri, istatistik ve words.md'ye yazan --kararlar/--istatistik bu
    yoldan gecmez. Her surecin ciktisi Ch_N/kosu.log'da."""
    # Alt surecin argumanlari: bolum yerine tek numara, zincir zorlamasi ve
    # paralel bayragi atilir (zincir burada kostu).
    temel, atla = [], False
    for x in argv:
        if atla:
            atla = False
            continue
        if x == "--paralel":
            atla = True
            continue
        if x.startswith("--paralel=") or x == "--zincir-yeniden":
            continue
        temel.append(x)
    i = temel.index(a.no)
    temel = temel[:i] + temel[i + 1:]

    print(f"Paralel kip: {len(nolar)} bolum, ayni anda {a.paralel}"
          + (" (oto: hiz sinirinda duser)" if getattr(a, "paralel_oto", False) else "")
          + ". Once betik zincirleri (sirayla):", flush=True)
    calisacak = []
    for no in nolar:
        b = Bolum(no, a.parti_boyu)
        if not b.dosya.exists():
            print(f"  {no}: YOK {b.dosya.name}")
            continue
        if (b.klasor / UYGULANDI).exists() and not a.bastan:
            print(f"  {no}: donuk (kesin duzeltmeler uygulanmis), atlandi")
            continue
        b.klasor.mkdir(parents=True, exist_ok=True)
        b.zincir_calistir(a.zincir_yeniden)
        calisacak.append(no)

    ortam = dict(os.environ, LOTM_SONRA_COCUK="1")
    bekleyen, kosan, sonuc = list(calisacak), {}, {}
    sinir, yeniden, kota = a.paralel, set(), dict(KOTA_DOLU)
    print(f"\nModel gecisleri: {len(calisacak)} bolum, gunlukler Ch_N/kosu.log", flush=True)
    try:
        while bekleyen or kosan:
            while bekleyen and len(kosan) < sinir:
                no = bekleyen.pop(0)
                klasor = RAPOR / f"Ch_{no}"
                (klasor / "OZET.txt").unlink(missing_ok=True)
                gunluk = (klasor / "kosu.log").open("w", encoding="utf-8")
                p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(no)] + temel,
                                     stdout=gunluk, stderr=subprocess.STDOUT, cwd=BETIKLER, env=ortam)
                kosan[no] = (p, gunluk, time.time())
                print(f"  {time.strftime('%H:%M:%S')} basladi {no}", flush=True)
            time.sleep(2)
            for no, (p, gunluk, bas) in list(kosan.items()):
                if p.poll() is None:
                    continue
                gunluk.close()
                del kosan[no]
                oz = RAPOR / f"Ch_{no}" / "OZET.txt"
                kisa = (oz.read_text(encoding="utf-8").strip().split("\t", 1)[-1] if oz.exists()
                        else f"HATA: cikis {p.returncode}, bkz. Ch_{no}/kosu.log")
                yeni_kota, hiz = gunluk_sorunu(RAPOR / f"Ch_{no}" / "kosu.log")
                if yeni_kota.keys() - kota.keys():
                    kota.update(yeni_kota)
                    # Sonra baslayan bolumler o motoru hic denemesin (kalan
                    # gecisleri hemen BEKLIYOR); oteki motor yurur.
                    ortam["LOTM_KOTA_DOLU"] = ",".join(kota)
                    print(f"  {time.strftime('%H:%M:%S')} KOTA DOLU: "
                          + "; ".join(f"{m}: {s}" for m, s in yeni_kota.items()), flush=True)
                if getattr(a, "paralel_oto", False) and no not in yeniden and hiz:
                    sinir = max(1, sinir - 1)
                    yeniden.add(no)
                    bekleyen.append(no)
                    print(f"  {time.strftime('%H:%M:%S')} hiz siniri {no}: ayni anda artik {sinir}, "
                          f"bolum kuyrugun sonunda yeniden denenecek", flush=True)
                    if sinir == 1 and len(kosan) == 0:
                        time.sleep(60)
                    continue
                sonuc[no] = (p.returncode, kisa)
                print(f"  {time.strftime('%H:%M:%S')} bitti   {no} ({(time.time() - bas) / 60:.0f} dk): {kisa}",
                      flush=True)
    except KeyboardInterrupt:
        for p, gunluk, _ in kosan.values():
            p.terminate()
            gunluk.close()
        print("\nDurduruldu; yarim kalan gecisler bir sonraki calistirmada BEKLIYOR gorunur.")
        return 130
    ozetler = [f"{no:4}  {sonuc[no][1]}" for no in calisacak if no in sonuc]
    rapor = (f"# Coklu sonra, paralel {a.paralel}"
             + (f" (oto, sonda {sinir})" if getattr(a, "paralel_oto", False) else "")
             + f" ({time.strftime('%Y-%m-%d %H:%M')})\n\n"
             f"Komut: sonra.py {' '.join(argv)}\n\n" + "\n".join(ozetler) + "\n" + kota_notu(kota))
    (RAPOR / "COKLU.md").write_text(rapor, encoding="utf-8")
    print(f"\n{'=' * 60}\n{rapor}-> {RAPOR / 'COKLU.md'}")
    return max([0] + [k for k, _ in sonuc.values()])


def bolum_isle(no: int, a, otomatik, motor_secimleri: dict, cift: bool, donem: bool) -> tuple:
    """Tek bolumun hatti. (cikis kodu, coklu kip icin tek satir ozet)."""
    b = Bolum(no, a.parti_boyu,
              tuple(int(x) for x in re.findall(r"\d+", a.yanki)))
    if not b.dosya.exists():
        print(f"YOK: {b.dosya}")
        return 1, f"YOK: {b.dosya.name}"
    b.klasor.mkdir(parents=True, exist_ok=True)
    isaret = b.klasor / UYGULANDI

    if a.kararlar:
        sonuc = b.kararlari_isle(a.kuru)
        print(sonuc)
        return 0, sonuc
    # Kesin duzeltmeler uygulandiktan sonra bolum degisir; hat yeniden
    # kurulsa her gecis ESKIMIS gorunur ve bastan calisirdi. Isaret varken
    # hat donuktur: yalniz kararlar kalir.
    if isaret.exists() and not a.bastan:
        print(f"{no}. bolumde kesin duzeltmeler uygulanmis ({isaret.read_text(encoding='utf-8')}).")
        print(f"  kalan kararlar: {b.klasor / '5_inceleme.md'}")
        print(f"  isledikten sonra: ./calistir.sh sonra {no} --kararlar")
        print(f"  hatti bastan kurmak icin: ./calistir.sh sonra {no} --bastan")
        return 0, "donuk: kesin duzeltmeler uygulanmis, kararlar bekliyor (5_inceleme.md)"
    if isaret.exists():
        isaret.unlink()

    b.zincir_calistir(a.zincir_yeniden)

    # Donem bir kez calistiysa birlestirmeye girer; hatta da gorunsun.
    adimlar = list(MODEL_ADIMLARI)
    if donem or (b.klasor / "1b_donem_cikti.md").exists():
        adimlar.insert(1, "donem")
    sonuc, notlar = {}, {}
    for adim in adimlar:
        if adim == "sadakat":
            ciftler, notlar["sadakat"] = b.sadakat()
        elif adim == "birlestir":
            onceki = [c for ad in adimlar[:-1] for _, c in sonuc[ad]]
            if not all(c.exists() for c in onceki):
                sonuc[adim] = []
                notlar[adim] = "onceki gecisler bitince kurulur"
                continue
            ciftler = b.birlestir()
        else:
            ciftler = getattr(b, adim)()
        if adim == "sadakat" and cift:
            ikinci = ikinci_motor(motor_sec("sadakat", motor_secimleri))
            ciftler = ciftler + [(g, c.with_name(f"{c.stem}.{ikinci}.md")) for g, c in ciftler]
        if otomatik and adim in otomatik:
            araclar = TRIYAJ_ARACLARI if adim == "triyaj" else None
            motor = motor_sec(adim, motor_secimleri)
            for girdi, cikti in ciftler:
                if durum(girdi, cikti) != "TAMAM":
                    yurut(girdi, cikti, a.model, a.sure, araclar, cikti_motoru(cikti, motor))
        if adim == "duzeltme":
            notlar[adim] = b.duzeltme_farki()
        if adim == "donem":
            notlar[adim] = "istege bagli; ciktisi birlestirmeye girer"
        # Sira onemli: okuma burada biterse sadakat girdileri ayni turda
        # onun SADAKAT? satirlariyla kurulur.
        sonuc[adim] = ciftler

    son = None
    if sonuc["birlestir"] and durum(*sonuc["birlestir"][0]) == "TAMAM":
        son = b.son_adim(a.kuru, a.kesin_yok or KESIN_YOK)

    # --- rapor
    ozet = b.zincir_ozeti()
    satirlar = [f"# {no}. bölüm — yayın sonrası hattı", "",
                f"Klasör: {b.klasor}", "", "## Betik zinciri",
                f"zincir.txt — {'temiz' if not ozet else f'{len(ozet)} dikkat satırı'}"]
    satirlar += [f"    {s}" for s in ozet]
    satirlar += ["", "## Model geçişleri"]
    sayac = {}
    for adim in adimlar:
        for girdi, cikti in sonuc[adim]:
            mt = cikti.with_name(cikti.name + ".motor")
            ek = f"  ({mt.read_text(encoding='utf-8').strip()})" if mt.exists() else ""
            d = durum(girdi, cikti)
            sayac[d] = sayac.get(d, 0) + 1
            satirlar.append(f"{d:9} {adim:9} {girdi.name}  ->  {cikti.name}{ek}")
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
                     f"Otomatik: ./calistir.sh sonra {no} --otomatik [adım...]"]
    rapor = "\n".join(satirlar) + "\n"
    (b.klasor / "DURUM.md").write_text(rapor, encoding="utf-8")
    print()
    print(rapor)
    kisa = son or ", ".join(f"{v} {k}" for k, v in sorted(sayac.items()))
    return 0, kisa + (f" · zincir: {len(ozet)} dikkat" if ozet else "")


if __name__ == "__main__":
    sys.exit(main())
