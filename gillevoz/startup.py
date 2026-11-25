"""Iniciar com o Windows: atalho GilleVoz.lnk na pasta Inicializar do usuário.

O atalho aponta para wscript.exe "GilleVoz.vbs", com a pasta de trabalho na raiz do projeto.
remover_v1() apaga o atalho antigo do v1 (o motor v2 é iniciado pelo Electron).
"""

import logging
import os

from .config import ROOT

NOME_ATALHO = "GilleVoz.lnk"
VBS = ROOT / "GilleVoz.vbs"

_log = logging.getLogger("gillevoz")


def _pasta_inicializar() -> str:
    return os.path.join(
        os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup"
    )


def _caminho_atalho() -> str:
    return os.path.join(_pasta_inicializar(), NOME_ATALHO)


def ativo() -> bool:
    return os.path.exists(_caminho_atalho())


def ativar() -> str:
    """Cria o atalho na pasta Inicializar. Devolve o caminho do .lnk."""
    from win32com.client import Dispatch  # pywin32 (requirements.txt)

    wscript = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wscript.exe")
    atalho = Dispatch("WScript.Shell").CreateShortcut(_caminho_atalho())
    atalho.TargetPath = wscript
    atalho.Arguments = f'"{VBS}"'
    atalho.WorkingDirectory = str(ROOT)
    atalho.Description = "GilleVoz - ditado por voz"
    atalho.save()
    return _caminho_atalho()


def desativar() -> None:
    """Remove o atalho da pasta Inicializar (se existir)."""
    if ativo():
        os.remove(_caminho_atalho())


def _alvo_atalho(caminho: str) -> str:
    """Destino + argumentos de um .lnk (ex.: wscript.exe "<pasta>/GilleVoz.vbs")."""
    from win32com.client import Dispatch  # pywin32 (requirements.txt)

    atalho = Dispatch("WScript.Shell").CreateShortcut(caminho)
    return f"{atalho.TargetPath} {atalho.Arguments}"


def remover_v1() -> bool:
    """Apaga GilleVoz.lnk da pasta Inicializar se ele abre o GilleVoz.vbs do v1. True se apagou."""
    caminho = _caminho_atalho()
    if not os.path.exists(caminho):
        return False
    try:
        if "gillevoz.vbs" not in _alvo_atalho(caminho).lower():
            return False
        os.remove(caminho)
    except Exception as e:
        _log.warning("Não consegui remover o atalho de inicialização do v1: %s", e)
        return False
    _log.info("Atalho de inicialização do v1 removido: %s", caminho)
    return True
