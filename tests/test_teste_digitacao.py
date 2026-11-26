"""Guardas de segurança do harness tools/teste_digitacao.py (só fakes: nenhuma janela real)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import teste_digitacao as td  # noqa: E402


def _tabstate(raiz, arquivos):
    pasta = raiz / "Packages" / "Microsoft.WindowsNotepad_8wekyb3d8bbwe" / "LocalState" / "TabState"
    pasta.mkdir(parents=True)
    for nome in arquivos:
        (pasta / nome).write_bytes(b"x")
    return pasta


def test_abas_salvas_detecta_tabstate(tmp_path):
    assert td.abas_salvas_do_bloco(str(tmp_path)) == []
    _tabstate(tmp_path, [])
    assert td.abas_salvas_do_bloco(str(tmp_path)) == []
    _tabstate(tmp_path / "outro", ["a.bin", "a.0.bin"])
    assert len(td.abas_salvas_do_bloco(str(tmp_path / "outro"))) == 2


@pytest.fixture
def sem_janelas(monkeypatch):
    """Tudo que tocaria janelas reais vira falha do teste."""
    proibido = lambda *a, **k: pytest.fail("mexeu numa janela real")  # noqa: E731
    monkeypatch.setattr(td, "focar", proibido)
    monkeypatch.setattr(td, "atalho", proibido)
    monkeypatch.setattr(td, "tecla", proibido)
    monkeypatch.setattr(td.user32, "PostMessageW", proibido)
    monkeypatch.setattr(td, "_bloco_aberto", lambda: False)
    abertos = []
    monkeypatch.setattr(td.subprocess, "Popen", lambda args, **k: abertos.append(args))
    monkeypatch.setattr(td, "achar_janela", lambda titulo, timeout=20.0: 0xABC)
    monkeypatch.setattr(td.time, "sleep", lambda s: None)
    return abertos


def test_recusa_com_abas_guardadas_sem_abrir_nada(sem_janelas, monkeypatch):
    monkeypatch.setattr(td, "abas_salvas_do_bloco", lambda: [Path("x.bin")])
    b = td.BlocoDeNotas()
    with pytest.raises(RuntimeError, match="guardada"):
        b.abrir()
    assert sem_janelas == []
    b.fechar()  # não mexe em nada


def test_janela_com_outras_abas_nao_e_tocada_nem_fechada(sem_janelas, monkeypatch):
    monkeypatch.setattr(td, "abas_salvas_do_bloco", lambda: [])
    monkeypatch.setattr(td, "contar_abas", lambda hwnd: 5)
    b = td.BlocoDeNotas()
    with pytest.raises(RuntimeError, match="5 abas"):
        b.abrir()
    assert len(sem_janelas) == 1  # só abriu o Bloco de Notas
    b.fechar()  # intocável: nada de foco, teclas ou WM_CLOSE
    b.arquivo.unlink()
    b.pasta.rmdir()


def test_fechar_confere_abas_de_novo(sem_janelas, monkeypatch):
    monkeypatch.setattr(td, "abas_salvas_do_bloco", lambda: [])
    abas = {"n": 1}
    monkeypatch.setattr(td, "contar_abas", lambda hwnd: abas["n"])
    monkeypatch.setattr(td, "focar", lambda j: None)
    b = td.BlocoDeNotas()
    b.abrir()
    abas["n"] = 2  # alguém abriu outra aba durante o teste
    with pytest.raises(RuntimeError, match="outras abas"):
        b.fechar()
    b.arquivo.unlink()
    b.pasta.rmdir()
