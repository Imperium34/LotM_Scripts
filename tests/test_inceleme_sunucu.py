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
