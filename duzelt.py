#!/usr/bin/env python3
"""
duzelt.py -- denetleyicilerin KESIN duzeltmelerini tek yerden uygular.

Denetleyiciler (sapka, lint, bicim, takvim, ciltler) bulgularini raporlar;
bir kismi tek dogru sonucu olan duzeltmelerdir. Bu betik onlari toplar,
once FARK gosterir, istenirse yedekleyip yazar. Yargi isteyen her bulgu
(esadli sapka, cogunluk TAHMINI ek, eki degisen varyant, anakronizm ...)
rapor kalir ve ozetin sonunda nereden okunacagi yazilir.

ADIMLAR (sirayla; her biri bir oncekinin sonucunu gorur)
------
  sapka     lint/sapka.py GÜVENLİ gruplari, yonu sozluk belirler
            (bolumler)
  lint      lint/sozluk_lint.py: 'duzelt'i acik varyant kurallari,
            yasakli bicimler, dogru_ekler'i tanimli ad ekleri (bolumler)
  bicim     bicim_denetle.py GÜVENLİ dizgi duzeltmeleri, tabandakiler
            haric (bolumler)
  belgeler  sapka GÜVENLİ, ses haritalari ve istemler; iki yazimi birden
            tasiyan ornek satirlarina dokunulmaz
  takvim    takvim_ata.py: YAYIMLANMAMIS bolumlerin tarihleri
  ciltler   _data/ciltler.yml, lotm.CILTLER'den

GUVENLIK
--------
  - Varsayilan KURU: hicbir dosya degismez, yalniz fark gosterilir.
  - Butun adimlar dosyalarin GECICI kopyasinda calisir; gercek dosyalara
    yalniz --uygula ile, en sonda ve hepsi birden yazilir.
  - --uygula once ayni farki gosterir ve sorar (--evet: sormadan).
  - Yazmadan once her ozgun dosya LotM/yedek/<tarih>/duzelt-<saat>/
    altina kopyalanir (KOK'a gore ayni yol). Geri almak:
        ./calistir.sh duzelt --geri-al yedek/<tarih>/duzelt-<saat>
  - Okunduktan sonra degismis bir dosyaya yazilmaz (o arada editorde
    kaydedildiyse).
  - Tam fark her calistirmada Reports/duzelt/son.diff'e yazilir.
  - Dipnot eklenmez, words.md'ye ve dondurulmus satirlara dokunulmaz.

Kullanim:
    python3 duzelt.py                    hepsi, KURU
    python3 duzelt.py lint sapka         yalniz bu adimlar
    python3 duzelt.py --bolum 68         yalniz 68 (bolum adimlari icin)
    python3 duzelt.py --bolum 60-68
    python3 duzelt.py --uygula           fark + soru + yedek + yaz
    python3 duzelt.py --uygula --evet    sormadan (zamanlayici icin)
    python3 duzelt.py --geri-al yedek/2026-10-31/duzelt-143005

Cikis kodu: 0 degisiklik yok ya da yazildi; 3 kuru calismada bekleyen
degisiklik var; 1 hata (yazilmadi).
"""

from __future__ import annotations

import argparse
import difflib
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

BETIK = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIK))
sys.path.insert(0, str(BETIK / "lint"))

import lotm  # noqa: E402

ADIMLAR = ["sapka", "lint", "bicim", "belgeler", "takvim", "ciltler"]
BOLUM_ADIMLARI = {"sapka", "lint", "bicim"}

KOK = lotm.KOK
SITE = lotm.SITE
BOLUMLER = lotm.BOLUMLER_TR
SOZLUK = lotm.SOZLUK_YOLU
KELIMELER = lotm.KELIMELER
BELGE_KLASORLERI = [KOK / "Tools/Voice_Maps", KOK / "Tools/Prompts"]
BICIM_TABAN = Path(os.environ.get("LOTM_BICIM_TABAN") or BETIK / "lint/bicim-taban.tsv")
KURALLAR = BETIK / "lint/lint-kurallari.yml"
SAPKA_TABAN = Path(os.environ.get("LOTM_SAPKA_TABAN") or BETIK / "lint/sapka-taban.tsv")
RAPOR = BETIK / "Reports/duzelt"

RENK = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _r(kod, s):
    return f"\033[{kod}m{s}\033[0m" if RENK else s


