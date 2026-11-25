import json

from gillevoz import config


def _origem_v1(tmp_path):
    origem = tmp_path / 'v1'
    (origem / 'historico').mkdir(parents=True)
    (origem / 'config.json').write_text(
        json.dumps({'modo': 'push', 'atalho': 'f9', 'barra_x': 10, 'barra_y': 20, 'bips': False}),
        encoding='utf-8',
    )
    (origem / 'historico' / '2026-11-24.md').write_text('# Ditados de 24/11/2026\n', encoding='utf-8')
    return origem


def test_migrar_v1_copia_e_converte(dados, tmp_path):
    origem = _origem_v1(tmp_path)
    assert config.migrar_v1(origem) is True
    novo = json.loads((dados / 'config.json').read_text(encoding='utf-8'))
    assert novo['atalho_push'] == 'f9'
    assert novo['atalho'] == 'ctrl+shift+space'
    assert novo['bips'] is False
    assert not ({'barra_x', 'barra_y', 'modo'} & set(novo))
    assert (dados / 'historico' / '2026-11-24.md').is_file()
    assert not (tmp_path / 'GilleVoz.migrando').exists()
    # o config migrado carrega e ganha as chaves novas
    assert config.load_config()['tempo_real'] is True


def test_migrar_v1_modo_toggle_mantem_atalho(dados, tmp_path):
    origem = tmp_path / 'v1'
    origem.mkdir()
    (origem / 'config.json').write_text(json.dumps({'modo': 'toggle', 'atalho': 'f8'}), encoding='utf-8')
    assert config.migrar_v1(origem) is True
    novo = json.loads((dados / 'config.json').read_text(encoding='utf-8'))
    assert novo['atalho'] == 'f8'
    assert 'atalho_push' not in novo


def test_migrar_v1_nao_sobrescreve(dados, tmp_path):
    origem = _origem_v1(tmp_path)
    dados.mkdir()
    (dados / 'config.json').write_text('{"atalho": "f1"}', encoding='utf-8')
    assert config.migrar_v1(origem) is False
    assert json.loads((dados / 'config.json').read_text(encoding='utf-8')) == {'atalho': 'f1'}
    assert not (dados / 'historico').exists()


def test_migrar_v1_sem_config_na_origem(dados, tmp_path):
    vazia = tmp_path / 'vazia'
    vazia.mkdir()
    assert config.migrar_v1(vazia) is False
    assert not dados.exists()
