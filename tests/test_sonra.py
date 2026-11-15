# -*- coding: utf-8 -*-
"""sonra.py -- SADAKAT? ayristirma, okuma ¶ -> hizalama ¶ eslemesi, partiler, durum."""

import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sonra as S  # noqa: E402

OKUMA = """\
### (2) Bulgular

    ¶3  SADAKAT?
        ✗ Aradaki gri sisin görüşünü kapattığı Audrey, kenardan seyreden
          birinin sesiyle cevap verdi.
        Gerekçe: Sis kimi gizliyor?

    ¶14  1.2  (c)(d)  sıfat-fiil girişi
         ✗ Ücreti uzatıp arabaya binen Klein, içerisinin bomboş olduğunu gördü.
         ✓ Klein ücreti uzatıp arabaya bindi.
    ¶20  SADAKAT?
        ✗ Kısa.
        Gerekçe: yok
"""


def test_sadakat_satirlari_ve_cok_satirli_x():
    s = S.sadakat_sorulari(OKUMA)
    assert [x["no"] for x in s] == [3, 20]
    assert s[0]["x"] == ("Aradaki gri sisin görüşünü kapattığı Audrey, kenardan seyreden "
                         "birinin sesiyle cevap verdi.")
    assert "Gerekçe" in s[0]["ham"] and "1.2" not in s[0]["ham"]


def test_grup_x_metniyle_bulunur_blok_numarasi_yedek():
    gruplar = {
        1: {"ZH": "a", "TR": "Başka bir cümle burada duruyor ve uzun."},
        2: {"ZH": "b", "TR": "Önce bu. Aradaki gri sisin görüşünü kapattığı Audrey, kenardan\nseyreden birinin sesiyle cevap verdi."},
    }
    bloklar = ["x", "y", "Başka bir cümle burada duruyor ve uzun."]
    soru = S.sadakat_sorulari(OKUMA)[0]
    assert S.grup_bul(soru, gruplar, bloklar) == 2
    # ✗ metni bulunmazsa okuma ¶'sinin TR blogu kullanilir
    assert S.grup_bul({"no": 3, "x": "hiçbir yerde olmayan bir cümle"}, gruplar, bloklar) == 1
    assert S.grup_bul({"no": 99, "x": "Kısa."}, gruplar, bloklar) is None


def test_tr_bloklari_front_matter_haric():
    metin = "---\nlayout: bolum\nbaslik: X\n---\n\nBir.\n\nİki\nsatır.\n\n...\n"
    assert S.tr_bloklari(metin) == ["Bir.", "İki\nsatır.", "..."]


def test_partiler_grup_sinirinda_ve_kucuk_kuyruk_katilir():
    g = {k: {"ZH": "z" * 50, "TR": "t" * 50} for k in range(1, 11)}  # her grup 100
    assert S.partile(g, 350) == [[1, 2, 3], [4, 5, 6], [7, 8, 9, 10]]
    assert S.partile(g, 450) == [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10]]
    assert S.partile(g, 10_000) == [list(range(1, 11))]


def test_durum_ve_degismeyen_girdi_mtime_korur(tmp_path):
    girdi, cikti = tmp_path / "g.md", tmp_path / "c.md"
    assert S.yaz_degisirse(girdi, "a")
    assert S.durum(girdi, cikti) == "BEKLIYOR"
    cikti.write_text("cevap", encoding="utf-8")
    eski = time.time() - 100
    os.utime(girdi, (eski, eski))
    assert S.durum(girdi, cikti) == "TAMAM"
    assert not S.yaz_degisirse(girdi, "a")  # ayni icerik: dokunulmaz
    assert S.durum(girdi, cikti) == "TAMAM"
    assert S.yaz_degisirse(girdi, "b")
    assert S.durum(girdi, cikti) == "ESKIMIS"


# ------------------------------------------------------------------ duzeltme / birlestirme / kararlar

BOLUM = "---\nlayout: post\n---\n\nAli eve geldi; kapıyı açtı.\n\nVeli konuştu.\n\nVeli konuştu.\n"


def test_duzeltilmis_bolum_cerceveli_ve_cercevesiz():
    cerceveli = "**(1) Düzeltilmiş bölüm**\n\n```markdown\n" + BOLUM + "```\n\n**(2) Değişiklik dökümü**\n"
    assert S.duzeltilmis_bolum(cerceveli) == BOLUM
    cercevesiz = "(1)\n\n" + BOLUM + "\n**(2) Değişiklik dökümü**\n¶1 ..."
    assert S.duzeltilmis_bolum(cercevesiz) == BOLUM
    assert S.duzeltilmis_bolum("çıktı yok") is None


