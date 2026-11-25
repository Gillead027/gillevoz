"""Indicador de gravação: uma pílula pequena no canto inferior central da tela.

Feito com a API do Windows (ctypes), SEM Tkinter. Motivo: a primeira criação do Tk no
processo ativa a janela e rouba o foco por alguns milissegundos (medido). Uma janela Win32
criada já com WS_EX_NOACTIVATE não rouba o foco (medido).

Regras para NÃO roubar o foco:
- A janela nasce com WS_EX_NOACTIVATE + WS_EX_TOOLWINDOW + WS_EX_TOPMOST e escondida.
- Só show() mostra, via ShowWindow(SW_SHOWNOACTIVATE). Posiciona com SetWindowPos(SWP_NOACTIVATE).
- Nunca chamamos SetForegroundWindow, SetFocus, SW_SHOW ou ativação de qualquer tipo.

Thread: a janela e a fila de mensagens ficam numa thread própria. Os métodos públicos
só enfileiram um comando e avisam a janela com PostMessage; então podem ser chamados
de qualquer thread.
"""

import ctypes
import queue
import threading
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Constantes da API do Windows
WM_PAINT = 0x000F
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_APP = 0x8000
WM_COMANDO = WM_APP + 1  # "há comandos na fila"
WS_POPUP = 0x80000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SWP_NOACTIVATE = 0x0010
SPI_GETWORKAREA = 0x0030
DT_CENTER = 0x0001
DT_VCENTER = 0x0004
DT_SINGLELINE = 0x0020
TRANSPARENT = 1
FW_BOLD = 700
ERROR_CLASS_ALREADY_EXISTS = 1410
HWND_TOPMOST = ctypes.c_void_p(-1)

COR_FUNDO = 0x242120  # COLORREF (BBGGRR) de #202120
COR_TEXTO = 0x00FFFFFF
TEXTO_PADRAO = "● gravando"
MARGEM_INFERIOR = 24  # distância da barra de tarefas (px)
CLASSE = "GilleVozIndicador"


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", ctypes.c_void_p), ("fErase", wintypes.BOOL), ("rcPaint", RECT),
                ("fRestore", wintypes.BOOL), ("fIncUpdate", wintypes.BOOL),
                ("rgbReserved", ctypes.c_byte * 32)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt", POINT)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


# Tipos explícitos (evitam truncar handles de 64 bits)
P = ctypes.c_void_p
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
user32.SetWindowPos.argtypes = [P, P, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, wintypes.UINT]
user32.SetWindowRgn.argtypes = [P, P, wintypes.BOOL]
user32.GetDC.argtypes = [P]
user32.GetDC.restype = P
user32.ReleaseDC.argtypes = [P, P]
user32.BeginPaint.argtypes = [P, ctypes.POINTER(PAINTSTRUCT)]
user32.BeginPaint.restype = P
user32.EndPaint.argtypes = [P, ctypes.POINTER(PAINTSTRUCT)]
user32.FillRect.argtypes = [P, ctypes.POINTER(RECT), P]
user32.DrawTextW.argtypes = [P, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(RECT), wintypes.UINT]
user32.InvalidateRect.argtypes = [P, P, wintypes.BOOL]
user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, P, wintypes.UINT]
# CreateFontW: 5 inteiros (altura..peso), 8 DWORDs (itálico..paso), 1 texto (nome da fonte)
gdi32.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
gdi32.CreateFontW.restype = P
gdi32.SelectObject.argtypes = [P, P]
gdi32.SelectObject.restype = P
gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
gdi32.CreateSolidBrush.restype = P
gdi32.DeleteObject.argtypes = [P]
gdi32.SetBkMode.argtypes = [P, ctypes.c_int]
gdi32.SetTextColor.argtypes = [P, wintypes.DWORD]
gdi32.GetTextExtentPoint32W.argtypes = [P, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(SIZE)]
gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
gdi32.CreateRoundRectRgn.restype = P

# Mapa hwnd -> Indicator, para a função de janela (comum a todas as instâncias)
_instancias = {}
_registro_lock = threading.Lock()
_classe_registrada = False


@WNDPROC
def _wndproc(hwnd, msg, wparam, lparam):
    inst = _instancias.get(hwnd)
    if inst is not None:
        if msg == WM_COMANDO:
            inst._processar_fila()
            return 0
        if msg == WM_PAINT:
            inst._pintar()
            return 0
    if msg == WM_CLOSE:
        user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _registrar_classe() -> None:
    global _classe_registrada
    with _registro_lock:
        if _classe_registrada:
            return
        wc = WNDCLASSW()
        wc.lpfnWndProc = _wndproc
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = CLASSE
        if not user32.RegisterClassW(ctypes.byref(wc)):
            if ctypes.get_last_error() != ERROR_CLASS_ALREADY_EXISTS:
                raise ctypes.WinError(ctypes.get_last_error())
        _classe_registrada = True


