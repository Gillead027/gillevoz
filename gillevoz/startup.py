"""Iniciar com o Windows: atalho GilleVoz.lnk na pasta Inicializar do usuário.

O atalho aponta para wscript.exe "GilleVoz.vbs", com a pasta de trabalho na raiz do projeto.
"""

import os

from .config import ROOT

NOME_ATALHO = "GilleVoz.lnk"
VBS = ROOT / "GilleVoz.vbs"


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
