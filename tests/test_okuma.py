# -*- coding: utf-8 -*-
"""okuma.py -- coklu bolum okuma gecisi, Yanki + kirpik sablon, ZH kontrol, tek inceleme.md."""

import json

import pytest
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import inceleme_sunucu as I  # noqa: E402
import okuma as O  # noqa: E402
import sonra as S  # noqa: E402


YANKI_ORNEK = """# Yankı Defteri

### #1 · Chanis düsturu
`Birebir · kritik · sabit`
- **Kurulum:** 18
- **Donmuş:** "Bizler muhafızlarız"
- **Ödeme:** **627**
- **Neden bozulur:** birebir.

### #2 · Kaptan → Kaptanım
`Biçim · kritik · eklenecek`
- **Kurulum:** Cilt 1–2 boyunca (iyeliksiz 'Kaptan'; kazanım)
- **Donmuş:** C.1–2 boyunca kazanılır
- **Ödeme:** **209**
- **Neden bozulur:** iyelik eki.

### #7 · Dört adımlık şans artırma ayini
`Nesne / Edim · kritik · denetlenmedi`
- **Kurulum:** 2; 51
- **Donmuş:** 19'a kadar 'şans artırma ritüeli' (3, 14, 19); dört efsun satırı
- **Ödeme:** **1166**
- **Neden bozulur:** adımlar.

### #16 · Kızıl Ay jesti
`Nesne / Edim · kritik · sabit`
- **Kurulum:** 26 ¶5
- **Donmuş:** "göğsüne ... dört kez dokun-" / "Kızıl Ay şeklini çiz-"; şükür: "Ulu Ece'ye medholsun"
- **Ödeme:** İleride, Klein'ın Tingen'den ayrıldıktan sonra bu jesti yaptığı her yer
- **Neden bozulur:** jest.

### #22 · Basiret düğmesi
`Nesne / Edim · kritik · sabit`
- **Kurulum:** 33
- **Donmuş:** "kaşlarının arasına iki kez vur-"
- **Ödeme:** İleride, Klein'ın Basiret'i her açıp kapadığı yer
- **Neden bozulur:** düğme.

### #99 · Gelecek kurulum
`Kalıp · kritik · eklenecek`
- **Kurulum:** 500
- **Donmuş:** "kaşlarının arasına iki kez vur-"
- **Ödeme:** İleride her yer
- **Neden bozulur:** 500'den önce eşleşmemeli.
"""

SABLON_ORNEK = """# Bölüm 90

## A. TERİMLER VE ÖZEL ADLAR

### A.1 Yerleşik terimler (değiştirilemez)

| İngilizce | Türkçe | Kullanım notu |
| --------- | ------ | ------------- |
| mysticism | İlm-i Esrar | not |
| Seer | Kâhin | not |

### A.2 Yeni terimler

| İngilizce | Türkçe | Etiket | Not |
| --------- | ------ | ------ | --- |
| bluff | blöf | `[YENİ]` | not |

### A.3 Metne eklenmeyecek

- Gizli bilgiler burada uzun uzun anlatılır.

---

## B. DONDURULAN SATIRLAR

| İngilizce | Türkçe (dondurulmuş) | Sayı | Not |
| --- | --- | --- | --- |
| Stop | Dur | 1 | sabit |

---

## C. AKTİF SES HARİTALARI

### Klein
Çok uzun ses haritası metni burada yer alır ve okuma geçişinde çıkarılmalıdır.

---

## D. HİTAP TABLOSU

| Konuşan | Muhatap | Hitap | Not |
| --- | --- | --- | --- |
| Klein | Dunn | Kaptan, siz | sabit |

---

## E. BÖLÜME ÖZEL NOTLAR

- Kaynak metin uyuşmazlıkları uzun anlatım.
"""


def test_aralik_etiketi():
    assert O.aralik_etiketi([1, 2, 3, 4]) == "1-4"
    assert O.aralik_etiketi([1, 2, 3, 7, 9, 10]) == "1-3,7,9-10"
    assert O.aralik_etiketi([42]) == "Ch_42"


