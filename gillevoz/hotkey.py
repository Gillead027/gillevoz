"""Atalho global (modos toggle e push) + Esc para cancelar, só durante a gravação.

Implementação principal: RegisterHotKey do Windows, numa thread com loop de mensagens.
  - O Windows entrega o atalho só para nós (não vaza para o app em foco) e não precisa
    de hook de teclado (hooks podem ser desligados pelo Windows se demorarem).
  - Esc é registrado apenas enquanto grava e desregistrado logo depois — fora da
    gravação o Esc chega normalmente nos outros apps.
  - Push-to-talk: ao receber o atalho, acompanha a tecla principal com GetAsyncKeyState
    e chama on_parar quando ela (ou todas as modificadoras) for solta.
Fallback: se o RegisterHotKey falhar (atalho já usado por outro programa), usa a lib
`keyboard` (hook global) com a mesma lógica.

AtalhoAcao: atalho simples (ex.: colar a última transcrição), só RegisterHotKey, sem
soltura nem Esc.

Botões laterais do mouse (mouse4/mouse5, com ou sem modificadores): RegisterHotKey não
serve para mouse, então usam o GanchoMouse (um gancho WH_MOUSE_LL só enquanto houver
atalho de mouse). Enquanto o botão é atalho, o clique é engolido (não volta página).
"""
from __future__ import annotations

import ctypes
import logging
import queue
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger("gillevoz")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
user32.VkKeyScanW.restype = ctypes.c_short

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT, WM_USER = 0x0312, 0x0012, 0x0400
WM_ESC_ON, WM_ESC_OFF = WM_USER + 1, WM_USER + 2
ID_ATALHO, ID_ESC = 1, 2
VK_ESCAPE = 0x1B
VK_FANTASMA = 0xE8  # VK não atribuído a nenhuma tecla
KEYEVENTF_KEYUP = 0x2
user32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, wintypes.DWORD, ctypes.c_size_t]

_MODS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT,
         "win": MOD_WIN, "windows": MOD_WIN, "super": MOD_WIN}
# VKs das modificadoras (genérica, esquerda, direita) para o push-to-talk
_VK_MODS = {MOD_CONTROL: (0x11, 0xA2, 0xA3), MOD_ALT: (0x12, 0xA4, 0xA5),
            MOD_SHIFT: (0x10, 0xA0, 0xA1), MOD_WIN: (0x5B, 0x5C)}
_TECLAS = {
    "space": 0x20, "espaço": 0x20, "espaco": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
    "backspace": 0x08, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "pause": 0x13, "capslock": 0x14, "scrolllock": 0x91, "printscreen": 0x2C,
}
_TECLAS.update({f"f{i}": 0x6F + i for i in range(1, 25)})


# Botões laterais do mouse. O "vk" devolvido por parse_atalho é o VK do próprio botão
# (VK_XBUTTON1/2): nunca colide com tecla, então serve para achar atalho repetido.
VK_XBUTTON1, VK_XBUTTON2 = 0x05, 0x06
_BOTOES_MOUSE = {"mouse4": VK_XBUTTON1, "mouse5": VK_XBUTTON2}
_BOTOES_RECUSADOS = {"mouse1", "mouse2", "mouse3"}


def parse_atalho(atalho: str) -> tuple[int, int]:
    """'ctrl+alt+space' -> (mods, vk); 'ctrl+mouse4' -> (mods, VK_XBUTTON1).
    Levanta ValueError se não entender."""
    partes = [p.strip().lower() for p in atalho.replace(" ", "").split("+") if p.strip()]
    mods, vk = 0, None
    for p in partes:
        if p in _MODS:
            mods |= _MODS[p]
        elif p in _BOTOES_MOUSE:
            vk = _BOTOES_MOUSE[p]
        elif p in _BOTOES_RECUSADOS:
            raise ValueError(f"o botão {p!r} não pode ser atalho (use um botão lateral: mouse4 ou mouse5)")
        elif p in _TECLAS:
            vk = _TECLAS[p]
        elif len(p) == 1:
            r = user32.VkKeyScanW(p)
            if r == -1:
                raise ValueError(f"tecla desconhecida: {p!r}")
            vk = r & 0xFF
        else:
            raise ValueError(f"tecla desconhecida: {p!r}")
    if vk is None:
        raise ValueError(f"atalho sem tecla principal: {atalho!r}")
    return mods, vk


