"""Regressões de concorrência/lifecycle sem janelas ou ações na sessão real."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from gillevoz import flowbar as f
from test_app_flowbar import _app


def bar():
    return f.FlowBar(*(lambda *a: None for _ in range(6)), posicao=(20, 20))


def test_stop_cancela_timer_que_poderia_reabrir_barra(monkeypatch):
    b = bar()
    b._thread = SimpleNamespace(is_alive=lambda: True, join=lambda timeout: None)
    b._timer_ocultar = Mock()
    monkeypatch.setattr(b, '_enfileirar', Mock())
    b.stop()
    b._timer_ocultar.cancel.assert_called_once()


def test_set_state_concorrente_mantem_fila_na_ordem_do_estado(monkeypatch):
    b = bar()
    entrou, liberar = threading.Event(), threading.Event()
    def enfileirar(cmd):
        if cmd == ('estado', 'gravando'):
            entrou.set()
            assert liberar.wait(2)
        b._fila.put(cmd)
    monkeypatch.setattr(b, '_enfileirar', enfileirar)
    t = threading.Thread(target=b.set_state, args=('gravando',))
    t.start()
    try:
        assert entrou.wait(2)
        b.set_state('pausado')
    finally:
        liberar.set()
        t.join(2)
    aplicados = []
    monkeypatch.setattr(b, '_aplicar_estado', aplicados.append)
    b._processar_fila()
    assert aplicados[-1] == b._estado, 'Tamanho/timer da UI ficaram em gravando mas o estado é pausado'


def test_enfileirar_aguarda_hwnd_durante_start_concorrente(monkeypatch):
    b = bar()
    # Estado real durante _run entre Thread.start e CreateWindowExW.
    b._thread = SimpleNamespace(is_alive=lambda: True)
    posts = []
    monkeypatch.setattr(f, 'user32', SimpleNamespace(PostMessageW=lambda hwnd, *args: posts.append(hwnd)))
    b._enfileirar(('estado', 'pausado'))
    assert None not in posts, 'PostMessageW(NULL) acorda a thread chamadora, não a janela da barra'


def test_escondida_nao_mantem_timer_de_animacao(monkeypatch):
    b = bar()
    b._hwnd = 123
    b._estado = 'transcrevendo'
    fake_user = SimpleNamespace(ShowWindow=Mock(), KillTimer=Mock())
    monkeypatch.setattr(f, 'user32', fake_user)
    monkeypatch.setattr(f.threading, 'Timer', lambda *a: SimpleNamespace(daemon=False, start=lambda: None))
    b._esconder(3600)
    fake_user.KillTimer.assert_any_call(123, f.TIMER_ANIMACAO)


def test_falha_criacao_janela_e_reportada_ao_chamador(monkeypatch):
    b = bar()
    erros = []
    monkeypatch.setattr(f, '_registrar_classes', lambda: None)
    monkeypatch.setattr(b, '_posicao_inicial', lambda *a: (20, 20))
    monkeypatch.setattr(b, '_trabalhador_cb', lambda: None)
    monkeypatch.setattr(f, 'user32', SimpleNamespace(CreateWindowExW=lambda *a: None))
    monkeypatch.setattr(threading, 'excepthook', lambda args: erros.append(args.exc_value))
    try:
        with pytest.raises(OSError):
            b.start()
    finally:
        if b._thread:
            b._thread.join(2)


def test_perda_da_captura_cancela_arraste():
    b = bar()
    b._arraste = {'cursor': (20, 20), 'janela': (20, 20), 'arrastou': True}
    b._tratar_barra(0x0215, 0, 999)  # WM_CAPTURECHANGED: outra janela capturou
    assert b._arraste is None, 'Sem captura o button-up pode ir para outra janela'


def test_clique_e_atalho_simultaneos_nao_abrem_microfone_duas_vezes(monkeypatch):
    for _ in range(20):
        app = _app(monkeypatch)
        monkeypatch.setattr(app, '_medidor', lambda sessao: None)
        inicio = threading.Barrier(3)
        erros = []
        def agir(fn):
            try:
                inicio.wait(timeout=2)
                fn()
            except BaseException as e:
                erros.append(e)
        a = threading.Thread(target=agir, args=(app.alternar_gravacao,))
        b = threading.Thread(target=agir, args=(app.iniciar_gravacao,))
        a.start()
        b.start()
        inicio.wait(timeout=2)
        a.join(2)
        b.join(2)
        assert not a.is_alive() and not b.is_alive() and not erros
        assert app.recorder.start.call_count == 1
        assert app.recorder.stop.call_count <= 1
        assert app.estado in ('gravando', 'transcrevendo')
