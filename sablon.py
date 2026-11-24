#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sablon.py -- Bolum Acilis Sablonu'nu Tools/Prompts/ kilavuzlariyla uretir.

Sohbette dosya yuklemek yerine: girdileri yerel LotM klasorunden toplar, tek
bir 'claude -p' oturumu (motorlar.calistir, sabit --session-id) Tools/Prompts/
altindaki en yeni sablon kilavuzlarini uygular, sablonu ve anahtar dosyasini
yazar. Oturum kayitlidir; ardindan sohbet olarak surdurulur:

    cd /home/ali/Projects/LotM && claude --resume <oturum>

Ciktilar Reports/sablon/Ch_N/:
    istem.md        modele giden mesaj (girdi dosyalarinin listesi)
    kaynak.md       ¶ numarali ZH/EN hizalama (cevir.py ile ayni gruplar)
    Ch_N.md         sablon            -> Tools/Schemas/Ch_N.md
    Ch_N_zh.tsv     Cince anahtar     -> Tools/Schemas/Ch_N_zh.tsv
    sohbet.md       sohbet ciktilari: makbuz, F, G, H, ses haritasi bosluklari
                    (sabit '## ' basliklari; oneri isleme bunlari okuyacak)
    oturum.txt      claude oturum kimligi
Sonra once.py N calisir: sablon_denetle -> Reports/once/Ch_N/sablon_denetimi.md.

Kullanim:
    sablon.py 86                  uret, Tools/Schemas'a kopyala, denetle
    sablon.py 86 --kuru           yalniz istem.md + kaynak.md
    sablon.py 86 --uzerine-yaz    var olan Tools/Schemas/Ch_86.md'yi yedekleyip degistir
    sablon.py 86 devam            sablon oturumunu sohbet olarak ac (claude --resume <oturum>)
    sablon.py 86 oneriler         sohbet.md'nin F / G / H'sini oneriler.md'ye (bkz. sablon_oneri.py)
    sablon.py 86 incele           oneriler.md'yi inceleme sayfasinda ac (k / r / e, A uygular)
    sablon.py 86 --kararlar       kabul edilenleri words.md / Echo_Notes.md'ye yaz
    sablon.py 86 --kopyala        model yok: sohbette duzeltilen Reports/sablon/Ch_86/Ch_86.md'yi
                                  yeniden Tools/Schemas'a koy (yedekler) ve denetle
    sablon.py 86 --model M        (varsayilan opus[1m]; LOTM_SABLON_MODEL)
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

BETIKLER = Path(__file__).resolve().parent
sys.path.insert(0, str(BETIKLER))
sys.path.insert(0, str(BETIKLER / "harita"))

import lotm  # noqa: E402
import motorlar as M  # noqa: E402

KOK = Path(os.environ.get("LOTM_KOK") or BETIKLER.parent)
TOOLS = KOK / "Tools"
HARITALAR = TOOLS / "Voice_Maps"
PROMPTS = TOOLS / "Prompts"
SITE = KOK / "Imperium34.github.io"
SABLONLAR = Path(os.environ.get("LOTM_SABLONLAR") or TOOLS / "Schemas")
KELIMELER = Path(os.environ.get("LOTM_KELIMELER") or TOOLS / "words.md")
HAZIRLIK = BETIKLER / "Reports" / "hazirlik"
ONCE = Path(os.environ.get("LOTM_ONCE_RAPOR") or BETIKLER / "Reports" / "once")
RAPOR = Path(os.environ.get("LOTM_SABLON_RAPOR") or BETIKLER / "Reports" / "sablon")
BECERI_PARCALARI = ("SKILL", "sartname", "sohbet_ciktilari")

# sohbet.md'nin basliklari: oneri isleme bunlari arar, degistirmeyin.
BASLIKLAR = [
    "## Tarama makbuzu",
    "## F — words.md teklifleri",
    "## G — Yankı defteri teklifleri",
    "## H — Ad kararları",
    "## Ses haritası boşlukları",
]


def _oku_metin(yol: Path) -> str:
    return yol.read_text(encoding="utf-8") if yol.exists() else ""


def _oku_oturum(klasor: Path) -> str:
    return _oku_metin(klasor / "oturum.txt").strip()


