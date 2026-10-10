#!/usr/bin/env python3
"""
belge_denetle.py -- ses haritalari ve istemler icin denetim.

Bolum denetleyicileri yalnizca _chapters'a bakar. Oysa taslak ureten model
ses haritalarini okur ve ORNEK satirlari neredeyse kelimesi kelimesine
taklit eder: bir ornekteki eski kelime ya da yanlis yazim, her yeni bolume
yeniden sizar. (Tespit edildigi gibi: Neil ve Azik orneklerindeki
"ritüel", "şans ayini", Side haritasinda donusturulmemis "Ebedi".)

Uc denetim:

  1. ORNEKLERDE ESKI KELIME. sozluk.yml'de gecis bolumu olan terimlerin
     eski karsiliklari (ritüel, mistisizm; bkz. yayim_denetle.gecis_bolumu)
     yalnizca ornek metninde aranir: _"…"_ alintilari ve "- **Örnek"
     satirlari. Kural metni bu kelimeleri bilerek anar; orada aranmaz.
     Uyaridir: ornegin hangi bolume ait oldugu dosyadan bilinemez.

     Eskiden gecisler lint-kurallari.yml'den (kesin_gecis + ogrenme_bolumu)
     okunuyordu. O anahtarlar kaldirilinca bu denetim HATASIZ ve SESSIZCE
     hicbir sey bulmaz olmustu; artik tek kaynak sozluk.yml.

  2. YALNIZCA KLEIN'A AIT ISARETLER. "Tamamdır" Klein.md disindaki bir
     haritanin orneginde geciyorsa hata: yan karakterler bu isareti
     kullanmaz (bkz. Klein.md, onay kademesi).

  3. KURAL / NOT KIMLIKLERI. Klein.md'deki "→ N-K5.1" gibi gerekce
     atiflarinin Klein_Notlar.md'de karsiligi olmali (yoksa hata); notlarda
     kurali silinmis ya da birlesmis N-kimlikleri yetim kalir (uyari).

Yazim (sapka) bu betikte degildir: calistir.sh ayni belgelere sapka.py'yi
kuru calistirir.

Kullanim:
    python3 belge_denetle.py                    varsayilan klasorler
    python3 belge_denetle.py dosya.md ...       belirli dosyalar
    python3 belge_denetle.py --notlar Klein_Notlar.md --klein Klein.md

Cikis kodu: hata varsa 1.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import lotm
from turkce import tr_desen

KLEIN_OZEL = ["tamamdır"]          # yalnizca Klein'in agzinda
# Ingilizceden turetilmis, Cinceyle henuz karsilastirilmamis ornekler bu
# isareti tasir. Hata degil; bolumune gelindiginde kaynakla denetlenecek
# ornekleri sayar ki liste unutulmasin.
DENETLENMEDI = "ZH denetlenmedi"
_ORNEK_SATIR = re.compile(r"^\s*[-*]\s*\*\*Örnek")
_ALINTI = re.compile(r'_"(.+?)"_')
# Kimlikler bir bolum harfi tasir: K (Kurallar), M (Muhatap Ekseni),
# A (Asamalar), T (tikler). Harf, ayni numaranin iki bolumde cakismasini onler.
_KIMLIK = r"[KMAT]\d+(?:\.\d+)*"
_K_BASLIK = re.compile(r"^#{2,6}\s+(" + _KIMLIK + r")\b", re.M)
_N_ATIF = re.compile(r"→\s*N-(" + _KIMLIK + r")")
_N_KIMLIK = re.compile(r"\bN-(" + _KIMLIK + r")")


def gecis_kurallari(sozluk) -> list:
    """[(kavram, gecis_bolumu, dogru, [eski desenler])] -- sozluk.yml'den."""
    from yayim_denetle import gecis_bolumu

    out = []
    for t in sozluk.terimler:
        bolum = gecis_bolumu(t)
        if not (t.tr and t.eski_karsiliklar and bolum):
            continue
        out.append((
            t.en or t.tr, bolum, t.tr,
            # yayim_denetle'nin eski_desen'i ile ayni desen: iki betik ayni
            # bicimleri bulsun. Harf duyarli, cunku eski karsiliklarin cogu
            # gunluk kelime (Şanslı, Fitne, Ölüm...).
            [lotm.desen_kur(e) for e in t.eski_karsiliklar],
        ))
    return out


def ornek_parcalari(metin: str):
    """(satir_no, ornek_metni) -- alintilar ve Örnek satirlari."""
    for no, satir in enumerate(metin.split("\n"), 1):
        if _ORNEK_SATIR.match(satir):
            yield no, satir
            continue
        for m in _ALINTI.finditer(satir):
            yield no, m.group(1)


