"""Histórico: toda transcrição é guardada em historico/AAAA-MM-DD.md, com horário."""

import time
from pathlib import Path

from .config import ROOT


def pasta_historico() -> Path:
    pasta = ROOT / "historico"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def salvar(texto: str, duracao_audio: float, tempo_transcricao: float) -> Path:
    """Acrescenta a transcrição ao arquivo do dia. Devolve o caminho do arquivo."""
    agora = time.localtime()
    arquivo = pasta_historico() / time.strftime("%Y-%m-%d.md", agora)

    novo = not arquivo.exists()
    texto = (texto or "").strip()
    with open(arquivo, "a", encoding="utf-8", newline="\n") as f:
        if novo:
            f.write(f"# Ditados de {time.strftime('%d/%m/%Y', agora)}\n\n")
        f.write(
            f"## {time.strftime('%H:%M:%S', agora)} "
            f"· áudio {duracao_audio:.1f} s · transcrição {tempo_transcricao:.2f} s\n\n"
        )
        f.write(f"{texto}\n\n---\n\n")
    return arquivo
