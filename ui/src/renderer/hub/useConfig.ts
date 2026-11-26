// Config do motor no Hub. Salvar é imediato (sem botão): interruptores e listas salvam na hora,
// campos de texto esperam 400 ms parados. A fila (filaConfig.ts) manda só o que mudou, um lote por vez.
import { useEffect, useState } from 'react'
import { FilaConfig, MSG_FALHOU, type Cfg, type ResultadoSalvar } from './filaConfig'

export type { Cfg, ResultadoSalvar }

export interface ConfigHub {
  /** Config como a tela deve mostrar (o do motor + mudanças ainda não confirmadas); null carregando. */
  cfg: Cfg | null
  /** Salva uma mudança. `adiar`: campo de texto (espera 400 ms sem digitar). */
  salvar(mudanca: Cfg, opcoes?: { adiar?: boolean }): Promise<ResultadoSalvar | null>
}

export function useConfig(pronto: boolean, aoFalhar: (msg: string) => void): ConfigHub {
  const api = window.gillevoz
  const [cfg, setCfg] = useState<Cfg | null>(null)
  const [fila] = useState(
    () =>
      new FilaConfig({
        enviar: (parcial) =>
          api.pedir<{ cfg?: Cfg }>('salvar_config', { cfg: parcial }).then((r) => r.cfg as Cfg),
        aoMudar: setCfg
      })
  )

  // Lê ao ficar pronto (o motor só responde depois de carregar o modelo).
  useEffect(() => {
    if (!pronto) return
    let vivo = true
    api
      .pedir<{ cfg?: Cfg }>('ler_config')
      .then((r) => vivo && fila.receber(r.cfg))
      .catch(() => {})
    return () => {
      vivo = false
    }
  }, [api, pronto, fila])

  useEffect(
    () =>
      api.aoEvento((e) => {
        if (e.tipo === 'config') fila.receber(e.cfg)
      }),
    [api, fila]
  )

  // Recarregar a página com um texto ainda esperando: manda já.
  useEffect(() => {
    const agora = (): void => fila.agora()
    window.addEventListener('beforeunload', agora)
    return () => window.removeEventListener('beforeunload', agora)
  }, [fila])

  const salvar: ConfigHub['salvar'] = (m, o) =>
    fila.salvar(m, o).then((r) => {
      if (!r) aoFalhar(MSG_FALHOU) // avisos iguais não empilham
      return r
    })
  return { cfg, salvar }
}

/** Para buscar: sem maiúsculas e sem acentos. */
export const normalizar = (s: string): string =>
  s
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()

/** Lista de textos do config (ignora o que não for texto). */
export const textos = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []

/** Lista de pares do config, ex.: trocas {de, para} ou atalhos_texto {gatilho, texto}. */
export function pares<A extends string, B extends string>(
  v: unknown,
  a: A,
  b: B
): Array<Record<A | B, string>> {
  if (!Array.isArray(v)) return []
  return v.filter(
    (x): x is Record<A | B, string> =>
      !!x && typeof x === 'object' && typeof x[a] === 'string' && typeof x[b] === 'string'
  )
}
