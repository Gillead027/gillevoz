// Escala térmica "inferno" (DESENHO-V2 §10) e regras do "termômetro de LED" (REFERENCIAS-UI §2).

export const ESCALA = ['#000004', '#320a5e', '#781c6d', '#bb3754', '#ed6925', '#fbb61a', '#fcffa4']

const rgb = (hex: string): number[] => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
const hex2 = (n: number): string => Math.round(n).toString(16).padStart(2, '0')

function limitar01(v: number): number {
  return Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 0
}

/** Cor da escala para v em 0..1 (fora disso, limitado), interpolando entre as 7 cores. */
export function corTermica(v: number): string {
  const t = limitar01(v) * (ESCALA.length - 1)
  const i = Math.min(Math.floor(t), ESCALA.length - 2)
  const f = t - i
  const a = rgb(ESCALA[i])
  const b = rgb(ESCALA[i + 1])
  return '#' + a.map((c, k) => hex2(c + (b[k] - c) * f)).join('')
}

/** Cor do LED pela altura: linha 0 (baixo) = #781C6D … linha total-1 (topo) = #FCFFA4. */
export function corLed(linha: number, total = 5): string {
  const inicio = 2 / 6 // #781C6D na escala
  const frac = total > 1 ? linha / (total - 1) : 1
  return corTermica(inicio + frac * (1 - inicio))
}

/** Quantos LEDs acendem para um volume 0..1 (arredonda volume × total, limitado 0..total). */
export function ledsAcesos(volume: number, total = 5): number {
  return Math.round(limitar01(volume) * total)
}
