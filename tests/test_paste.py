"""Clipboard real do Windows; nenhuma tecla enviada à janela do usuário.

O backup original é restaurado pelo fixture mesmo quando um teste falha.
"""
import struct
import threading

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
    monkeypatch.setattr(paste, 'digitar', lambda t, *a, **k: visto.append(t) or '')
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


class GuardaFalsa:
    """Janela em foco sempre estável (nenhuma espera)."""

    def __init__(self):
        self.chamadas = 0

    def esperar(self, parar=None, limite_s=None):
        self.chamadas += 1
        return (0x1234, 'Notepad', 'notepad.exe')


def _texto_dos_eventos(inputs):
    """Reconstrói o texto de um SendInput Unicode (só as teclas para baixo)."""
    unidades = [i.u.ki.wScan for i in inputs
                if i.u.ki.dwFlags & paste.KEYEVENTF_UNICODE and not i.u.ki.dwFlags & paste.KEYEVENTF_KEYUP]
    return b''.join(u.to_bytes(2, 'little') for u in unidades).decode('utf-16-le')


@pytest.fixture
def teclado(monkeypatch):
    """Nenhuma tecla real: SendInput, pausas, modificadoras e janela em foco são falsos."""
    estado = {'eventos': [], 'presas': lambda vk: False, 'guarda': GuardaFalsa(), 'ao_enviar': None,
              'ao_dormir': None}

    def enviar(inputs):
        if inputs and inputs[0].u.ki.dwFlags & paste.KEYEVENTF_UNICODE:
            estado['eventos'].append(_texto_dos_eventos(inputs))
        else:
            estado['eventos'].append(
                ('teclas', [(i.u.ki.wVk, bool(i.u.ki.dwFlags & paste.KEYEVENTF_KEYUP)) for i in inputs]))
        if estado['ao_enviar']:
            estado['ao_enviar']()

    def dormir(s):
        estado['eventos'].append(s)
        if estado['ao_dormir']:
            estado['ao_dormir']()

    monkeypatch.setattr(paste, '_enviar', enviar)
    monkeypatch.setattr(paste.time, 'sleep', dormir)
    monkeypatch.setattr(paste, '_pressionada', lambda vk: estado['presas'](vk))
    monkeypatch.setattr(paste, '_guarda', estado['guarda'])
    return estado


def test_digitar_uma_tecla_por_vez_com_pausa_maior_depois_do_separador(teclado):
    """Bloco de Notas do Win11 trava um instante depois de espaço/pontuação (corretor).

    Teclas Unicode que chegam durante a trava saem trocadas ("Gillezin.QQuero") ou somem.
    Medido com tools/teste_digitacao.py: palavra inteira num SendInput errava; letra a letra
    com pausa (maior depois do separador, inclusive no fim do trecho) acertou.
    """
    assert paste.digitar(' ab. c', threading.Event()) == ''
    curta, longa = paste.PAUSA_DIGITAR_S, paste.PAUSA_FIM_PALAVRA_S
    assert curta < longa
    assert teclado['eventos'] == [' ', longa, 'a', curta, 'b', curta, '.', longa, ' ', longa, 'c', curta]


def test_digitar_acentos_e_emoji(teclado):
    paste.digitar('ã😀', threading.Event())
    assert teclado['eventos'] == ['ã', paste.PAUSA_DIGITAR_S, '😀', paste.PAUSA_FIM_PALAVRA_S]


def test_digitar_espera_modificadora_sem_soltar_por_ele(teclado):
    """Tempo real: Ctrl/Shift apertados (ex.: atalho de parar) -> espera, nunca injeta soltura."""
    polls = {'n': 0}

    def presas(vk):
        polls['n'] += 1
        return polls['n'] <= 20  # segura por alguns ciclos
    teclado['presas'] = presas
    assert paste.digitar('oi', threading.Event(), soltar_apos_s=None) == ''
    assert all(not isinstance(e, tuple) for e in teclado['eventos']), 'injetou soltura de modificadora'
    assert [e for e in teclado['eventos'] if isinstance(e, str)] == ['o', 'i']
    assert paste.PAUSA_ESPERA_S in teclado['eventos']


def test_digitar_final_solta_modificadora_presa(teclado, monkeypatch):
    agora = {'t': 0.0}

    def relogio():
        agora['t'] += 0.1
        return agora['t']
    monkeypatch.setattr(paste.time, 'monotonic', relogio)
    soltas = set()
    teclado['presas'] = lambda vk: vk == paste.VK_LCONTROL and vk not in soltas

    def ao_enviar():
        ultimo = teclado['eventos'][-1]
        if isinstance(ultimo, tuple):
            soltas.update(vk for vk, up in ultimo[1] if up)
    teclado['ao_enviar'] = ao_enviar
    assert paste.digitar('oi', None, soltar_apos_s=0.6) == ''
    assert ('teclas', [(paste.VK_LCONTROL, True)]) in teclado['eventos']
    assert [e for e in teclado['eventos'] if isinstance(e, str)] == ['o', 'i']


def test_digitar_interrompido_entre_teclas_devolve_o_resto(teclado):
    parar = threading.Event()
    enviadas = []

    def ao_enviar():
        enviadas.append(1)
        if len(enviadas) == 3:
            parar.set()  # para logo depois da 3ª tecla
    teclado['ao_enviar'] = ao_enviar
    assert paste.digitar('um dois', parar) == 'dois'
    assert [e for e in teclado['eventos'] if isinstance(e, str)] == ['u', 'm', ' ']


