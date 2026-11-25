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
"""
from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import wintypes
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


def parse_atalho(atalho: str) -> tuple[int, int]:
    """'ctrl+alt+space' -> (mods, vk). Levanta ValueError se não entender."""
    partes = [p.strip().lower() for p in atalho.replace(" ", "").split("+") if p.strip()]
    mods, vk = 0, None
    for p in partes:
        if p in _MODS:
            mods |= _MODS[p]
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


def validar_atalho(atalho) -> str | None:
    """Devolve uma mensagem de erro (pt-BR) se o atalho não serve, ou None se está ok.

    Recusa vazio/não-texto, tecla desconhecida e combinação só de modificadores
    (todo atalho precisa de uma tecla comum, para usar sempre o RegisterHotKey).
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
        self._thread = threading.Thread(target=self._loop, daemon=True, name="gillevoz-hotkey")
        self._thread.start()
        self._pronto.wait(5)
        if self._erro:
            log.warning("RegisterHotKey falhou (%s); usando a lib keyboard como alternativa.", self._erro)
            self._iniciar_keyboard()
        else:
            log.info("Atalho global ativo: %s (modo %s)", self.atalho, self.modo)

    def stop(self) -> None:
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
        if not user32.RegisterHotKey(None, ID_ATALHO, self.mods | MOD_NOREPEAT, self.vk):
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
            user32.UnregisterHotKey(None, ID_ATALHO)

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
        self._thread: threading.Thread | None = None
        self._tid = 0
        self._pronto = threading.Event()
        self._erro: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True, name="gillevoz-atalho-acao")
        self._thread.start()
        self._pronto.wait(5)
        if self._erro:
            raise OSError(f"não consegui registrar o atalho '{self.atalho}': {self._erro}")
        log.info("Atalho de ação ativo: %s", self.atalho)

    def stop(self) -> None:
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
                    _tecla_fantasma(self.mods)
                    try:
                        self.on_apertar()
                    except Exception:
                        log.exception("Erro no callback do atalho %s", self.atalho)
        finally:
            user32.UnregisterHotKey(None, ID_ATALHO)
