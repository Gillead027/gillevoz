import copy
import json

import pytest

from gillevoz import config


@pytest.fixture
def config_path(monkeypatch, tmp_path):
    path = tmp_path / 'config.json'
    monkeypatch.setattr(config, 'CONFIG_PATH', path)
    return path


def test_cria_defaults_independentes(config_path):
    original = copy.deepcopy(config.DEFAULTS)
    cfg = config.load_config()
    assert json.loads(config_path.read_text(encoding='utf-8')) == original
    cfg['vocabulario'].append('teste isolado')
    assert config.DEFAULTS == original


def test_completa_sem_perder_escolhas(config_path):
    config_path.write_text(json.dumps({'auto_enter': True, 'extra': {'a': 1}}))
    cfg = config.load_config()
    assert cfg['auto_enter'] is True
    assert cfg['extra'] == {'a': 1}
    assert set(config.DEFAULTS) <= set(cfg)
    assert json.loads(config_path.read_text(encoding='utf-8')) == cfg


@pytest.mark.parametrize('conteudo', ['{quebrado', '[]', 'null'])
def test_invalido_preservado(config_path, conteudo):
    config_path.write_text(conteudo, encoding='utf-8')
    assert config.load_config() == config.DEFAULTS
    backups = list(config_path.parent.glob('config.json.invalido-*'))
    assert len(backups) == 1
    assert backups[0].read_text(encoding='utf-8') == conteudo


def test_save_atomico_preserva_anterior_se_replace_falhar(config_path, monkeypatch):
    config.save_config({'texto': 'ação'})
    def falhar(*args):
        raise OSError('troca falhou')
    monkeypatch.setattr(config.os, 'replace', falhar)
    with pytest.raises(OSError):
        config.save_config({'texto': 'novo'})
    assert json.loads(config_path.read_text(encoding='utf-8')) == {'texto': 'ação'}
    assert not list(config_path.parent.glob('*.tmp'))
