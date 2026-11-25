"""Motor sem janela: atalhos, gravação, tempo real, digitação/colagem, histórico e config.

Conversa com a interface (Electron) pelo protocolo JSON de protocolo.py (DESENHO-V2 §6.1).
Nunca escreve no stdout por conta própria: tudo que não é protocolo vai para o log.

Threads:
- quem chama iniciar()/cancelar() (atalho, leitor do stdin): só abre/fecha o microfone, rápido;
- parar() faz a transcrição final e a digitação/colagem; atalho e stdin o chamam numa thread
  de fundo para não travar;
- "gillevoz-tempo-real": durante a gravação mãos livres, transcreve e digita a cada intervalo;
- "gillevoz-nivel": manda o volume do microfone ~30x/s.
"""
from __future__ import annotations

import copy
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from . import config, historico, protocolo, som
from .audio import SAMPLERATE, bip
from .hotkey import AtalhoAcao, Hotkey, parse_atalho, validar_atalho
from .tempo_real import Concordancia, Digitador
from .texto import tirar_comando_enter
from .transcriber import montar_prompt

log = logging.getLogger("gillevoz")

ATALHOS = ("atalho", "atalho_push", "atalho_colar_ultima", "atalho_copiar_ultima")
JANELA_MAX_S = 25.0  # passa disso sem cortar e o Whisper (janela de 30 s) começa a perder fala
AUDIO_MIN_TR = int(0.3 * SAMPLERATE)  # menos que isso nem vale transcrever


def _so_palavras(texto: str) -> str:
    """Minúsculas, sem pontuação e com espaços simples (para comparar frases)."""
    return " ".join(re.sub(r"[^\w\s]", "", texto.lower()).split())


# O Whisper "ouve" estas frases no silêncio. Sozinhas, contam como nada dito.
_ALUCINACOES = {_so_palavras(t) for t in (
    "Obrigado.", "Obrigada.", "Legendas pela comunidade Amara.org", "Tchau.",
)}


def sem_fala(texto: str) -> bool:
    """True se o texto é vazio, só pontuação ou uma alucinação comum do silêncio."""
    limpo = _so_palavras(texto)
    return not limpo or limpo in _ALUCINACOES


def _dispositivos_entrada() -> list[dict]:
    """Microfones da API de áudio padrão do Windows: [{indice, nome}]."""
    import sounddevice as sd

    try:
        api = sd.query_devices(kind="input")["hostapi"]
    except Exception:
        api = None
    return [
        {"indice": i, "nome": d["name"]}
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0 and (api is None or d["hostapi"] == api)
    ]


def _copiar_padrao(texto: str) -> None:
    from . import paste

    paste.colocar_texto(texto)


@dataclass
class _Gravacao:
    """Tudo de uma gravação em andamento."""

    recorder: object
    push: bool
    tempo_real: bool
    hotkey_esc: object = None
    som_silenciado: bool = False
    parar: threading.Event = field(default_factory=threading.Event)
    threads: list = field(default_factory=list)
    # tempo real
    conc: Concordancia | None = None
    dig: Digitador | None = None
    digitado: str = ""      # o que realmente foi digitado (texto oficial)
    offset: int = 0         # amostra onde começa a janela atual
    contexto: str = ""      # texto confirmado antes da janela atual (vai no prompt)
    n_janela: int = 0       # palavras confirmadas na janela atual
    final: bool = False     # True durante a digitação final (comando "pressione enter")
    enter: bool = False     # o comando "pressione enter" foi dito no fim


