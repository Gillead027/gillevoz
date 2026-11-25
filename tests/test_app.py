import logging
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from gillevoz.app import App


def test_esc_entre_inicio_e_show_nao_deixa_indicador_visivel():
    # Reproduz o escalonamento de duas threads sem hooks, microfone ou janelas.
    app = App.__new__(App)
    app.cfg = {'ativo': True}
    app.estado = 'ocioso'
    app._lock = threading.RLock()
    app.log = logging.getLogger('gillevoz-teste')
    app.recorder = Mock()
    app.hotkey = Mock()
    app.tray = None
    indicador = SimpleNamespace(visivel=False)
    def show(texto):
        indicador.visivel = True
    def hide():
        indicador.visivel = False
    indicador.show, indicador.hide = show, hide
    app.indicator = indicador
    app._bip = lambda tipo: app.cancelar_gravacao() if tipo == 'inicio' else None
    app.iniciar_gravacao()
    assert app.estado == 'ocioso'
    app.recorder.cancel.assert_called_once()
    assert not indicador.visivel
