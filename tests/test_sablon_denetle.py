# -*- coding: utf-8 -*-
"""sablon_denetle.py -- sablonun karar tablolari butun kaynaklara karsi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ayrilmis as AY  # noqa: E402
import lotm  # noqa: E402
import sablon_denetle as SD  # noqa: E402


def _t(tr, en=None, zh=None, kategori="Temel Kavramlar", **kw):
    return lotm.Terim(tr=tr, en=en, en_ham=kw.pop("en_ham", en), zh=zh, kategori=kategori, **kw)


def _sablon(a1=(), a2=(), b=()):
    satir = lambda h: "| " + " | ".join(h) + " |"
    md = ["### A.1 Yerleşik terimler (değiştirilemez)", "",
          "| İngilizce | Türkçe | Kullanım notu |", "| --- | --- | --- |"]
    md += [satir(r) for r in a1]
    md += ["", "### A.2 Bu bölümde karara bağlanan özel adlar", "",
           "| İngilizce | Türkçe | Etiket | Not |", "| --- | --- | --- | --- |"]
    md += [satir(r) for r in a2]
    md += ["", "## B. DONDURULAN SATIRLAR", "",
           "| İngilizce | Türkçe (dondurulmuş) | Bölümdeki geçiş sayısı | Not |",
           "| --- | --- | --- | --- |"]
    md += [satir(r) for r in b]
    return "\n".join(md) + "\n"


def _kaynak(terimler=(), metinler=None, sablonlar=None, ayrilmis=()):
    return SD.Kaynaklar(terimler=list(terimler), salahiyetler=[], ayrilmis=list(ayrilmis),
                        metinler=metinler or {}, sablonlar=sablonlar or {}, yayim=[])


def _bulgular(md, kay):
    return [(b.seviye, b.bolum, b.mesaj) for b in SD.denetle(md, kay)[0]]


def test_yerlesik_denilen_karar_sozlukle_celisirse_hata():
    # Gercek kaymalar (eski sablonlar): Tarot Kulübü; sapka farki da bir karardir.
    kay = _kaynak([_t("Tarot Cemiyeti", "The Tarot Club"),
                   _t("Ruhanî Âlem", "Spirit World")])
    md = _sablon(a1=[("Tarot Club", "Tarot Kulübü", "—"), ("Spirit World", "Ruhanî Alem", "—")])
    b = _bulgular(md, kay)
    assert [x[0] for x in b if "sözlükte bu İngilizcenin" in x[2]] == ["HATA", "HATA"]


def test_govde_ve_cekim_bicimi_ayni_karardir():
    kay = _kaynak([
        _t("Kehanet yöntemi", "divination method"),
        _t("Şirazesini Yitirmek", "Losing Control"),
        _t("iki tekerlekli fayton", "two-wheeled carriage", kategori="words.md › Transport"),
        _t("Ruhanî sarkaç", "spirit pendulum", kategori="words.md › Objects", arama_adi=["sarkaç"]),
    ], metinler={"words.md": "kehanet yöntemi şirazesini yitirmek iki tekerlekli fayton sarkaç"})
    md = _sablon(a1=[("divination method", "kehanet yöntem-", "—"),
                     ("losing control", "şirazesini yitir-", "—"),
                     ("two-wheeled carriage", "tekerlekli fayton", "—"),
                     ("spirit pendulum", "sarkacı", "—")])
    assert not [x for x in _bulgular(md, kay) if "sözlükte bu İngilizcenin" in x[2]]


def test_ad_kod_adi_kaydina_baglanmaz_siradan_sozcuk_uyaridir():
    kay = _kaynak([
        _t("Yıldız", "Star", kategori="Tarot Cemiyeti", en_ham="Star (Leonard Mitchell)"),
        _t("dava evrakı", "case file", kategori="words.md › Police",
           en_ham="case file / materials"),
    ], metinler={"x": "leonard mitchell malzeme"})
    md = _sablon(a1=[("Leonard Mitchell", "Leonard Mitchell", "—"), ("materials", "malzeme", "—")])
    b = [x for x in _bulgular(md, kay) if "sözlükte bu İngilizcenin" in x[2]]
    assert [x[0] for x in b] == ["UYARI"] and "dava evrakı" in b[0][2]


def test_yerlesik_denilen_ama_hicbir_yerde_olmayan():
    kay = _kaynak(metinler={"Side_Character_Maps.md": "Tris: kurtarıcı"})
    md = _sablon(a1=[("Mr. Tris", "Bay Tris / Tris", "—"), ("bronze long table", "uzun tunç masa", "—")])
    b = [x for x in _bulgular(md, kay) if "hiçbir yerde" in x[2]]
    assert len(b) == 1 and "uzun tunç masa" in b[0][2]  # "Bay Tris": hitap atilir


def test_yeni_denilen_zaten_var_ya_da_ayrilmis_sozcuk_iceriyor():
    kay = _kaynak(
        [_t("Sezar Limanı", "Caesar Port", kategori="words.md › Cities")],
        ayrilmis=[AY.Ayrilmis("Gemici", "mertebe", "Denizci Yolu 7", "Seafarer"),
                  AY.Ayrilmis("falcı", "yasak", "kâhin", not_='"falcı" kullanılmaz')],
    )
    md = _sablon(a2=[("Caesar Pier", "Sezar Limanı", "[YENİ]", "—"),
                     ("Seafarers' Guild", "Gemici Loncası", "[YENİ]", "—"),
                     ("fortune-teller", "falcı", "[TEREDDÜT]", "—")],  # tereddut: denetlenmez
               b=[("the fortune-teller said", "falcının dediği", "1", "—")])
    b = _bulgular(md, kay)
    assert any(x[1] == "A.2" and "sözlükte zaten var: Sezar Limanı" in x[2] for x in b)
    assert any(x[1] == "A.2" and "'Gemici' ayrılmış sözcük" in x[2] for x in b)
    assert any(x[1] == "B" and "'falcının' words.md'de yasaklı" in x[2] for x in b)  # ekli bicim
    assert not any(x[1] == "A.2" and "falcı" in x[2] for x in b)


def test_onceki_sablonla_kayma_gecici_ve_aynen_haric():
    onceki = _sablon(
        a1=[("Klein / Benson", "aynen", "—"), ("divinity / gods", "ilahlar", "—")],
        a2=[("crystal ball", "billur küre [GEÇİCİ]", "[YENİ]", "—")],
        b=[("Praise the Lady.", "Tanrıçamıza hamdolsun.", "1", "—")],
    )
    kay = _kaynak(sablonlar={31: onceki})
    md = _sablon(
        a1=[("Klein / Benson", "Klein / Benson", "—"), ("divinity / gods", "ilah", "—")],
        a2=[("crystal ball", "kristal küre", "[YENİ]", "—")],
        b=[("Praise the Lady.", "Ulu Ece'ye medholsun.", "1", "—")],
    )
    b = [x for x in _bulgular(md, kay) if "aynı İngilizceye" in x[2]]
    assert len(b) == 1 and b[0][1] == "B" and "Ch_31" in b[0][2]


def test_es_anlamli_sozluk_bicimleri_kayma_sayilmaz():
    # words.md: "İlahlar Çağı / Dördüncü Çağ" ayni kayit
    kay = _kaynak([_t("İlahlar Çağı", "Fourth Epoch", kategori="words.md › Cosmology",
                      arama_adi=["Dördüncü Çağ"])],
                  sablonlar={35: _sablon(a1=[("Fourth Epoch", "Dördüncü Çağ", "—")])})
    md = _sablon(a1=[("Fourth Epoch", "İlahlar Çağı", "—")])
    assert not [x for x in _bulgular(md, kay) if "aynı İngilizceye" in x[2]]


def test_ingilizce_iki_cince_terimi_birlestirince_hata_yok():
    # 61: kaynak 深眠花 (uyku çiçeği); İngilizce 月亮花'ya da "Moon flower" der.
    terim = _t("mehtap çiçeği", "Moon flower", zh="月亮花")
    md = _sablon(a1=[("Moon flower (¶18)", "uyku çiçeği", "—")])
    kay = SD.Kaynaklar(terimler=[terim], salahiyetler=[], ayrilmis=[], metinler={},
                       sablonlar={}, yayim=[], zh_metin="“深眠花啊，属于红月的草药")
    assert not [x for x in _bulgular(md, kay) if "sözlükte bu İngilizcenin" in x[2]]
    # Cince metin yoksa ya da terimin Cincesi bolumde geciyorsa eski davranis.
    for zh_metin in ("", "月亮花"):
        kay = SD.Kaynaklar(terimler=[terim], salahiyetler=[], ayrilmis=[], metinler={},
                           sablonlar={}, yayim=[], zh_metin=zh_metin)
        assert [x[0] for x in _bulgular(md, kay) if "sözlükte bu İngilizcenin" in x[2]] == ["HATA"]


def test_satirdaki_cince_anahtardir():
    # 55: 占卜师 falcı, 占卜家 kâhin; ikisi de bölümde geçer, İngilizcesi fortune-teller.
    kay = SD.Kaynaklar(terimler=[_t("falcı", "fortune-teller", zh="占卜师")], salahiyetler=[],
                       ayrilmis=[], metinler={}, sablonlar={}, yayim=[], zh_metin="占卜师 占卜家")
    md = _sablon(a1=[("fortune-teller (占卜家)", "kâhin", "—")])
    assert not [x for x in _bulgular(md, kay) if "sözlükte bu İngilizcenin" in x[2]]
    md = _sablon(a1=[("fortune-teller (占卜师)", "kâhin", "—")])
    assert [x for x in _bulgular(md, kay) if "sözlükte bu İngilizcenin" in x[2]]


def test_onceki_sablon_baska_cince_ise_kayma_degil():
    eski = _sablon(a1=[("symbol (符号)", "sembol", "—")])
    kay = _kaynak(metinler={"x": "simge sembol"}, sablonlar={59: eski})
    yeni = _sablon(a1=[("symbol (象征)", "simge", "—")])
    assert not [x for x in _bulgular(yeni, kay) if "aynı İngilizceye" in x[2]]
    yeni = _sablon(a1=[("symbol", "simge", "—")])  # Cincesiz: Ingilizceye duser
    assert [x for x in _bulgular(yeni, kay) if "aynı İngilizceye" in x[2]]


def test_onceki_karar_bolumde_gecmeyen_cince_terimin_ise_kayma_degil():
    eski = _sablon(a2=[("Moon flower", "mehtap çiçeği", "[YENİ]", "—")])
    kw = dict(terimler=[_t("mehtap çiçeği", "Moon flower", zh="月亮花")], salahiyetler=[],
              ayrilmis=[], metinler={}, sablonlar={51: eski}, yayim=[])
    yeni = _sablon(a1=[("Moon flower", "uyku çiçeği", "—")])
    kay = SD.Kaynaklar(zh_metin="深眠花啊", **kw)
    assert not [x for x in _bulgular(yeni, kay) if "aynı İngilizceye" in x[2]]
    kay = SD.Kaynaklar(zh_metin="月亮花", **kw)
    assert [x for x in _bulgular(yeni, kay) if "aynı İngilizceye" in x[2]]


def test_cince_yan_dosyadan_okunur(tmp_path):
    yan = tmp_path / "Ch_55_zh.tsv"
    yan.write_text("# İngilizce\tÇince\nfortune-teller\t占卜家\nhoroscope / constellation\t星座\n",
                   encoding="utf-8")
    zh_yan = SD.zh_yan_oku(yan)
    assert zh_yan == {"fortune-teller": ["占卜家"], "horoscope": ["星座"], "constellation": ["星座"]}
    assert SD.zh_yan_yolu(tmp_path / "Ch_55.md") == yan
    kay = SD.Kaynaklar(terimler=[_t("falcı", "fortune-teller", zh="占卜师")], salahiyetler=[],
                       ayrilmis=[], metinler={}, sablonlar={}, yayim=[], zh_metin="占卜师 占卜家")
    md = _sablon(a1=[("fortune-teller", "kâhin", "—")])
    assert [x for x in _bulgular(md, kay) if "sözlükte bu İngilizcenin" in x[2]]
    b = SD.denetle(md, kay, zh_yan)[0]
    assert not [x for x in b if "sözlükte bu İngilizcenin" in x.mesaj]


def test_onceki_sablonun_yan_dosyasi_da_okunur():
    eski = _sablon(a1=[("symbol", "sembol", "—")])
    kay = SD.Kaynaklar(terimler=[], salahiyetler=[], ayrilmis=[], metinler={"x": "simge sembol"},
                       sablonlar={59: eski}, zh_yanlar={59: {"symbol": ["符号"]}}, yayim=[])
    b = SD.denetle(_sablon(a1=[("symbol", "simge", "—")]), kay, {"symbol": ["象征"]})[0]
    assert not [x for x in b if "aynı İngilizceye" in x.mesaj]


def test_bicim_esit_govde_tire_mastar():
    for a, b in [("işaret et-", "işaret etmek"), ("niyaz et", "niyaz etmek"), ("ol-", "olmak")]:
        assert SD.bicim_esit(a, b), (a, b)