def parse_atalho_mouse(atalho: str) -> tuple[int, int] | None:
    """'ctrl+mouse4' -> (mods, botão 1|2); None se o atalho não é de mouse."""
    mods, vk = parse_atalho(atalho)
    if vk == VK_XBUTTON1:
        return mods, 1
    if vk == VK_XBUTTON2:
        return mods, 2
    return None


def validar_atalho(atalho) -> str | None:
    """Devolve uma mensagem de erro (pt-BR) se o atalho não serve, ou None se está ok.

    Recusa vazio/não-texto, tecla desconhecida, botão do mouse que não é lateral e
    combinação só de modificadores (todo atalho precisa de uma tecla comum ou de um
    botão lateral do mouse).
    """
    if not isinstance(atalho, str):
        return f"Atalho inválido ({atalho!r}): precisa ser um texto como 'ctrl+shift+space'."
    if not atalho.replace("+", "").strip():
        return "Atalho vazio."
    try:
        parse_atalho(atalho)
    except ValueError as e:
        if "sem tecla principal" in str(e):
            return f"O atalho '{atalho}' precisa de uma tecla comum além de Ctrl/Alt/Shift/Win."
        return f"Atalho '{atalho}' inválido: {e}."
    return None


def _pressionada(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _tecla_fantasma(mods: int) -> None:
    """Com Alt/Win no atalho, a tecla principal é engolida pelo Windows e o app em foco veria
    "Alt sozinho" (abre o menu e come a próxima tecla, ex. o Ctrl+V) ou "Win sozinho" (abre o
    Iniciar) quando o usuário soltar. Uma tecla fantasma no meio evita isso."""
    if mods & (MOD_ALT | MOD_WIN):
        user32.keybd_event(VK_FANTASMA, 0, 0, 0)
        user32.keybd_event(VK_FANTASMA, 0, KEYEVENTF_KEYUP, 0)


# ------------------------------------------------------------ botões laterais do mouse
WH_MOUSE_LL = 14
WM_XBUTTONDOWN, WM_XBUTTONUP = 0x020B, 0x020C
LLMHF_INJECTED = 0x1

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


@dataclass(eq=False)
class Assinante:
    """Quem quer ouvir um botão lateral: mods exatos (MOD_*) e botão (1 = mouse4, 2 = mouse5)."""

    mods: int
    botao: int
    on_apertar: Callable[[], None]
    on_soltar: Callable[[], None] | None = None


def decidir_evento(msg: int, mouse_data: int, mods_fisicos: int, assinantes, apertados: dict,
                   injetado: bool = False) -> tuple[bool, list]:
    """Decide o que fazer com um evento do gancho de mouse (função pura, testável).

    Devolve (engolir, chamadas): engolir=True some com o clique (o app em foco não vê);
    chamadas são os callbacks a rodar FORA do gancho. `apertados` (botão -> Assinante) guarda
    quem recebeu o apertar, para que o soltar vá para ele mesmo se um modificador já foi solto.
    """
    if injetado or msg not in (WM_XBUTTONDOWN, WM_XBUTTONUP):
        return False, []
    botao = (mouse_data >> 16) & 0xFFFF
    if msg == WM_XBUTTONDOWN:
        for a in assinantes:
            if a.botao == botao and a.mods == mods_fisicos:
                apertados[botao] = a
                return True, [a.on_apertar]
        return False, []
    a = apertados.pop(botao, None)
    if a is None:
        return False, []
    return True, [a.on_soltar] if a.on_soltar else []


def _mods_fisicos() -> int:
    mods = 0
    for mod, vks in _VK_MODS.items():
        if any(_pressionada(v) for v in vks):
            mods |= mod
    return mods


class GanchoMouse:
    """Um único gancho global WH_MOUSE_LL, instalado só enquanto houver assinante.

    O callback do gancho só decide e enfileira (precisa voltar rápido, senão o Windows
    remove o gancho); os callbacks dos assinantes rodam numa thread trabalhadora, em ordem.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._assinantes: tuple[Assinante, ...] = ()
        self._apertados: dict = {}
        self._fila: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._tid = 0
        self._proc = HOOKPROC(self._ao_evento)  # guardar a referência: o Windows chama isto
        self._hook = None
        threading.Thread(target=self._trabalhar, daemon=True, name="gillevoz-mouse-trabalho").start()

    def assinar(self, a: Assinante) -> None:
        """Começa a ouvir. Levanta OSError se o Windows recusar o gancho."""
        with self._lock:
            self._assinantes = self._assinantes + (a,)
            if self._thread is not None:
                return
            pronto, erro = threading.Event(), []
            self._thread = threading.Thread(target=self._loop, args=(pronto, erro), daemon=True,
                                            name="gillevoz-mouse-gancho")
            self._thread.start()
            pronto.wait(5)
            if erro or not pronto.is_set():
                self._assinantes = tuple(x for x in self._assinantes if x is not a)
                self._thread, self._tid = None, 0
                raise OSError(f"não consegui instalar o gancho do mouse: {erro[0] if erro else 'sem resposta'}")
        log.info("Gancho do mouse ativo.")

    def cancelar(self, a: Assinante) -> None:
        """Para de ouvir; sem assinantes, o gancho é desinstalado."""
        with self._lock:
            self._assinantes = tuple(x for x in self._assinantes if x is not a)
            for b, x in list(self._apertados.items()):
                if x is a:
                    del self._apertados[b]
            if self._assinantes or self._thread is None:
                return
            thread, tid = self._thread, self._tid
            self._thread, self._tid = None, 0
        if tid:
            user32.PostThreadMessageW(tid, WM_QUIT, 0, 0)
        thread.join(2)
        log.info("Gancho do mouse desligado.")

    def _loop(self, pronto: threading.Event, erro: list) -> None:
        self._tid = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # cria a fila de mensagens da thread
        hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not hook:
            erro.append(f"erro {ctypes.get_last_error()}")
            pronto.set()
            return
        self._hook = hook
        pronto.set()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            user32.UnhookWindowsHookEx(hook)
            self._hook = None

    def _ao_evento(self, n_code: int, w_param: int, l_param: int) -> int:
        # Roda dentro do gancho: nada de trabalho pesado aqui.
        try:
            if n_code >= 0 and w_param in (WM_XBUTTONDOWN, WM_XBUTTONUP) and self._assinantes:
                info = MSLLHOOKSTRUCT.from_address(l_param)
                mods = _mods_fisicos() if w_param == WM_XBUTTONDOWN else 0
                engolir, chamadas = decidir_evento(w_param, info.mouseData, mods, self._assinantes,
                                                   self._apertados, bool(info.flags & LLMHF_INJECTED))
                for c in chamadas:
                    self._fila.put(c)
                if engolir:
                    return 1
        except Exception:
            log.debug("Erro no gancho do mouse", exc_info=True)
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _trabalhar(self) -> None:
        while True:
            fn = self._fila.get()
            try:
                fn()
            except Exception:
                log.exception("Erro no callback do atalho de mouse")


_gancho_mouse: GanchoMouse | None = None
_lock_gancho = threading.Lock()


def gancho_mouse() -> GanchoMouse:
    """O gancho de mouse do processo (criado sob demanda)."""
    global _gancho_mouse
    with _lock_gancho:
        if _gancho_mouse is None:
            _gancho_mouse = GanchoMouse()
        return _gancho_mouse


class Hotkey:
    """Atalho global.

    on_iniciar(), on_parar(), on_cancelar(): chamados na thread do atalho — devem ser rápidos.
    esta_gravando(): o app informa se está gravando (decide iniciar x parar no modo toggle).
    capturar_esc(True/False): o app liga a captura do Esc ao começar a gravar e desliga ao parar.
    """

    def __init__(self, atalho: str, modo: str, on_iniciar: Callable[[], None], on_parar: Callable[[], None],
                 on_cancelar: Callable[[], None], esta_gravando: Callable[[], bool]):
        self.atalho = atalho
        self.modo = modo if modo in ("toggle", "push") else "toggle"
        self.on_iniciar, self.on_parar, self.on_cancelar = on_iniciar, on_parar, on_cancelar
        self.esta_gravando = esta_gravando
        self.mods, self.vk = parse_atalho(atalho)
        self._mouse = parse_atalho_mouse(atalho)  # (mods, botão) se o atalho é de mouse
        self._assinante: Assinante | None = None
        self._thread: threading.Thread | None = None
        self._tid = 0
        self._pronto = threading.Event()
        self._erro: str | None = None
        self._usando_keyboard = False
        self._kb_esc_ligado = False
        self._kb_esc_bloqueado = False
        self._kb_travado = False
        self._kb_hotkey = None
        self._push_ativo = False

    # ------------------------------------------------------------ ciclo de vida
    def start(self) -> None:
        # Com atalho de mouse, a thread só cuida do Esc (o botão vem do GanchoMouse).
        self._thread = threading.Thread(target=self._loop, daemon=True, name="gillevoz-hotkey")
        self._thread.start()
        self._pronto.wait(5)
        if self._mouse:
            mods, botao = self._mouse
            a = Assinante(mods, botao, self._mouse_apertar, self._mouse_soltar)
            try:
                gancho_mouse().assinar(a)
            except OSError:
                self.stop()
                raise
            self._assinante = a
            log.info("Atalho global ativo (mouse): %s (modo %s)", self.atalho, self.modo)
        elif self._erro:
            log.warning("RegisterHotKey falhou (%s); usando a lib keyboard como alternativa.", self._erro)
            self._iniciar_keyboard()
        else:
            log.info("Atalho global ativo: %s (modo %s)", self.atalho, self.modo)

    def stop(self) -> None:
        if self._assinante is not None:
            gancho_mouse().cancelar(self._assinante)
            self._assinante = None
        if self._usando_keyboard:
            try:
                import keyboard

                keyboard.unhook_all()
            except Exception:
                pass
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(2)

    def capturar_esc(self, ligar: bool) -> None:
        if self._usando_keyboard:
            self._kb_capturar_esc(ligar)
        elif self._tid:
            user32.PostThreadMessageW(self._tid, WM_ESC_ON if ligar else WM_ESC_OFF, 0, 0)

    # ------------------------------------------------------------ RegisterHotKey
    def _loop(self) -> None:
        self._tid = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # cria a fila de mensagens da thread
        if not self._mouse and not user32.RegisterHotKey(None, ID_ATALHO, self.mods | MOD_NOREPEAT, self.vk):
            self._erro = f"erro {ctypes.get_last_error()} (atalho já em uso?)"
            self._tid = 0
            self._pronto.set()
            return
        self._pronto.set()
        esc_registrado = False
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == ID_ATALHO:
                    self._ao_apertar()
                elif msg.message == WM_HOTKEY and msg.wParam == ID_ESC:
                    self._chamar(self.on_cancelar)
                elif msg.message == WM_ESC_ON and not esc_registrado:
                    esc_registrado = bool(user32.RegisterHotKey(None, ID_ESC, MOD_NOREPEAT, VK_ESCAPE))
                    if not esc_registrado:
                        log.warning("Não consegui capturar o Esc (erro %d)", ctypes.get_last_error())
                elif msg.message == WM_ESC_OFF and esc_registrado:
                    user32.UnregisterHotKey(None, ID_ESC)
                    esc_registrado = False
        finally:
            if esc_registrado:
                user32.UnregisterHotKey(None, ID_ESC)
            if not self._mouse:
                user32.UnregisterHotKey(None, ID_ATALHO)

    # ------------------------------------------------------------ mouse (thread trabalhadora do gancho)
    def _mouse_apertar(self) -> None:
        if self.modo == "toggle":
            self._ao_apertar()
            return
        # push: o soltar vem do WM_XBUTTONUP (o botão engolido não aparece no GetAsyncKeyState)
        if self._push_ativo:
            return
        self._push_ativo = True
        _tecla_fantasma(self.mods)
        self._chamar(self.on_iniciar)

    def _mouse_soltar(self) -> None:
        if self.modo != "push" or not self._push_ativo:
            return
        self._push_ativo = False
        if self.esta_gravando():
            self._chamar(self.on_parar)

    # ------------------------------------------------------------ lógica comum
    def _chamar(self, fn) -> None:
        try:
            fn()
        except Exception:
            log.exception("Erro no callback do atalho")

    def _ao_apertar(self) -> None:
        _tecla_fantasma(self.mods)
        if self.modo == "toggle":
            self._chamar(self.on_parar if self.esta_gravando() else self.on_iniciar)
            return
        # push-to-talk
        if self._push_ativo:
            return
        self._push_ativo = True
        self._chamar(self.on_iniciar)
        threading.Thread(target=self._vigiar_soltura, daemon=True, name="gillevoz-push").start()

    def _segurando(self) -> bool:
        if self._usando_keyboard:
            # No fallback a lib bloqueia a tecla no hook, então GetAsyncKeyState não a vê;
            # usamos o rastreamento de teclas da própria lib.
            import keyboard

            try:
                return keyboard.is_pressed(self.atalho)
            except Exception:
                return False
        if not _pressionada(self.vk):
            return False
        for mod, vks in _VK_MODS.items():
            if self.mods & mod and not any(_pressionada(v) for v in vks):
                return False
        return True

    def _vigiar_soltura(self) -> None:
        try:
            time.sleep(0.03)
            while self._segurando():
                if not self.esta_gravando():  # cancelado com Esc enquanto segurava
                    return
                time.sleep(0.015)
            if self.esta_gravando():
                self._chamar(self.on_parar)
        finally:
            self._push_ativo = False

    # ------------------------------------------------------------ fallback: lib keyboard
    def _iniciar_keyboard(self) -> None:
        import keyboard

        self._usando_keyboard = True
        self._kb_hotkey = keyboard.add_hotkey(self.atalho, self._kb_ao_apertar, suppress=True,
                                              trigger_on_release=False)
        keyboard.hook(self._kb_filtro_esc, suppress=True)
        # Destrava quando a tecla principal for solta (equivalente ao MOD_NOREPEAT do caminho nativo).
        keyboard.hook(self._kb_soltura, suppress=False)
        log.info("Atalho global ativo via keyboard: %s (modo %s)", self.atalho, self.modo)

    def _kb_ao_apertar(self) -> None:
        """Ignora a repetição automática de tecla segurada: só dispara de novo após soltar."""
        if self._kb_travado:
            return
        self._kb_travado = True
        # Este callback roda dentro do hook de teclado: se demorar, o Windows remove o hook.
        threading.Thread(target=self._ao_apertar, daemon=True, name="gillevoz-atalho").start()

    def _kb_soltura(self, evento) -> None:
        if evento.event_type == "up" and self._kb_travado and self._kb_e_tecla_principal(evento):
            self._kb_travado = False

    def _kb_e_tecla_principal(self, evento) -> bool:
        import keyboard

        principal = self.atalho.replace(" ", "").split("+")[-1].lower()
        try:
            return not keyboard.is_pressed(principal)
        except Exception:
            return True

    def _kb_capturar_esc(self, ligar: bool) -> None:
        # Só liga/desliga uma flag; o hook bloqueante (instalado uma vez) decide na hora.
        self._kb_esc_ligado = ligar

    def _kb_filtro_esc(self, evento) -> bool:
        """Hook bloqueante da lib keyboard: devolver False bloqueia a tecla. Precisa ser rápido."""
        if evento.name not in ("esc", "escape"):
            return True
        if evento.event_type == "down":
            if not self._kb_esc_ligado:
                return True
            self._kb_esc_bloqueado = True
            threading.Thread(target=self._chamar, args=(self.on_cancelar,), daemon=True).start()
            return False
        # key up: bloqueia só se o down correspondente foi bloqueado
        if self._kb_esc_bloqueado:
            self._kb_esc_bloqueado = False
            return False
        return True


class AtalhoAcao:
    """Atalho global de uma ação só (ex.: colar a última transcrição).

    on_apertar() é chamado na thread do atalho: deve ser rápido (mande o trabalho para
    outra thread). start() levanta OSError se o Windows recusar o atalho (já em uso).
    """

    def __init__(self, atalho: str, on_apertar: Callable[[], None]):
        self.atalho = atalho
        self.on_apertar = on_apertar
        self.mods, self.vk = parse_atalho(atalho)
        self._mouse = parse_atalho_mouse(atalho)
        self._assinante: Assinante | None = None
        self._thread: threading.Thread | None = None
        self._tid = 0
        self._pronto = threading.Event()
        self._erro: str | None = None

    def _apertou(self) -> None:
        _tecla_fantasma(self.mods)
        try:
            self.on_apertar()
        except Exception:
            log.exception("Erro no callback do atalho %s", self.atalho)

    def start(self) -> None:
        if self._mouse:
            mods, botao = self._mouse
            a = Assinante(mods, botao, self._apertou)
            gancho_mouse().assinar(a)  # OSError se o Windows recusar
            self._assinante = a
            log.info("Atalho de ação ativo (mouse): %s", self.atalho)
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="gillevoz-atalho-acao")
        self._thread.start()
        self._pronto.wait(5)
        if self._erro:
            raise OSError(f"não consegui registrar o atalho '{self.atalho}': {self._erro}")
        log.info("Atalho de ação ativo: %s", self.atalho)

    def stop(self) -> None:
        if self._assinante is not None:
            gancho_mouse().cancelar(self._assinante)
            self._assinante = None
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(2)

    def _loop(self) -> None:
        self._tid = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # cria a fila de mensagens da thread
        if not user32.RegisterHotKey(None, ID_ATALHO, self.mods | MOD_NOREPEAT, self.vk):
            self._erro = f"erro {ctypes.get_last_error()} (atalho já em uso?)"
            self._tid = 0
            self._pronto.set()
            return
        self._pronto.set()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == ID_ATALHO:
                    self._apertou()
        finally:
            user32.UnregisterHotKey(None, ID_ATALHO)
