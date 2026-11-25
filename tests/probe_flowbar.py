"""Medição nativa isolada: sem App, hooks, microfone, config ou clipboard.

Executar com .venv/Scripts/python.exe -m tests.probe_flowbar NÃO é necessário:
use python tests/probe_flowbar.py, que adiciona a raiz explicitamente.
"""
import ctypes
import json
import math
from pathlib import Path
import queue
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gillevoz import flowbar as f


u = ctypes.WinDLL('user32', use_last_error=True)
k = ctypes.WinDLL('kernel32', use_last_error=True)
u.GetGuiResources.argtypes = [ctypes.c_void_p, ctypes.c_uint]
u.GetGuiResources.restype = ctypes.c_uint
k.GetCurrentProcess.restype = ctypes.c_void_p
u.GetForegroundWindow.restype = ctypes.c_void_p
u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
u.SendMessageW.restype = ctypes.c_ssize_t
u.UpdateWindow.argtypes = [ctypes.c_void_p]
u.IsWindow.argtypes = [ctypes.c_void_p]
u.IsWindowVisible.argtypes = [ctypes.c_void_p]
u.GetCapture.restype = ctypes.c_void_p
CUSTOM = f.WM_APP + 99


def wait_for(pred, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(.01)
    raise TimeoutError('Condição da medição não atingida')


class Probe(f.FlowBar):
    def __init__(self):
        super().__init__(*(lambda *a: None for _ in range(6)), posicao=(20, 20))
        self.actions = queue.Queue()
        self.paints = 0
        self.timers = 0

    def _desenhar_barra(self, *args):
        super()._desenhar_barra(*args)
        self.paints += 1

    def _tratar_barra(self, msg, wp, lp):
        if msg == CUSTOM:
            action, result = self.actions.get()
            try:
                result.append(action())
            except BaseException as e:
                result.append(e)
            return 0
        if msg == f.WM_TIMER and wp == f.TIMER_ANIMACAO:
            self.timers += 1
        return super()._tratar_barra(msg, wp, lp)

    def call(self, action):
        result = []
        self.actions.put((action, result))
        u.SendMessageW(self._hwnd, CUSTOM, 0, 0)
        if not result:
            raise RuntimeError('Thread/janela não respondeu')
        if isinstance(result[0], BaseException):
            raise result[0]
        return result[0]


def resources():
    return u.GetGuiResources(k.GetCurrentProcess(), 0)


def cpu_sample(bar, seconds):
    wall, cpu, ticks, paints = time.perf_counter(), time.process_time(), bar.timers, bar.paints
    time.sleep(seconds)
    wall, cpu = time.perf_counter() - wall, time.process_time() - cpu
    return dict(wall_s=round(wall, 4), cpu_s=round(cpu, 6),
                cpu_percent_one_core=round(100 * cpu / wall, 3),
                timers=bar.timers - ticks, paints=bar.paints - paints)


def main():
    report = {'gdi_before_start': resources()}
    foreground = u.GetForegroundWindow()
    bar = Probe()
    try:
        bar.start()
        wait_for(lambda: bar._hwnd and bar._thread.is_alive())
        bar.call(lambda: None)
        report['foreground_unchanged_start'] = foreground == u.GetForegroundWindow()
        report['mouseactivate_bar'] = int(u.SendMessageW(bar._hwnd, f.WM_MOUSEACTIVATE, 0, 0))
        report['idle'] = cpu_sample(bar, 2)
        bar.set_state('gravando')
        bar.call(lambda: None)
        time.sleep(.15)
        report['gdi_before_300_animation'] = bar.call(resources)
        p0, t0, cpu0 = bar.paints, time.perf_counter(), time.process_time()
        while bar.paints - p0 < 300:
            bar.set_level((math.sin(bar.paints * .2) + 1) / 2)
            time.sleep(.01)
            if time.perf_counter() - t0 > 25:
                raise TimeoutError('300 repaints não atingidos')
        report['animation'] = dict(paints=bar.paints - p0, wall_s=round(time.perf_counter() - t0, 4),
                                   cpu_s=round(time.process_time() - cpu0, 6))
        report['gdi_after_300_animation'] = bar.call(resources)
        bar.set_state('ocioso')
        bar.call(lambda: None)
        report['idle_after_animation'] = cpu_sample(bar, 2)
        bar.call(lambda: bar._abrir_menu(30, 150))
        report['mouseactivate_menu'] = int(u.SendMessageW(bar._menu, f.WM_MOUSEACTIVATE, 0, 0))
        report['gdi_before_300_menu'] = bar.call(resources)
        def menu_repaints():
            for _ in range(300):
                f.user32.InvalidateRect(bar._menu, None, False)
                u.UpdateWindow(bar._menu)
        bar.call(menu_repaints)
        report['gdi_after_300_menu'] = bar.call(resources)
        bar.call(bar._fechar_menu)
        bar.call(lambda: bar._inicio_arraste(0))
        report['capture_owned'] = bar.call(lambda: u.GetCapture() == bar._hwnd)
        # Não mover o cursor real nem disparar o callback de clique.
        bar.call(lambda: (f.user32.ReleaseCapture(), setattr(bar, '_arraste', None)))
        report['foreground_unchanged_menu_capture'] = foreground == u.GetForegroundWindow()
        x, y = f._clampear(1_000_000, 1_000_000, 52, 26)
        report['offscreen_saved_position_clamped'] = [x, y]
        bar.esconder_por(.15)
        wait_for(lambda: not u.IsWindowVisible(bar._hwnd))
        wait_for(lambda: u.IsWindowVisible(bar._hwnd))
        report['hide_returns_after_short_timer'] = True
        bar.set_state('transcrevendo')
        bar.esconder_por(30)
        bar.call(lambda: None)
        report['hidden_animation'] = cpu_sample(bar, 2)
        bar.mostrar()
        bar.set_state('ocioso')
        bar.call(lambda: None)
        old_hwnd, old_thread = bar._hwnd, bar._thread
        bar.esconder_por(.3)
        bar.call(lambda: None)
        bar.stop()
        report['stop_thread_dead_immediate'] = not old_thread.is_alive()
        report['stop_window_destroyed_immediate'] = not u.IsWindow(old_hwnd)
        time.sleep(.7)
        report['resurrected_after_stop'] = bool(bar._hwnd and bar._thread.is_alive())
        bar._cancelar_timer_ocultar()
        bar.stop()
        time.sleep(.1)
        report['remaining_flow_threads'] = [t.name for t in threading.enumerate() if t.name.startswith('gillevoz-flowbar')]
        report['gdi_after_final_stop'] = resources()
    finally:
        bar._cancelar_timer_ocultar()
        bar.stop()
        path = Path(__file__).with_name('flowbar_metrics.json')
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