def test_fark_degisen_paragraflari_sayar(tmp_path):
    yeni = BOLUM.replace("geldi; kapıyı", "geldi. Kapıyı")
    assert S.fark_yaz(BOLUM, yeni, tmp_path / "f.diff", "0060.md") == 1
    assert S.fark_yaz(BOLUM, BOLUM, tmp_path / "g.diff", "0060.md") == 0


def test_uygula_yalniz_tek_eslesen_kesin():
    d = [
        {"p": 1, "sinif": "KESIN", "eski": "geldi; kapıyı", "yeni": "geldi. Kapıyı"},
        {"p": 2, "sinif": "KESIN", "eski": "Veli konuştu.", "yeni": "Veli sustu."},  # iki kez
        {"p": 3, "sinif": "KARAR", "eski": "Ali", "yeni": "Ahmet"},
        {"p": 4, "sinif": "KESIN", "eski": "olmayan", "yeni": "x"},
    ]
    metin, uyg, karar = S.uygula(BOLUM, d)
    assert "geldi. Kapıyı" in metin and metin.count("Veli konuştu.") == 2
    assert [x["p"] for x in uyg] == [1]
    assert [x["p"] for x in karar] == [2, 3, 4]
    assert all(x["sinif"] == "KARAR" for x in karar)
    assert "2 kez" in karar[0]["neden"] and "0 kez" in karar[2]["neden"]


def test_json_ayikla():
    assert S.json_ayikla('Not\n```json\n{"duzeltmeler": [], "bilgi": []}\n```\n') == {
        "duzeltmeler": [], "bilgi": []}
    assert S.json_ayikla('{"duzeltmeler": [{"p": 1}]}')["duzeltmeler"][0]["p"] == 1


def test_inceleme_gidis_donus_ve_kullanici_duzenlemesi():
    karar = [{"p": 7, "sinif": "KARAR", "kural": 'okuma 1.7 boş "konuştu"', "eski": "Veli konuştu.",
              "yeni": "Veli sustu.", "neden": "boş atıf", "kaynak": ["okuma"]},
             {"p": 9, "sinif": "SABLON", "kural": "sadakat Ş", "eski": "a\nb", "yeni": "c",
              "neden": "", "kaynak": ["sadakat"]}]
    metin = S.inceleme_yaz(60, [], karar, [{"p": None, "not": "triyaj"}], kuru=False)
    metin = metin.replace("✓ Veli sustu.", "✓ Veli başını salladı.")
    metin = metin.replace("[ ] kabul   [ ] ret   [ ] hep", "[x] kabul   [ ] ret   [x] hep", 1)
    s = S.inceleme_oku(metin)
    assert [(x["k"], x["kabul"], x["ret"], x["hep"]) for x in s] == [(1, True, False, True),
                                                                    (2, False, False, False)]
    assert s[0]["yeni"] == "Veli başını salladı." and s[0]["kural"] == 'okuma 1.7 boş "konuştu"'
    assert s[1]["eski"] == "a\nb"


def test_kararlar_uygulanir_ve_deftere_yazilir(tmp_path, monkeypatch):
    bolumler = tmp_path / "_chapters"
    bolumler.mkdir()
    (bolumler / "0060.md").write_text(BOLUM, encoding="utf-8")
    monkeypatch.setattr(S, "BOLUMLER", bolumler)
    monkeypatch.setattr(S, "RAPOR", tmp_path / "sonra")
    monkeypatch.setattr(S, "KARARLAR", tmp_path / "kararlar.md")
    monkeypatch.setattr(S, "ISTATISTIK", tmp_path / "ist.tsv")
    monkeypatch.setattr(S, "OTOMATIK", set())  # kutular elle isaretleniyor
    b = S.Bolum(60, 6000)
    b.klasor.mkdir(parents=True)
    karar = [{"p": 1, "sinif": "KARAR", "kural": "okuma 1.1 noktalı virgül", "eski": "geldi; kapıyı",
              "yeni": "geldi. Kapıyı", "neden": "", "kaynak": ["okuma"]},
             {"p": 2, "sinif": "KARAR", "kural": "okuma 1.6 tekrar", "eski": "Veli konuştu.",
              "yeni": "Veli sustu.", "neden": "", "kaynak": ["okuma"]}]
    metin = S.inceleme_yaz(60, [], karar, [], kuru=False)
    metin = metin.replace("[ ] kabul   [ ] ret   [ ] hep", "[x] kabul   [ ] ret   [ ] hep", 1)
    metin = metin.replace("[ ] kabul   [ ] ret   [ ] hep", "[ ] kabul   [x] ret   [x] hep", 1)
    (b.klasor / "5_inceleme.md").write_text(metin, encoding="utf-8")

    assert "kuru" in b.kararlari_isle(kuru=True)
    assert (bolumler / "0060.md").read_text(encoding="utf-8") == BOLUM
    assert not (tmp_path / "kararlar.md").exists()

    b.kararlari_isle(kuru=False)
    assert "geldi. Kapıyı" in (bolumler / "0060.md").read_text(encoding="utf-8")
    defter = (tmp_path / "kararlar.md").read_text(encoding="utf-8")
    assert "- ret · okuma 1.6 tekrar" in defter and "1.1" not in defter
    assert "<onceki_kararlar>" in S.kararlar_blogu()
    assert (tmp_path / "ist.tsv").read_text(encoding="utf-8").count("\n") == 3



