// IPC entre o main e as janelas da Flow Bar e do menu (Tarefa 8).
import type { EstadoMotor } from './protocolo'

export type Borda = 'embaixo' | 'esquerda' | 'direita'

/** Tudo que a barra e o menu precisam saber; o main é a fonte da verdade. */
export interface Situacao {
  /** O motor já mandou `pronto` (modelo carregado). */
  pronto: boolean
  estado: EstadoMotor
  msg?: string
  /** O motor caiu demais e não reinicia sozinho ("Motor parou"). */
  desistiu: boolean
  borda: Borda
  /** Mostrar a dica "Arraste para mudar de lugar" (primeira vez). */
  mostrarDica: boolean
  /** Microfone escolhido no config (null = padrão do sistema). */
  microfone: string | number | null
}

/** Retângulo em coordenadas da página (CSS px) — o main converte para a tela. */
export interface RetanguloPagina {
  x: number
  y: number
  width: number
  height: number
}

export type FaseArraste = 'inicio' | 'fim'

export type AcaoMenu =
  | { acao: 'esconder' }
  | { acao: 'microfone'; nome: string | null }
  | { acao: 'abrir' }
  | { acao: 'pausar' }
  | { acao: 'retomar' }
  | { acao: 'sair' }

export const CANAL_SITUACAO = 'janela:situacao' // main -> janelas (push) e invoke (inicial)
export const CANAL_MOUSE_PILULA = 'barra:mouse' // barra <-> main (dentro: boolean)
export const CANAL_ARRASTE = 'barra:arraste' // barra -> main (fase, dx, dy desde o aperto)
export const CANAL_ABRIR_MENU = 'barra:menu' // barra -> main (retângulo da pílula)
export const CANAL_ABRIR_HUB = 'barra:hub' // barra -> main
export const CANAL_DICA_VISTA = 'barra:dica-vista' // barra -> main
export const CANAL_REINICIAR_MOTOR = 'barra:reiniciar-motor' // barra -> main
export const CANAL_MENU_ACAO = 'menu:acao' // menu -> main (AcaoMenu)
export const CANAL_MENU_ALTURA = 'menu:altura' // menu -> main (altura do conteúdo)
export const CANAL_MENU_ABERTO = 'menu:aberto' // main -> menu (a cada abertura)
