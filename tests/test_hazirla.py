# -*- coding: utf-8 -*-
"""hazirla.py -- ceviriden once: bolumde gecen yerlesmis terimler."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hazirla as H  # noqa: E402
import lotm  # noqa: E402


def _t(tr, en=None, zh=None, kategori="Temel Kavramlar", **kw):
    return lotm.Terim(tr=tr, en=en, zh=zh, kategori=kategori, **kw)


def test_cince_eslesme_okuma_sirasi_ve_bilesik_haric():
    terimler = [
        _t("Astral Beden", "Astral Projection", "星灵体"),
        _t("Ruhani Beden", "Spirit Body", "灵体"),
        _t("Kâhin", "Seer", "占卜家", kategori="Kâhin Yolu"),
    ]
    hepsi = sorted({t.zh for t in terimler}, key=len, reverse=True)
    zh = "克莱恩是占卜家。他看见了星灵体。灵体很淡。"
    e = H.terimleri_bul(zh, None, terimler, hepsi)
    assert [(x.terim.tr, x.sayi) for x in e] == [("Kâhin", 1), ("Astral Beden", 1), ("Ruhani Beden", 1)]


def test_cincesi_olmayan_terim_ingilizceden_bulunur_harf_kurali_ile():
    terimler = [
        _t("Kehanet", "Divination"),                              # Temel Kavramlar: duyarsiz
        _t("Ölüm", "Death", kategori="İlahlar ve Yüce Kadimler"),  # ozel ad: duyarli
    ]
    en = "Klein studied divination. Nobody feared death."
    e = H.terimleri_bul(None, en, terimler, [])
    assert [(x.terim.tr, x.nasil) for x in e] == [("Kehanet", "en")]


def test_sozluk_kaydi_words_md_kaydina_tercih_edilir():
    terimler = [
        _t("Sıradışı", "Beyonder", "非凡者", kategori="words.md › X"),
        _t("Sıradışı", "Beyonder", "非凡者"),
    ]
    e = H.terimleri_bul("一个非凡者", None, terimler, ["非凡者"])
    assert len(e) == 1 and e[0].terim.kategori == "Temel Kavramlar"


def test_salahiyet_yalniz_baglaminda_sayilir():
    kayitlar = [{"cince": "力量", "turkce": "Kudret"}, {"cince": "死亡", "turkce": "Mevt"}]
    zh = "他用尽了力量。祂掌握了死亡权柄。"
    baglamli, siradan = H.salahiyetleri_bul(zh, kayitlar, ["力量", "死亡"])
    assert [k["turkce"] for k, _n, _i in baglamli] == ["Mevt"]
    assert [k["turkce"] for k, _n, _i in siradan] == ["Kudret"]


def test_aday_adlar_iyelik_satir_sonu_ve_bilinenler():
    # Cumle basindaki tek buyuk harfli kelime bilerek aday sayilmaz (orada
    # her kelime buyuk harflidir); adaylar cumle ortasindan gelir.
    en = ("He saw Angelica's coat. He met Angelica and Old Neil at the Berserk Sea.\n\n"
          "First Divination Requester\n\nChapter 2: Klein's day. Klein Moretti waved.")
    bilinen = {"klein", "moretti", "old neil"}
    adaylar = {a.ad: a.sayi for a in H.aday_adlar(en, bilinen, en_kucuk=1)}
    assert adaylar.get("Angelica") == 2                 # iyelik ayni ad
    assert "Berserk Sea" in adaylar and "First Divination Requester" in adaylar
    assert not any("Chapter" in a for a in adaylar)    # satir sonu obegi bolmez
    assert "Klein Moretti" not in adaylar and "Klein" not in adaylar


def test_yaz_kapi_icermez_ve_eski_karsiligi_yasaklar():
    t = _t("Ayin", "Ritual", "仪式", bolum_siniri=22, eski_karsiliklar=["ritüel"],
           ham={"aciklama": "Bir tören.", "mudahale": "ceviri"})
    e = H.Eslesme(t, "zh", 2, 0, yayim=[30, 40])
    md = H.yaz_dokum(10, "仪式", None, [e], [], [], [], [], 53)
    assert "KULLANILMAZ (eski karşılık): ritüel" in md
    assert "yayımlanmış 2 bölümde (son: 40)" in md
    assert "22" not in md                                # bolum_siniri yazilmaz
    assert "yalnız Çince" in md



def test_salahiyet_tirnakli_ve_de_ile():
    kayitlar = [{"cince": "死亡", "turkce": "Mevt"}, {"cince": "秘密", "turkce": "Sır"}]
    zh = "祂拥有部分“死亡”权柄，也是秘密的象征。"
    baglamli, siradan = H.salahiyetleri_bul(zh, kayitlar, ["死亡", "秘密"])
    assert sorted(k["turkce"] for k, _n, _i in baglamli) == ["Mevt", "Sır"] and not siradan


# ------------------------------------------------------------------
# 55. bolum dokumunde gorulen hatalar


def _korpus(kucuk=(), orta=()):
    return H.Korpus(set(kucuk), set(orta))


def test_cok_bicimli_kayitta_bolumde_gecen_bicim_yazilir():
    # "kehanet gök haritası / gök haritası" ↔ "占卜星盘/星盘"; 55'te yalniz 星盘.
    t = _t("kehanet gök haritası", "divination star chart", "占卜星盘/星盘",
           kategori="words.md › Objects", arama_adi=["gök haritası"])
    e = H.terimleri_bul("他绘制了星盘。星盘很复杂。", None, [t], ["占卜星盘", "星盘"])[0]
    assert H._bicim_dagilimi(e) == [("kehanet gök haritası", 0), ("gök haritası", 2)]
    md = "\n".join(H._terim_satirlari(e, "", False))
    assert md.startswith("- **gök haritası**")
    assert "kehanet gök haritası bu bölümde GEÇMİYOR" in md


def test_ayni_anahtari_paylasan_farkli_kayitlar_1c():
    terimler = [
        _t("Ruhanî Beden", "Spirit Body", "灵体"),
        _t("ruhanî varlık", "spirit body", "灵体", kategori="words.md › Mysticism"),
    ]
    e = H.terimleri_bul("一个灵体飘过。", None, terimler, ["灵体"])
    assert sorted(x.cok_anlamli[0] for x in e) == ["Ruhanî Beden", "ruhanî varlık"]
    md = H.yaz_dokum(55, "一个灵体飘过。", None, e, [], [], [], [], 54)
    assert "### 1c." in md and "bağlam: 一个灵体飘过" in md


def test_ingilizce_cogul_eki_kabul_edilir():
    t = _t("Gizem Avcısı", "Mystery Pryer", kategori="Aşkın Yolları")
    e = H.terimleri_bul(None, "Old Neil said Mystery Pryers could do it.", [t], [])
    assert [(x.terim.tr, x.sayi) for x in e] == [("Gizem Avcısı", 1)]


def test_liste_buyuk_harfi_yayimda_kucuk_bulunur():
    class B:
        def __init__(self, no, metin):
            self.no, self.metin = no, metin

    kristal = _t("Kristal küre", "crystal ball", "水晶球", kategori="words.md › Objects")
    kahin = _t("Kâhin", "Seer", "占卜家", kategori="Kâhin Yolu")
    kahin_k = _t("kâhin", "fortune-teller", "占卜师", kategori="words.md › Mysticism")
    es = [H.Eslesme(kristal, "zh", 1, 0), H.Eslesme(kahin, "zh", 1, 0)]
    bolumler = [B(40, "Masada bir kristal kürenin yanında"), B(41, "Yaşlı kâhin güldü.")]
    H.yayim_kullanimi(es, bolumler, 55, H.harf_kardesleri([kristal, kahin, kahin_k]))
    assert es[0].yayim == [40] and es[0].kucuk_bicim == "kristal küre"
    assert es[1].yayim == []  # Kâhin'in kucuk harfli kardesi var: katlanmaz


def test_cince_anahtar_bilesimden_cikarilir():
    # 梦境占卜 ⊃ 占卜 (Kehanet); Rüya Kehaneti ⊃ Kehanet; ayni yerde.
    kehanet = _t("Kehanet", "Divination", "占卜")
    ruya = _t("Rüya Kehaneti", "Dream Divination")
    terimler = [kehanet, ruya]
    zh = "他开始占卜。" + "。" * 40 + "他用的是“梦境占卜”！" + "。" * 40
    en = "He began divining. " + "." * 40 + "He used dream divination! " + "." * 40
    es = H.terimleri_bul(zh, en, terimler, ["占卜"])
    z = H.zh_adaylari(zh, ({"占卜"}, set()))
    cik = H.anahtar_cikar(z, es, terimler, zh, en)
    assert [k for _t2, k in cik.values()] == ["梦境占卜"]
    _ts, _h, es2 = H.cikarimla_yeniden(zh, en, terimler, ["占卜"], cik)
    say = {x.terim.tr: (x.sayi, x.nasil, x.cikarim) for x in es2}
    assert say["Kehanet"] == (1, "zh", "")
    assert say["Rüya Kehaneti"] == (1, "zh", "梦境占卜")


def test_noktali_ad_gecislerin_ortaginda_kesilir():
    zh = "“乔伊斯·迈尔，1323年”粗略判断乔伊斯·迈尔会遭遇厄难。写下“乔伊斯·迈尔现在的状况”。乔伊斯·迈尔先生"
    adlar = {a.ad for a in H.zh_adaylari(zh, (set(), set()))}
    assert adlar == {"乔伊斯·迈尔"}


def test_uzatilmis_aday_kokune_indirgenir():
    zh = "他要用的是“梦境占卜法”！也能做“梦境占卜”，“梦境占卜”。"
    assert {a.ad for a in H.zh_adaylari(zh, (set(), set()))} == {"梦境占卜"}


def test_ingilizce_aday_temizligi_55():
    en = ("He had time. Sigh, it isn't letting me go… All I can hope for is Ray Bieber. "
          "According to Old Neil, Mystery Pryers could. Klein said, \"Congratulations Miss "
          "Anna, Mr. Joyce Meyer is here.\" He saw Anna. Anna nodded. It was Joyce's Year "
          "Path Number. Joyce smiled at Meyer. Outside? Angelica will bring tea.")
    bilinen = {"neil", "mystery pryer", "year path number"}
    korpus = _korpus(
        kucuk={"all", "old", "according", "congratulations", "sigh", "he", "it", "outside",
               "path", "number", "year"},
        orta={"Ray", "Bieber", "Neil", "Anna", "Joyce", "Meyer", "Angelica", "Old", "Miss",
              "Year", "Path", "Number"},
    )
    adaylar = {a.ad: a for a in H.aday_adlar(en, bilinen, sozcukler=korpus)}
    assert set(adaylar) == {"Ray Bieber", "Joyce Meyer", "Anna", "Angelica"}
    assert adaylar["Anna"].sayi == 3                       # cumle basindakiler dahil
    assert adaylar["Joyce Meyer"].parcalar == {"Joyce": 2, "Meyer": 1}


def test_unvan_ad_ve_cogul_kisi_adi():
    en = "He saw Corpse Collector Frye and Frye left. Tell the boss, Williams, now."
    bilinen = {"corpse collector", "william i"}
    korpus = _korpus(kucuk={"corpse", "collector", "he", "tell", "the", "boss", "now"},
                     orta={"Frye", "Williams", "Corpse", "Collector"})
    adaylar = {a.ad: a.sayi for a in H.aday_adlar(en, bilinen, sozcukler=korpus)}
    assert adaylar == {"Frye": 2, "Williams": 1}


def test_eslestirme_ses_ve_anlam_ayrimi():
    def aday(ad, k, dil, tur=""):
        return H.Aday(ad, len(k), k, dil, tur)

    korpus = _korpus(kucuk={"birth", "day", "path", "number", "street", "old"},
                     orta={"Stevens", "Ray", "Bieber", "Neil"})
    # 生日灵数 (anlamla) Stevens Street'e degil Birth Day Path Number'a gider;
    # 瑞尔·比伯 (sesle) Ray Bieber'a.
    en = [aday("Stevens Street", [100], "en"), aday("Birth Day Path Number", [140, 300], "en"),
          aday("Ray Bieber", [900], "en")]
    zh = [aday("生日灵数", [95, 290], "zh", "ad verme"), aday("瑞尔·比伯", [905], "zh", "noktalı ad")]
    H.adaylari_esle(en, zh, 1000, 1000, korpus)
    assert en[0].es is None
    assert en[1].es is zh[0] and en[2].es is zh[1]


def test_bilesik_takma_ad_dogru_terime_baglanir():
    mun = _t("Müneccimlik", "Astrology / Astromancy", "占星术")
    kil = _t("Müneccimlik Kılavuzu", None, "占星手册", kategori="words.md › Publications")
    en = "." * 50 + "he did not open the Astromancy Manual." + "." * 50
    zh = "。" * 50 + "他几乎没翻“占星手册”。" + "。" * 50
    es = H.terimleri_bul(zh, en, [mun, kil], ["占星手册", "占星术"])
    aday = H.Aday("Astromancy Manual", 1, [en.index("Astromancy")], "en")
    hedef = H.takma_ad_mi(aday, len(en), len(zh), es)
    assert hedef.terim.tr == "Müneccimlik Kılavuzu"
    kalan = H.ic_isabetleri_at(es, [(aday, hedef)])
    assert [x.terim.tr for x in kalan] == ["Müneccimlik Kılavuzu"]


def test_yakin_cince_anahtar():
    t = _t("iki tekerlekli fayton", "two-wheeled carriage", "双轮马车",
           kategori="words.md › Transport")
    en = "." * 40 + "A two-wheeled carriage steered quickly." + "." * 40
    zh = "。" * 40 + "两轮马车轻快地驶过街道。" + "。" * 40
    e = H.terimleri_bul(zh, en, [t], ["双轮马车"])[0]
    assert e.nasil == "en-yedek" and H.yakin_anahtarlar(e, zh, en) == ["两轮马车"]


# ------------------------------------------------------------------
# 56. bolum dokumunde gorulen hatalar. Dizeler 56'nin kendi metninden.


def _hizali(zh_cumle, en_cumle, pay=2000):
    """Cumleyi uzun bir dolgunun ortasina koyar: iki metinde oransal konum ayni."""
    return "。" * pay + zh_cumle + "。" * pay, "." * pay + en_cumle + "." * pay


def test_genel_ortak_kelime_baska_ulkeyi_baglamaz():
    # 56 ¶59: "Feynapotter Kingdom" yalniz 'kingdom' yuzunden Loen Krallığı'na
    # baglaniyordu. "Loen Kingdom" ayirt edici 'loen' ile dogru bag.
    loen = _t("Loen Krallığı", "Kingdom of Loen", "鲁恩王国", kategori="words.md › Nations")
    zh, en = _hizali("鲁恩王国是多信仰的国度，不像南方的费内波特王国。",
                     "The Loen Kingdom was unlike the Feynapotter Kingdom in the south.")
    es = H.terimleri_bul(zh, en, [loen], ["鲁恩王国"])
    korpus = _korpus(kucuk={"kingdom", "the", "south"}, orta={"Loen", "Feynapotter"})
    adaylar = [H.Aday("Loen Kingdom", 1, [en.index("Loen")], "en"),
               H.Aday("Feynapotter Kingdom", 1, [en.index("Feynapotter")], "en")]
    sonuc = {a.ad: (e.terim.tr if e else None)
             for a, e in H.takma_adlari_coz(adaylar, en, zh, es, korpus, set())}
    assert sonuc == {"Loen Kingdom": "Loen Krallığı", "Feynapotter Kingdom": None}


def test_genel_kelimeyle_bag_tek_talipse_kurulur():
    # 54: Foodaholic Empire = Gourmet Empire; terimin Ingilizcesi bolumde yok.
    t = _t("Büyük Oburlar İmparatorluğu", "Gourmet Empire", "大吃货帝国",
           kategori="words.md › Key Figures")
    zh, en = _hizali("大吃货帝国", "the Foodaholic Empire")
    es = H.terimleri_bul(zh, en, [t], ["大吃货帝国"])
    korpus = _korpus(kucuk={"empire", "the"}, orta={"Foodaholic"})
    a = H.Aday("Foodaholic Empire", 1, [en.index("Foodaholic")], "en")
    [(_a, e)] = H.takma_adlari_coz([a], en, zh, es, korpus, set())
    assert e is not None and e.terim.tr == "Büyük Oburlar İmparatorluğu"


def test_gelecekteki_varyant_kaydin_aciklamasi_gosterilmez():
    # 56: Toprak Ana'nin "Dünya Savaşı Sonrası" kaydi (kapi 1409) dosyada once
    # geldigi icin gosteriliyor, sonraki tazim ismi doküme giriyordu.
    sonra = _t("Toprak Ana", "Earth Mother", kategori="İlahlar ve Yüce Kadimler",
               bolum_siniri=1409,
               ham={"terim": "Toprak Ana (Dünya Savaşı Sonrası)", "aciklama": "Sonraki tazim."})
    ana = _t("Toprak Ana", "Earth Mother", kategori="İlahlar ve Yüce Kadimler",
             bolum_siniri=3, ham={"terim": "Toprak Ana", "aciklama": "Asıl tazim."})
    en = "The Feynapotter Kingdom only worshiped Earth Mother."
    md = H.yaz_dokum(56, None, en, H.terimleri_bul(None, en, [sonra, ana], [], 56),
                     [], [], [], [], 55)
    assert "Asıl tazim." in md and "Sonraki tazim." not in md
    # Tek kayit da olsa sonraki bir bolumde acilan aciklama yazilmaz; kapi da.
    tek = H.yaz_dokum(56, None, en, H.terimleri_bul(None, en, [sonra], [], 56),
                      [], [], [], [], 55)
    assert "Sonraki tazim." not in tek and "1409" not in tek
    assert "açıklama gösterilmedi" in tek


def test_ingilizceden_bulunan_siradan_sozcuk_yerlesmis_sayilmaz():
    # 56 ¶63: Cincesiz "el yazması ← notebook" Klein'in kendi defterine
    # yerlesmis terim diye veriliyordu.
    t = _t("el yazması", "notebook", kategori="words.md › Key Figures")
    en = "Klein flipped open his notebook, took out his pen."
    md = H.yaz_dokum(56, None, en, H.terimleri_bul(None, en, [t], []), [], [], [], [], 55)
    assert "el yazması" not in md.split("### 1b.")[0]
    assert "### 1d." in md and 'bağlam: "Klein flipped open his notebook' in md


def test_ad_kurali_ve_cevrilmis_kok():
    korpus = _korpus(kucuk={"sacred", "emblem", "pier", "port"},
                     orta={"Wayne", "Caesar", "Shaud", "Mandarin"})
    sesli = H.Aday("韦恩", 3, [0], "zh", "unvan")
    assert H._ad_karari("Wayne", korpus, {}, sesli).startswith("Türkçesi: Wayne")
    # Sesle cevrilmis Cince esi yok: kesin degil (56: Mandarin = 中文 = Çince)
    assert H._ad_karari("Mandarin", korpus, {}).startswith("Türkçesi büyük ihtimalle: Mandarin")
    assert H._ad_karari("Mrs. Shaud", korpus, {}).startswith("Türkçesi büyük ihtimalle: Shaud")
    assert H._ad_karari("Sacred Emblem", korpus, {}) is None
    kokler = H.cevrilmis_kokler(
        [_t("Sezar Limanı", "Caesar Port", "凯撒港", kategori="words.md › Cities")], korpus)
    assert kokler == {"caesar": "Sezar Limanı"}
    assert "Caesar → Sezar Limanı" in H._ad_karari("Caesar Pier", korpus, kokler)


def test_yayimlanmis_aday_turkcesi_yoksa_a1_denmez():
    # 56: Fourth Epoch, Sacred Emblem "YAYIMLANMIŞ → A.1" diye verilip Turkcesi
    # tahmin ediliyordu; Sacred Emblem 17'de baska bir amblemdi.
    a = H.Aday("Sacred Emblem", 1, [0], "en", ilk_bolum=17)
    md = H.yaz_dokum(56, None, "Sacred Emblem", [], [], [a], [], [], 55)
    assert "bakılmadan A.1'e alınmaz" in md
    assert "karşılık yayımlanmış metinde, A.1" not in md


def test_capa_adlari_dokumde_gorunur():
    # 56: Glacis, Klein... bilinen ad sayilip aday olmuyor, dokumde de hic
    # gorunmuyordu. Capanin Turkce kelime capalari (Nergis) ad degildir;
    # bulunmus bir terimin icindeki gecis (所罗门 ⊂ 所罗门帝国) sayilmaz.
    capa = {"格拉西斯": "Glacis", "弗萨克": "Feysac", "水仙花街": "Nergis", "所罗门": "Solomon"}
    zh = "格拉西斯先生。不像北边的弗萨克帝国。所罗门帝国的后裔。水仙花街。格拉西斯。"
    en = "Mr. Glacis. Unlike the Frosac Empire. The Solomon Empire. Daffodil Street. Glacis."
    solomon = _t("Solomon İmparatorluğu", "Solomon Empire", "所罗门帝国",
                 kategori="words.md › Nations")
    es = H.terimleri_bul(zh, en, [solomon], ["所罗门帝国"])
    korpus = _korpus(kucuk={"empire"}, orta={"Glacis", "Feysac", "Solomon"})
    assert H.capa_adlari(zh, en, capa, es, korpus) == [
        ("Glacis", "格拉西斯", 2, False),
        ("Feysac", "弗萨克", 1, True),  # Ingilizce "Frosac" yazmis
    ]


def test_ses_dizisindeki_durma_harfi_adi_kesmez():
    # 56: 里 ve 内 hem durma hem ses harfi; 特里斯 斯'ye kesilip dusuyordu.
    # 父亲韦恩'in anlamli on eki yuzunden Wayne hic eslesmiyordu.
    def adlar(zh):
        return {a.ad for a in H.zh_adaylari(zh, (set(), set()))}

    assert adlar("而特里斯先生鼓舞我们") == {"特里斯"}
    assert adlar("安娜的父亲韦恩先生惊愕反问道") == {"韦恩"}
    assert adlar("南方的费内波特先生") == {"费内波特"}
    assert adlar("这里安娜小姐笑了") == {"安娜"}  # kenardaki 里 gecilmez
    assert adlar("老尼尔先生") == {"老尼尔"}  # butunu sesle cevrilmis: dokunulmaz


def test_bilinen_anahtarin_koku_yeni_bilesikte():
    # 56 ¶59: 费内波特王国, Feynapotter Yaylası Kahvesi'nin (费内波特高原咖啡) koku.
    sahipler = {
        "费内波特高原咖啡": ("Feynapotter Yaylası Kahvesi", "Feynapotter Plateau Coffee"),
        "鲁恩王国": ("Loen Krallığı", "Kingdom of Loen"),
    }
    zh, en = _hizali("鲁恩王国不像南方的费内波特王国。",
                     "The Loen Kingdom was unlike the Feynapotter Kingdom.")
    aday = H.Aday("Feynapotter Kingdom", 1, [en.index("Feynapotter")], "en")
    [k] = H.kok_isabetleri(zh, sahipler, [aday], len(en))
    assert (k.parca, k.sahip, k.en_es) == (
        "费内波特", "Feynapotter Yaylası Kahvesi", "Feynapotter Kingdom")


def test_mertebe_adi_siradan_anlamda_not_alir():
    # 56 ¶13: 水手 (Denizci, Mertebe 9) siradan "denizci" anlaminda geciyor.
    t = _t("Denizci", "Sailor", "水手", kategori="Aşkın Yolları", yol="Denizci Yolu", seviye=9)
    zh = "水手更是只剩下原本的三分之一。他成为了“水手”。"
    e = H.terimleri_bul(zh, None, [t], ["水手"])[0]
    md = "\n".join(H._terim_satirlari(e, zh, False))
    assert "tırnaklı ×1, tırnaksız ×1" in md and "küçük harf" in md


def test_cumle_basindaki_thank_god_aday_degildir():
    # 56 ¶17, ¶20
    en = ("Tears welled up. Thank God, praise be to God, He prevented it. "
          "We came back. Thank God for letting me see you. Mr. Tris led us.")
    korpus = _korpus(kucuk={"thank", "god", "tears", "praise"}, orta={"Tris"})
    adaylar = {a.ad for a in H.aday_adlar(en, set(), sozcukler=korpus)}
    assert "Thank God" not in adaylar and "Tris" in adaylar


def test_yalniz_baslikta_gecen_tek_kelime_dokume_girmez():
    # 56: baslik "Escape from the Sea"
    a = H.Aday("Escape", 1, [0], "en", "başlık")
    md = H.yaz_dokum(56, None, "Escape from the Sea\nText.", [], [], [a], [], [], 55)
    assert "Escape" not in md


def test_tirnakli_ifadenin_tirnaksiz_gecisleri_ayri_sayilir():
    # 56 ¶12, ¶15: 英雄 ×3, yalniz biri tirnakli.
    zh = "依然有英雄出现。那位“英雄”，自称特里斯的英雄。"
    [a] = [x for x in H.zh_adaylari(zh, (set(), set())) if x.ad == "英雄"]
    assert (a.sayi, a.tirnakli) == (3, 1)
    md = H.yaz_dokum(56, zh, None, [], [], [], [a], [], 55)
    assert "tırnaklı ×1, öteki geçişler tırnaksız" in md


# ------------------------------------------------------------------
# 1-56 dogrulamasinda gorulen hatalar


def test_tarot_uyesi_kod_adiyla_aranir_sahibinin_adiyla_degil():
    # sozluk: terim "Yıldız (The Star)", ingilizce "Leonard Mitchell" (sahibi).
    # Dokum "Yıldız ← Leonard Mitchell"i yerlesmis terim diye veriyordu.
    t = _t("Yıldız", "Leonard Mitchell", kategori="Tarot Cemiyeti",
           en_ham="Leonard Mitchell", ham={"terim": "Yıldız (The Star)"})
    assert H.terimleri_bul(None, "Leonard Mitchell smiled at Klein.", [t], []) == []
    e = H.terimleri_bul(None, "Then The Star spoke first.", [t], [])
    assert [(x.terim.tr, x.nasil) for x in e] == [("Yıldız", "en")]


def test_yayim_cumle_basinda_buyuk_yazilan_kucuk_terim():
    class B:
        def __init__(self, no, metin):
            self.no, self.metin = no, metin

    baston = _t("baston", "cane", "手杖", kategori="words.md › Objects")
    kahin = _t("Kâhin", "Seer", "占卜家", kategori="Kâhin Yolu")
    kahin_k = _t("kâhin", "fortune-teller", "占卜师", kategori="words.md › Mysticism")
    es = [H.Eslesme(baston, "zh", 1, 0), H.Eslesme(kahin_k, "zh", 1, 0)]
    bolumler = [B(30, "Baston elindeydi."), B(31, "Kâhin güldü.")]
    H.yayim_kullanimi(es, bolumler, 56, H.harf_kardesleri([baston, kahin, kahin_k]))
    assert es[0].yayim == [30]
    assert es[1].yayim == []  # Kâhin baska bir terimdir: kâhin katlanmaz


def test_kaynak_bir_kez_bolum_bolum_hazirlanir():
    # Toplu calisma (hazirla_dogrula) icin: korpus bir kez, bolumler ayri ayri.
    kehanet = _t("kehanet", "divination", "占卜", kategori="words.md › Mysticism")
    kay = H.Kaynak(
        terimler=[kehanet], salahiyetler=[], zh_hepsi=["占卜"],
        zh_bolumler={1: lotm.Bolum(1, "他开始占卜。", "zh")},
        en_bolumler={1: lotm.Bolum(1, "He began the divination.", "en")},
        tr_bolumler=[lotm.Bolum(1, "Kehanete başladı.", "tr")],
        sozcukler=frozenset(), capa={},
    )
    h = H.hazirla_bolum(1, kay)
    assert [(e.terim.tr, e.nasil, e.sayi) for e in h.eslesmeler] == [("kehanet", "zh", 1)]
    assert h.son_yayim == 1 and H.hazirla_bolum(2, kay) is None
