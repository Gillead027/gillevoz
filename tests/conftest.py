import importlib

import pytest


@pytest.fixture
def dados(monkeypatch, tmp_path):
    """Isola a pasta de dados em tmp_path/GilleVoz (nunca toca o %APPDATA% real)."""
    from gillevoz import config, historico

    pasta = tmp_path / "GilleVoz"
    monkeypatch.setenv("GILLEVOZ_DADOS", str(pasta))
    importlib.reload(config)
    importlib.reload(historico)
    yield pasta
    monkeypatch.undo()
    importlib.reload(config)
    importlib.reload(historico)
