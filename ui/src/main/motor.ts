import { EventEmitter } from 'node:events'
import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { basename, dirname, join, resolve } from 'node:path'
import type { ComandoMotor, EventoMotor } from '../shared/protocolo'

export interface OpcoesMotor {
  python: string
  args: string[]
  cwd: string
  env?: Record<string, string>
  /** Espera antes de reiniciar o processo que caiu (padrão 500 ms). */
  atrasoReinicioMs?: number
  /** Tempo máximo de um pedir() (padrão 10 s). */
  tempoLimitePedidoMs?: number
}

const MAX_REINICIOS = 3
const JANELA_REINICIO_MS = 60_000

interface PedidoPendente {
  resolver: (v: never) => void
  rejeitar: (e: Error) => void
  timer: NodeJS.Timeout
}

/**
 * Dono do processo do motor Python. Emite:
 *  - 'evento' (EventoMotor): cada linha JSON do stdout que não é resposta de pedido;
 *  - 'caiu' (código): o processo terminou sem termos pedido;
 *  - 'desistiu': caiu mais de 3 vezes em 60 s, não reinicia mais.
 */
export class MotorProcess extends EventEmitter {
  private filho?: ChildProcess
  private pendentes = new Map<number, PedidoPendente>()
  private proximoId = 1
  private quedas: number[] = []
  private encerrando = false
  private timerReinicio?: NodeJS.Timeout
  private resto = ''

  constructor(private readonly opcoes: OpcoesMotor) {
    super()
  }

  get pid(): number | undefined {
    return this.filho?.pid
  }