def _atomik_kopyala(kaynak: Path, hedef: Path) -> None:
    """Atomik kopya + taze mtime (once.py bayatlik denetimi her zaman tetiklensin)."""
    hedef.parent.mkdir(parents=True, exist_ok=True)
    fd, gecici = tempfile.mkstemp(prefix=f".{hedef.name}.", dir=hedef.parent)
    os.close(fd)
    try:
        shutil.copyfile(kaynak, gecici)
        os.replace(gecici, hedef)
    except BaseException:
        Path(gecici).unlink(missing_ok=True)
        raise


def beceri_dosyalari(prompts: Path | None = None) -> list[Path]:
    """PROMPTS altindaki en yeni lotm_chapter_template_vX_{SKILL,sartname,sohbet_ciktilari}.md.

    Yalniz PROMPTS klasorune bakar; Prompts/old/ altindaki eski surumler secilmez.
    """
    kok = prompts or PROMPTS
    desen = re.compile(
        r"lotm_chapter_template_v(\d+(?:\.\d+)*)_(" + "|".join(BECERI_PARCALARI) + r")\.md"
    )
    surumler: dict[tuple[int, ...], dict[str, Path]] = {}
    if kok.exists():
        for p in kok.glob("lotm_chapter_template_v*.md"):
            m = desen.fullmatch(p.name)
            if m:
                v = tuple(int(x) for x in m.group(1).split("."))
                surumler.setdefault(v, {})[m.group(2)] = p
    if surumler:
        en_yeni = max(surumler)
        etiket = ".".join(str(x) for x in en_yeni)
        parcalar = surumler[en_yeni]
        return [
            parcalar.get(a, kok / f"lotm_chapter_template_v{etiket}_{a}.md")
            for a in BECERI_PARCALARI
        ]
    return [kok / f"lotm_chapter_template_v5_{a}.md" for a in BECERI_PARCALARI]


def eksik_basliklar(sohbet: str) -> list[str]:
    """sohbet.md'de sablon_oneri.bolumler()'in bekledigi tam satir basliklardan eksikler."""
    satirlar = {s.strip() for s in sohbet.splitlines()}
    return [b for b in BASLIKLAR if b not in satirlar]


def kaynak_metni(no: int) -> str:
    """cevir.hizali_kaynak ile ayni ¶ gruplari (sablon ¶'lari ceviriyle eslessin)."""
    from gruplar import gruplar
    g = gruplar(no, "en")
    if not g:
        raise FileNotFoundError(f"{no}. bolumun ZH/EN metni bulunamadi")
    return "\n\n".join(f"¶{k}\nZH: {v['ZH']}\nEN: {v['EN']}" for k, v in g.items())


# Okunacaklar (tam) ve aranacaklar (Grep / parca Read): ses haritalarinin tamami
# ~400 KB; bolume dusen girisler ses_haritasi.md'de (once.py). words.md dokumun
# ikinci kontroludur (beceri: optional).
def girdiler(no: int, klasor: Path) -> list[tuple[str, Path, str]]:
    """(etiket, yol, kip) -- kip: 'oku' (zorunlu, tam), 'oku?' (varsa tam), 'ara'."""
    onceki = no - 1
    return [
        ("system_core", lotm.cekirdek_istem(), "oku"),
        ("chapter_text", klasor / "kaynak.md", "oku"),
        ("term_dump", HAZIRLIK / f"Ch_{no}_terimler.md", "oku"),
        ("reserved_index", HAZIRLIK / "ayrilmis_dizin.md", "oku"),
        ("voicemaps: bu bölümün karakterleri, aşamaları ve girişleri (Klein.md + Side_Character_Maps.md'den)",
         ONCE / f"Ch_{no}" / "ses_haritasi.md", "oku"),
        ("echo", HARITALAR / "Echo_Notes.md", "oku"),
        ("schema", HARITALAR / "Schema.md", "oku"),
        ("previous_template", SABLONLAR / f"Ch_{onceki}.md", "oku?"),
        ("previous_chapter", SITE / "_chapters" / f"{onceki:04d}.md", "oku?"),
        ("review", BETIKLER / "Reports" / "sonra" / f"Ch_{onceki}" / "5_inceleme.md", "oku?"),
        ("voicemaps (tam)", HARITALAR / "Klein.md", "ara"),
        ("voicemaps (tam)", HARITALAR / "Side_Character_Maps.md", "ara"),
        ("glossary", KELIMELER, "ara"),
    ]


