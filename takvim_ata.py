#!/usr/bin/env python3
"""
takvim_ata.py -- yayimlanmamis bolumlere takvime gore tarih verir.

takvim_denetle.py tarihleri DENETLER, bu betik YAZAR. Ikisi ayni takvimi
(_data/takvim.yml) okur ama ayri betiklerdir: *_denetle betikleri hicbir
dosyaya dokunmaz ve calistir.sh bu varsayimla calisir.

NE YAPAR
--------
Son yayimlanmis bolumu (tarihi su andan once ya da su an olan en buyuk
numarali bolum) CAPA alir. Ondan sonraki her bolume sirayla, bir oncekinden
sonraki ilk yayin gununu verir -- bolumun ait oldugu donemin gunlerine ve
saatine gore, aralari atlayarak. Tarihi olmayan bolum de tarih alir.

Ne zaman calistirilir: takvim degistiginde (yeni donem, ara), bir bolum
eklendiginde ya da tamponun tarihleri elle bozuldugunda.

KURALLAR
--------
  - Yayimlanmis bir bolume ASLA dokunulmaz. Tarihini degistirmek, ne zaman
    ciktigini yanlis gosterir (bkz. takvim_denetle, GECMIS).
  - Atanan hicbir tarih su andan once olamaz: o bolum bir sonraki derlemede
    hemen yayimlanirdi. Capa cok eskiyse zincir su andan sonraki ilk yayin
    gunune kayar (bugunun saati gecmediyse bugun dahil).
  - Istisna listesindeki gelecek bir bolumun tarihi korunur; sonrakiler ona
    gore hesaplanir.
  - Capadan ONCE yayimlanmamis bir bolum varsa (48 gelecekte, 49 yayinda)
    hicbir sey yazilmaz: sira bozuk, once elle cozulmeli.
  - Varsayilan KURU CALISMA: degisiklikler listelenir, dosyaya yazilmaz.
    Yazmak icin --yaz. Yazdiktan sonra git diff inceleme adimidir.
  - Sonucta (kuru calismada da, yazilacak hâliyle) takvim_denetle'nin
    denetimi calisir.

Kullanim:
    python3 takvim_ata.py                 ne degisecegini goster
    python3 takvim_ata.py --yaz           yaz
    python3 takvim_ata.py --simdi "2026-10-20 12:00:00 +0300"
                                          o anda calissaydi ne olurdu

Cikis kodu: 0 degisiklik yok ya da yazildi; 3 kuru calismada bekleyen
degisiklik var; 2 takvim gecersiz ya da sira bozuk (hicbir sey yazilmadi);
1 yazildi ama denetim hata buldu.
"""

from __future__ import annotations

import argparse
import copy
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import lotm
import takvim_denetle as TD

_TARIH_SATIRI = re.compile(r"^(date[ \t]*:)[^\r\n]*", re.M)
_TARIH_BICIMI = "%Y-%m-%d %H:%M:%S %z"


def _gun(d: datetime) -> str:
    return f"{d:%Y-%m-%d %H:%M:%S %z} ({TD.GUN_ADI[d.weekday()]})"


def plan_kur(ks: list, takvim: TD.Takvim, simdi: datetime):
    """
    Doner: (degisiklikler, notlar). degisiklikler: [(kunye, eski, yeni)].
    Sira bozuksa TD.TakvimHatasi yukseltir (hicbir sey yazilmamali).
    """
    yayinda = [k for k in ks if k.tarih and k.tarih <= simdi]
    if not yayinda:
        raise TD.TakvimHatasi("yayimlanmis bolum yok; capa bulunamadi")
    capa = max(yayinda, key=lambda k: k.no)

    bozuk = [k.no for k in ks if k.no < capa.no and (not k.tarih or k.tarih > simdi)]
    if bozuk:
        raise TD.TakvimHatasi(
            f"bölüm {capa.no} yayında ama ondan önceki {', '.join(map(str, bozuk))} "
            f"yayımlanmamış ya da tarihsiz; sıra bozuk, önce elle çözün"
        )

    degisiklikler, notlar = [], []
    onceki = capa.tarih
    beklenen_no = capa.no + 1
    for k in (x for x in ks if x.no > capa.no):
        if k.no != beklenen_no:
            notlar.append(
                f"bölüm {beklenen_no}–{k.no - 1} dosyası yok; {k.no} "
                f"bir önceki dosyaya göre tarihlendi"
            )
        beklenen_no = k.no + 1

        if k.no in takvim.istisnalar and k.tarih:
            notlar.append(
                f"bölüm {k.no} istisna ({takvim.istisnalar[k.no]}); tarihi korundu"
            )
            onceki = k.tarih
            continue
        d = takvim.donem(k.no)
        if d is None:
            notlar.append(f"bölüm {k.no} ilk dönemden önce; atlandı")
            if k.tarih:
                onceki = k.tarih
            continue

        yeni = TD.sonraki_gun(onceki, d, takvim)
        if yeni <= simdi:
            ilk = yeni
            while yeni <= simdi:
                yeni = TD.sonraki_gun(yeni, d, takvim)
            notlar.append(
                f"bölüm {k.no}: sıradaki yayın günü {ilk:%Y-%m-%d} geçmişte "
                f"kaldı; zincir şu andan sonraki ilk güne ({yeni:%Y-%m-%d}) kaydı"
            )
        if k.tarih != yeni:
            degisiklikler.append((k, k.tarih, yeni))
        onceki = yeni
    return degisiklikler, notlar


