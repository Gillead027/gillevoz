import importlib
import logging

from gillevoz import log


def test_log_vai_para_pasta_dados_sem_console(dados, monkeypatch, capsys):
    logger = logging.getLogger('gillevoz')
    monkeypatch.setattr(logger, 'handlers', [])
    monkeypatch.setattr(logger, '_gillevoz_pronto', False, raising=False)
    importlib.reload(log)
    log.setup_logging(console=False)
    logger.info('mensagem de teste')
    for h in logger.handlers:
        h.flush()
        h.close()
    assert 'mensagem de teste' in (dados / 'logs' / 'gillevoz.log').read_text(encoding='utf-8')
    assert capsys.readouterr().out == ''
    assert not any(type(h) is logging.StreamHandler for h in logger.handlers)
