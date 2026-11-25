// Menu do clique direito da barra (DESENHO-V2 §7). Menu nativo do Windows traria a janela dona para a
// frente e roubaria o foco; por isso é HTML numa janela sem foco, igual à barra.
// Sem foco não existe 'blur': o menu fecha quando o mouse fica 600 ms fora dele (e da pílula) ou ao escolher.
import { BrowserWindow, ipcMain, screen } from 'electron'
import { carregarPagina, opcoesSemFoco } from './barra'
import { CANAL_MENU_ABERTO, CANAL_MENU_ALTURA } from '../../shared/janelas'
import type { Borda } from '../../shared/janelas'

const LARGURA = 236
const VAO = 8 // distância entre a pílula e o menu
const FORA_FECHA_MS = 600
const VIGIA_MS = 50

export interface Menu {
  janela: BrowserWindow
  /** Abre ao lado da pílula (retângulo em coordenadas de tela); se já estiver aberto, fecha. */
  alternar(pilula: Electron.Rectangle, borda: Borda): void
  fechar(): void
  aberto(): boolean
}

const dentro = (p: Electron.Point, r: Electron.Rectangle, folga = 0): boolean =>
  p.x >= r.x - folga &&
  p.x < r.x + r.width + folga &&
  p.y >= r.y - folga &&
  p.y < r.y + r.height + folga

export function criarMenu(): Menu {
  const janela = new BrowserWindow({
    ...opcoesSemFoco(),
    title: 'GilleVoz — Menu',
    width: LARGURA,
    height: 200
  })
  janela.setAlwaysOnTop(true, 'screen-saver')
  carregarPagina(janela, 'menu')
  // Fechado = invisível e com o clique atravessando, mas sem hide(): no Windows, uma janela sem foco
  // que foi escondida e mostrada de novo para de receber cliques (só o movimento do mouse chega).
  let aberto = false
  janela.setOpacity(0)
  janela.setIgnoreMouseEvents(true)
  janela.once('ready-to-show', () => janela.showInactive())

  let altura = 200
  let ancora: { pilula: Electron.Rectangle; borda: Borda } | undefined
  let vigia: NodeJS.Timeout | undefined

  const posicionar = (): void => {
    if (!ancora || janela.isDestroyed()) return
    const { pilula, borda } = ancora
    const area = screen.getDisplayNearestPoint({ x: pilula.x, y: pilula.y }).workArea
    let x: number
    let y: number
    if (borda === 'embaixo') {
      x = pilula.x + pilula.width / 2 - LARGURA / 2
      y = pilula.y - VAO - altura
    } else {
      x = borda === 'esquerda' ? pilula.x + pilula.width + VAO : pilula.x - VAO - LARGURA
      y = pilula.y + pilula.height / 2 - altura / 2
    }
    x = Math.min(Math.max(x, area.x + 4), area.x + area.width - LARGURA - 4)
    y = Math.min(Math.max(y, area.y + 4), area.y + area.height - altura - 4)
    janela.setBounds({ x: Math.round(x), y: Math.round(y), width: LARGURA, height: altura })
  }

  const fechar = (): void => {
    clearInterval(vigia)
    vigia = undefined
    ancora = undefined
    aberto = false
    if (janela.isDestroyed()) return
    janela.setOpacity(0)
    janela.setIgnoreMouseEvents(true)
  }

  const vigiar = (): void => {
    let foraDesde: number | undefined
    clearInterval(vigia)
    vigia = setInterval(() => {
      if (!ancora || janela.isDestroyed()) return fechar()
      const p = screen.getCursorScreenPoint()
      const seguro = dentro(p, janela.getBounds()) || dentro(p, ancora.pilula, 6)
      if (seguro) foraDesde = undefined
      else if (foraDesde === undefined) foraDesde = Date.now()
      else if (Date.now() - foraDesde >= FORA_FECHA_MS) fechar()
    }, VIGIA_MS)
  }

  ipcMain.on(CANAL_MENU_ALTURA, (e, h: number) => {
    if (e.sender !== janela.webContents || !Number.isFinite(h)) return
    altura = Math.max(40, Math.min(600, Math.ceil(h)))
    posicionar()
  })

  return {
    janela,
    fechar,
    aberto: () => aberto,
    alternar: (pilula, borda) => {
      if (aberto) return fechar()
      aberto = true
      ancora = { pilula, borda }
      janela.webContents.send(CANAL_MENU_ABERTO)
      posicionar()
      janela.setIgnoreMouseEvents(false)
      janela.setOpacity(1)
      janela.moveTop()
      vigiar()
    }
  }
}
