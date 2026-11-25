// "Termômetro de LED" (REFERENCIAS-UI §2): 14 colunas × 5 LEDs quadrados de 3 px com 1 px de vão.
// O volume acende LEDs de baixo para cima; cada LED aceso tem a cor térmica pela altura.
// Ideias: Voice Pill (React Bits) + visualizador em matriz de LED (Inspora). Código próprio.
import { useEffect, useRef, useState } from 'react'
import { corLed, ledsAcesos } from './escalaTermica'

const COLUNAS = 14
const LINHAS = 5
const LED = 3
const VAO = 1
const APAGADO = '#14111c'
const CORES = Array.from({ length: LINHAS }, (_, i) => corLed(i, LINHAS))

/** Monta junto com o estado "gravando": começa zerada e guarda os últimos níveis (o mais novo à
 * direita), um passo a cada 2 eventos (~15/s ≈ 1 s de onda). */
export default function Onda(): React.JSX.Element {
  const [niveis, setNiveis] = useState<number[]>(() => Array(COLUNAS).fill(0))
  const pendente = useRef<number[]>([])
  useEffect(
    () =>
      window.gillevoz.aoEvento((e) => {
        if (e.tipo !== 'nivel') return
        pendente.current.push(e.valor)
        if (pendente.current.length < 2) return
        const v = Math.max(...pendente.current)
        pendente.current = []
        setNiveis((h) => [...h.slice(1), v])
      }),
    []
  )
  const largura = COLUNAS * LED + (COLUNAS - 1) * VAO
  const altura = LINHAS * LED + (LINHAS - 1) * VAO
  return (
    <svg
      className="onda"
      width={largura}
      height={altura}
      viewBox={`0 0 ${largura} ${altura}`}
      shapeRendering="crispEdges"
      aria-hidden
    >
      {niveis.map((v, col) => {
        const acesos = ledsAcesos(v, LINHAS)
        return CORES.map((cor, lin) => (
          <rect
            key={`${col}-${lin}`}
            x={col * (LED + VAO)}
            y={(LINHAS - 1 - lin) * (LED + VAO)}
            width={LED}
            height={LED}
            fill={lin < acesos ? cor : APAGADO}
          />
        ))
      })}
    </svg>
  )
}
