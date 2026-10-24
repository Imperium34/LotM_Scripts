# -*- coding: utf-8 -*-
"""sonra.py -- SADAKAT? ayristirma, okuma ¶ -> hizalama ¶ eslemesi, partiler, durum."""

import os
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
