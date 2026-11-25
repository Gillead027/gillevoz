"""O v2 não tem janela no Python: sobram só os modos de linha de comando do app."""
import importlib.util

from gillevoz import app


def test_app_sem_janela_mantem_modos_de_linha_de_comando():
    assert not hasattr(app, "App")
    assert callable(app.testar_wav)
    assert callable(app.baixar_modelo)


def test_modulos_de_janela_do_v1_foram_removidos():
    for nome in ("flowbar", "indicator", "tray"):
        assert importlib.util.find_spec(f"gillevoz.{nome}") is None, nome
