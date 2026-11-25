"""Clipboard real do Windows; nenhuma tecla enviada à janela do usuário.

O backup original é restaurado pelo fixture mesmo quando um teste falha.
"""
import struct

import pytest
import pyperclip
import win32clipboard

from gillevoz import paste


@pytest.fixture
def clipboard(monkeypatch):
    # O código atual não salva CF_HDROP (arquivos copiados no Explorer).
    # Não apagar arquivos que o próprio usuário deixou no clipboard.
    if win32clipboard.IsClipboardFormatAvailable(15):
        pytest.skip('Clipboard do usuário contém arquivos; preservar sem alteração')
    original = paste.salvar_clipboard()
    assert original[0] == 'win32', 'Backup completo necessário antes de alterar o clipboard'
    monkeypatch.setattr(paste, 'soltar_modificadoras', lambda: None)
    monkeypatch.setattr(paste, '_enviar', lambda inputs: pytest.fail('Teclas reais proibidas neste teste'))
    try:
        paste.colocar_texto('original: ação e coração')
        yield
    finally:
        paste.restaurar_clipboard(original)


def test_salvar_e_restaurar_texto_real(clipboard):
    backup = paste.salvar_clipboard()
    paste.colocar_texto('temporário')
    paste.restaurar_clipboard(backup)
    assert pyperclip.paste() == 'original: ação e coração'


@pytest.mark.parametrize('texto,espaco,esperado', [
    ('ação', False, 'ação'), ('ação', True, 'ação '),
    ('ação ', True, 'ação '), ('ação\n', True, 'ação\n'),
])
def test_colar_restaurar_sem_enter(clipboard, monkeypatch, texto, espaco, esperado):
    visto = []
    monkeypatch.setattr(paste, 'enviar_ctrl_v', lambda: visto.append(pyperclip.paste()))
    monkeypatch.setattr(paste, 'enviar_enter', lambda: pytest.fail('auto_enter=False enviou Enter'))
    paste.colar(texto, auto_enter=False, espera_ms=0, espaco_final=espaco)
    assert visto == [esperado]
    assert pyperclip.paste() == 'original: ação e coração'


def test_outro_app_copia_durante_colagem(clipboard, monkeypatch):
    monkeypatch.setattr(paste, 'enviar_ctrl_v', lambda: paste.colocar_texto('novo do usuário'))
    paste.colar('ditado', espera_ms=0)
    assert pyperclip.paste() == 'novo do usuário'


def test_clipboard_restaurado_quando_colagem_falha(clipboard, monkeypatch):
    def falhar():
        raise RuntimeError('falha simulada após colocar texto')
    monkeypatch.setattr(paste, 'enviar_ctrl_v', falhar)
    with pytest.raises(RuntimeError):
        paste.colar('ditado', espera_ms=0)
    assert pyperclip.paste() == 'original: ação e coração'


def test_arquivos_copiados_no_explorer_restaurados(clipboard, monkeypatch):
    nomes = ('C:\\teste-gillevoz\\arquivo.txt\0\0').encode('utf-16-le')
    dropfiles = struct.pack('<IiiII', 20, 0, 0, 0, 1) + nomes
    paste._abrir_clipboard(win32clipboard)
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(15, dropfiles)
        assert win32clipboard.GetClipboardData(15) == ('C:\\teste-gillevoz\\arquivo.txt',)
    finally:
        win32clipboard.CloseClipboard()
    monkeypatch.setattr(paste, 'enviar_ctrl_v', lambda: None)
    paste.colar('ditado', espera_ms=0)
    assert win32clipboard.IsClipboardFormatAvailable(15), 'Lista de arquivos copiados foi perdida'


@pytest.mark.parametrize('espaco,esperado', [(False, 'ação'), (True, 'ação ')])
def test_digitar_sem_enter_e_sem_tocar_clipboard(clipboard, monkeypatch, espaco, esperado):
    visto = []
    monkeypatch.setattr(paste, 'digitar', visto.append)
    monkeypatch.setattr(paste, 'enviar_enter', lambda: pytest.fail('Enter não autorizado'))
    paste.colar('ação', metodo='digitar', auto_enter=False, espaco_final=espaco)
    assert visto == [esperado]
    assert pyperclip.paste() == 'original: ação e coração'


def test_auto_enter_explicito(clipboard, monkeypatch):
    eventos = []
    monkeypatch.setattr(paste, 'enviar_ctrl_v', lambda: eventos.append('colar'))
    monkeypatch.setattr(paste, 'enviar_enter', lambda: eventos.append('enter'))
    paste.colar('texto', auto_enter=True, espera_ms=0)
    assert eventos == ['colar', 'enter']


def test_apagar_envia_backspace_n_vezes(monkeypatch):
    enviados = []
    monkeypatch.setattr(paste, '_enviar', lambda inputs: enviados.extend(inputs))
    paste.apagar(3)
    assert len(enviados) == 6
    assert all(i.u.ki.wVk == 0x08 for i in enviados)
    assert [bool(i.u.ki.dwFlags & paste.KEYEVENTF_KEYUP) for i in enviados] == [False, True] * 3
    enviados.clear()
    paste.apagar(0)
    assert enviados == []


def test_digitar_espera_mais_depois_de_fim_de_palavra(monkeypatch):
    """Bloco de Notas do Win11 trava um instante depois de espaço/pontuação (corretor).

    Se a próxima letra chega durante a trava, as teclas Unicode pendentes saem todas
    com a letra mais nova ("Gillezin. Quero" virou "Gillezin.QQuero"). Por isso a pausa
    depois de um caractere que fecha palavra é maior — inclusive no fim do trecho,
    porque o próximo trecho do tempo real vem logo em seguida.
    """
    eventos = []
    monkeypatch.setattr(paste, '_enviar', lambda inputs: eventos.append(chr(inputs[0].u.ki.wScan)))
    monkeypatch.setattr(paste.time, 'sleep', lambda s: eventos.append(s))
    paste.digitar('ab c.')
    assert paste.PAUSA_FIM_PALAVRA_S > paste.PAUSA_DIGITAR_S
    curta, longa = paste.PAUSA_DIGITAR_S, paste.PAUSA_FIM_PALAVRA_S
    assert eventos == ['a', curta, 'b', curta, ' ', longa, 'c', curta, '.', longa]


def test_digitar_letra_acentuada_nao_e_fim_de_palavra(monkeypatch):
    pausas = []
    monkeypatch.setattr(paste, '_enviar', lambda inputs: None)
    monkeypatch.setattr(paste.time, 'sleep', pausas.append)
    paste.digitar('ação')
    assert pausas == [paste.PAUSA_DIGITAR_S] * 4
