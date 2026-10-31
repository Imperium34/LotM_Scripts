#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sapka.py -- şapkalı yazımı bölümler boyunca tekleştirir.

sozluk_lint.py'nin diyakritik taraması ADAY üretir; bu betik adayların
MEKANİK OLARAK GÜVENLİ olanlarını uygular ve geri kalanını elle bakılmak
üzere ayırır.

NEDEN İKİYE AYRILIYOR
---------------------
"Hepsine şapka koy" güvenli bir kural değil. Şapkanın Türkçede üç ayrı işi
var ve yalnızca ikisi mekanik:

  1. k/g/l DAMAKSILLAŞMASI  (kâğıt, mekân, imkân, rüzgâr, pekâlâ, yegâne)
     Şapka uzunluk değil, ünsüzün inceliğini gösterir. Karşılığı olan
     şapkasız bir kelime yok, dolayısıyla körlemesine değiştirilebilir.

  2. ARAPÇA ALINTILARDA UZUNLUK  (âdeta, dâhil, hâdise, zât, hâl ailesi)
     Kayıt tercihi. Şapkasız biçim çoğu zaman ayrı bir kelime değil, aynı
     kelimenin sadeleşmiş yazımı. Birkaç istisna dışında güvenli.

  3. NİSBET -î  (resmî, askerî, tarihî, hayalî, madenî, dinî)
     GÜVENLİ DEĞİL. "resmî" resmi/official demek, "resmi" ise "onun resmi".
     İkisi ayrı kelime; hangisinin kastedildiği ancak cümleye bakılarak
     bilinir. Bu grup asla otomatik değiştirilmez, yalnızca listelenir.

Ayrıca 1. ve 2. gruptaki birkaç kelime gerçek eşadlıdır ve elde bırakılır:
    hakim               ~ hâkim (hükmeden) / hakîm (bilge)
    hala (teyze/hala)   ~ hâlâ (henüz)
    hale (ayla/nur)     ~ hâle (hâl + yönelme)
    alem (bayrak/sancak)~ âlem (dünya)
    adet (sayı)         ~ âdet (görenek)
    kar  (yağan)        ~ kâr  (kazanç)

SÖZLÜK YÖNÜ BELİRLER
--------------------
Bazı kelimeler sözlükteki ÖZEL ADLARIN içinde de geçer: "Ruhani Âlem",
"Ebedi Gece Tanrıçası", "Semavi Muazzez", "Kabus". Bir kelime sözlükte
geçiyorsa, sözlükteki yazımı o kelimenin KİTAP BOYUNCA yazımıdır: listede
"ebedi -> ebedî" yazsa bile sözlük "Ebedi" diyorsa değişiklik TERSİNE
uygulanır ("ebedî" -> "ebedi"). Böylece "Semavî Muazzez" gibi sözlükle
çelişen bir yazım da sözlüğe çekilir. Karar tek yerde verilir: bir
kelimenin yazımını değiştirmek için sözlüğü değiştirin, betik gerisini
yapar. Sözlükte aynı kelime iki yazımla geçiyorsa kelimeye dokunulmaz ve
"önce sözlüğü tekleştirin" diye raporlanır.

LİSTEYİ BÜYÜTMEK: --kesif
------------------------
Liste kapalı kalır, ama elle tahmin edilmez. --kesif bölümlerde AYNI
kelimenin hem şapkalı hem şapkasız geçtiği çiftleri bulur ve yapıştırılmaya
hazır satır olarak yazar. Hangi yöne gidileceğine (ve kelimenin hangi
gruba girdiğine) insan karar verir.