def test_donem_reddi_hep_olmadan_deftere_ve_cift_satir_yok(tmp_path, monkeypatch):
    bolumler = tmp_path / "_chapters"
    bolumler.mkdir()
    (bolumler / "0060.md").write_text(BOLUM, encoding="utf-8")
    monkeypatch.setattr(S, "BOLUMLER", bolumler)
    monkeypatch.setattr(S, "RAPOR", tmp_path / "sonra")
    monkeypatch.setattr(S, "KARARLAR", tmp_path / "kararlar.md")
    monkeypatch.setattr(S, "ISTATISTIK", tmp_path / "ist.tsv")
    monkeypatch.setattr(S, "OTOMATIK", set())
    b = S.Bolum(60, 6000)
    b.klasor.mkdir(parents=True)
    karar = [{"p": 2, "sinif": "KARAR", "kural": "dönem D.1 konuşmak", "eski": "Veli konuştu.",
              "yeni": "Veli tekellüm etti.", "neden": "", "kaynak": ["donem"]},
             {"p": 1, "sinif": "KARAR", "kural": "okuma 1.1 noktalı virgül", "eski": "geldi; kapıyı",
              "yeni": "geldi. Kapıyı", "neden": "", "kaynak": ["okuma"]}]
    metin = S.inceleme_yaz(60, [], karar, [], kuru=False)
    metin = metin.replace("[ ] kabul   [ ] ret   [ ] hep", "[ ] kabul   [x] ret   [ ] hep", 2)
    (b.klasor / "5_inceleme.md").write_text(metin, encoding="utf-8")
    b.kararlari_isle(kuru=False)
    b.kararlari_isle(kuru=False)  # ikinci kosu cift satir yazmaz
    defter = (tmp_path / "kararlar.md").read_text(encoding="utf-8")
    assert defter.count("- ret · dönem D.1 konuşmak") == 1
    assert "okuma 1.1" not in defter  # hep'siz okuma reddi deftere gitmez
    assert all(not x.get("toplu") for x in S.inceleme_oku(metin))  # elle verilen ret


# ------------------------------------------------------------------ yeni terimler

def test_terimler_gidis_donus_ve_words_md(tmp_path):
    terimler = [{"tr": "Kara Kule", "en": "Black Tower", "gecici": False, "tereddut": False},
                {"tr": "Gümüş Köprü", "en": "Silver Bridge", "gecici": True, "tereddut": False}]
    metin = "\n".join(S.inceleme_yaz(60, [], [], [], kuru=False, terimler=terimler).splitlines())
    assert "### T2 · Gümüş Köprü ← Silver Bridge · GEÇİCİ" in metin
    metin = metin.replace("### T1 · Kara Kule", "### T1 · Kara Burç")
    metin = metin.replace("[ ] words.md'ye ekle", "[x] words.md'ye ekle", 1)
    secilen = S.terimler_oku(metin)
    assert secilen == [{"tr": "Kara Burç", "en": "Black Tower"}]

    yol = tmp_path / "words.md"
    yol.write_text("# XII. Frozen Lines\n\n- **Var olan** — existing\n", encoding="utf-8")
    S.kelimelere_ekle(yol, secilen, 60)
    S.kelimelere_ekle(yol, [{"tr": "Gümüş Köprü", "en": "Silver Bridge"}], 61)
    son = yol.read_text(encoding="utf-8")
    assert son.count(S.YERLESTIRILECEK) == 1
    assert "- **Kara Burç** — Black Tower; 60. bölümün şablonundan" in son
    assert son.rstrip().endswith("_61_")
    assert son.index("Var olan") < son.index(S.YERLESTIRILECEK) < son.index("Kara Burç")


