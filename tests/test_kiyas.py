# -*- coding: utf-8 -*-
"""
kiyas.py testleri. Gercek korpusa DOKUNMAZ: adim tablosu ve veri parmak izi
degistirilir (monkeypatch), adimlar `python3 -c ...` kadar kucuk komutlardir ve
LOTM_KIYAS tmp_path'e yonlendirilir.

Adimlarin davranisini ortam degiskenleriyle (KIYAS_DEGER, KIYAS_UYKU) oynatiyoruz:
cocuk surec ortami miras alir, boylece "betik degisti" durumu tabloyu elle
yeniden yazmadan taklit edilir.
"""

import pytest

import kiyas

PY_YAZ = "import os;print('x' + os.environ.get('KIYAS_DEGER', ''))"
PY_ERR = "import os,sys;print('sure: ' + os.environ.get('KIYAS_DEGER', '') + 's', file=sys.stderr);print('sabit')"
PY_DOSYA = ("import os,sys;"
            "open(sys.argv[1] + '/a.txt', 'w').write('d' + os.environ.get('KIYAS_DEGER', ''))")
PY_YOL = "import sys;print(sys.argv[1])"
PY_HATA = "import sys;print('hata var', file=sys.stderr);print('cikti');sys.exit(3)"
PY_UYKU = "import os,time;time.sleep(float(os.environ.get('KIYAS_UYKU', '0')));print('bitti')"


def adim(*komut, gerekli=()):
    return {"komut": list(komut), "gerekli": list(gerekli)}


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    """LOTM_KIYAS tmp'de; adim tablosu ve parmak izi sahte, degistirilebilir."""
    monkeypatch.setenv("LOTM_KIYAS", str(tmp_path / "kiyas"))
    monkeypatch.delenv("KIYAS_DEGER", raising=False)
    monkeypatch.delenv("KIYAS_UYKU", raising=False)
    durum = {"adimlar": {"a": adim("-c", PY_YAZ)}, "parmak": {"veri": {"x.md": "h:1"}}}
    monkeypatch.setattr(kiyas, "adim_tablosu", lambda: (durum["adimlar"], ["not: deneme"]))
    monkeypatch.setattr(kiyas, "parmak_al", lambda: durum["parmak"])
    monkeypatch.setattr(kiyas, "NORMALLESTIRICI", {})
    return durum


def kos(*arg):
    return kiyas.main(["--isci", "2", *arg])


def test_taban_sonra_kiyas_ayni_ve_cikis_0(ortam, capsys):
    ortam["adimlar"]["b"] = adim("-c", PY_DOSYA, "{CIKTI}")
    assert kos("--taban-yaz") == 0
    capsys.readouterr()
    assert kos() == 0
    cikti = capsys.readouterr().out
    assert "AYNI" in cikti and "HEPSI AYNI" in cikti and "FARKLI" not in cikti


def test_cikti_degisince_cikis_1_adim_ve_dosya_adi_gorunur(ortam, capsys, monkeypatch):
    ortam["adimlar"]["b"] = adim("-c", PY_DOSYA, "{CIKTI}")
    kos("--taban-yaz")
    capsys.readouterr()
    monkeypatch.setenv("KIYAS_DEGER", "yeni")
    assert kos() == 1
    cikti = capsys.readouterr().out
    assert "FARKLI" in cikti
    assert "a / stdout.txt" in cikti and "b / dosya/a.txt" in cikti
    assert "-xyeni" not in cikti and "+xyeni" in cikti       # diff satiri okunur
    assert "diff -u" in cikti                                  # tam diff icin komut


def test_taban_yoksa_cikis_2_ve_ipucu(ortam, capsys):
    assert kos() == 2
    assert "--taban-yaz" in capsys.readouterr().out


def test_taban_yaz_var_olani_ezmez_uzerine_yaz_ezer(ortam, capsys, monkeypatch):
    assert kos("--taban-yaz") == 0
    monkeypatch.setenv("KIYAS_DEGER", "yeni")
    assert kos("--taban-yaz") == 2
    assert "--uzerine-yaz" in capsys.readouterr().out
    assert kos() == 1                       # taban hala eski
    assert kos("--taban-yaz", "--uzerine-yaz") == 0
    assert kos() == 0                       # yeni taban degisikligi kabul etti


def test_yol_normallestirme_iki_farkli_cikti_klasoru_ayni_sayilir(ortam, capsys):
    # taban/ ve son/ farkli klasorlerdir; adim kendi {CIKTI}'sini yazdirir.
    ortam["adimlar"]["y"] = adim("-c", PY_YOL, "{CIKTI}")
    kos("--taban-yaz")
    ham = (kiyas.kiyas_koku() / "taban" / "y" / "stdout.txt").read_text()
    assert ham.strip() == "<CIKTI>"
    assert kos() == 0
    assert (kiyas.kiyas_koku() / "son" / "y" / "stdout.txt").read_text() == ham


