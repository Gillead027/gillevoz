"""Teste de digitação do tempo real em janelas de verdade (paste.digitar).

Abre janelas PRÓPRIAS (nunca mexe nas que já existem), digita uma frase em pt-BR com
acentos e pontuação, trecho a trecho como o tempo real faz, lê de volta e compara.

  .venv\\Scripts\\python.exe tools\\teste_digitacao.py [--alvos bloco,winforms,edge]
                                                    [--rodadas 3] [--carga]

Alvos:
  bloco    — Bloco de Notas aberto pelo teste com um arquivo temporário (lido por WM_GETTEXT);
             recusa rodar se já houver um Bloco de Notas aberto (não mexe nas abas de ninguém);
  winforms — uma TextBox numa janelinha do PowerShell (lida por WM_GETTEXT);
  edge     — <textarea> de um HTML local no Edge com perfil temporário (lido por
             Ctrl+A/Ctrl+C, com a área de transferência restaurada depois).
--carga ocupa todos os núcleos da CPU durante o teste (o caso em que o Bloco de Notas trocava letras).

Segurança: antes de cada palavra confere se a janela em foco é a do teste; se não for, para
na hora (nada é digitado em outra janela). Não use o PC enquanto roda (~1 min).
"""
from __future__ import annotations

import argparse
import ctypes
import multiprocessing
import os
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from gillevoz import paste  # noqa: E402

FRASE = ("Olá, Gillezin. Quero ação já: coração, pão e maçã! Você está aí? "
         "Não sei... 100% (ok) — é isso, né?")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LPARAM
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
WM_GETTEXT, WM_GETTEXTLENGTH, WM_SETTEXT, WM_CLOSE = 0x000D, 0x000E, 0x000C, 0x0010
GA_ROOT = 2
VK_A, VK_C, VK_S, VK_W, VK_DELETE = 0x41, 0x43, 0x53, 0x57, 0x2E


