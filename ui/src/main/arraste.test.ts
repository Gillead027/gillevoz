import { describe, expect, it } from 'vitest'
import { Arraste } from './arraste'

interface Cenario {
  a: Arraste
  movimentos: [number, number][]
  terminou: () => number
  andar: (ms: number) => number
  moverCursor: (x: number, y: number) => { x: number; y: number }
}

function montar(): Cenario {
  let t = 0
  let cursor = { x: 500, y: 500 }
  const movimentos: [number, number][] = []
  let terminou = 0
  const a = new Arraste({
    cursor: () => cursor,
    mover: (x, y) => movimentos.push([x, y]),
    terminou: () => terminou++,
    agora: () => t
  })
  return {
    a,
    movimentos,
    terminou: () => terminou,
    andar: (ms: number) => (t += ms),
    moverCursor: (x: number, y: number) => (cursor = { x, y })
  }
}

describe('Arraste', () => {
  it('segue o cursor descontando o quanto já andou no limiar', () => {
    const m = montar()
    expect(m.a.iniciar({ x: 100, y: 200 }, 5, 0)).toBe(true)
    expect(m.movimentos.at(-1)).toEqual([105, 200])
    m.moverCursor(560, 470)
    m.a.tique()
    expect(m.movimentos.at(-1)).toEqual([165, 170])
  })

  it('soltar segue uma última vez e termina uma vez só', () => {
    const m = montar()
    m.a.iniciar({ x: 0, y: 0 }, 0, 0)
    m.moverCursor(510, 500)
    m.a.soltar()
    m.a.soltar()
    expect(m.movimentos.at(-1)).toEqual([10, 0])
    expect(m.terminou()).toBe(1)
    expect(m.a.ativo).toBe(false)
  })

  it('sem sinal por mais de 3 s termina sozinho, sem exceção, e depois para de mover', () => {
    const m = montar()
    m.a.iniciar({ x: 0, y: 0 }, 0, 0)
    for (let i = 0; i < 200; i++) {
      m.andar(16)
      expect(() => m.a.tique()).not.toThrow()
    }
    expect(m.terminou()).toBe(1)
    expect(m.a.ativo).toBe(false)
    const n = m.movimentos.length
    m.moverCursor(900, 900)
    m.a.tique()
    expect(m.movimentos.length).toBe(n)
  })

  it('parado mas com o botão apertado (sinais chegando) por mais de 3 s não cai', () => {
    const m = montar()
    m.a.iniciar({ x: 0, y: 0 }, 0, 0)
    for (let i = 0; i < 400; i++) {
      m.andar(16)
      if (i % 16 === 0) m.a.sinal() // renderer manda 'segue' a cada ~250 ms mesmo sem mover
      m.a.tique()
    }
    expect(m.terminou()).toBe(0)
    expect(m.a.ativo).toBe(true)
  })

  it('não começa dois arrastes nem aceita deslocamento inválido', () => {
    const m = montar()
    expect(m.a.iniciar({ x: 0, y: 0 }, Number.NaN, 0)).toBe(false)
    expect(m.a.iniciar({ x: 0, y: 0 }, 0, 0)).toBe(true)
    expect(m.a.iniciar({ x: 0, y: 0 }, 0, 0)).toBe(false)
  })
})
