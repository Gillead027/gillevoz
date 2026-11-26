"""Cola texto na janela em foco sem roubar o foco, restaurando a área de transferência.

Fluxo (metodo="clipboard"):
  1. salva o conteúdo atual da área de transferência (todos os formatos que dá pra copiar
     como bytes: texto, HTML, RTF, imagem DIB, formatos de apps...; se o pywin32 falhar,
     salva pelo menos o texto via pyperclip);
  2. coloca o texto (marcado para NÃO entrar no histórico Win+V);
  3. espera o usuário soltar Ctrl/Alt/Shift/Win do atalho (se não soltar, solta por ele);
  4. envia Ctrl+V, espera `espera_ms` e restaura o conteúdo original — a não ser que outro
     programa tenha escrito na área de transferência nesse meio-tempo.
Nunca aperta Enter quando auto_enter=False.
"""
from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import wintypes

log = logging.getLogger("gillevoz")

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT

# Teclas modificadoras que podem estar presas pelo atalho (VK codes).
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU = 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5
VK_LWIN, VK_RWIN = 0x5B, 0x5C
VK_V, VK_RETURN, VK_BACK = 0x56, 0x0D, 0x08
_MODIFICADORAS = [VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU, VK_LSHIFT, VK_RSHIFT, VK_LWIN, VK_RWIN]
_EXTENDIDAS = {VK_RCONTROL, VK_RMENU, VK_LWIN, VK_RWIN}

# Formatos que são handles GDI (não dá pra copiar como bytes) — o Windows sintetiza
# CF_BITMAP a partir de CF_DIB, então a imagem não se perde.
_FORMATOS_PULAR = {2, 3, 9, 14, 0x0080, 0x0082, 0x0083, 0x008E}  # BITMAP, METAFILEPICT, PALETTE, ENHMETAFILE, OWNERDISPLAY, DSP*
CF_UNICODETEXT = 13

# ---------------------------------------------------------------- SendInput
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x1, 0x2, 0x4
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

# Marca nossas teclas injetadas para o hotkey.py poder ignorá-las, se quiser.
GILLEVOZ_EXTRA = 0x47564F5A  # "GVOZ"


def _tecla(vk: int = 0, up: bool = False, scan: int = 0, unicode: bool = False) -> INPUT:
    flags = 0
    if up:
        flags |= KEYEVENTF_KEYUP
    if unicode:
        flags |= KEYEVENTF_UNICODE
    if vk in _EXTENDIDAS:
        flags |= KEYEVENTF_EXTENDEDKEY
    if vk and not unicode and not scan:
        scan = user32.MapVirtualKeyW(vk, 0) & 0xFF  # MAPVK_VK_TO_VSC: alguns apps/hooks olham o scan code
    i = INPUT(type=INPUT_KEYBOARD)
    i.u.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=GILLEVOZ_EXTRA)
    return i


def _enviar(inputs: list[INPUT]) -> None:
    if not inputs:
        return
    arr = (INPUT * len(inputs))(*inputs)
    n = user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
    if n != len(inputs):
        log.warning("SendInput enviou %d de %d eventos (erro %d)", n, len(inputs), ctypes.get_last_error())


