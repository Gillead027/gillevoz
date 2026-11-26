import { describe, expect, it } from 'vitest'
import { comandoPermitido, pedidoPermitido } from './protocolo'

describe('whitelist de comandos vindos das janelas (M5)', () => {
  it('aceita só tipos conhecidos', () => {
    expect(comandoPermitido({ tipo: 'iniciar' })).toBe(true)
    expect(comandoPermitido({ tipo: 'salvar_config', cfg: { bips: true } })).toBe(true)
    expect(comandoPermitido({ tipo: 'voar' })).toBe(false)
    expect(comandoPermitido({ tipo: 'sair' })).toBe(false) // só o main encerra o motor
    expect(comandoPermitido(null)).toBe(false)
    expect(comandoPermitido('iniciar')).toBe(false)
    expect(comandoPermitido({ tipo: 1 })).toBe(false)
  })

  it('pedidos: tipo conhecido e dados em objeto simples', () => {
    expect(pedidoPermitido('estatisticas', undefined)).toBe(true)
    expect(pedidoPermitido('listar_historico', { dia: '2026-11-25' })).toBe(true)
    expect(pedidoPermitido('salvar_config', { cfg: {} })).toBe(true)
    expect(pedidoPermitido('sair', undefined)).toBe(false)
    expect(pedidoPermitido('cair', {})).toBe(false)
    expect(pedidoPermitido('estatisticas', 'lixo')).toBe(false)
    expect(pedidoPermitido('estatisticas', [1])).toBe(false)
  })
})
