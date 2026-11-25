import { describe, expect, it, vi } from 'vitest'

vi.mock('electron', () => ({ Menu: {}, Tray: class {}, nativeImage: {} }))
const { desenharIcone, rgbaParaPng } = await import('./bandeja')

const pixel = (buf: Buffer, tam: number, x: number, y: number): number[] => {
  const o = (y * tam + x) * 4
  return [buf[o], buf[o + 1], buf[o + 2], buf[o + 3]]
}

describe('ícone da bandeja', () => {
  it('desenha RGBA no tamanho pedido, com cantos transparentes', () => {
    for (const tam of [16, 32] as const) {
      const buf = desenharIcone(tam, 'ocioso')
      expect(buf.length).toBe(tam * tam * 4)
      expect(pixel(buf, tam, 0, 0)[3]).toBeLessThan(128)
      expect(pixel(buf, tam, tam / 2, tam / 2)[3]).toBe(255)
    }
  })

  it('LED de baixo da coluna do meio é #781C6D; pausado apaga a cor', () => {
    // 16 px: LED 2 px, vão 1 px, origem 1 → coluna 2, linha de baixo = x 7..8, y 13..14
    expect(pixel(desenharIcone(16, 'ocioso'), 16, 7, 13).slice(0, 3)).toEqual([0x78, 0x1c, 0x6d])
    expect(pixel(desenharIcone(16, 'pausado'), 16, 7, 13).slice(0, 3)).toEqual([0x4a, 0x43, 0x58])
    expect(pixel(desenharIcone(16, 'erro'), 16, 7, 13).slice(0, 3)).toEqual([0xbb, 0x37, 0x54])
  })

  it('gravando acende mais LEDs que ocioso', () => {
    // coluna 0, terceiro LED de baixo para cima (y 7..8): apagado no ocioso, aceso gravando
    expect(pixel(desenharIcone(16, 'ocioso'), 16, 1, 7).slice(0, 3)).toEqual([0x16, 0x12, 0x1f])
    expect(pixel(desenharIcone(16, 'gravando'), 16, 1, 7).slice(0, 3)).toEqual([0xed, 0x69, 0x25])
  })

  it('gera um PNG válido', () => {
    const png = rgbaParaPng(desenharIcone(16, 'ocioso'), 16, 16)
    expect([...png.subarray(0, 8)]).toEqual([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
    expect(png.subarray(12, 16).toString('ascii')).toBe('IHDR')
  })
})
