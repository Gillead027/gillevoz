import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from gillevoz.audio import Recorder


def test_cinco_minutos_em_blocos_sem_perda():
    recorder = Recorder()
    bloco = np.full((1600, 1), .25, dtype=np.float32)
    for _ in range(3000):
        recorder._callback(bloco, len(bloco), None, None)
    assert sum(chunk.nbytes for chunk in recorder._chunks) == 19_200_000
    audio = recorder.stop()
    assert audio.shape == (300 * 16000,)
    assert audio.dtype == np.float32
    assert np.all(audio == .25)
    assert recorder._chunks == []


def test_cancel_descarta_audio():
    recorder = Recorder()
    recorder._callback(np.ones((1600, 1), dtype=np.float32), 1600, None, None)
    recorder.cancel()
    assert recorder.stop().size == 0


def test_stream_fechado_se_start_falhar(monkeypatch):
    stream = Mock()
    stream.start.side_effect = RuntimeError('microfone desconectado')
    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(InputStream=lambda **kw: stream))
    recorder = Recorder()
    with pytest.raises(RuntimeError):
        recorder.start()
    stream.close.assert_called_once()
    assert recorder._stream is None
    assert not recorder.gravando


def test_stream_fechado_mesmo_se_stop_falhar():
    stream = Mock()
    stream.stop.side_effect = RuntimeError('dispositivo removido')
    recorder = Recorder()
    recorder._stream = stream
    recorder.gravando = True
    recorder.cancel()
    stream.close.assert_called_once()
    assert not recorder.gravando
