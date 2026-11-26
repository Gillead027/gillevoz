// Barra de título própria do Hub (a janela não tem moldura do Windows): área de arrastar, ícone do
// app, minimizar e fechar (fechar só esconde: o GilleVoz continua na bandeja).
import { IconMinus, IconX } from '@tabler/icons-react'
import icone from './icone.svg'

export default function BarraTitulo(): React.JSX.Element {
  const hub = window.gillevoz.hub
  return (
    <header className="barra-titulo">
      <div className="barra-titulo-marca">
        <img src={icone} alt="" width={16} height={16} draggable={false} />
        <span>GilleVoz</span>
      </div>
      <div className="barra-titulo-botoes">
        <button
          type="button"
          className="janela-botao"
          aria-label="Minimizar"
          title="Minimizar"
          onClick={() => hub.janela('minimizar')}
        >
          <IconMinus size={14} stroke={1.5} />
        </button>
        <button
          type="button"
          className="janela-botao fechar"
          aria-label="Fechar"
          title="Fechar (continua na bandeja)"
          onClick={() => hub.janela('fechar')}
        >
          <IconX size={14} stroke={1.5} />
        </button>
      </div>
    </header>
  )
}
