import time

from gillevoz import historico


def test_append_unicode_multilinha_e_tempos(monkeypatch, tmp_path):
    monkeypatch.setattr(historico, 'ROOT', tmp_path)
    instante = time.struct_time((2026, 11, 25, 10, 20, 30, 2, 329, -1))
    monkeypatch.setattr(historico.time, 'localtime', lambda: instante)
    path = historico.salvar('ação\ncoração', 300.0, 1.234)
    assert historico.salvar('segundo ditado', 2, .5) == path
    texto = path.read_text(encoding='utf-8')
    assert path.name == '2026-11-25.md'
    assert texto.count('# Ditados de') == 1
    assert texto.count('## 10:20:30') == 2
    assert 'áudio 300.0 s · transcrição 1.23 s' in texto
    assert 'ação\ncoração' in texto
    assert texto.index('coração') < texto.index('segundo ditado')


def test_dias_separados(monkeypatch, tmp_path):
    monkeypatch.setattr(historico, 'ROOT', tmp_path)
    for dia in (24, 25):
        instante = time.struct_time((2026, 11, dia, 12, 0, 0, 1, 328, -1))
        monkeypatch.setattr(historico.time, 'localtime', lambda: instante)
        historico.salvar(str(dia), 1, .1)
    assert len(list((tmp_path / 'historico').glob('*.md'))) == 2
