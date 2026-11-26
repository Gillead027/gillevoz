import type { ComandoMotor, EventoMotor } from '../shared/protocolo'
import type {
  AcaoJanelaHub,
  AcaoMenu,
  FaseArraste,
  InfoHub,
  PastaHub,
  RetanguloPagina,
  Situacao
} from '../shared/janelas'

/** Chamadas das janelas da Flow Bar e do menu (só o que elas precisam). */
export interface JanelaApi {
  /** Situação atual (pronto, estado, borda...). */
  situacao(): Promise<Situacao>
  /** Assina as mudanças de situação; devolve a função que cancela. */
  aoSituacao(cb: (s: Situacao) => void): () => void
  /** Barra: o mouse entrou/saiu da pílula (liga/desliga o clique atravessando). */
  mouseNaPilula(dentro: boolean): void
  /** Barra: o main percebeu que o mouse já saiu da janela (o Windows não avisou). */
  aoMouseFora(cb: () => void): () => void
  /** Barra: arraste começou (dx/dy já andados desde o aperto), continua (sinal) ou terminou;
   * quem move a janela seguindo o cursor é o main. */
  arrastar(fase: FaseArraste, dx: number, dy: number): void
  /** Barra: abre/fecha o menu ao lado da pílula. */
  abrirMenu(pilula: RetanguloPagina): void
  abrirHub(): void
  dicaVista(): void
  reiniciarMotor(): void
  /** Menu: escolheu uma opção. */
  acaoMenu(a: AcaoMenu): void
  /** Menu: altura do conteúdo, para a janela caber. */
  alturaMenu(altura: number): void
  /** Menu: foi aberto de novo (volta para a lista principal). */
  aoAbrirMenu(cb: () => void): () => void
}

/** Chamadas só do Hub (janela principal). */
export interface HubApi {
  /** Versão, pasta dos dados, "iniciar com o Windows" e o último `pronto` do motor. */
  info(): Promise<InfoHub>
  /** Barra de título própria: minimizar ou fechar (fechar só esconde). */
  janela(acao: AcaoJanelaHub): void
  /** Abre a pasta dos dados ou a dos logs no Explorer. */
  abrirPasta(qual: PastaHub): void
  /** Liga/desliga "iniciar com o Windows"; devolve o valor que ficou valendo. */
  iniciarComWindows(ligar: boolean): Promise<boolean>
  /** "Recarregar motor": reinicia o processo do motor. */
  recarregarMotor(): void
  /** Copia um texto para a área de transferência. */
  copiar(texto: string): void
}

export interface GilleVozApi {
  enviar(cmd: ComandoMotor): void
  pedir<T = unknown>(tipo: string, dados?: object): Promise<T>
  /** Assina os eventos do motor; devolve a função que cancela a assinatura. */
  aoEvento(cb: (e: EventoMotor) => void): () => void
  janela: JanelaApi
  hub: HubApi
}

declare global {
  interface Window {
    gillevoz: GilleVozApi
  }
}
