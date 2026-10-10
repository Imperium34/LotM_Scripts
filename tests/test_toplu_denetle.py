# -*- coding: utf-8 -*-
"""
toplu_denetle.terimi_tara -- sentetik, onceden hizalanmis bir onbellek ile.

Bu dosyanin sebebi bir KeyError: ceviri_denetle.tara() vurus kaydina
'hedef_metin_dar' alani eklendi ve siniflandir() onu okumaya basladi, ama
toplu_denetle kendi vurus kayitlarini elle kuruyordu ve alan orada hic
yoktu. Iki uretici, bir sema; biri guncellendi. Artik ikisi de
ceviri_denetle.vurus_kur() kullaniyor ve bu test toplu tarafini
calistirarak semanin yeniden ayrismasini yakalar.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import toplu_denetle as TD  # noqa: E402


def _bolum(no, k_par, h_par, nereye, kayan):
    """Hizalamasi onceden verilmis bir HizalanmisBolum; diske yazmaz."""
    b = TD.HizalanmisBolum(no, "en", "tr", "\n".join(k_par), "\n".join(h_par), k_par, h_par)
    b._sonuc = (nereye, kayan)
    return b


def onbellek():
    k_par = ["The Beyonder arrived.", "Nothing here.", "Another Beyonder spoke."]
    h_par = ["Aşkın geldi.", "Burada bir şey yok.", "Başka biri konuştu."]
    nereye = {0: [0], 1: [1], 2: [2]}
    kayan = {2}  # ucuncu paragraf kaymis bolgede
    return {7: _bolum(7, k_par, h_par, nereye, kayan)}


def test_terimi_tara_calisir_ve_siniflandirir():
    vuruslar = TD.terimi_tara("Beyonder", ["Aşkın"], onbellek(), "en", "tr", duyarsiz=False)
    assert [v["bulunan"] for v in vuruslar] == [["Aşkın"], []]
    assert [v["kayan"] for v in vuruslar] == [False, True]


def test_ozetle_kayan_eslesmeyeni_karantinaya_alir():
    vuruslar = TD.terimi_tara("Beyonder", ["Aşkın"], onbellek(), "en", "tr", duyarsiz=False)
    sayim, eslesmeyen, karantina, tek, komsu = TD.ozetle(vuruslar)
    assert sayim == {"Aşkın": 1}
    assert eslesmeyen == [] and len(karantina) == 1 and tek == 0 and komsu == []


def test_iki_uretici_ayni_semayi_kullanir():
    import ceviri_denetle as CD
    tek = CD.vurus_kur(1, "x", ["a", "b"], [0])
    vuruslar = TD.terimi_tara("Beyonder", ["Aşkın"], onbellek(), "en", "tr", duyarsiz=False)
    # toplu ek alanlar ekleyebilir ama ortak alanlarin hicbirini dusuremez.
    assert set(tek) <= set(vuruslar[0])


def test_tablo_sutunlari_basliga_hizali(capsys):
    kayit = {
        "terim": "Aşkın", "sorgu": "Beyonder", "kategori": "Temel Kavramlar",
        "eski_gorulen": set(), "toplam": 12, "sayim": {"Aşkın": 9},
        "eslesmeyen": [{"bolum": 3, "hedef_metin": "x"}], "karantina": [{}, {}],
        "tek_tarafli": 0, "oran": 0.1,
    }
    TD.satir_yaz([kayit], 100)
    satirlar = [s for s in capsys.readouterr().out.splitlines() if s.strip("─ ")]
    baslik, veri = satirlar[0], satirlar[1]
    # krntn degeri basligin altinda, karsiliklar kendi basliginin altinda
    assert veri[baslik.index("krntn") + 4] == "2"
    assert veri.index("Aşkın×9") == baslik.index("karşılıklar")


def _kayik_onbellek(ikinci_turkce):
    # Bolum 28'in sonundaki durum: kaynak paragraf ¶1'e hizalandi ama Turkce
    # ceviri ayni icerigi iki paragrafa boldugu icin terim ¶2'de duruyor.
    k_par = ["Dunn named the Seer pathway.",
             "Klein recalled Roselle's regret: Apprentice, Marauder, Seer!"]
    h_par = ["Dunn Kâhin yolunu andı.", "_Kâhin mi?_", ikinci_turkce]
    return {28: _bolum(28, k_par, h_par, {0: [0], 1: [1]}, set())}


def test_terim_komsu_paragrafta_ise_eslesmeyen_sayilmaz():
    ob = _kayik_onbellek("Klein pişmanlığı andı: Çırak, Kapkaççı veya Kâhin!")
    v = TD.terimi_tara("Marauder", ["Kapkaççı"], ob, "en", "tr", duyarsiz=False)
    sayim, eslesmeyen, karantina, tek, komsu = TD.ozetle(v)
    assert eslesmeyen == [] and len(komsu) == 1
    assert sayim == {"Kapkaççı": 1}


def test_komsuda_da_yoksa_gercek_bulgu():
    ob = _kayik_onbellek("Klein pişmanlığı andı: Çırak, Yağmacı veya Kâhin!")
    v = TD.terimi_tara("Marauder", ["Kapkaççı"], ob, "en", "tr", duyarsiz=False)
    _s, eslesmeyen, _k, _t, komsu = TD.ozetle(v)
    assert len(eslesmeyen) == 1 and komsu == []
    # ayrinti eslesmeyende hizalanan (dar) paragrafi gosterir
    assert eslesmeyen[0]["hedef_metin_dar"] == "_Kâhin mi?_"


def test_eski_isareti_dar_ekranda_da_gorunur(capsys):
    kayit = {
        "terim": "İlm-i Esrar", "sorgu": "Mysticism", "kategori": "Temel Kavramlar",
        "eski_gorulen": {"mistisizm"}, "toplam": 29,
        "sayim": {"İlm-i Esrar": 25, "mistisizm": 4},
        "eslesmeyen": [], "karantina": [], "komsu": [], "tek_tarafli": 0, "oran": 0.0,
    }
    TD.satir_yaz([kayit], 80)  # karsiliklar sutununa ancak 11 karakter kalir
    satir = [s for s in capsys.readouterr().out.splitlines() if s.startswith("İlm-i")][0]
    assert "⚠" in satir and "mistisizm" in satir


def _tek_bolum(k_par, h_par):
    return {32: _bolum(32, k_par, h_par, {i: [i] for i in range(len(k_par))}, set())}


def test_en_arama_adi_ile_aranir(monkeypatch):
    import lotm
    t = lotm.Terim(tr="Dimağ Beden", en="Heart and Mind Body", kategori="Temel Kavramlar",
                   en_arama_adi=["Body of Heart and Mind"])
    monkeypatch.setattr(lotm, "sozluk_yukle", lambda *a, **k: lotm.Sozluk([t], veri={}))
    (sorgu, *_), = TD.sweep_terimleri("en", "tr")[0]
    assert sorgu == "Body of Heart and Mind"
    ob = _tek_bolum(["Further out will be the Body of Heart and Mind."],
                    ["Daha da dışarıda Dimağ Beden bulunur."])
    v = TD.terimi_tara(sorgu, ["Dimağ Beden"], ob, "en", "tr", duyarsiz=True)
    assert [x["bulunan"] for x in v] == [["Dimağ Beden"]]


def test_etiketteki_slash_alternatifleri_ayri_aranir():
    ob = _tek_bolum(["A scene from the Fog of History."], ["Tarihin Sisi'nden bir sahne."])
    v = TD.terimi_tara("Historical Void / Fog of History", ["Tarihin Sisi"], ob,
                       "en", "tr", duyarsiz=False)
    assert len(v) == 1


def test_duyarli_taramada_kucuk_harfli_gecis_sayilmaz():
    ob = _tek_bolum(["the sequence ended."], ["dizi bitti."])
    assert TD.terimi_tara("Sequence", ["Mertebe"], ob, "en", "tr", duyarsiz=False) == []


def test_ikisi_her_terimi_en_iyi_anahtariyla_tarar(monkeypatch):
    import lotm
    ts = [
        lotm.Terim(tr="kâhya", en="butler", zh="管家", kategori="words.md › X"),   # ikisi de: zh
        lotm.Terim(tr="Ferman", en="Decree", zh="令", kategori="words.md › X"),     # tek karakter: en
        lotm.Terim(tr="bölme", zh="隔断", kategori="words.md › X"),                # yalniz zh
        lotm.Terim(tr="Aşkın", en="Beyonder", kategori="Temel Kavramlar"),         # yalniz en
        lotm.Terim(tr="yalnız ad", kategori="words.md › X"),                       # hicbiri
    ]
    monkeypatch.setattr(lotm, "sozluk_yukle", lambda *a, **k: lotm.Sozluk(ts, veri={}))
    isler, atlanan = TD.isleri_kur("ikisi", "tr")
    hangi = {t.tr: k for k, _s, t, *_ in isler}
    assert hangi == {"kâhya": "zh", "bölme": "zh", "Ferman": "en", "Aşkın": "en"}
    assert atlanan == 1


def test_ikisi_ayni_terimi_tek_satira_indirir(monkeypatch):
    import lotm
    ts = [
        lotm.Terim(tr="Asılmış Adam", en="Hanged Man", kategori="Tarot Cemiyeti"),
        lotm.Terim(tr="Asılmış Adam", en="Hanged Man", zh="倒吊人", kategori="words.md › Tarot"),
        lotm.Terim(tr="Kâhin", en="Seer", kategori="Kâhin Yolu"),
        lotm.Terim(tr="kâhin", en="Seer", kategori="words.md › X"),
    ]
    monkeypatch.setattr(lotm, "sozluk_yukle", lambda *a, **k: lotm.Sozluk(ts, veri={}))
    isler, _ = TD.isleri_kur("ikisi", "tr")
    satirlar = [(k, t.tr, t.kategori) for k, _s, t, *_ in isler]
    assert ("zh", "Asılmış Adam", "words.md › Tarot") in satirlar     # Cince kazanir
    assert ("en", "Kâhin", "Kâhin Yolu") in satirlar                   # esitlikte sozluk
    assert len(satirlar) == 2
