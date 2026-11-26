"""Atalho com botão lateral do mouse: parse/validação e a decisão do gancho (sem gancho real)."""
import pytest

from gillevoz import hotkey
from gillevoz.hotkey import (MOD_ALT, MOD_CONTROL, WM_XBUTTONDOWN, WM_XBUTTONUP, Assinante,
                             decidir_evento)


# ------------------------------------------------------------ parse / validar
def test_parse_atalho_mouse():
    assert hotkey.parse_atalho_mouse("mouse4") == (0, 1)
    assert hotkey.parse_atalho_mouse("mouse5") == (0, 2)
    assert hotkey.parse_atalho_mouse("ctrl+mouse4") == (MOD_CONTROL, 1)
    assert hotkey.parse_atalho_mouse("ctrl+alt+space") is None


def test_parse_atalho_mouse_nao_colide_com_teclado():
    # o motor usa parse_atalho para achar atalho repetido: mouse4 != mouse5 != qualquer tecla
    combos = {hotkey.parse_atalho(a) for a in ("mouse4", "mouse5", "ctrl+mouse4", "f9", "ctrl+a")}
    assert len(combos) == 5


@pytest.mark.parametrize("atalho", ["mouse4", "mouse5", "ctrl+mouse4", "Shift+Mouse5"])
def test_validar_aceita_botoes_laterais(atalho):
    assert hotkey.validar_atalho(atalho) is None


@pytest.mark.parametrize("atalho", ["mouse1", "mouse2", "mouse3", "ctrl+mouse1", "mouse6"])
def test_validar_recusa_outros_botoes(atalho):
    assert hotkey.validar_atalho(atalho) is not None


def test_validar_continua_recusando_so_modificadores():
    assert "tecla comum" in hotkey.validar_atalho("ctrl+alt")


# ------------------------------------------------------------ decisão do gancho
def _ass(mods=0, botao=1):
    ev = []
    return Assinante(mods, botao, lambda: ev.append("apertar"), lambda: ev.append("soltar")), ev


def _dados(botao):
    return botao << 16  # o botão vem na palavra alta de mouseData


def test_botao_certo_engole_e_chama_apertar():
    a, ev = _ass()
    apertados = {}
    engolir, chamadas = decidir_evento(WM_XBUTTONDOWN, _dados(1), 0, [a], apertados)
    assert engolir
    for c in chamadas:
        c()
    assert ev == ["apertar"]


def test_soltar_chama_on_soltar_mesmo_sem_o_modificador():
    a, ev = _ass(mods=MOD_CONTROL)
    apertados = {}
    decidir_evento(WM_XBUTTONDOWN, _dados(1), MOD_CONTROL, [a], apertados)
    engolir, chamadas = decidir_evento(WM_XBUTTONUP, _dados(1), 0, [a], apertados)  # soltou o Ctrl antes
    assert engolir
    for c in chamadas:
        c()
    assert ev == ["soltar"]
    assert apertados == {}


def test_modificador_exigido_ausente_nao_casa_nem_engole():
    a, _ = _ass(mods=MOD_CONTROL)
    apertados = {}
    assert decidir_evento(WM_XBUTTONDOWN, _dados(1), 0, [a], apertados) == (False, [])
    assert decidir_evento(WM_XBUTTONUP, _dados(1), 0, [a], apertados) == (False, [])


def test_modificador_a_mais_nao_casa():
    a, _ = _ass()
    assert decidir_evento(WM_XBUTTONDOWN, _dados(1), MOD_ALT, [a], {}) == (False, [])


def test_outro_botao_nao_casa():
    a, _ = _ass(botao=1)
    assert decidir_evento(WM_XBUTTONDOWN, _dados(2), 0, [a], {}) == (False, [])


def test_sem_assinantes_nunca_engole():
    assert decidir_evento(WM_XBUTTONDOWN, _dados(1), 0, [], {}) == (False, [])
    assert decidir_evento(WM_XBUTTONUP, _dados(1), 0, [], {}) == (False, [])


def test_evento_injetado_ignorado():
    a, _ = _ass()
    apertados = {}
    assert decidir_evento(WM_XBUTTONDOWN, _dados(1), 0, [a], apertados, injetado=True) == (False, [])
    assert apertados == {}


def test_outras_mensagens_passam():
    a, _ = _ass()
    assert decidir_evento(0x0201, 0, 0, [a], {}) == (False, [])  # WM_LBUTTONDOWN
