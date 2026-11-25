"""Protocolo JSON por linhas entre o motor e a interface."""
import io
import json
import threading

from gillevoz import protocolo


def test_canal_uma_linha_por_mensagem():
    saida = io.BytesIO()
    canal = protocolo.Canal(saida)
    canal.enviar("estado", estado="gravando")
    canal.enviar("final", texto="ação e coração", palavras=3)
    linhas = saida.getvalue().decode("utf-8").splitlines()
    assert len(linhas) == 2
    assert json.loads(linhas[0]) == {"tipo": "estado", "estado": "gravando"}
    assert json.loads(linhas[1])["texto"] == "ação e coração"
    assert "ação e coração" in linhas[1]  # acentos legíveis (ensure_ascii=False)


def test_canal_thread_safe_nao_mistura_linhas():
    saida = io.BytesIO()
    canal = protocolo.Canal(saida)

    def mandar(n):
        for i in range(200):
            canal.enviar("nivel", valor=n, i=i)

    ts = [threading.Thread(target=mandar, args=(n,)) for n in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    linhas = saida.getvalue().decode("utf-8").splitlines()
    assert len(linhas) == 800
    assert all(json.loads(linha)["tipo"] == "nivel" for linha in linhas)


def test_ler_ignora_linhas_invalidas(caplog):
    entrada = io.StringIO(
        '{"tipo": "iniciar"}\n'
        "isto não é json\n"
        "\n"
        '[1, 2]\n'
        '{"sem_tipo": 1}\n'
        '{"tipo": "estatisticas", "id": 7}\n'
    )
    with caplog.at_level("WARNING", logger="gillevoz"):
        cmds = list(protocolo.ler(entrada))
    assert cmds == [{"tipo": "iniciar"}, {"tipo": "estatisticas", "id": 7}]
    assert "inválida" in caplog.text