Kullanım:
    python3 sapka.py bolumler/*.md            # kuru çalıştırma (yazmaz)
    python3 sapka.py --uygula bolumler/*.md   # dosyaları değiştirir
    python3 sapka.py --elle bolumler/*.md     # yalnızca elle bakılacaklar
    python3 sapka.py --kesif bolumler/*.md    # listeye aday çiftler
    python3 sapka.py --sozluk _data/sozluk.yml ...   # yönü sözlük belirler
    python3 sapka.py --sozluk ... --kelimeler words.md ...   # words.md de
    python3 sapka.py --sozluk-gocu --sozluk sozluk.yml --kelimeler words.md
                                              # sözlüğün kendisini şapkalıya taşı

SÖZLÜK GÖÇÜ
-----------
--sozluk-gocu listeyi (yalnız GÜVENLİ gruplar, ileri yönde) sözlük
dosyalarının KENDİSİNE uygular. sozluk.yml'de yalnızca Türkçe ad alanları
değişir (terim, isim, arama_adi); satırlar metin olarak düzenlenir, yani
yorumlar, boş satırlar ve girinti aynen kalır ve diff yalnız o kelimeleri
gösterir. eski_karsiliklar ASLA değişmez (bilerek eski biçimlerdir).
--duzyazi ile aciklama / cevirmen_notu da taşınır. Yazmadan önce iki
sürüm de ayrıştırılıp karşılaştırılır: izin verilen alanların dışında tek
bir değer değişmişse hiçbir şey yazılmaz. words.md düz metin olarak baştan
sona taşınır. Göçten sonra aynı komut bölümler için ileri yönde çalışır.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# turkce.py Tools/ kokunde; bu betik lint/ alt klasorunde.
for _yol in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent):
    if (_yol / "turkce.py").exists():
        sys.path.insert(0, str(_yol))
        break
from turkce import tr_buyut, tr_kucult  # noqa: E402
from lotm import atomik_yaz  # noqa: E402

# --------------------------------------------------------------------
# GÜVENLİ: şapkasız biçim -> şapkalı biçim
# Liste bilerek KAPALIDIR: yalnızca metinde fiilen geçtiği doğrulanmış
# biçimler var. Açık uçlu bir kök+ek üretici, "halk" ya da "halı" gibi
# alakasız kelimelere sıçrama riski taşır.
# --------------------------------------------------------------------

DAMAKSIL = {                       # k / g / l inceltmesi
    "kağıt": "kâğıt",
    "kağıdı": "kâğıdı",
    "kağıda": "kâğıda",
    "kağıtları": "kâğıtları",
    "kağıdın": "kâğıdın",          # 46. bölümde şapkalı geçiyor
    "mekan": "mekân",
    "mekana": "mekâna",
    "mekanı": "mekânı",
    "mekanda": "mekânda",
    "imkan": "imkân",
    "imkanı": "imkânı",
    "imkansız": "imkânsız",
    "rüzgar": "rüzgâr",
    "rüzgarla": "rüzgârla",
    "rüzgarın": "rüzgârın",
    "rüzgarı": "rüzgârı",
    "pekala": "pekâlâ",
    "yegane": "yegâne",
    "sükunet": "sükûnet",
    "sükunetin": "sükûnetin",
    "sükunetini": "sükûnetini",
    "sükunete": "sükûnete",
    "sükuneti": "sükûneti",        # keşif
    "kabus": "kâbus",              # keşif; sözlükte Mertebe adı "Kabus"
    "ilaveten": "ilâveten",
    "bekar": "bekâr",              # 46. bölüm
    "eşkal": "eşkâl",              # 46. bölüm: "eşkâlini"
    "eşkali": "eşkâli",
    "eşkalini": "eşkâlini",
    # 26 Eki kararı: kayıt kelimeleri otomatik (lâkin, kelâm, lâyık,
    # ahlâk, evlât); gündelik olanlar aşağıda KAYIT'ta.
    "lakin": "lâkin",
    "kelam": "kelâm",
    "kelamı": "kelâmı",
    "kelamına": "kelâmına",
    "kelamları": "kelâmları",
    "layık": "lâyık",
    "layıkıyla": "lâyıkıyla",
    "ahlak": "ahlâk",
    "ahlakı": "ahlâkı",
    "ahlakına": "ahlâkına",
    "ahlaklarına": "ahlâklarına",
    "evlat": "evlât",
    "evladı": "evlâdı",
}

UZUNLUK = {                        # Arapça alıntılarda uzun ünlü
    "adeta": "âdeta",
    "dahil": "dâhil",
    "dahili": "dâhilî",
    "hadise": "hâdise",
    "hadiseye": "hâdiseye",
    "hadiseler": "hâdiseler",
    "zat": "zât",
    "zatı": "zâtı",
    # hâl ailesi -- tek kelime, çok çekim
    "hal": "hâl",
    "hali": "hâli",
    "halde": "hâlde",
    "haldeydi": "hâldeydi",
    "halinde": "hâlinde",
    "halinden": "hâlinden",
    "haline": "hâline",
    "halini": "hâlini",
    "halihazırda": "hâlihazırda",
    "haliyle": "hâliyle",          # keşif
    "heyula": "heyûlâ",            # keşif
    "herhalde": "herhâlde",
}

# Şapkası Kubbealtı'na göre doğru ama kelimenin kendisi GÜNLÜK KONUŞMA
# malzemesi olanlar. Otomatik uygulanmaz: bu sözlüğün asıl kaydı anlatıcıda
# arkaik, Klein'ın iç sesinde modern. "lâzım" gibi bir kelime Melissa'nın
# mutfak repliğine ya da Klein'ın argosuna şapka takarak tam da ayırmaya
# çalıştığınız iki sesi birbirine karıştırır.
KAYIT = {
    "lazım": "lâzım",
    # 26 Eki kararı: damaksıl şapka doğru, ama kelime gündelik dilden.
    # Anlatıcıda istenirse elle konur; Klein'ın sesinde ve replikte kalır.
    "laf": "lâf",
    "lafı": "lâfı",
    "lafa": "lâfa",
    "lamba": "lâmba",
    "lambası": "lâmbası",
    "selam": "selâm",
    "plan": "plân",
    "telaş": "telâş",
    "telaşla": "telâşla",
    "ilan": "ilân",
    "ilaç": "ilâç",
}

# NİSBET -î, ama EŞADLISI OLMAYANLAR. Ölçüt: şapkasız "-i" biçimi aynı
# kökün iyelik/belirtme hâli olarak okunabiliyor mu? "resmi" okunur (resm +
# i), "esrari" okunamaz: "esrar"ın belirtme hâli ünlü uyumu gereği "esrarı"
# olur. Kalın ünlülü kökler çoğunlukla bu yüzden güvenlidir; ama "hayal ->
# hayali" gibi ince l ile biten kökler kuralı bozar, onun için her kelime
# tek tek düşünülerek eklenir.
NISBET_GUVENLI = {
    "ruhani": "ruhanî",            # 32, 33, 37, 45 -- iki yazım karışık
    "esrari": "esrarî",            # sözlük "Esrarî Müşahede" oldu
    "mizahi": "mizahî",            # keşif; "mizah"ın belirtmesi "mizahı"
    "asli": "aslî",                # keşif; "asıl"ın belirtmesi "aslı"
    "semavi": "semavî",            # keşif; sözlükte "Semavi Muazzez"
    "ebedi": "ebedî",              # keşif; sözlükte "Ebedî Gece Tanrıçası".
                                   # "ebed"in belirtmesi "ebedi" olur ama
                                   # o isim metinde fiilen kullanılmıyor
    "ilahi": "ilahî",              # keşif; şapkalı×13, şapkasız×1 (19).
                                   # "ilah"ın belirtmesi "ilahı"
    "marazi": "marazî",            # keşif; "maraz"ın belirtmesi "marazı"
    "mali": "malî",                # keşif; "mal"ın belirtmesi "malı"
}

GUVENLI = {**DAMAKSIL, **UZUNLUK, **NISBET_GUVENLI}

# --------------------------------------------------------------------
# ELLE: değiştirilmez, yalnızca raporlanır
# --------------------------------------------------------------------

NISBET = {
    "resmi": "resmî",     # resmî (official) ~ resmi (onun resmi)
    "askeri": "askerî",   # askerî (military) ~ askeri (askeri gördü)
    "tarihi": "tarihî",   # tarihî (historical) ~ tarihi (onun tarihi)
    "hayali": "hayalî",   # hayalî (imaginary) ~ hayali (onun hayali)
    "madeni": "madenî",   # madenî (metallic) ~ madeni (madeni işletti)
    "dini": "dinî",       # dinî (religious) ~ dini (onun dini)
    "milli": "millî",
    "ilmi": "ilmî",       # "Ayin İlmi" (iyelik) de buraya düşer
    "mesleki": "meslekî", # meslekî (professional) ~ mesleki (onun mesleki)
}

ESADLI = {
    "hala": "hâlâ",   # hala = teyze/hala
    "hale": "hâle",   # hale = ayla, nur halkası
    "haleye": "hâleye",
    "alem": "âlem",   # alem = bayrak/sancak tepeliği
    "aleme": "âleme",
    "alemin": "âlemin",            # keşif
    "alemi": "âlemi",
    "adet": "âdet",   # adet = sayı
    "adeti": "âdeti",
    "adetleri": "âdetleri",
    "kar": "kâr",     # kar = yağan kar
    # hakim: hâkim (hükmeden) ~ hakîm (bilge). Eskiden DAMAKSIL'deydi, yani
    # --uygula "bilge" anlamındaki bir "hakim"i de "hâkim" yapardı; lint ise
    # aynı kelimeyi diyakritik_ciftleri'nde belirsiz sayıyordu.
    "hakim": "hâkim",
    "hakimi": "hâkimi",
    "hakimdi": "hâkimdi",          # keşif; 15. bölüm "esinti hakimdi"
    "hakimdir": "hâkimdir",
}

# --------------------------------------------------------------------

TR_HARF = "A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîûÊê"
_KELIME = re.compile(rf"[{TR_HARF}]+")
_SAPKA = str.maketrans("âîûÂÎÛ", "aiuAIU")

# Her grubun birleşimi; bicimler() hedefi buradan okur. Eskiden KAYIT
# bakılan gruplarda yoktu ve "lazım" için hedef None dönüyordu.
TUM = {**GUVENLI, **NISBET, **ESADLI, **KAYIT}


# --------------------------------------------------------------------
# Sözlük koruması
# --------------------------------------------------------------------

_PARANTEZ = re.compile(r"\(([^)]*)\)")
_MADDE = re.compile(r"^\s*-\s*\*\*(.+?)\*\*")


def sozluk_adlari(yol=None, kelimeler=None) -> list:
    """
    Sözlükteki bütün Türkçe adlar: terim (parantez içi dahil, ayrı ad
    olarak), arama_adi, mertebe adları; kelimeler verilirse words.md'nin
    kalın yazılmış maddeleri de.
    """
    adlar = []
    if yol:
        try:
            import yaml
        except ImportError:
            sys.exit("--sozluk için PyYAML gerekli:  pip install pyyaml")
        veri = yaml.safe_load(Path(yol).read_text(encoding="utf-8")) or []
        for g in veri:
            if not isinstance(g, dict):
                continue
            adlar.append(str(g.get("terim") or ""))
            adlar += [str(a) for a in g.get("arama_adi") or []]
            for m in g.get("mertebeler") or []:
                if isinstance(m, dict):
                    adlar.append(str(m.get("isim") or ""))
    if kelimeler:
        for satir in Path(kelimeler).read_text(encoding="utf-8").splitlines():
            m = _MADDE.match(satir)
            if m:
                adlar.append(m.group(1))
    out = []
    for ad in adlar:
        out.append(_PARANTEZ.sub(" ", ad))
        out += _PARANTEZ.findall(ad)
    return [a for a in out if a.strip()]


def sozluk_yazimlari(adlar) -> dict:
    """{şapkasız küçük biçim: {sözlükteki küçük yazım(lar)}}"""
    yazim = defaultdict(set)
    for ad in adlar:
        for k in _KELIME.findall(ad):
            kk = tr_kucult(k)
            yazim[kk.translate(_SAPKA)].add(kk)
    return yazim


def sozluge_gore(sozluk: dict, yazimlar: dict):
    """
    Listedeki (şapkasız -> şapkalı) çiftlerin YÖNÜNÜ sözlüğe göre belirler.

    Doner: (ileri, geri, celisen)
      ileri    sözlükte geçmiyor ya da sözlük şapkalı yazıyor: olduğu gibi
      geri     sözlük ŞAPKASIZ yazıyor: {şapkalı: şapkasız}, tersine uygulanır
      celisen  sözlük kelimeyi iki (ya da başka bir) yazımla yazıyor: dokunulmaz
    """
    ileri, geri, celisen = {}, {}, {}
    for k, v in sozluk.items():
        var = yazimlar.get(tr_kucult(k).translate(_SAPKA))
        if not var or var == {tr_kucult(v)}:
            ileri[k] = v
        elif var == {tr_kucult(k)}:
            geri[v] = k
        else:
            celisen[k] = v
    return ileri, geri, celisen


# --------------------------------------------------------------------
# Sözlük göçü
# --------------------------------------------------------------------

AD_ALANLARI = {"terim", "isim", "arama_adi"}
DUZYAZI_ALANLARI = {"aciklama", "cevirmen_notu", "cevirmen_notu_ek", "cevirmen_notu_sinir"}
DOKUNULMAZ = {"eski_karsiliklar", "ingilizce", "cince"}
_YML_ANAHTAR = re.compile(r"^(\s*)(-\s+)?([A-Za-z_]+):(\s*)(.*)$")
_YML_OGE = re.compile(r"^(\s*)-\s+(.*)$")


def sozluk_yml_gocu(metin: str, sozluk: dict, duzyazi: bool = False) -> tuple:
    """
    sozluk.yml METNİNİ satır satır taşır. Yalnızca izinli alanların değerleri
    değişir; başka her karakter yerinde kalır.

    İki çok satırlı biçim izlenir:
      liste     "arama_adi:" ardından "- x" satırları. Sözlük offset=0 ile
                yazıldığı için tire ANAHTARLA AYNI hizada olabilir.
      blok dize "aciklama: >-" ardından daha içeride duran satırlar.

    Doner: (yeni metin, [(satır no, eski satır, yeni satır)])
    """
    izinli = AD_ALANLARI | (DUZYAZI_ALANLARI if duzyazi else set())
    out, degisen = [], []
    blok = None  # (anahtar, anahtarın boşluk girintisi, "liste" | "dize")
    for no, satir in enumerate(metin.split("\n"), 1):
        yeni = satir
        m = _YML_ANAHTAR.match(satir)
        bosluk = len(satir) - len(satir.lstrip(" "))
        if blok and satir.strip():
            anahtar, kg, tur = blok
            devam = (tur == "dize" and bosluk > kg) or (
                tur == "liste" and m is None and _YML_OGE.match(satir) and bosluk >= kg)
            if devam:
                if anahtar in izinli:
                    yeni = _cevir(satir, sozluk)[0]
            else:
                blok = None
        if not (blok and satir.strip()) and m:
            anahtar, deger = m.group(3), m.group(5)
            if anahtar in izinli and deger and deger not in (">", ">-", "|", "|-"):
                yeni = satir[: len(satir) - len(deger)] + _cevir(deger, sozluk)[0]
            if deger in (">", ">-", "|", "|-", ">+", "|+"):
                blok = (anahtar, bosluk, "dize")
            elif not deger and anahtar in (AD_ALANLARI | DOKUNULMAZ | DUZYAZI_ALANLARI):
                blok = (anahtar, bosluk, "liste")
        if yeni != satir:
            degisen.append((no, satir, yeni))
        out.append(yeni)
    return "\n".join(out), degisen


def _yapi_farki(eski, yeni, izinli, yol=()):
    """İki ayrıştırılmış YAML ağacı arasında İZİNSİZ farkların listesi."""
    if isinstance(eski, dict) and isinstance(yeni, dict):
        if list(eski) != list(yeni):
            return [yol]
        return [f for k in eski for f in _yapi_farki(eski[k], yeni[k], izinli, yol + (k,))]
    if isinstance(eski, list) and isinstance(yeni, list):
        if len(eski) != len(yeni):
            return [yol]
        return [f for i, (a, b) in enumerate(zip(eski, yeni))
                for f in _yapi_farki(a, b, izinli, yol + (i,))]
    if eski == yeni:
        return []
    anahtar = next((k for k in reversed(yol) if isinstance(k, str)), None)
    return [] if anahtar in izinli and isinstance(eski, str) else [yol]


def sozluk_gocu(yol, kelimeler, sozluk: dict, uygula_: bool, duzyazi: bool) -> int:
    """sozluk.yml ve words.md'yi taşır; kuru çalıştırmada yalnız gösterir."""
    toplam = 0
    if yol:
        import yaml
        eski = Path(yol).read_text(encoding="utf-8")
        yeni, degisen = sozluk_yml_gocu(eski, sozluk, duzyazi)
        izinli = AD_ALANLARI | (DUZYAZI_ALANLARI if duzyazi else set())
        fark = _yapi_farki(yaml.safe_load(eski), yaml.safe_load(yeni), izinli)
        if fark:
            print(f"DURDURULDU: {yol} izinli alanların dışında değişti: {fark[:5]}")
            return 1
        _goster(Path(yol).name, degisen)
        toplam += len(degisen)
        if uygula_ and degisen:
            atomik_yaz(yol, yeni)
    if kelimeler:
        eski = Path(kelimeler).read_text(encoding="utf-8")
        yeni_satirlar = [s if korunan else _cevir(s, sozluk)[0]
                         for s, korunan in zip(eski.split("\n"), _dondurulmus(eski))]
        degisen = [(i, a, b) for i, (a, b) in enumerate(zip(eski.split("\n"), yeni_satirlar), 1)
                   if a != b]
        _goster(Path(kelimeler).name, degisen)
        toplam += len(degisen)
        if uygula_ and degisen:
            atomik_yaz(kelimeler, "\n".join(yeni_satirlar))
    print(f"\n{'═' * 72}\n{toplam} satır "
          + ("yazıldı. Diff'i okuyun:  git diff" if uygula_ else "değişecek. Yazmak için:  --uygula"))
    return 0


_BOLUM_BASLIGI = re.compile(r"^#\s")


def _dondurulmus(metin: str) -> list:
    """
    words.md'nin her satiri icin: dokunulmaz mi? "Frozen Lines" bolumu
    (rubai dahil) ve "dondurulmuş" diye isaretli her madde, harfi harfine
    korunur: yayimlanmis satirlarin aynisidir, sapka listesi bile
    degistiremez.
    """
    out, bolumde = [], False
    for satir in metin.split("\n"):
        if _BOLUM_BASLIGI.match(satir):
            bolumde = "frozen" in satir.lower() or "dondurulmu" in satir.lower()
        out.append(bolumde or "dondurulmuş" in satir)
    return out


def _goster(ad, degisen):
    if not degisen:
        return
    print(f"\n{'─' * 72}\n{ad}: {len(degisen)} satır\n{'─' * 72}")
    for no, a, b in degisen:
        print(f"  {no:>5}  - {a.strip()}\n         + {b.strip()}")


# --------------------------------------------------------------------
# Keşif
# --------------------------------------------------------------------

def kesfet(dosyalar: dict) -> list:
    """
    Aynı kelimenin hem şapkalı hem şapkasız geçtiği çiftler.

    Doner: [(sapkasiz, sapkali, n_sapkasiz, n_sapkali, bolum_sayisi, listede)]
    toplam geçişe göre büyükten küçüğe. Küçük harfe indirilmiş olarak
    karşılaştırılır; bicimler() baş harfi büyük hâli zaten kapsar.
    """
    sayim, nerede = Counter(), defaultdict(set)
    for ad, metin in dosyalar.items():
        for k in _KELIME.findall(metin):
            kk = tr_kucult(k)
            sayim[kk] += 1
            nerede[kk].add(ad)
    out = []
    for kk, n in sayim.items():
        duz = kk.translate(_SAPKA)
        if duz == kk or duz not in sayim:
            continue
        out.append((duz, kk, sayim[duz], n, len(nerede[duz] | nerede[kk]), duz in TUM))
    return sorted(out, key=lambda t: -(t[2] + t[3]))


def kesif_yaz(ciftler: list):
    yeni = [c for c in ciftler if not c[5]]
    eski = [c for c in ciftler if c[5]]
    print(f"\n{'─' * 72}\nKEŞİF — aynı kelime iki yazımla ({len(ciftler)} çift)\n{'─' * 72}")
    if yeni:
        print("\n  Listede YOK (yön ve grup kararı sizin; -î ile bitenler eşadlı mı?):\n")
        for duz, sapkali, nd, ns, nb, _ in yeni:
            not_ = "   # nisbet: eşadlı mı?" if sapkali.endswith("î") else ""
            print(f'    "{duz}": "{sapkali}",   # şapkalı×{ns}, şapkasız×{nd}, '
                  f'{nb} bölüm{not_}')
    if eski:
        print("\n  Listede var, ikisi de hâlâ metinde:\n")
        for duz, sapkali, nd, ns, nb, _ in eski:
            print(f"    {duz} ×{nd}  /  {sapkali} ×{ns}   ({nb} bölüm)")


def desen(kelime: str) -> re.Pattern:
    """
    Tam kelime eşleşmesi.

    '\\b' KULLANILMAZ: Python'da '_' bir kelime karakteridir, dolayısıyla
    markdown italik işaretine bitişik bir kelime ('_hâlâ') '\\b' ile
    yakalanmaz. Klein'ın iç sesi baştan sona italik olduğu için bu, tam da
    en çok geçtiği yerde kör kalmak demekti.
    """
    return re.compile(rf"(?<![^\W_]){re.escape(kelime)}(?![^\W_])")


def _cevir(metin: str, sozluk: dict) -> tuple:
    """Listeyi bir metne uygular; (yeni metin, değişiklik sayısı)."""
    toplam = 0
    for kelime in sozluk:
        for aranan, yazilacak in bicimler(kelime, sozluk[kelime]):
            metin, n = desen(aranan).subn(yazilacak, metin)
            toplam += n
    return metin, toplam


def cevir_belge(metin: str, sozluk: dict) -> tuple:
    """
    _cevir gibi, ama ORNEK satirlarina dokunmaz: iki yazimi birden tasiyan
    satir (istemde '"resmi üye" -> "resmî üye"', tabloda 'pekala | pekâlâ')
    bir ornektir ve "duzeltmek" onu yok eder. Bolumlerde bu koruma yok:
    orada iki yazimin ayni paragrafta gecmesi tutarsizliktir.
    """
    ciftler = [(desen(aranan), desen(yazilacak), yazilacak)
               for kelime in sozluk
               for aranan, yazilacak in bicimler(kelime, sozluk[kelime])]
    out, toplam = [], 0
    for satir in metin.split("\n"):
        for d_aranan, d_yazilacak, yazilacak in ciftler:
            if not d_aranan.search(satir) or d_yazilacak.search(satir):
                continue  # gecmiyor ya da ornek satiri (iki yazim birden)
            satir, n = d_aranan.subn(yazilacak, satir)
            toplam += n
        out.append(satir)
    return "\n".join(out), toplam


def uygulanacak_liste(sozluk_yolu=None, kelimeler=None) -> dict:
    """
    --uygula'nin yazacagi liste: GÜVENLİ gruplar, yonu sozluge gore
    (ileri + tersine); sozlukte iki yazimla gecenler disarida.
    """
    if not (sozluk_yolu or kelimeler):
        return dict(GUVENLI)
    yazimlar = sozluk_yazimlari(sozluk_adlari(sozluk_yolu, kelimeler))
    ileri, geri, _celisen = sozluge_gore(GUVENLI, yazimlar)
    return {**ileri, **geri}


def plan(metinler: dict, liste: dict, belge: bool = False) -> dict:
    """
    {yol: metin} -> {yol: (yeni metin, degisiklik sayisi)}, yalniz degisenler.
    Hicbir sey YAZMAZ; yazmak duzelt.py'nin isi (fark + yedek).
    belge=True: ornek satirlari korunur (istemler, ses haritalari).
    """
    out = {}
    for yol, metin in metinler.items():
        yeni, n = (cevir_belge if belge else _cevir)(metin, liste)
        if n and yeni != metin:
            out[yol] = (yeni, n)
    return out


def bicimler(kelime: str, hedef: str | None = None) -> list[tuple[str, str]]:
    """(aranan, yazılacak) çiftleri -- küçük ve baş harfi büyük hâlleriyle."""
    hedef = hedef or TUM[kelime]
    return [(kelime, hedef), (tr_buyut(kelime), tr_buyut(hedef))]


def tara(dosyalar: dict, sozluk: dict) -> dict:
    """sozluk'teki her biçimin nerede geçtiğini bulur."""
    bulgu: dict = defaultdict(list)
    for kelime in sozluk:
        for aranan, yazilacak in bicimler(kelime, sozluk[kelime]):
            d = desen(aranan)
            for ad, metin in sorted(dosyalar.items()):
                for m in d.finditer(metin):
                    satir = metin.count("\n", 0, m.start()) + 1
                    # Baglam kendi satirinda (paragrafinda) kalir: komsu
                    # paragraftaki bir duzenleme ELLE tabanini bozmasin.
                    bas = max(metin.rfind("\n", 0, m.start()) + 1, m.start() - 45)
                    son = metin.find("\n", m.end())
                    son = min(len(metin) if son < 0 else son, m.end() + 45)
                    ctx = re.sub(r"\s+", " ", metin[bas:son])
                    bulgu[kelime].append((ad, satir, aranan, yazilacak, ctx))
    return bulgu


def uygula(yol: Path, sozluk: dict) -> int:
    metin, toplam = _cevir(yol.read_text(encoding="utf-8"), sozluk)
    if toplam:
        atomik_yaz(yol, metin)
    return toplam


# --------------------------------------------------------------------
# ELLE tabani: okunup "kalsin" denmis gecisler
# --------------------------------------------------------------------
#
# KAYIT / NISBET / ESADLI gruplari her calistirmada ayni yuzlerce gecisi
# getiriyordu (selam, laf, adet...); cogu bilerek sapkasiz. bicim-taban.tsv
# gibi: taban dosyasindaki gecisler bastirilir, yalniz YENI olanlar gorunur.
# Anahtar satir numarasi icermez (dosya, kelime, baglam), yani ust
# paragraflardaki bir duzenleme tabani bozmaz; gecisin kendi cumlesi
# degisirse yeniden gorunur -- dogru olan da bu.

ELLE_GRUPLARI = ("KAYIT", "NISBET", "ESADLI")


def elle_listesi() -> dict:
    return {**KAYIT, **NISBET, **ESADLI}


def _taban_baglami(ctx: str) -> str:
    return re.sub(r"\s+", " ", ctx).strip()


def taban_anahtari(ad: str, aranan: str, ctx: str) -> tuple:
    return (ad, aranan, _taban_baglami(ctx))


def taban_oku(yol) -> set:
    if not yol or not Path(yol).exists():
        return set()
    out = set()
    for satir in Path(yol).read_text(encoding="utf-8").splitlines():
        if not satir.strip() or satir.startswith("#"):
            continue
        parca = satir.split("\t")
        if len(parca) == 3:
            out.add(tuple(parca))
    return out


def taban_yaz(yol, dosyalar: dict) -> int:
    bulgu = tara(dosyalar, elle_listesi())
    satirlar = sorted({taban_anahtari(ad, a, ctx)
                       for v in bulgu.values() for ad, _s, a, _y, ctx in v})
    govde = ("# sapka.py ELLE tabani: okunmus, oldugu gibi kalacak gecisler.\n"
             "# dosya<TAB>aranan<TAB>baglam. Elle silinebilir; yeniden uretmek:\n"
             "#   ./calistir.sh sapka-taban\n"
             + "".join("\t".join(t) + "\n" for t in satirlar))
    atomik_yaz(yol, govde)
    return len(satirlar)


def tabandan_suz(bulgu: dict, taban: set) -> tuple:
    """(suzulmus bulgu, bastirilan sayi)"""
    if not taban:
        return bulgu, 0
    out, bastirilan = defaultdict(list), 0
    for kelime, kayitlar in bulgu.items():
        for k in kayitlar:
            if taban_anahtari(k[0], k[2], k[4]) in taban:
                bastirilan += 1
            else:
                out[kelime].append(k)
    return out, bastirilan


def yaz_bolum(baslik: str, bulgu: dict, ornek: int = 2):
    if not bulgu:
        return
    print(f"\n{'─' * 72}\n{baslik}\n{'─' * 72}")
    for kelime in sorted(bulgu, key=lambda k: -len(bulgu[k])):
        kayitlar = bulgu[kelime]
        hedef = next((y for _a, _s, a, y, _c in kayitlar if a == kelime),
                     kayitlar[0][3])
        dosya_sayisi = len({k[0] for k in kayitlar})
        print(f"\n  {kelime} → {hedef}   "
              f"({len(kayitlar)} yerde, {dosya_sayisi} bölüm)")
        for ad, satir, _a, _y, ctx in kayitlar[:ornek]:
            print(f"     {ad}:{satir}  … {ctx.strip()} …")
        if len(kayitlar) > ornek:
            print(f"     … {len(kayitlar) - ornek} tane daha")


def main() -> int:
    ap = argparse.ArgumentParser(description="Şapka tekleştirici")
    ap.add_argument("bolumler", nargs="*")
    ap.add_argument("--uygula", action="store_true",
                    help="dosyaları gerçekten değiştir (varsayılan: kuru)")
    ap.add_argument("--elle", action="store_true",
                    help="yalnızca elle bakılacakları listele")
    ap.add_argument("--kesif", action="store_true",
                    help="iki yazımla geçen kelimeleri listele (listeye aday)")
    ap.add_argument("--sozluk", default=None,
                    help="sozluk.yml; sözlükte geçen kelimenin yazımını sözlük belirler")
    ap.add_argument("--kelimeler", default=None,
                    help="words.md; kalın maddeleri de sözlük gibi sayılır")
    ap.add_argument("--sozluk-gocu", action="store_true", dest="gocu",
                    help="listeyi sözlük dosyalarının kendisine uygula (ileri yönde)")
    ap.add_argument("--taban", default=None,
                    help="ELLE tabanı (lint/sapka-taban.tsv): içindeki geçişler bastırılır")
    ap.add_argument("--taban-yaz", dest="taban_yaz", default=None,
                    help="şimdiki bütün ELLE geçişlerini tabana yaz ve çık")
    ap.add_argument("--denetle", action="store_true",
                    help="kuru; GÜVENLİ değişiklik bekliyorsa çıkış 1 (kanca için)")
    ap.add_argument("--duzyazi", action="store_true",
                    help="göçte aciklama / cevirmen_notu da taşınsın")
    a = ap.parse_args()

    if a.gocu:
        if not (a.sozluk or a.kelimeler):
            ap.error("--sozluk-gocu için --sozluk ve/veya --kelimeler gerekli")
        return sozluk_gocu(a.sozluk, a.kelimeler, GUVENLI, a.uygula, a.duzyazi)
    if not a.bolumler:
        ap.error("bölüm dosyası verilmedi")

    yollar = [Path(y) for y in a.bolumler]
    dosyalar = {p.name: p.read_text(encoding="utf-8") for p in yollar}

    if a.kesif:
        kesif_yaz(kesfet(dosyalar))
        return 0
    if a.taban_yaz:
        n = taban_yaz(a.taban_yaz, dosyalar)
        print(f"{n} ELLE geçişi tabana yazıldı: {a.taban_yaz}")
        return 0
    taban = taban_oku(a.taban)

    uygulanacak, geri = dict(GUVENLI), {}
    if a.sozluk or a.kelimeler:
        yazimlar = sozluk_yazimlari(sozluk_adlari(a.sozluk, a.kelimeler))
        uygulanacak, geri, celisen = sozluge_gore(GUVENLI, yazimlar)
        yaz_bolum("SÖZLÜKTE İKİ YAZIM — önce sözlüğü tekleştirin (dokunulmadı)",
                  tara(dosyalar, celisen), ornek=2)
        yaz_bolum("SÖZLÜĞE GÖRE TERSİNE — sözlük şapkasız yazıyor",
                  tara(dosyalar, geri), ornek=2)

    if not a.elle:
        yaz_bolum("GÜVENLİ — DAMAKSILLAŞMA (k/g/l)",
                  tara(dosyalar, {k: v for k, v in DAMAKSIL.items() if k in uygulanacak}))
        yaz_bolum("GÜVENLİ — ARAPÇA ALINTILARDA UZUNLUK",
                  tara(dosyalar, {k: v for k, v in UZUNLUK.items() if k in uygulanacak}))
        yaz_bolum("GÜVENLİ — EŞADLISI OLMAYAN NİSBET -î",
                  tara(dosyalar, {k: v for k, v in NISBET_GUVENLI.items() if k in uygulanacak}))

    bastirilan = 0
    for baslik, grup in (
            ("ELLE — KAYIT KARARI  (şapka doğru, ama kelime günlük dilden)", KAYIT),
            ("ELLE — NİSBET -î  (anlam ayırır, otomatik değiştirilmez)", NISBET),
            ("ELLE — EŞADLI  (her geçiş ayrı okunmalı)", ESADLI)):
        bulgu, n = tabandan_suz(tara(dosyalar, grup), taban)
        bastirilan += n
        yaz_bolum(baslik, bulgu, ornek=3)
    if bastirilan:
        print(f"\n  (ELLE: {bastirilan} geçiş tabanda, gösterilmedi)")

    if a.elle:
        return 0

    uygulanacak = {**uygulanacak, **geri}
    guvenli_sayi = sum(len(v) for v in tara(dosyalar, uygulanacak).values())
    print(f"\n{'═' * 72}")
    if not a.uygula:
        print(f"{guvenli_sayi} güvenli değişiklik bulundu. "
              f"Yazmak için:  ./calistir.sh duzelt sapka --uygula")
        return 1 if (a.denetle and guvenli_sayi) else 0

    toplam = 0
    for p in yollar:
        n = uygula(p, uygulanacak)
        if n:
            print(f"  {p.name}: {n}")
            toplam += n
    print(f"\n{toplam} değişiklik yazıldı. "
          f"Diff'i okuyun:  git diff")
    return 0


if __name__ == "__main__":
    sys.exit(main())
