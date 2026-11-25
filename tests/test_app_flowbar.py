"""Integração app <-> Flow Bar com uma barra falsa (sem janelas, microfone ou hooks)."""
import json
import logging
import threading
import time
from unittest.mock import Mock

import pytest

from gillevoz import app as appmod
from gillevoz.app import App


class BarraFalsa:
    def __init__(self):
        self.estados, self.niveis = [], []

    def set_state(self, estado):
        self.estados.append(estado)

    def set_level(self, nivel):
        self.niveis.append(nivel)


def _app(monkeypatch):
    app = App.__new__(App)
    app.cfg = {"ativo": True, "bips": False}
    app.estado = "ocioso"
    app._lock = threading.RLock()
    app._sair = threading.Event()
    app._sessao = 0
    app.log = logging.getLogger("gillevoz-teste")
    app.recorder = Mock()
    app.recorder.nivel.return_value = 0.5
    app.recorder.stop.return_value = __import__("numpy").zeros(0, dtype="float32")
    app.hotkey = Mock()
    app.tray = Mock()
    app.indicator = None
    app.barra = BarraFalsa()
    app._thread_transcricao = None
    monkeypatch.setattr(app, "_transcrever_e_colar", lambda audio: None)
    return app


def test_clique_no_mic_alterna_e_estados_chegam_na_barra(monkeypatch):
    app = _app(monkeypatch)
    app.alternar_gravacao()
    assert app.estado == "gravando"
    time.sleep(0.25)  # medidor ~30 Hz
    app.alternar_gravacao()
    assert app.estado == "transcrevendo"
    assert app.barra.estados == ["gravando", "transcrevendo"]
    assert 4 <= len(app.barra.niveis) <= 12  # ~30 Hz durante ~0,25 s
    assert set(app.barra.niveis) == {0.5}
    n = len(app.barra.niveis)
    time.sleep(0.15)
    assert len(app.barra.niveis) == n, "medidor continuou depois de parar"
    app.hotkey.capturar_esc.assert_any_call(True)
    app.hotkey.capturar_esc.assert_called_with(False)


def test_x_da_barra_cancela_como_esc(monkeypatch):
    app = _app(monkeypatch)
    app.iniciar_gravacao()
    app.cancelar_gravacao()
    assert app.estado == "ocioso"
    assert app.barra.estados[-1] == "ocioso"
    app.recorder.cancel.assert_called_once()
    app.recorder.stop.assert_not_called()


def test_cancelamento_concorrente_deixa_barra_ociosa(monkeypatch):
    # Mesmo escalonamento do teste do indicador: cancelamento logo após iniciar.
    app = _app(monkeypatch)
    app._bip = lambda tipo: app.cancelar_gravacao() if tipo == "inicio" else None
    app.iniciar_gravacao()
    assert app.estado == "ocioso"
    assert app.barra.estados[-1] == "ocioso"


def test_pausar_e_ativar_pela_bandeja_atualiza_barra(monkeypatch):
    app = _app(monkeypatch)
    monkeypatch.setattr(appmod, "save_config", lambda cfg: None)
    app.toggle_ativo()
    assert app.barra.estados[-1] == "pausado"
    app.alternar_gravacao()  # clique no mic pausado não grava
    assert app.estado == "pausado"
    app.recorder.start.assert_not_called()
    app.toggle_ativo()
    assert app.barra.estados[-1] == "ocioso"


def test_pausar_durante_gravacao_cancela_e_pausa(monkeypatch):
    app = _app(monkeypatch)
    monkeypatch.setattr(appmod, "save_config", lambda cfg: None)
    app.iniciar_gravacao()
    app.toggle_ativo()
    assert app.estado == "pausado"
    assert app.barra.estados[-1] == "pausado"
    app.recorder.cancel.assert_called_once()


