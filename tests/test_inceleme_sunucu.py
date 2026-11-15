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
