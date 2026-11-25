// Janela da Flow Bar (DESENHO-V2 §7): transparente, sem moldura e SEM FOCO — clicar nela nunca tira
// o foco da janela onde a pessoa está digitando. Fora da pílula o clique atravessa a janela.
import { BrowserWindow, ipcMain, screen } from 'electron'
import { join } from 'path'
import { is } from '@electron-toolkit/utils'
import { bordaMaisProxima, calcularPosicao } from '../posicao'
import { CANAL_ARRASTE, CANAL_MOUSE_PILULA } from '../../shared/janelas'
import type { Borda, FaseArraste } from '../../shared/janelas'

export const TAMANHO_BARRA = { w: 360, h: 120 }
/** A pílula fica a 4 px da beirada da janela (sobra para o anel do mic); 10 + 4 = 14 px da borda da tela. */
const MARGEM_JANELA = 10
/** Arraste sem nenhum sinal do renderer por este tempo é dado como terminado. */
const SEM_SINAL_ARRASTE_MS = 3000

/** Opções comuns das janelas sem foco (barra e menu). */
export function opcoesSemFoco(): Electron.BrowserWindowConstructorOptions {
  return {
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    focusable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    hasShadow: false,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false
    }
  }
}

/** Carrega uma página do renderer (barra/ ou menu/) no dev server ou nos arquivos gerados. */
export function carregarPagina(janela: BrowserWindow, pagina: 'barra' | 'menu'): void {
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    janela.loadURL(`${process.env['ELECTRON_RENDERER_URL']}/${pagina}/index.html`)
  } else {
    janela.loadFile(join(__dirname, `../renderer/${pagina}/index.html`))
  }
}

export interface Barra {
  janela: BrowserWindow
  borda(): Borda
  esconderPor(ms: number): void
  mostrar(): void
}

