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


def test_amostras_sem_parar():
    recorder = Recorder()
    recorder._chunks = [np.array([0, 1, 2], dtype=np.float32), np.array([3, 4], dtype=np.float32)]
    recorder.gravando = True
    parte = recorder.amostras(2)
    assert parte.tolist() == [2, 3, 4]
    assert recorder.gravando
    assert recorder.amostras().tolist() == [0, 1, 2, 3, 4]
    parte[0] = 99  # é cópia
    assert recorder._chunks[0][2] == 2


def _wav_de_teste(tmp_path, segundos=1.0):
    import wave

    x = (np.sin(np.linspace(0, 2000, int(16000 * segundos))) * 0.3 * 32767).astype("<i2")
    caminho = tmp_path / "t.wav"
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(x.tobytes())
    return caminho


def test_recorder_wav(tmp_path):
    from gillevoz.audio import RecorderWav, carregar_wav

    caminho = _wav_de_teste(tmp_path)
    r = RecorderWav(str(caminho), tempo_real=False)
    r.start()
    assert r.gravando
    assert r.amostras(100).shape == (15900,)
    assert r.nivel() > 0
    audio = r.stop()
    assert not r.gravando
    assert audio.shape == (16000,)
    assert r.samplerate == 16000
    assert np.allclose(audio, carregar_wav(caminho))


def test_recorder_wav_tempo_real_para_com_stop(tmp_path):
    import time

    from gillevoz.audio import RecorderWav

    r = RecorderWav(str(_wav_de_teste(tmp_path, 2.0)), tempo_real=True)
    r.start()
    time.sleep(0.3)
    parcial = r.amostras()
    assert 0 < parcial.size < 32000
    audio = r.stop()
    assert r._thread is None or not r._thread.is_alive()
    assert audio.size < 32000
    time.sleep(0.2)
    assert r.amostras().size == 0
