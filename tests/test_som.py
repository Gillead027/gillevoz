"""Silenciar o PC durante o ditado, com um volume falso (não muda o som real)."""
from gillevoz import som


class VolumeFalso:
    def __init__(self, mudo=0):
        self.mudo = mudo
        self.chamadas = []

    def GetMute(self):
        return self.mudo

    def SetMute(self, valor, contexto):
        self.chamadas.append(valor)
        self.mudo = valor


def test_silenciar_e_restaurar(monkeypatch):
    vol = VolumeFalso(mudo=0)
    monkeypatch.setattr(som, "_volume", lambda: vol)
    s = som.Silenciador()
    s.silenciar()
    assert vol.mudo == 1
    s.restaurar()
    assert vol.mudo == 0
    s.restaurar()  # idempotente
    assert vol.chamadas == [1, 0]


def test_nao_desmuta_quem_ja_estava_mudo(monkeypatch):
    vol = VolumeFalso(mudo=1)
    monkeypatch.setattr(som, "_volume", lambda: vol)
    s = som.Silenciador()
    s.silenciar()
    s.restaurar()
    assert vol.mudo == 1


def test_falha_vira_log_nunca_excecao(monkeypatch, caplog):
    def quebra():
        raise OSError("sem placa de som")

    monkeypatch.setattr(som, "_volume", quebra)
    s = som.Silenciador()
    s.silenciar()
    s.restaurar()
    assert "sem placa de som" in caplog.text