# ------------------------------------------------------------ calisma kopyasi


class Calisma:
    """
    Gercek dosyalarin gecici kopyasi. Adimlar kopyayi okur ve kopyaya
    yazar; gercek dosyalar 'yaz' cagrilana kadar degismez.
    """

    def __init__(self):
        self.kok = Path(tempfile.mkdtemp(prefix="lotm-duzelt-"))
        self.ozgun: dict[Path, bytes] = {}  # gercek yol -> okunan icerik
        self.mtime: dict[Path, float] = {}
        self.adim_sayilari: dict[str, dict[Path, int]] = {}
        self.notlar: list[str] = []

    def kopya(self, gercek: Path) -> Path:
        gercek = Path(gercek).resolve()
        try:
            goreli = gercek.relative_to(KOK.resolve())
        except ValueError:
            goreli = Path("_dis") / gercek.name
        k = self.kok / goreli
        if gercek not in self.ozgun:
            veri = gercek.read_bytes()
            self.ozgun[gercek] = veri
            self.mtime[gercek] = gercek.stat().st_mtime
            k.parent.mkdir(parents=True, exist_ok=True)
            k.write_bytes(veri)
        return k

    def gercek(self, kopya: Path) -> Path:
        goreli = Path(kopya).relative_to(self.kok)
        for g in self.ozgun:
            try:
                if g.relative_to(KOK.resolve()) == goreli:
                    return g
            except ValueError:
                if Path("_dis") / g.name == goreli:
                    return g
        raise KeyError(kopya)

    def kaydet(self, adim: str, kopya: Path, yeni, sayi: int):
        veri = yeni.encode("utf-8") if isinstance(yeni, str) else yeni
        if Path(kopya).read_bytes() == veri:
            return
        Path(kopya).write_bytes(veri)
        self.adim_sayilari.setdefault(adim, {})[self.gercek(kopya)] = sayi

    def degisenler(self) -> list[Path]:
        out = []
        for g, veri in self.ozgun.items():
            if self.kopyasi(g).read_bytes() != veri:
                out.append(g)
        return sorted(out)

    def kopyasi(self, g: Path) -> Path:
        try:
            return self.kok / g.relative_to(KOK.resolve())
        except ValueError:
            return self.kok / "_dis" / g.name

    def temizle(self):
        shutil.rmtree(self.kok, ignore_errors=True)


# ------------------------------------------------------------ adimlar


def _bolum_yollari(aralik: tuple | None) -> list[Path]:
    out = []
    for p in sorted(Path(BOLUMLER).glob("*.md")):
        try:
            no = int("".join(c for c in p.stem if c.isdigit()) or "x")
        except ValueError:
            continue
        if aralik is None or aralik[0] <= no <= aralik[1]:
            out.append(p)
    return out


def adim_sapka(c: Calisma, yollar, belge=False):
    import sapka

    kel = KELIMELER if Path(KELIMELER).exists() else None
    liste = sapka.uygulanacak_liste(SOZLUK if SOZLUK.exists() else None, kel)
    kopyalar = [c.kopya(y) for y in yollar]
    metinler = {k: k.read_text(encoding="utf-8") for k in kopyalar}
    adim = "belgeler" if belge else "sapka"
    for k, (yeni, n) in sapka.plan(metinler, liste, belge=belge).items():
        c.kaydet(adim, k, yeni, n)
    # Elle kalanlar: ayni gruplarin sayimi (yazilmaz).
    elle = sapka.tara({k.name: metinler[k] for k in kopyalar}, sapka.elle_listesi())
    elle, _bastirilan = sapka.tabandan_suz(elle, sapka.taban_oku(SAPKA_TABAN))
    n = sum(len(v) for v in elle.values())
    if n:
        komut = "./calistir.sh belgeler" if belge else "./calistir.sh sapka"
        c.notlar.append(f"{adim}: {n} YENİ geçiş kayıt / nisbet / eşadlı grubunda (tabanda "
                        f"olmayan); okuyarak karar verilir -> {komut}")


