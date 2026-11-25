"""Flow Bar: barrinha flutuante sempre visível (estilo Flow Bar do Wispr Flow).

Win32 puro via ctypes, sem Tkinter. Regras para NÃO roubar o foco:
- Janela WS_POPUP com WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST.
  Fora da barra de tarefas e do Alt+Tab (TOOLWINDOW).
- WM_MOUSEACTIVATE responde MA_NOACTIVATE: clicar na barra não ativa a janela.
- Mostrar só com ShowWindow(SW_SHOWNOACTIVATE); mover só com SetWindowPos(SWP_NOACTIVATE).
- Nunca SetForegroundWindow, SetFocus ou TrackPopupMenu (o menu é próprio, sem ativação).
- Arrastar usa SetCapture, que não ativa a janela.

Threads: a janela e o loop de mensagens rodam numa thread própria. Os métodos públicos
só enfileiram comandos e avisam a janela com PostMessage (thread-safe). Os callbacks
(on_mic etc.) rodam numa thread de trabalho, para o clique nunca travar a fila de mensagens.
"""

import collections
import ctypes
import logging
import queue
import threading
import time
from ctypes import wintypes

log = logging.getLogger("gillevoz")

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

P = ctypes.c_void_p

# ---------- constantes Win32 ----------
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_ERASEBKGND = 0x0014
WM_PAINT = 0x000F
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_MOUSEACTIVATE = 0x0021
WM_CANCELMODE = 0x001F
WM_CAPTURECHANGED = 0x0215
WM_APP = 0x8000
WM_COMANDO = WM_APP + 1  # "há comandos na fila"
MA_NOACTIVATE = 3
MK_LBUTTON = 0x0001
WS_POPUP = 0x80000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SWP_NOACTIVATE = 0x0010
SPI_GETWORKAREA = 0x0030
MONITOR_DEFAULTTONEAREST = 2
SRCCOPY = 0x00CC0020
TRANSPARENT = 1
PS_SOLID = 0
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
DT_LEFT = 0x0000
DT_CENTER = 0x0001
DT_VCENTER = 0x0004
ANTIALIASED_QUALITY = 4
GLIFO_MIC = 0xE720   # Segoe Fluent Icons / Segoe MDL2 Assets
GLIFO_X = 0xE711
GLIFO_PARAR = 0xE71A
FONTES_ICONE = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
DT_SINGLELINE = 0x0020
FW_NORMAL = 400
HWND_TOPMOST = ctypes.c_void_p(-1)

TIMER_ANIMACAO = 1
TIMER_MENU = 2
TIMER_NO_TOPO = 3
INTERVALO_NO_TOPO_MS = 500  # outras janelas "sempre no topo" (ex.: Chrome PiP) podem cobrir a barra
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
INTERVALO_ANIMACAO_MS = 40
DISTANCIA_ARRASTE = 4  # px: acima disso é arraste, abaixo é clique

# ---------- cores (COLORREF = BBGGRR) ----------
def _cor(hex_rgb: str) -> int:
    r, g, b = int(hex_rgb[0:2], 16), int(hex_rgb[2:4], 16), int(hex_rgb[4:6], 16)
    return r | (g << 8) | (b << 16)


def _misturar(c1: int, c2: int, t: float) -> int:
    """Mistura duas cores: t=0 vira c1, t=1 vira c2."""
    out = 0
    for shift in (0, 8, 16):
        a = (c1 >> shift) & 0xFF
        b = (c2 >> shift) & 0xFF
        out |= int(a + (b - a) * t) << shift
    return out


FUNDO = _cor("0E0E0E")
TEXTO = _cor("E9E6E1")
LARANJA = _cor("FF4D12")
BORDA = _cor("2A2A2A")
DESTAQUE_MENU = _cor("1E1E1E")
ESMAECIDO = _misturar(TEXTO, FUNDO, 0.35)
TEXTO_MENU_DESLIGADO = _misturar(TEXTO, FUNDO, 0.6)

# ---------- tamanhos (px) ----------
TAM_OCIOSO = (52, 26)
TAM_GRAVANDO = (200, 32)
TAM_TRANSCREVENDO = (72, 26)
LARGURA_BOTAO = 32  # área clicável de X e ■ durante a gravação
N_BARRAS_ONDA = 26
ITEM_MENU_ALTURA = 24
MENU_LARGURA = 180
ITEMS_MENU = ["Esconder por 1 hora", "Configurações", "Sair"]


