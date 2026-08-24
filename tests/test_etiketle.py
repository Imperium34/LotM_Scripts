# -*- coding: utf-8 -*-
"""
etiketle.py -- yazma yolu.

Bu dosyadaki en onemli test test_bolum_basligi_yorumu_dosyayi_bozmaz.
Bu bir REGRESYON testi: hata gercekten olmustu ve sessizdi.

  ruamel bir yorumu kendinden onceki anahtara baglar. Bir girdinin SON
  mertebesine yeni alan eklendiginde ("metinde", "kaynak") o alanlar
  yorumdan SONRA yaziliyordu. bosluk_duzelt'in girinti kaydirmasi ise
  yorumu gorunce blogu kapatiyordu, yani yeni alanlar kaydirilmadan
  kaliyor ve kardeslerinden iki bosluk geride duruyordu. Sonuc:
  ayristirilamayan bir sozluk.yml -- ustelik --yerinde ile YERINE
  yazilmis oluyordu.

Tetikleyici sekil, gercek sozluk.yml'de her yerde bulunan sekil:
girdiler arasinda "# --- Bolum ---" basligi.
"""

import textwrap

import pytest

YOL_VE_YORUM = """\
# --- Yollar ---

- terim: Avcı
  ingilizce: Hunter
  kategori: Yollar
  mertebeler:
    - seviye: 9
      isim: Avcı (Hunter)
      bolum_siniri: 20
    - seviye: 8
      isim: Değişken (Provoker)
      bolum_siniri: 90

# --- Kavramlar ---

- terim: Sıradışı
  ingilizce: Beyonder
  kategori: Kavramlar
  bolum_siniri: 3
"""


def _rapor_yaz(yol, satirlar):
    bas = ("guven\tbolum\tkanit_bolum\tguvenilir_mi\tseviye\tyol\tterim"
           "\teslesen\tmevcut\tbaglam")
    yol.write_text("\n".join([bas] + satirlar) + "\n", encoding="utf-8")


def _etiketle_calistir(sozluk_yolu, rapor_yolu, monkeypatch):
    import etiketle
    monkeypatch.setattr("sys.argv", ["etiketle.py", "--sozluk",
                                     str(sozluk_yolu), "--rapor",
                                     str(rapor_yolu), "--yerinde"])
    etiketle.main()


def test_bolum_basligi_yorumu_dosyayi_bozmaz(tmp_path, monkeypatch, capsys):
    """
    REGRESYON: girdiler arasi "# ---" yorumu, son mertebeye alan
    eklendiginde dosyayi ayristirilamaz hale getiriyordu.
    """
    import yaml

    sozluk = tmp_path / "sozluk.yml"
    sozluk.write_text(YOL_VE_YORUM, encoding="utf-8")
    rapor = tmp_path / "rapor.tsv"
    _rapor_yaz(rapor, [
        "yuksek\t21\t21\tevet\t9\tAvcı\tHunter\tHunter\t20\t...",
        "orta\t90\t90\tevet\t8\tAvcı\tProvoker\tProvoker\t90\t...",
        "yuksek\t1\t2\tevet\t\tKavramlar\tBeyonder\tBeyonder\t3\t...",
    ])

    _etiketle_calistir(sozluk, rapor, monkeypatch)

    metin = sozluk.read_text(encoding="utf-8")
    veri = yaml.safe_load(metin)          # bozuksa burada patlar

    assert len(veri) == 2
    # yeni alanlar SON mertebeye de dogru girintiyle yazilmis olmali
    son_mertebe = veri[0]["mertebeler"][-1]
    assert son_mertebe["metinde"] is True
    assert son_mertebe["kaynak"] == "metin"
    # bolum basligi yorumu korunmus olmali (ruamel'in secilme sebebi)
    assert "# --- Kavramlar ---" in metin
    assert "# --- Yollar ---" in metin


def test_yeni_alanlar_kardesleriyle_ayni_girintide(tmp_path, monkeypatch):
    sozluk = tmp_path / "sozluk.yml"
    sozluk.write_text(YOL_VE_YORUM, encoding="utf-8")
    rapor = tmp_path / "rapor.tsv"
    _rapor_yaz(rapor, [
        "yuksek\t21\t21\tevet\t9\tAvcı\tHunter\tHunter\t20\t...",
        "orta\t90\t90\tevet\t8\tAvcı\tProvoker\tProvoker\t90\t...",
    ])
    _etiketle_calistir(sozluk, rapor, monkeypatch)

    girintiler = {}
    for satir in sozluk.read_text(encoding="utf-8").split("\n"):
        s = satir.strip()
        for alan in ("isim:", "metinde:", "kaynak:"):
            if s.startswith(alan) and satir.startswith("      "):
                girintiler.setdefault(alan, set()).add(
                    len(satir) - len(satir.lstrip()))
    assert girintiler.get("metinde:") == girintiler.get("isim:"), \
        "metinde: kardeslerinden farkli girintide"


def test_dogrula_bozuk_ciktida_yazmayi_engeller(tmp_path, monkeypatch):
    """
    Guard: bosluk_duzelt bir gun yine bozarsa dosya YERINE yazilmamali.
    """
    import etiketle

    sozluk = tmp_path / "sozluk.yml"
    ozgun = YOL_VE_YORUM
    sozluk.write_text(ozgun, encoding="utf-8")
    rapor = tmp_path / "rapor.tsv"
    _rapor_yaz(rapor, ["yuksek\t21\t21\tevet\t9\tAvcı\tHunter\tHunter\t20\t..."])

    monkeypatch.setattr(etiketle, "bosluk_duzelt",
                        lambda m: m.replace("  ingilizce:", "   ?ingilizce:"))
    monkeypatch.setattr("sys.argv", ["etiketle.py", "--sozluk", str(sozluk),
                                     "--rapor", str(rapor), "--yerinde"])
    with pytest.raises(SystemExit):
        etiketle.main()

    assert sozluk.read_text(encoding="utf-8") == ozgun, "dosyaya dokunuldu"


