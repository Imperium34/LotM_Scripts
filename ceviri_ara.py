#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ceviri_ara.py -- bir terimin bolumler boyunca NASIL cevrildigini gosterir.

sozluk.yml "ne karar verdim" sorusunu yanitlar. Bu betik "ne yayimladim"
sorusunu yanitlar. Ikisi ayni olmak zorunda degil; aradaki fark zaten
aranan seydir.

NASIL CALISIR
-------------
Terim kaynak metinde (EN/ZH) aranir. Bulunan her paragraf, bolum.hizala ile
hedef metne (TR) hizalanir ve karsi paragraf cikarilir. Yani karsilik
sozlukten degil, YAYIMLANMIS METINDEN okunur.

Karsiligin hangi kelime oldugunu bulmak icin iki yol var:

  1. SOZLUKTEN. Terim sozlukte varsa karsiligi ve eski_karsiliklar
     adaylardir. Hangisi gectigine bakilir.
  2. KESFEDEREK. Sozlukte yoksa, terimin gectigi paragraflarda gecip
     GECMEDIGI paragraflarda gecmeyen govdeler aranir (tf-idf benzeri).
     Kesin degildir, aday uretir.

Ikisinde de asil ciktisi olan sey EŞLEŞMEYENLER'dir: terimin gectigi ama
hicbir adayin bulunmadigi paragraflar. Ya yeni bir karsilik kullanilmis,
ya terim atlanmis, ya da hizalama kaymis. Ucu de bakmaya deger.

Kullanim:
    ceviri_ara.py "Beyonder"                  EN -> TR, ozet
    ceviri_ara.py "Beyonder" --tam            her gecisi tek tek
    ceviri_ara.py "Sıradışı" --hedef en       ters yon: arkasinda ne vardi?
    ceviri_ara.py 序列 --hedef tr             Cinceden
    ceviri_ara.py "Beyonder" --bolum 1-200
    ceviri_ara.py "Beyonder" --aday Sıradışı --aday Olağanüstü