def test_yanki_secimi_akilli():
    girisler = S.yanki_girisleri(YANKI_ORNEK)
    # 14. bolum: #7 Donmus'te gecer; #2 'Kaptan' surekli; #16 (kurulum 26 > 14) cikmamali.
    metin_14 = "---\ntitle: x\n---\n\nKaptan kapıdan içeri girdi, Kızıl Ay şeklini çizdi.\n"
    assert O.yanki_secimi_akilli(14, girisler, metin_14) == [2, 7]

    # 70. bolum: #16 ve #22 surekli ve metinde geciyor; #99 (kurulum 500 > 70) cikmamali.
    metin_70 = "---\ntitle: x\n---\n\nKlein kaşlarının arasına iki kez vurdu. Ulu Ece'ye medholsun.\n"
    assert O.yanki_secimi_akilli(70, girisler, metin_70) == [16, 22]


def test_sablon_kirp_ve_yayimlanmis(tmp_path, monkeypatch):
    kirpik = O.sablon_kirp(SABLON_ORNEK)
    assert "İlm-i Esrar · Kâhin · blöf" in kirpik
    assert "## B. DONDURULAN SATIRLAR" in kirpik
    assert "## D. HİTAP TABLOSU" in kirpik
    assert "AKTİF SES HARİTALARI" not in kirpik
    assert "Metne eklenmeyecek" not in kirpik
    assert "BÖLÜME ÖZEL NOTLAR" not in kirpik

    sab = tmp_path / "Ch_90.md"
    sab.write_text(SABLON_ORNEK, encoding="utf-8")
    monkeypatch.setattr(S, "SABLONLAR", tmp_path)
    b = S.Bolum(90, 6000)

    yayimli_metin = "---\ndate: 2020-01-01 20:00:00 +0300\n---\n\nMetin.\n"
    assert O.sablon_blogu_okuma(b, yayimli_metin) == ""

    yeni_metin = "---\ndate: 2099-01-01 20:00:00 +0300\n---\n\nMetin.\n"
    blok = O.sablon_blogu_okuma(b, yeni_metin)
    assert "<bolum_sablonu>" in blok and "İlm-i Esrar" in blok and "AKTİF SES HARİTALARI" not in blok


def test_okuma_ayristir_coklu_cift_ve_ozel_satirlar():
    bolum = (
        "---\ntitle: test\n---\n\n"
        "Birinci cümlede aynı sözcük tekrar tekrar geçti. İkinci cümlede de saat çıkarıp saate baktı.\n\n"
        "Üçüncü paragrafta belirsiz bir ifade vardı.\n\n"
        "Dördüncü paragrafta şüpheli bir yineleme var.\n\n"
        "Beşinci paragrafta üslup sorunu: elini uzatıp ağzını kapattı.\n"
    )
    cikti = """## (1) Yoğunluk raporu

    madde  örüntü  sayı  yığılma
    1.6    tekrar  2     ¶1

## (2) Bulgular

    ¶1   1.6  (c)  tekrar ve saat
         ✗ Birinci cümlede aynı sözcük tekrar tekrar geçti.
         ✓ Birinci cümlede aynı sözcük bir kez daha geçti.
         (Aynı sözcük yan yana.)
         ✗ İkinci cümlede de saat çıkarıp saate baktı.
         ✓ İkinci cümlede de saat çıkarıp baktı.

    ¶2   SADAKAT?
         ✗ Üçüncü paragrafta belirsiz bir ifade vardı.
         Gerekçe: Kaynakta belirsizlik var mı?

    ¶3–¶4  1.6  ŞÜPHELİ  yineleme
         ✗ Dördüncü paragrafta şüpheli bir yineleme var.
         Gerekçe: Kasıtlı olabilir.

    ¶4   1.9 1.M.2  (d)  fiil kalıbı
         ✗ Beşinci paragrafta üslup sorunu: elini uzatıp ağzını kapattı.
         ✓ Beşinci paragrafta üslup sorunu: eliyle ağzını kapattı.
         Not: Kendi ağzına elini uzatmaz.

## (3) Öneri dağılımı

    sözcük düşürme  2
"""
    bulgular, sadakat, bilgi = O.okuma_ayristir(cikti, bolum, no=12)
    assert len(bulgular) == 3
    assert [b["p"] for b in bulgular] == [1, 1, 4]
    assert bulgular[0]["bolum"] == 12
    assert S.aileler(bulgular[0]["kural"]) == {"okuma 1.6"}
    assert S.aileler(bulgular[2]["kural"]) == {"okuma 1.9", "okuma 1.M"}
    assert len(sadakat) == 1 and sadakat[0]["p"] == 2
    assert len(bilgi) == 1 and "ŞÜPHELİ" in bilgi[0]["not"]