def test_dogrula_girdi_sayisi_degisirse_yakalar():
    import etiketle
    saglam = "- terim: A\n- terim: B\n"
    assert etiketle.dogrula(saglam, 2) is None
    assert etiketle.dogrula(saglam, 3) is not None
    assert etiketle.dogrula("- terim: A\n  bozuk: [\n", 1) is not None


# --------------------------------------------------- turetilen kurallar

def test_alt_dize_riski_turetiliyor(lotm_modulu, tmp_path):
    """
    'Hunter' hem kendi basina hem 'Demon Hunter' icinde gecer; tarayicinin
    buldugu bolum guvenilmez. Bu iliski sozlukte zaten yazili -- elle
    liste tutmak ayni bilgiyi ikinci kez yazmakti.
    """
    import etiketle
    lotm = lotm_modulu
    yol = tmp_path / "s.yml"
    yol.write_text(textwrap.dedent("""\
        - terim: Avcı
          ingilizce: Hunter
          kategori: Yollar
        - terim: Şeytan Avcısı
          ingilizce: Demon Hunter
          kategori: Yollar
        - terim: Sıradışı
          ingilizce: Beyonder
          kategori: Kavramlar
        """), encoding="utf-8")

    riskli = etiketle.alt_dize_riski_turet(lotm.sozluk_yukle(yol))
    assert "Hunter" in riskli
    assert "Demon Hunter" not in riskli
    assert "Beyonder" not in riskli


def test_cins_isim_isareti_bolum_yazmayi_engeller(tmp_path, monkeypatch, capsys):
    """
    searcher.py 'guvenilir_mi' sutununu yaziyordu, etiketle.py ayristirip
    kullanmadan atiyordu. Artik okunuyor.
    """
    sozluk = tmp_path / "sozluk.yml"
    sozluk.write_text(textwrap.dedent("""\
        - terim: Avcı
          ingilizce: Hunter
          kategori: Yollar
          mertebeler:
            - seviye: 8
              isim: Değişken (Provoker)
              bolum_siniri: 5
        """), encoding="utf-8")
    rapor = tmp_path / "rapor.tsv"
    _rapor_yaz(rapor, [
        "yuksek\t900\t900\thayir(cins_isim)\t8\tAvcı\tProvoker\tProvoker\t5\t..."
    ])

    import etiketle
    monkeypatch.setattr("sys.argv", ["etiketle.py", "--sozluk", str(sozluk),
                                     "--rapor", str(rapor), "--yerinde"])
    etiketle.main()

    import yaml
    veri = yaml.safe_load(sozluk.read_text(encoding="utf-8"))
    assert veri[0]["mertebeler"][0]["bolum_siniri"] == 5, \
        "cins isim isaretine ragmen kapi degisti"
    assert "ilk_gecis" not in veri[0]["mertebeler"][0], \
        "cins isim isaretine ragmen ilk_gecis yazildi"
    assert "ilk_gecis_atlandi_cins_isim" in capsys.readouterr().out


# ------------------------------------------- kapi vs ilk gecis ayrimi

KAPI_SOZLUK = """\
- terim: Görücü
  ingilizce: Seer
  kategori: Yollar
  mertebeler:
    - seviye: 9
      isim: Çırak (Seer)
      bolum_siniri: 137
"""


@pytest.mark.parametrize("tarayici_bolum", ["21", "400"])
def test_editoryal_kapi_hicbir_yonde_ezilmez(tmp_path, monkeypatch,
                                             tarayici_bolum):
    """
    bolum_siniri cevirmenin karari: terimin ACIKLANDIGI bolum. Tarayicinin
    buldugu ilk gecis ondan once de sonra da olabilir; ikisi de kapiyi
    degistirmemeli.

    Eskiden 'tarayici > mevcut' oldugunda kapi sessizce eziliyordu.
    """
    import yaml

    sozluk = tmp_path / "sozluk.yml"
    sozluk.write_text(KAPI_SOZLUK, encoding="utf-8")
    rapor = tmp_path / "rapor.tsv"
    _rapor_yaz(rapor, [
        f"yuksek\t{tarayici_bolum}\t{tarayici_bolum}\tevet\t9\tGörücü"
        f"\tSeer\tSeer\t137\t..."
    ])

    _etiketle_calistir(sozluk, rapor, monkeypatch)

    m = yaml.safe_load(sozluk.read_text(encoding="utf-8"))[0]["mertebeler"][0]
    assert m["bolum_siniri"] == 137, "editoryal kapi ezildi"
    assert m["ilk_gecis"] == int(tarayici_bolum)


def test_ilk_gecis_serbestce_guncellenir(tmp_path, monkeypatch):
    """Turetilen alan; her calistirmada yeniden yazilabilir."""
    import yaml

    sozluk = tmp_path / "sozluk.yml"
    sozluk.write_text(KAPI_SOZLUK.replace(
        "      bolum_siniri: 137",
        "      bolum_siniri: 137\n      ilk_gecis: 99"), encoding="utf-8")
    rapor = tmp_path / "rapor.tsv"
    _rapor_yaz(rapor, ["yuksek\t21\t21\tevet\t9\tGörücü\tSeer\tSeer\t137\t..."])

    _etiketle_calistir(sozluk, rapor, monkeypatch)

    m = yaml.safe_load(sozluk.read_text(encoding="utf-8"))[0]["mertebeler"][0]
    assert m["ilk_gecis"] == 21
    assert m["bolum_siniri"] == 137
