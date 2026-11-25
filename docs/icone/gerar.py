"""Gera os conceitos B e C do ícone do GilleVoz (o A é desenhado à mão em a-g-termico.svg)."""
from pathlib import Path

AQUI = Path(__file__).parent
FUNDO = '<rect x="16" y="16" width="480" height="480" rx="116" fill="#0B0912"/>'
BORDA = '<rect x="16.5" y="16.5" width="479" height="479" rx="115.5" fill="none" stroke="#241E30" stroke-width="3"/>'
TERMICA = ["#781C6D", "#BB3754", "#ED6925", "#FBB61A", "#FCFFA4"]


def matriz_led() -> str:
    acesos = [2, 4, 5, 3, 1]  # LEDs acesos por coluna (de 5), formando uma onda
    tam, vao = 56, 14
    total = 5 * tam + 4 * vao
    x0 = y0 = (512 - total) / 2
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">', FUNDO, BORDA]
    for c, h in enumerate(acesos):
        for linha in range(5):
            x = x0 + c * (tam + vao)
            y = y0 + (4 - linha) * (tam + vao)
            cor = TERMICA[linha] if linha < h else "#16121F"  # cor pela altura, igual à barra
            s.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{tam}" height="{tam}" rx="12" fill="{cor}"/>')
    s.append("</svg>")
    return "\n".join(s)


def pilula() -> str:
    s = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">',
        '<defs><linearGradient id="p" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#320A5E"/><stop offset="1" stop-color="#ED6925"/></linearGradient></defs>',
        FUNDO, BORDA,
        '<rect x="56" y="186" width="400" height="140" rx="70" fill="#000004" stroke="url(#p)" stroke-width="10"/>',
    ]
    for i, a in enumerate([30, 62, 92, 60, 34]):
        x = 146 + i * 48
        s.append(f'<rect x="{x}" y="{256 - a / 2:.0f}" width="28" height="{a}" rx="14" fill="{TERMICA[min(4, a // 20)]}"/>')
    s.append("</svg>")
    return "\n".join(s)


(AQUI / "b-matriz-led.svg").write_text(matriz_led(), encoding="utf-8")
(AQUI / "c-pilula.svg").write_text(pilula(), encoding="utf-8")
