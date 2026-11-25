import { afterEach, describe, expect, it } from 'vitest'
import { join } from 'node:path'
import { MotorProcess } from './motor'
import type { EventoMotor } from '../shared/protocolo'

const FALSO = join(__dirname, '../../test/motor-falso.mjs')
const criados: MotorProcess[] = []

function novo(extra: Partial<ConstructorParameters<typeof MotorProcess>[0]> = {}): MotorProcess {
  const m = new MotorProcess({
    python: process.execPath,
    args: [FALSO],
    cwd: process.cwd(),
    atrasoReinicioMs: 10,
    ...extra
  })
  criados.push(m)
  return m
}

function esperar<T = unknown>(m: MotorProcess, nome: string, ms = 5000): Promise<T> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`tempo esgotado esperando '${nome}'`)), ms)
    m.once(nome, (v: T) => {
      clearTimeout(t)
      resolve(v)
    })
  })
}

afterEach(async () => {
  while (criados.length) await criados.pop()!.parar()
})

describe('MotorProcess', () => {
  it('pedir() resolve com a resposta do id certo', async () => {
    const m = novo()
    const pronto = esperar(m, 'evento')
    m.iniciar()
    expect(((await pronto) as EventoMotor).tipo).toBe('pronto')
    const [a, b] = await Promise.all([
      m.pedir<{ tipo: string; id: number }>('estatisticas'),
      m.pedir<{ tipo: string; id: number }>('listar_microfones')
    ])
    expect(a.tipo).toBe('estatisticas_resposta')
    expect(b.tipo).toBe('listar_microfones_resposta')
    expect(a.id).not.toBe(b.id)
  })

  it('pedir() rejeita após o tempo limite', async () => {
    const m = novo({ tempoLimitePedidoMs: 150 })
    const pronto = esperar(m, 'evento')
    m.iniciar()
    await pronto
    await expect(m.pedir('mudo')).rejects.toThrow(/tempo/i)
  })

  it('linha quebrada no stdout é ignorada sem exceção', async () => {
    const m = novo()
    const eventos: EventoMotor[] = []
    m.on('evento', (e: EventoMotor) => eventos.push(e))
    const pronto = esperar(m, 'evento')
    m.iniciar()
    await pronto
    m.enviar({ tipo: 'lixo' } as never)
    await new Promise<void>((resolve) => {
      m.on('evento', (e: EventoMotor) => e.tipo === 'log' && resolve())
    })
    expect(eventos.map((e) => e.tipo)).toEqual(['pronto', 'log'])
    // continua funcionando
    expect((await m.pedir<{ id: number }>('estatisticas')).id).toBeTypeOf('number')
  })

  it('cai 1x: emite caiu e volta com novo pid', async () => {
    const m = novo()
    const p1 = esperar<{ pid: number }>(m, 'evento')
    m.iniciar()
    const pid1 = (await p1).pid
    const caiu = esperar<number>(m, 'caiu')
    const volta = esperar<{ pid: number }>(m, 'evento')
    m.enviar({ tipo: 'cair' } as never)
    expect(await caiu).toBe(1)
    expect((await volta).pid).not.toBe(pid1)
  })

  it('cai 4x em 60 s: emite desistiu', async () => {
    const m = novo()
    let caidas = 0
    m.on('caiu', () => caidas++)
    m.on('evento', (e: EventoMotor) => {
      if (e.tipo === 'pronto') m.enviar({ tipo: 'cair' } as never)
    })
    const desistiu = esperar(m, 'desistiu', 15000)
    m.iniciar()
    await desistiu
    expect(caidas).toBe(4)
  })

  it('parar() encerra sem reiniciar nem emitir caiu', async () => {
    const m = novo()
    const pronto = esperar(m, 'evento')
    m.iniciar()
    await pronto
    let caiu = false
    m.on('caiu', () => (caiu = true))
    await m.parar()
    await new Promise((r) => setTimeout(r, 100))
    expect(caiu).toBe(false)
    expect(m.pid).toBeUndefined()
  })
})
