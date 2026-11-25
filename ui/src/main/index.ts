import { app, BrowserWindow, ipcMain } from 'electron'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { electronApp, optimizer } from '@electron-toolkit/utils'
import { MotorProcess, resolverPython } from './motor'
import { criarBarra, type Barra } from './janelas/barra'
import { criarMenu, type Menu } from './janelas/menu'
import { criarBandeja, type Bandeja } from './bandeja'
import { CANAL_ENVIAR, CANAL_EVENTO, CANAL_PEDIR } from '../shared/protocolo'
import type { ComandoMotor, EventoMotor } from '../shared/protocolo'
import {
  CANAL_ABRIR_HUB,
  CANAL_ABRIR_MENU,
  CANAL_DICA_VISTA,
  CANAL_MENU_ACAO,
  CANAL_REINICIAR_MOTOR,
  CANAL_SITUACAO
} from '../shared/janelas'
import type { AcaoMenu, Borda, RetanguloPagina, Situacao } from '../shared/janelas'

let motor: MotorProcess | undefined
let barra: Barra | undefined
let menu: Menu | undefined
let bandeja: Bandeja | undefined

const UMA_HORA_MS = 60 * 60 * 1000

/** Lê o config.json direto do disco (só leitura) para a barra já abrir no lugar certo:
 * o motor só responde `ler_config` depois de carregar o modelo. */
function lerConfigLocal(): Record<string, unknown> {
  const pasta = process.env['GILLEVOZ_DADOS'] || join(app.getPath('appData'), 'GilleVoz')
  try {
    const cfg = JSON.parse(readFileSync(join(pasta, 'config.json'), 'utf8'))
    return cfg && typeof cfg === 'object' ? cfg : {}
  } catch {
    return {}
  }
}

const cfgInicial = lerConfigLocal()
const bordaValida = (b: unknown): Borda =>
  b === 'esquerda' || b === 'direita' || b === 'embaixo' ? b : 'embaixo'
const microfoneDo = (cfg: Record<string, unknown>): string | number | null => {
  const m = cfg['microfone']
  return typeof m === 'string' || typeof m === 'number' ? m : null
}

const situacao: Situacao = {
  pronto: false,
  estado: 'ocioso',
  desistiu: false,
  borda: bordaValida(cfgInicial['barra_borda']),
  mostrarDica: cfgInicial['dica_arraste_vista'] !== true,
  microfone: microfoneDo(cfgInicial)
}

function atualizarSituacao(mudancas: Partial<Situacao>): void {
  Object.assign(situacao, mudancas)
  if (!('msg' in mudancas) && 'estado' in mudancas) delete situacao.msg
  for (const janela of [barra?.janela, menu?.janela]) {
    if (janela && !janela.isDestroyed()) janela.webContents.send(CANAL_SITUACAO, situacao)
  }
  bandeja?.atualizar(situacao.desistiu ? 'erro' : situacao.estado)
}

function salvarConfig(cfg: Record<string, unknown>): void {
  motor?.enviar({ tipo: 'salvar_config', cfg })
}

/** Abre o Hub (janela principal). */
function abrirHub(): void {
  // TODO(Tarefa 9): criar/mostrar a janela do Hub. Por enquanto só registra o pedido.
  console.log('[hub] abrir o Hub (ainda não existe: Tarefa 9)')
}

function aoEventoDoMotor(e: EventoMotor): void {
  for (const janela of BrowserWindow.getAllWindows()) {
    if (!janela.isDestroyed()) janela.webContents.send(CANAL_EVENTO, e)
  }
  if (e.tipo === 'pronto') atualizarSituacao({ pronto: true, desistiu: false })
  else if (e.tipo === 'estado') atualizarSituacao({ estado: e.estado, msg: e.msg })
  else if (e.tipo === 'config') {
    atualizarSituacao({
      microfone: microfoneDo(e.cfg),
      mostrarDica: e.cfg['dica_arraste_vista'] !== true
    })
  }
}

function iniciarMotor(): void {
  const { python, args, cwd } = resolverPython(app.isPackaged)
  motor = new MotorProcess({ python, args, cwd })
  motor.on('evento', aoEventoDoMotor)
  motor.on('caiu', (codigo) => {
    console.error('[motor] caiu, código', codigo)
    // Enquanto reinicia, a barra volta ao "carregando".
    atualizarSituacao({ pronto: false, estado: 'ocioso' })
  })
  motor.on('desistiu', () => {
    console.error('[motor] caiu 4 vezes em 60 s; sem novas tentativas')
    atualizarSituacao({ desistiu: true, estado: 'erro', msg: 'Motor parou' })
  })
  motor.iniciar()
}

