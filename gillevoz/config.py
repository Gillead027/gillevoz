"""Configuração do GilleVoz, guardada em config.json na raiz do projeto.

Regras:
- Se o config.json não existir, ele é criado com os valores padrão (DEFAULTS).
- Se faltar alguma chave, ela é acrescentada com o valor padrão.
- Nunca apagamos as chaves que o usuário já tem (nem as que não conhecemos).
- Se o arquivo estiver com erro de sintaxe, guardamos uma cópia com a
  extensão .invalido-AAAAMMDD-HHMMSS e recriamos com os padrões.
"""

import copy
import json
import os
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

DEFAULTS = {
    "atalho": "ctrl+shift+space",
    "modo": "toggle",  # "toggle" (aperta e solta) ou "push" (segura)
    "modelo": "large-v3-turbo",
    "dispositivo": "cuda",
    "compute_type": "float16",
    "modelo_cpu": "small",
    "idioma": "pt",
    "vocabulario": [
        "Maestri", "Maestro", "Claude", "Claude Code", "Codex", "Opus", "Haiku",
        "Gillezin", "Cariacica", "capixaba", "027", "Batalha do STN", "Delux MC",
        "Vercel", "Supabase", "Next.js", "Tailwind", "deploy", "commit", "prompt",
        "workspace", "front-end", "back-end", "Dito Feito", "Ponte Cultural",
        "NÃO MORRO FÁLIDO", "OUTFIT", "D.A.P.A.",
    ],
    "metodo_colagem": "clipboard",  # "clipboard" (cola) ou "digitar"
    "auto_enter": False,  # nunca aperta Enter sozinho por padrão
    "espaco_final": True,  # acrescenta um espaço no fim do texto colado (não duplica)
    "microfone": None,  # None = microfone padrão do sistema
    "bips": True,
    "ativo": True,
    "barra_ativa": True,  # mostra a Flow Bar flutuante
    "barra_x": None,  # posição salva da barra (None = padrão: centro inferior)
    "barra_y": None,
}


def _ler_json(caminho: Path):
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    """Grava o config.json de forma segura (arquivo temporário + troca)."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(CONFIG_PATH.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, CONFIG_PATH)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load_config() -> dict:
    """Devolve o config como dict. Cria o arquivo se não existir."""
    if not CONFIG_PATH.exists():
        cfg = copy.deepcopy(DEFAULTS)
        save_config(cfg)
        return cfg

    try:
        cfg_usuario = _ler_json(CONFIG_PATH)
        if not isinstance(cfg_usuario, dict):
            raise ValueError("o config.json precisa ser um objeto { ... }")
    except (ValueError, OSError) as erro:
        # JSON quebrado: guarda a cópia para o usuário recuperar e recria os padrões.
        marca = time.strftime("%Y%m%d-%H%M%S")
        copia = CONFIG_PATH.with_name(f"config.json.invalido-{marca}")
        os.replace(CONFIG_PATH, copia)
        cfg = copy.deepcopy(DEFAULTS)
        save_config(cfg)
        print(f"[config] config.json inválido ({erro}). Cópia em {copia.name}; usando padrões.")
        return cfg

    cfg = copy.deepcopy(DEFAULTS)
    cfg.update(cfg_usuario)  # o que o usuário escreveu vence o padrão
    if any(k not in cfg_usuario for k in DEFAULTS):
        save_config(cfg)  # acrescenta as chaves novas, sem apagar nada
    return cfg