def test_okuma_ayristir_codex_bicimleri():
    bolum = (
        "---\ntitle: t\n---\n\n"
        "Birinci cümlede saat çıkarıp saate baktı.\n\n"
        "_İkinci cümlede italik metin var._\n\n"
        "Üçüncü cümlede şüpheli anlam var.\n\n"
        "Dördüncü cümlede boş konuştu.\n"
    )
    cikti = """## 2. Bulgular

**¶1 · 1.6 · (c) · `saat` tekrarı**
> ✗ Birinci cümlede saat çıkarıp saate baktı.
>
> ✓ Birinci cümlede saat çıkarıp baktı.

**¶2\u20021.9\u2002(d)\u2002italik**
- ✗ `_İkinci cümlede italik metin var._`
- ✓ `_İkinci cümlede farklı italik metin var._`

**¶3 · 1.M.4 · SADAKAT? · Nedensellik**
> ✗ Üçüncü cümlede şüpheli anlam var.

Gerekçe — Bağlamdan çıkmıyor.

**¶4 · 1.7(ii) · (c) · konuştu**
- ✗ Dördüncü cümlede boş konuştu.
- ✓ Dördüncü cümlede konuştu.

## 3. Öneri dağılımı
"""
    bulgular, sadakat, bilgi = O.okuma_ayristir(cikti, bolum, no=9)
    assert len(bulgular) == 3 and not bilgi
    assert bulgular[1]["eski"] == "_İkinci cümlede italik metin var._"
    assert len(sadakat) == 1 and sadakat[0]["gerekce"] == "Bağlamdan çıkmıyor."


def test_cift_okuma_birlestir():
    b1 = [
        {"bolum": 5, "p": 1, "sinif": "KARAR", "kaynak": ["okuma"], "kural": "okuma 1.6 tekrar",
         "eski": "a b", "yeni": "a c", "neden": "n1"},
        {"bolum": 5, "p": 2, "sinif": "KARAR", "kaynak": ["okuma"], "kural": "okuma 1.2 giris",
         "eski": "x y", "yeni": "x z", "neden": "n2"},
    ]
    b2 = [
        {"bolum": 5, "p": 1, "sinif": "KARAR", "kaynak": ["okuma"], "kural": "okuma 1.6 tekrar",
         "eski": "a b", "yeni": "a c", "neden": "n1b"},
        {"bolum": 5, "p": 2, "sinif": "KARAR", "kaynak": ["okuma"], "kural": "okuma 1.2 giris",
         "eski": "x y", "yeni": "w z", "neden": "n2b"},
    ]
    bir, _, _ = O.cift_okuma_birlestir([("claude", b1, [], []), ("codex", b2, [], [])])
    assert len(bir) == 3
    assert bir[0]["okuma_motor"] == ["claude", "codex"]
    assert all("seçenek:" in x["neden"] for x in bir[1:])


def test_zh_sonuc_uygula_engel_ve_sadakat(monkeypatch):
    bolum = (
        "---\ntitle: t\n---\n\n"
        "Klein hafifçe başını sallayıp hafifçe gülümsedi.\n\n"
        "Klein kapıyı usulca açtı.\n\n"
        "Rüzgârın sesiyle sessizlik çekildi.\n"
    )
    bulgular = [
        {"bolum": 8, "p": 1, "sinif": "KARAR", "kaynak": ["okuma"], "kural": "okuma 1.6 hafifçe",
         "eski": "Klein hafifçe başını sallayıp hafifçe gülümsedi.",
         "yeni": "Klein başını sallayıp hafifçe gülümsedi.", "neden": "tekrar"},
        {"bolum": 8, "p": 2, "sinif": "KARAR", "kaynak": ["okuma"], "kural": "okuma 1.6 usulca",
         "eski": "Klein kapıyı usulca açtı.", "yeni": "Klein kapıyı açtı.", "neden": "gereksiz"},
    ]
    sadakat = [
        {"bolum": 8, "p": 3, "kural": "okuma", "eski": "Rüzgârın sesiyle sessizlik çekildi.",
         "gerekce": "sessizlik çekilmek ters anlam"},
    ]
    zh_cikti = """```json
{
  "inceleme": [
    {"id": "M1", "karar": "ONAY", "zh_not": "", "yeni": null},
    {"id": "M2", "karar": "RET", "zh_not": "ZH 轻轻: usulca kaynakta açıkça var.", "yeni": null}
  ],
  "sadakat": [
    {"id": "S1", "sorun": true, "kural": "sadakat A anlam kayması",
     "eski": "Rüzgârın sesiyle sessizlik çekildi.",
     "yeni": "Rüzgârın sesiyle sessizlik çöktü.",
     "neden": "ZH 寂静降临: sessizlik çöktü, çekildi değil."}
  ]
}
```"""
    monkeypatch.setattr(O, "_gruplari_yukle", lambda no: {
        i: {"TR": d["eski"], "ZH": "原文"} for i, d in enumerate(bulgular, 1)
    })
    son, bilgi = O.zh_sonuc_uygula(8, bolum, bulgular, sadakat, zh_cikti)
    assert not bilgi
    assert len(son) == 3
    assert not son[0].get("zh_engel")  # ONAY -> otomatik 1.6 icin hala uygun
    assert son[1].get("zh_engel") and "ZH kontrol ret" in son[1]["dikkat"]
    assert son[2]["kural"] == "sadakat A anlam kayması" and son[2]["yeni"].endswith("çöktü.")