def istem_kur(no: int, klasor: Path, liste: list, beceri: list[Path] | None = None) -> str:
    oku, ara, eksik = [], [], []
    for e, y, k in liste:
        yol = Path(y)
        satir = f"- `<{e}>`: {yol}"
        if not yol.exists():
            eksik.append(satir)
        elif k == "ara":
            ara.append(satir)
        else:
            oku.append(satir)
    beceri_listesi = beceri if beceri is not None else beceri_dosyalari()
    beceri_metin = "\n".join(f"- {b}" for b in beceri_listesi)
    basliklar = "\n".join(BASLIKLAR)
    n = chr(10)
    return f"""# {no}. bölüm için Bölüm Açılış Şablonu

Aşağıdaki üç şablon kılavuz dosyasını baştan sona oku ve kurallarını eksiksiz uygula (yalnızca bu üç dosyayı kullan; `Tools/Prompts/old/` altındaki eski sürümleri okuma ya da arama):
{beceri_metin}

Girdiler yerel dosyalarda; hepsi verilmiş sayılır, kullanıcıdan dosya isteme.

Baştan sona oku (uzunsa parça parça):
{n.join(oku)}

Tamamını okuma; gerektiğinde Grep ile ara ve ilgili kısmı oku (ses haritası özeti bir karakteri ince bırakıyorsa, dökümün açık bıraktığı bir terim, [YENİ] satırlarının yeniden denetimi):
{n.join(ara)}
{("Bulunamayanlar (beceri kuralına göre eksik say):" + n + n.join(eksik)) if eksik else ""}

`kaynak.md`'deki ¶ numaraları, çevirmene gidecek hizalama gruplarıdır; şablondaki her ¶ bu numaralarla yazılır.

Başka bir bölümün metni gerekirse `Source/` dosyalarını açma (Çince gb18030'dur); `python3 {BETIKLER / "bolum.py"} <no> --zh --tr` (ya da `--zh --en`) kullan.

## Teslim

1. Şablonu `{klasor / f"Ch_{no}.md"}` dosyasına, Çince anahtar dosyasını `{klasor / f"Ch_{no}_zh.tsv"}` dosyasına yaz. Başka hiçbir dosyayı yazma ya da değiştirme. `sablon_denetle.py`'yi betik kendisi çalıştıracak; hatırlatma satırı gerekmez.
2. Son cevabın (sohbet kısmı) yalnız şu başlıkları, bu sırayla ve aynen taşır; her başlığın altı `sohbet_ciktilari.md`'deki kurallarla yazılır, boşsa "yok":

{basliklar}

Başlıklardan önce ya da sonra başka metin yazma. Bu cevap bir betik tarafından okunacak:
- F'de var olan bir words.md satırını değiştiren her satır, satırın sonunda `  ← DEĞİŞTİRME: <ne değişti>` taşır; işaret hiçbir zaman kategori başlığına konmaz. Kategori başlıkları words.md'deki başlıkların aynısıdır (`## Ritual & Incantation`, `# XII. Frozen Lines`); words.md'de olmayan başlık açma.
- H'de her ad için, açıklama satırından sonra bir `md` kod bloğu: words.md başlığı ve iki F satırı, önce şablonun kullandığı, sonra öteki seçenek (her biri ötekinin biçimini `yazılmaz` ile yasaklar).
- G'deki girişler tek bir kod bloğunda; kusur raporları ve eşleşme notları kod bloğunun dışında.
"""


def cikti_kurtar(
    klasor: Path, oturum: str, no: int, tmp_kok: Path = Path("/tmp")
) -> list[str]:
    """Yazma izni reddedilirse model dosyalari kendi scratchpad'ine yazar
    (21 Kas, Ch86): /tmp/claude-*/<proje>/<oturum>/scratchpad/. Oradan al."""
    if not oturum or any(c in oturum for c in "*?[]"):
        return []
    kurtarilan = []
    for ad in (f"Ch_{no}.md", f"Ch_{no}_zh.tsv"):
        if (klasor / ad).exists():
            continue
        bulunan = list(tmp_kok.glob(f"claude-*/*/{oturum}/scratchpad/{ad}"))
        if bulunan:
            en_yeni = max(bulunan, key=lambda p: p.stat().st_mtime)
            _atomik_kopyala(en_yeni, klasor / ad)
            kurtarilan.append(ad)
            print(f"  UYARI: {ad} oturumun scratchpad'inden alindi ({en_yeni})")
    return kurtarilan


