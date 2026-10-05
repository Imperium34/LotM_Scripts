# -*- coding: utf-8 -*-
"""
bolum.hizala -- kaynak dipnotu.

Paragraflar Bolum 28'in sonundan, oldugu gibi. Dipnot eskiden son Turkce
paragrafi kendine cekiyordu; "Kapkaççı" bu yuzden yanlis bir ESLESMEYEN
olarak raporlandi.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bolum as B  # noqa: E402

ZH = [
    "“第三种我们只有序列9，‘圣堂’有没有藏着别的，我就不清楚了，它叫做‘占卜家’。”",
    "占卜家？克莱恩瞳孔微缩，想到了罗塞尔大帝在日记里留下的遗憾：",
    "他后悔当初没在学徒、偷盗者和占卜家之中选择！",
    "注1：改编自爱德华·菲兹杰拉德英译的《鲁拜集》。",
]
TR = [
    'Dunn Smith yan gözle kızıl aya bakarak, "Üçüncü Yolun sadece Mertebe 9\'u '
    'elimizde var. Kutsal Katedral\'de devamı var mıdır, emin değilim," dedi. '
    '"Adı, Kâhin."',
    "_Kâhin mi?_",
    "İmparator Roselle'in günlüğüne düştüğü o pişmanlığı anımsayan Klein'ın göz "
    "bebekleri daraldı: Çırak, Kapkaççı veya Kâhin'i seçmemiş olmaktan pişmandı!",
]


def test_dipnot_tanima():
    assert B.dipnot_mu(ZH[3])
    assert B.dipnot_mu("注：一段说明")
    assert not B.dipnot_mu(ZH[1])


def test_dipnot_tek_basina_kalir_ve_anlatiyi_birakmaz():
    gruplar = B.hizala(ZH, TR)
    assert ([3], []) in gruplar
    # Marauder'in gectigi Cince paragraf, Kapkaççı'nin gectigi Turkce
    # paragrafla ayni grupta
    grup = next(g for g in gruplar if 2 in g[0])
    assert 2 in grup[1]


def test_dipnotsuz_bolum_degismez():
    assert B.hizala(ZH[:3], TR) == [([0], [0]), ([1], [1]), ([2], [2])]
