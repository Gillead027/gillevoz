import { afterEach, describe, expect, it, vi } from 'vitest'
import { join } from 'node:path'
import { MotorProcess, anunciarOciosoAoCair, resolverPython } from './motor'
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
    const aviso = vi.spyOn(console, 'warn').mockImplementation(() => {})
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
    expect(aviso).toHaveBeenCalledTimes(1)
    aviso.mockRestore()
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

  it('reiniciarManual() depois de desistir zera as quedas: a próxima queda reinicia', async () => {
    const m = novo()
    let derrubar = true
    m.on('evento', (e: EventoMotor) => {
      if (e.tipo === 'pronto' && derrubar) m.enviar({ tipo: 'cair' } as never)
    })
    const desistiu = esperar(m, 'desistiu', 15000)
    m.iniciar()
    await desistiu
    let desistiuDeNovo = false
    m.on('desistiu', () => (desistiuDeNovo = true))
    // Nova tentativa manual: cai mais 1 vez e precisa voltar sozinho (não desistir).
    const caiu = esperar(m, 'caiu')
    m.reiniciarManual()
    await caiu
    derrubar = false
    const volta = esperar<{ tipo: string }>(m, 'evento')
    expect((await volta).tipo).toBe('pronto')
    expect(desistiuDeNovo).toBe(false)
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

  it('executável inexistente: conta como queda, desiste e parar() não trava', async () => {
    const erro = vi.spyOn(console, 'error').mockImplementation(() => {})
    const m = novo({ python: 'nao-existe-gillevoz', args: [] })
    let caidas = 0
    m.on('caiu', () => caidas++)
    const desistiu = esperar(m, 'desistiu', 5000)
    m.iniciar()
    await desistiu
    expect(caidas).toBe(4)
    await expect(m.pedir('estatisticas')).rejects.toThrow(/indispon/i)
    await m.parar()
    erro.mockRestore()
  })

  it('Review Focus 5: cair durante "gravando" reinicia e as janelas recebem estado ocioso', async () => {
    const m = novo()
    const enviados: EventoMotor[] = []
    // O main repassa para todas as janelas tudo o que esta função transmite.
    anunciarOciosoAoCair(m, (e) => enviados.push(e))
    const pronto = esperar(m, 'evento')
    m.iniciar()
    await pronto
    const gravando = esperar<EventoMotor>(m, 'evento')
    m.enviar({ tipo: 'gravar' } as never)
    expect(await gravando).toEqual({ tipo: 'estado', estado: 'gravando' })
    const caiu = esperar(m, 'caiu')
    const volta = esperar<EventoMotor>(m, 'evento')
    m.enviar({ tipo: 'cair' } as never)
    await caiu
    expect(enviados).toEqual([{ tipo: 'estado', estado: 'ocioso' }])
    expect((await volta).tipo).toBe('pronto')
  })
})

describe('resolverPython empacotado', () => {
  // Mesmo layout que o instalador cria (instalador/gillevoz.iss): app\, python\ e motor\.
  const INSTALACAO = 'C:\\Users\\Fulano\\AppData\\Local\\Programs\\GilleVoz'

  it('usa python\\pythonw.exe e a pasta motor\\ ao lado da pasta app\\', () => {
    const r = resolverPython(true, `${INSTALACAO}\\app\\GilleVoz.exe`)
    expect(r.python).toBe(`${INSTALACAO}\\python\\pythonw.exe`)
    expect(r.cwd).toBe(`${INSTALACAO}\\motor`)
    expect(r.args).toEqual(['-m', 'gillevoz', '--motor'])
  })

  it('aceita a pasta app com outra caixa (App\\)', () => {
    const r = resolverPython(true, `${INSTALACAO}\\App\\GilleVoz.exe`)
    expect(r.python).toBe(`${INSTALACAO}\\python\\pythonw.exe`)
    expect(r.cwd).toBe(`${INSTALACAO}\\motor`)
  })
})
