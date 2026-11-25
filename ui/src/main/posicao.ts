// Posição da Flow Bar na área útil do monitor (DESENHO-V2 §7).
// `pos` (0..1) é onde fica o CENTRO da janela ao longo da borda; a janela nunca sai da área.

export interface Retangulo {
  x: number
  y: number
  width: number
  height: number
}

export type Borda = 'embaixo' | 'esquerda' | 'direita'

const limitar = (v: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, Number.isFinite(v) ? v : min))

export function calcularPosicao(
  area: Retangulo,
  borda: Borda,
  pos: number,
  tamanho: { w: number; h: number },
  margem = 14
): { x: number; y: number } {
  const p = limitar(pos, 0, 1)
  if (borda === 'embaixo') {
    const x = limitar(
      area.x + p * area.width - tamanho.w / 2,
      area.x,
      area.x + area.width - tamanho.w
    )
    return { x: Math.round(x), y: Math.round(area.y + area.height - tamanho.h - margem) }
  }
  const y = limitar(
    area.y + p * area.height - tamanho.h / 2,
    area.y,
    area.y + area.height - tamanho.h
  )
  const x = borda === 'esquerda' ? area.x + margem : area.x + area.width - tamanho.w - margem
  return { x: Math.round(x), y: Math.round(y) }
}

/** Borda (esquerda / embaixo / direita) mais perto do ponto, e a posição 0..1 ao longo dela. */
export function bordaMaisProxima(
  area: Retangulo,
  centro: { x: number; y: number }
): { borda: Borda; pos: number } {
  const distancias: [Borda, number][] = [
    ['embaixo', area.y + area.height - centro.y],
    ['esquerda', centro.x - area.x],
    ['direita', area.x + area.width - centro.x]
  ]
  const [borda] = distancias.reduce((a, b) => (b[1] < a[1] ? b : a))
  const pos =
    borda === 'embaixo' ? (centro.x - area.x) / area.width : (centro.y - area.y) / area.height
  return { borda, pos: limitar(pos, 0, 1) }
}
