"""Histórico: cada transcrição vai para historico/AAAA-MM-DD.md (leitura humana)
e para historico/AAAA-MM-DD.jsonl (dados estruturados, usados pela interface)."""

import datetime
import json
import re
import time
from pathlib import Path

from . import config

_CABECALHO = re.compile(
    r"^## (\d\d:\d\d:\d\d) · áudio ([\d.]+) s · transcrição ([\d.]+) s$"
)
_DIA = re.compile(r"^\d{4}-\d\d-\d\d$")


def pasta_historico() -> Path:
    pasta = config.PASTA_DADOS / "historico"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _hoje() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def salvar(texto: str, duracao_audio: float, tempo_transcricao: float) -> Path:
    """Acrescenta a transcrição ao .md e ao .jsonl do dia. Devolve o caminho do .md."""
    agora = time.localtime()
    pasta = pasta_historico()
    arquivo = pasta / time.strftime("%Y-%m-%d.md", agora)

    novo = not arquivo.exists()
    texto = (texto or "").strip()
    hora = time.strftime("%H:%M:%S", agora)
    with open(arquivo, "a", encoding="utf-8", newline="\n") as f:
        if novo:
            f.write(f"# Ditados de {time.strftime('%d/%m/%Y', agora)}\n\n")
        f.write(
            f"## {hora} "
            f"· áudio {duracao_audio:.1f} s · transcrição {tempo_transcricao:.2f} s\n\n"
        )
        f.write(f"{texto}\n\n---\n\n")

    item = {
        "hora": hora,
        "texto": texto,
        "duracao_audio": float(duracao_audio),
        "tempo_transcricao": float(tempo_transcricao),
        "palavras": len(texto.split()),
    }
    jsonl = pasta / time.strftime("%Y-%m-%d.jsonl", agora)
    with open(jsonl, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return arquivo


def _ler_jsonl(caminho: Path) -> list[dict]:
    itens = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            item = json.loads(linha)
        except ValueError:
            continue  # linha quebrada (ex.: queda de energia no meio da escrita)
        if isinstance(item, dict):
            itens.append(item)
    return itens


def _ler_md(caminho: Path) -> list[dict]:
    """Lê um .md no formato do v1 (dia sem .jsonl correspondente)."""
    itens = []
    atual = None
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        m = _CABECALHO.match(linha)
        if m:
            atual = {
                "hora": m.group(1),
                "duracao_audio": float(m.group(2)),
                "tempo_transcricao": float(m.group(3)),
                "linhas": [],
            }
            itens.append(atual)
        elif linha == "---":
            atual = None
        elif atual is not None:
            atual["linhas"].append(linha)
    for item in itens:
        texto = "\n".join(item.pop("linhas")).strip()
        item["texto"] = texto
        item["palavras"] = len(texto.split())
    return itens


def listar(dia: str | None = None) -> list[dict]:
    """Ditados do dia (AAAA-MM-DD, padrão hoje), do mais recente para o mais antigo."""
    dia = dia or _hoje()
    if not _DIA.match(dia):
        return []
    pasta = config.PASTA_DADOS / "historico"
    jsonl, md = pasta / f"{dia}.jsonl", pasta / f"{dia}.md"
    if jsonl.is_file():
        itens = _ler_jsonl(jsonl)
    elif md.is_file():
        itens = _ler_md(md)
    else:
        return []
    return itens[::-1]


def dias() -> list[str]:
    """Dias com histórico, do mais recente para o mais antigo."""
    pasta = config.PASTA_DADOS / "historico"
    if not pasta.is_dir():
        return []
    achados = {
        p.stem for p in pasta.iterdir()
        if p.suffix in (".md", ".jsonl") and _DIA.match(p.stem)
    }
    return sorted(achados, reverse=True)


def estatisticas() -> dict:
    """Números para o painel: palavras, ditados, palavras por minuto e sequência de dias."""
    hoje = _hoje()
    palavras_total = ditados_total = palavras_hoje = 0
    segundos = 0.0
    com_ditado = set()
    for dia in dias():
        itens = listar(dia)
        if not itens:
            continue
        com_ditado.add(dia)
        palavras = sum(int(i.get("palavras", 0)) for i in itens)
        palavras_total += palavras
        ditados_total += len(itens)
        segundos += sum(float(i.get("duracao_audio", 0)) for i in itens)
        if dia == hoje:
            palavras_hoje = palavras

    ppm = int(palavras_total / (segundos / 60)) if segundos > 0 else 0

    # sequência: dias seguidos com ditado, contando de hoje (ou de ontem, se hoje ainda não teve)
    dia_atual = datetime.date.fromisoformat(hoje)
    if hoje not in com_ditado:
        dia_atual -= datetime.timedelta(days=1)
    sequencia = 0
    while dia_atual.isoformat() in com_ditado:
        sequencia += 1
        dia_atual -= datetime.timedelta(days=1)

    return {
        "palavras_hoje": palavras_hoje,
        "palavras_total": palavras_total,
        "ditados_total": ditados_total,
        "ppm": ppm,
        "sequencia_dias": sequencia,
    }
