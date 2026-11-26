// Config do motor no Hub. Salvar é imediato (sem botão): interruptores e listas salvam na hora,
// campos de texto esperam 400 ms parados. Sempre manda o config inteiro lido do motor + a mudança.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

export type Cfg = Record<string, unknown>

export interface ResultadoSalvar {
  enviado: Cfg
  recebido: Cfg
}

const ESPERA_TEXTO_MS = 400

export interface ConfigHub {
  /** Config como a tela deve mostrar (o do motor + mudanças ainda não enviadas); null carregando. */
  cfg: Cfg | null
  /** Salva uma mudança. `adiar`: campo de texto (espera 400 ms sem digitar). */
  salvar(mudanca: Cfg, opcoes?: { adiar?: boolean }): Promise<ResultadoSalvar | null>
}

export function useConfig(pronto: boolean, aoFalhar: (msg: string) => void): ConfigHub {
  const api = window.gillevoz
  const [doMotor, setDoMotor] = useState<Cfg | null>(null)
  // Mudanças ainda não confirmadas pelo motor: o estado desenha a tela, o ref serve ao envio.
  const [pendentesVisiveis, setPendentesVisiveis] = useState<Cfg>({})
  const motorRef = useRef<Cfg | null>(null)
  const pendentes = useRef<Cfg>({})
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const falhar = useRef(aoFalhar)
  useLayoutEffect(() => {
    falhar.current = aoFalhar
  })

  const receber = useCallback((cfg: unknown): void => {
    if (!cfg || typeof cfg !== 'object') return
    motorRef.current = cfg as Cfg
    setDoMotor(cfg as Cfg)
  }, [])

  // Lê ao ficar pronto (o motor só responde depois de carregar o modelo).
  useEffect(() => {
    if (!pronto) return
    let vivo = true
    api
      .pedir<{ cfg?: Cfg }>('ler_config')
      .then((r) => vivo && receber(r.cfg))
      .catch(() => {})
    return () => {
      vivo = false
    }
  }, [api, pronto, receber])

  useEffect(
    () =>
      api.aoEvento((e) => {
        if (e.tipo === 'config') receber(e.cfg)
      }),
    [api, receber]
  )

  const enviar = useCallback(async (): Promise<ResultadoSalvar | null> => {
    clearTimeout(timer.current)
    timer.current = undefined
    const mudancas = pendentes.current
    if (!motorRef.current || Object.keys(mudancas).length === 0) return null
    pendentes.current = {}
    setPendentesVisiveis({})
    const antes = motorRef.current
    const enviado = { ...antes, ...mudancas }
    // Otimista: a tela já mostra o novo valor e o próximo envio parte dele (não desfaz este).
    receber(enviado)
    try {
      // `ativo` (pausado pela barra/bandeja) não vem em evento `config`: a cópia daqui pode estar
      // velha, então fica de fora e o motor mantém o valor dele.
      const paraMotor = { ...enviado }
      delete paraMotor['ativo']
      const r = await api.pedir<{ cfg?: Cfg }>('salvar_config', { cfg: paraMotor })
      receber(r.cfg)
      return { enviado, recebido: (r.cfg as Cfg) ?? enviado }
    } catch {
      receber(antes)
      falhar.current('Não consegui salvar: o motor não respondeu.')
      return null
    }
  }, [api, receber])

  const salvar = useCallback(
    (mudanca: Cfg, opcoes: { adiar?: boolean } = {}): Promise<ResultadoSalvar | null> => {
      pendentes.current = { ...pendentes.current, ...mudanca }
      setPendentesVisiveis(pendentes.current)
      if (opcoes.adiar) {
        clearTimeout(timer.current)
        timer.current = setTimeout(enviar, ESPERA_TEXTO_MS)
        return Promise.resolve(null)
      }
      return enviar()
    },
    [enviar]
  )

  // Fechar o Hub com um texto ainda esperando: manda já.
  useEffect(() => {
    const agora = (): void => {
      if (timer.current) void enviar()
    }
    window.addEventListener('beforeunload', agora)
    return () => window.removeEventListener('beforeunload', agora)
  }, [enviar])

  const cfg = doMotor ? { ...doMotor, ...pendentesVisiveis } : null
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
