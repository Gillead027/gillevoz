import { app, BrowserWindow, ipcMain } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { MotorProcess, resolverPython } from './motor'
import { CANAL_ENVIAR, CANAL_EVENTO, CANAL_PEDIR } from '../shared/protocolo'
import type { ComandoMotor, EventoMotor } from '../shared/protocolo'

let motor: MotorProcess | undefined

function iniciarMotor(): void {
  const { python, args, cwd } = resolverPython(app.isPackaged)
  motor = new MotorProcess({ python, args, cwd })
  motor.on('evento', (e: EventoMotor) => {
    for (const janela of BrowserWindow.getAllWindows()) {
      if (!janela.isDestroyed()) janela.webContents.send(CANAL_EVENTO, e)
    }
  })
  motor.on('caiu', (codigo) => console.error('[motor] caiu, código', codigo))
  motor.on('desistiu', () => console.error('[motor] caiu 4 vezes em 60 s; sem novas tentativas'))
  motor.iniciar()
}

// Janela provisória (oculta): carrega o renderer com a ponte. Flow Bar e Hub vêm nas Tarefas 8-9.
function criarJanelaProvisoria(): void {
  const janela = new BrowserWindow({
    width: 900,
    height: 670,
    show: false,
    webPreferences: { preload: join(__dirname, '../preload/index.js'), sandbox: false }
  })
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    janela.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    janela.loadFile(join(__dirname, '../renderer/index.html'))
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

  iniciarMotor()
  criarJanelaProvisoria()
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
