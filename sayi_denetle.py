#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sayi_denetle.py -- Çincedeki sayı/para miktarı Türkçede karşılıksız mı?

Makine çevirisinin klasik hatası: "yedi peni" -> "sekiz peni", 1349 -> 1348,
"on iki" -> "on". Şimdiye dek bunu yalnız model okuması yakalıyordu.

Ölçüt: ZH'deki bir MİKTARIN değeri, grubun ve komşu grupların (PENCERE: p-2..p+2)
TR metninde hiçbir sayı olarak geçmiyorsa bulgu. Pencere şart: hizalama bazı
bölümlerde bir iki paragraf kayıyor (5. bölüm: ZH ¶43 = TR ¶44).

Miktar = yalnız sayısal bağlamdaki sayı (Çincede 一/十/万 sayısız sözcüğün içinde):
  para   sayı + 镑/金镑/苏勒/便士 (Arap ya da Çin rakamı)
  rakam  Arap rakamıyla yazılmış her sayı (yıl, kapı no, kart no ...)
  tarih  sayı + 年/月/日/号 ("六月" için Türkçe ay adı da sayılır)
  saat   sayı + 点 (yalnız 半/钟/整/分 ya da rakamla devam ediyorsa)
  yas    sayı + 岁
  sira   第N, 序列N (ordinal TR'de aynı sayı sayılır: "ikinci")
  sayi   sayı + ölçü sözcüğü (个/张/位/次/天/小时/米 ...)
  ters   (yalnız --tur ters) TR'de rakamla yazılmış ya da para birimli sayı,
         ZH penceresinde yok. Varsayılan çıktıya girmez.

Eşleştirme: her TR sayısı en çok BİR ZH miktarını karşılar (7 peni ... 7 peni
iki kez geçiyorsa TR'de de iki kez aranır); para değeri yalnızca bir para
birimi (Sterlin/soli/peni) geçen cümledeki sayılardan aranır, öbürleri pencerede
başka yerde geçen aynı sayıya takılmasın diye. Serbest ama doğru karşılıklar
kabul edilir: 五点 = 17:40, 六月 = Haziran, 三十分钟 = yarım saat, 120分钟 = iki saat,
乔治三世 = III. George (Romen rakamı).

Kasıtlı olarak SAYILMAYANLAR (sebep: serbest çeviri, kesinlik düşer):
  * Değeri 1 (Çincede 一 ve Türkçede "bir" çoğu kez tanımlık; "1苏勒" dahil).
  * Ölçü sözcüğüyle gelen 2 ve (人/位/名 için) 3: "ikisi", "ikili", "kardeşler",
    "aralarında", "çift" gibi serbest karşılıklar yüzünden gürültü (1–73'te
    bu eşik 27 bulguyu 7'ye indiriyor, farkın tamamı serbest çeviri).
  * 第二天 ("ertesi gün"), 世 (hükümdar sırası, TR'de sonraki anışlarda düşüyor).
  * Yaklaşıklık: üst üste rakamlar (三四次, 两三个, 四五十), 几/多/余/来/数
    (十几, 二十多, 数百), 左右/上下.
  * Kesirler ve özel karşılıklar: 半, 一刻钟 (çeyrek), 一打 (düzine), 双/对 (çift),
    百分之N, 分之; hafta (周: 四周 "çevre" olabilir), 点 olarak "puan"
    (三点一线); 1,5 gibi ondalıklar; para birimi dönüşümleri (25 peni = 2 soli 1 peni).
  * Sayı olmayan sözcükler (十分, 万一, 千万, 百姓, 乱七八糟 ...): sayı yalnızca
    birim/ölçü sözcüğü ya da 第/序列 önekiyle gelirse miktar sayılır; bu yüzden
    liste kısa (DURDUR) ve yalnız birimi tutan kalıpları kapsıyor.
  * TR'de sayı, çoğu yerde "var" sayılır: belirsiz biçimler (altı = "altı/alt",
    ikisi, yüz) sayı kabul edilir. Yanlışlıkla "var" saymak gerçek bulguyu
    gizler, yanlışlıkla "yok" saymak gürültü üretir; hizalama zaten gürültülü
    olduğundan kesinlik için "var" yönünde cömert davranılır. Sınırı: pencerede
    aynı değerde başka bir sayı varsa değişiklik gizlenir (ölçüm: sentetik
    bozmaların yaklaşık beşte dördü yakalanıyor).

Rapor adımıdır; çıkış kodu bulgu olsa da 0, kullanım hatasında 1.

Kullanim:
    sayi_denetle.py 63              tek bolum
    sayi_denetle.py 55-64           aralik (sonda bolum basina ozet); 55,58,60-64 de olur
    sayi_denetle.py 5 --tur para,rakam     yalniz bu turler
    sayi_denetle.py 5 --ayrinti     her bulgu icin uzun baglam
"""

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "harita"))

import lotm  # noqa: E402
from gruplar import gruplar  # noqa: E402
from turkce import tr_kucult  # noqa: E402

PENCERE = 2  # p-2 .. p+2 gruplarinin TR'sine bakilir
# Olcu sozcuguyle gelen kucuk sayilar (iki kisi, iki adim) serbest cevrilir:
SAYI_ALT = 3    # "sayi" turunde bundan kucuk deger sayilmaz
INSAN_ALT = 4   # 人/位/名 icin (kardesler, ikili, ikisi...)

TURLER = ("para", "rakam", "tarih", "saat", "yas", "sira", "sayi", "ters")
VARSAYILAN_TURLER = ("para", "rakam", "tarih", "saat", "yas", "sira", "sayi")

# Sayi gibi gorunen ama sayi olmayan kaliplar (birim kosulu zaten eler; bu
# liste birim kosulunu atlatan nadir durumlar icin).
DURDUR = (r"十分(?!钟)", r"万分", r"千万", r"万一", r"百姓", r"三三两两", r"乱七八糟",
          r"七上八下", r"五颜六色", r"四周", r"第一时间", r"三长两短", r"一五一十",
          r"十全十美", r"三桅", r"十字", r"万物", r"五官")


@dataclass(frozen=True)
class Bulgu:
    p: int          # grup numarasi
    tur: str        # para / rakam / tarih / saat / yas / sira / sayi / ters
    belirtec: str   # Cincedeki (ters icin Turkcedeki) sayi metni, birimiyle
    deger: int
    zh: str         # Cince baglam
    tr: str         # Turkce baglam
    aralik: tuple = ()  # bakilan pencere (ilk ¶, son ¶)


# =====================================================================
# CINCE: miktar cikarma
# =====================================================================

_RAKAM = "一二两三四五六七八九"
_CN = "零〇一二两三四五六七八九十百千万亿"
_CN_DEG = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9}
_YER = {"十": 10, "百": 100, "千": 1000}

_TOKEN = re.compile(r"\d+(?:[-–]\d+)+|\d+(?:[.,]\d+)*|[" + _CN + r"]+")

# Birim onekleri/sonlari (uzun olan once).
_PARA = r"(?:铜便士|便士|苏勒|金镑|英镑|镑)"
_OLCU = (r"(?:分钟|小时|钟头|个|名|位|张|枚|条|只|头|次|天|秒|米|公里|里|英里|码|英尺|英寸|"
         r"公斤|磅|人|件|本|把|块|杯|瓶|层|级|阶|步|道|种|家|间|栋|颗|根|座|辆|部|封|份|倍|"
         r"遍|回|趟|场|批|套|页|段|片|圈|轮|口|句|声|条|周年|星期|夜|岁|年|月|日|号|点|发|楼)")

_YAKLASIK_ONCE = "几数多余近"
_YAKLASIK_SONRA = re.compile(r"^(?:[几多余来]|左右|上下)")


def _cn_deger(s: str):
    """Cince rakam dizisi -> int (万/亿 destekli). Gecersizse None."""
    if len(s) >= 3 and all(c in _CN_DEG for c in s) and s[0] not in "零〇":
        return int("".join(str(_CN_DEG[c]) for c in s))  # 一一八四年: rakam rakam okunan yil
    if not s or s[0] in "百千万亿" or any(a in "十百千" and b in "十百千" for a, b in zip(s, s[1:])):
        return None
    # ardisik rakamlar (三四, 一二三) yaklasiklik ya da rakam rakam okuma
    for a, b in zip(s, s[1:]):
        if a in _RAKAM and b in _RAKAM:
            return None
    if "亿" in s:
        sol, _, sag = s.partition("亿")
        a = _cn_deger(sol) if sol else 1
        b = _cn_deger(sag) if sag else 0
        return None if a is None or b is None else a * 10**8 + b
    if "万" in s:
        sol, _, sag = s.partition("万")
        a = _cn_deger(sol) if sol else None
        b = _cn_deger(sag) if sag else 0
        return None if a is None or b is None else a * 10000 + b
    if s in ("零", "〇"):
        return 0
    return lotm.cn_sayi(s)


def _arap_deger(s: str):
    if re.fullmatch(r"\d+(?:[.,]\d{3})+", s):  # 1,250 / 1.250 binlik
        return int(re.sub(r"[.,]", "", s))
    if re.fullmatch(r"\d+[.,]\d+", s):  # ondalik: tam kismi
        return None
    return int(s)


def _bagla(zh: str, bas: int, son: int):
    """Belirtecin cevresine gore (tur, belirtec_sonu) ya da None."""
    once = zh[max(0, bas - 2):bas]
    sonra = zh[son:son + 3]
    if once[-1:] and once[-1] in _YAKLASIK_ONCE:
        return None
    if _YAKLASIK_SONRA.match(sonra):
        return None
    if sonra.startswith("分之") or once.endswith("之"):
        return None
    m = re.match(_PARA, sonra)
    if m:
        return "para", son + m.end()
    if once.endswith("序列") or once[-1:] == "第":
        if zh[son:son + 1] in ("天", "日") and zh[bas:son] in ("二", "两", "2"):
            return None  # 第二天 = "ertesi gun": serbest karsilik
        return "sira", son
    if sonra[:1] == "点":
        if re.search(r"(?:上午|下午|晚上|凌晨|中午|早上|清晨|傍晚|夜里|到|至|从)$", zh[max(0, bas - 2):bas]):
            return "saat", son + 1  # 下午两点, 从九点到十一点: saat bagi acik
        if re.match(r"点(?:半|钟|整|\d+分|[" + _CN + r"]+分)", zh[son:son + 6]):
            return "saat", son + 1
        return None
    if sonra[:1] == "岁":
        return "yas", son + 1
    if sonra[:1] in ("年", "日", "号") or (sonra[:1] == "月"):
        return "tarih", son + 1
    m = re.match(_OLCU, sonra)
    if m:
        return "sayi", son + m.end()
    return None


def cince_miktarlar(zh: str, turler=VARSAYILAN_TURLER) -> list:
    """[(tur, belirtec, deger, konum)] -- zh icindeki sayisal miktarlar."""
    out = []
    durdur = [m.span() for d in DURDUR for m in re.finditer(d, zh)]
    for m in _TOKEN.finditer(zh):
        s = m.group()
        bas, son = m.span()
        if any(a < son and bas < b for a, b in durdur):
            continue
        if re.match(r"\d", s):
            if "-" in s or "–" in s:
                out.append(("rakam", s, -1, bas))
                continue
            deger = _arap_deger(s)
            if deger is not None and zh[son:son + 1] in ("万", "亿"):
                deger *= 10000 if zh[son] == "万" else 10**8
                son += 1
            if deger is None or deger <= 1:
                continue
            if (bas and zh[bas - 1] in _YAKLASIK_ONCE) or _YAKLASIK_SONRA.match(zh[son:son + 2]):
                continue
            b = _bagla(zh, bas, son)
            tur = b[0] if b and b[0] in ("para", "tarih", "saat", "yas", "sira") else "rakam"
            if b and b[0] == "sayi":
                tur = "rakam"
            out.append((tur, zh[bas:b[1] if b else son], deger, bas))
            continue
        deger = _cn_deger(s)
        if deger is None or deger <= 1:
            continue
        b = _bagla(zh, bas, son)
        if not b:
            continue
        # 两人/两个/两步 (2) ve 三人: "ikisi", "ikili", "kardesler", "aralarinda" gibi
        # serbest karsiliklar cok; ölçü sözcüğüyle gelen küçük sayı sayılmaz.
        if b[0] == "sayi" and (deger < SAYI_ALT or (deger < INSAN_ALT and zh[son:son + 1] in "人位名")):
            continue
        out.append((b[0], zh[bas:b[1]], deger, bas))
    return [x for x in out if x[0] in turler]


# =====================================================================
# TURKCE: sayi ayristirma
# =====================================================================

_TEMEL = {
    "bir": 1, "iki": 2, "üç": 3, "dört": 4, "dörd": 4, "beş": 5, "altı": 6, "yedi": 7,
    "sekiz": 8, "dokuz": 9, "on": 10, "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50,
    "altmış": 60, "yetmiş": 70, "seksen": 80, "doksan": 90, "yüz": 100, "bin": 1000,
    "milyon": 10**6,
}
_BAS = (100, 1000, 10**6)

_ORD = r"(?:ıncı|inci|uncu|üncü|ncı|nci|ncu|ncü)"
_DAG = r"(?:şar|şer|ar|er)"
_TUR = r"(?:lık|lik|luk|lük)"
# on / yuz / bin / milyon: zamir ve yuz(yuzu) ile karismamasi icin dar
_EK_DAR = re.compile(r"^(?:|" + _ORD + r"|" + _DAG + r"|" + _TUR + r")$")
_EK_MILYON = re.compile(r"^(?:|" + _ORD + r"|" + _TUR + r"|[dt][ae]n?|[yn]?[ae]|[yn]?[ıiuü])$")
# Oteki sayilar icin ek zinciri serbest (ikisi, yirmi beşindeydi, dördüncüsü ...):
# bu govdelerle baslayip sayi olmayan sozcukler yalniz asagidaki listedir.
_SAYI_DEGIL_RX = re.compile(
    r"^(?:beşik|beşir|ikiz|ikram|ikindi|ikilem|üçgen|üçüz|dörtnala|kırkayak|"
    r"yediğ|yedir|sekizgen|altıgen|dörtgen|beşgen|altın(?!cı)|yediveren|yedek|doksanlı)")
_SAYI_DEGIL = {"binmek", "bini"}

_KOKLER = sorted(_TEMEL, key=len, reverse=True)
_SOZ = re.compile(r"[a-zçğıöşüâîû]+")
_RAKAM_TR = re.compile(r"\d+(?:[.,:]\d+)*")
_AYLAR = {"ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
          "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12}


def _sayi_sozcugu(w: str, onluktan_sonra: bool = False):
    """Tek sözcük -> temel deger ya da None. bir yalniz kendisi (birlikte, biri ...)."""
    if w in _SAYI_DEGIL or _SAYI_DEGIL_RX.match(w):
        return None
    if w == "bir":
        return 1
    if onluktan_sonra and re.fullmatch(r"bir(?:i|le|de|den|e|in|ini|inci|inde|ine)", w):
        return 1  # "on birle gece yarisi": onluktan sonra gelen bir + ek
    for k in _KOKLER:
        if k != "bir" and w.startswith(k):
            ek = w[len(k):]
            if k in ("on", "yüz", "bin"):
                ok = _EK_DAR.match(ek)
            elif k == "milyon":
                ok = _EK_MILYON.match(ek)
            else:
                ok = True
            if ok:
                return _TEMEL[k]
    return None


def _birlestir(degerler: list) -> list:
    """Yan yana sayi sozcuklerinin degerleri -> sayilar. 'on iki' 12, 'iki üç' 2 ve 3.

    Gecerli ardisiklik: basamak sozcugu (yüz/bin/milyon) her seyden sonra gelir;
    yüz'den sonra onluk ya da birlik; onluktan sonra yalniz birlik; bin/milyon'dan
    sonra herhangi biri. Birlikten sonra yalniz basamak sozcugu. Gerisinde yeni sayi."""
    out, toplam, cur, onceki = [], 0, 0, None

    def kapat():
        nonlocal toplam, cur
        if toplam + cur:
            out.append(toplam + cur)
        toplam = cur = 0

    for v in degerler:
        if onceki is not None and v not in _BAS:
            if onceki < 10:
                devam = False
            elif onceki < 100:
                devam = v < 10
            else:
                devam = True
            if not devam:
                kapat()
        if v == 100:
            cur = (cur or 1) * 100
        elif v in (1000, 10**6):
            toplam += (cur or 1) * v
            cur = 0
        else:
            cur += v
        onceki = v
    kapat()
    return out


def _roma(r: str) -> int:
    d = {"I": 1, "V": 5, "X": 10}
    top = 0
    for a, b in zip(r, r[1:] + " "):
        top += -d[a] if b != " " and d[a] < d[b] else d[a]
    return top


def _sayilar_konumlu(metin: str) -> list:
    """[(deger, konum)]: metindeki her sayi olusu, ayri ayri (ayni deger tekrar sayilir).

    Konum, kucultulmus metindeki baslangic indeksidir (tr_kucult uzunlugu korur)."""
    out = [(_roma(m.group(1)), m.start(1)) for m in re.finditer(
        r"(?<![\wçğıöşüÇĞİÖŞÜ])([IVX]{2,5})(?![\wçğıöşüÇĞİÖŞÜ])", metin)]
    t = tr_kucult(metin)
    for m in _RAKAM_TR.finditer(t):
        s = m.group()
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
            out.append((int(s.replace(".", "")), m.start()))
            continue
        for parca in re.split(r"[.,:]", s):
            if parca:
                out.append((int(parca), m.start()))
    # sozcuk dizileri: yalniz bosluk ya da tireyle ayrilmis sayi sozcukleri
    dizi, bas = [], 0
    son_bit = -1
    for m in _SOZ.finditer(t):
        v = _sayi_sozcugu(m.group(), bool(dizi) and 10 <= dizi[-1] < 100)
        ayrac = t[son_bit:m.start()] if son_bit >= 0 else None
        if v is not None and dizi and ayrac is not None and re.fullmatch(r"[ -]", ayrac):
            dizi.append(v)
        else:
            out += [(x, bas) for x in _birlestir(dizi)]
            dizi, bas = ([v], m.start()) if v is not None else ([], 0)
        son_bit = m.end()
    out += [(x, bas) for x in _birlestir(dizi)]
    return out


def turkce_sayi_listesi(metin: str) -> list:
    """Turkce metindeki sayilarin degerleri, olus sirasiyla (tekrarlar korunur)."""
    return [v for v, _ in _sayilar_konumlu(metin)]


def turkce_sayilar(metin: str) -> set:
    """Turkce metindeki sayilarin degerleri (rakam ve yazi). Yorum: bkz. docstring."""
    return set(turkce_sayi_listesi(metin))


_PARA_TR = re.compile(r"(?:sterlin|soli|peni)")
_BIRIM_TR = re.compile(r"\d+(?:[.,:]\d+)*|[a-zçğıöşüâîû]+")


def turkce_para_listesi(metin: str) -> list:
    """Para birimi sozcugu (Sterlin/soli/peni) bulunan CUMLEDEKI sayilar.

    Para degeri YALNIZ bu sayilardan aranir: aksi halde "yedi peni" -> "sekiz peni"
    degisikligi, pencerede baska bir yerde gecen "yedi" yuzunden kacar. Cumle
    siniri yeter: "en fazla dört, kenar semtte altı peni" gibi birimi
    yalniz sona koyan sayimlar da yakalanir."""
    t = tr_kucult(metin)
    konumlu = _sayilar_konumlu(metin)
    secilen = set()
    for c in re.finditer(r"(?:[^.!?…\n]|(?<=\d)\.(?=\d))+", t):
        if _PARA_TR.search(c.group()):
            secilen |= {j for j, (_, ps) in enumerate(konumlu) if c.start() <= ps < c.end()}
    return [konumlu[j][0] for j in sorted(secilen)]


def turkce_para(metin: str) -> set:
    return set(turkce_para_listesi(metin))


def turkce_aylar(metin: str) -> list:
    """Ay adlari (ocak..aralik, ekli de: Haziran'da, temmuz) -> ay numaralari, olus sirasiyla."""
    out = []
    for w in _SOZ.findall(tr_kucult(metin)):
        for ay, no in _AYLAR.items():
            if w == ay or (w.startswith(ay) and len(w) - len(ay) <= 4):
                out.append(no)
                break
    return out


# =====================================================================
# BULGULAR
# =====================================================================


def _kisalt(s: str, bas: int, son: int, onde=14, sonda=18) -> str:
    return "…" + s[max(0, bas - onde):son + sonda].replace("\n", " ") + "…"


def _tr_baglam(zh: str, tr: str, konum: int, tur: str) -> str:
    if not tr:
        return "(TR yok)"
    if tur == "para":
        m = re.search(r"Sterlin|soli|peni", tr)
        if m:
            return _kisalt(tr, m.start(), m.end(), 30, 30)
    orani = int(len(tr) * konum / max(1, len(zh)))
    return _kisalt(tr, orani, orani, 35, 35)


def bulgular(no: int, turler=VARSAYILAN_TURLER) -> list:
    """[Bulgu]: ZH'deki sayisal miktar, TR penceresinde sayi olarak yok.

    Her TR sayisi en cok BIR ZH miktarini karsilar (tuketilir): ayni tutar
    bitisik gruplarda tekrar ediyorsa (7 peni ... 7 peni) birinin eksilmesi
    gizlenmesin."""
    g = gruplar(no, "tr")
    if not g:
        return []
    ham = {p: x.get("TR", "") for p, x in g.items()}
    genel = {p: Counter(turkce_sayi_listesi(t)) for p, t in ham.items()}
    paralar = {p: Counter(turkce_para_listesi(t)) for p, t in ham.items()}
    aylar = {p: Counter(turkce_aylar(t)) for p, t in ham.items()}
    out = []

    def tuket(kaynak, p, deger) -> bool:
        for q in sorted((q for q in range(p - PENCERE, p + PENCERE + 1) if q in kaynak),
                        key=lambda q: abs(q - p)):
            if kaynak[q][deger] > 0:
                kaynak[q][deger] -= 1
                return True
        return False

    for p in sorted(g):
        zh = g[p].get("ZH", "")
        if not zh or not ham[p]:
            continue
        pen = [q for q in range(p - PENCERE, p + PENCERE + 1) if q in g]
        ham_pen = " ".join(ham[q] for q in pen)
        gorulen = set()
        for tur, belirtec, deger, konum in cince_miktarlar(zh, tur_zh(turler)):
            # Ayni grupta ayni deger tekrar ediyorsa (四个角落四份, 序列7及序列7) Turkce
            # tekrarlamayabilir; para disinda yalniz ilki aranir.
            if tur != "para" and (tur, deger) in gorulen:
                continue
            gorulen.add((tur, deger))
            if tur == "rakam" and deger == -1:  # 2-049 gibi kod: yazimiyla ara
                if belirtec in ham_pen:
                    continue
            elif tur == "para":
                if tuket(paralar, p, deger):
                    continue
            elif tur == "tarih" and belirtec.endswith("月") and tuket(aylar, p, deger):
                continue
            elif tur == "saat" and deger < 12 and tuket(genel, p, deger + 12):
                continue  # 五点 -> 17:00 (24 saatli yazim)
            elif tuket(genel, p, deger):
                continue
            if tur == "sayi" and zaman_esdegeri(belirtec, deger, ham_pen,
                                                set().union(*(set(genel[q]) for q in pen))):
                continue
            if tur not in turler:
                continue
            out.append(Bulgu(p, tur, belirtec, deger, _kisalt(zh, konum, konum + len(belirtec)),
                             _tr_baglam(zh, ham[p], konum, tur), (pen[0], pen[-1])))
    if "ters" in turler:
        out += _ters(g, genel)
    return out


def tur_zh(turler):
    return tuple(t for t in turler if t != "ters") or ("para",)


def zaman_esdegeri(belirtec: str, deger: int, tr_pencere: str, sayilar: set) -> bool:
    """30分钟 = yarim saat, 120分钟 = iki saat, 2小时 = 120 dakika: serbest ama dogru karsiliklar."""
    t = tr_kucult(tr_pencere)
    if belirtec.endswith("分钟"):
        if deger in (15, 45) and "çeyrek" in t:
            return True
        if deger % 30 == 0 and ("yarım" in t or "buçuk" in t):
            return True
        return deger % 60 == 0 and deger // 60 in sayilar
    if belirtec.endswith("小时"):
        return deger * 60 in sayilar
    return False


def zh_degerler(zh: str) -> set:
    """ZH'deki HER sayi degeri (birim aranmaksizin, yaklasik ifadelerin parcalari dahil).

    Ters yon icin: TR'deki sayinin Cincede herhangi bir bicimde gecip gecmedigine bakar."""
    out = set()
    for m in _TOKEN.finditer(zh):
        s = m.group()
        if s[0].isdigit():
            out.update(int(x) for x in re.findall(r"\d+", s))
            d = _arap_deger(s) if re.fullmatch(r"\d+(?:[.,]\d+)*", s) else None
            if d is not None:
                out.add(d)
                if zh[m.end():m.end() + 1] == "万":
                    out.add(d * 10000)
            continue
        d = _cn_deger(s)
        if d is not None:
            out.add(d)
        out.update(_CN_DEG[c] for c in s if c in _CN_DEG)
        out.update(_YER[c] for c in s if c in _YER)
        if "半" in zh:
            out.add(30)  # 十点半 -> 10:30
        # "二十三" gibi sayilarda 20/3 parcalari, "三千" gibi 3000
        for a, b in re.findall(r"([" + _RAKAM + r"]?)([十百千])", s):
            out.add(_CN_DEG.get(a, 1) * _YER[b])
    out |= {d + 12 for d in out if 1 <= d <= 12}  # 两点 -> 14:00
    return out


def _ters(g, genel) -> list:
    """TR'de rakamla ya da para birimiyle yazilmis sayi, ZH penceresinde hic yok."""
    out = []
    zh_set = {p: zh_degerler(x.get("ZH", "")) for p, x in g.items()}
    for p in sorted(g):
        tr = g[p].get("TR", "")
        if not tr:
            continue
        pen = [q for q in range(p - PENCERE, p + PENCERE + 1) if q in g]
        zh = set().union(*(zh_set[q] for q in pen))
        adaylar = []
        for m in _RAKAM_TR.finditer(tr):
            if re.fullmatch(r"\d+,\d+", m.group()):
                continue  # ondalik (1,5): ZH'de 一个半 olabilir
            for x in re.split(r"[.,:]", m.group()) if not re.fullmatch(r"\d{1,3}(?:\.\d{3})+", m.group()) \
                    else [m.group().replace(".", "")]:
                if x:
                    adaylar.append((int(x), m.start(), m.group(), "rakam"))
        t = tr_kucult(tr)
        for m in re.finditer(r"(?:sterlin|soli|peni)", t):
            kons = [(v, k) for v, k in _sayilar_konumlu(tr) if m.start() - 40 <= k < m.start()]
            if kons:
                v, k = kons[-1]
                adaylar.append((v, k, tr[k:m.end()], "para"))
        for deger, k, yazi, tur in adaylar:
            if deger <= 1 or deger in zh or deger in (12, 20):  # 12 peni = 1 soli, 20 soli = 1 Sterlin
                continue
            out.append(Bulgu(p, "ters", yazi, deger, "(ZH'de karşılığı yok)",
                             _kisalt(tr, k, k + len(yazi)), (pen[0], pen[-1])))
    return out


# =====================================================================
# CLI
# =====================================================================

bolum_listesi = lotm.bolum_listesi


def _arg(argv):
    nolar, turler, ayrinti = None, VARSAYILAN_TURLER, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--ayrinti":
            ayrinti = True
        elif a == "--tur":
            i += 1
            if i >= len(argv):
                raise ValueError("--tur bir deger ister")
            turler = tuple(x for x in argv[i].split(",") if x)
            kotu = [t for t in turler if t not in TURLER]
            if kotu or not turler:
                raise ValueError(f"bilinmeyen tur: {','.join(kotu) or '(bos)'}; gecerli: {','.join(TURLER)}")
        elif a.startswith("-"):
            raise ValueError(f"bilinmeyen secenek: {a}")
        elif nolar is None:
            nolar = bolum_listesi(a)
        else:
            raise ValueError("birden fazla bolum argumani")
        i += 1
    if nolar is None:
        raise ValueError("bolum numarasi yok")
    return nolar, turler, ayrinti


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        nolar, turler, ayrinti = _arg(argv)
    except ValueError as e:
        print(f"hata: {e}\n{__doc__}")
        return 1
    sayilar = []
    for no in nolar:
        try:
            b = bulgular(no, turler)
            if not b and not gruplar(no, "tr"):
                print(f"=== {no}: Türkçe metin ya da hizalama yok, atlandı")
                sayilar.append((no, 0))
                continue
        except Exception as e:  # eksik/bozuk bolum dosyasi rapor adimini dusurmesin
            print(f"=== {no}: okunamadı, atlandı ({type(e).__name__})")
            sayilar.append((no, 0))
            continue
        sayilar.append((no, len(b)))
        if len(nolar) == 1 or b:
            yon = "TR'deki sayı ZH'de yok" if turler == ("ters",) else "ZH'deki sayı TR'de yok"
            print(f"=== {no}: {len(b)} sayı uyuşmazlığı ({yon})")
        for x in b:
            a, z = x.aralik
            if x.tur == "ters":
                print(f"  ¶{x.p} [ters] {x.belirtec} ({x.deger}) → ZH ¶{a}–{z}'de yok | TR: {x.tr}")
            else:
                print(f"  ¶{x.p} [{x.tur}] {x.belirtec} ({x.deger}) → TR ¶{a}–{z}'te yok"
                      f" | ZH: {x.zh} | TR: {x.tr}")
            if ayrinti:
                g = gruplar(no, "tr")
                print(f"      ZH ¶{x.p}: {g[x.p]['ZH']}")
                for q in range(a, z + 1):
                    if q in g:
                        print(f"      TR ¶{q}: {g[q]['TR']}")
    if len(nolar) > 1:
        print("\nözet: " + ", ".join(f"{n}:{s}" for n, s in sayilar))
    return 0


if __name__ == "__main__":
    sys.exit(main())
