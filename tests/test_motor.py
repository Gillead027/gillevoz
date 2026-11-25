"""Motor sem janela: fluxo iniciar/parar, tempo real e protocolo, tudo com fakes.

Nada aqui abre microfone, registra atalho global, mexe na área de transferência ou
digita na janela do usuário.
"""
import copy
import io
import json
import threading
import time

import numpy as np
import pytest

from gillevoz import config, historico, motor, protocolo

SR = 16000


class RecorderFalso:
    """Áudio scriptado: `amostras` cresce com o tempo, como um microfone de verdade."""

    def __init__(self, erro_ao_iniciar=None):
        self.erro_ao_iniciar = erro_ao_iniciar
        self.gravando = False
        self.cancelado = False
        self._t0 = 0.0

    def start(self):
        if self.erro_ao_iniciar:
            raise self.erro_ao_iniciar
        self._t0 = time.monotonic()
        self.gravando = True

    def _total(self):
        return int(max(1.0, time.monotonic() - self._t0) * SR)

    def amostras(self, desde=0):
        return np.zeros(max(0, self._total() - desde), dtype=np.float32)

    def stop(self):
        self.gravando = False
        return np.zeros(self._total(), dtype=np.float32)

    def cancel(self):
        self.gravando = False
        self.cancelado = True

    def nivel(self):
        return 0.5 if self.gravando else 0.0


class TranscriberFalso:
    """Devolve hipóteses de uma lista; a última se repete (inclusive na leitura final)."""

    def __init__(self, hipoteses=None, texto=""):
        self.hipoteses = [list(h) for h in (hipoteses or [[]])]
        self.texto = texto
        self.chamadas = 0
        self.vocab = []

    def transcrever_palavras(self, audio, confirmado=""):
        i = min(self.chamadas, len(self.hipoteses) - 1)
        self.chamadas += 1
        return [(p, n * 0.5, n * 0.5 + 0.4) for n, p in enumerate(self.hipoteses[i])]

    def transcrever(self, audio):
        return self.texto


class Ambiente:
    def __init__(self, cfg=None, hipoteses=None, texto="", erro_mic=None):
        self.cfg = copy.deepcopy(config.DEFAULTS)
        self.cfg["bips"] = False
        self.cfg.update(cfg or {})
        self.saida = io.BytesIO()
        self.digitado = ""
        self.apagados = []
        self.colagens = []
        self.enters = 0
        self.recorders = []
        self.transcriber = TranscriberFalso(hipoteses, texto)
        self.erro_mic = erro_mic
        self.motor = motor.Motor(
            self.cfg, protocolo.Canal(self.saida),
            criar_recorder=self._criar_recorder,
            transcriber=self.transcriber,
            digitar=self._digitar,
            apagar=self.apagados.append,
            colar=self._colar,
            enviar_enter=self._enter,
            intervalo_tr=0.02,
        )
        self.motor.espera_erro = 0.05

    def _criar_recorder(self):
        r = RecorderFalso(self.erro_mic)
        self.recorders.append(r)
        return r

    def _digitar(self, texto):
        self.digitado += texto

    def _colar(self, texto, **kw):
        self.colagens.append((texto, kw))

    def _enter(self):
        self.enters += 1

    def mensagens(self, tipo=None):
        msgs = [json.loads(linha) for linha in self.saida.getvalue().decode("utf-8").splitlines()]
        return [m for m in msgs if tipo is None or m["tipo"] == tipo]

    def estados(self):
        return [m["estado"] for m in self.mensagens("estado")]


def esperar(cond, timeout=3.0):
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.01)
    return False


def threads_tempo_real():
    return [t for t in threading.enumerate() if t.name == "gillevoz-tempo-real" and t.is_alive()]


@pytest.fixture(autouse=True)
def _dados_isolados(dados):
    """Todo teste do motor usa uma pasta de dados temporária (histórico/config)."""
    yield dados