const daBarra = (e: Electron.IpcMainEvent): boolean => e.sender === barra?.janela.webContents

const retanguloValido = (r: unknown): r is RetanguloPagina =>
  typeof r === 'object' &&
  r !== null &&
  (['x', 'y', 'width', 'height'] as const).every((k) =>
    Number.isFinite((r as Record<string, unknown>)[k])
  )

/** Confere o formato da ação que veio do menu (não confiar no que chega por IPC). */
function acaoValida(a: unknown): a is AcaoMenu {
  if (typeof a !== 'object' || a === null) return false
  const { acao, nome } = a as { acao?: unknown; nome?: unknown }
  if (acao === 'microfone') return nome === null || typeof nome === 'string'
  return ['esconder', 'abrir', 'pausar', 'retomar', 'sair'].includes(acao as string)
}

function aoAcaoDoMenu(a: AcaoMenu): void {
  menu?.fechar()
  switch (a.acao) {
    case 'esconder':
      barra?.esconderPor(UMA_HORA_MS)
      break
    case 'microfone':
      salvarConfig({ microfone: a.nome })
      break
    case 'abrir':
      abrirHub()
      break
    case 'pausar':
    case 'retomar':
      motor?.enviar({ tipo: a.acao })
      break
    case 'sair':
      app.quit()
      break
  }
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.gillevoz.app')
  app.on('browser-window-created', (_, janela) => optimizer.watchWindowShortcuts(janela))

  ipcMain.on(CANAL_ENVIAR, (_, cmd: ComandoMotor) => motor?.enviar(cmd))
  ipcMain.handle(CANAL_PEDIR, (_, tipo: string, dados?: object) => {
    if (!motor) return Promise.reject(new Error('motor não iniciado'))
    return motor.pedir(tipo, dados)
  })
  ipcMain.handle(CANAL_SITUACAO, () => situacao)
  ipcMain.on(CANAL_ABRIR_HUB, (e) => {
    if (daBarra(e)) abrirHub()
  })
  ipcMain.on(CANAL_DICA_VISTA, (e) => {
    if (!daBarra(e)) return
    atualizarSituacao({ mostrarDica: false })
    salvarConfig({ dica_arraste_vista: true })
  })
  ipcMain.on(CANAL_REINICIAR_MOTOR, (e) => {
    if (!daBarra(e) || !situacao.desistiu) return
    atualizarSituacao({ desistiu: false, estado: 'ocioso', pronto: false })
    motor?.reiniciarManual()
  })
  ipcMain.on(CANAL_MENU_ACAO, (e, a: unknown) => {
    if (menu && e.sender === menu.janela.webContents && acaoValida(a)) aoAcaoDoMenu(a)
  })
  ipcMain.on(CANAL_ABRIR_MENU, (e, r: RetanguloPagina) => {
    if (!barra || !menu || !daBarra(e) || !retanguloValido(r)) return
    const b = barra.janela.getBounds()
    menu.alternar({ x: b.x + r.x, y: b.y + r.y, width: r.width, height: r.height }, barra.borda())
  })

  iniciarMotor()

  const pos = Number(cfgInicial['barra_pos'])
  barra = criarBarra(
    { borda: situacao.borda, pos: Number.isFinite(pos) ? pos : 0.5 },
    (borda, novaPos) => {
      atualizarSituacao({ borda })
      salvarConfig({ barra_borda: borda, barra_pos: novaPos })
    }
  )
  menu = criarMenu()
  bandeja = criarBandeja({
    abrir: abrirHub,
    pausarOuRetomar: (pausado) => motor?.enviar({ tipo: pausado ? 'retomar' : 'pausar' }),
    sair: () => app.quit(),
    clicar: () => barra?.mostrar()
  })
})

// Fechar o Electron encerra o motor.
let saindo = false
app.on('before-quit', (e) => {
  if (saindo || !motor) return
  e.preventDefault()
  saindo = true
  motor.parar().finally(() => app.quit())
})

app.on('window-all-closed', () => app.quit())
