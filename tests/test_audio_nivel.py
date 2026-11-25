"""Recorder.nivel(): 0..1, suavizado, zero fora da gravação, thread-safe."""
import threading

import numpy as np

from gillevoz.audio import Recorder, nivel_de_bloco


def _bloco(db):
    return np.full((1600, 1), 10 ** (db / 20), dtype=np.float32)


def test_faixa_e_limites():
    assert nivel_de_bloco(np.zeros(1600, np.float32)) == 0.0
    assert nivel_de_bloco(_bloco(-70)[:, 0]) == 0.0      # ruído de fundo
    assert nivel_de_bloco(np.ones(1600, np.float32)) == 1.0
    assert 0.3 < nivel_de_bloco(_bloco(-30)[:, 0]) < 0.8  # fala normal no meio da escala


def test_suavizacao_sobe_rapido_desce_devagar_e_zera_parado():
    r = Recorder()
    r.gravando = True
    r._callback(_bloco(-12), 1600, None, None)
    subida = r.nivel()
    assert 0.5 <= subida < 1.0
    r._callback(np.zeros((1600, 1), np.float32), 1600, None, None)
    assert 0.3 < r.nivel() < subida  # cai, mas não despenca de uma vez
    r.gravando = False
    assert r.nivel() == 0.0


def test_leitura_concorrente_sempre_no_intervalo():
    r = Recorder()
    r.gravando = True
    valores, parar = [], threading.Event()

    def ler():
        while not parar.is_set():
            valores.append(r.nivel())

    t = threading.Thread(target=ler)
    t.start()
    rng = np.random.default_rng(0)
    for _ in range(2000):
        r._callback(rng.uniform(-1, 1, (160, 1)).astype(np.float32), 160, None, None)
    parar.set()
    t.join()
    assert valores and all(0.0 <= v <= 1.0 for v in valores)
