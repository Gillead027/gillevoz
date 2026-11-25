from gillevoz.texto import (
    achar_gatilho, aplicar_trocas, maior_k, normalizar, tirar_comando_enter,
)


def test_normalizar_minusculas_sem_pontuacao_nas_pontas():
    assert normalizar("Código.") == "código"
    assert normalizar("¿Olá?") == "olá"


def test_troca_de_varias_palavras_mantem_pontuacao_final():
    trocas = [{"de": "cloud code", "para": "Claude Code"}]
    assert aplicar_trocas(["eu", "uso", "cloud", "code."], trocas) == ["eu", "uso", "Claude", "Code."]


def test_troca_de_uma_palavra_ignora_maiusculas():
    assert aplicar_trocas(["Maestre"], [{"de": "maestre", "para": "Maestri"}]) == ["Maestri"]


def test_troca_sem_correspondencia_nao_altera():
    assert aplicar_trocas(["oi", "gente"], [{"de": "cloud code", "para": "x"}]) == ["oi", "gente"]


def test_achar_gatilho_no_fim():
    atalhos = [{"gatilho": "meu pix", "texto": "Chave: 123"}]
    assert achar_gatilho(["manda", "meu", "pix"], atalhos) == (2, "Chave: 123")
    assert achar_gatilho(["manda", "meu", "Pix."], atalhos) == (2, "Chave: 123")


def test_achar_gatilho_inexistente():
    assert achar_gatilho(["oi"], [{"gatilho": "meu pix", "texto": "x"}]) is None


def test_achar_gatilho_mais_longo_vence():
    atalhos = [{"gatilho": "pix", "texto": "curto"}, {"gatilho": "meu pix", "texto": "longo"}]
    assert achar_gatilho(["meu", "pix"], atalhos) == (2, "longo")


def test_maior_k():
    assert maior_k([{"de": "a b c", "para": "x"}], [{"gatilho": "d e", "texto": "y"}]) == 3
    assert maior_k([], []) == 1


def test_tirar_comando_enter():
    assert tirar_comando_enter("Bom dia, pressione Enter.") == ("Bom dia,", True)
    assert tirar_comando_enter("enter no meio") == ("enter no meio", False)
    assert tirar_comando_enter("pressione enter") == ("", True)
