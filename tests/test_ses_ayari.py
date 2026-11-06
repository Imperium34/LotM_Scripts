# -*- coding: utf-8 -*-
"""ses_ayari.py -- ek uyumu, anlati secimi, sablon doruk ayristirma, uygulama."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ses_ayari as A  # noqa: E402
import sonra as S  # noqa: E402


def test_ek_uyumu():
    ornek = [("durum", "vaziyet", "da", "te"), ("durum", "vaziyet", "undaki", "indeki"),
             ("durum", "vaziyet", "daydı", "teydi"), ("bilgi", "malumat", "sini", "ını"),
             ("bilgi", "malumat", "nin", "ın"), ("bilgi", "malumat", "yle", "la"),
             ("bilgi", "malumat", "ydi", "tı"), ("soruşturma", "tahkikat", "sı", "ı"),
             ("eksik", "noksan", "ti", "dı"), ("eksik", "noksan", "liği", "lığı"),
             ("önem", "ehemmiyet", "siz", "siz"), ("yaklaşık", "takriben", "", "")]
    for eski, yeni, ek, beklenen in ornek:
        assert A.ek_cevir(eski, yeni, ek) == beklenen, (eski, ek)
    # Fiil/yapim ekleri ve zarfa gelen ek cevrilmez.
    for eski, yeni, ek in [("bilgi", "malumat", "sayar"), ("bilgi", "malumat", "lendirdi"),
                           ("önem", "ehemmiyet", "sedi"), ("soruşturma", "tahkikat", "cı"),
                           ("yaklaşık", "takriben", "la")]:
        assert A.ek_cevir(eski, yeni, ek) is None, (eski, ek)


KURAL = {"ozdes": {"durum": "vaziyet", "bilgi": "malumat"}, "ozdes_istisna": ["bilgin"]}


def test_yalniz_anlati_ve_birebir():
    metin = ("---\ntitle: x\n---\n\n"
             "Durum buydu. \"Durum kötü,\" dedi bilgin.\n\n"
             "_Bu durum da ne?_ Klein bilgiyi not etti.\n\n"
             "Durum buydu.")
    out = A.taban_adaylari(metin, KURAL, donmus=[])
    # ¶1'deki "Durum buydu." metinde iki kez geciyor: birebir kurali eler.
    # Diyalog, ic ses ve 'bilgin' atlanir.
    assert [(x["p"], x["eski"], x["yeni"]) for x in out] == [
        (2, "Klein bilgiyi not etti.", "Klein malumatı not etti.")]


def test_taban_secimi_yayilir_ve_tekrari_sinirlar():
    ad = [{"p": p, "eski": f"c{p}", "donem": "vaziyet"} for p in range(1, 40)]
    sec = A.taban_sec(ad, 5, 40)
    assert len(sec) == 2  # ayni donem sozcugu en cok iki kez
    ad += [{"p": p, "eski": f"m{p}", "donem": "malumat"} for p in range(1, 40)]
    sec = A.taban_sec(ad, 4, 40)
    assert len(sec) == 4 and min(b["p"] - a["p"] for a, b in zip(sec, sec[1:])) >= 2


TAHSIS = """- **Gotik sözcük tahsisi:** iki doruk. Birincisi ¶37–¶39, kutudaki gümbürtü: en çok üç gotik sözcük; ¶39'daki 'korkunç bir şey' kaynağındır. İkincisi ¶74–¶79, 2-049'un ortaya çıkışı: en çok dört; yük anatomik ayrıntıdadır.
  - **Aç bırakılacak bölge:** ¶1–¶36. Burada gotik sıfırdır.
  - Eşik ¶80'dir: mühür kalkar; burada en fazla bir gotik sözcük.
  - ¶82–¶84 ham detaydır, gotik sözcük almaz. Bölüm toplamı en fazla beş.
  - **Duygusal doruk ¶90–¶92'dir ve sade kalır.**
- **Algı fiili yığılması:** ¶5'te en fazla iki kez."""


def test_doruk_ayristirma():
    t = A.tahsis_bolumu("# E\n\n" + TAHSIS + "\n")
    assert "Algı fiili" not in t
    assert [(d["bas"], d["son"], d["butce"]) for d in A.doruklar(t)] == [
        (37, 39, 3), (74, 79, 4), (80, 80, 1)]


def test_doruk_maddeleri_birebir():
    metin = "---\nt: x\n---\n\nKoku yayıldı.\n\nKapı açıldı. Koku yayıldı."
    cikti = ('```json\n{"doruklar": [{"aralik": "¶1–¶2", "uyum": "tamam", "oneriler": ['
             '{"grup": 2, "eski": "Kapı açıldı.", "yeni": "Kapı tekinsizce açıldı.", "neden": "x"},'
             '{"grup": 1, "eski": "Koku yayıldı.", "yeni": "Ufunet yayıldı.", "neden": "y"}]}]}\n```')
    m, b = A.doruk_maddeleri(cikti, metin)
    assert [(x["p"], x["eski"]) for x in m] == [(2, "Kapı açıldı.")]
    assert "2 kez" in b[0]["not"]


def test_kararlar_yedekle_ve_uygula(tmp_path):
    dosya = tmp_path / "0099.md"
    dosya.write_text("---\nt: x\n---\n\nDurum buydu.\n\nBilgi yoktu.\n", encoding="utf-8")
    klasor = tmp_path / "Ch_99"
    klasor.mkdir()
    karar = [{"p": 1, "sinif": "KARAR", "kaynak": ["ses_ayari taban"], "kural": "ses_ayari dönem tabanı durum→vaziyet",
              "eski": "Durum buydu.", "yeni": "Vaziyet buydu.", "neden": ""},
             {"p": 2, "sinif": "KARAR", "kaynak": ["ses_ayari taban"], "kural": "ses_ayari dönem tabanı bilgi→malumat",
              "eski": "Bilgi yoktu.", "yeni": "Malumat yoktu.", "neden": ""}]
    inc = S.inceleme_yaz(99, [], karar, [], kuru=False)
    inc = inc.replace("[ ] kabul   [ ] ret   [ ] hep", "[x] kabul   [ ] ret   [ ] hep", 1)
    inc = inc.replace("[ ] kabul   [ ] ret   [ ] hep", "[ ] kabul   [x] ret   [x] hep", 1)
    (klasor / "inceleme.md").write_text(inc, encoding="utf-8")
    eski_yedek, eski_defter = A.YEDEK, S.KARARLAR
    A.YEDEK, S.KARARLAR = tmp_path / "yedek", tmp_path / "kararlar.md"
    try:
        assert A.kararlari_isle(99, dosya, klasor, kuru=True).startswith("kuru: 1 uygulandı")
        assert "Durum buydu." in dosya.read_text(encoding="utf-8")
        sonuc = A.kararlari_isle(99, dosya, klasor, kuru=False)
        assert sonuc.startswith("1 uygulandı, 1 kalıcı karar")
        assert "Vaziyet buydu." in dosya.read_text(encoding="utf-8")
        assert "Bilgi yoktu." in dosya.read_text(encoding="utf-8")
        yedek = list((tmp_path / "yedek").rglob("0099.md"))
        assert len(yedek) == 1 and "Durum buydu." in yedek[0].read_text(encoding="utf-8")
        assert "ret · ses_ayari dönem tabanı bilgi→malumat" in S.KARARLAR.read_text(encoding="utf-8")
        assert A.kararlari_isle(99, dosya, klasor, kuru=False).startswith("zaten")
    finally:
        A.YEDEK, S.KARARLAR = eski_yedek, eski_defter
