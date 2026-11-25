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


def test_palavras_junta_continuacao_sem_espaco():
    """Token do Whisper sem espaço no começo continua a palavra anterior ("front" + "-end")."""
    from types import SimpleNamespace as NS

    palavras = [(" front", 0.0, 0.4), ("-end", 0.4, 0.7), (" e", 0.8, 0.9),
                (" back", 1.0, 1.3), ("-end.", 1.3, 1.6)]
    segmento = NS(words=[NS(word=w, start=a, end=b) for w, a, b in palavras])

    class ModeloFalso:
        def transcribe(self, audio, **kw):
            return iter([segmento]), None

    tr = Transcriber.__new__(Transcriber)
    tr.model, tr.idioma, tr.vocab, tr.device_efetivo = ModeloFalso(), "pt", [], "cpu"
    r = tr.transcrever_palavras(np.zeros(16000, dtype=np.float32))
    assert [p for p, _, _ in r] == ["front-end", "e", "back-end."]
    assert r[0][1:] == (0.0, 0.7)
    assert r[2][1:] == (1.0, 1.6)


def test_palavras_nao_junta_atravessando_segmentos():
    """O 1º token de um segmento sem espaço é palavra nova, não continuação do segmento anterior."""
    from types import SimpleNamespace as NS

    def seg(*ws):
        return NS(words=[NS(word=w, start=a, end=b) for w, a, b in ws])

    segmentos = [seg((" Gillezin.", 2.0, 2.6)), seg(("Quero", 2.8, 3.1), (" que", 3.1, 3.3))]

    class ModeloFalso:
        def transcribe(self, audio, **kw):
            return iter(segmentos), None

    tr = Transcriber.__new__(Transcriber)
    tr.model, tr.idioma, tr.vocab, tr.device_efetivo = ModeloFalso(), "pt", [], "cpu"
    r = tr.transcrever_palavras(np.zeros(16000, dtype=np.float32))
    assert [p for p, _, _ in r] == ["Gillezin.", "Quero", "que"]
    assert r[1][1:] == (2.8, 3.1)
