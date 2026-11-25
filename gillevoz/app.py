"""Orquestra o GilleVoz: atalho/Flow Bar -> grava -> transcreve -> cola, com bandeja."""
from __future__ import annotations

import ctypes
import logging
import os
import threading
import time

from . import historico, paste
from .audio import Recorder, bip
from .config import CONFIG_PATH, load_config, save_config
from .log import setup_logging

log = logging.getLogger("gillevoz")

_MUTEX_NOME = "Local\\GilleVoz-instancia-unica"


def _instancia_unica():
    """Cria um mutex nomeado. Devolve o handle, ou None se já houver outro GilleVoz rodando."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    h = kernel32.CreateMutexW(None, False, _MUTEX_NOME)
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return h


class App:
    def __init__(self):
        self.log = setup_logging()
        self.cfg = load_config()
        self.estado = "ocioso"  # ocioso | gravando | transcrevendo | pausado
        self._lock = threading.RLock()
        self._sair = threading.Event()
        self._modelo_pronto = threading.Event()
        self._colagem_lock = threading.Lock()  # trecho crítico: mexe na área de transferência
        self._thread_transcricao = None
        self.transcriber = None
        self.recorder = Recorder(device=self.cfg.get("microfone"))
        self.indicator = None  # indicador antigo (só se barra_ativa=false ou a barra falhar)
        self.barra = None      # Flow Bar
        self._sessao = 0       # incrementa a cada gravação (encerra a thread do medidor antiga)
        self.tray = None
        self.hotkey = None
        self._t_inicio_gravacao = 0.0

    # ------------------------------------------------------------ inicialização
    def run(self) -> int:
        mutex = _instancia_unica()
        if mutex is None:
            self.log.warning("O GilleVoz já está rodando; saindo.")
            return 1

        self._iniciar_visual()
        self._iniciar_tray()

        threading.Thread(target=self._carregar_modelo, daemon=True, name="gillevoz-modelo").start()

        from .hotkey import Hotkey

        try:
            self.hotkey = Hotkey(
                self.cfg.get("atalho", "ctrl+shift+space"), self.cfg.get("modo", "toggle"),
                on_iniciar=self.iniciar_gravacao, on_parar=self.parar_gravacao,
                on_cancelar=self.cancelar_gravacao, esta_gravando=lambda: self.estado == "gravando",
            )
            self.hotkey.start()
        except Exception:
            self.log.exception("Não consegui ativar o atalho global '%s'", self.cfg.get("atalho"))
            self._notificar("Atalho inválido ou em uso. Veja o config.json.")

        if not self.cfg.get("ativo", True):
            self._set_estado("pausado")
        self.log.info("GilleVoz rodando. Atalho: %s (%s). Esc cancela a gravação.",
                      self.cfg.get("atalho"), self.cfg.get("modo"))
        try:
            while not self._sair.wait(0.5):
                pass
        except KeyboardInterrupt:
            pass
        self._encerrar()
        return 0

    def _iniciar_visual(self) -> None:
        """Flow Bar (padrão) ou, se desligada/quebrada, o indicador antigo."""
        if self.cfg.get("barra_ativa", True):
            barra = None
            try:
                from .flowbar import FlowBar

                x, y = self.cfg.get("barra_x"), self.cfg.get("barra_y")
                barra = FlowBar(
                    on_mic=lambda: self._em_thread(self.alternar_gravacao),
                    on_parar=lambda: self._em_thread(self.parar_gravacao),
                    on_cancelar=lambda: self._em_thread(self.cancelar_gravacao),
                    on_config=lambda: self._em_thread(lambda: os.startfile(str(CONFIG_PATH))),
                    on_sair=self.sair,
                    on_mover=lambda x_, y_: self._em_thread(self.salvar_posicao_barra, x_, y_),
                    posicao=(int(x), int(y)) if x is not None and y is not None else None,
                )
                barra.start()  # levanta exceção (inclusive timeout) se a janela não subir
                self.barra = barra
                self._barra("set_state", self.estado)
                if self.barra is not None:
                    return
            except Exception:
                self.log.warning("Falha ao iniciar a Flow Bar; usando o indicador simples", exc_info=True)
                self._parar_barra_com_seguranca(barra)
                self.barra = None
        try:
            from .indicator import Indicator

            self.indicator = Indicator()
            self.indicator.start()
        except Exception:
            self.log.exception("Falha ao iniciar o indicador (seguindo sem ele)")
            self.indicator = None

    def _parar_barra_com_seguranca(self, barra) -> None:
        if barra is None:
            return
        try:
            barra.stop()
        except Exception:
            self.log.debug("barra.stop() falhou ao desistir da Flow Bar", exc_info=True)

    def _barra(self, metodo: str, *args) -> bool:
        """Chama a Flow Bar tolerando barra morta: na 1ª falha, desliga a barra e segue sem ela.

        Devolve True se a chamada foi feita.
        """
        barra = getattr(self, "barra", None)
        if barra is None:
            return False
        t = getattr(barra, "_thread", None)
        erro = None
        if t is not None and not t.is_alive():
            erro = "thread da barra terminou"
        else:
            try:
                getattr(barra, metodo)(*args)
                return True
            except Exception as e:
                erro = f"{type(e).__name__}: {e}"
        if getattr(self, "barra", None) is barra:
            self.barra = None
            self.log.warning("Flow Bar parou de responder (%s em %s); seguindo sem ela.", erro, metodo)
            # stop() pode esperar a thread da barra; não segura quem chamou (às vezes com self._lock).
            threading.Thread(target=self._parar_barra_com_seguranca, args=(barra,), daemon=True,
                             name="gillevoz-parar-barra").start()
        return False

    def _em_thread(self, fn, *args) -> None:
        """Callbacks da barra rodam no loop de mensagens dela: tira o trabalho de lá."""
        def _rodar():
            try:
                fn(*args)
            except Exception:
                self.log.exception("Erro ao tratar ação da Flow Bar")
        threading.Thread(target=_rodar, daemon=True, name="gillevoz-acao-barra").start()

    def _iniciar_tray(self) -> None:
        try:
            from . import startup
            from .tray import Tray

            self.tray = Tray(
                on_toggle_ativo=self.toggle_ativo,
                on_abrir_historico=lambda: os.startfile(str(historico.pasta_historico())),
                on_abrir_config=lambda: os.startfile(str(CONFIG_PATH)),
                on_toggle_startup=self.toggle_startup,
                on_sair=self.sair,
                startup_ativo=startup.ativo,
            )
            self.tray.run_detached()
            self.tray.set_state("transcrevendo")  # enquanto o modelo carrega
        except Exception:
            self.log.exception("Falha ao iniciar o ícone da bandeja (seguindo sem ele)")
            self.tray = None

    def _carregar_modelo(self) -> None:
        from .transcriber import Transcriber

        try:
            self.transcriber = Transcriber(self.cfg)
            msg = f"GilleVoz pronto ({self.transcriber.device_efetivo}). {self.cfg.get('atalho')} para ditar."
            if self.transcriber.device_efetivo != "cuda":
                msg += " Atenção: rodando na CPU (mais lento)."
            self._notificar(msg)
        except Exception:
            self.log.exception("Não consegui carregar o modelo de transcrição")
            self._notificar("Erro ao carregar o modelo. Veja logs/gillevoz.log.")
        finally:
            self._modelo_pronto.set()
            with self._lock:
                if self.estado == "ocioso":
                    self._set_estado("ocioso")

    # ------------------------------------------------------------ helpers
    def _set_estado(self, estado: str) -> None:
        """Muda o estado e avisa bandeja e Flow Bar (chamar com self._lock)."""
        self.estado = estado
        self._barra("set_state", estado)
        if self.tray:
            try:
                self.tray.set_state(estado)
            except Exception:
                self.log.debug("tray.set_state falhou", exc_info=True)

    def _notificar(self, msg: str) -> None:
        self.log.info(msg)
        if self.tray:
            try:
                self.tray.notify(msg)
            except Exception:
                pass

    def _ind(self, metodo: str, *args) -> None:
        """Chama o indicador sem deixar uma falha dele travar o app (ele só enfileira comandos)."""
        ind = self.indicator
        if ind is None:
            return
        t = getattr(ind, "_thread", None)
        if t is not None and not t.is_alive():
            if not getattr(self, "_aviso_indicador", False):
                self._aviso_indicador = True
                self.log.error("Indicador de gravação parou de funcionar; seguindo sem ele.")
            return
        try:
            getattr(ind, metodo)(*args)
        except Exception:
            self.log.debug("Indicador falhou em %s", metodo, exc_info=True)

    def _bip(self, tipo: str) -> None:
        if self.cfg.get("bips", True):
            bip(tipo)

    # ------------------------------------------------------------ gravação
    def alternar_gravacao(self) -> None:
        """Clique no mic da barra: mesmo comportamento do atalho no modo toggle."""
        if self.estado == "gravando":
            self.parar_gravacao()
        else:
            self.iniciar_gravacao()

    def _medidor(self, sessao: int) -> None:
        """Manda o volume do microfone para a barra ~30x por segundo enquanto grava."""
        while not self._sair.is_set():
            with self._lock:
                if self.estado != "gravando" or self._sessao != sessao:
                    break
                nivel = self.recorder.nivel()
            if not self._barra("set_level", nivel):
                break
            time.sleep(1 / 30)

    def iniciar_gravacao(self) -> None:
        with self._lock:
            sair = getattr(self, "_sair", None)
            if sair is not None and sair.is_set():
                return
            if self.estado != "ocioso" or not self.cfg.get("ativo", True):
                if self.estado == "transcrevendo":
                    self._bip("erro")
                return
            try:
                self.recorder.device = self.cfg.get("microfone")
                self.recorder.start()
            except Exception as e:
                self.log.error("Não consegui abrir o microfone: %s", e)
                self._bip("erro")
                self._notificar("Não consegui abrir o microfone.")
                return
            self._t_inicio_gravacao = time.perf_counter()
            self._set_estado("gravando")
            if self.hotkey:
                self.hotkey.capturar_esc(True)
            # Estado e indicador mudam juntos, sob o mesmo lock: um cancelamento em outra
            # thread não consegue esconder a pílula antes dela aparecer.
            self._ind("show", "● gravando")
            self._sessao = getattr(self, "_sessao", 0) + 1
            if getattr(self, "barra", None) is not None:
                threading.Thread(target=self._medidor, args=(self._sessao,), daemon=True,
                                 name="gillevoz-medidor").start()
        self._bip("inicio")

    def parar_gravacao(self) -> None:
        with self._lock:
            if self.estado != "gravando":
                return
            audio = self.recorder.stop()
            if self.hotkey:
                self.hotkey.capturar_esc(False)
            self._set_estado("transcrevendo")
            self._ind("set_text", "… transcrevendo")
            self._thread_transcricao = threading.Thread(
                target=self._transcrever_e_colar, args=(audio,), daemon=True, name="gillevoz-transcricao")
            self._thread_transcricao.start()
        self._bip("fim")

    def cancelar_gravacao(self) -> None:
        with self._lock:
            if self.estado != "gravando":
                return
            self.recorder.cancel()
            if self.hotkey:
                self.hotkey.capturar_esc(False)
            self._set_estado("ocioso")
            self._ind("hide")
        self.log.info("Gravação cancelada (Esc).")

    def _transcrever_e_colar(self, audio) -> None:
        duracao = len(audio) / 16000.0
        try:
            if not self._modelo_pronto.is_set():
                self._ind("set_text", "… carregando modelo")
                self._modelo_pronto.wait()
            if self.transcriber is None:
                raise RuntimeError("modelo não carregado")
            t0 = time.perf_counter()
            texto = self.transcriber.transcrever(audio)
            dt = time.perf_counter() - t0
            self.log.info("Transcrição: áudio %.1f s | transcrição %.2f s | %.1fx tempo real | %s | %d caracteres",
                          duracao, dt, (duracao / dt) if dt > 0 else 0, self.transcriber.device_efetivo, len(texto))
            if texto:
                try:
                    historico.salvar(texto, duracao, dt)
                except Exception:
                    self.log.exception("Falha ao salvar no histórico")
                with self._colagem_lock:
                    if self._sair.is_set():
                        self.log.info("Saída solicitada: texto NÃO colado (está salvo no histórico).")
                    else:
                        paste.colar(
                            texto,
                            metodo=self.cfg.get("metodo_colagem", "clipboard"),
                            auto_enter=bool(self.cfg.get("auto_enter", False)),
                            espaco_final=bool(self.cfg.get("espaco_final", True)),
                            espera_ms=int(self.cfg.get("espera_colagem_ms", 150)),
                        )
            else:
                self.log.info("Nenhuma fala reconhecida; nada colado.")
        except Exception:
            self.log.exception("Erro ao transcrever/colar")
            self._bip("erro")
            self._notificar("Erro ao transcrever. Veja logs/gillevoz.log.")
        finally:
            with self._lock:
                if self.estado == "transcrevendo":
                    self._ind("hide")
                    self._set_estado("ocioso" if self.cfg.get("ativo", True) else "pausado")

    # ------------------------------------------------------------ menu da bandeja
    def toggle_ativo(self) -> None:
        with self._lock:
            self.cfg["ativo"] = not self.cfg.get("ativo", True)
            save_config(self.cfg)
            if not self.cfg["ativo"]:
                if self.estado == "gravando":
                    self.recorder.cancel()
                    if self.hotkey:
                        self.hotkey.capturar_esc(False)
                    self._ind("hide")
                    self._set_estado("ocioso")
                if self.estado != "transcrevendo":
                    self._set_estado("pausado")
            elif self.estado == "pausado":
                self._set_estado("ocioso")
        self.log.info("GilleVoz %s.", "ativado" if self.cfg["ativo"] else "pausado")

    def salvar_posicao_barra(self, x: int, y: int) -> None:
        """Chamado quando o usuário solta a barra depois de arrastar."""
        with self._lock:
            cfg_disco = load_config()  # relê o arquivo: não sobrescreve edições manuais
            cfg_disco["barra_x"], cfg_disco["barra_y"] = int(x), int(y)
            save_config(cfg_disco)
            self.cfg["barra_x"], self.cfg["barra_y"] = int(x), int(y)
        self.log.info("Posição da Flow Bar salva: %d, %d", x, y)

    def toggle_startup(self) -> None:
        from . import startup

        try:
            if startup.ativo():
                startup.desativar()
                self.log.info("Iniciar com o Windows: desligado")
            else:
                startup.ativar()
                self.log.info("Iniciar com o Windows: ligado")
        except Exception:
            self.log.exception("Falha ao mudar 'Iniciar com o Windows'")

    def sair(self) -> None:
        self._sair.set()

    def _encerrar(self) -> None:
        self.log.info("Encerrando GilleVoz.")
        self._sair.set()  # bloqueia novas gravações e novas colagens
        if self.hotkey:
            try:
                self.hotkey.stop()
            except Exception:
                self.log.debug("Erro ao parar o atalho", exc_info=True)
        with self._lock:
            try:
                if self.estado == "gravando":
                    self.recorder.cancel()
            except Exception:
                pass
        # Espera a transcrição em andamento (para salvar no histórico) e, principalmente,
        # o trecho que mexe na área de transferência terminar de restaurar o conteúdo original.
        t = self._thread_transcricao
        if t is not None and t.is_alive():
            self.log.info("Aguardando a transcrição em andamento terminar...")
            t.join(30)
        if self._colagem_lock.acquire(timeout=10):
            self._colagem_lock.release()
        else:
            self.log.warning("Colagem ainda em andamento ao sair; a área de transferência pode não ter sido restaurada.")
        self._parar_barra_com_seguranca(self.barra)
        for parte in (self.tray, self.indicator):
            if parte is None:
                continue
            try:
                parte.stop()
            except Exception:
                self.log.debug("Erro ao parar %s", parte, exc_info=True)


# ---------------------------------------------------------------- modos de linha de comando
def testar_wav(caminho: str, colar: bool = False, atraso: float = 3.0) -> int:
    from .audio import carregar_wav
    from .transcriber import Transcriber

    lg = setup_logging()
    cfg = load_config()
    t0 = time.perf_counter()
    tr = Transcriber(cfg)
    lg.info("Carga do modelo: %.1f s (%s, %s, %s)", time.perf_counter() - t0,
            tr.modelo_efetivo, tr.device_efetivo, tr.compute_type_efetivo)
    audio = carregar_wav(caminho)
    duracao = len(audio) / 16000.0
    t1 = time.perf_counter()
    texto = tr.transcrever(audio)
    dt = time.perf_counter() - t1
    lg.info("TESTE %s: áudio %.1f s | transcrição %.2f s | %.1fx tempo real | device_efetivo=%s | modelo=%s",
            os.path.basename(caminho), duracao, dt, (duracao / dt) if dt > 0 else 0,
            tr.device_efetivo, tr.modelo_efetivo)
    lg.info("TEXTO: %s", texto)
    print(texto, flush=True)
    if texto:
        arq = historico.salvar(texto, duracao, dt)
        lg.info("Salvo no histórico: %s", arq)
        if colar:
            lg.info("Colando em %.1f s na janela em foco...", atraso)
            time.sleep(atraso)
            paste.colar(texto, metodo=cfg.get("metodo_colagem", "clipboard"),
                        auto_enter=bool(cfg.get("auto_enter", False)),
                        espaco_final=bool(cfg.get("espaco_final", True)))
            lg.info("Colado.")
    return 0


def baixar_modelo() -> int:
    from .transcriber import Transcriber

    lg = setup_logging()
    cfg = load_config()
    t0 = time.perf_counter()
    tr = Transcriber(cfg)
    lg.info("Modelo baixado e pronto: %s em %s (%.1f s).", tr.modelo_efetivo, tr.device_efetivo,
            time.perf_counter() - t0)
    print(f"OK: {tr.modelo_efetivo} em {tr.device_efetivo}", flush=True)
    return 0
