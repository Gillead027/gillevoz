import { describe, expect, it } from 'vitest'
import { bordaMaisProxima, calcularPosicao } from './posicao'

const AREA = { x: 0, y: 0, width: 1920, height: 1040 }
const TAM = { w: 360, h: 120 }

describe('calcularPosicao', () => {
  it('embaixo no centro, 14 px acima da barra de tarefas', () => {
    expect(calcularPosicao(AREA, 'embaixo', 0.5, TAM)).toEqual({ x: 780, y: 906 })
  })

  it('esquerda e direita ficam a 14 px da borda, centradas em pos', () => {
    expect(calcularPosicao(AREA, 'esquerda', 0.5, TAM)).toEqual({ x: 14, y: 460 })
    expect(calcularPosicao(AREA, 'direita', 0.5, TAM)).toEqual({ x: 1546, y: 460 })
  })

  it('não deixa a janela sair da área útil nas pontas', () => {
    expect(calcularPosicao(AREA, 'embaixo', 0, TAM)).toEqual({ x: 0, y: 906 })
    expect(calcularPosicao(AREA, 'embaixo', 1, TAM)).toEqual({ x: 1560, y: 906 })
    expect(calcularPosicao(AREA, 'direita', 5, TAM)).toEqual({ x: 1546, y: 920 })
  })

  it('respeita a origem da área (segundo monitor) e a margem', () => {
    const area = { x: 1920, y: 100, width: 1280, height: 984 }
    expect(calcularPosicao(area, 'embaixo', 0.5, TAM, 10)).toEqual({ x: 2380, y: 954 })
  })
})

describe('bordaMaisProxima', () => {
  it('ponto perto do canto esquerdo vai para a esquerda', () => {
    expect(bordaMaisProxima(AREA, { x: 40, y: 300 }).borda).toBe('esquerda')
  })

  it('ponto perto da direita vai para a direita, com pos ao longo da borda', () => {
    const r = bordaMaisProxima(AREA, { x: 1900, y: 520 })
    expect(r.borda).toBe('direita')
    expect(r.pos).toBeCloseTo(0.5)
  })

  it('ponto perto de baixo vai para baixo', () => {
    const r = bordaMaisProxima(AREA, { x: 480, y: 1000 })
    expect(r).toEqual({ borda: 'embaixo', pos: 0.25 })
  })

  it('a borda de cima não existe: perto do topo escolhe a lateral mais próxima', () => {
    expect(bordaMaisProxima(AREA, { x: 300, y: 5 }).borda).toBe('esquerda')
  })

  it('pos fica entre 0 e 1 mesmo fora da área', () => {
    const r = bordaMaisProxima(AREA, { x: -50, y: 2000 })
    expect(r.pos).toBeGreaterThanOrEqual(0)
    expect(r.pos).toBeLessThanOrEqual(1)
  })

  it('soltar onde a barra estaria devolve a mesma posição (ida e volta)', () => {
    const { x, y } = calcularPosicao(AREA, 'embaixo', 0.3, TAM)
    const r = bordaMaisProxima(AREA, { x: x + TAM.w / 2, y: y + TAM.h / 2 })
    expect(r.borda).toBe('embaixo')
    expect(r.pos).toBeCloseTo(0.3)
  })
})
