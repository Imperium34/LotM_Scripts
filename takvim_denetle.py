#!/usr/bin/env python3
"""
takvim_denetle.py -- bolum basliklari ve yayin tarihleri.

Iki hata elle yakalanmadan yayina cikmisti: iki bolume ayni ad verilmisti,
bir bolumun tarihi takvime uymuyordu (ikincisi ancak yayindan sonra fark
edildi). Bu betik ikisini de on madde basliginda (front matter) denetler.

TAKVIM
------
Takvim kodda degil, VERIDE durur: sitenin _data/takvim.yml dosyasi (bkz.
--takvim). Orada donemler ("1'den itibaren carsamba ve cumartesi 20:00",
"61'den itibaren pazartesi, carsamba ve cumartesi") ve kabul edilmis
istisnalar yazilidir. Takvim degisikligi = o dosyada bir satir; gecmisi
git'te gorunur. Ayni dosyayi takvim_ata.py de okuyacak.

Bolum N'nin tarihi, bolum N-1'den sonraki ILK yayin gunu olmalidir -- N'nin
ait oldugu donemin gunlerine gore, o donemin saatinde. Donem sinirinda da
ayni kural: 61, 60'tan sonraki ilk YENI-donem gunudur.

  hata    : baslik bicimi / numara uyusmuyor, ayni ad iki bolumde,
            tarih yok ya da okunamiyor, donemin gunlerinden biri degil,
            tarih bir oncekinden sonra degil (ayni gun ya da geri),
            beklenen gunden ONCE
  uyari   : bir ya da daha cok gun atlanmis (ara verilmis olabilir),
            saat/saat dilimi takvimdekinden farkli

GECMIS
------
Yayinlanmis bir bolumun tarihini sonradan degistirmek, ne zaman ciktigini
yanlis gosterir. Bilinen gecmis bu yuzden duzeltilmez, KABUL EDILIR:

  ilk donemin 'baslangic'i  takvim kurallari o bolumden itibaren; oncekiler
                            yalnizca baslik ve sira denetimine girer
  istisnalar                bilinen, kabul edilmis sapmalar, gerekcesiyle
                            (20: "salı çıktı"). Sonraki bolum yine ona gore
                            denetlenir.
  aralar                    yayin yapilmayan tarih araliklari, nedeniyle.
                            Aradaki gunler atlanmis sayilmaz; arada tarihli
                            bolum hatadir.

Eskiden bunlar --baslangic / --istisna bayraklariydi; karar betigi cagiran
yerde (calistir.sh) duruyordu. Artik verenin kendisi veri; bayraklar
verilirse betik nereye tasinacaklarini soyleyip durur.

Kullanim:
    python3 takvim_denetle.py                  butun bolumler
    python3 takvim_denetle.py --bolum 47       yalnizca 47'yi ilgilendirenler
                                               + 47 icin beklenen tarih
    python3 takvim_denetle.py --takvim yol/takvim.yml

Cikis kodu: hata varsa 1; takvim dosyasi gecersizse 2.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

import yaml

import lotm
from turkce import tr_kucult

GUN_ADI = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]
_DOSYA = re.compile(r"^(\d+)\.md$")
_BASLIK = re.compile(r"^Bölüm\s+(\d+)\s*:\s*(.*\S)\s*$")
_SAPKA = str.maketrans("âîûÂÎÛ", "aiuAIU")


# ---------------------------------------------------------------- takvim


def _gun_anahtari(ad: str) -> str:
    """'Çarşamba', 'carsamba', 'çarşamba' -> 'carsamba' (yazim farki affedilir)."""
    return tr_kucult(str(ad)).translate(str.maketrans("çğışöü", "cgisou"))


_GUN_NO = {_gun_anahtari(a): i for i, a in enumerate(GUN_ADI)}


class TakvimHatasi(ValueError):
    """takvim.yml gecersiz. Denetim yapilmaz: yanlis takvimle denetlemek
    yanlis guvence verir."""


@dataclass
class Donem:
    baslangic: int
    gunler: frozenset  # datetime.weekday() degerleri
    saat: time  # tzinfo'lu

    @property
    def gun_adlari(self) -> str:
        return "/".join(GUN_ADI[g] for g in sorted(self.gunler))

    def zaman(self, gun) -> datetime:
        """O gunde, bu donemin yayin saatinde."""
        return datetime.combine(gun, self.saat)


@dataclass
class Ara:
    bas: date
    bit: date  # dahil
    neden: str


@dataclass
class Takvim:
    donemler: list  # baslangica gore sirali
    istisnalar: dict = field(default_factory=dict)  # {bolum: gerekce}
    aralar: list = field(default_factory=list)  # [Ara], yayin yapilmayan gunler

    def ara(self, gun: date) -> Ara | None:
        for a in self.aralar:
            if a.bas <= gun <= a.bit:
                return a
        return None

    def donem(self, no: int) -> Donem | None:
        """Bolum no'nun donemi; ilk donemden onceyse None (yalniz baslik/sira)."""
        bulunan = None
        for d in self.donemler:
            if d.baslangic <= no:
                bulunan = d
        return bulunan

    def takvimde(self, no: int) -> bool:
        return self.donem(no) is not None and no not in self.istisnalar


