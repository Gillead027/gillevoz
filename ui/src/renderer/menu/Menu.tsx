// Menu do clique direito da Flow Bar (DESENHO-V2 §7), desenhado numa janela sem foco.
// Destaque que desliza entre as linhas: ideia do Glide Select (React Bits) / Glide Pill Tabs (MicroKit),
// 300 ms cubic-bezier(.32,.72,0,1), fade 180 ms (REFERENCIAS-UI §2). Código próprio.
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  IconCheck,
  IconChevronLeft,
  IconChevronRight,
  IconEyeOff,
  IconLayoutSidebar,
  IconMicrophone,
  IconPlayerPause,
  IconPlayerPlay,
  IconPower
} from '@tabler/icons-react'
import type { AcaoMenu, Situacao } from '../../shared/janelas'

interface Microfone {
  indice: number
  nome: string
}

type Lista = 'principal' | 'microfones'

interface Linha {
  id: string
  rotulo: string
  icone?: React.ReactNode
  fim?: React.ReactNode
  perigo?: boolean
  inativa?: boolean
  aoEscolher?: () => void
}

const ICONE = { size: 16, stroke: 1.5 }

export default function Menu(): React.JSX.Element {
  const api = window.gillevoz
  const [s, setS] = useState<Situacao | null>(null)
  const [lista, setLista] = useState<Lista>('principal')
  const [mics, setMics] = useState<Microfone[] | 'carregando' | 'erro'>('carregando')
  const raiz = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.janela.situacao().then(setS)
    const pararSituacao = api.janela.aoSituacao(setS)
    const pararAbrir = api.janela.aoAbrirMenu(() => setLista('principal'))
    return () => {
      pararSituacao()
      pararAbrir()
    }
  }, [api])

  // A janela acompanha a altura do conteúdo.
  useLayoutEffect(() => {
    const el = raiz.current
    if (!el) return
    const medir = (): void => api.janela.alturaMenu(el.getBoundingClientRect().height)
    medir()
    const obs = new ResizeObserver(medir)
    obs.observe(el)
    return () => obs.disconnect()
  }, [api])

  const escolher = (a: AcaoMenu): void => api.janela.acaoMenu(a)

  const abrirMicrofones = (): void => {
    setLista('microfones')
    setMics('carregando')
    api
      .pedir<{ itens?: Microfone[] }>('listar_microfones')
      .then((r) => setMics(Array.isArray(r.itens) ? r.itens : []))
      .catch(() => setMics('erro'))
  }

  const pausado = s?.estado === 'pausado'
  let linhas: Linha[]
  if (lista === 'principal') {
    linhas = [
      {
        id: 'esconder',
        rotulo: 'Esconder por 1 hora',
        icone: <IconEyeOff {...ICONE} />,
        aoEscolher: () => escolher({ acao: 'esconder' })
      },
      {
        id: 'microfone',
        rotulo: 'Microfone',
        icone: <IconMicrophone {...ICONE} />,
        fim: <IconChevronRight size={14} stroke={1.5} />,
        aoEscolher: abrirMicrofones
      },
      {
        id: 'abrir',
        rotulo: 'Abrir GilleVoz',
        icone: <IconLayoutSidebar {...ICONE} />,
        aoEscolher: () => escolher({ acao: 'abrir' })
      },
      {
        id: 'pausar',
        rotulo: pausado ? 'Retomar' : 'Pausar',
        icone: pausado ? <IconPlayerPlay {...ICONE} /> : <IconPlayerPause {...ICONE} />,
        aoEscolher: () => escolher({ acao: pausado ? 'retomar' : 'pausar' })
      },
      { id: '-', rotulo: '' },
      {
        id: 'sair',
        rotulo: 'Sair',
        icone: <IconPower {...ICONE} />,
        perigo: true,
        aoEscolher: () => escolher({ acao: 'sair' })
      }
    ]
  } else {
    const atual = s?.microfone ?? null
    const marca = (sim: boolean): React.ReactNode =>
      sim ? <IconCheck size={14} stroke={1.75} className="marca" /> : null
    linhas = [
      {
        id: 'voltar',
        rotulo: 'Microfone',
        icone: <IconChevronLeft {...ICONE} />,
        aoEscolher: () => setLista('principal')
      },
      { id: '-', rotulo: '' },
      {
        id: 'padrao',
        rotulo: 'Padrão do sistema',
        fim: marca(atual === null),
        aoEscolher: () => escolher({ acao: 'microfone', nome: null })
      }
    ]
    if (mics === 'carregando') linhas.push({ id: 'aguarde', rotulo: 'Procurando…', inativa: true })
    else if (mics === 'erro')
      linhas.push({ id: 'falhou', rotulo: 'Não consegui listar', inativa: true })
    else
      for (const m of mics) {
        linhas.push({
          id: `mic-${m.indice}`,
          rotulo: m.nome,
          fim: marca(atual === m.nome || atual === m.indice),
          aoEscolher: () => escolher({ acao: 'microfone', nome: m.nome })
        })
      }
  }

  return (
    <div className="menu" ref={raiz}>
      <ListaComDestaque key={lista} linhas={linhas} />
    </div>
  )
}

function ListaComDestaque({ linhas }: { linhas: Linha[] }): React.JSX.Element {
  const [destaque, setDestaque] = useState<{ y: number; h: number } | null>(null)

  return (
    <div className="lista" onMouseLeave={() => setDestaque(null)}>
      <div
        className="destaque"
        style={{
          opacity: destaque ? 1 : 0,
          height: destaque?.h ?? 0,
          transform: `translateY(${destaque?.y ?? 0}px)`
        }}
      />
      {linhas.map((l, i) =>
        l.id === '-' ? (
          <div key={`sep-${i}`} className="separador" />
        ) : (
          <button
            key={l.id}
            className={`item ${l.perigo ? 'perigo' : ''} ${l.inativa ? 'inativa' : ''}`}
            disabled={l.inativa}
            onMouseEnter={(e) => {
              if (l.inativa) return
              const el = e.currentTarget
              setDestaque({ y: el.offsetTop, h: el.offsetHeight })
            }}
            onClick={l.aoEscolher}
          >
            <span className="icone">{l.icone}</span>
            <span className="texto">{l.rotulo}</span>
            {l.fim && <span className="fim">{l.fim}</span>}
          </button>
        )
      )}
    </div>
  )
}
