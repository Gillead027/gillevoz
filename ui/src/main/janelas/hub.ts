// Hub (DESENHO-V2 §8): janela normal, PODE ter foco (tem campos de texto). Sem moldura do Windows:
// a barra de título é própria. Fechar só esconde; quem encerra o app é "Sair" (menu/bandeja).
import { app, BrowserWindow, clipboard, ipcMain, shell } from 'electron'
import { join } from 'path'
import { carregarPagina } from './barra'
import {
  CANAL_HUB_ABRIR_PASTA,
  CANAL_HUB_COPIAR,
  CANAL_HUB_INFO,
  CANAL_HUB_INICIAR_WINDOWS,
  CANAL_HUB_JANELA,
  CANAL_HUB_RECARREGAR_MOTOR
} from '../../shared/janelas'
import type { InfoHub } from '../../shared/janelas'
import icone from '../../../resources/gillevoz.png?asset'

/** Nome da entrada "Executar" do Windows; o instalador escreve a mesma chave. */
const NOME_LOGIN = 'GilleVoz'
const FUNDO = '#000004'

/** Em desenvolvimento o executável é o electron.exe e precisa da pasta do app como argumento;
 * instalado, o padrão (o próprio GilleVoz.exe, sem argumentos) já está certo. */
const alvoLogin = (): { path?: string; args?: string[] } =>
  app.isPackaged ? {} : { path: process.execPath, args: [app.getAppPath()] }

/** A entrada "GilleVoz" do Executar está ligada? O `openAtLogin` do Electron procura pelo nome
 * padrão do app, não pelo `name` usado ao gravar; por isso confere também `launchItems`. */
function abreComWindows(): boolean {
  const s = app.getLoginItemSettings(alvoLogin())
  const exe = process.execPath.toLowerCase()
  return (
    s.openAtLogin ||
    (s.launchItems ?? []).some(
      (i) => i.name === NOME_LOGIN && i.enabled && i.path.toLowerCase() === exe
    )
  )
}

export interface Hub {
  janela: BrowserWindow
  /** Mostra e traz para a frente (restaura se estiver minimizado). */
  mostrar(): void
}

export interface OpcoesHub {
  pastaDados: string
  /** Último `pronto` do motor. */
  motor(): InfoHub['motor']
  recarregarMotor(): void
  /** O app está encerrando: aí fechar fecha de verdade. */
  encerrando(): boolean
}

export function criarHub(op: OpcoesHub): Hub {
  const janela = new BrowserWindow({
    title: 'GilleVoz',
    width: 960,
    height: 640,
    minWidth: 820,
    minHeight: 560,
    show: false,
    frame: false,
    backgroundColor: FUNDO,
    icon: icone,
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false
    }
  })
  carregarPagina(janela, 'hub')

  let pronta = false
  let mostrarQuandoPronta = false
  janela.once('ready-to-show', () => {
    pronta = true
    if (mostrarQuandoPronta) mostrar()
  })

  const mostrar = (): void => {
    if (janela.isDestroyed()) return
    if (!pronta) {
      mostrarQuandoPronta = true
      return
    }
    if (janela.isMinimized()) janela.restore()
    janela.show()
    janela.focus()
  }

  janela.on('close', (e) => {
    if (op.encerrando()) return
    e.preventDefault()
    janela.hide()
  })

  const doHub = (e: Electron.IpcMainEvent | Electron.IpcMainInvokeEvent): boolean =>
    !janela.isDestroyed() && e.sender === janela.webContents

  const aoJanela = (e: Electron.IpcMainEvent, acao: unknown): void => {
    if (!doHub(e)) return
    if (acao === 'minimizar') janela.minimize()
    else if (acao === 'fechar') janela.hide()
  }
  const aoAbrirPasta = (e: Electron.IpcMainEvent, qual: unknown): void => {
    if (!doHub(e)) return
    if (qual !== 'dados' && qual !== 'logs') return
    const pasta = qual === 'dados' ? op.pastaDados : join(op.pastaDados, 'logs')
    shell.openPath(pasta).then((erro) => {
      if (erro) console.error('[hub] não consegui abrir', pasta, erro)
    })
  }
  const aoRecarregar = (e: Electron.IpcMainEvent): void => {
    if (doHub(e)) op.recarregarMotor()
  }
  const aoCopiar = (e: Electron.IpcMainEvent, texto: unknown): void => {
    if (doHub(e) && typeof texto === 'string') clipboard.writeText(texto)
  }

  ipcMain.on(CANAL_HUB_JANELA, aoJanela)
  ipcMain.on(CANAL_HUB_ABRIR_PASTA, aoAbrirPasta)
  ipcMain.on(CANAL_HUB_RECARREGAR_MOTOR, aoRecarregar)
  ipcMain.on(CANAL_HUB_COPIAR, aoCopiar)
  ipcMain.handle(CANAL_HUB_INFO, (e): InfoHub => {
    if (!doHub(e)) throw new Error('só o Hub')
    return {
      versao: app.getVersion(),
      pastaDados: op.pastaDados,
      iniciarComWindows: abreComWindows(),
      motor: op.motor()
    }
  })
  ipcMain.handle(CANAL_HUB_INICIAR_WINDOWS, (e, ligar: unknown): boolean => {
    if (!doHub(e)) throw new Error('só o Hub')
    if (typeof ligar === 'boolean') {
      app.setLoginItemSettings({ openAtLogin: ligar, name: NOME_LOGIN, ...alvoLogin() })
    }
    return abreComWindows()
  })

  janela.on('closed', () => {
    ipcMain.removeListener(CANAL_HUB_JANELA, aoJanela)
    ipcMain.removeListener(CANAL_HUB_ABRIR_PASTA, aoAbrirPasta)
    ipcMain.removeListener(CANAL_HUB_RECARREGAR_MOTOR, aoRecarregar)
    ipcMain.removeListener(CANAL_HUB_COPIAR, aoCopiar)
    ipcMain.removeHandler(CANAL_HUB_INFO)
    ipcMain.removeHandler(CANAL_HUB_INICIAR_WINDOWS)
  })

  return { janela, mostrar }
}