# ------------------------------------------------------------------ ciclo e tempo real
def test_estados_ciclo():
    amb = Ambiente(hipoteses=[["olá", "mundo."]])
    amb.motor.iniciar()
    assert amb.estados()[-1] == "gravando"
    time.sleep(0.1)
    amb.motor.parar()
    assert amb.estados()[-2:] == ["transcrevendo", "ocioso"]
    finais = amb.mensagens("final")
    assert len(finais) == 1
    assert finais[0]["texto"] == "olá mundo."
    assert finais[0]["palavras"] == 2
    assert finais[0]["duracao_audio"] > 0
    assert "tempo_transcricao" in finais[0]
    assert amb.mensagens("historico")[0]["dia"] == time.strftime("%Y-%m-%d")


def test_tempo_real_digita_durante_a_fala():
    amb = Ambiente(hipoteses=[["eu", "vou"], ["eu", "vou", "embora"], ["eu", "vou", "embora", "agora."]])
    amb.motor.iniciar()
    assert esperar(lambda: amb.digitado.startswith("eu")), "nada foi digitado durante a fala"
    amb.motor.parar()
    assert amb.digitado.rstrip() == "eu vou embora agora."
    assert amb.mensagens("final")[-1]["texto"] == "eu vou embora agora."
    assert amb.apagados == []
    assert amb.colagens == []
    assert any(m["confirmado"].startswith("eu") for m in amb.mensagens("parcial"))
    itens = historico.listar()
    assert [i["texto"] for i in itens] == ["eu vou embora agora."]


def test_tempo_real_comando_enter_no_fim():
    amb = Ambiente(hipoteses=[["mande", "isso", "pressione", "enter."]])
    amb.motor.iniciar()
    time.sleep(0.15)
    amb.motor.parar()
    assert "pressione" not in amb.digitado
    assert amb.digitado.rstrip() == "mande isso"
    assert amb.enters == 1
    assert amb.mensagens("final")[-1]["texto"] == "mande isso"


def test_tempo_real_aplica_trocas():
    amb = Ambiente(
        cfg={"trocas": [{"de": "cloud code", "para": "Claude Code"}]},
        hipoteses=[["abre", "o", "cloud", "code", "agora."]],
    )
    amb.motor.iniciar()
    time.sleep(0.15)
    amb.motor.parar()
    assert amb.digitado.rstrip() == "abre o Claude Code agora."


def test_push_cola_no_final():
    amb = Ambiente(texto="eu vou embora agora.", hipoteses=[["não", "deveria", "usar"]])
    amb.motor.iniciar(push=True)
    time.sleep(0.1)
    amb.motor.parar()
    assert amb.digitado == ""
    assert len(amb.colagens) == 1
    texto, kw = amb.colagens[0]
    assert texto == "eu vou embora agora."
    assert kw["espaco_final"] is True
    assert amb.transcriber.chamadas == 0  # push nunca usa tempo real
    assert amb.mensagens("final")[-1]["texto"] == "eu vou embora agora."


def test_tempo_real_desligado_cola_no_final():
    amb = Ambiente(cfg={"tempo_real": False}, texto="tudo certo.")
    amb.motor.iniciar()
    amb.motor.parar()
    assert amb.digitado == ""
    assert [c[0] for c in amb.colagens] == ["tudo certo."]


def test_push_comando_enter_vira_auto_enter():
    amb = Ambiente(texto="manda pressione enter.")
    amb.motor.iniciar(push=True)
    amb.motor.parar()
    texto, kw = amb.colagens[0]
    assert texto == "manda"
    assert kw["auto_enter"] is True


# ------------------------------------------------------------------ Review Focus
def test_microfone_indisponivel():
    amb = Ambiente(erro_mic=OSError("dispositivo ocupado"))
    amb.motor.iniciar()
    erros = [m for m in amb.mensagens("estado") if m["estado"] == "erro"]
    assert erros and "Microfone" in erros[0]["msg"]
    assert esperar(lambda: amb.estados()[-1] == "ocioso")
    assert amb.motor.estado == "ocioso"


@pytest.mark.parametrize("push", [False, True])
@pytest.mark.parametrize("fala", [[], ["Obrigado."], ["..."], ["Legendas", "pela", "comunidade", "Amara.org"]])
def test_silencio_nao_digita(push, fala):
    amb = Ambiente(hipoteses=[fala], texto=" ".join(fala))
    amb.motor.iniciar(push=push)
    time.sleep(0.1)
    amb.motor.parar()
    assert amb.digitado == ""
    assert amb.colagens == []
    assert amb.mensagens("final") == []
    assert historico.listar() == []
    assert amb.estados()[-1] == "ocioso"