def _eylem_devam(no: int, klasor: Path) -> int:
    kimlik_yolu = klasor / "oturum.txt"
    oturum = _oku_oturum(klasor)
    if not oturum:
        print(f"HATA: {kimlik_yolu} yok veya bos: once ./calistir.sh sablon {no}")
        return 1
    os.chdir(KOK)  # oturumlar cwd'ye gore kayitli
    os.execvp("claude", ["claude", "--resume", oturum])
    return 0


def _eylem_oneriler(no: int, klasor: Path, yeniden: bool) -> int:
    import sablon_oneri as O
    sohbet, cikti = klasor / "sohbet.md", klasor / "oneriler.md"
    if not sohbet.exists():
        print(f"HATA: {sohbet} yok")
        return 1
    if (
        cikti.exists()
        and re.search(r"\[[xX✓✔]\] (kabul|ret)", _oku_metin(cikti))
        and not yeniden
    ):
        print(f"HATA: {cikti} işaretli maddeler taşıyor; yeniden kurmak için --yeniden")
        return 1
    hazir, bolum = O.bolum_durumu(no)
    lotm.atomik_yaz(
        cikti,
        O.oneriler_kur(
            no,
            _oku_metin(sohbet),
            _oku_metin(O.KELIMELER),
            _oku_metin(O.YANKI),
            _oku_metin(SABLONLAR / f"Ch_{no}.md"),
            _oku_metin(SABLONLAR / f"Ch_{no}_zh.tsv"),
            bolum if hazir else "",
        ),
    )
    if not hazir:
        print(
            f"UYARI: {no} henüz yayımlanmadı ya da sonra kararları işlenmedi: metin denetimi yok, "
            "uygulama bekler. Çeviri ve sonra'dan sonra 'oneriler --yeniden' daha iyi."
        )
    print(f"{cikti}\nİnceleme: ./calistir.sh sablon {no} incele   Uygula: ./calistir.sh sablon {no} --kararlar")
    return 0


def _eylem_incele(no: int, klasor: Path) -> int:
    yol = klasor / "oneriler.md"
    if not yol.exists():
        print(f"HATA: {yol} yok: once ./calistir.sh sablon {no} oneriler")
        return 1
    rc = subprocess.call([
        sys.executable, str(BETIKLER / "inceleme_sunucu.py"),
        "--dosya", str(yol), "--bolum", str(no), "--tek",
    ])
    import sablon_oneri as O
    kn = O.kuyruk_notu(O.kuyruk_sayisi())
    if kn:
        print(kn)
    return rc


def _hazirla_ve_istem(no: int, klasor: Path) -> tuple[str | None, int]:
    """1. hazirlik (once.py --sadece-hazirlik), kaynak.md, girdi denetimi, istem.md."""
    print(f"hazirlik: once.py {no} --sadece-hazirlik ...", flush=True)
    p = subprocess.run(
        [sys.executable, str(BETIKLER / "once.py"), str(no), "--sadece-hazirlik"],
        capture_output=True, text=True, cwd=BETIKLER,
    )
    if p.returncode != 0 or not (HAZIRLIK / f"Ch_{no}_terimler.md").exists():
        if p.stdout.strip():
            print(p.stdout[-2000:])
        if p.stderr.strip():
            print(p.stderr[-2000:])
        print("HATA: hazirlik / terim dokumu uretilemedi")
        return None, 1

    try:
        metin = kaynak_metni(no)
    except FileNotFoundError as e:
        print(f"HATA: {e}")
        return None, 1

    klasor.mkdir(parents=True, exist_ok=True)
    lotm.atomik_yaz(klasor / "kaynak.md", metin + "\n")

    try:
        liste = girdiler(no, klasor)
    except FileNotFoundError as e:
        print(f"HATA: {e}")
        return None, 1

    for e, y, kip in liste:
        if kip == "oku" and not Path(y).exists():
            print(f"HATA: zorunlu girdi yok: <{e}> {y}")
            return None, 1

    beceri = beceri_dosyalari()
    for b in beceri:
        if not b.exists():
            print(f"HATA: sablon kilavuz dosyasi yok: {b}")
            return None, 1

    istem = istem_kur(no, klasor, liste, beceri=beceri)
    lotm.atomik_yaz(klasor / "istem.md", istem)
    return istem, 0


