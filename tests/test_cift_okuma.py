# -*- coding: utf-8 -*-
"""Cift okuma (22 Kas): ikinci okuyucunun dosya adi, inceleme satiri, istatistik."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import motorlar as M  # noqa: E402
import sonra as S  # noqa: E402

BLOK = """## 1. Anlam

### K1 · ¶3 · KARAR · okuma 1.2
✗ a
✓ b
Neden: x
Kaynak: okuma
Okuma: codex
[x] kabul   [ ] ret   [ ] hep

### K2 · ¶4 · KARAR · sadakat B
✗ c
✓ d
Neden: y
Kaynak: sadakat
Sadakat: ikisi
[ ] kabul   [x] ret   [ ] hep
"""


def test_motor_adi():
    assert M.cikti_motoru(Path("1_okuma_cikti.codex.md"), "") == "codex"
    assert M.cikti_motoru(Path("1_okuma_cikti.md"), "x") == "x"
    assert M.ikinci_motor("antigravity", None, "okuma") == "codex"


def test_kayit_ve_ozet(tmp_path):
    secim = S.inceleme_oku(BLOK)
    assert secim[0]["omotor"] == "codex" and secim[1]["smotor"] == "ikisi"
    yol = tmp_path / "karar_motor.tsv"
    S.motor_kaydet(yol, 90, secim)
    ozet = S.motor_ozeti(yol)
    assert "Çift sadakat (1 bölüm: 90)" in ozet and "Çift okuma (1 bölüm: 90)" in ozet
    okuma = ozet.split("Çift okuma")[1]
    assert [s for s in okuma.splitlines() if s.startswith("codex")][0].split()[1] == "1"


def test_istatistik_akislar_ve_eski_satirlar(tmp_path, monkeypatch):
    import inceleme_sunucu as I

    ist = tmp_path / "istatistik.tsv"
    motor = tmp_path / "motor.tsv"
    ist.write_text("bolum\tk\taile\ton\tkarar\n"
                   "90\tK1\tokuma 1.2\t0\tret\n"
                   "91\tK1\tokuma 1.2\t0\tret\n", encoding="utf-8")
    motor.write_text("bolum\tk\tsinif\tkural\tsadakat\tkarar\n"
                     "90\tK1\tKARAR\tokuma 1.2\tokuma:claude\tret\n"
                     "90\tK2\tKARAR\tsadakat B\tikisi\tkabul\n", encoding="utf-8")
    monkeypatch.setattr(S, "ISTATISTIK", ist)
    monkeypatch.setattr(S, "RAPOR", tmp_path / "sonra")
    secim = S.inceleme_oku(BLOK)
    S.istatistik_kaydet(ist, 90, secim[:1], "okuma")
    S.motor_kaydet(motor, 90, secim[:1], "okuma")
    kip = I.Kip("sonra")
    inceleme = kip.yol(90)
    inceleme.parent.mkdir(parents=True)
    inceleme.write_text(BLOK, encoding="utf-8")
    assert kip.istatistikte() == {91}
    assert not kip.islenmis(90)
    assert {(p[4], p[-1]) for p in S.guncel_istatistik(motor, motor=True)} == {
        ("okuma:codex", "okuma"), ("ikisi", "")
    }
    S.istatistik_kaydet(ist, 90, secim, "sonra")
    S.istatistik_kaydet(ist, 90, secim, "sonra")
    S.motor_kaydet(motor, 90, secim, "sonra")
    assert [(p[0], p[-1]) for p in S.guncel_istatistik(ist)] == [
        ("91", ""), ("90", "okuma"), ("90", "sonra"), ("90", "sonra")
    ]
    assert {(p[4], p[-1]) for p in S.guncel_istatistik(motor, motor=True)} == {
        ("okuma:codex", "okuma"), ("okuma:codex", "sonra"), ("ikisi", "sonra")
    }
    assert [s for s in S.istatistik_ozeti(ist).splitlines() if s.startswith("okuma 1.2")][0].split()[2:5] == ["2", "1", "0"]
    S.motor_kaydet(motor, 90, [], "okuma")
    assert {p[-1] for p in S.guncel_istatistik(motor, motor=True)} == {"sonra"}
