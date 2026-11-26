import { describe, expect, it, vi } from 'vitest'
import { FilaConfig } from './filaConfig'
import type { Cfg } from './filaConfig'

/** Motor falso: guarda o config, junta {**antigo, **parcial} e só responde quando mandarmos. */
function motorFalso(inicial: Cfg): {
  disco: () => Cfg
  enviados: Cfg[]
  enviar: (parcial: Cfg) => Promise<Cfg>
  responder: () => void
  falhar: () => void
} {
  let disco = { ...inicial }
  const enviados: Cfg[] = []
  const fila: Array<{ parcial: Cfg; ok: (c: Cfg) => void; erro: (e: Error) => void }> = []
  return {
    disco: () => disco,
    enviados,
    enviar: (parcial) =>
      new Promise((ok, erro) => {
        enviados.push(parcial)
        fila.push({ parcial, ok, erro })
      }),
    responder: () => {
      const p = fila.shift()!
      disco = { ...disco, ...p.parcial }
      p.ok({ ...disco })
    },
    falhar: () => fila.shift()!.erro(new Error('motor caiu'))
  }
}

const tique = (): Promise<void> => new Promise((r) => setTimeout(r, 0))

describe('FilaConfig', () => {
  it('dois interruptores rápidos e um texto: nenhum envio leva valor velho e a tela não volta', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      const m = motorFalso({ bips: false, tempo_real: false, idioma: 'pt', barra_pos: 0.5 })
      const fila = new FilaConfig({ enviar: m.enviar, aoMudar: () => {}, aoFalhar: () => {} })
      fila.receber(m.disco())
      const telas: Cfg[] = []
      const olhar = (): void => {
        telas.push(fila.visivel()!)
      }

      void fila.salvar({ bips: true })
      olhar()
      void fila.salvar({ tempo_real: true })
      olhar()
      void fila.salvar({ idioma: 'en' }, { adiar: true })
      olhar()
      // Só um salvar_config por vez, e só com as chaves que mudaram.
      expect(m.enviados).toEqual([{ bips: true }])

      // Um `config` antigo chega no meio (ex.: eco da barra): não pode apagar o que está pendente.
      fila.receber({ bips: false, tempo_real: false, idioma: 'pt', barra_pos: 0.7 })
      olhar()

      m.responder()
      await vi.advanceTimersByTimeAsync(0)
      olhar()
      // A resposta 1 não desfaz a mudança 2: o próximo lote sai com tudo o que falta.
      expect(m.enviados[1]).toEqual({ tempo_real: true, idioma: 'en' })

      m.responder()
      await vi.advanceTimersByTimeAsync(500)
      olhar()

      // Depois de mudar, o valor nunca volta na tela (telas[i] = depois da mudança i).
      telas.forEach((t, i) => {
        expect(t.bips).toBe(true)
        if (i >= 1) expect(t.tempo_real).toBe(true)
        if (i >= 2) expect(t.idioma).toBe('en')
      })
      expect(m.enviados).toHaveLength(2)
      expect(m.enviados.every((p) => !('barra_pos' in p))).toBe(true)
      expect(m.disco()).toEqual({ bips: true, tempo_real: true, idioma: 'en', barra_pos: 0.5 })
    } finally {
      vi.useRealTimers()
    }
  })

  it('texto espera 400 ms parado e manda só o último valor', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      const m = motorFalso({ trocas: [] })
      const fila = new FilaConfig({ enviar: m.enviar, aoMudar: () => {}, aoFalhar: () => {} })
      fila.receber(m.disco())
      void fila.salvar({ trocas: [{ de: 'a', para: 'b' }] }, { adiar: true })
      await vi.advanceTimersByTimeAsync(300)
      void fila.salvar({ trocas: [{ de: 'ab', para: 'b' }] }, { adiar: true })
      await vi.advanceTimersByTimeAsync(300)
      expect(m.enviados).toEqual([])
      await vi.advanceTimersByTimeAsync(150)
      expect(m.enviados).toEqual([{ trocas: [{ de: 'ab', para: 'b' }] }])
    } finally {
      vi.useRealTimers()
    }
  })

  it('erro num lote descarta só as chaves dele; o resto segue', async () => {
    const m = motorFalso({ bips: false, tempo_real: false })
    const falhas: string[] = []
    const fila = new FilaConfig({
      enviar: m.enviar,
      aoMudar: () => {},
      aoFalhar: (msg) => falhas.push(msg)
    })
    fila.receber(m.disco())
    const r1 = fila.salvar({ bips: true })
    const r2 = fila.salvar({ tempo_real: true })
    m.falhar()
    expect(await r1).toBeNull()
    await tique()
    expect(falhas).toHaveLength(1)
    // bips volta ao do motor; tempo_real (pendente) continua e é enviado.
    expect(fila.visivel()).toEqual({ bips: false, tempo_real: true })
    expect(m.enviados[1]).toEqual({ tempo_real: true })
    m.responder()
    expect((await r2)?.recebido).toEqual({ bips: false, tempo_real: true })
  })
})