def _onceki_oturumu_yedekle(no: int, klasor: Path) -> None:
    """Yeni model cagrisindan once var olan rapor ciktilarini yedekler."""
    mevcut = [
        klasor / ad
        for ad in (f"Ch_{no}.md", f"Ch_{no}_zh.tsv", "sohbet.md", "oturum.txt")
        if (klasor / ad).exists()
    ]
    if not mevcut:
        return
    yedek = lotm.yedek_klasoru(f"sablon-rapor-{no}")
    yedek.mkdir(parents=True, exist_ok=True)
    for y in mevcut:
        shutil.copy2(y, yedek / y.name)
    print(f"yedek (onceki oturum): {yedek}")


def _yerine_koy_ve_denetle(no: int, klasor: Path, oturum: str) -> int:
    cikti, cikti_zh = klasor / f"Ch_{no}.md", klasor / f"Ch_{no}_zh.tsv"
    hedef, hedef_zh = SABLONLAR / f"Ch_{no}.md", SABLONLAR / f"Ch_{no}_zh.tsv"

    sohbet = _oku_metin(klasor / "sohbet.md")
    eksik_baslik = eksik_basliklar(sohbet)
    if eksik_baslik:
        print("UYARI: sohbet.md'de eksik baslik: " + ", ".join(eksik_baslik))
    if not cikti_zh.exists():
        print(f"UYARI: {cikti_zh.name} yazilmadi")

    # 3. Tools/Schemas'a atomik kopya (var olan once yedeklenir; taze mtime)
    if hedef.exists() or hedef_zh.exists():
        yedek = lotm.yedek_klasoru(f"sablon-{no}")
        yedek.mkdir(parents=True, exist_ok=True)
        for y in (hedef, hedef_zh):
            if y.exists():
                shutil.copy2(y, yedek / y.name)
        print(f"yedek: {yedek}")
    _atomik_kopyala(cikti, hedef)
    if cikti_zh.exists():
        _atomik_kopyala(cikti_zh, hedef_zh)
    elif hedef_zh.exists():
        hedef_zh.unlink()
        print(f"UYARI: eski {hedef_zh.name} kaldirildi (yedeklendi; yeni calistirmada uretilmedi)")

    # 4. denetim
    p = subprocess.run(
        [sys.executable, str(BETIKLER / "once.py"), str(no)],
        capture_output=True, text=True, cwd=BETIKLER,
    )
    if p.stdout.strip():
        print(p.stdout.strip())
    if p.stderr.strip():
        print(p.stderr.strip(), file=sys.stderr)
    print()
    print(f"Sablon:  {hedef}")
    print(f"Sohbet:  {klasor / 'sohbet.md'}  (F / G / H önerileri)")
    print(f"Oneriler: ./calistir.sh sablon {no} oneriler")
    if oturum:
        devam = f"./calistir.sh sablon {no} devam   (= cd {KOK} && claude --resume {oturum})"
        print(f"Oturum:  {oturum}")
        print(f"Sohbete devam:  {devam}")
    return p.returncode


def _eylem_kopyala(no: int, klasor: Path) -> int:
    """Model yok: sohbette (claude --resume) duzeltilmis ciktiyi yerine koy, denetle."""
    cikti = klasor / f"Ch_{no}.md"
    oturum = _oku_oturum(klasor)
    cikti_kurtar(klasor, oturum, no)
    if not cikti.exists():
        print(f"HATA: {cikti} yok")
        return 1
    return _yerine_koy_ve_denetle(no, klasor, oturum)


