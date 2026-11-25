from pathlib import Path

import numpy as np
import pytest

from gillevoz.audio import carregar_wav
from gillevoz.transcriber import Transcriber, montar_prompt

WAV = Path(__file__).resolve().parent.parent / "testes_audio" / "fala20s.wav"


def test_prompt_so_vocabulario():
    assert montar_prompt(["A", "B"], "") == "A, B."


def test_prompt_vazio():
    assert montar_prompt([], "") is None


def test_prompt_com_confirmado_curto():
    assert montar_prompt(["A"], "olá mundo") == "A. olá mundo"


def test_prompt_corta_comeco_do_confirmado():
    p = montar_prompt(["A"], "x" * 1000, limite=100)
    assert len(p) <= 100
    assert p.startswith("A.")


def test_prompt_corta_vocabulario_no_fim():
    p = montar_prompt(["abcdefghij"] * 5, "texto", limite=20)
    assert len(p) <= 20
    assert p.startswith("abcdefghij")


@pytest.mark.gpu
def test_transcrever_palavras_gpu():
    if not WAV.exists():
        pytest.skip("testes_audio/fala20s.wav ausente")
    try:
        t = Transcriber({"dispositivo": "cuda"})
    except Exception as e:  # pragma: no cover
        pytest.skip(f"modelo/CUDA indisponível: {e}")
    if t.device_efetivo != "cuda":
        pytest.skip("CUDA indisponível")
    palavras = t.transcrever_palavras(carregar_wav(WAV)[: 16000 * 8])
    assert palavras
    inicios = [p[1] for p in palavras]
    assert inicios == sorted(inicios)
    assert all(fim >= ini for _, ini, fim in palavras)
    print(palavras[:8])
