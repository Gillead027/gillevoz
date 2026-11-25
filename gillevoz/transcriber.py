"""Transcrição local com faster-whisper (GPU com fallback automático para CPU)."""
from __future__ import annotations

import logging
import time

import numpy as np

from .cuda_dlls import registrar_dlls_cuda

log = logging.getLogger("gillevoz")


def _carregar_modelo(nome: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel

    # Primeiro tenta só o cache local (o app não usa internet depois de baixar o modelo).
    try:
        return WhisperModel(nome, device=device, compute_type=compute_type, local_files_only=True)
    except Exception as e_local:
        msg = str(e_local).lower()
        # Erro de CUDA/DLL não se resolve baixando de novo: propaga.
        if any(k in msg for k in ("cuda", "cublas", "cudnn", "dll", "device")):
            raise
        log.info("Modelo %s não está no cache local; baixando (só desta vez)...", nome)
        return WhisperModel(nome, device=device, compute_type=compute_type)


class Transcriber:
    """Carrega o modelo uma vez e mantém na memória.

    Atributos: device_efetivo ("cuda"|"cpu"), modelo_efetivo, compute_type_efetivo.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.idioma = cfg.get("idioma", "pt")
        vocab = cfg.get("vocabulario") or []
        self.initial_prompt = ", ".join(vocab) + "." if vocab else None
        self.model = None
        self.device_efetivo = None
        self.modelo_efetivo = None
        self.compute_type_efetivo = None

        dispositivo = cfg.get("dispositivo", "cuda")
        t0 = time.perf_counter()
        if dispositivo == "cuda":
            try:
                registrar_dlls_cuda()
                self._usar(cfg.get("modelo", "large-v3-turbo"), "cuda", cfg.get("compute_type", "float16"))
                self._aquecer()
            except Exception as e:
                log.warning(
                    "CUDA falhou (%s: %s). Caindo para CPU com modelo '%s'/int8 — vai ficar mais lento.",
                    type(e).__name__, e, cfg.get("modelo_cpu", "small"),
                )
                self._fallback_cpu()
        else:
            self._fallback_cpu()
        log.info(
            "Modelo pronto: %s em %s (%s) em %.1f s",
            self.modelo_efetivo, self.device_efetivo, self.compute_type_efetivo, time.perf_counter() - t0,
        )

    def _usar(self, nome: str, device: str, compute_type: str) -> None:
        self.model = None
        self.model = _carregar_modelo(nome, device, compute_type)
        self.device_efetivo = device
        self.modelo_efetivo = nome
        self.compute_type_efetivo = compute_type

    def _fallback_cpu(self) -> None:
        self._usar(self.cfg.get("modelo_cpu", "small"), "cpu", "int8")
        self._aquecer()

    def _aquecer(self) -> None:
        # 1 s de ruído baixo, sem VAD, força a inicialização real dos kernels (cuDNN etc.).
        rng = np.random.default_rng(0)
        audio = (rng.standard_normal(16000) * 0.01).astype(np.float32)
        segs, _ = self.model.transcribe(audio, language=self.idioma, beam_size=1, vad_filter=False)
        for _ in segs:
            pass

    def _rodar(self, audio: np.ndarray) -> str:
        segs, _info = self.model.transcribe(
            audio,
            language=self.idioma,
            vad_filter=True,
            initial_prompt=self.initial_prompt,
            beam_size=5,
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segs).strip()

    def transcrever(self, audio: np.ndarray) -> str:
        """Recebe float32 mono 16 kHz e devolve o texto (pode ser vazio)."""
        if audio is None or len(audio) < 1600:  # < 0,1 s
            return ""
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        try:
            return self._rodar(audio)
        except Exception as e:
            if self.device_efetivo != "cuda":
                raise
            log.error("Erro na GPU durante a transcrição (%s); recarregando na CPU.", e)
            self._fallback_cpu()
            return self._rodar(audio)