def test_yol_normallestir_en_uzun_yol_once(tmp_path):
    esle = [(str(tmp_path / "a" / "b"), "<IC>"), (str(tmp_path / "a"), "<DIS>")]
    esle.sort(key=lambda x: -len(x[0]))
    veri = f"{tmp_path}/a/b/x ve {tmp_path}/a/y".encode()
    assert kiyas.yol_normallestir(veri, esle) == b"<IC>/x ve <DIS>/y"


def test_adim_normallestirici_sure_satirini_eler(ortam, capsys, monkeypatch):
    ortam["adimlar"] = {"s": adim("-c", PY_ERR)}
    kos("--taban-yaz")
    monkeypatch.setenv("KIYAS_DEGER", "99")
    assert kos() == 1                        # normallestirici yokken sure satiri fark sayilir
    monkeypatch.setattr(kiyas, "NORMALLESTIRICI", {"s": [("stderr", r"^sure: .*\n", "")]})
    capsys.readouterr()
    assert kos() == 0


def test_normallestirici_baska_adima_dokunmaz(ortam, monkeypatch):
    ortam["adimlar"] = {"s": adim("-c", PY_ERR)}
    kos("--taban-yaz")
    monkeypatch.setenv("KIYAS_DEGER", "99")
    monkeypatch.setattr(kiyas, "NORMALLESTIRICI", {"baska": [("stderr", r"^sure: .*\n", "")]})
    assert kos() == 1


def test_parmak_izi_degisince_uyari_ama_tek_basina_fark_degil(ortam, capsys):
    kos("--taban-yaz")
    ortam["parmak"] = {"veri": {"x.md": "h:2", "y.md": "h:3"}, "yeni_grup": {"z": "h:4"}}
    capsys.readouterr()
    assert kos() == 0                         # cikti ayni: veri uyarisi kod 1 yapmaz
    cikti = capsys.readouterr().out
    assert "VERI DEGISMIS" in cikti and "veri:" in cikti and "1 degisen [x.md]" in cikti
    assert "yeni_grup" in cikti and "HEPSI AYNI" in cikti


def test_parmak_izi_ayniysa_uyari_yok(ortam, capsys):
    kos("--taban-yaz")
    capsys.readouterr()
    kos()
    assert "VERI DEGISMIS" not in capsys.readouterr().out


def test_parmak_farki_gruplar_ve_kisaltir():
    eski = {"g": {f"{i}.md": "1" for i in range(10)}}
    yeni = {"g": {f"{i}.md": "2" for i in range(10)}}
    (g, ek, sil, deg), = kiyas.parmak_farki(eski, yeni)
    assert (g, ek, sil, len(deg)) == ("g", [], [], 10)
    satirlar = "\n".join(kiyas.parmak_yaz_rapor(kiyas.parmak_farki(eski, yeni)))
    assert "10 degisen" in satirlar and "(+6)" in satirlar     # 70 satir degil, tek satir
    assert kiyas.parmak_farki(eski, eski) == []


def test_parmak_al_gercek_girdiler_sentetik_depoda(tmp_path, monkeypatch):
    kok = tmp_path / "depo"
    site = kok / "Imperium34.github.io"
    (site / "_data").mkdir(parents=True)
    (site / "_chapters").mkdir()
    (site / "_data" / "sozluk.yml").write_text("a: 1\n")
    (site / "_chapters" / "0001.md").write_text("bir\n")
    for d in ("Voice_Maps", "Prompts", "Schemas"):
        (kok / "Tools" / d).mkdir(parents=True)
        (kok / "Tools" / d / "x.md").write_text(d)
    (kok / "Tools" / "Prompts" / "old").mkdir()
    (kok / "Tools" / "Prompts" / "old" / "eski.md").write_text("eski")
    (kok / "Tools" / "words.md").write_text("k\n")
    (kok / "Source").mkdir()
    (kok / "Source" / "buyuk.txt").write_bytes(b"x" * (1 << 20))
    (kok / "Source" / "kucuk.txt").write_text("x")
    monkeypatch.setattr(kiyas.lotm, "KOK", kok)
    monkeypatch.setattr(kiyas.lotm, "SITE", site)
    monkeypatch.setattr(kiyas.lotm, "KELIMELER", kok / "Tools" / "words.md")
    p = kiyas.parmak_al()
    assert set(p) == {"site/_data", "site/_chapters", "words.md", "Tools/Voice_Maps",
                      "Tools/Prompts", "Tools/Schemas", "Source (boyut+mtime)"}
    assert list(p["Tools/Prompts"]) == ["Prompts/x.md"]          # ust duzey: old/ yok
    assert list(p["Source (boyut+mtime)"]) == ["buyuk.txt"]      # yalniz buyuk dosya
    assert p["Source (boyut+mtime)"]["buyuk.txt"].startswith("b:1048576:")
    assert p["site/_chapters"]["_chapters/0001.md"].startswith("h:")
    (site / "_chapters" / "0001.md").write_text("degisti\n")
    (g, _, _, deg), = kiyas.parmak_farki(p, kiyas.parmak_al())
    assert g == "site/_chapters" and deg == ["_chapters/0001.md"]