def test_parar_imediato_e_cliques_rapidos():
    amb = Ambiente(hipoteses=[["um", "dois."]], texto="um dois.")
    amb.motor.iniciar()
    time.sleep(0.1)
    amb.motor.parar()
    amb.motor.iniciar()
    amb.motor.iniciar()
    amb.motor.parar()
    amb.motor.parar()
    assert len(amb.mensagens("final")) == 2
    assert esperar(lambda: not threads_tempo_real())
    assert amb.motor.estado == "ocioso"


def test_cancelar_nao_digita_nem_salva():
    amb = Ambiente(hipoteses=[["a", "b", "c"]])
    amb.motor.iniciar()
    amb.motor.cancelar()
    assert amb.estados()[-1] == "ocioso"
    assert amb.recorders[-1].cancelado
    assert amb.mensagens("final") == []
    assert not threads_tempo_real()


def test_cancelar_durante_o_bip_de_inicio(monkeypatch):
    # Esc chegando enquanto o início ainda está terminando: nada fica gravando.
    amb = Ambiente(cfg={"bips": True})
    monkeypatch.setattr(motor, "bip", lambda tipo: amb.motor.cancelar() if tipo == "inicio" else None)
    amb.motor.iniciar()
    assert amb.motor.estado == "ocioso"
    assert amb.recorders[-1].cancelado
    assert not threads_tempo_real()


def test_silenciar_pc_restaura_sempre(monkeypatch):
    chamadas = []

    class SilenciadorFalso:
        def silenciar(self):
            chamadas.append("silenciar")

        def restaurar(self):
            chamadas.append("restaurar")

    monkeypatch.setattr(motor.som, "Silenciador", SilenciadorFalso)
    amb = Ambiente(cfg={"silenciar_pc": True}, hipoteses=[["oi."]])
    amb.motor.iniciar()
    amb.motor.cancelar()
    amb.motor.iniciar()
    amb.motor.parar()
    assert chamadas == ["silenciar", "restaurar", "silenciar", "restaurar"]


def test_pausado_nao_grava():
    amb = Ambiente()
    amb.motor.tratar({"tipo": "pausar"})
    assert amb.estados()[-1] == "pausado"
    amb.motor.iniciar()
    assert amb.recorders == []
    amb.motor.tratar({"tipo": "retomar"})
    assert amb.estados()[-1] == "ocioso"


# ------------------------------------------------------------------ config e consultas
def test_salvar_config_atalho_invalido():
    amb = Ambiente()
    anterior = amb.motor.cfg["atalho"]
    amb.motor.tratar({"tipo": "salvar_config", "cfg": {"atalho": "ctrl", "bips": True}})
    logs = amb.mensagens("log")
    assert logs and logs[0]["nivel"] == "erro"
    assert amb.motor.cfg["atalho"] == anterior
    assert amb.motor.cfg["bips"] is True  # o resto foi salvo
    assert config.load_config()["atalho"] == anterior
    assert amb.mensagens("config")[-1]["cfg"]["atalho"] == anterior


@pytest.mark.parametrize("valor", [123, "ctrl+shift", ""])
def test_salvar_config_atalho_opcional_invalido(valor):
    amb = Ambiente()
    amb.motor.tratar({"tipo": "salvar_config", "cfg": {"atalho_push": valor}})
    assert amb.mensagens("log")[0]["nivel"] == "erro"
    assert amb.motor.cfg["atalho_push"] is None


def test_salvar_config_atalho_repetido():
    amb = Ambiente()
    amb.motor.tratar({"tipo": "salvar_config", "cfg": {"atalho_push": "Ctrl+Shift+Space"}})
    assert amb.mensagens("log")[0]["nivel"] == "erro"
    assert amb.motor.cfg["atalho_push"] is None