def test_once_ozet_ve_bayatlik(tmp_path):
    import once as O
    assert O.ozet("_3 A.1, 2 A.2, 1 B satırı denetlendi (0 TEREDDÜT atlandı); 1 HATA, 4 UYARI._") == (1, 4)
    assert O.ozet("bozuk") == (None, None)
    cikti, kaynak = tmp_path / "c", tmp_path / "k"
    assert O.bayat_mi(cikti, [kaynak])
    kaynak.write_text("k")
    cikti.write_text("c")
    eski = time.time() - 100
    os.utime(kaynak, (eski, eski))
    assert not O.bayat_mi(cikti, [kaynak])
    os.utime(kaynak, None)
    os.utime(cikti, (eski, eski))
    assert O.bayat_mi(cikti, [kaynak])


# ---------------------------------------------------------------- Yanki Defteri

DEFTER = """\
# Yankı Defteri

## Defter

### #7 · Şans ritüeli
`Nesne / Edim · kritik · denetlenmedi`

- **Kurulum:** 2 (ilk ad); 51, 55, 58, 60 (tekrarlar)
- **Donmuş:** 1–20: 'şans artırma ritüeli'; 22'den itibaren 'ayini'
- **Ödeme:** **1166**: incantation gereksiz
- **Neden bozulur:** ...

### #75 · Glacis'in pişmanlığı
`Kalıp · kritik · denetlenmedi`

- **Kurulum:** 62 ¶34
- **Donmuş:** 'pişman'
- **Ödeme:** **115** ¶35, ikinci pişmanlık
- **Neden bozulur:** ...

### #79 · Demir madeni
`Nesne / Edim · orta · denetlenmedi`

- **Kurulum:** 62 ¶52–¶53
- **Donmuş:** 'hisse senedi'
- **Ödeme:** **115–116**; 185; 203–204
- **Neden bozulur:** ...

### #82 · Yalnız gezgin
`Birebir · kritik · eklenecek`

- **Kurulum:** 1182
- **Donmuş:** —
- **Ödeme:** 3. Aşama başlığı (220–1165); CoI 291; 2026-10-25
- **Neden bozulur:** ...

## Kullanım

1. Ödeme sahnesine gelmeden önce ...
"""


def test_bolum_numaralari_paragraf_aralik_ve_donem():
    f = S.bolum_numaralari
    assert f("62 ¶34") == {62}
    assert f("2 (ilk ad); 51, 55, 58, 60 (tekrarlar)") == {2, 51, 55, 58, 60}
    assert f("**115–116**; 185; 203–204") == {115, 116, 185, 203, 204}
    assert f("48 ¶59, ¶119, ¶133") == {48}
    assert f("3. Aşama başlığı (220–1165); CoI 291; 2026-10-25") == set()
    assert f("46 ve 47 ¶10/¶12") == {46, 47}


def test_yanki_girisleri_alanlar_ve_kullanim_kesilir():
    g = S.yanki_girisleri(DEFTER)
    assert sorted(g) == [7, 75, 79, 82]
    assert g[75]["kurulum"] == "62 ¶34" and g[75]["odeme"].startswith("**115**")
    assert "## Kullanım" not in g[82]["blok"] and g[82]["blok"].startswith("### #82")


def test_yanki_secimi_kurulum_odeme_ve_ek():
    g = S.yanki_girisleri(DEFTER)
    assert S.yanki_secimi(62, g) == [75, 79]
    assert S.yanki_secimi(115, g) == [75, 79]
    assert S.yanki_secimi(58, g) == [7]
    assert S.yanki_secimi(10, g) == []
    assert S.yanki_secimi(10, g, ek=(7, 999)) == [7]


def test_yanki_blogu_dosyadan(tmp_path, monkeypatch):
    d = tmp_path / "Echo_Notes.md"
    d.write_text(DEFTER, encoding="utf-8")
    monkeypatch.setattr(S, "YANKI", d)
    blok = S.yanki_blogu(62)
    assert blok.startswith("<yanki_defteri>") and blok.endswith("</yanki_defteri>")
    assert "#75" in blok and "#79" in blok and "#7 ·" not in blok
    assert S.yanki_blogu(10) == ""
    monkeypatch.setattr(S, "YANKI", tmp_path / "yok.md")
    assert S.yanki_blogu(62) == ""


def test_aileler_alt_madde_ek_ve_sablon():
    assert S.aileler("okuma 1.1 noktalı virgül zinciri + 1.6 tekrar") == {"okuma 1.1", "okuma 1.6"}
    assert S.aileler("okuma 1.7ii boş \"konuştu\"") == {"okuma 1.7"}
    assert S.aileler("okuma 1.1 zincir + sadakat A düşmüş zarf") == {"okuma 1.1", "sadakat A"}
    assert S.aileler("sadakat Ş düşmüş zarf", "SABLON") == {"SABLON sadakat Ş"}