def _eylem_uret(a: argparse.Namespace, klasor: Path) -> int:
    no = a.no
    hedef = SABLONLAR / f"Ch_{no}.md"
    if hedef.exists() and not (a.uzerine_yaz or a.kuru):
        print(f"HATA: {hedef} zaten var. Yeniden uretmek icin --uzerine-yaz (once yedeklenir).")
        return 1

    istem, kod = _hazirla_ve_istem(no, klasor)
    if kod != 0 or istem is None:
        return kod
    if a.kuru:
        print(f"kuru: {klasor / 'istem.md'}")
        return 0

    cikti, cikti_zh = klasor / f"Ch_{no}.md", klasor / f"Ch_{no}_zh.tsv"
    _onceki_oturumu_yedekle(no, klasor)
    for ad in (cikti.name, cikti_zh.name, "sohbet.md"):
        (klasor / ad).unlink(missing_ok=True)
    oturum = str(uuid.uuid4())
    lotm.atomik_yaz(klasor / "oturum.txt", oturum + "\n")

    izin_yolu = f"//{str(klasor.resolve()).lstrip('/')}/**"
    print(f"sablon: claude -p (oturum {oturum}) ... 15-30 dk surer", flush=True)
    t0 = time.monotonic()
    s = M.calistir(
        istem, "claude", model=a.model, sure=a.sure, cwd=KOK, oturum=oturum,
        araclar=[
            "Read", "Glob", "Grep",
            f"Write({izin_yolu})",
            f"Edit({izin_yolu})",
            f"Bash(python3 {BETIKLER / 'bolum.py'}:*)",
        ],
        ek_argumanlar=["-n", f"LotM şablon {no}"],
    )
    gecen = int(time.monotonic() - t0)
    print(f"sablon: bitti ({gecen // 60} dk {gecen % 60} sn)", flush=True)
    if s.ok:
        lotm.atomik_yaz(klasor / "sohbet.md", s.metin.strip() + "\n")
    cikti_kurtar(klasor, oturum, no)
    if not s.ok or not cikti.exists():
        print(f"HATA: sablon yazilmadi ({s.hata or cikti.name + ' yok'})")
        print(f"Oturuma bakmak icin: cd {KOK} && claude --resume {oturum}")
        return 1
    return _yerine_koy_ve_denetle(no, klasor, oturum)


def _arguman_cozumle(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bolum acilis sablonu (Tools/Prompts kilavuzlari, claude -p).")
    ap.add_argument("no", type=int)
    ap.add_argument(
        "eylem", nargs="?", choices=["devam", "oneriler", "incele"],
        help="devam: oturumu sohbet olarak ac (claude --resume); oneriler: sohbet.md -> "
             "oneriler.md; incele: oneriler.md'yi inceleme sayfasinda ac",
    )
    ap.add_argument("--kuru", action="store_true", help="yalniz istem.md ve kaynak.md")
    ap.add_argument("--uzerine-yaz", action="store_true", help="var olan Tools/Schemas/Ch_N.md'yi yedekleyip degistir")
    ap.add_argument(
        "--kararlar", action="store_true",
        help="oneriler.md'de kabul edilenleri uygula (words.md; Echo_Notes sonra N --kararlar'dan sonra)",
    )
    ap.add_argument("--yeniden", action="store_true", help="oneriler: isaretli oneriler.md'yi yeniden kur")
    ap.add_argument(
        "--kopyala", action="store_true",
        help="model yok: Reports/sablon/Ch_N/'deki sablonu (sohbette duzeltilmis) Tools/Schemas'a koy, denetle",
    )
    ap.add_argument(
        "--model", default=os.environ.get("LOTM_SABLON_MODEL", "opus[1m]"),
        help="varsayilan opus[1m] (LOTM_SABLON_MODEL): girdiler ~150k jeton",
    )
    ap.add_argument("--sure", type=int, default=3600, help="saniye (varsayilan 3600)")
    a = ap.parse_args(argv)

    bayraklar = [ad for ad, var in (("--kararlar", a.kararlar), ("--kuru", a.kuru), ("--kopyala", a.kopyala)) if var]
    if len(bayraklar) > 1:
        ap.error(f"birlikte kullanilamaz: {', '.join(bayraklar)}")
    if a.eylem and (bayraklar or a.uzerine_yaz):
        cakisan = bayraklar + (["--uzerine-yaz"] if a.uzerine_yaz else [])
        ap.error(f"'{a.eylem}' ile birlikte kullanilamaz: {', '.join(cakisan)}")
    if a.yeniden and a.eylem != "oneriler":
        ap.error("--yeniden yalniz 'oneriler' eylemiyle kullanilir")
    if a.kararlar and a.uzerine_yaz:
        ap.error("--kararlar ile --uzerine-yaz birlikte kullanilamaz")
    return a


def main(argv=None) -> int:
    a = _arguman_cozumle(argv)
    no = a.no
    klasor = RAPOR / f"Ch_{no}"

    if a.eylem == "devam":
        return _eylem_devam(no, klasor)
    if a.eylem == "oneriler":
        return _eylem_oneriler(no, klasor, a.yeniden)
    if a.eylem == "incele":
        return _eylem_incele(no, klasor)
    if a.kararlar:
        import sablon_oneri as O
        return O.kararlar(no, klasor)
    if a.kopyala:
        return _eylem_kopyala(no, klasor)
    return _eylem_uret(a, klasor)


if __name__ == "__main__":
    sys.exit(main())
