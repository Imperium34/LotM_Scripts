#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
toplu_denetle.py -- ceviri_denetle.py'yi sozlugun TAMAMI icin calistirir.

UST DUZEY SORU: "Hangi terimlerde yayimlanan metin sozlukten sapiyor?"

ceviri_denetle.py tek terim sorar; bu betik ayni soruyu 381 terime birden
sorar ve sonucu ESLESMEME ORANINA gore siralar. Listenin basi
'eski_karsiliklar' geri doldurma sirasidir: kaydi tutulmamis bir karsilik
kullandiginiz yerler.

NEDEN DONGU TERS CEVRILDI
-------------------------
ceviri_denetle.tara() her cagrida (a) butun bolumleri diskten okur,
(b) her bolumu paragraflara boler, (c) Gale-Church hizalamasini yeniden
kurar. Hizalama O(n*m) dinamik programlama; 42 bolum icin kabul edilebilir,
381 terim x 42 bolum icin degil.

Oysa hizalama TERIMDEN BAGIMSIZDIR. Ayni bolum cifti hangi terim icin
hizalanirsa hizalansin ayni sonucu verir. Bu yuzden burada dongu ters:

    her bolum icin BIR KEZ hizala  ->  butun terimleri o hizalamaya sor

42 hizalama, 381*42 degil. Terim basina kalan is yalnizca bir regex
taramasi, ki o da once ham bolum metninde ucuz bir on elemeden geciyor.

HIZALAMA ONBELLEGI
------------------
Hizalama ayrica DISKTE onbelleklenir (.hizalama_onbellek/, LOTM_ONBELLEK ile
degistirilebilir) ve LAZY'dir: bir bolum yalnizca icinde aranan terim gecerse
hizalanir. Anahtar; bolumun iki metni, hizalama kodu (bolum.py,
hizalama_denetle.py, capa.py) ve sozluk dosyalarinin icerigidir. Bir bolumu
duzenlerseniz yalnizca o bolum yeniden hizalanir. --yenile onbellegi siler.