"""

import argparse
import math
import re
import sys
from collections import Counter, defaultdict

import lotm
import bolum as B

# Turkce cekim eki deseni. Migrasyondan once denetci2.py'deydi ve buradan
# oraya import ediliyordu; artik dogru yerde.
desen_kur = lotm.desen_kur


_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
_KELIME = re.compile(r"[^\W\d_]+", re.UNICODE)

# Kesif taramasinda govde uzunlugu. Turkce ekleri kirpmak icin: "Sıradışı",
# "Sıradışılar", "Sıradışının" hepsi "sıradı" olur. Kaba ama ek listesi
# bakmaktan ucuz ve bilinmeyen kelimelerde de calisir.
KOK_UZUNLUK = 6

# Bu govdeler hedef paragraflarin %25'inden fazlasinda geciyorsa aday
# sayilmaz -- ayirt edici degiller.
GURULTU_ESIGI = 0.25


# --------------------------------------------------------------- yardimci


def _kok(kelime: str) -> str:
    return kelime.casefold()[:KOK_UZUNLUK]


def _koku_olanlar(metin: str) -> set:
    return {_kok(k) for k in _KELIME.findall(metin)}


def dili_kestir(sorgu: str) -> str:
    """Sorgudan kaynak dili tahmin eder."""
    if _CJK.search(sorgu):
        return "zh"
    if re.search(r"[ğışĞİŞçöüÇÖÜâî]", sorgu):
        return "tr"
    return "en"


def desen_kur_kaynak(sorgu: str, kaynak: str, harf_duyarsiz: bool):
    """
    Her dil icin farkli eslesme:
      zh  duz altdize (kelime siniri yok)
      tr  Turkce cekim ekleri (denetci2.desen_kur)
      en  kelime siniri; sorgu buyuk harf iceriyorsa harf duyarli
    """
    if kaynak == "zh":
        return re.compile(re.escape(sorgu))
    if kaynak == "tr":
        return desen_kur(sorgu, harf_duyarli=not harf_duyarsiz)
    bayrak = re.IGNORECASE if (harf_duyarsiz or sorgu.islower()) else 0
    return re.compile(r"(?<!\w)" + re.escape(sorgu) + r"(?!\w)", bayrak)


def bolum_araligi(ifade):
    """'1-200' -> (1, 200);  '279' -> (279, 279);  None -> None"""
    if not ifade:
        return None
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", ifade)
    if not m:
        sys.exit(f"bolum araligi anlasilmadi: {ifade!r}  (ornek: 1-200)")
    bas = int(m.group(1))
    return (bas, int(m.group(2)) if m.group(2) else bas)


# --------------------------------------------------------------- adaylar


def sozlukten_adaylar(sorgu: str, hedef: str) -> list:
    """
    Sorguyla eslesen sozluk kayitlarindan hedef dildeki karsiliklari toplar.
    eski_karsiliklar da dahil -- asil merak edilen zaten onlarin metinde
    kalip kalmadigi.
    """
    try:
        sozluk = lotm.sozluk_yukle()
    except (FileNotFoundError, OSError) as e:
        print(f"uyari: sozluk okunamadi ({e}); kesif moduna geciliyor",
              file=sys.stderr)
        return []

    q = sorgu.casefold()
    adaylar = []
    for t in sozluk.terimler:
        alanlar = [(t.tr or "").casefold(), (t.en or "").casefold(), t.zh or ""]
        if not any(q == a or (len(q) > 3 and q in a) for a in alanlar if a):
            continue
        if hedef == "tr":
            adaylar.append(t.tr)
            adaylar += list(t.eski_karsiliklar)
        elif hedef == "en" and t.en:
            adaylar.append(t.en)
        elif hedef == "zh" and t.zh:
            adaylar.append(t.zh)

    gorulen, temiz = set(), []
    for a in adaylar:
        a = (a or "").strip()
        if a and a.casefold() not in gorulen:
            gorulen.add(a.casefold())
            temiz.append(a)
    return temiz


def adaylari_kesfet(vurus_paragraflari, arka_plan, ust=8) -> list:
    """
    Terimin gectigi paragraflarda gecip digerlerinde gecmeyen govdeler.

    Skor = (vurus orani) * log(toplam / arka plan orani). Yani hem sik hem
    ayirt edici olan kazanir. 'bir', 'bu', 've' her yerde gectigi icin
    ikinci carpan onlari sifira yaklastirir.
    """
    if not vurus_paragraflari:
        return []

    vurus_df = Counter()
    for p in vurus_paragraflari:
        vurus_df.update(_koku_olanlar(p))

    arka_df = Counter()
    for p in arka_plan:
        arka_df.update(_koku_olanlar(p))

    n_vurus, n_arka = len(vurus_paragraflari), max(1, len(arka_plan))
    puanlar = []
    for kok, df in vurus_df.items():
        if len(kok) < 3:
            continue
        if arka_df[kok] / n_arka > GURULTU_ESIGI:
            continue
        oran = df / n_vurus
        if oran < 0.15:                      # dagilmis gurultu
            continue
        puanlar.append((oran * math.log(n_arka / (arka_df[kok] + 1) + 1), kok))

    puanlar.sort(reverse=True)
    return [kok for _, kok in puanlar[:ust]]


# --------------------------------------------------------------- tarama


def _hedef_metin(kume_b, indisler) -> str:
    return "\n".join(kume_b[x] for x in indisler)


def tara(sorgu, kaynak, hedef, aralik, harf_duyarsiz):
    """
    Doner: (vuruslar, arka_plan)
      vuruslar   -> [{bolum, kaynak_metin, hedef_metin, tip}]
      arka_plan  -> ayni bolumlerin terimin GECMEDIGI hedef paragraflari

    Arka plana vurus paragraflari DAHIL EDILMEZ. Edilirse kesif bozulur:
    aranan karsilik hem sayacta hem paydada gorunur, "her yerde geciyor"
    diye elenir ve tam da bulunmasi gereken kelime gurultu sayilir.
    """
    desen = desen_kur_kaynak(sorgu, kaynak, harf_duyarsiz)

    yukle = {"zh": lotm.bolumler_zh, "en": lotm.bolumler_en,
             "tr": lotm.bolumler_tr}

    def oku(ad):
        try:
            return lotm.bolum_sozlugu(yukle[ad]())
        except (FileNotFoundError, OSError) as e:
            sys.exit(f"{ad.upper()} kaynagi okunamadi: {e}\n"
                     f"LOTM_KOK dogru mu? (su an: {lotm.KOK})")

    k_bolumler, h_bolumler = oku(kaynak), oku(hedef)

    ortak = sorted(set(k_bolumler) & set(h_bolumler))
    if aralik:
        ortak = [n for n in ortak if aralik[0] <= n <= aralik[1]]
    if not ortak:
        sys.exit("kaynak ve hedefte ortak bolum yok "
                 "(TR yayimlanmis bolumler mi eksik?)")

    print(f"{len(ortak)} ortak bolum taraniyor "
          f"({ortak[0]}-{ortak[-1]})...", file=sys.stderr)

    k_baslik = B.KAYNAKLAR[kaynak][2]
    h_baslik = B.KAYNAKLAR[hedef][2]

    vuruslar, arka_plan = [], []
    for no in ortak:
        k_ham = k_bolumler[no].metin
        if not desen.search(k_ham):
            continue

        k_par = B.paragraflar(k_ham, k_baslik)
        h_par = B.paragraflar(h_bolumler[no].metin, h_baslik)

        gruplar = B.hizala(k_par, h_par)
        nereye = {}
        for ia, ib in gruplar:
            for i in ia:
                nereye[i] = ib

        tuketilen = set()
        for i, p in enumerate(k_par):
            if not desen.search(p):
                continue
            ib = nereye.get(i, [])
            tuketilen.update(ib)
            vuruslar.append({
                "bolum": no,
                "kaynak_metin": p,
                "hedef_metin": _hedef_metin(h_par, ib) if ib else "",
                "tip": "eslesti" if ib else "tek_tarafli",
            })

        arka_plan.extend(p for j, p in enumerate(h_par) if j not in tuketilen)

    return vuruslar, arka_plan


def siniflandir(vuruslar, adaylar, hedef):
    """Her vurusa, hedef paragrafinda gecen adaylari etiketler."""
    if hedef == "tr":
        desenler = [(a, desen_kur(a, harf_duyarli=False)) for a in adaylar]
    elif hedef == "zh":
        desenler = [(a, re.compile(re.escape(a))) for a in adaylar]
    else:
        desenler = [(a, re.compile(r"(?<!\w)" + re.escape(a) + r"(?!\w)",
                                   re.IGNORECASE)) for a in adaylar]

    for v in vuruslar:
        v["bulunan"] = [ad for ad, d in desenler if d.search(v["hedef_metin"])]
    return vuruslar


# --------------------------------------------------------------- cikti


def _yaz_paragraf(etiket, metin, genislik, desen=None):
    girinti = " " * (len(etiket) + 2)
    govde = genislik - len(girinti)
    if desen:
        metin = desen.sub(lambda m: f"«{m.group(0)}»", metin)
    kolon = B._kolon_fabrikasi(metin)
    for j, s in enumerate(B._sar(metin, govde, kolon)):
        print((f"{etiket}  " if j == 0 else girinti) + s)


def ozet_yaz(vuruslar, adaylar, kesif, sorgu, kaynak, hedef):
    print(f"\n'{sorgu}'  [{kaynak.upper()} -> {hedef.upper()}]")
    print(f"{len(vuruslar)} gecis, "
          f"{len({v['bolum'] for v in vuruslar})} bolumde\n")

    if not vuruslar:
        return

    if kesif:
        print("Adaylar sozlukten degil, metinden KESFEDILDI (govde eslesmesi):")
        print(f"  {', '.join(adaylar) if adaylar else '(hicbiri)'}\n")

    sayim = defaultdict(list)
    eslesmeyen = []
    tek_tarafli = []
    for v in vuruslar:
        if v["tip"] == "tek_tarafli":
            tek_tarafli.append(v)
        elif v["bulunan"]:
            for ad in v["bulunan"]:
                sayim[ad].append(v["bolum"])
        else:
            eslesmeyen.append(v)

    print("=== KULLANILAN KARSILIKLAR ===")
    if not sayim:
        print("  hicbir aday hedef metinde bulunamadi")
    for ad, bolumler in sorted(sayim.items(), key=lambda kv: -len(kv[1])):
        b = sorted(set(bolumler))
        yer = f"bolum {b}" if len(b) <= 12 else f"{len(b)} bolum, ilk {b[:6]}..."
        print(f"  {ad}: {len(bolumler)} gecis, {yer}")

    if len(sayim) > 1:
        print("\n  ^ birden fazla karsilik var. Kasitli mi?")

    print(f"\n=== ESLESMEYEN ({len(eslesmeyen)}) ===")
    print("    Terim kaynakta var, bilinen hicbir karsilik hedefte yok.")
    print("    Yeni bir karsilik, atlanmis bir cumle, ya da kaymis hizalama.")
    if not eslesmeyen:
        print("  yok")
    for v in eslesmeyen[:15]:
        ozet = re.sub(r"\s+", " ", v["hedef_metin"])[:110]
        print(f"  [bolum {v['bolum']}] {ozet}")
    if len(eslesmeyen) > 15:
        print(f"  ... {len(eslesmeyen) - 15} tane daha (--tam ile hepsi)")

    if tek_tarafli:
        print(f"\n=== HIZALANAMAYAN ({len(tek_tarafli)}) ===")
        print("    Kaynak paragrafin hedefte karsiligi yok. Cogunlukla")
        print("    birlestirilmis paragraf; bazen atlanmis metin.")
        b = sorted({v["bolum"] for v in tek_tarafli})
        print(f"  bolum {b if len(b) <= 20 else b[:20]}")


def tam_yaz(vuruslar, sorgu, kaynak, hedef, genislik, harf_duyarsiz):
    desen = desen_kur_kaynak(sorgu, kaynak, harf_duyarsiz)
    k_ad, h_ad = kaynak.upper(), hedef.upper()

    for v in vuruslar:
        etiketler = ", ".join(v.get("bulunan") or [])
        durum = f"  -> {etiketler}" if etiketler else "  -> ESLESMEYEN"
        if v["tip"] == "tek_tarafli":
            durum = "  -> HIZALANAMADI"
        bas = f"──── bolum {v['bolum']}{durum} "
        print(bas + "─" * max(4, genislik - len(bas)))

        _yaz_paragraf(k_ad, v["kaynak_metin"], genislik, desen)
        print()
        if v["hedef_metin"]:
            _yaz_paragraf(h_ad, v["hedef_metin"], genislik)
            print()


def main():
    ap = argparse.ArgumentParser(
        description="Bir terimin bolumler boyunca nasil cevrildigini gosterir.")
    ap.add_argument("sorgu")
    ap.add_argument("--kaynak", choices=("zh", "en", "tr"), default=None,
                    help="varsayilan: sorgudan kestirilir")
    ap.add_argument("--hedef", choices=("zh", "en", "tr"), default=None,
                    help="varsayilan: tr (kaynak tr ise en)")
    ap.add_argument("--aday", action="append", default=[],
                    help="karsilik adayi; tekrarlanabilir")
    ap.add_argument("--bolum", default=None, help="'1-200' ya da '279'")
    ap.add_argument("--tam", action="store_true",
                    help="her gecisi paragraf paragraf yaz")
    ap.add_argument("--harf-duyarsiz", action="store_true", dest="duyarsiz")
    ap.add_argument("--genislik", type=int, default=None)
    a = ap.parse_args()

    import shutil
    genislik = a.genislik or shutil.get_terminal_size((100, 40)).columns

    kaynak = a.kaynak or dili_kestir(a.sorgu)
    hedef = a.hedef or ("en" if kaynak == "tr" else "tr")
    if kaynak == hedef:
        sys.exit("kaynak ve hedef ayni olamaz")
    if not a.kaynak:
        print(f"kaynak dil '{kaynak}' varsayildi (--kaynak ile degistirin)",
              file=sys.stderr)

    vuruslar, arka_plan = tara(a.sorgu, kaynak, hedef,
                               bolum_araligi(a.bolum), a.duyarsiz)

    adaylar, kesif = a.aday, False
    if not adaylar:
        adaylar = sozlukten_adaylar(a.sorgu, hedef)
    if not adaylar:
        kesif = True
        adaylar = adaylari_kesfet([v["hedef_metin"] for v in vuruslar
                                   if v["hedef_metin"]], arka_plan)

    siniflandir(vuruslar, adaylar, hedef)

    if a.tam:
        tam_yaz(vuruslar, a.sorgu, kaynak, hedef, genislik, a.duyarsiz)
    ozet_yaz(vuruslar, adaylar, kesif, a.sorgu, kaynak, hedef)


if __name__ == "__main__":
    main()