def adim_lint(c: Calisma, yollar):
    import yaml
    import sozluk_lint as SL

    kurallar = yaml.safe_load(KURALLAR.read_text(encoding="utf-8")) or {}
    for y in yollar:
        k = c.kopya(y)
        ham = k.read_text(encoding="utf-8")
        yeni, onergeler = SL.duzeltme_plani(ham, kurallar)
        if onergeler:
            c.kaydet("lint", k, yeni, len(onergeler))
    # Kalan lint hatalari, duzeltilmis kopyada.
    try:
        govde, baslik = SL.bolumleri_yukle([c.kopya(y) for y in yollar])
        r = SL.Rapor()
        metin = {**govde, **baslik}
        SL.denetle_varyant(r, metin, kurallar)
        SL.denetle_yasakli(r, metin, kurallar)
        SL.denetle_ek_uyumu(r, metin, kurallar)
        hata = sum(1 for b in r.bulgular if b.agirlik == "hata")
        uyari = sum(1 for b in r.bulgular if b.agirlik != "hata")
        if hata or uyari:
            c.notlar.append(
                f"lint: duzeltmeden sonra {hata} hata, {uyari} uyarı kalıyor "
                f"(eki değişen varyant, çoğunluk tahmini ek...) -> ./calistir.sh lint")
    except Exception as e:  # sayim bilgi icin; duzeltmeyi durdurmasin
        c.notlar.append(f"lint: kalan bulgular sayılamadı ({e})")


def adim_bicim(c: Calisma, yollar):
    import bicim_denetle as BD

    taban = BD.taban_oku(str(BICIM_TABAN)) if BICIM_TABAN.exists() else None
    kod_adlari = BD.kod_adi_deseni(str(SOZLUK)) if SOZLUK.exists() else None
    kopyalar = [c.kopya(y) for y in yollar]
    elle = 0
    for k, (yeni, n, e) in BD.plan(kopyalar, kod_adlari, taban, None).items():
        c.kaydet("bicim", k, yeni, n)
        elle += e
    if elle:
        c.notlar.append(f"bicim: {elle} bulgu elle (cümle kurulumu, italik içi atıf...) "
                        f"-> python3 bicim_denetle.py --duzelt")


def adim_belgeler(c: Calisma, _yollar):
    belgeler = [p for d in BELGE_KLASORLERI if d.is_dir() for p in sorted(d.glob("*.md"))]
    if belgeler:
        adim_sapka(c, belgeler, belge=True)


def adim_takvim(c: Calisma, _yollar):
    import takvim_ata as TA
    import takvim_denetle as TD

    # Butun bolum klasoru kopyalanir: tarih zinciri hepsine bakar.
    for y in sorted(Path(BOLUMLER).glob("*.md")):
        c.kopya(y)
    klasor = c.kopyasi(Path(BOLUMLER).resolve())
    takvim = TD.takvim_oku(TD.varsayilan_takvim_yolu(Path(BOLUMLER)))
    simdi = datetime.now(takvim.donemler[0].saat.tzinfo)
    ks = TD.kunyeler(klasor)
    if any(k.tarih_ham and not k.tarih for k in ks):
        c.notlar.append("takvim: tarihi okunamayan bölüm var; atlandı -> ./calistir.sh takvim")
        return
    TD._dilim_esitle(ks, takvim)
    try:
        degisiklikler, notlar = TA.plan_kur(ks, takvim, simdi)
    except TD.TakvimHatasi as e:
        c.notlar.append(f"takvim: {e}; atlandı")
        return
    c.notlar += [f"takvim: {n}" for n in notlar]
    for k, _eski, yeni in degisiklikler:
        yol = klasor / k.dosya
        c.kaydet("takvim", yol, TA.yeni_icerik(yol, yeni), 1)


def adim_ciltler(c: Calisma, _yollar):
    import ciltler_yaz

    hedef = Path(ciltler_yaz.HEDEF)
    if not hedef.exists():
        return
    k = c.kopya(hedef)
    c.kaydet("ciltler", k, ciltler_yaz.metin(), 1)


CALISTIR = {
    "sapka": adim_sapka,
    "lint": adim_lint,
    "bicim": adim_bicim,
    "belgeler": adim_belgeler,
    "takvim": adim_takvim,
    "ciltler": adim_ciltler,
}


# ------------------------------------------------------------ fark


def _goreli(g: Path) -> str:
    try:
        return str(g.relative_to(KOK.resolve()))
    except ValueError:
        return str(g)


def _kelime_harfi(ch: str) -> bool:
    return ch.isalpha() or ch in "'\u2019"