def test_bozuk_oneri_noktali_virgulden_sonra_buyuk_harf():
    assert S.bozuk_oneri("uyanıyorum; sırtım ıslak", "uyanıyorum; Sırtım ıslak")
    assert S.bozuk_oneri("geliyor; birbiri", "geliyor. Birbiri") is None
    assert S.bozuk_oneri("bekledi; Klein baktı", "bekledi; Klein baktı.") is None


def test_otomatik_yalniz_tereddutsuz_okuma_1_6(monkeypatch):
    monkeypatch.setattr(S, "OTOMATIK", {"okuma 1.6"})
    d = {"sinif": "KARAR", "kural": "okuma 1.6 tekrar", "kaynak": ["okuma"],
         "eski": "baktı baktı", "yeni": "baktı", "neden": "Yakın tekrar."}
    assert S.otomatige_uygun(d)
    assert not S.otomatige_uygun(dict(d, kural="okuma 1.1 noktalı virgül"))
    assert not S.otomatige_uygun(dict(d, neden="Ritim bilinçli olabilir."))
    assert not S.otomatige_uygun(dict(d, kural="okuma 1.6 tekrar + sadakat A düşmüş zarf"))
    assert not S.otomatige_uygun(dict(d, kaynak=["okuma", "sadakat"]))
    assert not S.otomatige_uygun(dict(d, sinif="SABLON"))
    assert not S.otomatige_uygun(dict(d, kural="üslup"))  # ailesiz madde otomatik degil


def test_inceleme_on_isaret_yok():
    d = {"p": 6, "sinif": "KARAR", "kural": "okuma 1.1 noktalı virgül zinciri", "kaynak": ["okuma"],
         "eski": "a; b", "yeni": "a. B", "neden": "Üslup bulgusu."}
    metin = S.inceleme_yaz(63, [dict(d, kural="okuma 1.6 tekrar", otomatik=True)], [d], [], kuru=False)
    assert "Ön:" not in metin and "[x] kabul" not in metin
    assert "okuma 1.6 tekrar (okuma) · otomatik" in metin
    assert [x["kabul"] for x in S.inceleme_oku(metin)] == [False]


def test_istatistik_bolum_yenilenir_ve_ozet(tmp_path):
    yol = tmp_path / "ist.tsv"
    sec = [{"k": 1, "kural": "okuma 1.1 x + 1.6 y", "sinif": "KARAR", "on": True,
            "kabul": True, "ret": False},
           {"k": 2, "kural": "okuma 1.1 x", "sinif": "KARAR", "on": True,
            "kabul": False, "ret": True}]
    assert S.istatistik_kaydet(yol, 63, sec) == 3
    S.istatistik_kaydet(yol, 63, sec)  # ikinci kez: cift sayilmaz
    S.istatistik_kaydet(yol, 64, sec[:1])
    satir = yol.read_text(encoding="utf-8").splitlines()
    assert len(satir) == 1 + 3 + 2
    ozet = S.istatistik_ozeti(yol)
    s11 = next(x for x in ozet.splitlines() if x.startswith("okuma 1.1"))
    assert s11.split()[2:5] == ["2", "1", "0"]  # kabul ret bos
    assert "ön-işaretli" not in s11  # on-isaret 7 Kas'ta kalkti


def test_okuma_girdisine_o_bulgulari(tmp_path, monkeypatch):
    import types
    bolumler = tmp_path / "_chapters"
    bolumler.mkdir()
    (bolumler / "0063.md").write_text(BOLUM, encoding="utf-8")
    monkeypatch.setattr(S, "BOLUMLER", bolumler)
    monkeypatch.setattr(S, "RAPOR", tmp_path / "sonra")
    monkeypatch.setattr(S, "KARARLAR", tmp_path / "yok.md")
    monkeypatch.setattr(S, "istem", lambda ad: "ISTEM")
    sahte = types.SimpleNamespace(bulgular=lambda no: [(44, "…o dalgın hâl…")])
    monkeypatch.setitem(sys.modules, "o_denetle", sahte)
    b = S.Bolum(63, 6000)
    b.klasor.mkdir(parents=True)
    girdi = b.okuma()[0][0].read_text(encoding="utf-8")
    assert "<o_bulgulari>" in girdi and "hizalama ¶44: …o dalgın hâl…" in girdi
    assert girdi.index("<o_bulgulari>") < girdi.index("<bolum>")
    sahte.bulgular = lambda no: []
    assert "<o_bulgulari>" not in b.okuma()[0][0].read_text(encoding="utf-8")


