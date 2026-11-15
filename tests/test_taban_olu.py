# -*- coding: utf-8 -*-
"""
Olu taban satirlari: bicim_denetle.py ve lint/sapka.py. Bir satir hicbir
bulguyu bastirmiyorsa olu; yalniz KAPSAMDAKI satirlar olu sayilir (taranan
dosya, calisan kural). Rapor cikis kodunu degistirmez; --taban-olu-sil yalniz
olu ve kapsamdaki satirlari siler.
"""

import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
for yol in (KOK, KOK / "lint"):
    sys.path.insert(0, str(yol))

import bicim_denetle as B  # noqa: E402
import sapka  # noqa: E402

FM = '---\nlayout: post\ntitle: "Bölüm {n}: X"\n---\n\n'
K01 = "Kapıyı açtı; içeri girdi."          # K01: noktali virgul liste disinda
K01_B = "Pencereyi kapadı; perdeyi çekti."
B03 = '"Gel," dedi.'                      # B03 (HATA): virgulle kapanan replik


def _klasor(tmp_path, metinler):
    kl = tmp_path / "ch"
    kl.mkdir()
    for ad, govde in metinler.items():
        n = int(ad.split(".")[0])
        (kl / ad).write_text(FM.format(n=n) + govde + "\n", encoding="utf-8")
    return kl


def _anahtarlar(kl, ad):
    _p, bulgular, _t = B.dosyayi_denetle(kl / ad, None)
    return [(ad, b.kod, b.alinti) for b in bulgular]


def _taban(tmp_path, *anahtarlar, baslik="# yorum: elle yazilmis baslik\n"):
    t = tmp_path / "taban.tsv"
    t.write_text(baslik + "".join("\t".join(k) + "\n" for k in anahtarlar), encoding="utf-8")
    return t


def _bicim(monkeypatch, capsys, kl, taban, *ek):
    monkeypatch.setattr(sys, "argv", ["bicim_denetle.py", *ek, "--bolumler", str(kl),
                                      "--taban", str(taban)])
    kod = B.main()
    cikti = capsys.readouterr()
    return kod, cikti.out


ANAHTAR = "taban: kapsamdaki"


# ---------------------------------------------------------------- bicim

def test_bicim_canli_satir_olu_degil_ve_satir_yazilmaz(tmp_path, monkeypatch, capsys):
    kl = _klasor(tmp_path, {"0001.md": K01, "0002.md": K01_B})
    k = [x for x in _anahtarlar(kl, "0001.md") if x[1] == "K01"]
    assert k
    t = _taban(tmp_path, *k)
    kod, out = _bicim(monkeypatch, capsys, kl, t)
    assert "tabanda, bastırıldı" in out
    assert ANAHTAR not in out
    kod2, out2 = _bicim(monkeypatch, capsys, kl, t, "--taban-olu")
    assert "yok" in out2.split("ÖLÜ TABAN SATIRLARI")[1] and kod2 == kod


def test_bicim_metin_degisince_olu_olur_ve_listelenir(tmp_path, monkeypatch, capsys):
    kl = _klasor(tmp_path, {"0001.md": K01 + "\n\n" + B03, "0002.md": K01_B})
    eski = _anahtarlar(kl, "0001.md")
    t = _taban(tmp_path, *eski)
    kod0, _ = _bicim(monkeypatch, capsys, kl, t)
    assert kod0 == 0                                  # HATA da tabanda
    # Bolum duzenlendi: ikisinin de cumlesi degisti, ama bulgu yine var.
    (kl / "0001.md").write_text(
        FM.format(n=1) + "Kapıyı yavaşça açtı; içeri girdi.\n\n\"Gelin,\" dedi.\n", encoding="utf-8")
    kod, out = _bicim(monkeypatch, capsys, kl, t)
    assert ANAHTAR in out and "listesi için --taban-olu" in out
    assert kod == 1                                   # yeni HATA tabanda degil: eski davranis
    kod2, out2 = _bicim(monkeypatch, capsys, kl, t, "--taban-olu")
    assert kod2 == kod
    liste = out2.split("ÖLÜ TABAN SATIRLARI")[1]
    assert "0001.md  (2)" in liste and "0002.md" not in liste
    assert "K01\tKapıyı açtı; içeri girdi." in liste and 'B03\t"Gel," dedi.' in liste


