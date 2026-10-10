# -*- coding: utf-8 -*-
"""
capa.py ve hizalama_denetle.py'nin ic testleri (--kendini-dene).

Eskiden yalnizca elle cagrilinca calisiyorlardi; pytest onlari hic
gormuyordu ve kirilsalar kimse fark etmezdi.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import capa  # noqa: E402
import hizalama_denetle  # noqa: E402


def test_capa_kendini_dene(capsys):
    assert capa.kendini_dene() == 0, capsys.readouterr().out


def test_hizalama_denetle_kendini_dene(capsys):
    assert hizalama_denetle.kendini_dene() == 0, capsys.readouterr().out