  iniciar(): void {
    if (this.filho) return
    this.encerrando = false
    const filho = spawn(this.opcoes.python, this.opcoes.args, {
      cwd: this.opcoes.cwd,
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUNBUFFERED: '1',
        ...this.opcoes.env
      },
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true
    })
    this.filho = filho
    this.resto = ''
    filho.stdout!.setEncoding('utf8')
    filho.stdout!.on('data', (trecho: string) => this.aoReceber(trecho))
    filho.stderr!.setEncoding('utf8')
    filho.stderr!.on('data', (t: string) => console.error('[motor stderr]', t.trimEnd()))
    // EPIPE ao escrever num processo que acabou de morrer não pode derrubar o Electron.
    filho.stdin!.on('error', () => {})
    filho.on('error', (e) => console.error('[motor] falha ao iniciar:', e.message))
    // 'close' (e não 'exit'): se o executável nem inicia, só 'error' + 'close' são emitidos.
    filho.on('close', (codigo) => this.aoSair(filho, codigo))
  }

  /** Nova tentativa pedida pela pessoa (ex.: clique em "Motor parou"): zera a contagem de quedas,
   * senão uma única queda logo depois já contaria como desistência de novo. */
  reiniciarManual(): void {
    this.quedas = []
    clearTimeout(this.timerReinicio)
    this.iniciar()
  }

  enviar(cmd: ComandoMotor): void {
    const stdin = this.filho?.stdin
    if (!stdin || stdin.destroyed || !stdin.writable) return
    stdin.write(JSON.stringify(cmd) + '\n')
  }

  pedir<T = unknown>(tipo: string, dados: object = {}): Promise<T> {
    const stdin = this.filho?.stdin
    if (!stdin || stdin.destroyed || !stdin.writable) {
      return Promise.reject(new Error('motor indisponível'))
    }
    const id = this.proximoId++
    const limite = this.opcoes.tempoLimitePedidoMs ?? 10_000
    return new Promise<T>((resolver, rejeitar) => {
      const timer = setTimeout(() => {
        this.pendentes.delete(id)
        rejeitar(new Error(`tempo esgotado esperando resposta de '${tipo}'`))
      }, limite)
      this.pendentes.set(id, { resolver: resolver as (v: never) => void, rejeitar, timer })
      this.enviar({ ...dados, tipo, id } as ComandoMotor)
    })
  }

  /** Pede ao motor para sair; se não sair em 2 s, mata o processo. */
  async parar(): Promise<void> {
    this.encerrando = true
    clearTimeout(this.timerReinicio)
    const filho = this.filho
    this.rejeitarPendentes(new Error('motor encerrado'))
    if (!filho) return
    if (filho.pid === undefined) {
      // Falha ao iniciar: não há processo para esperar.
      this.filho = undefined
      return
    }
    await new Promise<void>((fim) => {
      const matar = setTimeout(() => filho.kill(), 2000)
      filho.once('close', () => {
        clearTimeout(matar)
        fim()
      })
      this.enviar({ tipo: 'sair' })
      filho.stdin?.end()
    })
  }

  private aoReceber(trecho: string): void {
    this.resto += trecho
    const linhas = this.resto.split('\n')
    this.resto = linhas.pop() ?? ''
    for (const linha of linhas) this.processarLinha(linha.trim())
  }

  private processarLinha(linha: string): void {
    if (!linha) return
    let msg: unknown
    try {
      msg = JSON.parse(linha)
    } catch {
      console.warn('[motor] linha ignorada (não é JSON):', linha.slice(0, 200))
      return
    }
    if (
      typeof msg !== 'object' ||
      msg === null ||
      typeof (msg as { tipo?: unknown }).tipo !== 'string'
    ) {
      console.warn('[motor] mensagem ignorada (sem tipo):', linha.slice(0, 200))
      return
    }
    const m = msg as { tipo: string; id?: unknown }
    if (typeof m.id === 'number' && this.pendentes.has(m.id)) {
      const p = this.pendentes.get(m.id)!
      this.pendentes.delete(m.id)
      clearTimeout(p.timer)
      p.resolver(m as never)
      return
    }
    this.emit('evento', msg as EventoMotor)
  }

  private aoSair(filho: ChildProcess, codigo: number | null): void {
    if (this.filho !== filho) return
    this.filho = undefined
    this.rejeitarPendentes(new Error('motor caiu'))
    if (this.encerrando) return
    this.emit('caiu', codigo)
    const agora = Date.now()
    this.quedas = this.quedas.filter((t) => agora - t < JANELA_REINICIO_MS)
    this.quedas.push(agora)
    if (this.quedas.length > MAX_REINICIOS) {
      this.emit('desistiu')
      return
    }
    this.timerReinicio = setTimeout(() => this.iniciar(), this.opcoes.atrasoReinicioMs ?? 500)
  }

  private rejeitarPendentes(erro: Error): void {
    for (const p of this.pendentes.values()) {
      clearTimeout(p.timer)
      p.rejeitar(erro)
    }
    this.pendentes.clear()
  }
}

/**
 * Descobre como iniciar o motor.
 * Desenvolvimento: .venv do projeto. Empacotado: <instalação>\python e <instalação>\motor,
 * onde <instalação> é a pasta-mãe da pasta 'app' que contém o executável do Electron.
 */
export function resolverPython(
  empacotado: boolean,
  exeDoApp: string = process.execPath
): { python: string; args: string[]; cwd: string } {
  const args = ['-m', 'gillevoz', '--motor']
  if (empacotado) {
    const pastaApp = dirname(exeDoApp)
    const instalacao = basename(pastaApp).toLowerCase() === 'app' ? dirname(pastaApp) : pastaApp
    return {
      python: join(instalacao, 'python', 'pythonw.exe'),
      args,
      cwd: join(instalacao, 'motor')
    }
  }
  const raiz = resolverRaizDev()
  return { python: join(raiz, '.venv', 'Scripts', 'pythonw.exe'), args, cwd: raiz }
}

function resolverRaizDev(): string {
  // Sobe a partir da pasta atual até achar o pacote gillevoz (ui/ fica dentro da raiz).
  let atual = resolve(process.cwd())
  for (let i = 0; i < 5; i++) {
    if (existsSync(join(atual, 'gillevoz', '__main__.py'))) return atual
    atual = dirname(atual)
  }
  return 'C:\\Mudo Tech\\gillevoz'
}
