import type { ComandoMotor, EventoMotor } from '../shared/protocolo'

export interface GilleVozApi {
  enviar(cmd: ComandoMotor): void
  pedir<T = unknown>(tipo: string, dados?: object): Promise<T>
  /** Assina os eventos do motor; devolve a função que cancela a assinatura. */
  aoEvento(cb: (e: EventoMotor) => void): () => void
  /** Reservado para as janelas (Flow Bar / Hub) nas próximas tarefas. */
  janela: Record<string, never>
}

declare global {
  interface Window {
    gillevoz: GilleVozApi
  }
}