def satir_farki(eski: str, yeni: str, ad: str, baglam: int = 45) -> list[str]:
    """
    Bolumlerde paragraf = tek satir; duz bir diff her degisiklik icin
    bütün paragrafi basar. Burada satir icinde yalniz degisen yer,
    git --word-diff gibi [-eski-]{+yeni+} olarak, kisa baglamla.
    """
    out = []
    a, b = eski.split("\n"), yeni.split("\n")
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        if op == "replace" and i2 - i1 == j2 - j1:
            ciftler = zip(range(i1, i2), range(j1, j2))
        else:
            for i in range(i1, i2):
                out.append(f"  {ad}:{i + 1}  " + _r("31", f"- {a[i][:160]}"))
            for j in range(j1, j2):
                out.append(f"  {ad}:{j + 1}  " + _r("32", f"+ {b[j][:160]}"))
            continue
        for i, j in ciftler:
            s1, s2 = a[i], b[j]
            ic = difflib.SequenceMatcher(None, s1, s2, autojunk=False)
            for op2, x1, x2, y1, y2 in ic.get_opcodes():
                if op2 == "equal":
                    continue
                # Butun kelimeyi goster: "Alger'[-in-]{+ın+}", "l[-a-]{+â+}yık" degil.
                sol = 0
                while x1 - sol > 0 and _kelime_harfi(s1[x1 - sol - 1]):
                    sol += 1
                sag = 0
                while x2 + sag < len(s1) and _kelime_harfi(s1[x2 + sag]):
                    sag += 1
                x1, y1, x2, y2 = x1 - sol, y1 - sol, x2 + sag, y2 + sag
                on = s1[max(0, x1 - baglam):x1]
                son = s1[x2:x2 + baglam]
                parca = ""
                if x2 > x1:
                    parca += _r("31", f"[-{s1[x1:x2]}-]")
                if y2 > y1:
                    parca += _r("32", f"{{+{s2[y1:y2]}+}}")
                out.append(f"  {ad}:{i + 1}  …{on}{parca}{son}…")
    return out


def tam_fark(c: Calisma, degisen) -> str:
    parcalar = []
    for g in degisen:
        eski = c.ozgun[g].decode("utf-8")
        yeni = c.kopyasi(g).read_text(encoding="utf-8")
        ad = _goreli(g)
        parcalar += difflib.unified_diff(
            eski.splitlines(keepends=True), yeni.splitlines(keepends=True),
            f"a/{ad}", f"b/{ad}", n=0)
    return "".join(parcalar)


# ------------------------------------------------------------ yazma


def yedek_klasoru() -> Path:
    simdi = datetime.now()
    return KOK / "yedek" / simdi.strftime("%Y-%m-%d") / f"duzelt-{simdi:%H%M%S}"


def yaz(c: Calisma, degisen) -> Path | None:
    # Once denetim: okunduktan sonra degismis dosya varsa HICBIRINE yazilmaz.
    oynayan = [g for g in degisen
               if g.stat().st_mtime != c.mtime[g] or g.read_bytes() != c.ozgun[g]]
    if oynayan:
        print(_r("31", "HATA: bu dosyalar okunduktan sonra değişti; hiçbir şey yazılmadı:"))
        for g in oynayan:
            print(f"  {_goreli(g)}")
        print("  Komutu yeniden çalıştırın.")
        return None
    yedek = yedek_klasoru()
    for g in degisen:
        hedef = yedek / _goreli(g)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_bytes(c.ozgun[g])
    for g in degisen:
        lotm.atomik_yaz(g, c.kopyasi(g).read_bytes())
    return yedek


def geri_al(klasor: Path) -> int:
    klasor = klasor if klasor.is_absolute() else (KOK / klasor)
    if not klasor.is_dir():
        print(f"HATA: yedek klasörü yok: {klasor}")
        return 1
    dosyalar = [p for p in sorted(klasor.rglob("*")) if p.is_file()]
    for p in dosyalar:
        hedef = KOK / p.relative_to(klasor)
        lotm.atomik_yaz(hedef, p.read_bytes())
        print(f"  geri alındı: {p.relative_to(klasor)}")
    print(f"{len(dosyalar)} dosya {_goreli(klasor)} yedeğinden geri yüklendi.")
    return 0


# ------------------------------------------------------------ ana akis