def ornek_denetle(ad: str, metin: str, kurallar: list, klein_mi: bool) -> list:
    """[(agirlik, satir, mesaj)]"""
    bulgu = []
    ozel = [] if klein_mi else [(w, re.compile(r"(?<![^\W_])" + tr_desen(w))) for w in KLEIN_OZEL]
    for no, parca in ornek_parcalari(metin):
        for kavram, bolum, dogru, eskiler in kurallar:
            for d in eskiler:
                for m in d.finditer(parca):
                    bulgu.append(("uyari", no,
                                  f"örnekte “{m.group()}” [{kavram}]: sahne {bolum}. bölümden "
                                  f"sonraysa “{dogru}” olmalı"))
        for kelime, d in ozel:
            for m in d.finditer(parca):
                bulgu.append(("hata", no, f"örnekte “{m.group()}”: yalnızca Klein kullanır "
                                          f"(bkz. Klein.md, onay kademesi)"))
    return bulgu


def kimlik_denetle(klein: str, notlar: str) -> list:
    """[(agirlik, dosya, mesaj)] -- atif / yetim not."""
    kurallar = set(_K_BASLIK.findall(klein))
    atiflar = set(_N_ATIF.findall(klein))
    notlar_ = set(_N_KIMLIK.findall(notlar))
    bulgu = []
    for k in sorted(atiflar - notlar_):
        bulgu.append(("hata", "Klein.md", f"“→ N-{k}” atfı var ama notlarda N-{k} yok"))
    for k in sorted(notlar_):
        # N-K5 (genel) bolum notudur; kural basligi K5 olmasa da K5.x varsa gecerli
        if k not in kurallar and not any(x == k or x.startswith(k + ".") for x in kurallar):
            bulgu.append(("uyari", "Klein_Notlar.md", f"N-{k} yetim: Klein.md'de {k} kuralı yok"))
    return bulgu


def varsayilan_dosyalar() -> list:
    kok = lotm.KOK / "Tools"
    out = []
    for klasor in ("Voice_Maps", "Prompts"):
        out += sorted((kok / klasor).glob("*.md"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dosyalar", nargs="*", type=Path)
    ap.add_argument("--sozluk", type=Path, default=None, help="varsayilan: lotm.SOZLUK_YOLU")
    ap.add_argument("--klein", type=Path, default=None, help="varsayilan: Voice_Maps/Klein.md")
    ap.add_argument("--notlar", type=Path, default=None, help="varsayilan: Voice_Maps/Klein_Notlar.md")
    a = ap.parse_args()

    dosyalar = a.dosyalar or varsayilan_dosyalar()
    if not dosyalar:
        print("  belge bulunamadı", file=sys.stderr)
        return 0
    yol = a.sozluk or lotm.SOZLUK_YOLU
    if yol.exists():
        kurallar = gecis_kurallari(lotm.sozluk_yukle(yol))
    else:
        # Sessiz kalmasin: 1. denetim bu yuzden bir kez hic calismadan gecti.
        print(f"  !! sözlük yok ({yol}); örneklerde eski kelime denetlenmedi", file=sys.stderr)
        kurallar = []
    hata = uyari = 0
    for yol in dosyalar:
        if yol.name == "Klein_Notlar.md":
            continue            # gerekce metni: model okumaz, ornek taklidi yok
        metin = yol.read_text(encoding="utf-8")
        bekleyen = [no for no, s in enumerate(metin.split("\n"), 1) if DENETLENMEDI in s]
        if bekleyen:
            print(f"  ·  {yol.name}: {len(bekleyen)} örnek Çinceyle denetlenmedi "
                  f"(satır {', '.join(map(str, bekleyen[:8]))}{'…' if len(bekleyen) > 8 else ''})")
        for agirlik, no, mesaj in ornek_denetle(yol.name, metin, kurallar, yol.name.startswith("Klein")):
            print(f"  {'!!' if agirlik == 'hata' else ' *'} {yol.name}:{no}  {mesaj}")
            hata += agirlik == "hata"
            uyari += agirlik == "uyari"

    klein = a.klein or lotm.KOK / "Tools" / "Voice_Maps" / "Klein.md"
    notlar = a.notlar or klein.with_name("Klein_Notlar.md")
    if klein.exists() and notlar.exists():
        for agirlik, ad, mesaj in kimlik_denetle(klein.read_text(encoding="utf-8"),
                                                 notlar.read_text(encoding="utf-8")):
            print(f"  {'!!' if agirlik == 'hata' else ' *'} {ad}  {mesaj}")
            hata += agirlik == "hata"
            uyari += agirlik == "uyari"
    print(f"  belgeler: {hata} hata, {uyari} uyarı ({len(dosyalar)} dosya)")
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
