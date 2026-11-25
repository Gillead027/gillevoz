import copy
import json
import logging

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


def test_config_cria_em_pasta_dados(dados):
    cfg = config.load_config()
    assert (dados / 'config.json').is_file()
    assert cfg['tempo_real'] is True
    assert cfg['barra_borda'] == 'embaixo'
    assert 'modo' not in cfg and 'barra_x' not in cfg


def test_limpar_descarta_itens_ruins(caplog, monkeypatch):
    monkeypatch.setattr(logging.getLogger('gillevoz'), 'propagate', True)
    with caplog.at_level('WARNING', logger='gillevoz'):
        cfg = config.limpar({
            'trocas': [{'de': 'a', 'para': 'b'}, 'x', {'de': ''}],
            'atalhos_texto': 'x',
            'vocabulario': ['ok', '', 3],
            'bips': 'sim',
        })
    assert cfg['trocas'] == [{'de': 'a', 'para': 'b'}]
    assert cfg['atalhos_texto'] == []
    assert cfg['vocabulario'] == ['ok']
    assert cfg['bips'] is True
    assert len(caplog.records) >= 4


def test_limpar_mantem_validos():
    entrada = {'atalhos_texto': [{'gatilho': 'meu email', 'texto': 'a@b.c'}], 'barra_pos': 1, 'atalho_push': 'f9'}
    assert config.limpar(entrada) == entrada


def test_limpar_microfone_aceita_indice_inteiro(monkeypatch):
    monkeypatch.setattr(logging.getLogger('gillevoz'), 'propagate', False)
    assert config.limpar({'microfone': 3})['microfone'] == 3
    assert config.limpar({'microfone': 'Headset'})['microfone'] == 'Headset'
    assert config.limpar({'microfone': True})['microfone'] is None