def test_salvar_config_registro_falho_mantem_anterior():
    amb = Ambiente()
    registrados = []

    class AcaoFalsa:
        def __init__(self, atalho, on_apertar):
            self.atalho = atalho

        def start(self):
            if self.atalho == "ctrl+alt+x":
                raise OSError("atalho já em uso")
            registrados.append(self.atalho)

        def stop(self):
            registrados.remove(self.atalho)

    amb.motor._criar_acao = AcaoFalsa
    amb.motor._criar_hotkey = lambda *a, **k: pytest.fail("não deveria re-registrar o atalho principal")
    amb.motor._atalhos_ativos = True
    amb.motor.tratar({"tipo": "salvar_config", "cfg": {"atalho_colar_ultima": "ctrl+alt+v"}})
    assert registrados == ["ctrl+alt+v"]
    amb.motor.tratar({"tipo": "salvar_config", "cfg": {"atalho_colar_ultima": "ctrl+alt+x"}})
    assert amb.mensagens("log")[-1]["nivel"] == "erro"
    assert registrados == ["ctrl+alt+v"]
    assert amb.motor.cfg["atalho_colar_ultima"] == "ctrl+alt+v"
    assert config.load_config()["atalho_colar_ultima"] == "ctrl+alt+v"


def test_salvar_config_modelo_recarrega_so_quando_muda():
    amb = Ambiente()
    recargas = []
    amb.transcriber.recarregar = lambda cfg: recargas.append(cfg["modelo"])
    amb.motor.tratar({"tipo": "salvar_config", "cfg": {"bips": True}})
    amb.motor.aguardar()
    assert recargas == []
    amb.motor.tratar({"tipo": "salvar_config", "cfg": {"modelo": "small"}})
    amb.motor.aguardar()
    assert recargas == ["small"]


def test_salvar_config_durante_gravacao_recarrega_depois():
    amb = Ambiente(hipoteses=[["oi."]])
    recargas = []
    amb.transcriber.recarregar = lambda cfg: recargas.append(cfg["dispositivo"])
    amb.motor.iniciar()
    amb.motor.tratar({"tipo": "salvar_config", "cfg": {"dispositivo": "cpu"}})
    amb.motor.aguardar()
    assert recargas == []
    amb.motor.parar()
    amb.motor.aguardar()
    assert recargas == ["cpu"]


def test_consultas_com_id():
    amb = Ambiente()
    amb.motor.tratar({"tipo": "estatisticas", "id": 7})
    r = amb.mensagens("estatisticas_resposta")[0]
    assert r["id"] == 7
    assert r["ditados_total"] == 0 and "palavras_hoje" in r
    amb.motor.tratar({"tipo": "ler_config", "id": "a"})
    r = amb.mensagens("ler_config_resposta")[0]
    assert r["id"] == "a" and r["cfg"]["atalho"] == amb.motor.cfg["atalho"]
    historico.salvar("primeiro ditado", 1.0, 0.1)
    amb.motor.tratar({"tipo": "listar_historico", "id": 3})
    r = amb.mensagens("listar_historico_resposta")[0]
    assert r["id"] == 3 and r["dia"] == time.strftime("%Y-%m-%d")
    assert r["itens"][0]["texto"] == "primeiro ditado" and r["dias"] == [r["dia"]]


def test_listar_microfones(monkeypatch):
    amb = Ambiente()
    monkeypatch.setattr(motor, "_dispositivos_entrada", lambda: [{"indice": 1, "nome": "Mic USB"}])
    amb.motor.tratar({"tipo": "listar_microfones", "id": 9})
    r = amb.mensagens("listar_microfones_resposta")[0]
    assert r == {"tipo": "listar_microfones_resposta", "id": 9, "itens": [{"indice": 1, "nome": "Mic USB"}]}


def test_colar_ultima_usa_o_ultimo_texto():
    amb = Ambiente(hipoteses=[["texto", "oficial."]])
    amb.motor.iniciar()
    amb.motor.parar()
    amb.motor.colar_ultima()
    assert amb.colagens[-1][0] == "texto oficial."


def test_rodar_termina_no_sair_e_ignora_lixo():
    amb = Ambiente()
    entrada = io.StringIO('lixo\n{"tipo": "estatisticas", "id": 1}\n{"tipo": "sair"}\n{"tipo": "estatisticas", "id": 2}\n')
    amb.motor.rodar(entrada)
    assert [m["id"] for m in amb.mensagens("estatisticas_resposta")] == [1]


def test_comando_desconhecido_responde_log():
    amb = Ambiente()
    amb.motor.tratar({"tipo": "voar"})
    assert amb.mensagens("log")[0]["nivel"] == "aviso"
