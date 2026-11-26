// Protocolo motor <-> interface (DESENHO-V2 §6.1): uma mensagem JSON por linha, UTF-8.

export type EstadoMotor = 'ocioso' | 'gravando' | 'transcrevendo' | 'pausado' | 'erro'

// ---- Motor -> interface (eventos) ----
export interface EventoPronto {
  tipo: 'pronto'
  dispositivo: 'cuda' | 'cpu'
  modelo: string
}
export interface EventoEstado {
  tipo: 'estado'
  estado: EstadoMotor
  msg?: string
}
export interface EventoNivel {
  tipo: 'nivel'
  valor: number // 0..1
}
export interface EventoParcial {
  tipo: 'parcial'
  confirmado: string // texto já digitado até agora
}
export interface EventoFinal {
  tipo: 'final'
  texto: string
  duracao_audio: number
  tempo_transcricao: number
  palavras: number
}
export interface EventoHistorico {
  tipo: 'historico'
  dia: string
}
export interface EventoConfig {
  tipo: 'config'
  cfg: Record<string, unknown>
}
export interface EventoLog {
  tipo: 'log'
  nivel: string
  msg: string
}

/** Resposta a um pedido com id: mesmo `tipo` do pedido + `_resposta`. */
export interface RespostaMotor {
  tipo: `${string}_resposta`
  id: number
  [campo: string]: unknown
}

export type EventoMotor =
  | EventoPronto
  | EventoEstado
  | EventoNivel
  | EventoParcial
  | EventoFinal
  | EventoHistorico
  | EventoConfig
  | EventoLog

// ---- Interface -> motor (comandos) ----
export type ComandoMotor =
  | { tipo: 'iniciar' }
  | { tipo: 'parar' }
  | { tipo: 'cancelar' }
  | { tipo: 'pausar' }
  | { tipo: 'retomar' }
  | { tipo: 'ler_config'; id?: number }
  | { tipo: 'salvar_config'; cfg: Record<string, unknown>; id?: number }
  | { tipo: 'colar_ultima' }
  | { tipo: 'copiar_ultima' }
  | { tipo: 'listar_historico'; dia?: string; id?: number }
  | { tipo: 'estatisticas'; id?: number }
  | { tipo: 'listar_microfones'; id?: number }
  | { tipo: 'sair' }

/** Canais IPC entre main, preload e renderer. */
export const CANAL_EVENTO = 'motor:evento'
export const CANAL_ENVIAR = 'motor:enviar'
export const CANAL_PEDIR = 'motor:pedir'

/** Comandos que as janelas podem mandar ao motor ('sair' fica só com o main). */
export const COMANDOS_DAS_JANELAS = [
  'iniciar',
  'parar',
  'cancelar',
  'pausar',
  'retomar',
  'ler_config',
  'salvar_config',
  'colar_ultima',
  'copiar_ultima',
  'listar_historico',
  'estatisticas',
  'listar_microfones'
] as const satisfies readonly ComandoMotor['tipo'][]

const objetoSimples = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v)

const tipoPermitido = (tipo: unknown): boolean =>
  typeof tipo === 'string' && (COMANDOS_DAS_JANELAS as readonly string[]).includes(tipo)

/** Confere um comando que chegou por IPC (não confiar no renderer). */
export function comandoPermitido(cmd: unknown): cmd is ComandoMotor {
  return objetoSimples(cmd) && tipoPermitido(cmd.tipo)
}

/** Confere um pedido (motor:pedir) que chegou por IPC. */
export function pedidoPermitido(tipo: unknown, dados: unknown): boolean {
  return tipoPermitido(tipo) && (dados === undefined || objetoSimples(dados))
}
