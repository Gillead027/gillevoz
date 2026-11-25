// Máquina de estados do arraste da Flow Bar, sem Electron (testável).
// O renderer avisa início, sinais de vida ('segue') e soltura; o main chama tique() a cada 16 ms
// para a janela seguir o cursor. Sem sinal por `semSinalMs`, o arraste termina sozinho
// (o renderer sumiu ou a soltura se perdeu) em vez de deixar a barra presa ao cursor.

export interface Ponto {
  x: number
  y: number
}

export interface DepsArraste {
  cursor(): Ponto
  /** Move a janela para (x, y). */
  mover(x: number, y: number): void
  /** O arraste acabou (soltou ou desistiu): grudar na borda e salvar. */
  terminou(): void
  agora?: () => number
  semSinalMs?: number
}

export class Arraste {
  private estado?: { janela: Ponto; cursor: Ponto; ultimoSinal: number }

  constructor(private readonly deps: DepsArraste) {}

  get ativo(): boolean {
    return this.estado !== undefined
  }

  /** Começa a seguir o cursor. dx/dy = quanto o mouse já andou desde o aperto (o limiar). */
  iniciar(janela: Ponto, dx: number, dy: number): boolean {
    if (this.estado || !Number.isFinite(dx) || !Number.isFinite(dy)) return false
    const c = this.deps.cursor()
    this.estado = { janela, cursor: { x: c.x - dx, y: c.y - dy }, ultimoSinal: this.agora() }
    this.seguir()
    return true
  }

  /** Sinal de vida do renderer (botão ainda apertado). */
  sinal(): void {
    if (this.estado) this.estado.ultimoSinal = this.agora()
  }

  /** Chamado periodicamente: segue o cursor, ou termina se o renderer parou de dar sinal. */
  tique(): void {
    if (!this.estado) return
    if (this.agora() - this.estado.ultimoSinal > (this.deps.semSinalMs ?? 3000))
      return this.encerrar()
    this.seguir()
  }

  /** O renderer avisou que o botão foi solto. */
  soltar(): void {
    if (!this.estado) return
    this.seguir()
    this.encerrar()
  }

  private agora(): number {
    return (this.deps.agora ?? Date.now)()
  }

  private seguir(): void {
    const e = this.estado!
    const c = this.deps.cursor()
    this.deps.mover(e.janela.x + c.x - e.cursor.x, e.janela.y + c.y - e.cursor.y)
  }

  private encerrar(): void {
    this.estado = undefined // antes do callback: nada aqui pode voltar a chamar seguir/encerrar
    this.deps.terminou()
  }
}
