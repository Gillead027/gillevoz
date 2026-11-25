"""Remoção do atalho de inicialização do v1 (sem tocar a pasta Inicializar real)."""
from gillevoz import startup


def _preparar(monkeypatch, tmp_path, alvo):
    monkeypatch.setattr(startup, "_pasta_inicializar", lambda: str(tmp_path))
    monkeypatch.setattr(startup, "_alvo_atalho", lambda caminho: alvo)
    lnk = tmp_path / startup.NOME_ATALHO
    lnk.write_bytes(b"lnk")
    return lnk


def test_remover_v1_apaga_atalho_do_vbs(monkeypatch, tmp_path):
    lnk = _preparar(monkeypatch, tmp_path, r'C:\Windows\System32\wscript.exe "C:\x\GilleVoz.vbs"')
    assert startup.remover_v1() is True
    assert not lnk.exists()


def test_remover_v1_mantem_atalho_de_outro_alvo(monkeypatch, tmp_path):
    lnk = _preparar(monkeypatch, tmp_path, r"C:\Programas\GilleVoz\GilleVoz.exe")
    assert startup.remover_v1() is False
    assert lnk.exists()


def test_remover_v1_sem_atalho(monkeypatch, tmp_path):
    monkeypatch.setattr(startup, "_pasta_inicializar", lambda: str(tmp_path))
    assert startup.remover_v1() is False