def test_bicim_tek_dosya_ve_kod_suzgeci_baskalarinin_satirini_olu_saymaz(tmp_path, monkeypatch, capsys):
    kl = _klasor(tmp_path, {"0001.md": K01 + "\n\n" + B03, "0002.md": K01_B})
    t = _taban(tmp_path, ("0001.md", "K01", "eski cumle"), ("0001.md", "B03", "eski b03"),
               ("0002.md", "K01", "eski cumle iki"))
    # tek dosya: yalniz 0001'in iki satiri kapsamda
    _k, out = _bicim(monkeypatch, capsys, kl, t, "1")
    assert "kapsamdaki 2 satırdan 2 tanesi ölü" in out
    _k, out = _bicim(monkeypatch, capsys, kl, t, "2")
    assert "kapsamdaki 1 satırdan 1 tanesi ölü" in out
    # --kod: yalniz o kodun satirlari kapsamda
    _k, out = _bicim(monkeypatch, capsys, kl, t, "--kod", "B03", "--taban-olu")
    assert "kapsamdaki 1 satırdan 1" in out
    assert "B03\teski b03" in out and "K01" not in out.split("ÖLÜ TABAN SATIRLARI")[1]
    # bos kapsam: satir yok
    _k, out = _bicim(monkeypatch, capsys, kl, t, "--kod", "B14")
    assert ANAHTAR not in out


def test_bicim_olmayan_dosya_yalniz_tam_taramada_olu(tmp_path, monkeypatch, capsys):
    kl = _klasor(tmp_path, {"0001.md": K01})
    t = _taban(tmp_path, ("0099.md", "K01", "yok artik"))
    _k, out = _bicim(monkeypatch, capsys, kl, t, "1")
    assert ANAHTAR not in out                           # kismi calisma: bilinemez
    _k, out = _bicim(monkeypatch, capsys, kl, t, "--taban-olu")
    assert "0099.md  (1, dosya yok)" in out
    _k, out = _bicim(monkeypatch, capsys, kl, t, "--kod", "B03", "--taban-olu")
    assert "0099.md  (1, dosya yok)" in out             # dosya yoksa kuraldan bagimsiz


def test_bicim_calismayan_kural_satiri_olu_sayilmaz():
    satirlar = [("", ("0001.md", "K13", "a")), ("", ("0001.md", "K01", "b"))]
    olu, kapsam = B.olu_satirlar(satirlar, set(), {"0001.md"}, None, {"K13"})
    assert olu == [("0001.md", "K01", "b")] and kapsam == 1


def test_bicim_olu_sil_yalniz_olu_kapsamdakileri_siler_yorum_ve_sirayi_korur(tmp_path, monkeypatch, capsys):
    kl = _klasor(tmp_path, {"0001.md": K01 + "\n\n" + B03, "0002.md": K01_B})
    canli = [x for x in _anahtarlar(kl, "0001.md") if x[1] == "K01"][0]
    k2 = [x for x in _anahtarlar(kl, "0002.md") if x[1] == "K01"][0]
    olu1 = ("0001.md", "B03", "eski b03")
    olu_kod = ("0002.md", "B14", "baska kod, --kod disinda kalir")
    yok = ("0099.md", "K01", "dosya yok")
    t = _taban(tmp_path, k2, olu1, canli, yok, olu1, olu_kod)   # olu1 iki kez
    once = t.read_text(encoding="utf-8").splitlines(keepends=True)
    # --kod B03: yalniz B03 olu satirlari (iki kopya) + yok dosya silinir
    _k, out = _bicim(monkeypatch, capsys, kl, t, "--kod", "B03", "--taban-olu-sil")
    assert "taban: 3 ölü satır silindi" in out
    sonra = t.read_text(encoding="utf-8").splitlines(keepends=True)
    assert sonra == [s for s in once if s not in ("\t".join(olu1) + "\n", "\t".join(yok) + "\n")]
    # tam tarama: kalan olu (B14) gider; canli, yorum ve sira kalir
    _k, out = _bicim(monkeypatch, capsys, kl, t, "--taban-olu-sil")
    assert "taban: 1 ölü satır silindi" in out
    assert t.read_text(encoding="utf-8") == "# yorum: elle yazilmis baslik\n" + "\t".join(k2) + "\n" + "\t".join(canli) + "\n"
    # tekrar: silinecek yok, dosya ayni, hicbir ozet satiri yok
    _k, out = _bicim(monkeypatch, capsys, kl, t, "--taban-olu-sil")
    assert "0 ölü satır silindi" in out


