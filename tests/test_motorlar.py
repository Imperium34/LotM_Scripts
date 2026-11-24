# -*- coding: utf-8 -*-
"""motorlar.py: sahte claude/codex/agy kabuk betikleriyle (LOTM_CLAUDE/LOTM_CODEX/LOTM_AGY)."""

from pathlib import Path

import motorlar as M
import sonra as S


def _betik(yol: Path, govde: str) -> Path:
    yol.write_text("#!/bin/sh\n" + govde, encoding="utf-8")
    yol.chmod(0o755)
    return yol


def _claude(t: Path, monkeypatch, govde='echo "$@" > "$(dirname "$0")/args"\ncat\n'):
    monkeypatch.setenv("LOTM_CLAUDE", str(_betik(t / "claude", govde)))
    return t / "args"


def _codex(t: Path, monkeypatch):
    # --output-last-message'dan sonraki argumana "SON: <stdin>" yazar, ekrana iz basar.
    _betik(t / "codex", 'echo "$@" > "$(dirname "$0")/args"\n'
                        'while [ $# -gt 0 ]; do [ "$1" = --output-last-message ] && f="$2"; shift; done\n'
                        'printf "SON: " > "$f"; cat >> "$f"\necho "codex iz satiri"\n')
    monkeypatch.setenv("LOTM_CODEX", f"{t / 'codex'} exec")
    return t / "args"


def _agy(t: Path, monkeypatch):
    # stdin'den bir sey gelirse STDIN basar; -p='<dosya> dosyasını...' yolunu acar.
    _betik(t / "agy", 'echo "$@" > "$(dirname "$0")/args"\n'
                      'g=$(cat); [ -n "$g" ] && echo STDIN\n'
                      'for a; do f="$a"; done\nf=${f#-p=}; f=${f%% dosyasını*}\n'
                      'echo "$f" > "$(dirname "$0")/yol"\nprintf "CEVAP: "; cat "$f"\n')
    monkeypatch.setenv("LOTM_AGY", f"{t / 'agy'} --output-format text --disable-slash-commands --mode plan")
    return t / "args"


def test_claude_stdin_ve_ek_argumanlar(tmp_path, monkeypatch):
    args = _claude(tmp_path, monkeypatch)
    s = M.calistir("merhaba", "claude", sure=30, cwd=tmp_path, ek_argumanlar=["--tools", "x"], kota={})
    assert s.ok and s.metin == "merhaba" and s.motor == "claude"
    a = args.read_text()
    assert "--model" in a and "--effort" in a and a.rstrip().endswith("--tools x")


def test_codex_son_mesaj_dosyasi_silinir(tmp_path, monkeypatch):
    args = _codex(tmp_path, monkeypatch)
    oneki = tmp_path / "cikti.md"
    s = M.calistir("girdi metni", "codex", sure=30, cwd=tmp_path, gecici=oneki, kota={})
    assert s.ok and s.metin == "SON: girdi metni"  # stdout'taki iz degil, son mesaj
    assert "-s read-only" in args.read_text()
    assert not (tmp_path / "cikti.md.codex-son").exists()


def test_agy_stdin_yok_istem_dosyada_ve_silinir(tmp_path, monkeypatch):
    args = _agy(tmp_path, monkeypatch)
    is_ = tmp_path / "is"
    is_.mkdir()
    s = M.calistir("x" * 200_000 + "\nson", "antigravity", sure=30, cwd=is_, kota={})
    assert s.ok and s.metin.startswith("CEVAP: xxx") and "STDIN" not in s.metin
    a = args.read_text()
    assert "-p=" in a and "--mode plan" in a and "--effort" not in a
    yol = Path((tmp_path / "yol").read_text().strip())
    assert yol.is_absolute() and yol.parent == is_.resolve()
    assert list(is_.iterdir()) == []  # gecici girdi silindi


def test_agy_arac_isterse_claude(tmp_path, monkeypatch, capsys):
    _agy(tmp_path, monkeypatch)
    args = _claude(tmp_path, monkeypatch)
    s = M.calistir("selam", "antigravity", sure=30, araclar=["Read"], cwd=tmp_path, kota={})
    assert s.ok and s.motor == "claude" and "--allowedTools Read" in args.read_text()
    assert "antigravity arac izni ayarlanamiyor" in capsys.readouterr().out