# ---------- estruturas ----------
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", P), ("fErase", wintypes.BOOL), ("rcPaint", RECT),
                ("fRestore", wintypes.BOOL), ("fIncUpdate", wintypes.BOOL),
                ("rgbReserved", ctypes.c_byte * 32)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", P), ("message", wintypes.UINT), ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM), ("time", wintypes.DWORD), ("pt", POINT)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, P, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", P), ("hIcon", P), ("hCursor", P), ("hbrBackground", P),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


# ---------- assinaturas (evitam truncar handles de 64 bits) ----------
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, P, P, P, P]
user32.CreateWindowExW.restype = P
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.DefWindowProcW.argtypes = [P, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), P, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.PostMessageW.argtypes = [P, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.DestroyWindow.argtypes = [P]
user32.ShowWindow.argtypes = [P, ctypes.c_int]
user32.SetWindowPos.argtypes = [P, P, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [P]
user32.GetWindowRect.argtypes = [P, ctypes.POINTER(RECT)]
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.SetCapture.argtypes = [P]
user32.SetCapture.restype = P
user32.ReleaseCapture.argtypes = []
user32.InvalidateRect.argtypes = [P, P, wintypes.BOOL]
user32.BeginPaint.argtypes = [P, ctypes.POINTER(PAINTSTRUCT)]
user32.BeginPaint.restype = P
user32.EndPaint.argtypes = [P, ctypes.POINTER(PAINTSTRUCT)]
user32.GetDC.argtypes = [P]
user32.GetDC.restype = P
user32.ReleaseDC.argtypes = [P, P]
user32.FillRect.argtypes = [P, ctypes.POINTER(RECT), P]
user32.FrameRect.argtypes = [P, ctypes.POINTER(RECT), P]
user32.DrawTextW.argtypes = [P, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(RECT), wintypes.UINT]
user32.SetTimer.argtypes = [P, ctypes.c_size_t, wintypes.UINT, P]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [P, ctypes.c_size_t]
user32.MonitorFromRect.argtypes = [ctypes.POINTER(RECT), wintypes.DWORD]
user32.MonitorFromRect.restype = P
user32.GetMonitorInfoW.argtypes = [P, ctypes.POINTER(MONITORINFO)]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, P, wintypes.UINT]
gdi32.CreateCompatibleDC.argtypes = [P]
gdi32.CreateCompatibleDC.restype = P
gdi32.CreateCompatibleBitmap.argtypes = [P, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = P
gdi32.SelectObject.argtypes = [P, P]
gdi32.SelectObject.restype = P
gdi32.DeleteObject.argtypes = [P]
gdi32.DeleteDC.argtypes = [P]
gdi32.BitBlt.argtypes = [P, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, P, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
gdi32.CreateSolidBrush.restype = P
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.CreatePen.restype = P
gdi32.MoveToEx.argtypes = [P, ctypes.c_int, ctypes.c_int, P]
gdi32.LineTo.argtypes = [P, ctypes.c_int, ctypes.c_int]
gdi32.SetBkMode.argtypes = [P, ctypes.c_int]
gdi32.SetTextColor.argtypes = [P, wintypes.DWORD]
gdi32.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
gdi32.CreateFontW.restype = P
gdi32.GetTextExtentPoint32W.argtypes = [P, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(SIZE)]
gdi32.GetTextFaceW.argtypes = [P, ctypes.c_int, wintypes.LPWSTR]

# Mapa hwnd -> (instância de FlowBar, "barra" ou "menu")
_janelas = {}
_registro_lock = threading.Lock()
_classes_ok = False


def _tratar(hwnd, msg, wp, lp, tipo):
    alvo = _janelas.get(hwnd)
    if alvo is not None and alvo[1] == tipo:
        resultado = alvo[0]._tratar_barra(msg, wp, lp) if tipo == "barra" \
            else alvo[0]._tratar_menu(msg, wp, lp)
        if resultado is not None:
            return resultado
    if msg == WM_CLOSE:
        user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_DESTROY:
        return 0
    return user32.DefWindowProcW(hwnd, msg, wp, lp)


@WNDPROC
def _proc_barra(hwnd, msg, wp, lp):
    return _tratar(hwnd, msg, wp, lp, "barra")


@WNDPROC
def _proc_menu(hwnd, msg, wp, lp):
    return _tratar(hwnd, msg, wp, lp, "menu")


def _registrar_classes() -> None:
    global _classes_ok
    with _registro_lock:
        if _classes_ok:
            return
        hinst = kernel32.GetModuleHandleW(None)
        for nome, proc in (("GilleVozFlowBar", _proc_barra), ("GilleVozFlowMenu", _proc_menu)):
            wc = WNDCLASSW()
            wc.lpfnWndProc = proc
            wc.hInstance = hinst
            wc.lpszClassName = nome
            if not user32.RegisterClassW(ctypes.byref(wc)):
                erro = ctypes.get_last_error()
                if erro != 1410:  # 1410 = a classe já existe
                    raise ctypes.WinError(erro)
        _classes_ok = True


def _clampear(x: int, y: int, w: int, h: int):
    """Mantém o retângulo dentro da área útil do monitor mais próximo (inclusive 2º monitor)."""
    rc = RECT(x, y, x + w, y + h)
    hmon = user32.MonitorFromRect(ctypes.byref(rc), MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
    t = mi.rcWork
    x = max(t.left, min(x, t.right - w))
    y = max(t.top, min(y, t.bottom - h))
    return x, y


def _area_util_primario():
    area = RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(area), 0)
    return area


def _pintar_com_buffer(hwnd, w: int, h: int, desenhar) -> None:
    """Desenha numa memória e copia de uma vez: sem piscar."""
    ps = PAINTSTRUCT()
    hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    antigo = gdi32.SelectObject(mem, bmp)
    desenhar(mem, w, h)
    gdi32.BitBlt(hdc, 0, 0, w, h, mem, 0, 0, SRCCOPY)
    gdi32.SelectObject(mem, antigo)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.EndPaint(hwnd, ctypes.byref(ps))


def _preencher(dc, x1, y1, x2, y2, cor) -> None:
    pincel = gdi32.CreateSolidBrush(cor)
    user32.FillRect(dc, ctypes.byref(RECT(x1, y1, x2, y2)), pincel)
    gdi32.DeleteObject(pincel)


def _linha(dc, x1, y1, x2, y2, cor, espessura=2) -> None:
    caneta = gdi32.CreatePen(PS_SOLID, espessura, cor)
    antiga = gdi32.SelectObject(dc, caneta)
    gdi32.MoveToEx(dc, x1, y1, None)
    gdi32.LineTo(dc, x2, y2)
    gdi32.SelectObject(dc, antiga)
    gdi32.DeleteObject(caneta)


def _criar_fonte_icones():
    """Cria a fonte de ícones UMA vez. Devolve (handle, nome) ou (None, None).

    Windows troca fonte inexistente por outra (ex.: Arial). Por isso conferimos o nome
    real da fonte criada e só aceitamos se for a pedida.
    """
    dc = user32.GetDC(None)
    try:
        for nome in FONTES_ICONE:
            fonte = gdi32.CreateFontW(-16, 0, 0, 0, FW_NORMAL, 0, 0, 0, 1, 0, 0,
                                      ANTIALIASED_QUALITY, 0, nome)
            antiga = gdi32.SelectObject(dc, fonte)
            real = ctypes.create_unicode_buffer(64)
            gdi32.GetTextFaceW(dc, 64, real)
            gdi32.SelectObject(dc, antiga)
            if real.value.lower() == nome.lower():
                return fonte, nome
            gdi32.DeleteObject(fonte)
        return None, None
    finally:
        user32.ReleaseDC(None, dc)


def _desenhar_glifo(dc, fonte, codigo: int, x0: int, y0: int, x1: int, y1: int, cor: int) -> bool:
    """Desenha um glifo centralizado no retângulo. Devolve False se não há fonte de ícones."""
    if not fonte:
        return False
    antiga = gdi32.SelectObject(dc, fonte)
    gdi32.SetTextColor(dc, cor)
    gdi32.SetBkMode(dc, TRANSPARENT)
    rc = RECT(x0, y0, x1, y1)
    user32.DrawTextW(dc, chr(codigo), 1, ctypes.byref(rc), DT_CENTER | DT_VCENTER | DT_SINGLELINE)
    gdi32.SelectObject(dc, antiga)
    return True


def _desenhar_mic(dc, cx: int, cy: int, cor: int) -> None:
    """Microfone feito com retângulos e linhas (sem depender de fonte de ícones)."""
    _preencher(dc, cx - 3, cy - 7, cx + 3, cy + 2, cor)   # cápsula
    _linha(dc, cx - 6, cy - 1, cx - 6, cy + 3, cor)       # suporte em U
    _linha(dc, cx - 6, cy + 3, cx + 6, cy + 3, cor)
    _linha(dc, cx + 6, cy + 3, cx + 6, cy - 1, cor)
    _linha(dc, cx, cy + 3, cx, cy + 7, cor)               # haste
    _linha(dc, cx - 3, cy + 7, cx + 3, cy + 7, cor)       # base


class FlowBar:
    """Barrinha flutuante. Contrato em docs/ARQUITETURA.md (seção Flow Bar)."""

    def __init__(self, on_mic, on_parar, on_cancelar, on_config, on_sair, on_mover, posicao=None):
        self._on_mic = on_mic
        self._on_parar = on_parar
        self._on_cancelar = on_cancelar
        self._on_config = on_config
        self._on_sair = on_sair
        self._on_mover = on_mover
        self._posicao = tuple(posicao) if posicao else None

        self._lock = threading.RLock()  # protege estado de ciclo de vida, ondas e timer
        self._encerrada = False  # depois de stop(): nada mais é enfileirado nem reiniciado
        self._erro_start = None  # erro de criação da janela, levantado por start()
        self._visivel = True
        self._estado = "ocioso"  # só a thread da UI altera; vem da ordem da fila de comandos
        self._ondas = collections.deque([0.0] * N_BARRAS_ONDA, maxlen=N_BARRAS_ONDA)
        self._tick = 0

        self._thread = None
        self._pronto = threading.Event()
        self._fila = queue.Queue()
        self._fila_cb = queue.Queue()
        self._hwnd = None
        self._menu = None
        self._menu_hover = -1
        self._menu_aberto = False
        self._fonte = None
        self._fonte_menu = None
        self._fonte_icone = None  # criada uma vez em _run; None = usar formas desenhadas
        self.fonte_icone_usada = None  # nome da fonte de ícones em uso (para diagnóstico)
        self._largura, self._altura = TAM_OCIOSO
        self._arraste = None  # (cursor_inicial, pos_janela_inicial, arrastou?)
        self._timer_ocultar = None

    # ================= API pública (qualquer thread) =================
    def start(self) -> None:
        """Cria a janela e espera ficar pronta. Levanta OSError se a janela não puder ser criada.

        Chamadas concorrentes esperam o mesmo início (uma única thread é criada).
        """
        with self._lock:
            if self._encerrada:
                raise RuntimeError("FlowBar já foi encerrada; crie outra instância")
            if self._thread and self._thread.is_alive():
                pronto = self._pronto
            else:
                self._pronto = threading.Event()
                self._erro_start = None
                pronto = self._pronto
                self._thread = threading.Thread(target=self._run, name="gillevoz-flowbar", daemon=True)
                threading.Thread(target=self._trabalhador_cb, name="gillevoz-flowbar-cb", daemon=True).start()
                self._thread.start()
        if not pronto.wait(5):
            raise TimeoutError("Flow Bar não ficou pronta em 5 s")
        if self._erro_start is not None:
            with self._lock:
                self._encerrada = True
            self._fila_cb.put(None)  # encerra o trabalhador de callbacks
            raise self._erro_start

    def stop(self) -> None:
        with self._lock:
            self._encerrada = True
            # Um "esconder por 1 hora" pendente não pode reabrir a barra depois do stop.
            if self._timer_ocultar is not None:
                self._timer_ocultar.cancel()
            vivo = self._thread is not None and self._thread.is_alive()
        if vivo:
            self._enfileirar(("stop", None), forcar=True)
            self._thread.join(3)
        self._fila_cb.put(None)

    def set_state(self, estado: str) -> None:
        if estado not in ("ocioso", "gravando", "transcrevendo", "pausado"):
            raise ValueError(f"estado desconhecido: {estado!r}")
        # Sem mudar _estado aqui: a ordem de chegada na fila é a verdade, e a UI aplica em ordem.
        self._enfileirar(("estado", estado))

    def set_level(self, nivel: float) -> None:
        """Nível 0..1 do áudio. Chamado ~30x/s durante a gravação; só guarda o valor."""
        nivel = max(0.0, min(1.0, float(nivel)))
        with self._lock:
            self._ondas.append(nivel)

    def esconder_por(self, segundos: float) -> None:
        self._enfileirar(("esconder", float(segundos)))

    def mostrar(self) -> None:
        self._enfileirar(("mostrar", None))

    # ================= interno: comunicação entre threads =================
    def _enfileirar(self, comando: tuple, forcar: bool = False) -> None:
        """Põe o comando na fila e acorda a janela. Depois de encerrada, não faz nada
        (exceto o próprio "stop", com forcar=True)."""
        with self._lock:
            if self._encerrada and not forcar:
                return
            precisa_iniciar = not (self._thread and self._thread.is_alive())
        if precisa_iniciar and not forcar:
            self.start()
        self._fila.put(comando)
        # Se a janela ainda não existe, o comando fica na fila e _run o drena ao ficar pronta.
        hwnd = self._hwnd
        if hwnd is not None:
            user32.PostMessageW(hwnd, WM_COMANDO, 0, 0)

    def _disparar(self, nome: str) -> None:
        """Manda o callback para a thread de trabalho (não bloqueia a janela)."""
        self._fila_cb.put(nome)

    def _trabalhador_cb(self) -> None:
        mapa = {
            "on_mic": lambda: self._on_mic(),
            "on_parar": lambda: self._on_parar(),
            "on_cancelar": lambda: self._on_cancelar(),
            "on_config": lambda: self._on_config(),
            "on_sair": lambda: self._on_sair(),
        }
        while True:
            item = self._fila_cb.get()
            if item is None:
                return
            try:
                if isinstance(item, tuple):  # ("on_mover", (x, y))
                    if self._on_mover:
                        self._on_mover(*item[1])
                elif item in mapa and mapa[item] is not None:
                    mapa[item]()
            except Exception:
                log.exception("Flow Bar: erro no callback %s", item)

    # ================= thread da janela =================
    def _run(self) -> None:
        try:
            self._preparar_janela()
        except Exception as erro:
            # Não levanta na thread (o app não veria): guarda e start() levanta para quem chamou.
            self._erro_start = erro
            self._pronto.set()
            return
        self._pronto.set()
        # Drena comandos que chegaram durante a criação (antes de existir HWND para acordar).
        self._processar_fila()

        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._menu:
            _janelas.pop(self._menu, None)
            user32.DestroyWindow(self._menu)
        _janelas.pop(self._hwnd, None)
        gdi32.DeleteObject(self._fonte)
        gdi32.DeleteObject(self._fonte_menu)
        if self._fonte_icone:
            gdi32.DeleteObject(self._fonte_icone)
            self._fonte_icone = None
        self._hwnd = None

    def _preparar_janela(self) -> None:
        _registrar_classes()
        hinst = kernel32.GetModuleHandleW(None)
        w, h = TAM_OCIOSO
        x, y = self._posicao_inicial(w, h)
        hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST, "GilleVozFlowBar", "",
            WS_POPUP, x, y, w, h, None, None, hinst, None)
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._hwnd = hwnd  # publicado ANTES de drenar a fila (ver _enfileirar)
        _janelas[hwnd] = (self, "barra")
        user32.SetTimer(hwnd, TIMER_NO_TOPO, INTERVALO_NO_TOPO_MS, None)
        self._fonte = gdi32.CreateFontW(-15, 0, 0, 0, 700, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI")
        self._fonte_menu = gdi32.CreateFontW(-14, 0, 0, 0, FW_NORMAL, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI")
        self._fonte_icone, self.fonte_icone_usada = _criar_fonte_icones()
        self._mostrar_sem_ativar(x, y, w, h)

    def _posicao_inicial(self, w: int, h: int):
        if self._posicao:
            return _clampear(self._posicao[0], self._posicao[1], w, h)
        area = _area_util_primario()
        x = area.left + (area.right - area.left - w) // 2
        y = area.bottom - h - 16
        return x, y

    def _mostrar_sem_ativar(self, x, y, w, h) -> None:
        user32.SetWindowPos(self._hwnd, HWND_TOPMOST, x, y, w, h, SWP_NOACTIVATE)
        user32.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)

    # ---------- mensagens da barra ----------
    def _tratar_barra(self, msg, wp, lp):
        if msg == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_PAINT:
            _pintar_com_buffer(self._hwnd, self._largura, self._altura, self._desenhar_barra)
            return 0
        if msg == WM_COMANDO:
            self._processar_fila()
            return 0
        if msg == WM_TIMER and wp == TIMER_ANIMACAO:
            self._tick += 1
            user32.InvalidateRect(self._hwnd, None, False)
            return 0
        if msg == WM_TIMER and wp == TIMER_NO_TOPO:
            self._garantir_no_topo()
            return 0
        if msg == WM_LBUTTONDOWN:
            self._inicio_arraste(lp)
            return 0
        if msg == WM_MOUSEMOVE:
            self._mover_arraste(wp)
            return 0
        if msg == WM_LBUTTONUP:
            self._fim_clique_ou_arraste(lp)
            return 0
        if msg in (WM_CAPTURECHANGED, WM_CANCELMODE):
            # Perdemos o mouse (outra janela capturou ou o sistema cancelou): o button-up
            # pode nunca chegar aqui, então encerramos o arraste agora.
            self._cancelar_arraste()
            return 0
        if msg == WM_RBUTTONUP:
            ponto = POINT()
            user32.GetCursorPos(ctypes.byref(ponto))
            self._abrir_menu(ponto.x, ponto.y)
            return 0
        return None

    def _garantir_no_topo(self) -> None:
        """Reafirma a barra no topo do grupo "sempre no topo", sem ativar nem mover.

        Só mexe na ordem Z quando a barra está visível e o menu não está aberto.
        """
        if not user32.IsWindowVisible(self._hwnd) or self._menu_aberto:
            return
        user32.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def _inicio_arraste(self, lp) -> None:
        cursor = POINT()
        user32.GetCursorPos(ctypes.byref(cursor))
        rc = RECT()
        user32.GetWindowRect(self._hwnd, ctypes.byref(rc))
        self._arraste = {"cursor": (cursor.x, cursor.y), "janela": (rc.left, rc.top), "arrastou": False}
        user32.SetCapture(self._hwnd)  # captura o mouse sem ativar a janela

    def _mover_arraste(self, wp) -> None:
        if not self._arraste or not (wp & MK_LBUTTON):
            return
        cursor = POINT()
        user32.GetCursorPos(ctypes.byref(cursor))
        dx = cursor.x - self._arraste["cursor"][0]
        dy = cursor.y - self._arraste["cursor"][1]
        if not self._arraste["arrastou"]:
            if max(abs(dx), abs(dy)) <= DISTANCIA_ARRASTE:
                return
            self._arraste["arrastou"] = True
        x, y = _clampear(self._arraste["janela"][0] + dx, self._arraste["janela"][1] + dy,
                         self._largura, self._altura)
        user32.SetWindowPos(self._hwnd, HWND_TOPMOST, x, y, self._largura, self._altura, SWP_NOACTIVATE)

    def _cancelar_arraste(self) -> None:
        """Encerra o arraste sem depender do button-up. Se já tinha arrastado, salva a posição."""
        arraste = self._arraste
        self._arraste = None
        if not arraste or not arraste["arrastou"] or not self._hwnd:
            return
        rc = RECT()
        user32.GetWindowRect(self._hwnd, ctypes.byref(rc))
        x, y = _clampear(rc.left, rc.top, self._largura, self._altura)
        self._disparar(("on_mover", (x, y)))

    def _fim_clique_ou_arraste(self, lp) -> None:
        arraste = self._arraste
        self._arraste = None
        user32.ReleaseCapture()
        if arraste is None:
            return
        if arraste["arrastou"]:
            rc = RECT()
            user32.GetWindowRect(self._hwnd, ctypes.byref(rc))
            x, y = _clampear(rc.left, rc.top, self._largura, self._altura)
            if (x, y) != (rc.left, rc.top):
                user32.SetWindowPos(self._hwnd, HWND_TOPMOST, x, y, self._largura, self._altura,
                                    SWP_NOACTIVATE)
            self._disparar(("on_mover", (x, y)))
            return
        self._clique((lp & 0xFFFF))

    def _clique(self, x_cliente: int) -> None:
        """Clique sem arraste: decide a ação pelo estado e pela posição do clique."""
        with self._lock:
            estado = self._estado
        if estado == "ocioso":
            self._disparar("on_mic")
        elif estado == "gravando":
            if x_cliente < LARGURA_BOTAO:
                self._disparar("on_cancelar")          # X
            elif x_cliente >= self._largura - LARGURA_BOTAO:
                self._disparar("on_parar")             # ■
        # pausado e transcrevendo: o clique não faz nada

    def _processar_fila(self) -> None:
        while True:
            try:
                cmd, valor = self._fila.get_nowait()
            except queue.Empty:
                return
            if cmd == "estado":
                self._estado = valor  # a UI é a dona do estado: aplica na ordem em que chegou
                self._aplicar_estado(valor)
            elif cmd == "esconder":
                self._esconder(valor)
            elif cmd == "mostrar":
                self._cancelar_timer_ocultar()
                self._mostrar_atual()
            elif cmd == "stop":
                if self._menu:
                    user32.DestroyWindow(self._menu)
                user32.DestroyWindow(self._hwnd)
                user32.PostQuitMessage(0)  # encerra o loop de mensagens da thread
                return

    def _aplicar_estado(self, estado: str) -> None:
        """Muda o tamanho e liga/desliga a animação. Ancora no canto superior esquerdo."""
        if estado == "gravando":
            w, h = TAM_GRAVANDO
        elif estado == "transcrevendo":
            w, h = TAM_TRANSCREVENDO
        else:
            w, h = TAM_OCIOSO
        rc = RECT()
        user32.GetWindowRect(self._hwnd, ctypes.byref(rc))
        x, y = _clampear(rc.left, rc.top, w, h)
        self._largura, self._altura = w, h
        user32.SetWindowPos(self._hwnd, HWND_TOPMOST, x, y, w, h, SWP_NOACTIVATE)
        self._ligar_animacao(estado in ("gravando", "transcrevendo") and self._visivel)
        user32.InvalidateRect(self._hwnd, None, False)

    def _ligar_animacao(self, ligar: bool) -> None:
        """Animação só roda com a barra visível (escondida não gasta timer nem repaint)."""
        if ligar:
            user32.SetTimer(self._hwnd, TIMER_ANIMACAO, INTERVALO_ANIMACAO_MS, None)
        else:
            user32.KillTimer(self._hwnd, TIMER_ANIMACAO)

    def _esconder(self, segundos: float) -> None:
        with self._lock:
            if self._encerrada:
                return
        self._visivel = False
        user32.ShowWindow(self._hwnd, SW_HIDE)
        self._ligar_animacao(False)
        if self._menu_aberto:
            self._fechar_menu()
        self._cancelar_timer_ocultar()
        with self._lock:
            if self._encerrada:
                return
            self._timer_ocultar = threading.Timer(segundos, self.mostrar)
            self._timer_ocultar.daemon = True
            self._timer_ocultar.start()

    def _cancelar_timer_ocultar(self) -> None:
        with self._lock:
            if self._timer_ocultar:
                self._timer_ocultar.cancel()
                self._timer_ocultar = None

    def _mostrar_atual(self) -> None:
        rc = RECT()
        user32.GetWindowRect(self._hwnd, ctypes.byref(rc))
        x, y = _clampear(rc.left, rc.top, self._largura, self._altura)
        self._visivel = True
        self._mostrar_sem_ativar(x, y, self._largura, self._altura)
        # Retoma a animação se o estado pede (ficou suspensa enquanto escondida)
        self._ligar_animacao(self._estado in ("gravando", "transcrevendo"))

    # ---------- desenho da barra ----------
    def _desenhar_barra(self, dc, w: int, h: int) -> None:
        with self._lock:
            estado = self._estado
            ondas = list(self._ondas)
            tick = self._tick
        _preencher(dc, 0, 0, w, h, FUNDO)
        rc = RECT(0, 0, w, h)
        pincel = gdi32.CreateSolidBrush(BORDA)
        user32.FrameRect(dc, ctypes.byref(rc), pincel)
        gdi32.DeleteObject(pincel)

        cy = h // 2
        fonte = self._fonte_icone
        if estado in ("ocioso", "pausado"):
            cor = TEXTO if estado == "ocioso" else ESMAECIDO
            if not _desenhar_glifo(dc, fonte, GLIFO_MIC, 0, 0, w, h, cor):
                _desenhar_mic(dc, w // 2, cy, cor)
        elif estado == "gravando":
            # X cancelar (área do botão à esquerda) e ■ parar (à direita)
            if not _desenhar_glifo(dc, fonte, GLIFO_X, 0, 0, LARGURA_BOTAO, h, TEXTO):
                _linha(dc, 11, cy - 5, 21, cy + 5, TEXTO)
                _linha(dc, 21, cy - 5, 11, cy + 5, TEXTO)
            if not _desenhar_glifo(dc, fonte, GLIFO_PARAR, w - LARGURA_BOTAO, 0, w, h, TEXTO):
                _preencher(dc, w - 21, cy - 5, w - 11, cy + 5, TEXTO)
            self._desenhar_ondas(dc, w, h, ondas)
        elif estado == "transcrevendo":
            ativo = (tick // 3) % 3  # um ponto "aceso" por vez, andando
            for i in range(3):
                cor = TEXTO if i == ativo else ESMAECIDO
                x0 = w // 2 - 11 + i * 9
                _preencher(dc, x0, cy - 2, x0 + 4, cy + 2, cor)

    def _desenhar_ondas(self, dc, w: int, h: int, ondas) -> None:
        area_x0 = LARGURA_BOTAO
        area_x1 = w - LARGURA_BOTAO
        passo = (area_x1 - area_x0) / N_BARRAS_ONDA
        altura_max = h - 10
        cy = h // 2
        for i, nivel in enumerate(ondas):
            altura = max(2, int(nivel * altura_max))
            x0 = int(area_x0 + i * passo + 1)
            x1 = x0 + max(2, int(passo) - 3)
            _preencher(dc, x0, cy - altura // 2, x1, cy - altura // 2 + altura, LARANJA)

    # ================= menu do clique direito (próprio, sem ativação) =================
    def _abrir_menu(self, x_tela: int, y_tela: int) -> None:
        if self._menu is None:
            self._menu = user32.CreateWindowExW(
                WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST, "GilleVozFlowMenu", "",
                WS_POPUP, 0, 0, 10, 10, None, None, kernel32.GetModuleHandleW(None), None)
            _janelas[self._menu] = (self, "menu")
        altura = ITEM_MENU_ALTURA * len(ITEMS_MENU) + 8
        x, y = _clampear(x_tela, y_tela - altura, MENU_LARGURA, altura)
        user32.SetWindowPos(self._menu, HWND_TOPMOST, x, y, MENU_LARGURA, altura, SWP_NOACTIVATE)
        user32.ShowWindow(self._menu, SW_SHOWNOACTIVATE)
        self._menu_aberto = True
        self._menu_hover = -1
        user32.SetTimer(self._menu, TIMER_MENU, 60, None)  # fecha se clicar fora
        user32.InvalidateRect(self._menu, None, False)

    def _fechar_menu(self) -> None:
        if self._menu:
            user32.KillTimer(self._menu, TIMER_MENU)
            user32.ShowWindow(self._menu, SW_HIDE)
        self._menu_aberto = False

    def _tratar_menu(self, msg, wp, lp):
        if msg == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        if msg == WM_ERASEBKGND:
            return 1
        altura = ITEM_MENU_ALTURA * len(ITEMS_MENU) + 8
        if msg == WM_PAINT:
            _pintar_com_buffer(self._menu, MENU_LARGURA, altura, self._desenhar_menu)
            return 0
        if msg == WM_MOUSEMOVE:
            y = (lp >> 16) & 0xFFFF
            idx = self._item_em(y)
            if idx != self._menu_hover:
                self._menu_hover = idx
                user32.InvalidateRect(self._menu, None, False)
            return 0
        if msg == WM_LBUTTONUP:
            y = (lp >> 16) & 0xFFFF
            idx = self._item_em(y)
            self._fechar_menu()
            if idx == 0:
                self.esconder_por(3600)
            elif idx == 1:
                self._disparar("on_config")
            elif idx == 2:
                self._disparar("on_sair")
            return 0
        if msg == WM_TIMER and wp == TIMER_MENU:
            self._checar_clique_fora()
            return 0
        return None

    def _item_em(self, y: int) -> int:
        idx = (y - 4) // ITEM_MENU_ALTURA
        return idx if 0 <= idx < len(ITEMS_MENU) and y >= 4 else -1

    def _checar_clique_fora(self) -> None:
        apertado = (user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000) or \
                   (user32.GetAsyncKeyState(VK_RBUTTON) & 0x8000)
        if not apertado:
            return
        cursor = POINT()
        user32.GetCursorPos(ctypes.byref(cursor))
        rc = RECT()
        user32.GetWindowRect(self._menu, ctypes.byref(rc))
        dentro = rc.left <= cursor.x < rc.right and rc.top <= cursor.y < rc.bottom
        if not dentro:
            self._fechar_menu()

    def _desenhar_menu(self, dc, w: int, h: int) -> None:
        _preencher(dc, 0, 0, w, h, FUNDO)
        rc = RECT(0, 0, w, h)
        pincel = gdi32.CreateSolidBrush(BORDA)
        user32.FrameRect(dc, ctypes.byref(rc), pincel)
        gdi32.DeleteObject(pincel)
        antiga = gdi32.SelectObject(dc, self._fonte_menu)
        gdi32.SetBkMode(dc, TRANSPARENT)
        for i, texto in enumerate(ITEMS_MENU):
            y0 = 4 + i * ITEM_MENU_ALTURA
            if i == self._menu_hover:
                _preencher(dc, 2, y0, w - 2, y0 + ITEM_MENU_ALTURA, DESTAQUE_MENU)
            gdi32.SetTextColor(dc, TEXTO)
            texto_rc = RECT(12, y0, w - 8, y0 + ITEM_MENU_ALTURA)
            user32.DrawTextW(dc, texto, -1, ctypes.byref(texto_rc), DT_LEFT | DT_VCENTER | DT_SINGLELINE)
        gdi32.SelectObject(dc, antiga)