def test_bicim_olu_sil_kismi_calismada_reddedilir_dosyaya_dokunmaz(tmp_path, monkeypatch, capsys):
    kl = _klasor(tmp_path, {"0001.md": K01})
    t = _taban(tmp_path, ("0001.md", "K01", "olu"))
    once = t.read_bytes()
    for ek in (["0001.md"], ["1"], ["--bolum", "1"]):
        monkeypatch.setattr(sys, "argv", ["bicim_denetle.py", *ek, "--bolumler", str(kl),
                                          "--taban", str(t), "--taban-olu-sil"])
        with pytest.raises(SystemExit) as e:
            B.main()
        assert e.value.code == 2
    assert t.read_bytes() == once


def test_bicim_olu_bayraklari_taban_ister(tmp_path, monkeypatch):
    kl = _klasor(tmp_path, {"0001.md": K01})
    monkeypatch.setattr(sys, "argv", ["bicim_denetle.py", "--bolumler", str(kl), "--taban-olu"])
    with pytest.raises(SystemExit) as e:
        B.main()
    assert e.value.code == 2


def test_bicim_taban_olmadan_cikti_degismez(tmp_path, monkeypatch, capsys):
    kl = _klasor(tmp_path, {"0001.md": K01})
    monkeypatch.setattr(sys, "argv", ["bicim_denetle.py", "--bolumler", str(kl)])
    B.main()
    assert "taban:" not in capsys.readouterr().out


# ---------------------------------------------------------------- sapka

def _sapka(monkeypatch, capsys, taban, dosyalar, *ek):
    monkeypatch.setattr(sys, "argv", ["sapka.py", "--taban", str(taban), *ek,
                                      *map(str, dosyalar)])
    kod = sapka.main()
    return kod, capsys.readouterr().out


def _sapka_taban(tmp_path, *dosyalar):
    t = tmp_path / "sapka-taban.tsv"
    sapka.taban_yaz(t, {d.name: d.read_text("utf-8") for d in dosyalar})
    return t


def _bolumler(tmp_path):
    a = tmp_path / "1.md"
    b = tmp_path / "2.md"
    a.write_text("Bir adet elma.\n\nSelam verdi.\n", encoding="utf-8")
    b.write_text("Laf arasında sordu.\n", encoding="utf-8")
    return a, b


def test_sapka_canli_satir_olu_degil_degisince_olur(tmp_path, monkeypatch, capsys):
    a, b = _bolumler(tmp_path)
    t = _sapka_taban(tmp_path, a, b)
    kod, out = _sapka(monkeypatch, capsys, t, [a, b])
    assert "tabanda, gösterilmedi" in out and ANAHTAR not in out
    a.write_text("Bir adet elma.\n\nOnu selamlayarak geçti. Selam verdi sonra.\n", encoding="utf-8")
    kod2, out2 = _sapka(monkeypatch, capsys, t, [a, b])
    assert kod2 == kod == 0
    assert "kapsamdaki 3 satırdan 1 tanesi ölü" in out2           # "Selam verdi." baglami degisti
    kod3, out3 = _sapka(monkeypatch, capsys, t, [a, b], "--taban-olu")
    assert kod3 == kod
    assert "1.md  (1)" in out3 and "Selam\tSelam verdi." in out3


