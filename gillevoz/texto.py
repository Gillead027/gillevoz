"""Lógica de texto pura: trocas de palavras, atalhos de texto e comando "pressione enter".

Sem I/O e sem stdout (stdout é o protocolo JSON do motor).
"""
from __future__ import annotations

import re

_PONTAS = re.compile(r"^\W+|\W+$")
_PONTUACAO_FINAL = re.compile(r"\W+$")
_ENTER = re.compile(r"\s*\bpressione\s+enter\W*$", re.IGNORECASE)


def normalizar(palavra: str) -> str:
    """Minúsculas e sem pontuação nas pontas (acentos mantidos)."""
    return _PONTAS.sub("", palavra.lower())


def _chave(texto: str) -> list[str]:
    return [normalizar(p) for p in texto.split()]


def aplicar_trocas(palavras: list[str], trocas: list[dict]) -> list[str]:
    """Troca sequências de palavras ("de" -> "para"), preferindo a sequência mais longa.

    A pontuação final da última palavra trocada é mantida.
    """
    regras = [(_chave(t["de"]), t["para"].split()) for t in trocas]
    regras = [(de, para) for de, para in regras if de and para]
    regras.sort(key=lambda r: len(r[0]), reverse=True)
    norm = [normalizar(p) for p in palavras]

    saida: list[str] = []
    i = 0
    while i < len(palavras):
        for de, para in regras:
            n = len(de)
            if norm[i:i + n] == de:
                pontuacao = _PONTUACAO_FINAL.search(palavras[i + n - 1])
                novo = list(para)
                if pontuacao:
                    novo[-1] += pontuacao.group()
                saida.extend(novo)
                i += n
                break
        else:
            saida.append(palavras[i])
            i += 1
    return saida


def achar_gatilho(palavras: list[str], atalhos: list[dict]) -> tuple[int, str] | None:
    """Se o fim de `palavras` bate com um gatilho, devolve (nº de palavras, texto). O mais longo vence."""
    norm = [normalizar(p) for p in palavras]
    melhor: tuple[int, str] | None = None
    for atalho in atalhos:
        gatilho = _chave(atalho["gatilho"])
        n = len(gatilho)
        if n == 0 or n > len(norm) or norm[-n:] != gatilho:
            continue
        if melhor is None or n > melhor[0]:
            melhor = (n, atalho["texto"])
    return melhor


def maior_k(trocas: list[dict], atalhos: list[dict]) -> int:
    """Maior número de palavras entre os "de" das trocas e os gatilhos dos atalhos (mínimo 1)."""
    tamanhos = [len(t["de"].split()) for t in trocas] + [len(a["gatilho"].split()) for a in atalhos]
    return max([1, *tamanhos])


def tirar_comando_enter(texto: str) -> tuple[str, bool]:
    """Se o texto termina com "pressione enter", remove o comando e devolve (texto, True)."""
    m = _ENTER.search(texto)
    if not m:
        return texto, False
    return texto[:m.start()].rstrip(), True