_TAKVIM_ANAHTARLARI = {"saat", "donemler", "istisnalar", "aralar"}
_ARA_ANAHTARLARI = {"bas", "bit", "neden"}
_DONEM_ANAHTARLARI = {"baslangic", "gunler", "saat"}


def _saat_oku(ham, yer: str) -> time:
    # YAML tirnaksiz 20:00:00'i altmislik TAMSAYI olarak okur (72000).
    # Sessizce yanlis saat yerine acik hata.
    if not isinstance(ham, str):
        raise TakvimHatasi(
            f'{yer}: saat tirnak icinde yazilmali, ornek "20:00:00 +0300" '
            f"(okunan: {ham!r})"
        )
    try:
        t = datetime.strptime(ham.strip(), "%H:%M:%S %z")
    except ValueError:
        raise TakvimHatasi(
            f'{yer}: saat bicimi "SS:DD:ss +ZZZZ" olmali: {ham!r}'
        ) from None
    return t.timetz()


def takvim_oku(yol) -> Takvim:
    """
    _data/takvim.yml:

        saat: "20:00:00 +0300"          # donemlerin varsayilan saati
        donemler:
          - baslangic: 12
            gunler: [çarşamba, cumartesi]
          - baslangic: 61
            gunler: [pazartesi, çarşamba, cumartesi]
            saat: "20:00:00 +0300"      # istege bagli, donemin kendi saati
        istisnalar:
          20: "salı çıktı"
        aralar:                         # bu gunlerde yayin yok (iki uc dahil)
          - bas: 2026-12-24
            bit: 2027-01-03
            neden: "yılbaşı arası"

    Taninmayan anahtarlar HATADIR, sessizce yok sayilmaz: lint'teki
    'kesin_gecis' olayi, eksik/yanlis bir anahtarin kuralin anlamini
    sessizce degistirebildigini gosterdi.
    """
    try:
        # C yukleyici (libyaml): saf Python yukleyiciden ~10x hizli; ayni nesneleri uretir.
        ham = lotm.yaml_yukle(Path(yol).read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        raise TakvimHatasi(f"takvim dosyasi yok: {yol}") from None
    except yaml.YAMLError as e:
        raise TakvimHatasi(f"takvim dosyasi okunamadi: {e}") from None
    if not isinstance(ham, dict):
        raise TakvimHatasi("takvim dosyasinin kokunde bir esleme olmali")

    fazla = set(ham) - _TAKVIM_ANAHTARLARI
    if fazla:
        raise TakvimHatasi(
            f"taninmayan anahtar(lar): {', '.join(sorted(map(str, fazla)))}"
        )

    varsayilan = _saat_oku(ham["saat"], "saat") if "saat" in ham else None

    donemler = []
    for i, d in enumerate(ham.get("donemler") or [], 1):
        yer = f"donemler[{i}]"
        if not isinstance(d, dict):
            raise TakvimHatasi(f"{yer}: esleme olmali")
        fazla = set(d) - _DONEM_ANAHTARLARI
        if fazla:
            raise TakvimHatasi(
                f"{yer}: taninmayan anahtar(lar): {', '.join(sorted(map(str, fazla)))}"
            )
        bas = d.get("baslangic")
        if not isinstance(bas, int) or bas < 1:
            raise TakvimHatasi(
                f"{yer}: 'baslangic' pozitif bir bolum numarasi olmali: {bas!r}"
            )
        gunler = set()
        for g in d.get("gunler") or []:
            no = _GUN_NO.get(_gun_anahtari(g))
            if no is None:
                raise TakvimHatasi(f"{yer}: gun adi taninmadi: {g!r}")
            gunler.add(no)
        if not gunler:
            raise TakvimHatasi(f"{yer}: 'gunler' bos olamaz")
        saat = _saat_oku(d["saat"], f"{yer}.saat") if "saat" in d else varsayilan
        if saat is None:
            raise TakvimHatasi(f"{yer}: saat yok (donemde ya da en ustte 'saat' verin)")
        donemler.append(Donem(bas, frozenset(gunler), saat))

    if not donemler:
        raise TakvimHatasi("en az bir donem olmali")
    baslar = [d.baslangic for d in donemler]
    if baslar != sorted(set(baslar)):
        raise TakvimHatasi(f"donem baslangiclari artan ve tekil olmali: {baslar}")

    istisnalar = {}
    for no, gerekce in (ham.get("istisnalar") or {}).items():
        if not isinstance(no, int):
            raise TakvimHatasi(f"istisnalar: anahtar bolum numarasi olmali: {no!r}")
        if not (isinstance(gerekce, str) and gerekce.strip()):
            # Gerekcesiz istisna bir yil sonra kimsenin hatirlamadigi bir
            # sayidir; tam da bayraklardan veriye tasimanin cozdugu sorun.
            raise TakvimHatasi(
                f'istisnalar[{no}]: gerekce yazilmali (ornek: "salı çıktı")'
            )
        istisnalar[no] = gerekce.strip()

    aralar = []
    for i, a in enumerate(ham.get("aralar") or [], 1):
        yer = f"aralar[{i}]"
        if not isinstance(a, dict):
            raise TakvimHatasi(f"{yer}: esleme olmali")
        fazla = set(a) - _ARA_ANAHTARLARI
        if fazla:
            raise TakvimHatasi(
                f"{yer}: taninmayan anahtar(lar): {', '.join(sorted(map(str, fazla)))}"
            )
        try:
            # YAML tirnaksiz 2026-12-24'u zaten date olarak okur; tirnakliyi de kabul et.
            bas, bit = (
                v if isinstance(v, date) else date.fromisoformat(str(v))
                for v in (a.get("bas"), a.get("bit"))
            )
        except (TypeError, ValueError):
            raise TakvimHatasi(
                f"{yer}: 'bas' ve 'bit' YYYY-AA-GG tarihleri olmali"
            ) from None
        if bit < bas:
            raise TakvimHatasi(f"{yer}: 'bit' ({bit}) 'bas'tan ({bas}) once")
        neden = a.get("neden")
        if not (isinstance(neden, str) and neden.strip()):
            raise TakvimHatasi(f"{yer}: 'neden' yazilmali")
        aralar.append(Ara(bas, bit, neden.strip()))

    return Takvim(donemler, istisnalar, aralar)


def varsayilan_takvim_yolu(klasor=None) -> Path:
    """Sitenin _data/takvim.yml'i: bolum klasorunun (_chapters) kardesi."""
    return Path(klasor or lotm.BOLUMLER_TR).parent / "_data" / "takvim.yml"


def sonraki_gun(d: datetime, donem: Donem, takvim: Takvim | None = None) -> datetime:
    """
    d'den SONRAKI ilk yayin gunu (donemin gunlerine gore), donemin saatinde.
    takvim verilirse aralardaki gunler atlanir: ara bir 'atlanmis gun'
    sayilmaz, takvimin parcasidir.
    """
    x = d.date() + timedelta(days=1)
    while x.weekday() not in donem.gunler or (takvim and takvim.ara(x)):
        x += timedelta(days=1)
    return donem.zaman(x)


# ---------------------------------------------------------------- bolumler


@dataclass
class Kunye:
    no: int
    dosya: str
    baslik: str | None
    tarih_ham: str | None
    tarih: datetime | None = None


def on_madde(metin: str) -> dict:
    """'---' arasindaki 'anahtar: deger' satirlari (tirnaklar atilir)."""
    satirlar = metin.split("\n")
    if not satirlar or satirlar[0].strip() != "---":
        return {}
    out = {}
    for s in satirlar[1:]:
        if s.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", s)
        if m:
            deger = m.group(2).strip()
            if len(deger) >= 2 and deger[0] == deger[-1] and deger[0] in "\"'":
                deger = deger[1:-1]
            out[m.group(1)] = deger
    return out


def tarih_oku(ham: str | None) -> datetime | None:
    if not ham:
        return None
    for bicim in (
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(ham.strip(), bicim)
        except ValueError:
            continue
    return None


def kunyeler(klasor) -> list:
    out = []
    for p in sorted(Path(klasor).iterdir()):
        m = _DOSYA.match(p.name)
        if not m:
            continue
        om = on_madde(p.read_text(encoding="utf-8"))
        k = Kunye(int(m.group(1)), p.name, om.get("title"), om.get("date"))
        k.tarih = tarih_oku(k.tarih_ham)
        out.append(k)
    return sorted(out, key=lambda k: k.no)


def ad_anahtari(ad: str) -> str:
    """Karsilastirma icin: harf buyuklugu, sapka ve noktalama farki yok."""
    return re.sub(r"[^\w]+", " ", tr_kucult(ad).translate(_SAPKA)).strip()


def _dilim_esitle(ks: list, takvim: Takvim) -> list:
    """
    Saat dilimi yazilmamis tarihlere (2026-09-26 20:00:00) bolumun
    donemindeki dilimi verir (ilk donemden onceyse ilk donemin dilimini);
    yoksa naive ile aware karsilastirilamaz ve betik duser. Eskiden
    digerlerinin en sik dilimi kullaniliyordu; artik dilim takvimde yazili.
    Doner: dilimi eklenen bolum numaralari (uyari icin).
    """
    eklenen = []
    for k in ks:
        if k.tarih and k.tarih.tzinfo is None:
            d = takvim.donem(k.no) or takvim.donemler[0]
            k.tarih = k.tarih.replace(tzinfo=d.saat.tzinfo)
            eklenen.append(k.no)
    return eklenen


def _saat_metni(t: time) -> str:
    return datetime.combine(datetime(2000, 1, 1), t).strftime("%H:%M:%S %z")


# ---------------------------------------------------------------- denetim


def denetle(ks: list, takvim: Takvim):
    """
    Doner: [(agirlik, bolum_no, mesaj, ilgili)] -- agirlik 'hata' | 'uyari';
    ilgili: bulgu bir onceki bolume gore verildiyse onun numarasi, yoksa
    None. (--bolum N, N+1'in N'ye gore bulgularini bununla secer; eskiden
    mesaj metninde "bölüm N" aranirdi ve mesaj degisince sessizce bozulurdu.)
    """
    bulgu = []
    ekle = lambda agirlik, no, mesaj, ilgili=None: bulgu.append(
        (agirlik, no, mesaj, ilgili)
    )

    for no in _dilim_esitle(ks, takvim):
        if takvim.takvimde(no):
            k = next(x for x in ks if x.no == no)
            ekle(
                "uyari",
                no,
                f"tarihte saat dilimi yok ({k.tarih_ham!r}); "
                f"takvimdeki {k.tarih:%z} varsayıldı -- ekleyin",
            )

    # --- basliklar
    adlar = defaultdict(list)
    for k in ks:
        if not k.baslik:
            ekle("hata", k.no, "başlık yok")
            continue
        m = _BASLIK.match(k.baslik)
        if not m:
            ekle("hata", k.no, f"başlık biçimi 'Bölüm N: Ad' değil: {k.baslik!r}")
            continue
        if int(m.group(1)) != k.no:
            ekle("hata", k.no, f"başlıktaki numara {m.group(1)}, dosya {k.no}")
        adlar[ad_anahtari(m.group(2))].append((k.no, m.group(2)))
    for grup in adlar.values():
        if len(grup) > 1:
            nolar = ", ".join(str(n) for n, _ in grup)
            for n, ad in grup:
                ekle("hata", n, f"aynı ad birden çok bölümde ({nolar}): {ad!r}")

    # --- tarihler: gun ve saat (bolumun kendi donemine gore)
    tarihli = [k for k in ks if k.tarih]
    for k in ks:
        d = takvim.donem(k.no)
        if not k.tarih_ham:
            ekle("hata", k.no, "tarih yok")
        elif not k.tarih:
            ekle("hata", k.no, f"tarih okunamadı: {k.tarih_ham!r}")
        elif takvim.takvimde(k.no):
            a = takvim.ara(k.tarih.date())
            if a:
                ekle(
                    "hata",
                    k.no,
                    f"{k.tarih:%Y-%m-%d} bir ara içinde: {a.neden} ({a.bas}–{a.bit})",
                )
            if k.tarih.weekday() not in d.gunler:
                ekle(
                    "hata",
                    k.no,
                    f"{k.tarih:%Y-%m-%d} bir {GUN_ADI[k.tarih.weekday()]}; "
                    f"dönemin günleri {d.gun_adlari} (dönem {d.baslangic}'den itibaren)",
                )
            beklenen_saat = _saat_metni(d.saat)
            if k.tarih.strftime("%H:%M:%S %z") != beklenen_saat:
                ekle(
                    "uyari",
                    k.no,
                    f"saat {k.tarih:%H:%M:%S %z}, takvimde {beklenen_saat}",
                )

    # --- sira ve gun araligi
    for onceki, k in zip(tarihli, tarihli[1:]):
        if k.tarih <= onceki.tarih:
            ekle(
                "hata",
                k.no,
                f"tarih ({k.tarih:%Y-%m-%d}) bölüm {onceki.no}'dan "
                f"({onceki.tarih:%Y-%m-%d}) sonra değil",
                onceki.no,
            )
            continue
        if not takvim.takvimde(k.no) or k.no != onceki.no + 1:
            continue
        d = takvim.donem(k.no)
        beklenen = sonraki_gun(onceki.tarih, d, takvim)
        if k.tarih.date() < beklenen.date():
            ekle(
                "hata",
                k.no,
                f"tarih {k.tarih:%Y-%m-%d}; bölüm {onceki.no}'dan sonraki "
                f"ilk yayın günü {beklenen:%Y-%m-%d} ({GUN_ADI[beklenen.weekday()]})",
                onceki.no,
            )
        elif k.tarih.date() > beklenen.date():
            atlanan, x = 0, beklenen
            while x.date() < k.tarih.date():
                atlanan += 1
                x = sonraki_gun(x, d, takvim)
            ekle(
                "uyari",
                k.no,
                f"{atlanan} yayın günü atlanmış: beklenen {beklenen:%Y-%m-%d}, "
                f"yazılan {k.tarih:%Y-%m-%d} (ara mı verildi?)",
                onceki.no,
            )
    return bulgu


def beklenen_tarih(ks: list, no: int, takvim: Takvim) -> datetime | None:
    """
    Bolum no icin: bir onceki tarihli bolumden sonraki ilk yayin gunu, no'nun
    doneminin gunlerine gore ve o donemin saatinde. (Eskiden saat bir onceki
    bolumden kopyalaniyordu; onun saati yanlissa yanlislik devrederdi.)
    """
    d = takvim.donem(no)
    onceki = [k for k in ks if k.no < no and k.tarih]
    if d is None or not onceki:
        return None
    return sonraki_gun(onceki[-1].tarih, d, takvim)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--klasor", default=None, help="varsayilan: lotm.BOLUMLER_TR")
    ap.add_argument(
        "--takvim",
        default=None,
        help="takvim.yml; varsayilan: sitenin _data/takvim.yml'i",
    )
    ap.add_argument(
        "--bolum", type=int, default=None, help="yalnizca bu bolumu ilgilendirenler"
    )
    ap.add_argument("--bulgular", default=None, help="bulgulari fark.py icin TSV olarak yaz")
    # Eski bayraklar: verilirse KABUL EDILMEZ. Sessizce yok saymak (ya da
    # takvimin ustune yazmak) ayni karari yine iki yerde tutmak olurdu.
    ap.add_argument("--baslangic", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--istisna", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()

    if a.baslangic is not None or a.istisna is not None:
        print(
            "--baslangic / --istisna artik takvim.yml'de duruyor:\n"
            "  --baslangic N  -> ilk donemin 'baslangic: N' degeri\n"
            '  --istisna 20   -> istisnalar: altinda  20: "gerekce"\n'
            "Bayragi cagiran yerden (calistir.sh) kaldirin.",
            file=sys.stderr,
        )
        return 2

    try:
        takvim = takvim_oku(a.takvim or varsayilan_takvim_yolu(a.klasor))
    except TakvimHatasi as e:
        print(f"takvim: {e}", file=sys.stderr)
        return 2

    ks = kunyeler(a.klasor or lotm.BOLUMLER_TR)
    if not ks:
        print("bölüm dosyası bulunamadı", file=sys.stderr)
        return 1
    bulgu = denetle(ks, takvim)

    if a.bolum is not None:
        # N'yi ilgilendiren: kendi bulgulari + N+1'in N'ye gore bulgulari
        bulgu = [
            b
            for b in bulgu
            if b[1] == a.bolum or (b[1] == a.bolum + 1 and b[3] == a.bolum)
        ]
        bek = beklenen_tarih(ks, a.bolum, takvim)
        bu = next((k for k in ks if k.no == a.bolum), None)
        if bek:
            durum = ""
            if bu and bu.tarih:
                durum = (
                    "  ✓"
                    if bu.tarih == bek
                    else f"  (yazılan: {bu.tarih:%Y-%m-%d %H:%M:%S %z})"
                )
            print(
                f"  bölüm {a.bolum} için beklenen tarih: "
                f"{bek:%Y-%m-%d %H:%M:%S %z} ({GUN_ADI[bek.weekday()]}){durum}"
            )
        if a.bolum in takvim.istisnalar:
            print(f"  bölüm {a.bolum} istisna: {takvim.istisnalar[a.bolum]}")

    hata = [b for b in bulgu if b[0] == "hata"]
    uyari = [b for b in bulgu if b[0] == "uyari"]
    if a.bulgular:
        lotm.bulgulari_yaz(
            a.bulgular,
            [((no, mesaj), f"{no:04d}.md {agirlik}: {mesaj}") for agirlik, no, mesaj, _i in bulgu],
        )
    for agirlik, no, mesaj, _ilgili in sorted(bulgu, key=lambda b: (b[1], b[0])):
        print(f"  {'!!' if agirlik == 'hata' else ' *'} {no:04d}.md  {mesaj}")
    kapsam = f"bölüm {a.bolum}" if a.bolum is not None else f"{len(ks)} bölüm"
    donem_ozet = ", ".join(f"{d.baslangic}+ {d.gun_adlari}" for d in takvim.donemler)
    print(
        f"  başlık/tarih: {len(hata)} hata, {len(uyari)} uyarı ({kapsam}; takvim: {donem_ozet})"
    )
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