def test_iki_kosuda_da_sifirdan_farkli_cikis_ayni_ise_AYNI(ortam, capsys):
    ortam["adimlar"] = {"h": adim("-c", PY_HATA)}
    assert kos("--taban-yaz") == 0
    assert (kiyas.kiyas_koku() / "taban" / "h" / "kod.txt").read_text().strip() == "3"
    capsys.readouterr()
    assert kos() == 0
    assert "AYNI    h" in capsys.readouterr().out


def test_cikis_kodu_degisirse_fark(ortam, capsys):
    ortam["adimlar"] = {"h": adim("-c", "print('x')")}
    kos("--taban-yaz")
    # ayni stdout, farkli cikis kodu: kod.txt tek basina fark sayilmali
    stored = kiyas.kiyas_koku() / "taban" / "adimlar.json"
    stored.write_text(stored.read_text().replace("print('x')", "print('x');import sys;sys.exit(1)"))
    capsys.readouterr()
    assert kos() == 1
    assert "h / kod.txt" in capsys.readouterr().out


def test_zaman_asimi_hata_olarak_raporlanir_takilmaz(ortam, capsys, monkeypatch):
    ortam["adimlar"] = {"u": adim("-c", PY_UYKU)}
    assert kos("--taban-yaz", "--sure", "5") == 0
    monkeypatch.setenv("KIYAS_UYKU", "30")
    capsys.readouterr()
    import time
    t = time.perf_counter()
    assert kos("--sure", "1") == 1
    assert time.perf_counter() - t < 15
    cikti = capsys.readouterr().out
    assert "ZAMAN ASIMI" in cikti and "FARKLI" in cikti
    assert (kiyas.kiyas_koku() / "son" / "u" / "kod.txt").read_text().strip() == kiyas.ZAMAN_ASIMI


def test_ikisi_de_zaman_asimina_ugrarsa_yine_ayni_sayilmaz(ortam, capsys, monkeypatch):
    ortam["adimlar"] = {"u": adim("-c", PY_UYKU)}
    monkeypatch.setenv("KIYAS_UYKU", "30")
    assert kos("--taban-yaz", "--sure", "1") == 0
    assert "zaman asimina ugradi" in capsys.readouterr().out
    assert kos("--sure", "1") == 1


def test_tabanda_sonucu_olmayan_adim_YENI_girdisi_olmayan_EKSIK(ortam, capsys):
    import shutil
    ortam["adimlar"]["b"] = adim("-c", "print(1)", gerekli=["{KOK}/yok-boyle-dosya"])
    ortam["adimlar"]["b"]["gerekli"] = []
    kos("--taban-yaz")
    shutil.rmtree(kiyas.kiyas_koku() / "taban" / "b")
    capsys.readouterr()
    assert kos() == 1
    assert "YENI" in capsys.readouterr().out
    # girdi dosyasi sonradan kaybolursa adim kosulmaz, EKSIK
    import json
    yol = kiyas.kiyas_koku() / "taban" / "adimlar.json"
    veri = json.loads(yol.read_text())
    veri["adimlar"]["a"]["gerekli"] = ["{KOK}/yok-boyle-dosya"]
    yol.write_text(json.dumps(veri))
    assert kos("a") == 1
    assert "EKSIK" in capsys.readouterr().out


def test_adim_secimi_ve_bilinmeyen_adim(ortam, capsys):
    ortam["adimlar"]["b"] = adim("-c", "print('b')")
    kos("--taban-yaz")
    capsys.readouterr()
    assert kos("b") == 0
    cikti = capsys.readouterr().out
    assert "1 adim" in cikti and "AYNI    b" in cikti and "AYNI    a" not in cikti
    assert kos("yok") == 2
    assert "bilinmeyen adim" in capsys.readouterr().out
    assert kos("--taban-yaz", "a", "--uzerine-yaz") == 2        # taban tamamen alinir


def test_liste_tabandaki_komutlari_gosterir(ortam, capsys):
    kos("--taban-yaz")
    capsys.readouterr()
    assert kos("--liste") == 0
    cikti = capsys.readouterr().out
    assert "1 adim (taban)" in cikti and "not: not: deneme" in cikti


def test_seri_tek_isciyle_kosar(ortam, capsys):
    kos("--taban-yaz")
    capsys.readouterr()
    assert kiyas.main(["--seri"]) == 0
    assert "seri" in capsys.readouterr().out


def test_gecici_dizin_yarida_kalan_taban_eskiyi_bozmaz(ortam, capsys, monkeypatch):
    kos("--taban-yaz")
    def patla(*a, **k):
        raise RuntimeError("yarida kesildi")
    monkeypatch.setattr(kiyas, "hepsini_kos", patla)
    with pytest.raises(RuntimeError):
        kos("--taban-yaz", "--uzerine-yaz")
    assert (kiyas.kiyas_koku() / "taban" / "adimlar.json").exists()


def test_yer_tutucu_ac_betik_kok_cikti(tmp_path):
    s = kiyas.yer_tutucu_ac("{BETIK}/x {KOK}/y {CIKTI}/z", tmp_path)
    assert s == f"{kiyas.lotm.BETIK_KOK}/x {kiyas.lotm.KOK}/y {tmp_path}/z"
