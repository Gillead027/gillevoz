"""Validação de atalhos antes de registrar (sem registrar nada no Windows)."""
import pytest

from gillevoz import hotkey


def test_validar_atalho():
    assert hotkey.validar_atalho("ctrl+shift") is not None
    assert hotkey.validar_atalho("ctrl+shift+space") is None
    assert hotkey.validar_atalho("ctrl+xyz") is not None


@pytest.mark.parametrize("atalho", ["", "   ", "+", None, 5, ["ctrl", "a"]])
def test_validar_atalho_vazio_ou_nao_texto(atalho):
    erro = hotkey.validar_atalho(atalho)
    assert isinstance(erro, str) and erro


def test_validar_atalho_mensagens_em_portugues():
    assert "tecla comum" in hotkey.validar_atalho("ctrl+alt")
    assert "xyz" in hotkey.validar_atalho("ctrl+xyz")


@pytest.mark.parametrize("atalho", ["ctrl+alt+v", "f9", "ctrl+shift+c", "win+alt+space"])
def test_validar_atalho_aceita_validos(atalho):
    assert hotkey.validar_atalho(atalho) is None