def test_digitar_parado_durante_espera_de_modificadora(teclado):
    parar = threading.Event()
    teclado['presas'] = lambda vk: True
    polls = {'n': 0}

    def ao_dormir():
        polls['n'] += 1
        if polls['n'] > 5:
            parar.set()
    teclado['ao_dormir'] = ao_dormir
    assert paste.digitar('nada sai', parar, soltar_apos_s=None) == 'nada sai'
    assert [e for e in teclado['eventos'] if not isinstance(e, float)] == []


def test_digitar_confere_a_janela_antes_de_cada_tecla(teclado):
    paste.digitar('a b c', threading.Event())
    assert teclado['guarda'].chamadas == 5


# ---------------------------------------------------------------- janela em foco
class Relogio:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.mark.parametrize('hwnd,classe,processo', [
    (0, '', ''),
    (5, 'Shell_TrayWnd', 'explorer.exe'),
    (5, 'MultitaskingViewFrame', 'explorer.exe'),
    (5, 'XamlExplorerHostIslandWindow', 'explorer.exe'),
    (5, 'ForegroundStaging', 'explorer.exe'),
    (5, 'Windows.UI.Core.CoreWindow', 'StartMenuExperienceHost.exe'),
    (5, 'Windows.UI.Core.CoreWindow', 'SearchHost.exe'),
])
def test_guarda_espera_sem_janela_ou_interface_do_windows(hwnd, classe, processo):
    rel = Relogio()
    g = paste.GuardaJanela(info=lambda: (hwnd, classe, processo), relogio=rel, dormir=lambda s: None)
    g.motivo_espera(hwnd, classe, processo, rel())
    rel.t += 10  # já estável há muito tempo: mesmo assim espera
    assert g.motivo_espera(hwnd, classe, processo, rel()) is not None


def test_guarda_espera_janela_que_acabou_de_mudar():
    rel = Relogio()
    g = paste.GuardaJanela(info=None, relogio=rel, dormir=lambda s: None)
    assert g.motivo_espera(7, 'Notepad', 'notepad.exe', rel()) is not None  # primeira vez: recém-vista
    rel.t += paste.JANELA_ESTAVEL_S + 0.01
    assert g.motivo_espera(7, 'Notepad', 'notepad.exe', rel()) is None
    assert g.motivo_espera(8, 'Chrome_WidgetWin_1', 'chrome.exe', rel()) is not None  # trocou agora
    rel.t += 0.05
    assert g.motivo_espera(8, 'Chrome_WidgetWin_1', 'chrome.exe', rel()) is not None
    rel.t += paste.JANELA_ESTAVEL_S
    assert g.motivo_espera(8, 'Chrome_WidgetWin_1', 'chrome.exe', rel()) is None


def test_guarda_esperar_tem_limite():
    rel = Relogio()

    def dormir(s):
        rel.t += s
    g = paste.GuardaJanela(info=lambda: (5, 'Shell_TrayWnd', 'explorer.exe'), relogio=rel, dormir=dormir)
    inicio = rel.t
    assert g.esperar(None, limite_s=3.0) == (5, 'Shell_TrayWnd', 'explorer.exe')
    assert 3.0 <= rel.t - inicio < 3.2


def test_guarda_esperar_sai_quando_janela_estabiliza():
    rel = Relogio()
    janelas = iter([(0, '', '')] * 3 + [(9, 'Notepad', 'notepad.exe')] * 100)

    def dormir(s):
        rel.t += s
    g = paste.GuardaJanela(info=lambda: next(janelas), relogio=rel, dormir=dormir)
    inicio = rel.t
    assert g.esperar(None, limite_s=3.0) == (9, 'Notepad', 'notepad.exe')
    assert rel.t - inicio < 0.5


def test_guarda_esperar_respeita_parar():
    rel = Relogio()
    parar = threading.Event()

    def dormir(s):
        rel.t += s
        parar.set()
    g = paste.GuardaJanela(info=lambda: (0, '', ''), relogio=rel, dormir=dormir)
    g.esperar(parar, limite_s=3.0)
    assert rel.t - 100.0 < 0.1


# ---------------------------------------------------------------- colar no tempo real
def test_colar_com_parar_espera_modificadora_sem_soltar(clipboard, monkeypatch):
    monkeypatch.setattr(paste, '_guarda', GuardaFalsa())
    monkeypatch.setattr(paste, 'soltar_modificadoras', lambda: pytest.fail('soltou modificadora no tempo real'))
    monkeypatch.setattr(paste, '_pressionada', lambda vk: True)
    monkeypatch.setattr(paste, 'enviar_ctrl_v', lambda: pytest.fail('colou depois de parar'))
    parar = threading.Event()
    parar.set()
    assert paste.colar('linha 1\nlinha 2', parar=parar) == 'linha 1\nlinha 2'
    assert pyperclip.paste() == 'original: ação e coração'


def test_colar_com_parar_entrega_tudo(clipboard, monkeypatch):
    monkeypatch.setattr(paste, '_guarda', GuardaFalsa())
    monkeypatch.setattr(paste, 'soltar_modificadoras', lambda: pytest.fail('soltou modificadora no tempo real'))
    monkeypatch.setattr(paste, '_pressionada', lambda vk: False)
    visto = []
    monkeypatch.setattr(paste, 'enviar_ctrl_v', lambda: visto.append(pyperclip.paste()))
    assert paste.colar('linha 1\nlinha 2', espera_ms=0, parar=threading.Event()) == ''
    assert visto == ['linha 1\nlinha 2']
    assert pyperclip.paste() == 'original: ação e coração'