def test_ucdan_uca_coklu_bolum_tek_inceleme_ve_sunucu(tmp_path, monkeypatch):
    kok = tmp_path / "LotM"
    bolumler = kok / "Imperium34.github.io" / "_chapters"
    bolumler.mkdir(parents=True)
    (kok / "Tools").mkdir()
    rapor = tmp_path / "okuma"
    kararlar = tmp_path / "kararlar.md"
    ist = tmp_path / "ist.tsv"
    motor_ist = tmp_path / "motor.tsv"
    yedek = tmp_path / "yedek"

    for ad, deger in {
        "LOTM_KOK": kok, "LOTM_OKUMA_RAPOR": rapor, "LOTM_KARARLAR": kararlar,
        "LOTM_ISTATISTIK": ist, "LOTM_MOTOR_IST": motor_ist, "LOTM_YEDEK": yedek,
    }.items():
        monkeypatch.setenv(ad, str(deger))
    monkeypatch.setattr(O, "RAPOR", rapor)
    monkeypatch.setattr(S, "BOLUMLER", bolumler)
    monkeypatch.setattr(S, "KARARLAR", kararlar)
    monkeypatch.setattr(S, "ISTATISTIK", ist)
    monkeypatch.setattr(S, "MOTOR_IST", motor_ist)

    (bolumler / "0001.md").write_text(
        "---\ndate: 2020-01-01 20:00:00 +0300\n---\n\n"
        "Klein saatini çıkarıp saate baktı.\n\n"
        "Kapıyı açan Klein, odaya girdi.\n",
        encoding="utf-8",
    )
    (bolumler / "0002.md").write_text(
        "---\ndate: 2020-01-01 20:00:00 +0300\n---\n\n"
        "Dunn kapıyı kapatıp kapıya yaslandı.\n\n"
        "Ağır ağır konuştu. \"Gidelim.\"\n",
        encoding="utf-8",
    )

    # Hazirla + sahte okuma ciktilari (ZH kontrol kapali)
    for no, cikti in [
        (1, "## (2) Bulgular\n\n"
            "    ¶1  1.6  (c)  saat tekrarı\n"
            "        ✗ Klein saatini çıkarıp saate baktı.\n"
            "        ✓ Klein saatini çıkarıp baktı.\n\n"
            "    ¶2  1.2  (d)  sıfat-fiil girişi\n"
            "        ✗ Kapıyı açan Klein, odaya girdi.\n"
            "        ✓ Klein kapıyı açıp odaya girdi.\n"),
        (2, "## (2) Bulgular\n\n"
            "    ¶1  1.6  (c)  kapı tekrarı\n"
            "        ✗ Dunn kapıyı kapatıp kapıya yaslandı.\n"
            "        ✓ Dunn kapıyı kapatıp yaslandı.\n\n"
            "    ¶2  1.7(ii)  (c)  boş konuştu\n"
            "        ✗ Ağır ağır konuştu. \"Gidelim.\"\n"
            "        ✓ \"Gidelim.\" dedi ağır ağır.\n"),
    ]:
        k = rapor / f"Ch_{no}"
        k.mkdir(parents=True)
        (k / "girdi.md").write_text("g", encoding="utf-8")
        (k / "cikti.md").write_text(cikti, encoding="utf-8")

    kod, ozet = O.birlesik_inceleme_kur(
        [1, 2], "1-2", zh_kontrol=False, cift_okuma=False,
        motor_secimleri={}, kuru=False, kesin_yok=False,
    )
    assert kod == 0, ozet
    inc_yol = rapor / "1-2" / "inceleme.md"
    assert inc_yol.exists()
    # okuma 1.6 iki bolumde de otomatik uygulandi
    assert "Klein saatini çıkarıp baktı." in (bolumler / "0001.md").read_text(encoding="utf-8")
    assert "Dunn kapıyı kapatıp yaslandı." in (bolumler / "0002.md").read_text(encoding="utf-8")
    assert list(yedek.rglob("0001.md")) and list(yedek.rglob("0002.md"))

    # inceleme_sunucu ile coklu bolum incele + bir geri al + iki kabul + uygula
    kip = I.Kip("okuma", dosya_yolu=inc_yol)
    oturum = I.Oturum(kip, ["1-2"], yol=inc_yol)
    sunucu = ThreadingHTTPServer(("127.0.0.1", 0), None)
    kapandi = threading.Event()
    sunucu.RequestHandlerClass = I.uygulama(oturum, kapat=lambda: (sunucu.shutdown(), kapandi.set()))
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    adres = f"http://127.0.0.1:{sunucu.server_address[1]}"

    def post(yol, govde):
        req = urllib.request.Request(
            adres + yol, data=json.dumps(govde).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        return json.loads(urllib.request.urlopen(req, timeout=30).read())

    d = json.loads(urllib.request.urlopen(adres + "/api/maddeler", timeout=10).read())
    kararlar_m = [m for m in d["maddeler"] if m.get("tur") != "uyg"]
    uyg_m = [m for m in d["maddeler"] if m.get("tur") == "uyg"]
    assert {m["bolum"] for m in kararlar_m} == {1, 2}
    assert {u["bolum"] for u in uyg_m} == {1, 2}
    assert all(m["tr"] for m in kararlar_m)

    # K1 (Ch_1) kabul + hep, K2 (Ch_2) kabul, U1 (Ch_1 otomatik) geri al
    post("/api/madde", {"k": 1, "kabul": True, "ret": False, "hep": True})
    post("/api/madde", {"k": 2, "kabul": True, "ret": False, "hep": False})
    post("/api/geri", {"i": 1, "geri": True})

    son = post("/api/uygula", {})
    assert son["bitti"]
    assert kapandi.wait(5)

    m1 = (bolumler / "0001.md").read_text(encoding="utf-8")
    m2 = (bolumler / "0002.md").read_text(encoding="utf-8")
    assert "Klein saatini çıkarıp saate baktı." in m1  # U1 geri alindi
    assert "Klein kapıyı açıp odaya girdi." in m1      # K1 uygulandi
    assert "\"Gidelim.\" dedi ağır ağır." in m2        # K2 uygulandi
    assert kararlar.exists() and "1. bölüm ¶2" in kararlar.read_text(encoding="utf-8")
    assert ist.exists() and kip.islenmis("1-2")


@pytest.fixture
def onizleme_kosu(tmp_path, monkeypatch):
    bolum = tmp_path / "0001.md"
    bolum.write_text("Klein saatini çıkarıp saate baktı.\n", encoding="utf-8")
    rapor = tmp_path / "rapor"
    klasor = rapor / "Ch_1"
    klasor.mkdir(parents=True)
    (klasor / "girdi.md").write_text("girdi", encoding="utf-8")
    (klasor / "cikti.md").write_text(
        "## (2) Bulgular\n\n"
        "    ¶1  1.6  (c)  saat tekrarı\n"
        "        ✗ Klein saatini çıkarıp saate baktı.\n"
        "        ✓ Klein saatini çıkarıp baktı.\n", encoding="utf-8")
    monkeypatch.setattr(O, "RAPOR", rapor)
    monkeypatch.setattr(S, "BOLUMLER", tmp_path)
    monkeypatch.setattr(S, "KESIN_YOK", False)
    monkeypatch.setattr(O, "bolum_calistir", lambda *args: (0, "okuma TAMAM"))
    return bolum, rapor, klasor


@pytest.mark.parametrize(("sonuc", "zh", "neden"), [
    (None, "", "hizalama yok"),
    ("bozuk", "原文", "JSON okunamadı"),
    ("", "原文", "JSON okunamadı"),
    ('[{"inceleme": [{"id": "M1", "karar": "ONAY"}]}]', "原文", "JSON nesne değil"),
    ('{"inceleme": [{"id": "M1", "karar": "RET", "karar": "ONAY"}]}', "原文", "yinelenen JSON alanı"),
    ([], "原文", "karar eksik"),
    ([{"id": "M1"}], "原文", "karar eksik"),
    ([{"id": "M1", "karar": "ONAY"}] * 2, "原文", "yinelenen karar"),
    ([{"id": "M1", "karar": "BELKİ"}], "原文", "bilinmeyen karar"),
    ([None], "原文", "biçimsiz"),
    ([{"id": "M1", "karar": "ONAY"}], "", "hizalama yok"),
    ([{"id": "M1", "karar": "ONAY"}], "原文", None),
])
def test_zh_otomatik_icin_acik_onay_ve_hizalama(onizleme_kosu, monkeypatch, sonuc, zh, neden):
    bolum, rapor, klasor = onizleme_kosu
    monkeypatch.setattr(O, "_gruplari_yukle", lambda no: {1: {"TR": bolum.read_text(), "ZH": zh}})
    if sonuc is not None:
        (klasor / "zh_girdi.md").write_text("girdi", encoding="utf-8")
        (klasor / "zh_cikti.md").write_text(
            sonuc if isinstance(sonuc, str) else json.dumps({"inceleme": sonuc}), encoding="utf-8")
    assert O.main(["1", "--kuru", "--zh-kontrol"]) == 0
    preview = (rapor / "Ch_1" / S.INCELEME_ONIZLEME).read_text(encoding="utf-8")
    if neden:
        assert neden in preview
        assert "otomatik düzenlemeler (0)" in preview
    else:
        assert "otomatik düzenlemeler (1)" in preview


@pytest.mark.parametrize("yeniden", [[], ["--yeniden"]])
def test_kuru_canli_incelemeyi_korur(onizleme_kosu, yeniden):
    bolum, rapor, klasor = onizleme_kosu
    hedef = klasor
    canli = hedef / "inceleme.md"
    canli.write_text("### K1\n[x] kabul\n", encoding="utf-8")
    for ad in (O.UYGULANDI, O.KARARLAR_ISLENDI):
        (hedef / ad).write_text('{"işaret": true}', encoding="utf-8")
    onceki = {p: p.read_bytes() for p in [bolum, *hedef.iterdir(), *klasor.iterdir()]}
    assert O.main(["1", "--kuru", "--zh-kontrol-yok", *yeniden]) == 0
    preview = hedef / S.INCELEME_ONIZLEME
    metin = preview.read_text(encoding="utf-8")
    assert "Simüle edilen otomatik düzenlemeler (1)" in metin
    assert "Bunlar bölüme yazıldı" not in metin and "--kararlar" not in metin
    assert O.main(["1", "--kararlar", "--dosya", str(preview)]) == 1
    with pytest.raises(SystemExit) as exc:
        O.main(["1", "--kuru", "--bastan"])
    assert exc.value.code == 2
    assert {p: p.read_bytes() for p in onceki} == onceki


def test_toplu_okuma_bir_bolum_eskirse_canli_incelemeyi_korur(onizleme_kosu, monkeypatch, capsys):
    bolum, rapor, klasor = onizleme_kosu
    ikinci = bolum.with_name("0002.md")
    ikinci.write_bytes(bolum.read_bytes())
    for ad in ("girdi.md", "cikti.md"):
        hedef = rapor / "Ch_2" / ad
        hedef.parent.mkdir(exist_ok=True)
        hedef.write_bytes((klasor / ad).read_bytes())
    toplu = rapor / "1-2"
    toplu.mkdir()
    onceki = {toplu / ad: b"canli" for ad in ("inceleme.md", O.UYGULANDI, O.KARARLAR_ISLENDI)}
    for yol, veri in onceki.items():
        yol.write_bytes(veri)
    yedek = bolum.parent / "yedek"
    monkeypatch.setenv("LOTM_YEDEK", str(yedek))
    ilk = bolum.read_bytes()

    def model(no, *_):
        if no == 2:
            ikinci.write_bytes(ilk + b"editor")
        return 0, "okuma TAMAM"

    monkeypatch.setattr(O, "bolum_calistir", model)
    assert O.main(["1-2", "--yeniden", "--zh-kontrol-yok"]) == 1
    assert "0002.md" in capsys.readouterr().out
    assert bolum.read_bytes() == ilk and ikinci.read_bytes() == ilk + b"editor"
    assert {yol: yol.read_bytes() for yol in onceki} == onceki
    assert not yedek.exists()
