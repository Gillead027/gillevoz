"""Tempo real: decide quais palavras já são estáveis e as digita na janela ativa.

Lógica pura: o que digitar/apagar entra por funções injetadas (sem I/O, sem stdout).
Seguro para uso a partir de uma única thread de trabalho.
"""
from __future__ import annotations

from typing import Callable

from gillevoz.texto import achar_gatilho, aplicar_trocas, maior_k, normalizar


class Concordancia:
    """Confirma uma palavra só quando duas leituras seguidas concordam com ela."""

    def __init__(self) -> None:
        self.confirmadas: list[str] = []  # global: nunca é zerado
        self._anterior: list[str] = []
        self._n_janela = 0  # quantas palavras da janela atual já foram confirmadas

    def alimentar(self, hipotese: list[str]) -> list[str]:
        """Recebe a hipótese atual e devolve as palavras recém-confirmadas."""
        comum = 0
        limite = min(len(hipotese), len(self._anterior))
        while comum < limite and normalizar(hipotese[comum]) == normalizar(self._anterior[comum]):
            comum += 1
        novas = hipotese[self._n_janela:comum] if comum > self._n_janela else []
        self._n_janela = max(self._n_janela, comum)
        self._anterior = hipotese
        self.confirmadas += novas
        return novas

    def nova_janela(self) -> None:
        """Começa uma nova janela de áudio; o texto confirmado global continua."""
        self._anterior = []
        self._n_janela = 0

    def finalizar(self, hipotese_final: list[str]) -> list[str]:
        """Devolve o que falta confirmar da leitura final da janela."""
        return hipotese_final[self._n_janela:]


class Digitador:
    """Segura as últimas K palavras (para trocas/gatilhos) e digita o resto."""

    def __init__(
        self,
        digitar: Callable[[str], None],
        apagar: Callable[[int], None],
        trocas: list,
        atalhos: list,
        k_minimo: int = 1,
    ) -> None:
        self._digitar = digitar
        # `apagar` fica guardado para o caso (não esperado com K correto) de um
        # gatilho já digitado; hoje o gatilho só age em palavras ainda seguradas.
        self._apagar = apagar
        self._trocas = trocas
        self._atalhos = atalhos
        # k_minimo: o motor usa 2 para segurar "pressione enter" até saber se é o fim da fala.
        self._k = max(maior_k(trocas, atalhos), k_minimo)
        # Cada item é (palavra, final). "final" = já passou por troca/gatilho e não deve
        # ser reprocessada (evita trocas em cascata quando o "para" contém o "de").
        self._buffer: list[tuple[str, bool]] = []
        self.texto = ""  # tudo que foi digitado

    def receber(self, palavras: list[str]) -> None:
        """Acumula palavras (uma a uma), aplica trocas e gatilhos e digita tudo menos as últimas K."""
        for palavra in palavras:
            self._buffer.append((palavra, False))
            self._aplicar_trocas_na_cauda()
            self._aplicar_gatilho()
            self._emitir(len(self._buffer) - self._k)

    def descarregar(self) -> None:
        """Digita as palavras que ainda estavam seguradas."""
        self._emitir(len(self._buffer))

    def _aplicar_trocas_na_cauda(self) -> None:
        inicio = len(self._buffer)
        while inicio > 0 and not self._buffer[inicio - 1][1]:
            inicio -= 1
        crus = [p for p, _ in self._buffer[inicio:]]
        trocadas = aplicar_trocas(crus, self._trocas)
        if trocadas != crus:
            self._buffer[inicio:] = [(p, True) for p in trocadas]

    def _aplicar_gatilho(self) -> None:
        gatilho = achar_gatilho([p for p, _ in self._buffer], self._atalhos)
        if gatilho:
            n, texto_pronto = gatilho
            self._buffer[-n:] = [(texto_pronto, True)]

    def _emitir(self, quantas: int) -> None:
        if quantas <= 0:
            return
        saindo, self._buffer = self._buffer[:quantas], self._buffer[quantas:]
        trecho = " ".join(p for p, _ in saindo)
        if self.texto:
            trecho = " " + trecho
        self._digitar(trecho)
        self.texto += trecho
