// Ícone da bandeja do Windows: a matriz 5×5 de LEDs do ícone do app (docs/icone/b-matriz-led.svg),
// redesenhada em pixels inteiros para ficar nítida em 16 e 32 px, com a cor do estado.
import { Menu, Tray, nativeImage } from 'electron'
import { deflateSync } from 'node:zlib'
import type { EstadoMotor } from '../shared/protocolo'

type Rgb = [number, number, number]

const FUNDO: Rgb = [0x0b, 0x09, 0x12]
const BORDA: Rgb = [0x24, 0x1e, 0x30]
const APAGADO: Rgb = [0x14, 0x11, 0x1c]
// Cor do LED pela altura (de baixo para cima), igual ao ícone do app.
const POR_ALTURA: Rgb[] = [
  [0x78, 0x1c, 0x6d],
  [0xbb, 0x37, 0x54],
  [0xed, 0x69, 0x25],
  [0xfb, 0xb6, 0x1a],
  [0xfc, 0xff, 0xa4]
]
// pausado: o texto secundário #9A93A8 a ~45% sobre o fundo — mesma matriz, "apagada"
const PAUSADO: Rgb = [0x4a, 0x43, 0x58]
const ERRO: Rgb = [0xbb, 0x37, 0x54]

/** LEDs acesos por coluna (da esquerda para a direita). */
const ALTURAS_NORMAL = [2, 4, 5, 3, 1] // a "onda" do ícone do app
const ALTURAS_GRAVANDO = [3, 5, 5, 4, 2] // mais acesa

function corDoLed(estado: EstadoMotor, alturaLed: number): Rgb {
  if (estado === 'pausado') return PAUSADO
  if (estado === 'erro') return ERRO
  return POR_ALTURA[alturaLed]
}

/** Área coberta (0..1) de um retângulo arredondado num pixel, com 4×4 amostras. */
function cobertura(
  px: number,
  py: number,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
): number {
  let n = 0
  for (let sy = 0; sy < 4; sy++) {
    for (let sx = 0; sx < 4; sx++) {
      const qx = px + (sx + 0.5) / 4
      const qy = py + (sy + 0.5) / 4
      if (qx < x || qx > x + w || qy < y || qy > y + h) continue
      const cx = Math.min(Math.max(qx, x + r), x + w - r)
      const cy = Math.min(Math.max(qy, y + r), y + h - r)
      if ((qx - cx) ** 2 + (qy - cy) ** 2 <= r * r) n++
    }
  }
  return n / 16
}

/** Desenha o ícone em RGBA. 16 px: LED 2 px, vão 1 px. 32 px: LED 4 px, vão 2 px. */
export function desenharIcone(tamanho: 16 | 32, estado: EstadoMotor): Buffer {
  const led = tamanho === 16 ? 2 : 4
  const vao = tamanho === 16 ? 1 : 2
  const origem = (tamanho - (5 * led + 4 * vao)) / 2
  const raioFundo = tamanho === 16 ? 3.5 : 7
  const raioLed = tamanho === 16 ? 0 : 1
  const alturas = estado === 'gravando' ? ALTURAS_GRAVANDO : ALTURAS_NORMAL
  const px = Buffer.alloc(tamanho * tamanho * 4)

  for (let y = 0; y < tamanho; y++) {
    for (let x = 0; x < tamanho; x++) {
      const aFundo = cobertura(x, y, 0, 0, tamanho, tamanho, raioFundo)
      const aMiolo = cobertura(x, y, 1, 1, tamanho - 2, tamanho - 2, raioFundo - 1)
      // borda de 1 px (#241E30) em volta do fundo, como no ícone do app
      let cor: Rgb = BORDA.map((c, i) => c + (FUNDO[i] - c) * aMiolo) as Rgb
      for (let col = 0; col < 5; col++) {
        for (let lin = 0; lin < 5; lin++) {
          const lx = origem + col * (led + vao)
          const ly = origem + (4 - lin) * (led + vao) // lin 0 = embaixo
          const a = cobertura(x, y, lx, ly, led, led, raioLed)
          if (a === 0) continue
          const corLed = lin < alturas[col] ? corDoLed(estado, lin) : APAGADO
          cor = cor.map((c, i) => c + (corLed[i] - c) * a) as Rgb
        }
      }
      const o = (y * tamanho + x) * 4
      px[o] = Math.round(cor[0])
      px[o + 1] = Math.round(cor[1])
      px[o + 2] = Math.round(cor[2])
      px[o + 3] = Math.round(aFundo * 255)
    }
  }
  return px
}