def aralik_oku(s: str | None):
    if not s:
        return None
    if "-" in s:
        a, b = s.split("-", 1)
        return int(a), int(b)
    return int(s), int(s)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="adımlar: " + ", ".join(ADIMLAR),
    )
    ap.add_argument("adimlar", nargs="*", help="varsayılan: hepsi")
    ap.add_argument("--bolum", default=None, help="'68' ya da '60-68' (sapka/lint/bicim)")
    ap.add_argument("--uygula", action="store_true", help="farkı göster, sor, yedekle, yaz")
    ap.add_argument("--evet", action="store_true", help="--uygula ile: sormadan yaz")
    ap.add_argument("--geri-al", dest="geri_al", default=None, metavar="YEDEK",
                    help="bir duzelt yedeğini geri yükle")
    a = ap.parse_args()

    if a.geri_al:
        return geri_al(Path(a.geri_al))

    bilinmeyen = [x for x in a.adimlar if x not in ADIMLAR]
    if bilinmeyen:
        ap.error(f"bilinmeyen adım: {', '.join(bilinmeyen)} (adımlar: {', '.join(ADIMLAR)})")
    adimlar = a.adimlar or ADIMLAR
    try:
        aralik = aralik_oku(a.bolum)
    except ValueError:
        ap.error(f"--bolum: '68' ya da '60-68' bekleniyordu ({a.bolum!r})")
    yollar = _bolum_yollari(aralik)
    if any(x in BOLUM_ADIMLARI for x in adimlar) and not yollar:
        print(f"HATA: bölüm bulunamadı ({BOLUMLER}, aralık {a.bolum or 'hepsi'})")
        return 1

    c = Calisma()
    try:
        for adim in adimlar:
            try:
                CALISTIR[adim](c, yollar)
            except Exception as e:
                # Bir adimin cokmesi oncekilerin sonucunu da gecersiz
                # kilmaz ama yazmak icin her adim temiz bitmeli.
                print(_r("31", f"HATA: '{adim}' adımı çöktü: {type(e).__name__}: {e}"))
                print("  hiçbir şey yazılmadı.")
                return 1

        degisen = c.degisenler()
        baslik = "YAZILACAK" if a.uygula else "KURU — hiçbir dosya değişmez"
        print(_r("1", f"=== KESİN DÜZELTMELER ({baslik}) ==="))
        for adim in adimlar:
            sayilar = c.adim_sayilari.get(adim, {})
            if sayilar:
                print(f"  {adim:<9} {sum(sayilar.values()):>4} değişiklik, {len(sayilar)} dosya")
            else:
                print(f"  {adim:<9}    – ")

        if degisen:
            print()
            for g in degisen:
                eski = c.ozgun[g].decode("utf-8")
                yeni = c.kopyasi(g).read_text(encoding="utf-8")
                for s in satir_farki(eski, yeni, _goreli(g)):
                    print(s)
            RAPOR.mkdir(parents=True, exist_ok=True)
            (RAPOR / "son.diff").write_text(tam_fark(c, degisen), encoding="utf-8")
            print(f"\n  tam fark: {_goreli(RAPOR / 'son.diff')}")

        if c.notlar:
            print(_r("1", "\n=== ELLE BAKILACAKLAR (dokunulmadı) ==="))
            for n in c.notlar:
                print(f"  {n}")

        if not degisen:
            print("\nkesin düzeltme yok.")
            return 0
        if not a.uygula:
            print(f"\n{len(degisen)} dosya değişecek. Yazmak için aynı komuta --uygula ekleyin.")
            return 3

        if not a.evet:
            if not sys.stdin.isatty():
                print("\n--uygula soru sormadan yazmaz; etkileşimsiz çalıştırmada --evet verin.")
                return 1
            cevap = input(f"\n{len(degisen)} dosya yedeklenip yazılsın mı? [e/H] ").strip().lower()
            if cevap not in ("e", "evet"):
                print("iptal edildi; hiçbir şey yazılmadı.")
                return 0
        yedek = yaz(c, degisen)
        if yedek is None:
            return 1
        print(_r("32", f"\n{len(degisen)} dosya yazıldı."))
        print(f"  yedek:    {_goreli(yedek)}")
        print(f"  geri al:  ./calistir.sh duzelt --geri-al {_goreli(yedek)}")
        return 0
    finally:
        c.temizle()


if __name__ == "__main__":
    sys.exit(main())
