import time

from gillevoz import historico


def _fixar_hora(monkeypatch, ano, mes, dia, h=12, mi=0, s=0):
    instante = time.struct_time((ano, mes, dia, h, mi, s, 0, 1, -1))
    monkeypatch.setattr(historico.time, 'localtime', lambda *a: instante)


def test_append_unicode_multilinha_e_tempos(dados, monkeypatch):
    _fixar_hora(monkeypatch, 2026, 11, 25, 10, 20, 30)
    path = historico.salvar('ação\ncoração', 300.0, 1.234)
    assert historico.salvar('segundo ditado', 2, .5) == path
    texto = path.read_text(encoding='utf-8')
    assert path.name == '2026-11-25.md'
    assert path.parent == dados / 'historico'
    assert texto.count('# Ditados de') == 1
    assert texto.count('## 10:20:30') == 2
    assert 'áudio 300.0 s · transcrição 1.23 s' in texto
    assert 'ação\ncoração' in texto
    assert texto.index('coração') < texto.index('segundo ditado')


def test_dias_separados(dados, monkeypatch):
    for dia in (24, 25):
        _fixar_hora(monkeypatch, 2026, 11, dia)
        historico.salvar(str(dia), 1, .1)
    assert len(list((dados / 'historico').glob('*.md'))) == 2
    assert len(list((dados / 'historico').glob('*.jsonl'))) == 2


def test_historico_jsonl_e_listar(dados, monkeypatch):
    _fixar_hora(monkeypatch, 2026, 11, 25, 9, 0, 0)
    historico.salvar('um dois três', 3.0, 0.5)
    _fixar_hora(monkeypatch, 2026, 11, 25, 9, 5, 0)
    historico.salvar('quatro cinco', 2.0, 0.4)
    itens = historico.listar()
    assert len(itens) == 2
    assert itens[0]['texto'] == 'quatro cinco'
    assert itens[0]['hora'] == '09:05:00'
    assert itens[0]['palavras'] == 2
    assert itens[1]['palavras'] == 3
    assert itens[1]['duracao_audio'] == 3.0
    assert itens[1]['tempo_transcricao'] == 0.5


def test_estatisticas(dados, monkeypatch):
    _fixar_hora(monkeypatch, 2026, 11, 24)
    historico.salvar('um dois três quatro cinco', 30.0, 1)
    _fixar_hora(monkeypatch, 2026, 11, 25)
    historico.salvar('um dois três quatro cinco seis sete oito nove dez', 60.0, 1)
    est = historico.estatisticas()
    assert est['palavras_total'] == 15
    assert est['palavras_hoje'] == 10
    assert est['ditados_total'] == 2
    assert est['ppm'] == 10
    assert est['sequencia_dias'] == 2
    assert historico.dias() == ['2026-11-25', '2026-11-24']


def test_sequencia_conta_de_ontem_e_quebra_com_buraco(dados, monkeypatch):
    for dia in (21, 23, 24):
        _fixar_hora(monkeypatch, 2026, 11, dia)
        historico.salvar('a', 1, .1)
    _fixar_hora(monkeypatch, 2026, 11, 25)
    est = historico.estatisticas()
    assert est['sequencia_dias'] == 2
    assert est['palavras_hoje'] == 0


def test_listar_dia_v1_md(dados):
    pasta = dados / 'historico'
    pasta.mkdir(parents=True)
    (pasta / '2026-11-24.md').write_text(
        '# Ditados de 24/11/2026\n\n'
        '## 08:00:01 · áudio 3.5 s · transcrição 0.80 s\n\nprimeiro ditado\ncom duas linhas\n\n---\n\n'
        '## 08:10:02 · áudio 1.0 s · transcrição 0.20 s\n\nsegundo\n\n---\n\n',
        encoding='utf-8',
    )
    itens = historico.listar('2026-11-24')
    assert [i['texto'] for i in itens] == ['segundo', 'primeiro ditado\ncom duas linhas']
    assert itens[1]['duracao_audio'] == 3.5
    assert itens[1]['tempo_transcricao'] == 0.8
    assert itens[1]['palavras'] == 5
    assert historico.listar('2026-01-01') == []