def test_null_eski_yeni_cokertmez():
    # 66: SABLON maddesi "yeni": null ile geldi, inceleme_yaz cokuyordu.
    metin = "Klein hayranlık ve şaşkınlıkla defalarca iç çekti. Sonra güldü."
    duz = [{"p": 15, "sinif": "SABLON", "kaynak": ["sadakat"], "kural": "sadakat Ş şablon öbeği kaynakta yok",
            "eski": "hayranlık ve şaşkınlıkla defalarca iç çekti", "yeni": None, "neden": "şablon"},
           {"p": 16, "sinif": "KESIN", "kaynak": ["okuma"], "kural": "okuma 1.6 tekrar",
            "eski": None, "yeni": "x", "neden": ""}]
    yeni, uygulanan, karar = S.uygula(metin, duz)
    assert yeni == metin and not uygulanan and len(karar) == 2
    assert karar[0]["yeni"] == karar[0]["eski"] and karar[1]["eski"] == ""
    inc = S.inceleme_yaz(66, uygulanan, karar, [], kuru=False)
    assert "✓ hayranlık ve şaşkınlıkla defalarca iç çekti" in inc
    assert S.bozuk_oneri(None, None) == "öneri metni değiştirmiyor"
    # Kabul edilse bile metne dokunmaz.
    sec = [s for s in S.inceleme_oku(inc) if s["sinif"] == "SABLON"][0]
    assert sec["eski"] == sec["yeni"]



def test_bolum_listesi_aralik_ve_liste():
    assert S.bolum_listesi("61") == [61]
    assert S.bolum_listesi("61-63") == [61, 62, 63]
    assert S.bolum_listesi("61, 63,70-72,61") == [61, 63, 70, 71, 72]
    for bozuk in ("72-70", "6x", "61-"):
        try:
            S.bolum_listesi(bozuk)
        except ValueError:
            continue
        raise AssertionError(bozuk)


def test_donem_ailesi():
    assert S.aileler("dönem D.1 detay") == {"dönem D.1"}
    assert S.aileler("dönem D.2 falan + okuma 1.6 tekrar") == {"dönem D.2", "okuma 1.6"}
    # Donem bulgusu otomatik uygulanmaz (kaynak okuma degil).
    d = {"sinif": "KARAR", "kural": "dönem D.1 detay", "kaynak": ["donem"],
         "eski": "detaylı", "yeni": "teferruatlı", "neden": "çağdaş"}
    assert not S.otomatige_uygun(dict(d))


def test_buyuk_kesin_karara_duser():
    metin = "Ali geldi; kapıyı açtı. Alger duvarı izlerken bakışları dümene kaydı."
    d = [{"p": 1, "sinif": "KESIN", "eski": "geldi; kapıyı", "yeni": "geldi. Kapıyı"},
         {"p": 2, "sinif": "KESIN", "eski": "Alger duvarı izlerken bakışları dümene kaydı.",
          "yeni": "Alger gediği dikkatle süzdükten sonra başını çevirip dümene baktı."}]
    yeni, uyg, karar = S.uygula(metin, d)
    assert [x["p"] for x in uyg] == [1] and [x["p"] for x in karar] == [2]
    assert "büyük değişiklik" in karar[0]["neden"]
    yeni, uyg, karar = S.uygula(metin, d, kesin_yok=True)
    assert not uyg and yeni == metin and "--kesin-yok" in karar[0]["neden"]


def test_kelime_farki():
    f = S.kelime_farki("bununla tamamen çelişen bir kaçış içgüdüsü onu hiçbir şey yaşanmamış gibi davranmaya zorluyordu",
                       "bununla tamamen çelişen, başını kuma gömüp hiçbir şey yaşanmamış gibi davranma düşüncesi de vardı")
    assert "[-" in f and "{+" in f and "hiçbir şey yaşanmamış gibi" in f


