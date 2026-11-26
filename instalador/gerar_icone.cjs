// Gera instalador/icone.ico (16, 24, 32, 48, 64, 128, 256 px) e ui/resources/gillevoz.png (256 px)
// a partir de docs/icone/b-matriz-led.svg, desenhando o SVG com o próprio Chromium do Electron.
// Uso (na raiz do projeto):  ui\node_modules\.bin\electron instalador\gerar_icone.cjs
const { app, BrowserWindow } = require('electron')
const { readFileSync, writeFileSync } = require('node:fs')
const { join } = require('node:path')

const RAIZ = join(__dirname, '..')
const SVG = join(RAIZ, 'docs', 'icone', 'b-matriz-led.svg')
const ICO = join(__dirname, 'icone.ico')
const PNG = join(RAIZ, 'ui', 'resources', 'gillevoz.png')
const TAMANHOS = [16, 24, 32, 48, 64, 128, 256]

/** Desenha o SVG uma vez, grande (fundo transparente); os tamanhos do .ico saem reduzindo esta imagem. */
const BASE = 1024
async function desenhar() {
  const tamanho = BASE
  const janela = new BrowserWindow({
    width: tamanho,
    height: tamanho,
    show: false,
    frame: false,
    transparent: true,
    useContentSize: true,
    webPreferences: { offscreen: true }
  })
  janela.webContents.setZoomFactor(1)
  const svg = readFileSync(SVG, 'utf8')
  const html =
    '<html><body style="margin:0;background:transparent;overflow:hidden">' +
    `<img style="display:block;width:${tamanho}px;height:${tamanho}px" ` +
    `src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}"></body></html>`
  await janela.loadURL('data:text/html;base64,' + Buffer.from(html).toString('base64'))
  await new Promise((r) => setTimeout(r, 300))
  const img = await janela.webContents.capturePage()
  janela.destroy()
  return img
}

/** Entrada do .ico em DIB 32 bits (BGRA de baixo para cima + máscara AND zerada). */
function dib(img, tamanho) {
  const bgra = img.toBitmap() // BGRA no Windows, de cima para baixo
  const linha = tamanho * 4
  const mascaraLinha = Math.ceil(tamanho / 32) * 4
  const cab = Buffer.alloc(40)
  cab.writeUInt32LE(40, 0)
  cab.writeInt32LE(tamanho, 4)
  cab.writeInt32LE(tamanho * 2, 8) // altura dobrada (cor + máscara)
  cab.writeUInt16LE(1, 12)
  cab.writeUInt16LE(32, 14)
  cab.writeUInt32LE(linha * tamanho + mascaraLinha * tamanho, 20)
  // O Skia entrega alfa pré-multiplicado; o .ico espera a cor "pura".
  for (let i = 0; i < bgra.length; i += 4) {
    const a = bgra[i + 3]
    if (a > 0 && a < 255) {
      for (let c = 0; c < 3; c++) bgra[i + c] = Math.min(255, Math.round((bgra[i + c] * 255) / a))
    }
  }
  const pixels = Buffer.alloc(linha * tamanho)
  for (let y = 0; y < tamanho; y++) {
    bgra.copy(pixels, (tamanho - 1 - y) * linha, y * linha, (y + 1) * linha)
  }
  return Buffer.concat([cab, pixels, Buffer.alloc(mascaraLinha * tamanho)])
}

app.whenReady().then(async () => {
  const grande = await desenhar()
  const entradas = []
  for (const t of TAMANHOS) {
    // (a captura pode vir maior que BASE com escala de tela ≠ 100%; resize cuida disso)
    const img = grande.resize({ width: t, height: t, quality: 'best' })
    // 256 px vai em PNG (padrão do Windows); os menores em DIB, que todo leitor de .ico entende.
    entradas.push({ t, dados: t === 256 ? img.toPNG() : dib(img, t) })
    if (t === 256) writeFileSync(PNG, img.toPNG())
  }
  const cabecalho = Buffer.alloc(6)
  cabecalho.writeUInt16LE(1, 2) // tipo: ícone
  cabecalho.writeUInt16LE(entradas.length, 4)
  const diretorio = Buffer.alloc(16 * entradas.length)
  let deslocamento = 6 + diretorio.length
  entradas.forEach(({ t, dados }, i) => {
    const o = i * 16
    diretorio.writeUInt8(t === 256 ? 0 : t, o)
    diretorio.writeUInt8(t === 256 ? 0 : t, o + 1)
    diretorio.writeUInt16LE(1, o + 4) // planos
    diretorio.writeUInt16LE(32, o + 6) // bits por pixel
    diretorio.writeUInt32LE(dados.length, o + 8)
    diretorio.writeUInt32LE(deslocamento, o + 12)
    deslocamento += dados.length
  })
  writeFileSync(ICO, Buffer.concat([cabecalho, diretorio, ...entradas.map((e) => e.dados)]))
  console.log(`ok: ${ICO} (${TAMANHOS.join(', ')} px) e ${PNG}`)
  app.quit()
})