# ---------------------------------------------------------------- janelas
def _texto_janela(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def _classe(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def achar_janela(parte_titulo: str, timeout: float = 20.0):
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        achadas = []

        def cb(h, _):
            if user32.IsWindowVisible(h) and parte_titulo in _texto_janela(h):
                achadas.append(h)
            return True
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        if achadas:
            return achadas[0]
        time.sleep(0.2)
    raise RuntimeError(f"janela com '{parte_titulo}' não apareceu")


def filhas(hwnd, classe_comeca: str) -> list:
    achadas = []

    def cb(h, _):
        if _classe(h).startswith(classe_comeca) and user32.IsWindowVisible(h):
            achadas.append(h)
        return True
    user32.EnumChildWindows(hwnd, WNDENUMPROC(cb), 0)
    return achadas


def ler_wm_gettext(hwnd) -> str:
    n = user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.SendMessageW(hwnd, WM_GETTEXT, n + 1, ctypes.addressof(buf))
    return buf.value


def em_foco(alvo) -> bool:
    fg = user32.GetForegroundWindow()
    return bool(fg) and user32.GetAncestor(fg, GA_ROOT) == alvo


def focar(alvo) -> None:
    """Traz a janela DO TESTE para a frente (AttachThreadInput: a janela é nossa)."""
    for _ in range(20):
        if em_foco(alvo):
            return
        fg = user32.GetForegroundWindow()
        t_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        t_eu = kernel32.GetCurrentThreadId()
        if t_fg and t_fg != t_eu:
            user32.AttachThreadInput(t_eu, t_fg, True)
        user32.BringWindowToTop(alvo)
        user32.SetForegroundWindow(alvo)
        if t_fg and t_fg != t_eu:
            user32.AttachThreadInput(t_eu, t_fg, False)
        time.sleep(0.25)
    if not em_foco(alvo):
        raise RuntimeError("não consegui pôr a janela do teste em foco")


def atalho(vk: int, alvo) -> None:
    """Ctrl+<tecla>, só se a janela do teste estiver em foco."""
    if not em_foco(alvo):
        raise RuntimeError("janela do teste perdeu o foco; atalho não enviado")
    paste._enviar([paste._tecla(paste.VK_LCONTROL), paste._tecla(vk), paste._tecla(vk, up=True),
                   paste._tecla(paste.VK_LCONTROL, up=True)])
    time.sleep(0.15)


def tecla(vk: int, alvo) -> None:
    if not em_foco(alvo):
        raise RuntimeError("janela do teste perdeu o foco; tecla não enviada")
    paste._enviar([paste._tecla(vk), paste._tecla(vk, up=True)])
    time.sleep(0.1)


# ---------------------------------------------------------------- digitação
class GuardaDoTeste(paste.GuardaJanela):
    """A guarda de verdade + trava: se a janela em foco não for a do teste, para."""

    def __init__(self, alvo, parar):
        super().__init__()
        self.alvo, self.parar_teste = alvo, parar
        self.fora = None

    def esperar(self, parar=None, limite_s=paste.ESPERA_JANELA_MAX_S):
        info = super().esperar(parar, limite_s)
        if not self.alvo.conferir():
            hwnd, classe, processo = info
            self.fora = f"em foco: 0x{hwnd:X} {classe} {processo} '{_texto_janela(hwnd)}'"
            self.parar_teste.set()
        return info


def digitar_como_tempo_real(alvo) -> tuple[str, float, str | None]:
    """Digita FRASE trecho a trecho (" palavra"), como o Motor faz. Devolve (texto, s, abortou)."""
    parar = threading.Event()
    guarda = GuardaDoTeste(alvo, parar)  # alvo: objeto Alvo
    original, paste._guarda = paste._guarda, guarda
    palavras = FRASE.split(" ")
    trechos = [p if i == 0 else " " + p for i, p in enumerate(palavras)]
    enviado = ""
    t0 = time.perf_counter()
    try:
        for trecho in trechos:
            resto = paste.digitar(trecho, parar, soltar_apos_s=None)
            enviado += trecho[:len(trecho) - len(resto)]
            if resto:
                break
    finally:
        paste._guarda = original
    return enviado, time.perf_counter() - t0, guarda.fora


# ---------------------------------------------------------------- alvos
class Alvo:
    nome = ""

    def abrir(self): ...
    def conferir(self) -> bool:
        """A janela do teste está em foco (e pronta para receber teclas)?"""
        return em_foco(self.janela)

    def limpar(self): ...
    def ler(self) -> str: ...
    def fechar(self): ...


class BlocoDeNotas(Alvo):
    nome = "Bloco de Notas"

    def abrir(self):
        if _bloco_aberto():
            # Com abas, o Bloco de Notas junta tudo numa janela só: para nunca mexer nas abas
            # de ninguém, o teste só roda com um Bloco de Notas aberto por ele mesmo.
            raise RuntimeError("feche o Bloco de Notas antes; o teste só usa um aberto por ele")
        self.pasta = Path(tempfile.mkdtemp(prefix="gv_digit_"))
        self.arquivo = self.pasta / f"gillevoz_teste_{os.getpid()}.txt"
        self.arquivo.write_text("", encoding="utf-8")
        subprocess.Popen(["notepad.exe", str(self.arquivo)])
        self.janela = achar_janela(self.arquivo.stem)
        focar(self.janela)
        time.sleep(0.8)

    def conferir(self):
        # Com abas, além da janela, a aba ativa tem que ser a nossa.
        return em_foco(self.janela) and self.arquivo.stem in _texto_janela(self.janela)

    def _edit(self):
        # Com abas, só a aba ativa (a nossa: o título tem o nome do nosso arquivo) fica visível.
        if self.arquivo.stem not in _texto_janela(self.janela):
            raise RuntimeError("a aba ativa do Bloco de Notas não é a do teste")
        edits = filhas(self.janela, "RichEditD2DPT")
        if len(edits) != 1:
            raise RuntimeError(f"esperava 1 área de texto visível, achei {len(edits)}")
        return edits[0]

    def limpar(self):
        focar(self.janela)
        self._edit()
        atalho(VK_A, self.janela)
        tecla(VK_DELETE, self.janela)

    def ler(self):
        return ler_wm_gettext(self._edit())

    def fechar(self):
        # Esvazia e salva o NOSSO arquivo (assim fechar não pergunta nada) e fecha a janela,
        # que só tem a nossa aba (abrir() recusa rodar com outro Bloco de Notas aberto).
        try:
            if user32.IsWindow(self.janela) and self.arquivo.stem in _texto_janela(self.janela):
                focar(self.janela)
                self.limpar()
                atalho(VK_S, self.janela)
                fim = time.monotonic() + 5
                while time.monotonic() < fim and _texto_janela(self.janela).lstrip().startswith("*"):
                    time.sleep(0.2)
                user32.PostMessageW(self.janela, WM_CLOSE, 0, 0)
            fim = time.monotonic() + 10
            while time.monotonic() < fim and _bloco_aberto():
                time.sleep(0.3)
            if _bloco_aberto():
                raise RuntimeError("o Bloco de Notas do teste não fechou; feche-o sem salvar")
        finally:
            try:
                self.arquivo.unlink()
                self.pasta.rmdir()
            except OSError:
                pass


def _bloco_aberto() -> bool:
    saida = subprocess.run(["tasklist", "/FI", "IMAGENAME eq notepad.exe", "/NH"],
                           capture_output=True, text=True, errors="replace").stdout
    return "notepad.exe" in saida.lower()


FORM_PS = r"""
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object System.Windows.Forms.Form
$f.Text = '__TITULO__'
$f.Width = 700; $f.Height = 200
$t = New-Object System.Windows.Forms.TextBox
$t.Multiline = $true; $t.Dock = 'Fill'
$f.Controls.Add($t)
$f.Add_Shown({ $f.Activate(); $t.Focus() })
[void]$f.ShowDialog()
"""


class WinForms(Alvo):
    nome = "WinForms TextBox"

    def abrir(self):
        self.titulo = f"GilleVoz teste WinForms {os.getpid()}"
        self.proc = subprocess.Popen(["powershell", "-NoProfile", "-STA", "-Command",
                                      FORM_PS.replace("__TITULO__", self.titulo)])
        self.janela = achar_janela(self.titulo)
        focar(self.janela)
        time.sleep(0.5)

    def _edit(self):
        edits = filhas(self.janela, "WindowsForms10.EDIT")
        if len(edits) != 1:
            raise RuntimeError(f"esperava 1 TextBox, achei {len(edits)}")
        return edits[0]

    def limpar(self):
        buf = ctypes.create_unicode_buffer("")
        user32.SendMessageW(self._edit(), WM_SETTEXT, 0, ctypes.addressof(buf))
        focar(self.janela)

    def ler(self):
        return ler_wm_gettext(self._edit())

    def fechar(self):
        user32.PostMessageW(self.janela, WM_CLOSE, 0, 0)
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


HTML = """<!doctype html><meta charset="utf-8"><title>__TITULO__</title>
<textarea id="t" style="width:95vw;height:80vh" autofocus spellcheck="false"></textarea>
<script>document.getElementById('t').focus()</script>"""


class Edge(Alvo):
    nome = "Edge textarea"
    EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    def abrir(self):
        if not Path(self.EXE).exists():
            raise RuntimeError("Edge não encontrado")
        self.pasta = Path(tempfile.mkdtemp(prefix="gv_edge_"))
        self.titulo = f"GilleVoz teste Edge {os.getpid()}"
        pagina = self.pasta / "teste.html"
        pagina.write_text(HTML.replace("__TITULO__", self.titulo), encoding="utf-8")
        perfil = self.pasta / "perfil"
        self.proc = subprocess.Popen([self.EXE, f"--user-data-dir={perfil}", "--no-first-run",
                                      "--no-default-browser-check", "--disable-sync",
                                      f"--app={pagina.as_uri()}"])
        self.janela = achar_janela(self.titulo, timeout=30)
        focar(self.janela)
        time.sleep(1.5)

    def limpar(self):
        focar(self.janela)
        atalho(VK_A, self.janela)
        tecla(VK_DELETE, self.janela)

    def ler(self):
        focar(self.janela)
        backup, perdidos = paste.salvar_clipboard_detalhado()
        if perdidos:
            raise RuntimeError(f"área de transferência tem formatos que não dá pra salvar: {perdidos}")
        try:
            atalho(VK_A, self.janela)
            atalho(VK_C, self.janela)
            time.sleep(0.2)
            import pyperclip
            return pyperclip.paste()
        finally:
            paste.restaurar_clipboard(backup)

    def fechar(self):
        subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True)
        time.sleep(1.0)
        import shutil
        shutil.rmtree(self.pasta, ignore_errors=True)


ALVOS = {"bloco": BlocoDeNotas, "winforms": WinForms, "edge": Edge}


# ---------------------------------------------------------------- carga
def _queimar(fim: float) -> None:
    x = 0
    while time.time() < fim:
        x = (x * 1103515245 + 12345) % 2147483648


def iniciar_carga(segundos: float) -> list:
    fim = time.time() + segundos
    procs = [multiprocessing.Process(target=_queimar, args=(fim,), daemon=True)
             for _ in range(os.cpu_count() or 4)]
    for p in procs:
        p.start()
    return procs


def parar_carga(procs) -> None:
    for p in procs:
        p.terminate()
    for p in procs:
        p.join(5)


# ---------------------------------------------------------------- principal
def rodar(chave: str, rodadas: int, carga: bool) -> dict:
    alvo = ALVOS[chave]()
    res = {"alvo": alvo.nome, "carga": carga, "ok": 0, "total": rodadas, "tempos": [], "erros": []}
    procs = []
    try:
        alvo.abrir()
        if carga:
            procs = iniciar_carga(600)
            time.sleep(1.0)
        for i in range(rodadas):
            alvo.limpar()
            time.sleep(0.3)
            enviado, dt, fora = digitar_como_tempo_real(alvo)
            time.sleep(0.4)
            if fora:
                res["erros"].append(f"rodada {i + 1}: janela do teste perdeu o foco ({fora}); parei")
                break
            lido = alvo.ler().replace("\r\n", "\n")
            res["tempos"].append(dt)
            if lido == FRASE and enviado == FRASE:
                res["ok"] += 1
            else:
                res["erros"].append(f"rodada {i + 1}: lido={lido!r}")
    except Exception as e:
        res["erros"].append(f"{type(e).__name__}: {e}")
    finally:
        parar_carga(procs)
        try:
            alvo.fechar()
        except Exception as e:
            res["erros"].append(f"ao fechar: {e}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alvos", default="bloco,winforms,edge")
    ap.add_argument("--rodadas", type=int, default=3)
    ap.add_argument("--carga", action="store_true", help="também roda com todos os núcleos ocupados")
    ap.add_argument("--pausa", type=float, help="experimento: outra pausa depois do separador (s)")
    a = ap.parse_args()
    if a.pausa is not None:
        paste.PAUSA_FIM_PALAVRA_S = a.pausa
        print(f"Pausa depois do separador: {a.pausa * 1000:.0f} ms")
    cenarios = [False, True] if a.carga else [False]
    resultados = []
    for chave in [x.strip() for x in a.alvos.split(",") if x.strip()]:
        for carga in cenarios:
            r = rodar(chave, a.rodadas, carga)
            resultados.append(r)
            print(f"{r['alvo']:18} {'carga' if carga else 'parado':7} {r['ok']}/{r['total']}", flush=True)
            for e in r["erros"]:
                print("    ", e, flush=True)
    print()
    print("| Alvo | CPU | Iguais | Tempo médio por frase |")
    print("|---|---|---|---|")
    for r in resultados:
        media = sum(r["tempos"]) / len(r["tempos"]) if r["tempos"] else 0
        print(f"| {r['alvo']} | {'ocupada' if r['carga'] else 'parada'} | {r['ok']}/{r['total']} | {media:.2f} s |")
    print(f"\nFrase ({len(FRASE)} caracteres, {len(FRASE.split())} palavras): {FRASE}")
    return 0 if all(r["ok"] == r["total"] for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