def _pressionada(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


PAUSA_ESPERA_S = 0.02  # intervalo entre conferências (modificadoras, janela em foco)


def esperar_modificadoras(parar: threading.Event | None = None, soltar_apos_s: float | None = None) -> bool:
    """Espera o usuário soltar Ctrl/Alt/Shift/Win. Devolve False se `parar` foi acionado antes.

    soltar_apos_s=None: espera o tempo que for (tempo real: nunca solta por ele no meio do ditado).
    soltar_apos_s=N: depois de N segundos ainda apertadas, solta por ele (entrega final/colagem).
    """
    inicio = time.monotonic()
    while True:
        if parar is not None and parar.is_set():
            return False
        presas = [vk for vk in _MODIFICADORAS if _pressionada(vk)]
        if not presas:
            return True
        if soltar_apos_s is not None and time.monotonic() - inicio >= soltar_apos_s:
            log.debug("Soltando modificadoras ainda pressionadas: %s", [hex(v) for v in presas])
            _enviar([_tecla(vk, up=True) for vk in presas])
            time.sleep(PAUSA_ESPERA_S)
            return True
        time.sleep(PAUSA_ESPERA_S)


def soltar_modificadoras(timeout_s: float = 0.6) -> None:
    """Espera o usuário soltar Ctrl/Alt/Shift/Win; se continuar segurando, solta por ele.

    Sem isso, Ctrl+V viraria Ctrl+Alt+V (que em muitos apps é outra coisa).
    """
    esperar_modificadoras(None, soltar_apos_s=timeout_s)


# ---------------------------------------------------------------- janela em foco
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.OpenProcess.restype = wintypes.HANDLE
_k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                            ctypes.POINTER(wintypes.DWORD)]
_k32.QueryFullProcessImageNameW.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# Interface do próprio Windows (barra de tarefas, Alt+Tab, Win+Tab, Iniciar, Pesquisa):
# teclas digitadas ali iriam para o lugar errado. Esperamos ela sair da frente.
_CLASSES_SHELL = {
    "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "MultitaskingViewFrame", "XamlExplorerHostIslandWindow",
    "ForegroundStaging", "TaskSwitcherWnd", "TaskSwitcherOverlayWnd", "NotifyIconOverflowWindow",
    "TopLevelWindowForOverflowXamlIsland",
}
_PROCESSOS_SHELL = {"startmenuexperiencehost.exe", "searchhost.exe", "searchapp.exe", "shellexperiencehost.exe"}
JANELA_ESTAVEL_S = 0.15     # janela recém-trocada: espera ela "assentar"
ESPERA_JANELA_MAX_S = 3.0   # nunca espera mais que isso; depois segue mesmo assim


