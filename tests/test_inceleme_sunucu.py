# -*- coding: utf-8 -*-
"""inceleme_sunucu.py -- .md'ye geri yazma: yalniz hedef maddenin kutulari ve ✓ satiri."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import inceleme_sunucu as I  # noqa: E402
import sonra as S  # noqa: E402

KARAR = [{"p": 1, "sinif": "KARAR", "kural": "sadakat A düşmüş ayrıntı", "kaynak": ["sadakat"],
          "eski": "Kapı açıldı ve o sessizce içeri girip masanın başına oturdu.",
          "yeni": "Kapı gıcırdayarak açıldı ve o sessizce içeri girip masanın başına oturdu.", "neden": "ZH 吱呀"},
         {"p": 2, "sinif": "KARAR", "kural": "sadakat B eklenmiş duraksama", "kaynak": ["sadakat"],
          "eski": "Üzgünüm...", "yeni": "Üzgünüm.", "neden": "ZH 很抱歉"}]


def test_geri_yazma():
    md = S.inceleme_katmanla(S.inceleme_yaz(7, [], KARAR, [], kuru=False))
    ms, toplu_var, toplu = I.maddeler(md)
    assert [m["k"] for m in ms] == [1, 2] and toplu_var and not toplu
    yeni = I.madde_yaz(md, 1, kabul=True, ret=False, hep=True, yeni="Kapı gıcırdadı ve o sessizce içeri girip masanın başına oturdu.")
    sec = {s["k"]: s for s in S.inceleme_oku(yeni)}
    assert sec[1]["kabul"] and sec[1]["hep"] and sec[1]["yeni"].startswith("Kapı gıcırdadı")
    assert not (sec[2]["kabul"] or sec[2]["ret"])
    assert "{+gıcırdadı+}" in yeni  # Fark satiri da yenilendi
    yeni = I.toplu_yaz(yeni, True)
    sec = {s["k"]: s for s in S.inceleme_oku(yeni)}
    assert sec[2]["ret"] and sec[1]["kabul"]


def test_farklar():
    sx, sy = I.farklar("a b c", "a x c")
    assert ("-", "b") in sx and ("+", "x") in sy


def _kok(tmp_path, nolar):
    """Sahte LotM koku: bolum dosyalari + her bolum icin isaretli 5_inceleme.md."""
    kok = tmp_path / "LotM"
    bolumler = kok / "Imperium34.github.io" / "_chapters"
    bolumler.mkdir(parents=True)
    (kok / "Tools").mkdir()
    rapor = tmp_path / "sonra"
    for no in nolar:
        (bolumler / f"{no:04d}.md").write_text(
            "---\ntitle: x\n---\n\nKapı açıldı ve o sessizce içeri girip masanın başına oturdu.\n\nÜzgünüm...\n",
            encoding="utf-8")
        md = S.inceleme_katmanla(S.inceleme_yaz(no, [], KARAR, [], kuru=False))
        md = I.madde_yaz(md, 1, kabul=True, ret=False, hep=False, yeni=None)
        (rapor / f"Ch_{no}").mkdir(parents=True)
        (rapor / f"Ch_{no}" / "5_inceleme.md").write_text(md, encoding="utf-8")
    return kok, rapor


def test_uygula_sonraki_bolume_gecer_kuyruk_bitince_kapanir(tmp_path, monkeypatch):
    import json
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    kok, rapor = _kok(tmp_path, [7, 8])
    for ad, deger in {"LOTM_KOK": kok, "LOTM_SONRA_RAPOR": rapor, "LOTM_KARARLAR": tmp_path / "kararlar.md",
                      "LOTM_ISTATISTIK": tmp_path / "ist.tsv", "LOTM_KELIMELER": tmp_path / "words.md",
                      "LOTM_YEDEK": tmp_path / "yedek"}.items():
        monkeypatch.setenv(ad, str(deger))
    monkeypatch.setattr(S, "RAPOR", rapor)
    monkeypatch.setattr(S, "ISTATISTIK", tmp_path / "ist.tsv")
    monkeypatch.setattr(S, "BOLUMLER", kok / "Imperium34.github.io" / "_chapters")
    kip = I.Kip("sonra")
    assert kip.hazirlar(6) == [7, 8]
    oturum = I.Oturum(kip, [7] + kip.hazirlar(7))
    sunucu = ThreadingHTTPServer(("127.0.0.1", 0), None)
    kapandi = threading.Event()

    def kapat():
        sunucu.shutdown()
        kapandi.set()
    sunucu.RequestHandlerClass = I.uygulama(oturum, kapat=kapat)
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    adres = f"http://127.0.0.1:{sunucu.server_address[1]}"

    def post(yol):
        r = urllib.request.Request(adres + yol, data=b"{}", headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(r, timeout=60).read())

    d = json.loads(urllib.request.urlopen(adres + "/api/maddeler", timeout=10).read())
    assert d["bolum"] == 7 and d["kuyruk"] == [8] and d["isaretsiz"] == 1 and d["uygulanabilir"]
    d = post("/api/uygula")
    assert d.get("bolum") == 8 and "1 karar uygulandi" in d["sonuc"], d
    assert "gıcırdayarak" in (kok / "Imperium34.github.io/_chapters/0007.md").read_text(encoding="utf-8")
    assert kip.islenmis(7) and not kip.islenmis(8)
    assert list((tmp_path / "yedek").rglob("0007.md"))  # --kararlar oncesi yedek
    d = post("/api/uygula")
    assert d["bitti"] and len(d["uygulananlar"]) == 2
    assert kapandi.wait(5)
    assert kip.hazirlar(6) == []


def test_uygulananlar_sayfada_ve_geri_isareti():
    uyg = [{"p": 1, "kural": "okuma 1.6 bir şekilde", "kaynak": ["okuma"], "otomatik": True,
            "eski": "bir şekilde gülümsedi", "yeni": "gülümsedi"}]
    md = S.inceleme_katmanla(S.inceleme_yaz(7, uyg, KARAR, [], kuru=False))
    y = I.yazilanlar(md)
    assert [(x["k"], x["otomatik"], x["geri"], x["katman"]) for x in y] == [("U1", True, False, "0. Uygulananlar")]
    assert I.isaretsiz(md) == 2  # uygulananlar sayilmaz
    md = S.geri_yaz(md, 1, True)
    assert I.yazilanlar(md)[0]["geri"] and [m["k"] for m in I.maddeler(md)[0]] == [1, 2]


def test_grup_onderi_izleyenleri_tasir():
    karar = [{"p": 1, "sinif": "KARAR", "kural": "sadakat C terim kayması", "kaynak": ["sadakat"],
              "eski": "Elinde el yazması vardı.", "yeni": "Elinde günlük vardı.", "neden": "ZH 笔记"},
             {"p": 3, "sinif": "KARAR", "kural": "sadakat C terim kayması", "kaynak": ["sadakat"],
              "eski": "El yazmasını açtı.", "yeni": "Günlüğü açtı.", "neden": "ZH 笔记"}]
    md = S.inceleme_katmanla(S.inceleme_yaz(7, [], karar, [], kuru=False))
    assert I.isaretsiz(md) == 2
    md = I.grup_yaz(md, 1, kabul=True, ret=False, hep=False, yeni=None)
    ms = {m["k"]: m for m in I.maddeler(md)[0]}
    assert ms[2]["kabul"] and ms[2]["grup"] == 1 and I.isaretsiz(md) == 0
    md = I.grup_yaz(md, 1, kabul=False, ret=True, hep=False, yeni=None)  # onder fikir degistirir
    ms = {m["k"]: m for m in I.maddeler(md)[0]}
    assert ms[2]["ret"] and not ms[2]["kabul"]
    md = I.madde_yaz(md, 2, kabul=True, ret=False, hep=False, yeni=None)  # izleyen elle ayrilir
    md = I.grup_yaz(md, 1, kabul=False, ret=False, hep=False, yeni=None)
    ms = {m["k"]: m for m in I.maddeler(md)[0]}
    assert ms[2]["kabul"]


def test_baglam_grup_cakismaz_ve_kisa_eski_zh_bulur():
    b = I.Baglam(None)
    b.bloklar = ["İlk paragrafta kısa bir cevap vardı: Evet."]
    b.gruplar = {3: {"TR": "İlk paragrafta kısa bir cevap vardı: Evet.", "ZH": "第一段有个简短回答：是的。"}}
    sonuc = b.bul({"p": "1", "eski": "Evet."})
    assert sonuc["hizalama_grup"] == 3 and "是的" in sonuc["zh"]
    assert "grup" not in sonuc


def test_ayni_satirda_yalniz_ortusen_araliklar_baglanir():
    b = I.Baglam(None)
    b.metin = "İlk cümle. İkinci cümle.\n\nBağımsız satır."
    maddeler = [
        {"k": 1, "p": "1", "eski": "İlk cümle.", "yeni": "İlk söz."},
        {"k": 2, "p": "7", "eski": "İkinci cümle.", "yeni": "İkinci söz."},
        {"k": 3, "p": "7", "eski": "cümle. İkinci", "yeni": "cümle. Sonraki"},
        {"k": 4, "p": "1", "eski": "Bağımsız satır.", "yeni": "Başka satır."},
    ]
    b.cakisan_oneriler(maddeler)
    assert maddeler[0]["cakisanlar"] == [3]
    assert maddeler[1]["cakisanlar"] == [3]
    assert maddeler[2]["cakisanlar"] == [1, 2]
    assert "cakisanlar" not in maddeler[3]


def test_eski_incelemede_ayni_paragraf_ve_eski_metin_gerekir():
    b = I.Baglam(None)
    b.metin = "Baca orada saklı duruyordu."
    maddeler = [
        {"k": 1, "p": "54", "eski": "bükülmenin ardında", "yeni": "orada"},
        {"k": 2, "p": "54", "eski": "bükülmenin ardında", "yeni": "bükülen yerin ardında"},
        {"k": 3, "p": "54", "eski": "saklı duruyordu", "yeni": "gizlenmişti"},
        {"k": 4, "p": "-", "eski": "bükülmenin ardında", "yeni": "orada"},
        {"k": 5, "p": "-", "eski": "bükülmenin ardında", "yeni": "orada"},
    ]
    b.cakisan_oneriler(maddeler)
    assert maddeler[0]["cakisanlar"] == [2]
    assert "cakisanlar" not in maddeler[2]
    assert "cakisanlar" not in maddeler[3] and "cakisanlar" not in maddeler[4]


def test_celiskili_post_ve_bitti_sonrasi_cift_uygula_reddedilir(tmp_path, monkeypatch):
    import json
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    kok, rapor = _kok(tmp_path, [7])
    for ad, deger in {"LOTM_KOK": kok, "LOTM_SONRA_RAPOR": rapor, "LOTM_KARARLAR": tmp_path / "kararlar.md",
                      "LOTM_ISTATISTIK": tmp_path / "ist.tsv", "LOTM_KELIMELER": tmp_path / "words.md",
                      "LOTM_YEDEK": tmp_path / "yedek"}.items():
        monkeypatch.setenv(ad, str(deger))
    monkeypatch.setattr(S, "RAPOR", rapor)
    monkeypatch.setattr(S, "ISTATISTIK", tmp_path / "ist.tsv")
    monkeypatch.setattr(S, "BOLUMLER", kok / "Imperium34.github.io" / "_chapters")

    kip = I.Kip("sonra")
    oturum = I.Oturum(kip, [7])
    sunucu = ThreadingHTTPServer(("127.0.0.1", 0), None)
    sunucu.RequestHandlerClass = I.uygulama(oturum)
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    adres = f"http://127.0.0.1:{sunucu.server_address[1]}"
    try:
        # kabul+ret ayni anda 400 donmeli
        req = urllib.request.Request(
            adres + "/api/madde",
            data=json.dumps({"k": 1, "kabul": True, "ret": True, "hep": False}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            assert False, "400 bekleniyordu"
        except urllib.error.HTTPError as e:
            assert e.code == 400

        # Ilk uygula bitirir; ikinci uygula kip.uygula'yi yeniden cagirmaz
        req_u = urllib.request.Request(adres + "/api/uygula", data=b"{}", headers={"Content-Type": "application/json"})
        d1 = json.loads(urllib.request.urlopen(req_u, timeout=30).read())
        assert d1["bitti"] and len(d1["uygulananlar"]) == 1
        monkeypatch.setattr(kip, "uygula", lambda no: (_ for _ in ()).throw(AssertionError("yeniden cagrilmamali")))
        d2 = json.loads(urllib.request.urlopen(req_u, timeout=10).read())
        assert d2["bitti"] and len(d2["uygulananlar"]) == 1
    finally:
        sunucu.shutdown()


def test_islenmis_baska_bolumun_istatistigiyle_yanilmaz(tmp_path, monkeypatch):
    import os
    rapor = tmp_path / "sonra"
    ist = tmp_path / "ist.tsv"
    ist.write_text("bolum\tk\taile\ton\tkarar\n10\t1\tsadakat\t0\tkabul\n", encoding="utf-8")
    os.utime(ist, (1000, 1000))
    ch10 = rapor / "Ch_10" / "5_inceleme.md"
    ch10.parent.mkdir(parents=True)
    ch10.write_text("# 10\n", encoding="utf-8")
    os.utime(ch10, (2000, 2000))  # istatistikten sonra yeniden uretilmis
    monkeypatch.setattr(S, "RAPOR", rapor)
    monkeypatch.setattr(S, "ISTATISTIK", ist)

    kip = I.Kip("sonra")
    assert not kip.islenmis(10)
    # Baska bir bolum (11) islenip ortak ist.tsv'nin mtime'ini ileri tasiyor
    os.utime(ist, (3000, 3000))
    assert not kip.islenmis(10)


def test_olmayan_dosya_ve_kisayol_korumasi(tmp_path):
    assert I.main(["--dosya", str(tmp_path / "yok.md"), "--acma"]) == 1
    assert "if(e.ctrlKey||e.metaKey||e.altKey) return;" in I.SAYFA


def test_on_isaretli_onay_yazilir_ve_geri_alinir():
    md = ("## 2. Hızlı\n\n### K1 · Ch_41 · ¶3 · KARAR · okuma 1.1 Zincir\n✗ a; b\n✓ a. B\n"
          "Kaynak: okuma\nÖn: emsal R2 okuma 1.1 → kabul (1–40: 38/39)\n[x] kabul   [ ] ret   [ ] hep\n")
    m = I.maddeler(md)[0][0]
    assert m["on"].startswith("emsal R2") and not m["onay"]
    md2 = I.madde_yaz(md, 1, kabul=True, ret=False, hep=False, yeni=None, onay=True)
    assert "→ kabul (1–40: 38/39) · onaylandı\n" in md2 and I.maddeler(md2)[0][0]["onay"]
    md3 = I.madde_yaz(md2, 1, kabul=False, ret=True, hep=False, yeni=None, onay=True)
    assert md3.count("onaylandı") == 1 and "[ ] kabul   [x] ret" in md3
    assert I.madde_yaz(md3, 1, kabul=True, ret=False, hep=False, yeni=None, onay=False) == md
    assert I.madde_yaz(md, 1, kabul=True, ret=False, hep=False, yeni=None) == md  # onay=None dokunmaz