class Motor:
    def __init__(
        self,
        cfg: dict,
        canal: protocolo.Canal,
        *,
        criar_recorder: Callable[[], object],
        transcriber,
        digitar: Callable[[str], None],
        apagar: Callable[[int], None],
        colar: Callable[..., None],
        enviar_enter: Callable[[], None],
        intervalo_tr: float = 0.8,
        criar_hotkey=Hotkey,
        criar_acao=AtalhoAcao,
        copiar: Callable[[str], None] | None = None,
    ):
        self.cfg = cfg
        self.canal = canal
        self.transcriber = transcriber
        self.intervalo_tr = intervalo_tr
        self.espera_erro = 3.0  # segundos mostrando "erro" antes de voltar a "ocioso"
        self._criar_recorder = criar_recorder
        self._digitar = digitar
        self._apagar = apagar
        self._colar = colar
        self._enviar_enter = enviar_enter
        self._criar_hotkey = criar_hotkey
        self._criar_acao = criar_acao
        self._copiar = copiar or _copiar_padrao

        self.estado = self._estado_livre()
        self._lock = threading.RLock()        # estado e gravação atual
        self._lock_modelo = threading.Lock()  # transcrever x recarregar o modelo
        self._gravacao: _Gravacao | None = None
        self._silenciador: som.Silenciador | None = None
        self._atalhos: dict = {}               # chave do config -> atalho registrado
        self._atalhos_ativos = False
        self._recarregar_pendente = False
        self._ultimo_texto = ""
        self._fundo: list[threading.Thread] = []
        self._lock_fundo = threading.Lock()
        self._sair = threading.Event()
        self._token_erro = 0

    # ------------------------------------------------------------ helpers
    def _estado_livre(self) -> str:
        return "ocioso" if self.cfg.get("ativo", True) else "pausado"

    def _set_estado(self, estado: str, msg: str | None = None) -> None:
        self.estado = estado
        campos = {"estado": estado}
        if msg:
            campos["msg"] = msg
        self.canal.enviar("estado", **campos)

    def _erro(self, msg: str) -> None:
        """Mostra o erro e, depois de espera_erro segundos, volta a ocioso."""
        with self._lock:
            self._token_erro += 1
            token = self._token_erro
            self._set_estado("erro", msg)
        self._bip("erro")
        t = threading.Timer(self.espera_erro, self._fim_do_erro, args=(token,))
        t.daemon = True
        t.start()

    def _fim_do_erro(self, token: int) -> None:
        with self._lock:
            if self.estado == "erro" and self._token_erro == token:
                self._set_estado(self._estado_livre())

    def _bip(self, tipo: str) -> None:
        if self.cfg.get("bips", True):
            bip(tipo)

    def _em_fundo(self, fn: Callable[[], None], nome: str) -> None:
        def rodar():
            try:
                fn()
            except Exception:
                log.exception("Erro em %s", nome)

        t = threading.Thread(target=rodar, daemon=True, name=nome)
        with self._lock_fundo:
            self._fundo = [x for x in self._fundo if x.is_alive()]
            self._fundo.append(t)
        t.start()

    def aguardar(self, timeout: float = 30.0) -> None:
        """Espera as threads de fundo (parar, recarregar modelo, colar última) terminarem."""
        fim = time.monotonic() + timeout
        with self._lock_fundo:
            threads = list(self._fundo)
        for t in threads:
            if t is not threading.current_thread():
                t.join(max(0.0, fim - time.monotonic()))

    def _responder(self, cmd: dict, **campos) -> None:
        self.canal.enviar(f"{cmd['tipo']}_resposta", id=cmd.get("id"), **campos)

    # ------------------------------------------------------------ gravação
    def iniciar(self, push: bool = False, origem=None) -> None:
        """Começa a gravar. push=True (segurar para falar) nunca usa tempo real.

        origem: o Hotkey que iniciou (só ele captura o Esc); None = o atalho principal.
        """
        with self._lock:
            if self._sair.is_set() or not self.cfg.get("ativo", True):
                return
            if self.estado not in ("ocioso", "erro"):
                if self.estado == "transcrevendo":
                    self._bip("erro")
                return
            try:
                rec = self._criar_recorder()
                rec.start()
            except Exception as e:
                log.error("Não consegui abrir o microfone: %s", e)
                self._erro(f"Microfone indisponível: {e}")
                return
            g = _Gravacao(recorder=rec, push=push,
                          tempo_real=bool(self.cfg.get("tempo_real", True)) and not push)
            self._gravacao = g
            self._token_erro += 1  # um "volta a ocioso" pendente não vale mais
            self._set_estado("gravando")

            hk = origem if origem is not None else self._atalhos.get("atalho")
            if hk is not None:
                try:
                    hk.capturar_esc(True)
                    g.hotkey_esc = hk
                except Exception:
                    log.debug("capturar_esc falhou", exc_info=True)
            if self.cfg.get("silenciar_pc"):
                if self._silenciador is None:
                    self._silenciador = som.Silenciador()
                self._silenciador.silenciar()
                g.som_silenciado = True

            if g.tempo_real:
                g.conc = Concordancia()
                g.dig = Digitador(
                    lambda trecho, g=g: self._digitar_trecho(g, trecho), self._apagar,
                    self.cfg.get("trocas") or [], self.cfg.get("atalhos_texto") or [],
                    k_minimo=2 if self.cfg.get("comando_enter", True) else 1,
                )
                self._nova_thread(g, self._laco_tempo_real, "gillevoz-tempo-real")
            self._nova_thread(g, self._laco_nivel, "gillevoz-nivel")
        self._bip("inicio")

    def _nova_thread(self, g: _Gravacao, alvo, nome: str) -> None:
        t = threading.Thread(target=alvo, args=(g,), daemon=True, name=nome)
        g.threads.append(t)
        t.start()

    def _encerrar_threads(self, g: _Gravacao) -> None:
        g.parar.set()
        for t in g.threads:
            if t is not threading.current_thread():
                t.join(10)

    def _soltar_esc(self, g: _Gravacao) -> None:
        if g.hotkey_esc is not None:
            try:
                g.hotkey_esc.capturar_esc(False)
            except Exception:
                log.debug("capturar_esc(False) falhou", exc_info=True)

    def _restaurar_som(self, g: _Gravacao) -> None:
        if g.som_silenciado and self._silenciador is not None:
            g.som_silenciado = False
            self._silenciador.restaurar()

    def cancelar(self) -> None:
        """Descarta a gravação. No tempo real, o que já foi digitado fica (dá para Ctrl+Z)."""
        with self._lock:
            g = self._gravacao
            if self.estado != "gravando" or g is None:
                return
            self._gravacao = None
            g.parar.set()
            try:
                g.recorder.cancel()
            finally:
                self._soltar_esc(g)
                self._set_estado(self._estado_livre())
        try:
            self._encerrar_threads(g)
        finally:
            self._restaurar_som(g)
            self._depois_da_gravacao()
        log.info("Gravação cancelada.")

    def parar(self) -> None:
        """Para de gravar, transcreve o resto, digita/cola e salva. Volta a ocioso no fim."""
        with self._lock:
            g = self._gravacao
            if self.estado != "gravando" or g is None:
                return
            self._gravacao = None
            g.parar.set()
            self._set_estado("transcrevendo")
            self._soltar_esc(g)
            try:
                audio = g.recorder.stop()
            except Exception as e:
                log.exception("Erro ao parar a gravação")
                audio, erro = None, f"Erro ao parar a gravação: {e}"
            else:
                erro = None
        try:
            self._encerrar_threads(g)
            self._restaurar_som(g)  # antes do bip, para ele ser ouvido
            self._bip("fim")
            if erro is None:
                self._finalizar(g, audio)
        except Exception as e:
            log.exception("Erro ao transcrever/digitar")
            erro = f"Erro ao transcrever: {e}"
        finally:
            self._restaurar_som(g)
            self._depois_da_gravacao()
        if erro:
            self._erro(erro)
            return
        with self._lock:
            if self.estado == "transcrevendo":
                self._set_estado(self._estado_livre())

    def _finalizar(self, g: _Gravacao, audio) -> None:
        duracao = len(audio) / SAMPLERATE
        t0 = time.perf_counter()
        if g.tempo_real:
            texto = self._finalizar_tempo_real(g, audio)
        else:
            texto = self._finalizar_colando(audio)
        dt = time.perf_counter() - t0
        log.info("Transcrição: áudio %.1f s | final %.2f s | %s | %d caracteres",
                 duracao, dt, "tempo real" if g.tempo_real else "colado", len(texto))
        if not texto:
            log.info("Nenhuma fala reconhecida; nada digitado.")
            return
        self._ultimo_texto = texto
        try:
            historico.salvar(texto, duracao, dt)
        except Exception:
            log.exception("Falha ao salvar no histórico")
        self.canal.enviar("final", texto=texto, duracao_audio=round(duracao, 2),
                          tempo_transcricao=round(dt, 3), palavras=len(texto.split()))
        self.canal.enviar("historico", dia=time.strftime("%Y-%m-%d"))

    # ------------------------------------------------------------ modo colar (push / sem tempo real)
    def _aplicar_trocas(self, texto: str) -> str:
        partes: list[str] = []
        dig = Digitador(partes.append, lambda n: None,
                        self.cfg.get("trocas") or [], self.cfg.get("atalhos_texto") or [])
        dig.receber(texto.split())
        dig.descarregar()
        return dig.texto

    def _finalizar_colando(self, audio) -> str:
        with self._lock_modelo:
            texto = self.transcriber.transcrever(audio)
        if sem_fala(texto):
            return ""
        enter = False
        if self.cfg.get("comando_enter", True):
            texto, enter = tirar_comando_enter(texto)
        texto = self._aplicar_trocas(texto)
        if not texto:
            if enter:
                self._enviar_enter()
            return ""
        self._colar(
            texto,
            metodo=self.cfg.get("metodo_colagem", "clipboard"),
            auto_enter=bool(self.cfg.get("auto_enter", False)) or enter,
            espera_ms=int(self.cfg.get("espera_colagem_ms", 150)),
            espaco_final=bool(self.cfg.get("espaco_final", True)),
        )
        return texto

    # ------------------------------------------------------------ tempo real
    def _digitar_trecho(self, g: _Gravacao, trecho: str) -> None:
        if g.final and self.cfg.get("comando_enter", True):
            trecho, enter = tirar_comando_enter(trecho)
            g.enter = g.enter or enter
        if trecho:
            self._digitar(trecho)
            g.digitado += trecho

    def _laco_nivel(self, g: _Gravacao) -> None:
        while not g.parar.wait(1 / 30):
            try:
                self.canal.enviar("nivel", valor=round(float(g.recorder.nivel()), 3))
            except Exception:
                log.debug("medidor de nível parou", exc_info=True)
                return

    def _laco_tempo_real(self, g: _Gravacao) -> None:
        falhas = 0
        while not g.parar.wait(self.intervalo_tr):
            try:
                self._passo_tempo_real(g)
                falhas = 0
            except Exception:
                falhas += 1
                log.exception("Erro no tempo real (%d)", falhas)
                if falhas >= 3:
                    log.error("Tempo real desligado nesta gravação; o resto entra no final.")
                    return

    def _passo_tempo_real(self, g: _Gravacao) -> None:
        audio = g.recorder.amostras(g.offset)
        if len(audio) < AUDIO_MIN_TR:
            return
        with self._lock_modelo:
            palavras = self.transcriber.transcrever_palavras(audio, g.contexto)
        if g.parar.is_set():
            return  # parou/cancelou durante a leitura: não digita mais nada aqui
        hipotese = [p for p, _, _ in palavras]
        if sem_fala(" ".join(hipotese)):
            hipotese, palavras = [], []
        novas = g.conc.alimentar(hipotese)
        if novas:
            g.n_janela += len(novas)
            antes = g.digitado
            g.dig.receber(novas)
            if g.digitado != antes:
                self.canal.enviar("parcial", confirmado=g.digitado)
        if len(audio) > JANELA_MAX_S * SAMPLERATE:
            self._cortar_janela(g, audio, palavras)

    def _cortar_janela(self, g: _Gravacao, audio, palavras) -> None:
        """Fala longa: a janela recomeça no fim da última palavra confirmada."""
        if g.n_janela and g.n_janela <= len(palavras):
            g.offset += int(palavras[g.n_janela - 1][2] * SAMPLERATE)
        elif not palavras:
            g.offset += len(audio) - SAMPLERATE  # silêncio: guarda só o último segundo
        else:
            return  # nada confirmado ainda nesta janela: espera
        g.conc.nova_janela()
        g.n_janela = 0
        g.contexto = " ".join(g.conc.confirmadas)

    def _finalizar_tempo_real(self, g: _Gravacao, audio) -> str:
        with self._lock_modelo:
            palavras = self.transcriber.transcrever_palavras(audio[g.offset:], g.contexto)
        resto = g.conc.finalizar([p for p, _, _ in palavras])
        if not g.conc.confirmadas and sem_fala(" ".join(resto)):
            resto = []
        g.final = True
        g.dig.receber(resto)
        g.dig.descarregar()
        texto = g.digitado.strip()
        enter = g.enter or bool(self.cfg.get("auto_enter", False))
        if texto and not enter and self.cfg.get("espaco_final", True):
            self._digitar(" ")  # o próximo ditado não fica grudado (não entra no texto oficial)
        if enter and (texto or g.enter):
            self._enviar_enter()
        return texto

    # ------------------------------------------------------------ pausar / última transcrição
    def pausar(self) -> None:
        with self._lock:
            if self.cfg.get("ativo", True):
                self.cfg["ativo"] = False
                config.save_config(self.cfg)
            if self.estado == "gravando":
                self.cancelar()
            if self.estado not in ("pausado", "transcrevendo"):
                self._set_estado("pausado")

    def retomar(self) -> None:
        with self._lock:
            if not self.cfg.get("ativo", True):
                self.cfg["ativo"] = True
                config.save_config(self.cfg)
            if self.estado == "pausado":
                self._set_estado("ocioso")

    def _texto_ultima(self) -> str:
        if self._ultimo_texto:
            return self._ultimo_texto
        for dia in historico.dias():
            itens = historico.listar(dia)
            if itens:
                return itens[0].get("texto", "")
        return ""

    def colar_ultima(self) -> None:
        texto = self._texto_ultima()
        if not texto:
            log.info("Colar última: nenhum ditado ainda.")
            return
        self._colar(
            texto,
            metodo=self.cfg.get("metodo_colagem", "clipboard"),
            auto_enter=False,
            espera_ms=int(self.cfg.get("espera_colagem_ms", 150)),
            espaco_final=bool(self.cfg.get("espaco_final", True)),
        )

    def copiar_ultima(self) -> None:
        texto = self._texto_ultima()
        if texto:
            self._copiar(texto)
            log.info("Última transcrição copiada (%d caracteres).", len(texto))

    # ------------------------------------------------------------ atalhos
    def _registrar(self, chave: str, atalho: str):
        """Cria e liga o atalho de uma chave do config. Levanta exceção se falhar."""
        if chave in ("atalho", "atalho_push"):
            push = chave == "atalho_push"
            caixa = {}
            hk = self._criar_hotkey(
                atalho, "push" if push else "toggle",
                on_iniciar=lambda: self.iniciar(push=push, origem=caixa["hk"]),
                # push: a soltura já vem numa thread própria; toggle: tira da thread do atalho
                on_parar=self.parar if push else (lambda: self._em_fundo(self.parar, "gillevoz-parar")),
                on_cancelar=self.cancelar,
                esta_gravando=lambda: self.estado == "gravando",
            )
            caixa["hk"] = hk
        else:
            acao = self.colar_ultima if chave == "atalho_colar_ultima" else self.copiar_ultima
            hk = self._criar_acao(atalho, lambda: self._em_fundo(acao, f"gillevoz-{chave}"))
        hk.start()
        return hk

    def registrar_atalhos(self) -> None:
        """Liga os atalhos globais do config (chamado pelo modo --motor, não nos testes)."""
        self._atalhos_ativos = True
        for chave in ATALHOS:
            atalho = self.cfg.get(chave)
            if not atalho:
                continue
            try:
                self._atalhos[chave] = self._registrar(chave, atalho)
            except Exception as e:
                log.exception("Não consegui ativar o atalho %s=%r", chave, atalho)
                self.canal.enviar("log", nivel="erro", msg=f"Não consegui ativar o atalho '{atalho}': {e}")

    def _parar_atalho(self, chave: str) -> None:
        hk = self._atalhos.pop(chave, None)
        if hk is not None:
            try:
                hk.stop()
            except Exception:
                log.debug("Erro ao parar o atalho %s", chave, exc_info=True)

    def _reregistrar(self, antigo: dict) -> list[str]:
        """Re-registra os atalhos que mudaram. Se um falhar, volta o anterior. Devolve os erros."""
        if not self._atalhos_ativos:
            return []
        erros = []
        for chave in ATALHOS:
            novo = self.cfg.get(chave)
            if novo == antigo.get(chave):
                continue
            self._parar_atalho(chave)
            if not novo:
                continue
            try:
                self._atalhos[chave] = self._registrar(chave, novo)
            except Exception as e:
                log.warning("Atalho %s=%r falhou (%s); mantendo o anterior.", chave, novo, e)
                erros.append(f"Não consegui ativar o atalho '{novo}': {e}")
                self.cfg[chave] = antigo.get(chave)
                if antigo.get(chave):
                    try:
                        self._atalhos[chave] = self._registrar(chave, antigo[chave])
                    except Exception:
                        log.exception("Não consegui reativar o atalho anterior %r", antigo[chave])
        return erros

    # ------------------------------------------------------------ config
    def _validar_atalhos(self, novo: dict, antigo: dict) -> list[str]:
        """Confere os atalhos de `novo`; os inválidos voltam ao valor de `antigo`."""
        erros, usados = [], {}
        for chave in ATALHOS:
            valor = novo.get(chave)
            if valor is None and chave != "atalho":
                continue  # atalho opcional desligado
            erro = validar_atalho(valor)
            if erro is None:
                combinacao = parse_atalho(valor)
                if combinacao in usados:
                    erro = f"O atalho '{valor}' já é usado em '{usados[combinacao]}'."
                else:
                    usados[combinacao] = chave
            if erro:
                erros.append(erro)
                novo[chave] = antigo.get(chave)
        return erros

    def salvar_config(self, parcial, id_=None) -> None:
        if not isinstance(parcial, dict):
            self.canal.enviar("log", nivel="erro", msg="salvar_config sem 'cfg' válido.")
            return
        with self._lock:
            antigo = copy.deepcopy(self.cfg)
            novo = {**antigo, **copy.deepcopy(parcial)}
            erros = self._validar_atalhos(novo, antigo)
            novo = config.limpar(novo)
            self.cfg.clear()
            self.cfg.update(novo)  # mesmo dict: quem guardou a referência vê a mudança
            config.save_config(self.cfg)
            falhas = self._reregistrar(antigo)
            if falhas:
                erros += falhas
                config.save_config(self.cfg)
            modelo_mudou = any(antigo.get(k) != self.cfg.get(k) for k in ("modelo", "dispositivo"))
            vocab_mudou = any(antigo.get(k) != self.cfg.get(k) for k in ("vocabulario", "idioma"))
            if self.estado in ("gravando", "transcrevendo"):
                self._recarregar_pendente = self._recarregar_pendente or modelo_mudou
                modelo_mudou = False
            if self.estado == "pausado" and self.cfg.get("ativo", True):
                self._set_estado("ocioso")
            elif self.estado == "ocioso" and not self.cfg.get("ativo", True):
                self._set_estado("pausado")
        for erro in erros:
            self.canal.enviar("log", nivel="erro", msg=erro)
        if modelo_mudou:
            self._recarregar_modelo()
        elif vocab_mudou:
            self._aplicar_vocabulario()
        extra = {"id": id_} if id_ is not None else {}
        self.canal.enviar("config", cfg=copy.deepcopy(self.cfg), **extra)

    def _aplicar_vocabulario(self) -> None:
        tr = self.transcriber
        with self._lock_modelo:
            tr.vocab = list(self.cfg.get("vocabulario") or [])
            tr.idioma = self.cfg.get("idioma", "pt")
            tr.initial_prompt = montar_prompt(tr.vocab, "")

    def _recarregar_modelo(self) -> None:
        cfg = copy.deepcopy(self.cfg)

        def trabalho():
            try:
                with self._lock_modelo:
                    self.transcriber.recarregar(cfg)
            except Exception as e:
                log.exception("Não consegui recarregar o modelo")
                self.canal.enviar("log", nivel="erro", msg=f"Não consegui carregar o modelo: {e}")
                return
            self.canal.enviar("pronto", dispositivo=getattr(self.transcriber, "device_efetivo", None),
                              modelo=getattr(self.transcriber, "modelo_efetivo", None))

        self._em_fundo(trabalho, "gillevoz-recarregar")

    def _depois_da_gravacao(self) -> None:
        """Aplica uma troca de modelo que chegou no meio da gravação."""
        with self._lock:
            pendente, self._recarregar_pendente = self._recarregar_pendente, False
        if pendente:
            self._recarregar_modelo()

    # ------------------------------------------------------------ protocolo
    def tratar(self, cmd: dict) -> None:
        """Executa um comando da interface (DESENHO-V2 §6.1)."""
        tipo = cmd.get("tipo")
        try:
            if tipo == "iniciar":
                self.iniciar()
            elif tipo == "parar":
                self._em_fundo(self.parar, "gillevoz-parar")
            elif tipo == "cancelar":
                self.cancelar()
            elif tipo == "pausar":
                self.pausar()
            elif tipo == "retomar":
                self.retomar()
            elif tipo == "ler_config":
                self._responder(cmd, cfg=copy.deepcopy(self.cfg))
            elif tipo == "salvar_config":
                self.salvar_config(cmd.get("cfg"), cmd.get("id"))
            elif tipo == "colar_ultima":
                self._em_fundo(self.colar_ultima, "gillevoz-colar-ultima")
            elif tipo == "copiar_ultima":
                self.copiar_ultima()
            elif tipo == "listar_historico":
                dia = cmd.get("dia")
                dia = dia if isinstance(dia, str) and dia else time.strftime("%Y-%m-%d")
                self._responder(cmd, dia=dia, itens=historico.listar(dia), dias=historico.dias())
            elif tipo == "estatisticas":
                self._responder(cmd, **historico.estatisticas())
            elif tipo == "listar_microfones":
                self._responder(cmd, itens=_dispositivos_entrada())
            elif tipo == "sair":
                self._sair.set()
            else:
                log.warning("Comando desconhecido: %r", tipo)
                self.canal.enviar("log", nivel="aviso", msg=f"Comando desconhecido: {tipo}")
        except Exception as e:
            log.exception("Erro ao tratar o comando %r", tipo)
            self.canal.enviar("log", nivel="erro", msg=f"Erro ao tratar '{tipo}': {e}")

    def rodar(self, entrada) -> None:
        """Laço principal: lê comandos até 'sair' ou fim da entrada (interface fechou)."""
        try:
            for cmd in protocolo.ler(entrada):
                self.tratar(cmd)
                if self._sair.is_set():
                    break
        finally:
            self.encerrar()

    def encerrar(self) -> None:
        self._sair.set()  # bloqueia novas gravações
        for chave in list(self._atalhos):
            self._parar_atalho(chave)
        self.cancelar()
        self.aguardar()
        log.info("Motor encerrado.")