def test_kota_dolunca_bir_daha_cagrilmaz(tmp_path, monkeypatch, capsys):
    _claude(tmp_path, monkeypatch, 'cat >/dev/null\necho "You have hit your usage limit" >&2\nexit 1\n')
    kota = {}
    s = M.calistir("a", "claude", sure=30, cwd=tmp_path, kota=kota)
    assert not s.ok and s.kota and "usage limit" in kota["claude"]
    out = capsys.readouterr().out
    assert "HATA (cikis 1)" in out and "KOTA claude:" in out
    _claude(tmp_path, monkeypatch)  # artik basarirdi, ama denenmez
    s = M.calistir("a", "claude", sure=30, cwd=tmp_path, kota=kota)
    assert not s.ok and "ATLANDI claude" in capsys.readouterr().out


def test_komut_yoksa_hata_ve_motor_sec_duser(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LOTM_CLAUDE", str(tmp_path / "yok-boyle"))
    assert not M.calistir("a", "claude", sure=30, cwd=tmp_path, kota={}).ok
    assert "HATA: claude komutu bulunamadi" in capsys.readouterr().out
    monkeypatch.setenv("LOTM_CODEX", str(tmp_path / "yok-boyle"))
    monkeypatch.delenv("LOTM_MOTOR_CEVIR", raising=False)
    assert M.motor_sec("cevir", {"cevir": "codex"}) == "claude"
    assert M.motor_sec("cevir") == "claude"
    monkeypatch.setenv("LOTM_MOTOR_CEVIR", "codex")
    _codex(tmp_path, monkeypatch)
    assert M.motor_sec("cevir") == "codex"


def test_sonra_yurut_motor_etiketi_ve_ortak_ad(tmp_path, monkeypatch):
    assert S.KOTA_DOLU is M.KOTA_DOLU and S.motor_sec is M.motor_sec
    _codex(tmp_path, monkeypatch)
    _claude(tmp_path, monkeypatch)
    monkeypatch.setattr(S, "KOTA_DOLU", {})
    girdi, cikti = tmp_path / "1_okuma_girdi.md", tmp_path / "1_okuma_cikti.md"
    girdi.write_text("metin", encoding="utf-8")
    assert S.yurut(girdi, cikti, None, 30, None, "codex")
    assert cikti.read_text(encoding="utf-8").startswith("SON: metin")
    assert M.etiket_oku(cikti) == "codex"
    assert S.yurut(girdi, cikti, None, 30, None, "claude")
    assert not (tmp_path / "1_okuma_cikti.md.motor").exists() and M.etiket_oku(cikti) == "claude"


def test_cevir_motor_adi():
    import cevir
    assert cevir.motor_adi("claude", "sonnet") == "sonnet"
    assert cevir.motor_adi("claude", None) == M.VARSAYILAN_MODEL
    assert cevir.motor_adi("codex", None).startswith("codex")


def test_agy_arac_dususu_claude_kotasina_uyar(tmp_path, monkeypatch, capsys):
    _agy(tmp_path, monkeypatch)
    _claude(tmp_path, monkeypatch)
    kota = {"claude": "session limit"}
    s = M.calistir("selam", "antigravity", sure=30, araclar=["Read"], cwd=tmp_path, kota=kota)
    assert not s.ok and s.kota and s.motor == "claude"
    assert "ATLANDI claude" in capsys.readouterr().out


def test_stdout_kota_stderr_gurultusunde_kacmaz(tmp_path, monkeypatch):
    _claude(tmp_path, monkeypatch,
            'cat >/dev/null\necho "DeprecationWarning: minor" >&2\n'
            'echo "You have hit your session limit · resets 6:30am"\nexit 1\n')
    kota = {}
    s = M.calistir("a", "claude", sure=30, cwd=tmp_path, kota=kota)
    assert not s.ok and s.kota and "session limit" in kota["claude"]


def test_bos_ortam_ve_bilinmeyen_motor(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setenv("LOTM_CODEX", "")
    assert M.codex_komutu(tmp_path / "son")[0] == "codex"
    with pytest.raises(ValueError):
        M.calistir("a", "bilinmeyen", sure=30, cwd=tmp_path, kota={})


def test_bes_saatlik_kota_yakalanir():
    assert M.KOTA.search("You've hit your 5-hour limit · resets 5:50pm (Europe/Istanbul) · out of usage credits")
    assert M.KOTA.search("out of credits")


def test_ikinci_motor_varsayilan_ve_secimler(tmp_path, monkeypatch):
    _codex(tmp_path, monkeypatch)
    _agy(tmp_path, monkeypatch)
    monkeypatch.delenv("LOTM_MOTOR_SADAKAT2", raising=False)
    assert M.ikinci_motor("antigravity") == "codex"
    assert M.ikinci_motor("codex") == "claude"
    assert M.ikinci_motor("codex", {"sadakat2": "antigravity"}) == "antigravity"
    monkeypatch.setenv("LOTM_CODEX", str(tmp_path / "yok-boyle"))
    assert M.ikinci_motor("antigravity") == "claude"