def info_janela_foco() -> tuple[int, str, str]:
    """(hwnd, classe, nome do processo) da janela em foco; (0, "", "") se não houver."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return 0, "", ""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    classe = buf.value
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    processo = ""
    h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value) if pid.value else None
    if h:
        try:
            tam = wintypes.DWORD(520)
            caminho = ctypes.create_unicode_buffer(520)
            if _k32.QueryFullProcessImageNameW(h, 0, caminho, ctypes.byref(tam)):
                processo = caminho.value.rsplit("\\", 1)[-1]
        finally:
            _k32.CloseHandle(h)
    return int(hwnd), classe, processo


class GuardaJanela:
    """Antes de cada tecla: espera a janela em foco existir, não ser interface do
    Windows (Alt+Tab, Iniciar...) e não ter acabado de trocar. Nunca espera mais que o limite."""

    def __init__(self, info=info_janela_foco, relogio=time.monotonic, dormir=time.sleep):
        self._info = info
        self._relogio = relogio
        self._dormir = dormir
        self._ultima = None   # última janela vista
        self._desde = 0.0     # quando ela apareceu na frente (pelo que vimos)
        self._desistidas: set[int] = set()  # janelas que já estouraram o limite nesta entrega

    def nova_entrega(self) -> None:
        """Começo de um digitar(): cada janela ruim volta a ter direito a UMA espera."""
        self._desistidas.clear()

    def motivo_espera(self, hwnd: int, classe: str, processo: str, agora: float) -> str | None:
        """None = pode digitar; senão, o motivo para esperar."""
        if hwnd != self._ultima:
            self._ultima, self._desde = hwnd, agora
        if not hwnd:
            return "nenhuma janela em foco"
        if classe in _CLASSES_SHELL or processo.lower() in _PROCESSOS_SHELL:
            return f"interface do Windows em foco ({classe})"
        if agora - self._desde < JANELA_ESTAVEL_S:
            return "janela em foco acabou de mudar"
        return None

    def esperar(self, parar: threading.Event | None = None,
                limite_s: float = ESPERA_JANELA_MAX_S) -> tuple[int, str, str]:
        """Espera a janela ficar boa para digitar; devolve (hwnd, classe, processo)."""
        inicio = self._relogio()
        while True:
            info = self._info()
            motivo = self.motivo_espera(*info, self._relogio())
            if motivo is None or (parar is not None and parar.is_set()) or info[0] in self._desistidas:
                return info
            if self._relogio() - inicio >= limite_s:
                # Não espera de novo por esta janela nas próximas teclas desta entrega (senão
                # 100 letras com a Pesquisa em foco levariam 5 min segurando a trava de digitar).
                self._desistidas.add(info[0])
                log.info("Janela em foco não estabilizou em %.0f s (%s); digitando mesmo assim.", limite_s, motivo)
                return info
            self._dormir(PAUSA_ESPERA_S)


_guarda = GuardaJanela()


def enviar_ctrl_v() -> None:
    _enviar([_tecla(VK_LCONTROL), _tecla(VK_V), _tecla(VK_V, up=True), _tecla(VK_LCONTROL, up=True)])


def enviar_enter() -> None:
    _enviar([_tecla(VK_RETURN), _tecla(VK_RETURN, up=True)])


def apagar(n: int) -> None:
    """Aperta Backspace n vezes na janela em foco (tempo real; normalmente não é usado)."""
    if n <= 0:
        return
    evs = []
    for _ in range(n):
        evs.append(_tecla(VK_BACK))
        evs.append(_tecla(VK_BACK, up=True))
    _enviar(evs)


# Uma tecla Unicode por SendInput, com pausa entre elas. Depois de espaço/pontuação o Bloco
# de Notas do Win11 trava um instante (corretor ortográfico): teclas Unicode que chegam
# durante a trava saem trocadas ("Gillezin. Quero" -> "Gillezin.QQuero") ou somem.
# Medido com tools/teste_digitacao.py (Bloco de Notas, 2026-11-26): mandar a palavra inteira
# num SendInput (com 80 ms ou até 150 ms depois do separador) errou em 20-50% das frases
# ("coração,pão", "Quero oooo"); letra a letra com estas pausas acertou 33/33 parado e 8/8
# com a CPU ocupada.
PAUSA_DIGITAR_S = 0.015      # depois de letra/número
PAUSA_FIM_PALAVRA_S = 0.08   # depois de espaço/pontuação (inclusive no fim do trecho)


def _eventos_unicode(texto: str) -> list[INPUT]:
    evs = []
    for ch in texto:
        if ch == "\n":
            unidades = [0x0D]  # quebra de linha via Unicode \r (só no modo "digitar" da colagem)
        else:
            b = ch.encode("utf-16-le")
            unidades = [int.from_bytes(b[i:i + 2], "little") for i in range(0, len(b), 2)]
        for u in unidades:
            evs.append(_tecla(0, scan=u, unicode=True))
            evs.append(_tecla(0, scan=u, unicode=True, up=True))
    return evs


def digitar(texto: str, parar: threading.Event | None = None, *, soltar_apos_s: float | None = 0.6) -> str:
    """Digita via KEYEVENTF_UNICODE (acentos e emoji), uma tecla por vez.

    Antes de cada tecla: espera soltar Ctrl/Alt/Shift/Win (com soltar_apos_s=None nunca solta
    por ele) e espera a janela em foco ficar estável. Se `parar` for acionado, para antes da
    próxima tecla. Devolve o que NÃO foi digitado ("" = tudo).
    """
    texto = texto.replace("\r\n", "\n")
    _guarda.nova_entrega()
    for i, ch in enumerate(texto):
        if not esperar_modificadoras(parar, soltar_apos_s):
            return texto[i:]
        hwnd, classe, processo = _guarda.esperar(parar)
        if parar is not None and parar.is_set():
            return texto[i:]
        if i == 0:
            log.info("Digitando %d caracteres na janela 0x%X (classe %s, processo %s)",
                     len(texto), hwnd, classe or "?", processo or "?")
        _enviar(_eventos_unicode(ch))
        time.sleep(PAUSA_DIGITAR_S if ch.isalnum() else PAUSA_FIM_PALAVRA_S)
    return ""


# ---------------------------------------------------------------- área de transferência
def _abrir_clipboard(win32clipboard, tentativas: int = 20) -> None:
    ultimo = None
    for _ in range(tentativas):
        try:
            win32clipboard.OpenClipboard(0)
            return
        except Exception as e:  # outro app está com a área de transferência aberta
            ultimo = e
            time.sleep(0.02)
    raise RuntimeError(f"Não consegui abrir a área de transferência: {ultimo}")


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t

CF_BITMAP, CF_METAFILEPICT, CF_PALETTE, CF_ENHMETAFILE, CF_DIB, CF_DIBV5 = 2, 3, 9, 14, 8, 17


def _ler_bytes_crus(fmt: int):
    """Lê o HGLOBAL de um formato como bytes (ex.: CF_HDROP, que o pywin32 devolve como tupla).

    A área de transferência precisa estar aberta. Devolve None se não for um bloco de memória.
    """
    h = user32.GetClipboardData(fmt)
    if not h:
        return None
    tamanho = kernel32.GlobalSize(h)
    if not tamanho:
        return None
    ptr = kernel32.GlobalLock(h)
    if not ptr:
        return None
    try:
        return ctypes.string_at(ptr, tamanho)
    finally:
        kernel32.GlobalUnlock(h)


def salvar_clipboard_detalhado():
    """Faz o backup e diz o que NÃO deu pra salvar.

    Retorna (backup, perdidos): backup = ("win32", [(fmt, dado), ...]) ou ("texto", str|None);
    perdidos = lista de formatos que seriam perdidos se a área de transferência fosse esvaziada.
    """
    try:
        import win32clipboard

        _abrir_clipboard(win32clipboard)
        try:
            itens, pulados, falhos = [], [], []
            fmt = win32clipboard.EnumClipboardFormats(0)
            while fmt:
                if fmt in _FORMATOS_PULAR:
                    pulados.append(fmt)
                else:
                    dado = None
                    try:
                        dado = win32clipboard.GetClipboardData(fmt)
                    except Exception:
                        dado = None
                    if not isinstance(dado, (bytes, str)):
                        # tupla (CF_HDROP), int ou erro: copia o bloco de memória original
                        try:
                            dado = _ler_bytes_crus(fmt)
                        except Exception:
                            dado = None
                    if isinstance(dado, (bytes, str)):
                        itens.append((fmt, dado))
                    else:
                        falhos.append(fmt)
                fmt = win32clipboard.EnumClipboardFormats(fmt)
        finally:
            win32clipboard.CloseClipboard()
        salvos = {f for f, _ in itens}
        perdidos = list(falhos)
        for f in pulados:
            # O Windows recria BITMAP/PALETTE a partir do DIB salvo; metafiles e
            # formatos "owner display" não têm como ser recriados.
            if f in (CF_BITMAP, CF_PALETTE) and salvos & {CF_DIB, CF_DIBV5}:
                continue
            perdidos.append(f)
        return ("win32", itens), perdidos
    except Exception as e:
        log.warning("Backup completo da área de transferência falhou (%s); salvando só o texto.", e)
        try:
            import pyperclip

            texto = pyperclip.paste()
        except Exception:
            texto = None
        # Sem backup completo não dá pra garantir nada além do texto.
        return ("texto", texto), (["desconhecido"] if texto in (None, "") else [])


def salvar_clipboard():
    """Retorna ("win32", [(fmt, dado), ...]) ou ("texto", str|None)."""
    return salvar_clipboard_detalhado()[0]


def _marcar_sem_historico(win32clipboard) -> None:
    """Pede ao Windows para não guardar esse conteúdo no histórico Win+V nem na nuvem."""
    try:
        f1 = win32clipboard.RegisterClipboardFormat("ExcludeClipboardContentFromMonitorProcessing")
        win32clipboard.SetClipboardData(f1, b"\x00")
        f2 = win32clipboard.RegisterClipboardFormat("CanIncludeInClipboardHistory")
        win32clipboard.SetClipboardData(f2, (0).to_bytes(4, "little"))
        f3 = win32clipboard.RegisterClipboardFormat("CanUploadToCloudClipboard")
        win32clipboard.SetClipboardData(f3, (0).to_bytes(4, "little"))
    except Exception:
        pass


def colocar_texto(texto: str) -> None:
    try:
        import win32clipboard

        _abrir_clipboard(win32clipboard)
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(CF_UNICODETEXT, texto)
            _marcar_sem_historico(win32clipboard)
        finally:
            win32clipboard.CloseClipboard()
    except ImportError:
        import pyperclip

        pyperclip.copy(texto)


def restaurar_clipboard(backup) -> None:
    tipo, conteudo = backup
    if tipo == "win32":
        import win32clipboard

        _abrir_clipboard(win32clipboard)
        try:
            win32clipboard.EmptyClipboard()
            for fmt, dado in conteudo:
                try:
                    win32clipboard.SetClipboardData(fmt, dado)
                except Exception as e:
                    log.debug("Não restaurei formato %s: %s", fmt, e)
        finally:
            win32clipboard.CloseClipboard()
    else:
        import pyperclip

        pyperclip.copy(conteudo if conteudo is not None else "")


def sequencia_clipboard() -> int:
    return int(user32.GetClipboardSequenceNumber())


# ---------------------------------------------------------------- API pública
def colar(texto: str, metodo: str = "clipboard", auto_enter: bool = False, espera_ms: int = 150,
          espaco_final: bool = False, parar: threading.Event | None = None) -> str:
    """Cola `texto` onde o cursor estiver, na janela que já está em foco.

    espaco_final=True acrescenta um espaço no fim (se o texto ainda não terminar em espaço),
    para o próximo ditado ou o texto já existente não ficar grudado.
    parar (tempo real): espera as modificadoras sem soltá-las por ele e desiste se `parar`
    for acionado antes de colar. Devolve o que NÃO foi entregue ("" = tudo).
    """
    if not texto:
        return ""
    if espaco_final and not texto[-1].isspace():
        texto += " "
    if parar is None:
        soltar_modificadoras()
    else:
        if not esperar_modificadoras(parar, None):
            return texto
        _guarda.nova_entrega()
        _guarda.esperar(parar)
        if parar.is_set():
            return texto
    if metodo != "digitar":
        backup, perdidos = salvar_clipboard_detalhado()
        if perdidos:
            # Não apaga o que não conseguimos salvar: digita em vez de usar a área de transferência.
            log.warning("Área de transferência tem conteúdo que não dá pra salvar (formatos %s); "
                        "digitando o texto em vez de colar.", perdidos)
            metodo = "digitar"
    if metodo == "digitar":
        resto = digitar(texto, parar, soltar_apos_s=None if parar is not None else 0.6)
        if resto:
            return resto
    else:
        seq_nossa = None
        try:
            colocar_texto(texto)
            seq_nossa = sequencia_clipboard()
            enviar_ctrl_v()
            time.sleep(max(espera_ms, 0) / 1000.0)
        finally:
            # Sempre tenta restaurar, mesmo se algo acima falhou — exceto se outro programa
            # escreveu na área de transferência depois de nós.
            if seq_nossa is None or sequencia_clipboard() == seq_nossa:
                try:
                    restaurar_clipboard(backup)
                except Exception as e:
                    log.error("Falha ao restaurar a área de transferência: %s", e)
            else:
                log.info("Área de transferência mudou durante a colagem; não restaurei para não apagar o novo conteúdo.")
    if auto_enter:
        time.sleep(0.05)
        enviar_enter()
    return ""