def test_mover_salva_posicao_sem_perder_chaves(monkeypatch, tmp_path):
    import gillevoz.config as config

    arq = tmp_path / "config.json"
    arq.write_text(json.dumps({"atalho": "f9", "minha_chave": [1, 2]}), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", arq)
    monkeypatch.setattr(appmod, "load_config", config.load_config)
    monkeypatch.setattr(appmod, "save_config", config.save_config)
    app = _app(monkeypatch)
    app.salvar_posicao_barra(123, 456)
    salvo = json.loads(arq.read_text(encoding="utf-8"))
    assert (salvo["barra_x"], salvo["barra_y"]) == (123, 456)
    assert salvo["atalho"] == "f9" and salvo["minha_chave"] == [1, 2]
    assert (app.cfg["barra_x"], app.cfg["barra_y"]) == (123, 456)


# ---------------------------------------------------------------- barra que falha
class BarraQueFalhaNoStart:
    instancias = []

    def __init__(self, **kw):
        self.kw, self.parada = kw, 0
        BarraQueFalhaNoStart.instancias.append(self)

    def start(self):
        raise TimeoutError("janela da Flow Bar não ficou pronta em 5 s")

    def stop(self):
        self.parada += 1
        raise RuntimeError("stop também falha")  # o app precisa tolerar


class IndicadorFalso:
    def __init__(self):
        self.iniciado, self.chamadas = False, []

    def start(self):
        self.iniciado = True

    def show(self, texto="● gravando"):
        self.chamadas.append(("show", texto))

    def set_text(self, texto):
        self.chamadas.append(("set_text", texto))

    def hide(self):
        self.chamadas.append(("hide",))


def _app_visual(monkeypatch, barra_cls):
    import gillevoz.flowbar as flowbar
    import gillevoz.indicator as indicator

    monkeypatch.setattr(flowbar, "FlowBar", barra_cls)
    criados = []
    monkeypatch.setattr(indicator, "Indicator", lambda: criados.append(IndicadorFalso()) or criados[-1])
    app = _app(monkeypatch)
    app.barra = None
    app.cfg["barra_ativa"] = True
    return app, criados


def test_start_da_barra_levanta_usa_indicator(monkeypatch, caplog):
    BarraQueFalhaNoStart.instancias.clear()
    app, criados = _app_visual(monkeypatch, BarraQueFalhaNoStart)
    with caplog.at_level(logging.WARNING, logger="gillevoz-teste"):
        app._iniciar_visual()
    assert app.barra is None
    assert BarraQueFalhaNoStart.instancias[0].parada == 1, "stop() da barra não foi chamado"
    assert len(criados) == 1 and criados[0].iniciado and app.indicator is criados[0]
    assert any("Flow Bar" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)
    # O app segue funcionando com o indicador no lugar da barra
    app.iniciar_gravacao()
    assert app.estado == "gravando" and ("show", "● gravando") in criados[0].chamadas
    app.cancelar_gravacao()
    assert app.estado == "ocioso" and criados[0].chamadas[-1] == ("hide",)


def test_construtor_da_barra_levanta_usa_indicator(monkeypatch):
    def construtor_quebrado(**kw):
        raise OSError("CreateWindowExW falhou")
    app, criados = _app_visual(monkeypatch, construtor_quebrado)
    app._iniciar_visual()
    assert app.barra is None and app.indicator is criados[0] and criados[0].iniciado


class BarraQueMorre(BarraFalsa):
    def __init__(self):
        super().__init__()
        self.paradas = 0

    def set_level(self, nivel):
        raise RuntimeError("janela destruída")

    def stop(self):
        self.paradas += 1


def test_barra_morta_durante_gravacao_nao_derruba_app(monkeypatch):
    app = _app(monkeypatch)
    barra = BarraQueMorre()
    app.barra = barra
    app.iniciar_gravacao()          # set_state ok; medidor chama set_level -> falha
    time.sleep(0.2)
    assert app.barra is None, "app continuou usando a barra morta"
    assert barra.paradas == 1
    app.parar_gravacao()            # sem barra: transições continuam funcionando
    assert app.estado == "transcrevendo"
    app._set_estado("ocioso")
    app.alternar_gravacao()         # clique/atalho depois da falha ainda grava
    assert app.estado == "gravando"


def test_barra_com_thread_morta_e_ignorada(monkeypatch):
    app = _app(monkeypatch)
    barra = BarraFalsa()
    barra._thread = threading.Thread(target=lambda: None)
    barra._thread.start(); barra._thread.join()
    barra.stop = Mock()
    app.barra = barra
    app.iniciar_gravacao()
    assert barra.estados == [] and app.barra is None and app.estado == "gravando"
    time.sleep(0.1)
    barra.stop.assert_called_once()
