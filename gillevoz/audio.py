"""Gravação do microfone (16 kHz mono), bips e leitura de WAV."""
from __future__ import annotations

import logging
import threading
import time
import wave
from pathlib import Path

import numpy as np

log = logging.getLogger("gillevoz")

SAMPLERATE = 16000

# Faixa de volume da fala mapeada para 0..1 no medidor (dBFS do RMS de cada bloco).
NIVEL_DB_MIN = -55.0  # abaixo disso = silêncio/ruído de fundo
NIVEL_DB_MAX = -12.0  # fala alta perto do microfone
NIVEL_SUBIDA = 0.6    # suavização: sobe rápido...
NIVEL_DESCIDA = 0.2   # ...e desce devagar (onda não "pisca")


def nivel_de_bloco(bloco: np.ndarray) -> float:
    """RMS do bloco convertido para 0..1 numa escala logarítmica adequada à fala."""
    if bloco.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(bloco, dtype=np.float64))))
    if rms <= 1e-9:
        return 0.0
    db = 20.0 * np.log10(rms)
    return float(min(1.0, max(0.0, (db - NIVEL_DB_MIN) / (NIVEL_DB_MAX - NIVEL_DB_MIN))))


class Recorder:
    """Grava do microfone em blocos, sem limite de tempo (memória: ~64 KB por segundo)."""

    def __init__(self, samplerate: int = SAMPLERATE, device=None):
        self.samplerate = samplerate
        self.device = device
        self._stream = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self.gravando = False
        self._nivel = 0.0

    def _callback(self, indata, frames, time_info, status):  # roda na thread do PortAudio
        if status:
            log.debug("sounddevice status: %s", status)
        bloco = indata[:, 0].copy()
        alvo = nivel_de_bloco(bloco)
        with self._lock:
            self._chunks.append(bloco)
            fator = NIVEL_SUBIDA if alvo > self._nivel else NIVEL_DESCIDA
            self._nivel += fator * (alvo - self._nivel)

    def nivel(self) -> float:
        """Volume atual 0..1 (RMS do último bloco, suavizado). 0 quando não está gravando."""
        with self._lock:
            return self._nivel if self.gravando else 0.0

    def start(self) -> None:
        import sounddevice as sd

        if self.gravando:
            return
        with self._lock:
            self._chunks = []
            self._nivel = 0.0
        stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=1,
            dtype="float32",
            device=self.device,
            blocksize=0,
            callback=self._callback,
        )
        try:
            stream.start()
        except Exception:
            # Microfone sumiu/ocupado: fecha o stream criado antes de propagar o erro.
            try:
                stream.close()
            except Exception as e:  # pragma: no cover
                log.warning("Erro ao fechar stream de áudio após falha: %s", e)
            self._stream = None
            self.gravando = False
            raise
        self._stream = stream
        self.gravando = True

    def _fechar(self) -> None:
        s, self._stream = self._stream, None
        self.gravando = False
        with self._lock:
            self._nivel = 0.0
        if s is not None:
            try:
                s.stop()
            except Exception as e:
                log.warning("Erro ao parar stream de áudio: %s", e)
            finally:
                try:
                    s.close()
                except Exception as e:
                    log.warning("Erro ao fechar stream de áudio: %s", e)

    def stop(self) -> np.ndarray:
        """Para e devolve o áudio float32 mono."""
        self._fechar()
        with self._lock:
            chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).astype(np.float32, copy=False)

    def cancel(self) -> None:
        """Para e descarta o áudio."""
        self._fechar()
        with self._lock:
            self._chunks = []

    def amostras(self, desde: int = 0) -> np.ndarray:
        """Cópia do áudio gravado até agora, a partir da amostra `desde`, sem parar a gravação."""
        with self._lock:
            chunks = list(self._chunks)
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)[max(0, desde):].astype(np.float32)


