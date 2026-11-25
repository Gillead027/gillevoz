"""Logs do GilleVoz: arquivo PASTA_DADOS/logs/gillevoz.log (rotativo) + console opcional."""

import logging
from logging.handlers import RotatingFileHandler

from . import config

_FORMATO = "%(asctime)s %(levelname)-7s %(message)s"


def setup_logging(console: bool = True) -> logging.Logger:
    """Configura o logger "gillevoz". Pode ser chamada mais de uma vez sem duplicar.

    Com console=False nada é escrito no stdout (ele é o canal do protocolo JSON).
    """
    logger = logging.getLogger("gillevoz")
    if getattr(logger, "_gillevoz_pronto", False):
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    pasta = config.PASTA_DADOS / "logs"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = RotatingFileHandler(
        pasta / "gillevoz.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    arquivo.setFormatter(logging.Formatter(_FORMATO))
    logger.addHandler(arquivo)

    if console:
        saida = logging.StreamHandler()
        saida.setFormatter(logging.Formatter(_FORMATO))
        logger.addHandler(saida)

    logger._gillevoz_pronto = True
    return logger
