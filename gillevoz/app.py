"""Modos de linha de comando do GilleVoz: --testar-wav e --baixar-modelo.

O app do dia a dia é o motor sem janela (motor.py, `python -m gillevoz --motor`),
controlado pela interface Electron.
"""
from __future__ import annotations

import os
import time

from . import historico, paste
from .config import load_config
from .log import setup_logging


# ---------------------------------------------------------------- modos de linha de comando
def testar_wav(caminho: str, colar: bool = False, atraso: float = 3.0) -> int:
    from .audio import carregar_wav
    from .transcriber import Transcriber

    lg = setup_logging()
    cfg = load_config()
    t0 = time.perf_counter()
    tr = Transcriber(cfg)
    lg.info("Carga do modelo: %.1f s (%s, %s, %s)", time.perf_counter() - t0,
            tr.modelo_efetivo, tr.device_efetivo, tr.compute_type_efetivo)
    audio = carregar_wav(caminho)
    duracao = len(audio) / 16000.0
    t1 = time.perf_counter()
    texto = tr.transcrever(audio)
    dt = time.perf_counter() - t1
    lg.info("TESTE %s: áudio %.1f s | transcrição %.2f s | %.1fx tempo real | device_efetivo=%s | modelo=%s",
            os.path.basename(caminho), duracao, dt, (duracao / dt) if dt > 0 else 0,
            tr.device_efetivo, tr.modelo_efetivo)
    lg.info("TEXTO: %s", texto)
    print(texto, flush=True)
    if texto:
        arq = historico.salvar(texto, duracao, dt)
        lg.info("Salvo no histórico: %s", arq)
        if colar:
            lg.info("Colando em %.1f s na janela em foco...", atraso)
            time.sleep(atraso)
            paste.colar(texto, metodo=cfg.get("metodo_colagem", "clipboard"),
                        auto_enter=bool(cfg.get("auto_enter", False)),
                        espaco_final=bool(cfg.get("espaco_final", True)))
            lg.info("Colado.")
    return 0


def baixar_modelo() -> int:
    from .transcriber import Transcriber

    lg = setup_logging()
    cfg = load_config()
    t0 = time.perf_counter()
    tr = Transcriber(cfg)
    lg.info("Modelo baixado e pronto: %s em %s (%.1f s).", tr.modelo_efetivo, tr.device_efetivo,
            time.perf_counter() - t0)
    print(f"OK: {tr.modelo_efetivo} em {tr.device_efetivo}", flush=True)
    return 0
