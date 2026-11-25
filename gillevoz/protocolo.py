"""Protocolo motor ⇄ interface: uma mensagem JSON por linha, em UTF-8.

O motor escreve no stdout (só protocolo, nada de print) e lê comandos do stdin.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import BinaryIO, Iterator, TextIO

log = logging.getLogger("gillevoz")


class Canal:
    """Envia mensagens para a interface. Pode ser usado por várias threads ao mesmo tempo."""

    def __init__(self, saida: BinaryIO):
        self._saida = saida
        self._lock = threading.Lock()

    def enviar(self, tipo: str, **campos) -> None:
        linha = json.dumps({"tipo": tipo, **campos}, ensure_ascii=False) + "\n"
        dados = linha.encode("utf-8")
        with self._lock:
            self._saida.write(dados)
            self._saida.flush()


def ler(entrada: TextIO) -> Iterator[dict]:
    """Lê comandos (um JSON por linha). Linhas inválidas são ignoradas e registradas no log."""
    for linha in iter(entrada.readline, ""):
        linha = linha.strip()
        if not linha:
            continue
        try:
            cmd = json.loads(linha)
        except ValueError:
            log.warning("protocolo: linha inválida ignorada: %.200s", linha)
            continue
        if not isinstance(cmd, dict) or not isinstance(cmd.get("tipo"), str):
            log.warning("protocolo: mensagem inválida (sem 'tipo') ignorada: %.200s", linha)
            continue
        yield cmd