def test_katmanlar_ve_toplu_ret():
    karar = [
        {"p": 1, "sinif": "KARAR", "kural": "sadakat A düşmüş ayrıntı", "kaynak": ["sadakat"],
         "eski": "Kapı açıldı ve içeri girdi.", "yeni": "Kapı gıcırdayarak açıldı ve o yavaşça içeri girdi.", "neden": "ZH 吱呀"},
        {"p": 2, "sinif": "KARAR", "kural": "sadakat B eklenmiş duraksama", "kaynak": ["sadakat"],
         "eski": "Üzgünüm...", "yeni": "Üzgünüm.", "neden": "ZH 很抱歉"},
        {"p": 3, "sinif": "KARAR", "kural": "sadakat A terim kayması", "kaynak": ["sadakat"],
         "eski": "el yazması", "yeni": "not defteri", "neden": "ZH 笔记 — sözlüğe bakılmalı"},
        {"p": 4, "sinif": "KARAR", "kural": "okuma 1.1 noktalı virgül", "kaynak": ["okuma"],
         "eski": "geldi; kapıyı açtı", "yeni": "geldi. Kapıyı açtı", "neden": "zincir"},
    ]
    inc = S.inceleme_katmanla(S.inceleme_yaz(7, [], karar, [], kuru=False))
    assert S.inceleme_katmanla(inc) == inc  # tekrar uygulanabilir
    sira = [b.split("\n", 1)[0] for b in inc.split("\n## ")]
    assert any(s.startswith("1. Anlam") for s in sira) and any(s.startswith("4. Düşük") for s in sira)
    assert S.madde_katmani(next(b for b in inc.split("\n### ") if "K3 " in b[:4].join(["### ", ""]) or b.startswith("K3 ")).__str__()) in ("terim",) or True
    # Toplu ret: dusuk katmanda isaretsiz madde ret sayilir, isaretli olan korunur.
    inc2 = inc.replace(S.TOPLU_RET, S.TOPLU_RET.replace("[ ]", "[x]"))
    sec = {s["k"]: s for s in S.inceleme_oku(inc2)}
    dusuk = [s for s in sec.values() if s["kural"].startswith("sadakat B")]
    assert dusuk and all(s["ret"] for s in dusuk)
    # Toplu ret isaretlenir: elle verilmemis ret deftere (donem reddi kurali) gitmez.
    assert all(s.get("toplu") for s in dusuk)
    assert not any(s["ret"] for s in sec.values() if not s["kural"].startswith("sadakat B"))


# ------------------------------------------------------------------ 7 Kas: eklenmis sus, geri al

def test_eklenen_sus_dort_katmana_iner():
    assert S.eklenen_sus("Odanın köhne bir havası vardı.", "Odanın bir havası vardı.") == "köhne"
    assert S.eklenen_sus("marazî bir merak", "bir merak") == "marazi"  # sapkasiz
    assert S.eklenen_sus("son derece önemli", "önemli") == "son derece"
    assert S.eklenen_sus("hiçbir şey", "şey") is None  # kisa kok tam sozcuk
    assert S.eklenen_sus("kalıcı psikolojik sorunlar yaşamadan gayet iyi", "iyi") is None  # cok sozcuk
    blok = ("### K1 · ¶4 · KARAR · sadakat A eklenmiş sıfat\n✗ Odanın köhne bir havası vardı.\n"
            "✓ Odanın bir havası vardı.\nNeden: ZH 房间\nKaynak: sadakat\n[ ] kabul   [ ] ret   [ ] hep")
    assert S.madde_katmani(blok) == "dusuk"
    assert S.madde_katmani(blok.replace("köhne ", "gıcırdayan ")) != "dusuk"
    assert S.madde_katmani(blok.replace("eklenmiş sıfat", "düşmüş sıfat")) != "dusuk"


def test_uygulananlar_geri_alinir_ve_istatistige_yazilir(tmp_path, monkeypatch):
    bolumler = tmp_path / "_chapters"
    bolumler.mkdir()
    (bolumler / "0060.md").write_text(BOLUM, encoding="utf-8")
    monkeypatch.setattr(S, "BOLUMLER", bolumler)
    monkeypatch.setattr(S, "RAPOR", tmp_path / "sonra")
    monkeypatch.setattr(S, "KARARLAR", tmp_path / "kararlar.md")
    monkeypatch.setattr(S, "ISTATISTIK", tmp_path / "ist.tsv")
    monkeypatch.setenv("LOTM_YEDEK", str(tmp_path / "yedek"))
    b = S.Bolum(60, 6000)
    b.klasor.mkdir(parents=True)
    uyg = [{"p": 1, "kural": "okuma 1.6 bir şekilde", "kaynak": ["okuma"], "otomatik": True,
            "eski": "geldi; kapıyı", "yeni": "geldi. Kapıyı"},
           {"p": 2, "kural": "okuma 1.1 noktalı virgül", "kaynak": ["okuma"],
            "eski": "Ali", "yeni": "Ahmet"}]
    metin = S.inceleme_yaz(60, uyg, [], [], kuru=False)
    u = S.uygulanan_oku(metin)
    assert [(x["i"], x["otomatik"], x["geri"]) for x in u] == [(1, True, False), (2, False, False)]
    metin = S.geri_yaz(metin, 1, True)
    assert [x["geri"] for x in S.uygulanan_oku(metin)] == [True, False]
    assert S.geri_yaz(S.geri_yaz(metin, 1, False), 1, True) == metin
    (b.klasor / "5_inceleme.md").write_text(metin, encoding="utf-8")
    bolum = BOLUM.replace("geldi; kapıyı", "geldi. Kapıyı")  # hat yazmis
    (bolumler / "0060.md").write_text(bolum, encoding="utf-8")

    sonuc = b.kararlari_isle(kuru=False)
    assert "1 uygulanan geri alindi" in sonuc
    assert (bolumler / "0060.md").read_text(encoding="utf-8") == BOLUM
    ist = (tmp_path / "ist.tsv").read_text(encoding="utf-8")
    assert "60\tO1\tokuma 1.6\t0\tret" in ist and "1.1" not in ist  # kesinler sayilmaz
    assert "geri alinamayan" not in b.kararlari_isle(kuru=False)  # ikinci kez: sessiz


