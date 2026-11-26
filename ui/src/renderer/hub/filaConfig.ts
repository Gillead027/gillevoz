// Fila de salvamento do config do Hub (sem React, para testar).
// - Manda só as chaves que mudaram: o motor junta {**antigo, **parcial} (gillevoz/motor.py salvar_config).
// - Um salvar_config por vez: o que mudar enquanto um está no ar vai junto no próximo lote.
// - Tela = último config do motor + lote no ar + mudanças ainda não enviadas (nada "volta" na tela).
// - Erro: descarta só as chaves do lote que falhou, sem desfazer as outras.

export type Cfg = Record<string, unknown>

export interface ResultadoSalvar {
  enviado: Cfg
  recebido: Cfg
}

export const MSG_FALHOU = 'Não consegui salvar: o motor não respondeu.'

type Espera = (r: ResultadoSalvar | null) => void

export interface OpcoesFila {
  /** Manda `salvar_config {cfg: parcial}` e devolve o config inteiro que o motor respondeu. */
  enviar(parcial: Cfg): Promise<Cfg>
  /** O que a tela mostra mudou (recebe o novo valor de `visivel()`). */
  aoMudar(visivel: Cfg | null): void
  /** Um lote falhou (a promessa de `salvar` também resolve com null). */
  aoFalhar?(msg: string): void
  /** Espera dos campos de texto (padrão 400 ms). */
  esperaTextoMs?: number
}

export class FilaConfig {
  private motor: Cfg | null = null
  private noAr: Cfg | null = null
  private pendentes: Cfg = {}
  private esperando: Espera[] = []
  /** Há mudança de interruptor/lista na fila: manda assim que o lote no ar voltar. */
  private urgente = false
  private timer: ReturnType<typeof setTimeout> | undefined

  constructor(private readonly op: OpcoesFila) {}

  /** Config que chegou do motor (resposta de ler_config ou evento `config`). */
  receber(cfg: unknown): void {
    if (!cfg || typeof cfg !== 'object') return
    this.motor = cfg as Cfg
    this.op.aoMudar(this.visivel())
    if (this.urgente) this.descarregar()
  }

  visivel(): Cfg | null {
    return this.motor ? { ...this.motor, ...this.noAr, ...this.pendentes } : null
  }

  /** Salva uma mudança. `adiar`: campo de texto (espera parar de digitar). A promessa resolve com
   * a resposta do lote em que a mudança foi (ou null se falhou). */
  salvar(mudanca: Cfg, opcoes: { adiar?: boolean } = {}): Promise<ResultadoSalvar | null> {
    this.pendentes = { ...this.pendentes, ...mudanca }
    const resposta = new Promise<ResultadoSalvar | null>((r) => this.esperando.push(r))
    this.op.aoMudar(this.visivel())
    if (opcoes.adiar) {
      clearTimeout(this.timer)
      this.timer = setTimeout(() => {
        this.timer = undefined
        this.descarregar()
      }, this.op.esperaTextoMs ?? 400)
    } else {
      this.urgente = true
      this.descarregar()
    }
    return resposta
  }

  /** Manda já o que estiver esperando (ex.: a página vai fechar). */
  agora(): void {
    if (this.timer) this.urgente = true
    this.descarregar()
  }

  private descarregar(): void {
    if (this.noAr || !this.motor || Object.keys(this.pendentes).length === 0) return
    clearTimeout(this.timer)
    this.timer = undefined
    this.urgente = false
    const lote = this.pendentes
    const esperas = this.esperando
    this.pendentes = {}
    this.esperando = []
    this.noAr = lote
    this.op.enviar(lote).then(
      (cfg) => {
        this.noAr = null
        this.motor = cfg && typeof cfg === 'object' ? cfg : { ...this.motor, ...lote }
        for (const e of esperas) e({ enviado: lote, recebido: this.motor })
        this.depoisDoLote()
      },
      () => {
        this.noAr = null
        for (const e of esperas) e(null)
        this.op.aoFalhar?.(MSG_FALHOU)
        this.depoisDoLote()
      }
    )
  }

  private depoisDoLote(): void {
    this.op.aoMudar(this.visivel())
    // Texto ainda sendo digitado espera o próprio prazo; o resto sai agora.
    if (this.urgente || !this.timer) this.descarregar()
  }
}