// ---- PNG mínimo (RGBA 8 bits), para não depender de bibliotecas de imagem ----
const TABELA_CRC = Array.from({ length: 256 }, (_, n) => {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})

function crc32(buf: Buffer): number {
  let c = 0xffffffff
  for (const b of buf) c = TABELA_CRC[(c ^ b) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function bloco(tipo: string, dados: Buffer): Buffer {
  const tam = Buffer.alloc(4)
  tam.writeUInt32BE(dados.length)
  const corpo = Buffer.concat([Buffer.from(tipo, 'ascii'), dados])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(corpo))
  return Buffer.concat([tam, corpo, crc])
}

export function rgbaParaPng(rgba: Buffer, largura: number, altura: number): Buffer {
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(largura, 0)
  ihdr.writeUInt32BE(altura, 4)
  ihdr[8] = 8 // bits por canal
  ihdr[9] = 6 // RGBA
  const linhas = Buffer.alloc(altura * (largura * 4 + 1))
  for (let y = 0; y < altura; y++) {
    rgba.copy(linhas, y * (largura * 4 + 1) + 1, y * largura * 4, (y + 1) * largura * 4)
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    bloco('IHDR', ihdr),
    bloco('IDAT', deflateSync(linhas)),
    bloco('IEND', Buffer.alloc(0))
  ])
}

function imagemDoEstado(estado: EstadoMotor): Electron.NativeImage {
  const img = nativeImage.createEmpty()
  for (const [tamanho, escala] of [
    [16, 1],
    [32, 2]
  ] as const) {
    img.addRepresentation({
      scaleFactor: escala,
      width: tamanho,
      height: tamanho,
      buffer: rgbaParaPng(desenharIcone(tamanho, estado), tamanho, tamanho)
    })
  }
  return img
}

const DICA: Record<EstadoMotor, string> = {
  ocioso: 'GilleVoz',
  gravando: 'GilleVoz — gravando',
  transcrevendo: 'GilleVoz — transcrevendo',
  pausado: 'GilleVoz — pausado',
  erro: 'GilleVoz — erro'
}

export interface Bandeja {
  atualizar(estado: EstadoMotor): void
}

export function criarBandeja(acoes: {
  abrir(): void
  pausarOuRetomar(pausado: boolean): void
  sair(): void
  clicar(): void
}): Bandeja {
  const imagens = new Map<EstadoMotor, Electron.NativeImage>()
  const imagem = (e: EstadoMotor): Electron.NativeImage => {
    if (!imagens.has(e)) imagens.set(e, imagemDoEstado(e))
    return imagens.get(e)!
  }
  const tray = new Tray(imagem('ocioso'))
  let estadoAtual: EstadoMotor | undefined
  let menuPausado: boolean | undefined

  const montarMenu = (pausado: boolean): Menu =>
    Menu.buildFromTemplate([
      { label: 'Abrir GilleVoz', click: acoes.abrir },
      { label: pausado ? 'Retomar' : 'Pausar', click: () => acoes.pausarOuRetomar(pausado) },
      { type: 'separator' },
      { label: 'Sair', click: acoes.sair }
    ])

  tray.on('click', acoes.clicar)

  const atualizar = (estado: EstadoMotor): void => {
    if (estado === estadoAtual) return
    estadoAtual = estado
    tray.setImage(imagem(estado))
    tray.setToolTip(DICA[estado])
    const pausado = estado === 'pausado'
    if (pausado !== menuPausado) {
      menuPausado = pausado
      tray.setContextMenu(montarMenu(pausado))
    }
  }
  atualizar('ocioso')
  return { atualizar }
}
