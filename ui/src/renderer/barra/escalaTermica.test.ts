import { describe, expect, it } from 'vitest'
import { corLed, corTermica, ledsAcesos } from './escalaTermica'

describe('corTermica', () => {
  it('pontas da escala', () => {
    expect(corTermica(0)).toBe('#000004')
    expect(corTermica(1)).toBe('#fcffa4')
  })

  it('fora de 0..1 é limitado', () => {
    expect(corTermica(2)).toBe(corTermica(1))
    expect(corTermica(-3)).toBe(corTermica(0))
  })

  it('passa exatamente pelas cores intermediárias', () => {
    expect(corTermica(1 / 6)).toBe('#320a5e')
    expect(corTermica(3 / 6)).toBe('#bb3754')
    expect(corTermica(5 / 6)).toBe('#fbb61a')
  })

  it('interpola entre duas cores', () => {
    // meio caminho entre #000004 e #320a5e
    expect(corTermica(1 / 12)).toBe('#190531')
  })
})

describe('corLed', () => {
  it('cor pela altura: baixo #781C6D, topo #FCFFA4', () => {
    expect(corLed(0)).toBe('#781c6d')
    expect(corLed(4)).toBe('#fcffa4')
  })

  it('linhas do meio sobem pela escala', () => {
    expect(corLed(1)).toBe('#bb3754')
    expect(corLed(2)).toBe('#ed6925')
    expect(corLed(3)).toBe('#fbb61a')
  })
})

describe('ledsAcesos', () => {
  it('arredonda volume × total', () => {
    expect(ledsAcesos(0.5)).toBe(3)
    expect(ledsAcesos(0.19)).toBe(1)
    expect(ledsAcesos(0)).toBe(0)
  })

  it('limitado a 0..total', () => {
    expect(ledsAcesos(-1)).toBe(0)
    expect(ledsAcesos(9)).toBe(5)
    expect(ledsAcesos(Number.NaN)).toBe(0)
  })
})