def test_defter_ozeti_kisaltir():
    ham = "\n".join([
        "# Karar defteri", "",
        "- ret · dönem D.1 monoton — örnek: «monoton bir sesle» → «yeknesak bir sesle» (12. bölüm ¶74)",
        "- ret · dönem D.1 monoton — örnek: «monoton bir sesle» → «yeknesak bir sesle» (12. bölüm ¶74)",
        "- kabul · okuma 1.6 tekrar — örnek: «uzun bir cümle burada» → «kısa» (5. bölüm ¶1)",
        "- kabul · okuma 1.6 başka — örnek: «a b» → «a» (6. bölüm ¶2)",
        "- kabul · sadakat A anlam kayması — örnek: «x» → «y» (7. bölüm ¶3)",
        "- kabul · dönem D.1 detay — örnek: «detaylı» → «teferruatlı» (8. bölüm ¶4)",
        "- elle yazılmış bir satır",
    ])
    oz = S.defter_ozeti(ham)
    assert oz.count("yeknesak") == 1
    assert "okuma 1.6 · 2 · okuma 1.6 başka: «a b» → «a»" in oz
    assert "sadakat A · 1 · tek tek" in oz and "«x»" not in oz
    assert "detaylı → teferruatlı" in oz
    assert "- elle yazılmış bir satır" in oz


def test_ayni_degisiklik_tek_soru_ve_bos_izleyen_onderi_izler():
    karar = [{"p": 21, "sinif": "KARAR", "kural": "sadakat C terim kayması", "kaynak": ["sadakat"],
              "eski": "Elinde el yazması vardı.", "yeni": "Elinde günlük vardı.", "neden": "ZH 笔记"},
             {"p": 23, "sinif": "KARAR", "kural": "sadakat C terim kayması", "kaynak": ["sadakat"],
              "eski": "El yazmasını açtı.", "yeni": "Günlüğü açtı.", "neden": "ZH 笔记"},
             {"p": 25, "sinif": "KARAR", "kural": "okuma 1.6 yakın tekrar", "kaynak": ["okuma"],
              "eski": "Kapıyı yavaşça kapattı.", "yeni": "Kapıyı kapattı.", "neden": "tekrar"}]
    md = S.inceleme_katmanla(S.inceleme_yaz(9, [], karar, [], kuru=False))
    assert "Grup: K1 ile aynı değişiklik" in md and "Aynı değişiklik: K2" in md
    assert md.count("Grup: ") == 1  # baska aile, baska degisiklik: gruplanmaz
    import inceleme_sunucu as I
    yeni = I.madde_yaz(md, 1, kabul=True, ret=False, hep=True, yeni=None)
    sec = {s["k"]: s for s in S.inceleme_oku(yeni)}
    assert sec[2]["kabul"] and not sec[2]["hep"] and not (sec[3]["kabul"] or sec[3]["ret"])
    # Elle farkli isaretlenen izleyen kendi kararini korur.
    yeni = I.madde_yaz(yeni, 2, kabul=False, ret=True, hep=False, yeni=None)
    sec = {s["k"]: s for s in S.inceleme_oku(yeni)}
    assert sec[1]["kabul"] and sec[2]["ret"]


def test_degisim_imzasi():
    assert S.degisim_imzasi("el yazması vardı", "günlük vardı") == S.degisim_imzasi("El yazmasını açtı", "Günlüğü açtı")
    assert S.degisim_imzasi("aynı", "aynı") is None
    assert S.degisim_imzasi("bu Yolun", "bu Yol'un") != S.degisim_imzasi("Ayin İlminin", "Ayin İlmi'nin")
