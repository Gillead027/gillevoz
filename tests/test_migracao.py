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


def test_pasta_v1_e_a_pasta_do_projeto_mesmo_instalado():
    # Instalado, o código fica em <instalação>\motor; a migração tem que olhar a pasta do v1.
    assert str(config.PASTA_V1).lower() == r'c:\mudo tech\gillevoz'


def test_baixar_modelo_migra_v1_antes_de_criar_a_pasta_de_dados(monkeypatch):
    # A pós-instalação roda --baixar-modelo antes do primeiro uso; ele cria logs/ e config.json,
    # então precisa migrar o v1 antes, senão a migração nunca mais acontece.
    from gillevoz import __main__ as principal
    from gillevoz import app

    ordem = []
    monkeypatch.setattr(config, 'migrar_v1', lambda origem: ordem.append(('migrar', origem)))
    monkeypatch.setattr(app, 'baixar_modelo', lambda: ordem.append(('baixar',)) or 0)
    assert principal.main(['--baixar-modelo']) == 0
    assert ordem == [('migrar', config.PASTA_V1), ('baixar',)]