export function criarBarra(
  inicial: { borda: Borda; pos: number },
  aoMudarLugar: (borda: Borda, pos: number) => void
): Barra {
  const janela = new BrowserWindow({
    ...opcoesSemFoco(),
    title: 'GilleVoz — Barra',
    width: TAMANHO_BARRA.w,
    height: TAMANHO_BARRA.h
  })
  janela.setAlwaysOnTop(true, 'screen-saver')
  janela.setIgnoreMouseEvents(true, { forward: true })
  carregarPagina(janela, 'barra')

  let borda = inicial.borda
  let pos = inicial.pos
  let arraste:
    | {
        janela: Electron.Rectangle
        cursor: Electron.Point
        timer: NodeJS.Timeout
        ultimoSinal: number
      }
    | undefined
  let animacao: NodeJS.Timeout | undefined
  let timerEsconder: NodeJS.Timeout | undefined
  let escondida = false

  const moverPara = (x: number, y: number): void => {
    if (janela.isDestroyed()) return
    // setBounds com tamanho fixo: em monitores com escalas diferentes setPosition pode redimensionar.
    janela.setBounds({
      x: Math.round(x),
      y: Math.round(y),
      width: TAMANHO_BARRA.w,
      height: TAMANHO_BARRA.h
    })
  }

  const posicionar = (ponto: Electron.Point, animar: boolean): void => {
    const area = screen.getDisplayNearestPoint(ponto).workArea
    const alvo = calcularPosicao(area, borda, pos, TAMANHO_BARRA, MARGEM_JANELA)
    clearInterval(animacao)
    if (!animar) return moverPara(alvo.x, alvo.y)
    // Desliza até a borda (160 ms, desacelerando).
    const de = janela.getBounds()
    const t0 = Date.now()
    animacao = setInterval(() => {
      const t = Math.min(1, (Date.now() - t0) / 160)
      const k = 1 - Math.pow(1 - t, 3)
      moverPara(de.x + (alvo.x - de.x) * k, de.y + (alvo.y - de.y) * k)
      if (t === 1) clearInterval(animacao)
    }, 16)
  }

  const centroAtual = (): Electron.Point => {
    const b = janela.getBounds()
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 }
  }

  // Abre no monitor do mouse.
  posicionar(screen.getCursorScreenPoint(), false)
  janela.once('ready-to-show', () => janela.showInactive())

  const ehDaBarra = (e: Electron.IpcMainEvent): boolean => e.sender === janela.webContents

  // Vigia: o Windows às vezes não avisa a saída do mouse (cursor que "pula" para longe); sem isso
  // a pílula ficaria aberta e a área transparente pararia de deixar o clique passar.
  let vigiaMouse: NodeJS.Timeout | undefined
  const mouseSaiu = (): void => {
    clearInterval(vigiaMouse)
    vigiaMouse = undefined
    if (janela.isDestroyed()) return
    janela.setIgnoreMouseEvents(true, { forward: true })
  }

  const aoMouse = (e: Electron.IpcMainEvent, dentro: boolean): void => {
    if (!ehDaBarra(e) || escondida) return
    if (!dentro) {
      if (!arraste) mouseSaiu()
      return
    }
    janela.setIgnoreMouseEvents(false)
    clearInterval(vigiaMouse)
    vigiaMouse = setInterval(() => {
      if (arraste || janela.isDestroyed()) return
      const c = screen.getCursorScreenPoint()
      const b = janela.getBounds()
      if (c.x >= b.x && c.x < b.x + b.width && c.y >= b.y && c.y < b.y + b.height) return
      mouseSaiu()
      janela.webContents.send(CANAL_MOUSE_PILULA, false)
    }, 150)
  }

  // Arraste: o renderer só avisa quando começa e quando solta; quem segue o cursor é o main.
  // (Numa janela sem foco a captura do ponteiro não segura os eventos quando a janela se move:
  // depois do primeiro movimento o renderer parava de receber o mouse.)
  const seguirCursor = (): void => {
    if (!arraste) return
    // Rede de segurança: sem sinal do renderer por 3 s, o botão provavelmente foi solto fora da
    // janela (o pointerup se perdeu). Termina o arraste em vez de deixar a barra presa ao cursor.
    if (Date.now() - arraste.ultimoSinal > SEM_SINAL_ARRASTE_MS) return soltar()
    const c = screen.getCursorScreenPoint()
    moverPara(arraste.janela.x + c.x - arraste.cursor.x, arraste.janela.y + c.y - arraste.cursor.y)
  }

  const soltar = (): void => {
    if (!arraste) return
    seguirCursor()
    clearInterval(arraste.timer)
    arraste = undefined
    const centro = centroAtual()
    const area = screen.getDisplayNearestPoint(centro).workArea
    ;({ borda, pos } = bordaMaisProxima(area, centro))
    pos = Math.round(pos * 1000) / 1000
    posicionar(centro, true)
    aoMudarLugar(borda, pos)
  }

  const aoArrastar = (
    e: Electron.IpcMainEvent,
    fase: FaseArraste,
    dx: number,
    dy: number
  ): void => {
    if (!ehDaBarra(e)) return
    if (fase === 'fim') return soltar()
    if (fase === 'segue') {
      if (arraste) arraste.ultimoSinal = Date.now()
      return
    }
    if (arraste || !Number.isFinite(dx) || !Number.isFinite(dy)) return
    clearInterval(animacao)
    const c = screen.getCursorScreenPoint()
    // dx/dy: quanto o mouse já andou desde que o botão foi apertado (o limiar do arraste).
    arraste = {
      janela: janela.getBounds(),
      cursor: { x: c.x - dx, y: c.y - dy },
      timer: setInterval(seguirCursor, 16),
      ultimoSinal: Date.now()
    }
    seguirCursor()
  }

  ipcMain.on(CANAL_MOUSE_PILULA, aoMouse)
  ipcMain.on(CANAL_ARRASTE, aoArrastar)

  // Barra de tarefas mudou, resolução mudou, monitor saiu: volta para o lugar salvo.
  const reposicionar = (): void => {
    if (!arraste) posicionar(centroAtual(), false)
  }
  screen.on('display-metrics-changed', reposicionar)
  screen.on('display-removed', reposicionar)

  janela.on('closed', () => {
    clearInterval(animacao)
    clearInterval(arraste?.timer)
    clearInterval(vigiaMouse)
    clearTimeout(timerEsconder)
    ipcMain.removeListener(CANAL_MOUSE_PILULA, aoMouse)
    ipcMain.removeListener(CANAL_ARRASTE, aoArrastar)
    screen.removeListener('display-metrics-changed', reposicionar)
    screen.removeListener('display-removed', reposicionar)
  })

  const mostrar = (): void => {
    clearTimeout(timerEsconder)
    if (janela.isDestroyed() || !escondida) return
    escondida = false
    janela.setOpacity(1)
    janela.setIgnoreMouseEvents(true, { forward: true })
  }

  return {
    janela,
    borda: () => borda,
    esconderPor: (ms) => {
      // Sem hide(): janela sem foco escondida e mostrada de novo para de receber cliques (ver menu.ts).
      escondida = true
      clearInterval(vigiaMouse)
      vigiaMouse = undefined
      janela.setOpacity(0)
      janela.setIgnoreMouseEvents(true)
      clearTimeout(timerEsconder)
      timerEsconder = setTimeout(mostrar, ms)
    },
    mostrar
  }
}