class Indicator:
    def __init__(self):
        self._fila: "queue.Queue[tuple]" = queue.Queue()
        self._thread = None
        self._pronto = threading.Event()
        self._hwnd = None
        self._fonte = None
        self._texto = TEXTO_PADRAO
        self._largura = 0
        self._altura = 0
        self._visivel = False

    # ---------- API pública (qualquer thread) ----------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._pronto.clear()
        self._thread = threading.Thread(target=self._run, name="gillevoz-indicador", daemon=True)
        self._thread.start()
        self._pronto.wait(5)

    def show(self, texto: str = TEXTO_PADRAO) -> None:
        self._enfileirar(("show", texto))

    def set_text(self, texto: str) -> None:
        self._enfileirar(("text", texto))

    def hide(self) -> None:
        self._enfileirar(("hide", None))

    def stop(self) -> None:
        if not (self._thread and self._thread.is_alive()):
            return
        self._enfileirar(("stop", None))
        self._thread.join(3)

    # ---------- interno ----------
    def _enfileirar(self, comando: tuple) -> None:
        if not (self._thread and self._thread.is_alive()):
            self.start()
        self._fila.put(comando)
        user32.PostMessageW(self._hwnd, WM_COMANDO, 0, 0)

    def _run(self) -> None:
        _registrar_classe()
        # Nasce escondida (sem WS_VISIBLE) e já com os estilos de não-ativação.
        hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST, CLASSE, "",
            WS_POPUP, 0, 0, 10, 10, None, None, kernel32.GetModuleHandleW(None), None,
        )
        if not hwnd:
            self._pronto.set()
            raise ctypes.WinError(ctypes.get_last_error())
        self._hwnd = hwnd
        _instancias[hwnd] = self
        # Fonte "Segoe UI" 11 pt em negrito (altura -15 px a 96 DPI)
        self._fonte = gdi32.CreateFontW(-15, 0, 0, 0, FW_BOLD, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI")
        self._pronto.set()

        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        _instancias.pop(hwnd, None)
        gdi32.DeleteObject(self._fonte)
        self._fonte = None
        self._hwnd = None

    def _processar_fila(self) -> None:
        """Roda na thread da janela. Executa os comandos que chegaram."""
        while True:
            try:
                cmd, valor = self._fila.get_nowait()
            except queue.Empty:
                return
            if cmd == "show":
                self._texto = valor
                self._medir()
                self._posicionar()
                user32.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)
                self._visivel = True
                user32.InvalidateRect(self._hwnd, None, True)
            elif cmd == "text":
                self._texto = valor
                self._medir()
                if self._visivel:
                    self._posicionar()
                    user32.InvalidateRect(self._hwnd, None, True)
            elif cmd == "hide":
                user32.ShowWindow(self._hwnd, SW_HIDE)
                self._visivel = False
            elif cmd == "stop":
                user32.DestroyWindow(self._hwnd)  # dispara WM_DESTROY e encerra a thread
                return

    def _medir(self) -> None:
        """Mede o texto para dimensionar a pílula."""
        hdc = user32.GetDC(self._hwnd)
        antiga = gdi32.SelectObject(hdc, self._fonte)
        tamanho = SIZE()
        gdi32.GetTextExtentPoint32W(hdc, self._texto, len(self._texto), ctypes.byref(tamanho))
        gdi32.SelectObject(hdc, antiga)
        user32.ReleaseDC(self._hwnd, hdc)
        self._largura = tamanho.cx + 32  # 16 px de cada lado
        self._altura = tamanho.cy + 12

    def _posicionar(self) -> None:
        """Canto inferior central, acima da barra de tarefas, com cantos arredondados."""
        area = RECT()  # área útil da tela (sem a barra de tarefas)
        user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(area), 0)
        x = area.left + (area.right - area.left - self._largura) // 2
        y = area.bottom - self._altura - MARGEM_INFERIOR
        user32.SetWindowPos(self._hwnd, HWND_TOPMOST, x, y, self._largura, self._altura,
                            SWP_NOACTIVATE)
        regiao = gdi32.CreateRoundRectRgn(0, 0, self._largura + 1, self._altura + 1,
                                          self._altura, self._altura)
        user32.SetWindowRgn(self._hwnd, regiao, True)  # a janela passa a ser dona da região

    def _pintar(self) -> None:
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(self._hwnd, ctypes.byref(ps))
        area = RECT(0, 0, self._largura, self._altura)
        pincel = gdi32.CreateSolidBrush(COR_FUNDO)
        user32.FillRect(hdc, ctypes.byref(area), pincel)
        gdi32.DeleteObject(pincel)
        antiga = gdi32.SelectObject(hdc, self._fonte)
        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, COR_TEXTO)
        user32.DrawTextW(hdc, self._texto, -1, ctypes.byref(area),
                         DT_CENTER | DT_VCENTER | DT_SINGLELINE)
        gdi32.SelectObject(hdc, antiga)
        user32.EndPaint(self._hwnd, ctypes.byref(ps))
