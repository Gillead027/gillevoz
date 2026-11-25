"""Testes da concordância (palavras confirmadas) e do digitador do tempo real."""
from gillevoz.tempo_real import Concordancia, Digitador


def test_confirma_so_quando_duas_leituras_concordam():
    c = Concordancia()
    assert c.alimentar(["eu", "vou"]) == []
    assert c.alimentar(["eu", "vou", "no"]) == ["eu", "vou"]
    assert c.alimentar(["eu", "vou", "na", "feira"]) == []
    assert c.alimentar(["eu", "vou", "na", "feira", "hoje"]) == ["na", "feira"]


def test_nunca_desconfirma():
    c = Concordancia()
    c.alimentar(["eu", "vou"])
    c.alimentar(["eu", "vou", "no"])
    assert c.alimentar(["eu", "fui"]) == []
    assert c.confirmadas == ["eu", "vou"]


def test_finalizar_devolve_resto():
    c = Concordancia()
    c.alimentar(["eu", "vou"])
    c.alimentar(["eu", "vou", "embora."])
    assert c.confirmadas == ["eu", "vou"]
    assert c.finalizar(["eu", "vou", "embora."]) == ["embora."]


def test_nova_janela():
    c = Concordancia()
    c.alimentar(["eu", "vou"])
    c.alimentar(["eu", "vou", "no"])
    c.nova_janela()
    assert c.alimentar(["hoje"]) == []
    assert c.alimentar(["hoje", "sim"]) == ["hoje"]
    assert c.confirmadas == ["eu", "vou", "hoje"]


def _digitador(trocas=(), atalhos=()):
    chamadas = {"digitar": [], "apagar": []}
    d = Digitador(chamadas["digitar"].append, chamadas["apagar"].append, list(trocas), list(atalhos))
    return d, chamadas


def test_digitador_segura_k_palavras():
    d, _ = _digitador(trocas=[{"de": "um dois", "para": "x"}])
    d.receber(["a", "b", "c"])
    assert d.texto == "a"
    d.descarregar()
    assert d.texto == "a b c"


def test_digitador_troca_antes_de_digitar():
    d, ch = _digitador(trocas=[{"de": "cloud code", "para": "Claude Code"}])
    d.receber(["uso", "cloud"])
    d.receber(["code", "agora"])
    d.descarregar()
    assert d.texto == "uso Claude Code agora"
    assert "".join(ch["digitar"]) == d.texto
    assert ch["apagar"] == []


def test_digitador_gatilho():
    d, ch = _digitador(atalhos=[{"gatilho": "meu pix", "texto": "Chave: 123"}])
    d.receber(["meu", "pix"])
    d.descarregar()
    assert d.texto == "Chave: 123"
    assert "".join(ch["digitar"]) == d.texto
    assert ch["apagar"] == []


def test_digitador_texto_igual_ao_digitado():
    d, ch = _digitador()
    d.receber(["a"])
    d.descarregar()
    d.receber(["b"])
    d.descarregar()
    assert d.texto == "a b" == "".join(ch["digitar"])


def test_gatilho_no_meio_do_lote():
    d, ch = _digitador(atalhos=[{"gatilho": "meu pix", "texto": "Chave: 123"}])
    d.receber(["meu", "pix", "agora"])
    d.descarregar()
    assert d.texto == "Chave: 123 agora"
    assert "".join(ch["digitar"]) == d.texto
    assert ch["apagar"] == []


def test_gatilho_dividido_entre_lotes():
    d, ch = _digitador(atalhos=[{"gatilho": "meu pix", "texto": "Chave: 123"}])
    d.receber(["meu"])
    d.receber(["pix", "agora"])
    d.descarregar()
    assert d.texto == "Chave: 123 agora"
    assert "".join(ch["digitar"]) == d.texto


def test_troca_nao_se_acumula_em_palavras_seguradas():
    d, _ = _digitador(trocas=[{"de": "code", "para": "Claude Code"}])
    d.receber(["code"])
    d.receber(["x"])
    d.receber(["y"])
    d.descarregar()
    assert d.texto == "Claude Code x y"


def test_troca_que_repete_a_palavra():
    d, _ = _digitador(trocas=[{"de": "zap", "para": "zap zap"}])
    d.receber(["zap"])
    d.receber(["a"])
    d.receber(["b"])
    d.descarregar()
    assert d.texto == "zap zap a b"