def test_sapka_yalniz_verilen_dosyalar_kapsamdadir(tmp_path, monkeypatch, capsys):
    a, b = _bolumler(tmp_path)
    t = _sapka_taban(tmp_path, a, b)
    a.write_text("Hiçbiri yok.\n", encoding="utf-8")
    b.write_text("Hiçbiri yok.\n", encoding="utf-8")
    _k, out = _sapka(monkeypatch, capsys, t, [b])
    assert "kapsamdaki 1 satırdan 1 tanesi ölü" in out
    _k, out = _sapka(monkeypatch, capsys, t, [a, b], "--taban-olu")
    assert "kapsamdaki 3 satırdan 3 tanesi ölü" in out
    # taban dosyasinda olup hic verilmeyen dosya: kapsam disi, olu degil
    t.write_text(t.read_text("utf-8") + "9.md\tselam\tbaska cagrinin dosyasi\n", encoding="utf-8")
    _k, out = _sapka(monkeypatch, capsys, t, [b], "--taban-olu")
    assert "9.md" not in out and "kapsamdaki 1 satırdan 1" in out


def test_sapka_olu_yoksa_satir_yok_ve_denetle_hesaplamaz(tmp_path, monkeypatch, capsys):
    a, b = _bolumler(tmp_path)
    t = _sapka_taban(tmp_path, a, b)
    _k, out = _sapka(monkeypatch, capsys, t, [a, b])
    assert ANAHTAR not in out
    # --denetle ELLE'yi taramaz: butun satirlar "olu" gorunmesin
    kod, out = _sapka(monkeypatch, capsys, t, [a, b], "--denetle")
    assert ANAHTAR not in out and kod == 0


def test_sapka_olu_sil_yalniz_olu_ve_kapsamdakileri_siler(tmp_path, monkeypatch, capsys):
    a, b = _bolumler(tmp_path)
    t = _sapka_taban(tmp_path, a, b)
    t.write_text(t.read_text("utf-8") + "2.md\tselam\tolu ama b verilmedi\n", encoding="utf-8")
    once = t.read_text("utf-8").splitlines(keepends=True)
    a.write_text("Bir adet elma.\n\nSelamlaşıp durdu.\n", encoding="utf-8")   # "Selam verdi." gitti
    kod, out = _sapka(monkeypatch, capsys, t, [a], "--taban-olu-sil")
    assert kod == 0 and "taban: 1 ölü satır silindi" in out
    sonra = t.read_text("utf-8").splitlines(keepends=True)
    assert sonra == [s for s in once if not s.startswith("1.md\tSelam\t")]
    assert sonra[:3] == once[:3] and sonra[0].startswith("#")           # baslik yorumlari
    assert any(s.startswith("2.md\tselam\tolu") for s in sonra)          # kapsam disi kaldi
    _k, out = _sapka(monkeypatch, capsys, t, [a], "--taban-olu-sil")
    assert "0 ölü satır silindi" in out


def test_sapka_olu_bayraklari_uyumsuz_kiplerde_reddedilir(tmp_path, monkeypatch, capsys):
    a, b = _bolumler(tmp_path)
    t = _sapka_taban(tmp_path, a, b)
    once = t.read_bytes()
    for ek in (["--denetle"], ["--kesif"], ["--uygula"]):
        monkeypatch.setattr(sys, "argv", ["sapka.py", "--taban", str(t), "--taban-olu-sil", *ek, str(a)])
        with pytest.raises(SystemExit) as e:
            sapka.main()
        assert e.value.code == 2
    monkeypatch.setattr(sys, "argv", ["sapka.py", "--taban-olu", str(a)])      # --taban yok
    with pytest.raises(SystemExit) as e:
        sapka.main()
    assert e.value.code == 2
    assert t.read_bytes() == once and a.read_text("utf-8").startswith("Bir adet")
