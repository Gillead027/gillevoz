"""Logs do GilleVoz: arquivo logs/gillevoz.log (rotativo) + console."""

import logging
from logging.handlers import RotatingFileHandler

from .config import ROOT

LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "gillevoz.log"
_FORMATO = "%(asctime)s %(levelname)-7s %(message)s"


def setup_logging() -> logging.Logger:
    """Configura o logger "gillevoz". Pode ser chamada mais de uma vez sem duplicar."""
    logger = logging.getLogger("gillevoz")
    if getattr(logger, "_gillevoz_pronto", False):
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    arquivo = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    arquivo.setFormatter(logging.Formatter(_FORMATO))
    logger.addHandler(arquivo)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_FORMATO))
    logger.addHandler(console)

    logger._gillevoz_pronto = True
    return logger