class RecorderWav(Recorder):
    """Mesma interface do Recorder, mas alimenta o buffer com um WAV (testes, sem microfone).

    Com tempo_real=True entrega blocos de ~50 ms no ritmo do relógio, numa thread;
    com tempo_real=False o WAV inteiro entra de uma vez no start().
    """

    BLOCO = SAMPLERATE // 20  # 50 ms

    def __init__(self, caminho: str, tempo_real: bool = True):
        super().__init__()
        self.caminho = caminho
        self.tempo_real = tempo_real
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()

    def start(self) -> None:
        if self.gravando:
            return
        audio = carregar_wav(self.caminho)
        with self._lock:
            self._chunks = []
            self._nivel = 0.0
        self._parar = threading.Event()
        self.gravando = True
        if not self.tempo_real:
            for i in range(0, len(audio), self.BLOCO):
                self._alimentar(audio[i:i + self.BLOCO])
            return
        self._thread = threading.Thread(
            target=self._alimentar_no_ritmo, args=(audio, self._parar), daemon=True, name="gillevoz-wav"
        )
        self._thread.start()

    def _alimentar(self, bloco: np.ndarray) -> None:
        self._callback(bloco.reshape(-1, 1), len(bloco), None, None)

    def _alimentar_no_ritmo(self, audio: np.ndarray, parar: threading.Event) -> None:
        t0 = time.monotonic()
        for i in range(0, len(audio), self.BLOCO):
            # espera até o instante em que este bloco "terminaria de ser falado"
            espera = t0 + (i + self.BLOCO) / SAMPLERATE - time.monotonic()
            if parar.wait(max(0.0, espera)):
                return
            self._alimentar(audio[i:i + self.BLOCO])

    def _fechar(self) -> None:
        self._parar.set()
        t, self._thread = self._thread, None
        if t is not None and t is not threading.current_thread():
            t.join(timeout=1.0)
        self.gravando = False
        with self._lock:
            self._nivel = 0.0


_BIPS = {
    "inicio": [(880, 70)],
    "fim": [(660, 70)],
    "erro": [(300, 120), (220, 160)],
}


def bip(tipo: str = "inicio", esperar: bool = False) -> None:
    """Toca um bip curto sem bloquear quem chamou (esperar=True: só volta quando ele acabar)."""
    notas = _BIPS.get(tipo, _BIPS["inicio"])

    def _tocar():
        try:
            import winsound

            for freq, dur in notas:
                winsound.Beep(freq, dur)
        except Exception as e:  # pragma: no cover
            log.debug("bip falhou: %s", e)

    if esperar:
        _tocar()
        return
    threading.Thread(target=_tocar, daemon=True, name="gillevoz-bip").start()


def _reamostrar(x: np.ndarray, sr_origem: int, sr_destino: int = SAMPLERATE) -> np.ndarray:
    if sr_origem == sr_destino or len(x) == 0:
        return x
    n = int(round(len(x) * sr_destino / sr_origem))
    t_orig = np.arange(len(x)) / sr_origem
    t_novo = np.arange(n) / sr_destino
    return np.interp(t_novo, t_orig, x).astype(np.float32)


def carregar_wav(path) -> np.ndarray:
    """Lê um WAV PCM (8/16/24/32 bits, mono ou estéreo) e devolve float32 mono 16 kHz."""
    with wave.open(str(Path(path)), "rb") as w:
        canais = w.getnchannels()
        largura = w.getsampwidth()
        sr = w.getframerate()
        dados = w.readframes(w.getnframes())
    if largura == 1:
        x = (np.frombuffer(dados, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    elif largura == 2:
        x = np.frombuffer(dados, dtype="<i2").astype(np.float32) / 32768.0
    elif largura == 3:
        b = np.frombuffer(dados, dtype=np.uint8).reshape(-1, 3)
        i = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        i = np.where(i & 0x800000, i - 0x1000000, i)
        x = i.astype(np.float32) / 8388608.0
    elif largura == 4:
        x = np.frombuffer(dados, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"WAV com {largura * 8} bits não suportado")
    if canais > 1:
        x = x.reshape(-1, canais).mean(axis=1)
    return _reamostrar(x.astype(np.float32), sr)