def yeni_icerik(yol: Path, yeni: datetime) -> bytes:
    """
    Dosyanin, YALNIZCA front matter'daki 'date:' satiri degismis hâli
    (satir yoksa kapanis '---'inden once eklenir). Satir sonlari (LF/CRLF)
    ve dosyanin geri kalani bayt bayt korunur. Diske yazmaz.
    """
    ham = yol.read_bytes().decode("utf-8")
    satir_sonu = "\r\n" if "\r\n" in ham else "\n"
    if not ham.startswith("---"):
        raise ValueError(f"{yol.name}: front matter yok")
    # \r? : CRLF dosyada '$' satir sonundaki \r'den once eslesmez.
    kapanis = re.search(r"^---[ \t]*\r?$", ham[3:], re.M)
    if not kapanis:
        raise ValueError(f"{yol.name}: front matter kapanmamış")
    son = 3 + kapanis.start()
    fm, govde = ham[:son], ham[son:]

    deger = yeni.strftime(_TARIH_BICIMI)
    if _TARIH_SATIRI.search(fm):
        fm = _TARIH_SATIRI.sub(lambda m: f"{m.group(1)} {deger}", fm, count=1)
    else:
        if not fm.endswith("\n"):
            fm += satir_sonu
        fm += f"date: {deger}{satir_sonu}"
    return (fm + govde).encode("utf-8")


def atomik_yaz(yol: Path, icerik: bytes) -> None:
    """Gecici dosya + yer degistirme: yarim kalan yazma dosyayi bozamaz."""
    fd, gecici = tempfile.mkstemp(dir=yol.parent, prefix=f".{yol.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(icerik)
        os.replace(gecici, yol)
    except BaseException:
        Path(gecici).unlink(missing_ok=True)
        raise


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--klasor", default=None, help="varsayilan: lotm.BOLUMLER_TR")
    ap.add_argument(
        "--takvim", default=None, help="varsayilan: sitenin _data/takvim.yml'i"
    )
    ap.add_argument("--yaz", action="store_true", help="degisiklikleri dosyalara yaz")
    ap.add_argument(
        "--simdi",
        default=None,
        help='"su an" yerine bu an ("YYYY-AA-GG SS:DD:ss +ZZZZ")',
    )
    a = ap.parse_args()

    klasor = Path(a.klasor or lotm.BOLUMLER_TR)
    try:
        takvim = TD.takvim_oku(a.takvim or TD.varsayilan_takvim_yolu(klasor))
    except TD.TakvimHatasi as e:
        print(f"takvim: {e}", file=sys.stderr)
        return 2

    if a.simdi:
        try:
            simdi = datetime.strptime(a.simdi, _TARIH_BICIMI)
        except ValueError:
            print(
                f'--simdi bicimi: "YYYY-AA-GG SS:DD:ss +ZZZZ" ({a.simdi!r})',
                file=sys.stderr,
            )
            return 2
    else:
        simdi = datetime.now(takvim.donemler[0].saat.tzinfo)

    ks = TD.kunyeler(klasor)
    okunamayan = [k.no for k in ks if k.tarih_ham and not k.tarih]
    if okunamayan:
        print(
            f"tarihi okunamayan bölüm(ler): {okunamayan}; önce elle düzeltin",
            file=sys.stderr,
        )
        return 2
    TD._dilim_esitle(ks, takvim)

    try:
        degisiklikler, notlar = plan_kur(ks, takvim, simdi)
    except TD.TakvimHatasi as e:
        print(f"  !! {e} -- hiçbir şey yazılmadı", file=sys.stderr)
        return 2

    for n in notlar:
        print(f"   * {n}")
    if not degisiklikler:
        print("  tarihler takvimle uyumlu; değişiklik yok")
    for k, eski, yeni in degisiklikler:
        print(f"  {k.dosya}  {_gun(eski) if eski else '(tarih yok)'}  ->  {_gun(yeni)}")

    if degisiklikler and a.yaz:
        # Iki asama: once HER dosyanin yeni hâli bellekte hazirlanir; biri
        # bile hazirlanamazsa (bozuk front matter) hicbir dosyaya yazilmaz.
        # Aksi hâlde yarida kalan bir calisma tamponu karisik birakirdi:
        # bir kismi yeni, bir kismi eski takvime gore.
        try:
            hazir = [
                (klasor / k.dosya, yeni_icerik(klasor / k.dosya, yeni))
                for k, _eski, yeni in degisiklikler
            ]
        except (ValueError, UnicodeDecodeError, OSError) as e:
            print(f"  !! {e} -- hiçbir şey yazılmadı", file=sys.stderr)
            return 2
        for yol, icerik in hazir:
            atomik_yaz(yol, icerik)
        print(f"  {len(hazir)} bölümün tarihi yazıldı")
        sonuc = TD.kunyeler(klasor)  # yazilmis hâli diskten yeniden oku
    else:
        # Kuru calisma: yazilacak hâlini bellekte kur ve onu denetle.
        sonuc = copy.deepcopy(ks)
        yeniler = {k.no: yeni for k, _e, yeni in degisiklikler}
        for k in sonuc:
            if k.no in yeniler:
                k.tarih = yeniler[k.no]
                k.tarih_ham = yeniler[k.no].strftime(_TARIH_BICIMI)

    bulgu = TD.denetle(sonuc, takvim)
    hata = [b for b in bulgu if b[0] == "hata"]
    for agirlik, no, mesaj, _ in sorted(bulgu, key=lambda b: (b[1], b[0])):
        print(f"  {'!!' if agirlik == 'hata' else ' *'} {no:04d}.md  {mesaj}")
    durum = "yazıldıktan sonra" if (degisiklikler and a.yaz) else "yazılacak hâliyle"
    print(f"  denetim ({durum}): {len(hata)} hata, {len(bulgu) - len(hata)} uyarı")

    if degisiklikler and not a.yaz:
        print("  kuru çalışma -- yazmak için --yaz")
        return 3
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
