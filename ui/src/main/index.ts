import { app, BrowserWindow, ipcMain } from 'electron'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { electronApp, optimizer } from '@electron-toolkit/utils'
import { MotorProcess, anunciarOciosoAoCair, resolverPython } from './motor'
import { criarBarra, type Barra } from './janelas/barra'
import { criarMenu, type Menu } from './janelas/menu'
import { criarHub, type Hub } from './janelas/hub'
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
import type { AcaoMenu, Borda, InfoHub, RetanguloPagina, Situacao } from '../shared/janelas'

let motor: MotorProcess | undefined
let barra: Barra | undefined
let menu: Menu | undefined
let bandeja: Bandeja | undefined
let hub: Hub | undefined
/** Último `pronto` do motor (o Hub mostra o dispositivo/modelo efetivos). */
let ultimoPronto: InfoHub['motor'] = null
/** O app está encerrando (fechar o Hub deixa de só esconder). */
let encerrando = false

// Os arquivos internos do Chromium (cache, armazenamento) ficam em %LOCALAPPDATA%\GilleVoz.
// O padrão seria %APPDATA%\<productName> = %APPDATA%\GilleVoz, a pasta de dados do motor: criá-la
// antes do motor impediria a migração do v1 (DESENHO-V2 §11) e misturaria cache com os dados.
// Precisa vir antes do requestSingleInstanceLock (a trava usa essa pasta).
app.setPath('userData', join(process.env['LOCALAPPDATA'] || app.getPath('temp'), 'GilleVoz'))

// Uma instância só: abrir o GilleVoz de novo (atalho do Menu Iniciar) mostra o Hub da que já roda.
const primeiraInstancia = app.requestSingleInstanceLock()
if (!primeiraInstancia) app.quit()
else app.on('second-instance', () => abrirHub())

const UMA_HORA_MS = 60 * 60 * 1000

/** Pasta dos dados do usuário (a mesma que o motor usa). */
const pastaDados = (): string =>
  process.env['GILLEVOZ_DADOS'] || join(app.getPath('appData'), 'GilleVoz')

/** Lê o config.json direto do disco (só leitura) para a barra já abrir no lugar certo:
 * o motor só responde `ler_config` depois de carregar o modelo. */
function lerConfigLocal(): Record<string, unknown> {
  try {
    const cfg = JSON.parse(readFileSync(join(pastaDados(), 'config.json'), 'utf8'))
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

/** "Mostrar a barra sempre" (barra_ativa). Desligado: a barra só aparece enquanto dita. */
let barraSempre = cfgInicial['barra_ativa'] !== false

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
  for (const janela of [barra?.janela, menu?.janela, hub?.janela]) {
    if (janela && !janela.isDestroyed()) janela.webContents.send(CANAL_SITUACAO, situacao)
  }
  bandeja?.atualizar(situacao.desistiu ? 'erro' : situacao.estado)
  aplicarVisibilidadeBarra()
}

function aplicarVisibilidadeBarra(): void {
  if (!barra || barraSempre) return
  const ditando = ['gravando', 'transcrevendo', 'erro'].includes(situacao.estado)
  if (ditando || situacao.desistiu) barra.mostrar()
  else barra.esconder()
}

function aoConfig(cfg: Record<string, unknown>): void {
  const sempre = cfg['barra_ativa'] !== false
  if (sempre && !barraSempre) barra?.mostrar()
  barraSempre = sempre
  atualizarSituacao({
    microfone: microfoneDo(cfg),
    mostrarDica: cfg['dica_arraste_vista'] !== true
  })
}

function salvarConfig(cfg: Record<string, unknown>): void {
  motor?.enviar({ tipo: 'salvar_config', cfg })
}

/** Abre o Hub (janela principal); a janela é criada na primeira vez e depois só escondida. */
function abrirHub(): void {
  if (!app.isReady()) return
  if (!hub || hub.janela.isDestroyed()) {
    hub = criarHub({
      pastaDados: pastaDados(),
      motor: () => ultimoPronto,
      recarregarMotor: reiniciarMotor,
      encerrando: () => encerrando
    })
  }
  hub.mostrar()
}

/** Reinício pedido pela pessoa (clique em "Motor parou" ou "Recarregar motor" no Hub). */
function reiniciarMotor(): void {
  if (!motor) return
  ultimoPronto = null
  atualizarSituacao({ desistiu: false, estado: 'ocioso', pronto: false })
  // Rodando: para e sobe de novo; parado (desistiu): só sobe.
  if (motor.pid === undefined) motor.reiniciarManual()
  else
    motor.parar().then(() => {
      if (!encerrando) motor?.reiniciarManual()
    })
}

function aoEventoDoMotor(e: EventoMotor): void {
  for (const janela of BrowserWindow.getAllWindows()) {
    if (!janela.isDestroyed()) janela.webContents.send(CANAL_EVENTO, e)
  }
  if (e.tipo === 'pronto') {
    ultimoPronto = { dispositivo: e.dispositivo ?? null, modelo: e.modelo ?? null }
    atualizarSituacao({ pronto: true, desistiu: false })
  } else if (e.tipo === 'estado') atualizarSituacao({ estado: e.estado, msg: e.msg })
  else if (e.tipo === 'config') aoConfig(e.cfg)
}

function iniciarMotor(): void {
  const { python, args, cwd } = resolverPython(app.isPackaged)
  motor = new MotorProcess({ python, args, cwd })
  motor.on('evento', aoEventoDoMotor)
  // Review Focus 5: caiu no meio de uma gravação → todas as janelas recebem `estado ocioso`.
  anunciarOciosoAoCair(motor, aoEventoDoMotor)
  motor.on('caiu', (codigo) => {
    console.error('[motor] caiu, código', codigo)
    ultimoPronto = null
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
  if (!primeiraInstancia) return
  electronApp.setAppUserModelId('com.gillevoz.app')
  app.on('browser-window-created', (_, janela) => optimizer.watchWindowShortcuts(janela))

  ipcMain.on(CANAL_ENVIAR, (_, cmd: ComandoMotor) => motor?.enviar(cmd))
  ipcMain.handle(CANAL_PEDIR, async (_, tipo: string, dados?: object) => {
    if (!motor) throw new Error('motor não iniciado')
    const resposta = await motor.pedir<{ tipo?: string; cfg?: Record<string, unknown> }>(
      tipo,
      dados
    )
    // salvar_config responde com o próprio evento `config` (com id): as outras janelas e a
    // situação da barra também precisam saber da mudança.
    if (resposta?.tipo === 'config' && resposta.cfg && typeof resposta.cfg === 'object') {
      aoEventoDoMotor({ tipo: 'config', cfg: resposta.cfg })
    }
    return resposta
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
    reiniciarMotor()
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
  aplicarVisibilidadeBarra() // "mostrar a barra sempre" desligado já esconde ao abrir
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
  encerrando = true
  if (saindo || !motor) return
  e.preventDefault()
  saindo = true
  motor.parar().finally(() => app.quit())
})

app.on('window-all-closed', () => app.quit())
