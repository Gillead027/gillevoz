"""Ícone do GilleVoz na bandeja do Windows (pystray), com cores por estado."""

from typing import Callable

import pystray
from PIL import Image, ImageDraw

# Cor do círculo por estado
CORES = {
    "ocioso": (76, 175, 80),        # verde: pronto para ditar
    "gravando": (229, 57, 53),      # vermelho: microfone aberto
    "transcrevendo": (255, 193, 7), # amarelo: processando o áudio
    "pausado": (120, 120, 120),     # cinza: atalho desligado
}
ESTADOS = tuple(CORES)


def _icone(estado: str) -> Image.Image:
    tamanho = 64
    imagem = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    desenho.ellipse((4, 4, tamanho - 4, tamanho - 4), fill=CORES[estado] + (255,))
    # Um "microfone" simples em branco no centro
    desenho.rounded_rectangle((26, 14, 38, 38), radius=6, fill=(255, 255, 255, 255))
    desenho.rectangle((31, 38, 33, 46), fill=(255, 255, 255, 255))
    desenho.rectangle((24, 46, 40, 49), fill=(255, 255, 255, 255))
    return imagem


class Tray:
    def __init__(
        self,
        on_toggle_ativo: Callable[[], None],
        on_abrir_historico: Callable[[], None],
        on_abrir_config: Callable[[], None],
        on_toggle_startup: Callable[[], None],
        on_sair: Callable[[], None],
        startup_ativo: Callable[[], bool],
    ):
        self._on_toggle_ativo = on_toggle_ativo
        self._on_abrir_historico = on_abrir_historico
        self._on_abrir_config = on_abrir_config
        self._on_toggle_startup = on_toggle_startup
        self._on_sair = on_sair
        self._startup_ativo = startup_ativo
        self._estado = "ocioso"
        self._icon = pystray.Icon(
            "GilleVoz",
            icon=_icone(self._estado),
            title="GilleVoz - ditado por voz",
            menu=self._montar_menu(),
        )

    def _montar_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: "Ativar" if self._estado == "pausado" else "Pausar",
                lambda icon, item: self._on_toggle_ativo(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir histórico", lambda icon, item: self._on_abrir_historico()),
            pystray.MenuItem("Abrir config", lambda icon, item: self._on_abrir_config()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Iniciar com o Windows",
                lambda icon, item: self._alternar_startup(),
                checked=lambda item: self._startup_ativo(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", lambda icon, item: self._on_sair()),
        )

    def _alternar_startup(self) -> None:
        self._on_toggle_startup()
        self._icon.update_menu()

    # ---------- API pública ----------
    def run_detached(self) -> None:
        """Mostra o ícone numa thread própria (não bloqueia)."""
        self._icon.run_detached()

    def set_state(self, estado: str) -> None:
        if estado not in CORES:
            raise ValueError(f"estado desconhecido: {estado!r} (use {ESTADOS})")
        self._estado = estado
        self._icon.icon = _icone(estado)
        self._icon.update_menu()

    def notify(self, mensagem: str) -> None:
        self._icon.notify(mensagem, "GilleVoz")

    def stop(self) -> None:
        self._icon.stop()
