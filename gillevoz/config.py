"""Configuração do GilleVoz, guardada em config.json na pasta de dados.

A pasta de dados é %APPDATA%/GilleVoz (ou a pasta indicada pela variável de
ambiente GILLEVOZ_DADOS, usada nos testes).

Regras:
- Se o config.json não existir, ele é criado com os valores padrão (DEFAULTS).
- Se faltar alguma chave, ela é acrescentada com o valor padrão.
- Nunca apagamos as chaves que o usuário já tem (nem as que não conhecemos).
- Se o arquivo estiver com erro de sintaxe, guardamos uma cópia com a
  extensão .invalido-AAAAMMDD-HHMMSS e recriamos com os padrões.
"""

import copy
import json
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # pasta do código
PASTA_DADOS = Path(
    os.environ.get("GILLEVOZ_DADOS")
    or (Path(os.environ.get("APPDATA") or Path.home()) / "GilleVoz")
)
CONFIG_PATH = PASTA_DADOS / "config.json"

_log = logging.getLogger("gillevoz")

DEFAULTS = {
    "atalho": "ctrl+shift+space",
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
    "tempo_real": True,  # mostra a transcrição parcial enquanto fala
    "trocas": [],  # [{"de": str, "para": str}]
    "atalhos_texto": [],  # [{"gatilho": str, "texto": str}]
    "atalho_push": None,  # atalho de segurar-para-falar (None = desligado)
    "atalho_colar_ultima": None,
    "atalho_copiar_ultima": None,
    "silenciar_pc": False,
    "comando_enter": True,
    "barra_borda": "embaixo",
    "barra_pos": 0.5,
}


def _ler_json(caminho: Path):
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def _corrigir(chave: str, motivo: str) -> None:
    _log.warning("config: '%s' %s; corrigido.", chave, motivo)


def _tipo_ok(valor, padrao) -> bool:
    if padrao is None:
        # str (nome) ou int (índice do dispositivo, ex.: microfone); bool não vale como int
        return valor is None or isinstance(valor, str) or (
            isinstance(valor, int) and not isinstance(valor, bool)
        )
    if isinstance(padrao, bool):
        return isinstance(valor, bool)
    if isinstance(padrao, float):
        return isinstance(valor, (int, float)) and not isinstance(valor, bool)
    return isinstance(valor, type(padrao))


def _texto_ok(valor, vazio_ok: bool = False) -> bool:
    return isinstance(valor, str) and (vazio_ok or bool(valor.strip()))


def limpar(cfg: dict) -> dict:
    """Devolve uma cópia do config sem itens malformados e com tipos corrigidos."""
    cfg = copy.deepcopy(cfg)
    for chave, padrao in DEFAULTS.items():
        if chave in cfg and not _tipo_ok(cfg[chave], padrao):
            _corrigir(chave, f"com tipo errado ({type(cfg[chave]).__name__})")
            cfg[chave] = copy.deepcopy(padrao)

    def filtrar(chave, valido, normalizar):
        if chave not in cfg:
            return
        itens = []
        for item in cfg[chave]:
            if valido(item):
                itens.append(normalizar(item))
            else:
                _corrigir(chave, f"tinha um item inválido {item!r}")
        cfg[chave] = itens

    filtrar("vocabulario", lambda i: _texto_ok(i), lambda i: i)
    filtrar(
        "trocas",
        lambda i: isinstance(i, dict) and _texto_ok(i.get("de")) and _texto_ok(i.get("para"), True),
        lambda i: {"de": i["de"], "para": i["para"]},
    )
    filtrar(
        "atalhos_texto",
        lambda i: isinstance(i, dict) and _texto_ok(i.get("gatilho")) and _texto_ok(i.get("texto"), True),
        lambda i: {"gatilho": i["gatilho"], "texto": i["texto"]},
    )
    return cfg


def migrar_v1(origem: Path) -> bool:
    """Copia config.json e historico/ da pasta do v1 para a pasta de dados.

    Só migra se a pasta de dados ainda não existe. Devolve True se migrou.
    """
    origem = Path(origem)
    arq_config = origem / "config.json"
    if PASTA_DADOS.exists() or not arq_config.is_file():
        return False
    tmp = PASTA_DADOS.with_name(PASTA_DADOS.name + ".migrando")
    try:
        cfg = _ler_json(arq_config)
        if not isinstance(cfg, dict):
            raise ValueError("config.json do v1 não é um objeto")
        cfg.pop("barra_x", None)
        cfg.pop("barra_y", None)
        modo = cfg.pop("modo", None)
        if modo == "push":
            cfg["atalho_push"] = cfg.get("atalho")
            cfg["atalho"] = DEFAULTS["atalho"]
        # monta numa pasta temporária e só então troca, para não deixar migração pela metade
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        with open(tmp / "config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        if (origem / "historico").is_dir():
            shutil.copytree(origem / "historico", tmp / "historico")
        os.replace(tmp, PASTA_DADOS)
    except (ValueError, OSError) as erro:
        shutil.rmtree(tmp, ignore_errors=True)
        _log.warning("migração do v1 falhou: %s", erro)
        return False
    _log.info("config e histórico do v1 migrados de %s", origem)
    return True


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
        _log.warning("config.json inválido (%s). Cópia em %s; usando padrões.", erro, copia.name)
        return cfg

    cfg = copy.deepcopy(DEFAULTS)
    cfg.update(cfg_usuario)  # o que o usuário escreveu vence o padrão
    cfg = limpar(cfg)
    if any(k not in cfg_usuario for k in DEFAULTS):
        save_config(cfg)  # acrescenta as chaves novas, sem apagar nada
    return cfg
