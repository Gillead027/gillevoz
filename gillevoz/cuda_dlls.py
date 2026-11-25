"""Registra as DLLs do CUDA (cuBLAS/cuDNN instalados via pip) antes de carregar o modelo.

No Windows o ctranslate2 procura cublas64_12.dll / cudnn*.dll no PATH. Os pacotes
pip `nvidia-cublas-cu12` e `nvidia-cudnn-cu12` colocam essas DLLs em
site-packages/nvidia/<pacote>/bin, que não está no PATH — então adicionamos aqui.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("gillevoz")

_handles = []  # mantém as referências do add_dll_directory vivas
_registrado = False


def _pastas_bin() -> list[Path]:
    pastas: list[Path] = []
    candidatos = []
    for p in sys.path:
        if p and p.lower().endswith("site-packages"):
            candidatos.append(Path(p))
    # fallback: site-packages do próprio venv
    candidatos.append(Path(sys.prefix) / "Lib" / "site-packages")
    vistos = set()
    for sp in candidatos:
        nvidia = sp / "nvidia"
        if not nvidia.is_dir():
            continue
        for sub in sorted(nvidia.iterdir()):
            b = sub / "bin"
            if b.is_dir() and str(b).lower() not in vistos:
                vistos.add(str(b).lower())
                pastas.append(b)
    return pastas


def registrar_dlls_cuda() -> list[Path]:
    """Adiciona as pastas bin dos pacotes nvidia-* ao PATH e ao add_dll_directory.

    Pode ser chamada várias vezes (só registra uma vez). Retorna as pastas registradas.
    """
    global _registrado
    pastas = _pastas_bin()
    if _registrado:
        return pastas
    for b in pastas:
        os.environ["PATH"] = str(b) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            try:
                _handles.append(os.add_dll_directory(str(b)))
            except OSError as e:  # pragma: no cover
                log.warning("add_dll_directory falhou para %s: %s", b, e)
    _registrado = True
    if pastas:
        log.info("DLLs CUDA registradas: %s", ", ".join(str(p) for p in pastas))
    else:
        log.warning("Nenhuma pasta nvidia/*/bin encontrada (cuBLAS/cuDNN via pip ausentes?)")
    return pastas
