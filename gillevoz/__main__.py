"""python -m gillevoz --motor | --testar-wav ARQ [--colar] [--atraso N] | --baixar-modelo"""
import argparse
import io
import logging
import os
import sys


class _EscritorLog(io.TextIOBase):
    """Substitui o sys.stdout no modo --motor: qualquer print vira linha de log."""

    def __init__(self) -> None:
        self._log = logging.getLogger("gillevoz")
        self._pendente = ""

    def writable(self) -> bool:
        return True

    def write(self, texto: str) -> int:
        self._pendente += texto
        *linhas, self._pendente = self._pendente.split("\n")
        for linha in linhas:
            if linha.strip():
                self._log.info("stdout: %s", linha)
        return len(texto)


def _rodar_motor() -> int:
    from . import config

    # Antes de qualquer coisa que crie a pasta de dados (log, config, histórico).
    config.migrar_v1(config.PASTA_V1)

    from . import log as gv_log

    lg = gv_log.setup_logging(console=False)
    # Canal do protocolo numa cópia do stdout original. O fd 1 passa a apontar para o stderr:
    # biblioteca nativa (CUDA, ctranslate2...) que escreve direto no stdout não corrompe o JSON.
    sys.stdout.flush()
    saida = os.fdopen(os.dup(1), "wb")
    try:
        os.dup2(2, 1)
    except OSError as e:
        lg.warning("Não consegui desviar o stdout nativo para o stderr: %s", e)
    sys.stdout = _EscritorLog()
    entrada = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")

    from . import paste, protocolo, startup
    from .audio import Recorder, RecorderWav
    from .motor import Motor

    canal = protocolo.Canal(saida)
    try:
        startup.remover_v1()
        cfg = config.load_config()
        from .transcriber import Transcriber

        transcriber = Transcriber(cfg)
    except Exception as e:
        lg.exception("Não consegui iniciar o motor")
        canal.enviar("estado", estado="erro", msg=f"Erro ao carregar o modelo: {e}")
        return 1

    wav_simulado = os.environ.get("GILLEVOZ_WAV_SIMULADO")
    motor = None

    def criar_recorder():
        if wav_simulado:
            return RecorderWav(wav_simulado, tempo_real=True)
        return Recorder(device=motor.cfg.get("microfone"))

    def digitar(texto: str, parar=None) -> str:
        # Tempo real (com `parar`): espera Ctrl/Shift serem soltos, sem soltar por ele.
        # Entrega final (sem `parar`): se continuarem apertados, solta por ele depois de 0,6 s.
        return paste.digitar(texto, parar, soltar_apos_s=None if parar is not None else 0.6)

    def enviar_enter() -> None:
        paste.soltar_modificadoras()
        paste.enviar_enter()

    motor = Motor(
        cfg, canal,
        criar_recorder=criar_recorder,
        transcriber=transcriber,
        digitar=digitar,
        apagar=paste.apagar,
        colar=paste.colar,
        enviar_enter=enviar_enter,
    )
    if wav_simulado:
        lg.info("Microfone simulado com o WAV %s", wav_simulado)
    canal.enviar("pronto", dispositivo=transcriber.device_efetivo, modelo=transcriber.modelo_efetivo)
    canal.enviar("estado", estado=motor.estado)
    motor.registrar_atalhos()
    lg.info("Motor rodando (atalho %s).", cfg.get("atalho"))
    motor.rodar(entrada)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gillevoz", description="GilleVoz — ditado por voz local")
    p.add_argument("--motor", action="store_true",
                   help="motor sem janela, controlado pela interface via JSON no stdin/stdout")
    p.add_argument("--testar-wav", metavar="ARQ", help="transcreve um WAV, loga os tempos e salva no histórico")
    p.add_argument("--colar", action="store_true", help="com --testar-wav: cola o texto na janela em foco")
    p.add_argument("--atraso", type=float, default=3.0, help="segundos antes de colar (padrão 3)")
    p.add_argument("--baixar-modelo", action="store_true", help="baixa/carrega o modelo e sai")
    a = p.parse_args(argv)

    if a.motor:
        return _rodar_motor()

    from . import app, config

    # --baixar-modelo (pós-instalação) e --testar-wav criam a pasta de dados: migra o v1 antes.
    if a.baixar_modelo or a.testar_wav:
        config.migrar_v1(config.PASTA_V1)
    if a.baixar_modelo:
        return app.baixar_modelo()
    if a.testar_wav:
        return app.testar_wav(a.testar_wav, colar=a.colar, atraso=a.atraso)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