Kullanim:
    toplu_denetle.py                        EN -> TR, butun sozluk
    toplu_denetle.py --kaynak zh            Cinceden (yalnizca cince'si olanlar)
    toplu_denetle.py --bolum 1-42
    toplu_denetle.py --en-az 3              3'ten az gecisi olanlari atla
    toplu_denetle.py --format tsv > kuyruk.tsv
    toplu_denetle.py --ayrinti "Aşkın"      tek terimin eslesmeyenlerini yaz
    toplu_denetle.py --yenile               hizalama onbellegini sil
    toplu_denetle.py --hepsi                tam eslesen terimleri de tabloda goster
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import os
import pickle
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from collections import Counter, defaultdict

import lotm
import bolum as B
import ceviri_denetle as CD
import hizalama_denetle as HD
import capa as _capa
from lotm import gecis_bolumu
import turkce

_CAPA_SOZLUGU = _capa.sozluk_yukle()

# Betik klasorune bagli (orada .gitignore'da). Eskiden cwd'ye gore goreliydi:
# baska bir klasorden calistirmak yeni, bos bir onbellek acip butun
# hizalamalari bastan hesapliyordu.
ONBELLEK_DIZINI = Path(
    os.environ.get("LOTM_ONBELLEK") or lotm.BETIK_KOK / ".hizalama_onbellek"
)


# --------------------------------------------------------------- hizalama


@functools.lru_cache(maxsize=None)
def _kod_izi() -> str:
    """
    Onbellek anahtarinin 'kod ve girdi' kismi.

    Hizalama sozlukten YALNIZCA capa ciftleri (zh, tr) uzerinden etkilenir;
    eski_karsiliklar, notlar, bolum_siniri duzenlemeleri onbellegi bozmaz.
    capa.py'nin kullandigi lotm.desen_kur / zh_desen koddur, o yuzden lotm.py
    de anahtarda.
    """
    h = hashlib.sha1()
    # Bu dosya da: _hizala_bolum burada. Eskiden yalnizca ice aktarilan
    # moduller anahtardaydi; _hizala_bolum degisince onbellek eski
    # sonuclari sessizce vermeye devam ederdi.
    for m in (B, HD, _capa, lotm, turkce):
        h.update(Path(m.__file__).read_bytes())
    h.update(Path(__file__).read_bytes())
    h.update(repr(sorted(_CAPA_SOZLUGU.items())).encode())
    h.update(repr([(z, tr) for z, tr, *_ in _capa.terim_capalari()]).encode())
    return h.hexdigest()


def _hizala_bolum(k_par, h_par, kaynak, hedef):
    """
    Tek bolumun hizalamasi. Doner: (nereye, kayan).
    Saf fonksiyon: surec havuzunda calisabilir.

      nereye  {kaynak paragraf indisi: [hedef paragraf indisleri]}
      kayan   hizalamanin kaydigi kaynak paragraf indisleri

    KAYAN NEDEN GEREKLI: hizalama kaydiginda ESLESMEYEN listesi sessizce
    curur -- terim kaynakta var, karsilik hedefte var, ama ikisi ayni gruba
    dusmedigi icin "eslesmedi" gorunur ve bir ceviri hatasindan ayirt
    edilemez. Turkce'nin paragraf teamulu Cince'ninkinden farkli (anlati ile
    ardindan gelen replik cogu zaman tek paragrafta birlesiyor) ve BU TEAMUL
    KENDI ICINDE DE TUTARLI DEGIL: Bolum 16 birlestiriyor, Bolum 40
    birlestirmiyor. Yani kaynaga bakan hicbir kural bunu onceden bilemez ve
    hizalayici kimi yerde kacinilmaz olarak kayacaktir.
    Cozum kaymayi ortadan kaldirmak degil, KARANTINAYA ALMAK.
    """
    capalar = set(_capa.capa_bul(k_par, h_par, _CAPA_SOZLUGU))
    gruplar = B.hizala(k_par, h_par, capalar)
    nereye, grup_no = {}, {}
    for g, (ia, ib) in enumerate(gruplar):
        for j in ia:
            nereye[j] = ib
            grup_no[j] = g
    # sozluk: capa yer degistirmesi de kayma sinyali sayilir. Eskiden
    # verilmiyordu; hizalama_denetle bir bolumu "kaymis" gosterirken (17,
    # 46, 50) burada o gruplar karantinaya girmiyor, ESLESMEYEN sayiliyordu.
    rapor = HD.bolumu_denetle(
        k_par, h_par, gruplar, k_dil=kaynak, h_dil=hedef, sozluk=_CAPA_SOZLUGU
    )
    supheli = {g for bas, son in rapor["kaymalar"] for g in range(bas, son + 1)}
    kayan = {j for j, g in grup_no.items() if g in supheli}
    return nereye, kayan


def _hizala_is(args):
    return _hizala_bolum(*args)


class HizalanmisBolum:
    """
    Metinler hemen yuklenir; hizalama ilk gerektiginde hesaplanir (ya da
    diskten okunur).
    """

    def __init__(self, no, kaynak, hedef, k_ham, h_ham, k_par, h_par):
        self.no, self.kaynak, self.hedef = no, kaynak, hedef
        self.k_ham, self.k_par, self.h_par = k_ham, k_par, h_par
        self._sonuc = None
        ozet = hashlib.sha1(
            "\0".join((_kod_izi(), kaynak, hedef, k_ham, h_ham)).encode()
        ).hexdigest()
        self._yol = ONBELLEK_DIZINI / f"{kaynak}-{hedef}-{no}-{ozet[:16]}.pkl"

    def diskte_var(self):
        return self._yol.exists()

    def ayarla(self, sonuc):
        self._sonuc = sonuc
        ONBELLEK_DIZINI.mkdir(exist_ok=True)
        gecici = self._yol.with_suffix(".tmp")
        gecici.write_bytes(pickle.dumps(sonuc))
        gecici.replace(self._yol)  # yarim yazilmis dosya kalmasin
        # bu bolumun eski surumlerini temizle
        for eski in self._yol.parent.glob(
            f"{self.kaynak}-{self.hedef}-{self.no}-*.pkl"
        ):
            if eski != self._yol:
                eski.unlink(missing_ok=True)

    @property
    def hizalama(self):
        if self._sonuc is None:
            if self._yol.exists():
                self._sonuc = pickle.loads(self._yol.read_bytes())
            else:
                self.ayarla(
                    _hizala_bolum(self.k_par, self.h_par, self.kaynak, self.hedef)
                )
        return self._sonuc


def hepsini_hizala(onbellek, isci=None):
    """
    Diskte olmayan hizalamalari hesapla (tam tarama icin). Cok eksik varsa
    birden cok cekirdekte; az ise tek surecte (havuz kurmak daha pahali).
    """
    eksik = [b for b in onbellek.values() if not b.diskte_var()]
    if not eksik:
        return
    print(f"{len(eksik)} bolum hizalanacak...", file=sys.stderr)
    if len(eksik) <= 3:
        for b in eksik:
            b.hizalama  # lazy hesaplar ve diske yazar
        return
    isler = [(b.k_par, b.h_par, b.kaynak, b.hedef) for b in eksik]
    with ProcessPoolExecutor(isci) as ex:
        for b, sonuc in zip(eksik, ex.map(_hizala_is, isler)):
            b.ayarla(sonuc)


def hizalama_onbellegi(kaynak: str, hedef: str, aralik):
    """
    Ortak bolumleri yukler. Hizalama LAZY'dir (bkz. HizalanmisBolum).

    Doner: {bolum_no: HizalanmisBolum}
    """
    yukle = {"zh": lotm.bolumler_zh, "en": lotm.bolumler_en, "tr": lotm.bolumler_tr}

    def oku(ad):
        try:
            return lotm.bolum_sozlugu(yukle[ad]())
        except (FileNotFoundError, OSError) as e:
            sys.exit(
                f"{ad.upper()} kaynagi okunamadi: {e}\n"
                f"LOTM_KOK dogru mu? (su an: {lotm.KOK})"
            )

    k_bolumler, h_bolumler = oku(kaynak), oku(hedef)
    ortak = sorted(set(k_bolumler) & set(h_bolumler))
    if aralik:
        ortak = [n for n in ortak if aralik[0] <= n <= aralik[1]]
    if not ortak:
        sys.exit("kaynak ve hedefte ortak bolum yok")

    k_baslik = B.KAYNAKLAR[kaynak][2]
    h_baslik = B.KAYNAKLAR[hedef][2]

    onbellek = {}
    for no in ortak:
        k_ham, h_ham = k_bolumler[no].metin, h_bolumler[no].metin
        onbellek[no] = HizalanmisBolum(
            no,
            kaynak,
            hedef,
            k_ham,
            h_ham,
            B.paragraflar(k_ham, k_baslik),
            B.paragraflar(h_ham, h_baslik),
        )
    print(f"{len(ortak)} bolum yuklendi ({ortak[0]}-{ortak[-1]}).", file=sys.stderr)
    return onbellek


# --------------------------------------------------------------- terimler


def harf_duyarli_mi(t) -> bool:
    """
    Harf duyarliligi TERIM BASINA, kategoriye gore belirlenir.

    Iki hata tipi ayni eksende oturuyor ve tek bir kuresel bayrakla ikisi
    birden cozulmuyor:

      DUYARLI olursa -> kavram terimleri kacar. LotM'un Ingilizcesi
          "mysticism" ve "ritual" gibi kavramlari cogu yerde KUCUK harfle
          yaziyor; sozlukte ise "Mysticism" olarak duruyorlar. Duyarli
          arama bunlari hic bulamaz ve terim taramada YOK gorunur --
          gorunmeyen bir yanlis negatif.

      DUYARSIZ olursa -> Mertebe adlari gurultuye bogulur. Mertebe adlari
          ozel isimdir ve Ingilizcede daima buyuk harfle yazilir, ama
          karsiliklari gunluk kelimelerdir: Judge, Reader, Criminal,
          Demon, Mother, Death. Duyarsiz arama metindeki her "judge"i,
          her "mother"i vurus sayar; "Şeytan / Demon" 1 gecisten 10
          gecise cikar ve dokuzu curuktur.

    Ayrim kategoride: yalnizca 'Temel Kavramlar' ortak isimlerden olusur
    (mysticism, ritual, potion, sequence, divination). Diger her kategori --
    Mertebeler, Ilahlar, Organizasyonlar, Cografya -- ozel isimdir ve
    Ingilizcede daima buyuk harfle yazilir. Ilk surumde olcut 'bool(t.yol)'
    idi, yani yalnizca mertebeler duyarliydi; bu, adi ayni zamanda ortak
    isim olan ILAHLARI acikta biraktigi icin "Ölüm / Death" metindeki her
    "death"i vurus sayiyordu.
    """
    return t.kategori != "Temel Kavramlar"


def sweep_terimleri(
    kaynak: str, hedef: str, en_kisa: int = 4, kelimeler: str = "dahil"
):
    """
    Sozlukten (sorgu, terim, adaylar, duyarli) uretir.

    ceviri_denetle.sozlukten_adaylar() serbest metinle arama yapar; burada
    kayda ZATEN sahibiz, o yuzden dogrudan alanlari kullaniyoruz. Aday
    listesi guncel karsilik + eski_karsiliklar'dir: birincisi "hâlâ
    kullaniliyor mu", ikincisi "geride kaldi mi" sorusunu yanitlar.
    arama_adi verilmisse karsilik olarak O kullanilir -- cok kelimeli ve
    fiilimsi terimlerde ("Şirazesini Yitirmek") degismeyen sey ifadenin
    kendisi degil govdedir ("şiraze").
    """
    # kelimeler: "dahil" (sozluk + words.md), "haric" (yalniz sozluk),
    # "yalniz" (yalniz words.md). words.md maddeleri lotm.kelimeler_yukle'den
    # gelir; kategorileri "words.md › ..." ile baslar.
    sozluk = lotm.sozluk_yukle(kelimeler=(kelimeler != "haric"))
    cikti, atlanan, tekrar = [], 0, set()
    for t in sozluk.terimler:
        kelime_mi = t.kategori.startswith(lotm.KELIME_KATEGORI)
        if kelimeler == "yalniz" and not kelime_mi:
            continue
        sorgu = {"en": t.en, "zh": t.zh, "tr": t.tr}.get(kaynak)
        # Tek karakterlik Cince anahtar aranamaz: 法 (Kanun) 魔法'in, 令
        # (Ferman) 命令'in, 组 (Beşinci Birim'in ikinci bicimi) her "grup"un
        # icinde gecer; Kanun 146 gecisin 130'unu eslesmeyen gosteriyordu.
        # Bu parcalar atilir; hic parca kalmazsa terim atlananlara sayilir.
        # Kose parantezle yazilmis tek karakter (「镑」) kasitlidir, kalir.
        if kaynak == "zh" and sorgu:
            sorgu = (
                "/".join(
                    p for p in sorgu.split("/") if len(p.strip()) > 1 or t.zh_kesin
                )
                or None
            )
        # Ingilizce: en_arama_adi verilmisse metinde ARANAN adlar onlardir
        # (bkz. lotm.Terim). Eskiden yalnizca etiket aranirdi; "Heart and
        # Mind Body" metinde hic gecmedigi icin Dimağ Beden tabloda hic
        # gorunmuyordu. Birden cok ad " / " ile birlestirilir; terimi_tara
        # ayirip her birini arar (etiketin kendisindeki "/" gibi).
        if kaynak == "en" and t.en_arama_adi:
            sorgu = " / ".join(a.strip() for a in t.en_arama_adi if a and a.strip())
        if not sorgu or len(sorgu.strip()) < (1 if kaynak == "zh" else en_kisa):
            atlanan += 1
            continue
        sorgu = sorgu.strip()

        # Tarot Cemiyeti'nde 'terim' kod adi, 'ingilizce' ise uyenin gercek
        # adidir (Yıldız / Leonard Mitchell). Bu yonde taranamaz: Turkce
        # metin de "Leonard Mitchell" diyor, dolayisiyla %100 eslesmeme
        # cikar ve bu bir ceviri hatasi degildir.
        if (
            kaynak == "en"
            and hedef == "tr"
            and t.kategori == "Tarot Cemiyeti"
            and lotm.tr_kucult(sorgu) not in lotm.tr_kucult(t.tr)
        ):
            atlanan += 1
            continue

        anahtar = (t.tr, sorgu)
        if anahtar in tekrar:  # sozlukteki birebir tekrar kayitlar
            continue
        tekrar.add(anahtar)

        if hedef == "tr":
            # GUNCEL ve ESKI karsiliklar ayri tutulur. arama_adi ayni
            # karsiligin cekim varyantlaridir ("gökkubbe", "yıldızlı
            # gökkubbe"), eski_karsiliklar ise BASKA bir kelimedir
            # ("ritüel" -> "ayin"). Ikisi tek listede toplanirsa
            # "birden fazla karsilik var" uyarisi, terkedilmis bir
            # karsilik ile ayni kelimenin iki yazilisini ayirt edemez.
            guncel = t.tr_bicimleri()
            eski = list(t.eski_karsiliklar or [])
            adaylar = guncel + eski
        elif hedef == "en":
            adaylar = [t.en] if t.en else []
        else:
            adaylar = [t.zh] if t.zh else []
        adaylar = list(dict.fromkeys(a for a in adaylar if a))
        if adaylar:
            cikti.append(
                (
                    sorgu,
                    t,
                    adaylar,
                    harf_duyarli_mi(t),
                    set(eski) if hedef == "tr" else set(),
                )
            )
    return cikti, atlanan


# --------------------------------------------------------------- tarama


def kaynak_deseni(sorgu, kaynak, duyarsiz, haric=None):
    """
    Terimin kaynak dildeki arama deseni. terimi_tara ile Cince bilesik
    ipucu (bkz. ceviri_denetle.zh_bilesik_ipuclari) AYNI deseni kullanmali;
    ipucu desenin bulmadigi bir gecise bakarsa sozlukte zaten kayitli
    bilesikleri de "eksik" diye raporlar.

    haric: terimin kendi {hariç: ...} dizileri (bkz. lotm.denetim_etiketi);
    yalnizca Cincede anlamlidir, cunku Cince desen kelime siniri tanimaz.
    """
    if kaynak in ("en", "zh"):
        # "A / B" -> A veya B. words.md'nin Cince alani da boyle gelebilir
        # ("印章/盖章"). Hem en_arama_adi listesi hem etiketin kendi
        # "/" alternatifleri ("Historical Void / Fog of History"); eskiden
        # butun dize tek parca aranip hic bulunmuyordu.
        #
        # desen_kur_kaynak EN icin "sorgu.islower()" ise kendiliginden
        # IGNORECASE aciyor. Duyarli istedigimizde bunu geri almak gerekiyor,
        # aksi hâlde kucuk harfli bir Mertebe adi sessizce duyarsiz taraniyor;
        # bayrak bu yuzden tek tek desenlerden degil duyarsiz'dan gelir.
        parcalar = [p.strip() for p in sorgu.split("/") if p.strip()]
        return re.compile(
            "|".join(
                f"(?:{CD.desen_kur_kaynak(p, kaynak, duyarsiz, haric if kaynak == 'zh' else None).pattern})"
                for p in parcalar
            ),
            re.IGNORECASE if duyarsiz else 0,
        )
    return CD.desen_kur_kaynak(sorgu, kaynak, duyarsiz)


def mertebe_isaret_deseni(desen):
    """
    Cince bir Mertebe adinin kaynakta Mertebe olarak ISARETLENDIGI yerler:
    tirnak icinde (‘占卜家’, “愚者”), 序列/序列9'dan hemen sonra ya da
    途径/魔药/序列'den hemen once.

    Mertebe adlarinin cogu gundelik kelimedir: 错误 Kusur, 痛苦 Maraz,
    疯子 Meczup, 黑暗 Karanlık. "这一定是错误的" Mertebe degil, "yanlış"tir
    ve Turkcede de oyle cevrilir (2026-10-23 karari: salahiyet kurali
    Mertebe adlarina uygulanmaz). Isaretsiz ve karsiligi bulunmayan bir
    gecis bu yuzden eslesmeyen sayilmaz, 'siradan' kovasina duser.
    Isaretsiz ama karsiligi bulunan gecis yine eslesti sayilir; tirnaksiz
    gercek Mertebe gecisleri (哪怕不眠者) boylece kaybolmaz.
    """
    p = desen.pattern
    return re.compile(
        f"[“‘「『](?:{p})[”’」』]"
        f"|(?:{p})(?=途径|魔药|序列)"
        f"|序列[0-9〇零一二三四五六七八九十]*(?:{p})"
    )


def terimi_tara(
    sorgu, adaylar, onbellek, kaynak, hedef, duyarsiz, desen=None, isaret=None
):
    """
    Tek terim, onceden yuklenmis bolumler uzerinde. tara()'nin ucuzu.

    isaret verilirse (bkz. mertebe_isaret_deseni) her vurusa 'siradan'
    alani eklenir: kaynak paragrafta terim isaretli olarak gecmiyorsa True.
    """
    desen = desen or kaynak_deseni(sorgu, kaynak, duyarsiz)
    vuruslar = []
    for no, b in onbellek.items():
        if not desen.search(b.k_ham):  # on eleme: hizalama bile tetiklenmez
            continue
        nereye, kayan = b.hizalama  # lazy: ilk vurusta hesaplanir / diskten gelir
        k_par, h_par = b.k_par, b.h_par
        for i, p in enumerate(k_par):
            if not desen.search(p):
                continue
            # Kayit ceviri_denetle.vurus_kur ile kurulur (sema tek yerde).
            #
            # KOMSU PENCERESI. Turkce paragraf yapisi bilerek Cince'den
            # farkli kuruluyor (okur icin bolme/birlestirme); hizalama her
            # zaman kusursuz olamaz ve karsilik cogu zaman hemen yandaki
            # paragrafta durur. Hedef bu yuzden +-1 Turkce paragrafla
            # genisletilir, ama DAR ve GENIS ayri tutulur: yalnizca komsuda
            # bulunan bir karsilik "eslesti" sayilmaz, 'komsu' kovasina
            # duser (bkz. ozetle). Yanlis bir karsiligi komsudaki dogru bir
            # gecisin arkasina saklamamak icin.
            ib = list(nereye.get(i, []))
            komsu = []
            if ib:
                komsu = [
                    j
                    for j in (min(ib) - 1, max(ib) + 1)
                    if 0 <= j < len(h_par) and j not in ib
                ]
            vuruslar.append(
                CD.vurus_kur(
                    no,
                    p,
                    h_par,
                    ib + komsu,
                    ib_dar=ib,
                    genis="komsu" if komsu else None,
                    kayan=i in kayan,
                    **({"siradan": not isaret.search(p)} if isaret else {}),
                )
            )
    if vuruslar:
        CD.siniflandir(vuruslar, adaylar, hedef, kesif=False)
    return vuruslar


def ozetle(vuruslar):
    """
    Dort kova:
      eslesti     karsilik hizalanan Turkce paragrafta
      komsu       hizalanan paragrafta YOK, hemen yandakinde VAR. Buyuk
                  olasilikla paragraf yapisi farki; ama komsudaki gecis
                  baska bir cumleye de ait olabilir, bu yuzden eslesti
                  sayilmaz ve ayri listelenir. Orana girmez.
      karantina   hizalamasi kaymis bolgede ve komsuda da yok. Hakkinda
                  hicbir sey soylenemez -- ne dogru ne yanlis.
      eslesmeyen  saglam bolgede, ne hizalanan paragrafta ne komsusunda.
                  Gercek bulgu.
    Hicbir kovaya girmeyen: tek tarafli (kaynak paragrafin hedefi yok).

    Doner: (sayim, eslesmeyen, karantina, tek_tarafli, komsu)
    """
    sayim = defaultdict(int)
    eslesmeyen, karantina, komsu, tek_tarafli = [], [], [], 0
    for v in vuruslar:
        if v["tip"] == "tek_tarafli":
            tek_tarafli += 1
        elif v["bulunan_dar"]:
            for ad in v["bulunan_dar"]:
                sayim[ad] += 1
        elif v["bulunan"]:
            komsu.append(v)
            for ad in v["bulunan"]:
                sayim[ad] += 1
        elif v.get("kayan"):
            karantina.append(v)
        else:
            eslesmeyen.append(v)
    return dict(sayim), eslesmeyen, karantina, tek_tarafli, komsu


# --------------------------------------------------------------- cikti


def _ad(k) -> str:
    """Tablodaki ad; words.md maddeleri '·' ile baslar."""
    kelime = str(k.get("kategori", "")).startswith(lotm.KELIME_KATEGORI)
    return ("·" if kelime else "") + k["terim"]


def satir_yaz(kayitlar, genislik=100):
    print(f"\n{'─' * genislik}")
    print(
        f"{'terim':<28}{'geçiş':>6}{'eşleşmeyen':>12}{'oran':>7}{'krntn':>7}{'komşu':>7}  karşılıklar"
    )
    print("─" * genislik)
    for k in kayitlar:
        # Terk edilmis karsilik varsa ONCE o yazilir ve basina isaret konur.
        # Eskiden isaret dizenin SONUNA ekleniyordu ve satir kirpilinca ilk
        # kaybolan oydu: komsu sutunu eklenince "İlm-i Esrar" satirinda
        # "mistisizm"den sonraki "⚠ eski" artik gorunmuyordu.
        eski = k.get("eski_gorulen") or set()
        sirali = sorted(k["sayim"].items(), key=lambda kv: (kv[0] not in eski, -kv[1]))
        kars = ("⚠ " if eski else "") + ", ".join(f"{a}×{n}" for a, n in sirali[:3])
        # 'krntn' basligi vardi ama degeri hic yazilmiyordu; karsiliklar bir
        # sutun sola kayip krntn'in altina dusuyordu.
        print(
            f"{_ad(k)[:27]:<28}{k['toplam']:>6}{len(k['eslesmeyen']):>12}"
            f"{k['oran']:>7.0%}{len(k.get('karantina', [])):>7}"
            f"{len(k.get('komsu', [])):>7}  {kars[: genislik - 69]}"
        )


def ayrinti_yaz(kayit, ust=15, arka_plan=None, elenen=None):
    yer = (
        f"   [{kayit['kategori']}]"
        if str(kayit.get("kategori", "")).startswith(lotm.KELIME_KATEGORI)
        else ""
    )
    print(f"\n{'═' * 72}\n{kayit['terim']}  ←  {kayit['sorgu']}{yer}\n{'═' * 72}")
    print(
        f"{kayit['toplam']} geçiş, {len(kayit['eslesmeyen'])} eşleşmeyen, "
        f"{len(kayit['karantina'])} karantina (hizalama kaymış), "
        f"{len(kayit.get('komsu', []))} komşuda, "
        f"{kayit['tek_tarafli']} hizalanamayan"
        + (
            f", {len(kayit['siradan'])} gündelik anlamda (Mertebe olarak işaretsiz)"
            if kayit.get("siradan")
            else ""
        )
        + (
            f", {len(kayit['genis'])} serbest çeviri (madde {{geniş}} işaretli)"
            if kayit.get("genis")
            else ""
        )
    )
    CD.zh_elenen_yaz(elenen)
    if kayit["sayim"]:
        for a, n in sorted(kayit["sayim"].items(), key=lambda kv: -kv[1]):
            print(f"  {a}: {n}")
    # Eslesmeyende DAR metin gosterilir: hizalanan paragraf. Komsular
    # zaten aranmis ve orada da yok.
    desen = kayit.get("desen")
    zh_mi = kayit.get("kaynak") == "zh" and desen is not None
    for v in kayit["eslesmeyen"][:ust]:
        ozet = re.sub(r"\s+", " ", v["hedef_metin_dar"])[:110]
        # Cince pencere: ayni dizi (占卜家) tekrar ediyorsa eslesmeme buyuk
        # olasilikla sozlukte eksik bir bilesikten gelir, ceviriden degil.
        pen = f"〔{CD.zh_pencere(v['kaynak_metin'], desen)}〕 " if zh_mi else ""
        print(f"  [bölüm {v['bolum']}] {pen}{ozet or '(hedef paragraf boş)'}")
    if len(kayit["eslesmeyen"]) > ust:
        print(f"  ... {len(kayit['eslesmeyen']) - ust} tane daha")
    if kayit.get("genis"):
        print("  serbest çeviri ({geniş}; bulgu sayılmaz):")
        for v in kayit["genis"][:ust]:
            ozet = re.sub(r"\s+", " ", v["hedef_metin_dar"])[:110]
            pen = f"〔{CD.zh_pencere(v['kaynak_metin'], desen)}〕 " if zh_mi else ""
            print(f"  [bölüm {v['bolum']}] {pen}{ozet or '(hedef paragraf boş)'}")
        if len(kayit["genis"]) > ust:
            print(f"  ... {len(kayit['genis']) - ust} tane daha")
    if zh_mi and kayit["eslesmeyen"]:
        CD.zh_bilesik_yaz(
            CD.zh_bilesik_raporu(
                kayit["eslesmeyen"], desen, arka_plan, dil=kayit.get("hedef", "tr")
            )
        )
    if kayit.get("komsu"):
        print("  komşuda bulunanlar (paragraf yapısı farkı mı, başka cümle mi?):")
        for v in kayit["komsu"][:ust]:
            ozet = re.sub(r"\s+", " ", v["hedef_metin_dar"])[:70] or "(boş)"
            print(
                f"  [bölüm {v['bolum']}] {', '.join(v['bulunan'])}  <- hizalanan: {ozet}"
            )


def bilesik_ipucu_yaz(kayitlar, en_az=3, pay=0.25):
    """
    Tablo sonrasi: eslesmeyenleri sozlukte KAYITLI OLMAYAN bir Cince
    bilesikte yogunlasan terimler. Bunlar ceviri hatasi degil sozluk
    eksigi olabilir; once bakilmalari gerekir, cunku oranlari yanilticidir
    (kehanet <- 占卜: 39 eslesmeyenin cogu dogru cevrilmis 占卜家 / 占卜师).

    Esik: en cok gecen dizi en az 'en_az' eslesmeyende VE eslesmeyenlerin
    en az 'pay' kadarinda. Hedef metinde kesif yapilmaz (her terim icin
    pahali); ayrinti icin --ayrinti.
    """
    satirlar = []
    for k in kayitlar:
        if k.get("kaynak") != "zh" or not k["eslesmeyen"] or k.get("desen") is None:
            continue
        ipuclari = CD.zh_bilesik_ipuclari(k["eslesmeyen"], k["desen"], en_az=en_az)[:3]
        if not ipuclari or ipuclari[0][1] < pay * len(k["eslesmeyen"]):
            continue
        kapsanan = {id(v) for _d, _n, vs in ipuclari for v in vs}
        satirlar.append((k, ipuclari, len(kapsanan)))
    if not satirlar:
        return
    print(
        "\nEşleşmeyenleri sözlükte kayıtlı olmayan bir Çince bileşikte yoğunlaşan terimler"
    )
    print('(oranları yanıltıcı olabilir; ayrıntı için --ayrinti "<terim>"):')
    for k, ipuclari, kapsanan in sorted(satirlar, key=lambda s: -s[2]):
        dokum = ", ".join(f"{d}×{n}" for d, n, _vs in ipuclari)
        print(
            f"  {_ad(k)} ← {k['sorgu']}: {dokum}  "
            f"({len(k['eslesmeyen'])} eşleşmeyenin {kapsanan}'i)"
        )


def tsv_yaz(kayitlar):
    print("terim\tsorgu\ttoplam\teslesmeyen\toran\ttek_tarafli\tkomsu\tkarsiliklar")
    for k in kayitlar:
        kars = "|".join(f"{a}:{n}" for a, n in k["sayim"].items())
        print(
            f"{k['terim']}\t{k['sorgu']}\t{k['toplam']}\t"
            f"{len(k['eslesmeyen'])}\t{k['oran']:.3f}\t{k['tek_tarafli']}\t"
            f"{len(k.get('komsu', []))}\t{kars}"
        )


# --------------------------------------------------------------- ana


def eski_ozeti(vuruslar, sayim, eski, gecis=None):
    """
    (eski_gorulen, eski_sayim). Gecis bolumu varsa (bolum_siniri, bkz.
    lotm.gecis_bolumu) yalnizca o bolumden itibaren bulunan eski
    bicimler sayilir.
    """
    if not gecis:
        g = {a for a in sayim if a in eski}
        return g, {a: sayim[a] for a in g}
    kesit = gecis
    sonra = defaultdict(int)
    for v in vuruslar:
        if v.get("bolum") is not None and v["bolum"] >= kesit:
            for ad in v.get("bulunan_dar") or v.get("bulunan") or []:
                if ad in eski:
                    sonra[ad] += 1
    return set(sonra), dict(sonra)


def isleri_kur(kaynak: str, hedef: str, kelimeler: str = "dahil"):
    """
    Taranacak terimler: [(kaynak, sorgu, terim, adaylar, duyarli, eski)].

    kaynak "ikisi" ise her terim EN IYI anahtariyla taranir: Cincesi
    (tek karakterlik parcalar atildiktan sonra) varsa Cince, yoksa
    Ingilizce. Cince anahtar kesindir; Ingilizce yalnizca Cincesi
    girilmemis terimler icin devreye girer. Boylece zincir tek bir
    tablo uretir, ayni terim iki kez gorunmez.

    Doner: (isler, atlanan) -- atlanan, hicbir anahtarla taranamayanlar.
    """
    if kaynak != "ikisi":
        liste, atlanan = sweep_terimleri(kaynak, hedef, kelimeler=kelimeler)
        return [(kaynak, *x) for x in liste], atlanan
    zh, _ = sweep_terimleri("zh", hedef, kelimeler=kelimeler)
    en, _ = sweep_terimleri("en", hedef, kelimeler=kelimeler)
    zh_anahtar = {(t.tr, t.kategori) for _s, t, *_ in zh}
    en_kalan = [x for x in en if (x[1].tr, x[1].kategori) not in zh_anahtar]
    # Hic taranamayan: ne Cince ne Ingilizce anahtari olan. Ayni filtreyle
    # sozlugu bir kez daha sayariz; sweep'in kendi "atlanan"i tek dil icindir.
    taranan = zh_anahtar | {(t.tr, t.kategori) for _s, t, *_ in en_kalan}
    tum = {
        (t.tr, t.kategori)
        for t in lotm.sozluk_yukle(kelimeler=(kelimeler != "haric")).terimler
        if kelimeler != "yalniz" or t.kategori.startswith(lotm.KELIME_KATEGORI)
    }
    isler = [("zh", *x) for x in zh] + [("en", *x) for x in en_kalan]
    return _tekillestir(isler), len(tum - taranan)


def _tekillestir(isler: list) -> list:
    """
    Ayni Turkce terim hem sozlukte hem words.md'de varsa tabloda iki kez
    cikiyordu ("Asılmış Adam" sozlukten Ingilizceyle, "·Asılmış Adam"
    words.md'den Cinceyle). Terim basina TEK satir kalir: Cince anahtarla
    taranan once gelir (kesin), esitlikte sozluk words.md'ye tercih edilir.
    """

    def oncelik(is_):
        kaynak, _s, t, *_ = is_
        return (kaynak != "zh", t.kategori.startswith(lotm.KELIME_KATEGORI))

    secilen = {}
    for is_ in sorted(isler, key=oncelik):
        secilen.setdefault(lotm.tr_kucult(is_[2].tr), is_)
    return [is_ for is_ in isler if secilen[lotm.tr_kucult(is_[2].tr)] is is_]


def fark_kayitlari(kayitlar) -> list:
    """
    fark.py icin (anahtar, gorunum): her ESLESMEYEN gecis ve metinde kalan
    her terk edilmis karsilik. Anahtar kaynak paragrafindan kurulur; kaynak
    metin degismez, yani bir gecis yalnizca ceviri, sozluk ya da hizalama
    degisince belirir ya da kaybolur. Karantina ve komsu bilerek disarida:
    hizalama kusurudur, ceviri bulgusu degil.
    """
    out = []
    for k in kayitlar:
        for v in k["eslesmeyen"]:
            kaynak = re.sub(r"\s+", " ", v["kaynak_metin"])[:80]
            hedef = re.sub(r"\s+", " ", v["hedef_metin_dar"])[:70]
            out.append((
                ("eslesmeyen", k["terim"], v["bolum"], kaynak),
                f"[bölüm {v['bolum']}] {_ad(k)} <- {k['sorgu']}: eşleşmeyen | {hedef}",
            ))
        for eski, n in sorted(k.get("eski_sayim", {}).items()):
            out.append((
                ("eski", k["terim"], eski),
                f"{_ad(k)}: terk edilmiş '{eski}' metinde ×{n}",
            ))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sozlugun tamamini yayimlanmis metne karsi tarar."
    )
    ap.add_argument(
        "--kaynak",
        choices=("zh", "en", "ikisi"),
        default="en",
        help="ikisi: Cincesi olan terim Cince, olmayan Ingilizce anahtarla (zincir bunu kullanir)",
    )
    ap.add_argument("--hedef", choices=("tr", "en", "zh"), default="tr")
    ap.add_argument("--bolum", default=None, help="'1-200' ya da '279'")
    ap.add_argument(
        "--en-az",
        type=int,
        default=1,
        dest="en_az",
        help="bu sayidan az gecisi olan terimleri atla",
    )
    ap.add_argument(
        "--harf-duyarsiz",
        action="store_true",
        dest="duyarsiz",
        help="kategori kararını ezip her terimi duyarsız tara",
    )
    ap.add_argument(
        "--ayrinti", default=None, help="tek terimin eslesmeyenlerini ayrintili yaz"
    )
    ap.add_argument(
        "--kelimeler",
        choices=("dahil", "haric", "yalniz"),
        default="dahil",
        help="words.md maddeleri: dahil (varsayilan), haric, ya da yalniz onlar",
    )
    ap.add_argument("--format", choices=("tablo", "tsv"), default="tablo")
    ap.add_argument(
        "--hepsi",
        action="store_true",
        help="tam eslesen terimleri de tabloda goster (varsayilan: gizli)",
    )
    ap.add_argument(
        "--yenile",
        action="store_true",
        help="hizalama onbellegini sil ve sifirdan hesapla",
    )
    ap.add_argument("--genislik", type=int, default=None)
    ap.add_argument(
        "--bulgular", default=None,
        help="eslesmeyen gecisleri ve eski karsiliklari fark.py icin TSV olarak yaz",
    )
    a = ap.parse_args()

    import shutil

    genislik = a.genislik or shutil.get_terminal_size((100, 40)).columns

    if a.kaynak == a.hedef:
        sys.exit("kaynak ve hedef ayni olamaz")

    if a.yenile and ONBELLEK_DIZINI.exists():
        for f in ONBELLEK_DIZINI.glob("*.pkl"):
            f.unlink(missing_ok=True)

    terimler, atlanan = isleri_kur(a.kaynak, a.hedef, a.kelimeler)
    # --ayrinti: yalnizca istenen terim taranir; bolumler de yalnizca o
    # terimin gectigi yerde hizalanir (bkz. HizalanmisBolum).
    if a.ayrinti:
        q = lotm.tr_kucult(a.ayrinti)
        terimler = [x for x in terimler if q in lotm.tr_kucult(x[2].tr)]
    kullanilan = sorted({k for k, *_ in terimler})
    onbellekler = {
        k: hizalama_onbellegi(k, a.hedef, CD.bolum_araligi(a.bolum)) for k in kullanilan
    }
    # Tam taramada hizalamalar bastan, cok cekirdekte hesaplanir.
    if not a.ayrinti:
        for ob in onbellekler.values():
            hepsini_hizala(ob)
    dokum = ", ".join(
        f"{sum(1 for k, *_ in terimler if k == x)} {x}" for x in kullanilan
    )
    print(
        f"{len(terimler)} terim taranacak ({dokum})"
        f"{f'; {atlanan} tanesi anahtarı olmadığı için atlandı' if atlanan else ''}",
        file=sys.stderr,
    )

    kayitlar = []
    for i, (kaynak, sorgu, t, adaylar, duyarli, eski) in enumerate(terimler, 1):
        print(f"\rtaraniyor: {i}/{len(terimler)}", end="", file=sys.stderr)
        # --harf-duyarsiz kuresel olarak zorlar; verilmezse karar kategoriye
        # birakilir (bkz. harf_duyarli_mi).
        duyarsiz = a.duyarsiz or not duyarli
        desen = kaynak_deseni(sorgu, kaynak, duyarsiz, t.zh_haric)
        # Mertebe adlari gundelik anlamda da gecer; yalnizca Cincede
        # isaretli olup olmadigi anlasilabilir (bkz. mertebe_isaret_deseni).
        isaret = (
            mertebe_isaret_deseni(desen) if kaynak == "zh" and t.mertebe_mi else None
        )
        vuruslar = terimi_tara(
            sorgu, adaylar, onbellekler[kaynak], kaynak, a.hedef, duyarsiz,
            desen=desen, isaret=isaret,
        )
        if len(vuruslar) < a.en_az:
            continue
        sayim, eslesmeyen, karantina, tek, komsu = ozetle(vuruslar)
        siradan = [v for v in eslesmeyen if v.get("siradan")]
        eslesmeyen = [v for v in eslesmeyen if not v.get("siradan")]
        # {geniş} isaretli terim: anahtar gundelik bir kelime, eslesmeyenler
        # serbest ceviridir. Orana ve bulgulara girmez, --ayrinti'da gorunur.
        genis = eslesmeyen if t.genis else []
        if t.genis:
            eslesmeyen = []
        eski_g, eski_s = eski_ozeti(
            vuruslar, sayim, eski, gecis_bolumu(t) if a.hedef == "tr" else None
        )
        kayitlar.append(
            {
                "terim": t.tr,
                "sorgu": sorgu,
                "kaynak": kaynak,
                "hedef": a.hedef,
                "desen": desen,
                "kategori": t.kategori,
                "eski_gorulen": eski_g,
                "eski_sayim": eski_s,
                "toplam": len(vuruslar),
                "sayim": sayim,
                "eslesmeyen": eslesmeyen,
                "karantina": karantina,
                "komsu": komsu,
                "siradan": siradan,
                "genis": genis,
                "tek_tarafli": tek,
                # Oran YALNIZCA saglam bolgeler uzerinden. Kaymis bolgelerden
                # gelen eslesmeyenler paydadan da cikarilir, aksi hâlde
                # hizalama hatasi ceviri hatasi gibi gorunur. Gundelik
                # anlamdaki Mertebe gecisleri de ayni sebeple disarida.
                "oran": (
                    len(eslesmeyen)
                    / (len(vuruslar) - len(karantina) - len(siradan) - len(genis))
                    if len(vuruslar) - len(karantina) - len(siradan) - len(genis) > 0
                    else 0.0
                ),
            }
        )
    print(f"\r{len(kayitlar)} terim metinde geçiyor.{' ' * 20}", file=sys.stderr)

    if a.ayrinti:
        bulunan = list(kayitlar)  # terimler zaten ayrinti sorgusuna gore suzuldu
        if not bulunan:
            sys.exit(f"'{a.ayrinti}' taramada geçmiyor")
        for k in bulunan:
            arka, elenen = None, None
            if k["kaynak"] == "zh":
                ob = onbellekler["zh"]
                # Kesif icin arka plan: taranan bolumlerin butun hedef
                # paragraflari (kume paragraflari zh_bilesik_raporu'nda cikarilir).
                arka = [p for b in ob.values() for p in b.h_par]
                elenen = sum(
                    (
                        CD.zh_elenenler(p.strip(), [b.k_ham for b in ob.values()])
                        for p in k["sorgu"].split("/")
                        if p.strip()
                    ),
                    Counter(),
                )
            ayrinti_yaz(k, arka_plan=arka, elenen=elenen)
        return 0

    kayitlar.sort(key=lambda k: (-k["oran"], -k["toplam"]))
    if a.bulgular:
        lotm.bulgulari_yaz(a.bulgular, fark_kayitlari(kayitlar))
    if a.format == "tsv":
        tsv_yaz(kayitlar)
    else:
        # Tabloda yalnizca is cikaran satirlar: eslesmeyeni ya da metinde
        # kalmis terk edilmis karsiligi olanlar. 640 terimin 570'i temiz;
        # onlar listeyi uzatip bulgulari ekranin disina itiyordu. TSV ve
        # --bulgular etkilenmez, ozet satiri hepsini sayar.
        gorunen = (
            kayitlar
            if a.hepsi
            else [k for k in kayitlar if k["eslesmeyen"] or k.get("eski_gorulen")]
        )
        satir_yaz(gorunen, genislik)
        if len(gorunen) < len(kayitlar):
            print(
                f"({len(kayitlar) - len(gorunen)} tam eşleşen terim gizlendi; "
                f"hepsi için --hepsi)"
            )
        bilesik_ipucu_yaz(kayitlar)
        temiz = sum(1 for k in kayitlar if not k["eslesmeyen"])
        eskiler = [k for k in kayitlar if k.get("eski_gorulen")]
        print(
            f"\n{temiz}/{len(kayitlar)} terim tam eşleşti. "
            f"{len(eskiler)} terimde terk edilmiş karşılık hâlâ metinde"
            + (":" if eskiler else ".")
        )
        for k in sorted(eskiler, key=lambda k: -sum(k["eski_sayim"].values())):
            dokum = ", ".join(
                f"{a}×{k['eski_sayim'][a]}" for a in sorted(k["eski_gorulen"])
            )
            guncel = sum(n for a, n in k["sayim"].items() if a not in k["eski_gorulen"])
            print(f"  ⚠ {k['terim']}: {dokum}  (güncel karşılık: {guncel})")
        genisler = [k for k in kayitlar if k.get("genis")]
        if genisler:
            print(
                f"{len(genisler)} {{geniş}} terimde "
                f"{sum(len(k['genis']) for k in genisler)} serbest çeviri ayrı tutuldu "
                f"(bulgu sayılmaz; görmek için --ayrinti)."
            )
        print("Listenin başı: eski_karşılık geri doldurma sırası.")
        if any(_ad(k).startswith("·") for k in kayitlar):
            print("· = words.md maddesi (yalnız onlar için: --kelimeler yalniz)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
