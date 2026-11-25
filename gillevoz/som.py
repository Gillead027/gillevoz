"""Silencia o som do PC enquanto grava (opção "silenciar_pc") e devolve como estava.

Usa a pycaw (volume do alto-falante padrão). Nenhuma falha aqui pode atrapalhar o
ditado: tudo vira log, nunca exceção.
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger("gillevoz")


def _volume():
    """IAudioEndpointVolume do alto-falante padrão (inicializa o COM nesta thread)."""
    import comtypes
    from pycaw.pycaw import AudioUtilities

    try:
        comtypes.CoInitialize()
    except OSError:
        pass  # COM já iniciado nesta thread com outro modo; segue assim mesmo
    return AudioUtilities.GetSpeakers().EndpointVolume


class Silenciador:
    """silenciar() guarda se o PC já estava mudo; restaurar() volta ao que era (idempotente)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._estava_mudo: bool | None = None  # None = não silenciamos nada

    def silenciar(self) -> None:
        with self._lock:
            try:
                vol = _volume()
                if self._estava_mudo is None:
                    self._estava_mudo = bool(vol.GetMute())
                vol.SetMute(1, None)
            except Exception as e:
                log.warning("Não consegui silenciar o PC: %s", e)

    def restaurar(self) -> None:
        with self._lock:
            estava, self._estava_mudo = self._estava_mudo, None
            if estava is None or estava:
                return
            try:
                _volume().SetMute(0, None)
            except Exception as e:
                log.warning("Não consegui devolver o som do PC: %s", e)
