// Hub (DESENHO-V2 §8): barra de título própria, menu lateral com marcador que desliza e as páginas
// Início, Dicionário, Atalhos de texto e Configurações.
import { useCallback, useEffect, useRef, useState } from 'react'
import { IconBook2, IconHome, IconSettings, IconTextPlus } from '@tabler/icons-react'
import type { InfoHub, Situacao } from '../../shared/janelas'
import BarraTitulo from './BarraTitulo'
import Inicio from './Inicio'
import Dicionario from './Dicionario'
import AtalhosTexto from './AtalhosTexto'
import Configuracoes from './Configuracoes'
import { Avisos, Teclas } from './pecas'
import { useAvisar } from './avisos'
import { useMarcador } from './ganchos'
import { useConfig } from './useConfig'
import { mesmoAtalho } from './atalho'

export type Pagina = 'inicio' | 'dicionario' | 'atalhos' | 'configuracoes'

const PAGINAS: Array<{ id: Pagina; rotulo: string; Icone: typeof IconHome }> = [
  { id: 'inicio', rotulo: 'Início', Icone: IconHome },
  { id: 'dicionario', rotulo: 'Dicionário', Icone: IconBook2 },
  { id: 'atalhos', rotulo: 'Atalhos de texto', Icone: IconTextPlus },
  { id: 'configuracoes', rotulo: 'Configurações', Icone: IconSettings }
]

/** Salva um atalho e devolve a mensagem de erro do motor (ou null se ficou valendo). */
export type SalvarAtalho = (chave: string, valor: string | null) => Promise<string | null>

/** Pausa o GilleVoz enquanto um atalho novo é gravado (senão apertar o atalho atual começaria a
 * ditar); devolve a função que retoma. */
export type SuspenderAtalhos = () => () => void

export default function Hub(): React.JSX.Element {
  return (
    <Avisos>
      <Conteudo />
    </Avisos>
  )
}

function Conteudo(): React.JSX.Element {
  const api = window.gillevoz
  const avisar = useAvisar()
  const [pagina, setPagina] = useState<Pagina>('inicio')
  const [situacao, setSituacao] = useState<Situacao | null>(null)
  const [info, setInfo] = useState<InfoHub | null>(null)
  const pronto = situacao?.pronto ?? false
  const { cfg, salvar } = useConfig(pronto, (msg) => avisar(msg, 'erro'))

  useEffect(() => {
    api.janela.situacao().then(setSituacao)
    api.hub.info().then(setInfo)
    return api.janela.aoSituacao(setSituacao)
  }, [api])

  // Erros do motor: viram aviso, menos os de atalho (esses aparecem embaixo do campo).
  const errosRecentes = useRef<Array<{ msg: string; t: number }>>([])
  const salvandoAtalho = useRef(0)
  useEffect(
    () =>
      api.aoEvento((e) => {
        if (e.tipo === 'pronto') {
          setInfo((i) =>
            i ? { ...i, motor: { dispositivo: e.dispositivo, modelo: e.modelo } } : i
          )
        } else if (e.tipo === 'log' && e.nivel === 'erro') {
          errosRecentes.current = [
            ...errosRecentes.current.slice(-9),
            { msg: e.msg, t: Date.now() }
          ]
          if (salvandoAtalho.current === 0) avisar(e.msg, 'erro')
        }
      }),
    [api, avisar]
  )

  const salvarAtalho: SalvarAtalho = useCallback(
    async (chave, valor) => {
      const t0 = Date.now()
      salvandoAtalho.current++
      try {
        const r = await salvar({ [chave]: valor })
        if (!r) return 'Não consegui salvar: o motor não respondeu.'
        const ficou = r.recebido[chave]
        const valeu =
          valor === null
            ? ficou === null || ficou === undefined
            : typeof ficou === 'string' && mesmoAtalho(ficou, valor)
        if (valeu) return null
        await new Promise((fim) => setTimeout(fim, 150)) // o `log` com o motivo pode vir depois
        const erro = errosRecentes.current.filter((x) => x.t >= t0).pop()
        return erro?.msg ?? 'O motor recusou esse atalho.'
      } finally {
        setTimeout(() => salvandoAtalho.current--, 300)
      }
    },
    [salvar]
  )

  const situacaoRef = useRef(situacao)
  useEffect(() => {
    situacaoRef.current = situacao
  })
  const suspenderAtalhos: SuspenderAtalhos = useCallback(() => {
    const jaPausado = situacaoRef.current?.estado === 'pausado'
    if (!jaPausado) api.enviar({ tipo: 'pausar' })
    let retomou = false
    return () => {
      if (retomou || jaPausado) return
      retomou = true
      api.enviar({ tipo: 'retomar' })
    }
  }, [api])

  // Ctrl+1..4 troca de página.
  useEffect(() => {
    const tecla = (e: KeyboardEvent): void => {
      if (!e.ctrlKey || e.altKey || e.shiftKey) return
      const i = Number(e.key) - 1
      if (i >= 0 && i < PAGINAS.length) {
        e.preventDefault()
        setPagina(PAGINAS[i].id)
      }
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [])

  const atalho = typeof cfg?.['atalho'] === 'string' ? (cfg['atalho'] as string) : null

  return (
    <div className="hub">
      <BarraTitulo />
      <div className="hub-corpo">
        <MenuLateral
          pagina={pagina}
          irPara={setPagina}
          situacao={situacao}
          info={info}
          atalho={atalho}
        />
        <main className="hub-pagina" key={pagina}>
          {pagina === 'inicio' && <Inicio pronto={pronto} atalho={atalho} />}
          {pagina === 'dicionario' && <Dicionario cfg={cfg} salvar={salvar} />}
          {pagina === 'atalhos' && <AtalhosTexto cfg={cfg} salvar={salvar} />}
          {pagina === 'configuracoes' && (
            <Configuracoes
              cfg={cfg}
              salvar={salvar}
              salvarAtalho={salvarAtalho}
              suspenderAtalhos={suspenderAtalhos}
              situacao={situacao}
              info={info}
              aoMudarInfo={setInfo}
            />
          )}
        </main>
      </div>
    </div>
  )
}

function MenuLateral({
  pagina,
  irPara,
  situacao,
  info,
  atalho
}: {
  pagina: Pagina
  irPara: (p: Pagina) => void
  situacao: Situacao | null
  info: InfoHub | null
  atalho: string | null
}): React.JSX.Element {
  const ativo = useMarcador<HTMLButtonElement>(pagina, 'y')
  const [sobre, setSobre] = useState<Pagina | null>(null)
  const realce = useMarcador<HTMLButtonElement>(sobre, 'y')

  return (
    <nav className="lateral" aria-label="Páginas">
      <div className="lateral-lista" onMouseLeave={() => setSobre(null)}>
        <span
          className="lateral-realce"
          aria-hidden
          style={{
            opacity: realce.marcador && sobre !== pagina ? 1 : 0,
            height: realce.marcador?.tam ?? 0,
            transform: `translateY(${realce.marcador?.pos ?? 0}px)`
          }}
        />
        <span
          className="lateral-marcador"
          aria-hidden
          style={{
            opacity: ativo.marcador ? 1 : 0,
            height: ativo.marcador?.tam ?? 0,
            transform: `translateY(${ativo.marcador?.pos ?? 0}px)`
          }}
        />
        {PAGINAS.map(({ id, rotulo, Icone }, i) => (
          <button
            key={id}
            type="button"
            ref={(el) => {
              ativo.registrar(id)(el)
              realce.registrar(id)(el)
            }}
            className={`lateral-item ${pagina === id ? 'ativo' : ''}`}
            aria-current={pagina === id ? 'page' : undefined}
            title={`${rotulo} (Ctrl+${i + 1})`}
            onMouseEnter={() => setSobre(id)}
            onClick={() => irPara(id)}
          >
            <Icone size={16} stroke={1.5} />
            <span>{rotulo}</span>
          </button>
        ))}
      </div>
      <StatusMotor situacao={situacao} info={info} atalho={atalho} />
    </nav>
  )
}

const NOME_DISPOSITIVO: Record<string, string> = { cuda: 'GPU', cpu: 'CPU' }

function StatusMotor({
  situacao,
  info,
  atalho
}: {
  situacao: Situacao | null
  info: InfoHub | null
  atalho: string | null
}): React.JSX.Element {
  let tom = 'carregando'
  let texto = 'Carregando o motor…'
  if (situacao?.desistiu) {
    tom = 'erro'
    texto = 'Motor parou'
  } else if (situacao?.pronto) {
    const e = situacao.estado
    tom = e
    texto =
      e === 'gravando'
        ? 'Gravando'
        : e === 'transcrevendo'
          ? 'Transcrevendo'
          : e === 'pausado'
            ? 'Pausado'
            : e === 'erro'
              ? 'Erro no ditado'
              : 'Pronto para ditar'
  }
  const m = info?.motor
  const detalhe =
    situacao?.pronto && m
      ? [NOME_DISPOSITIVO[m.dispositivo ?? ''] ?? m.dispositivo, m.modelo]
          .filter(Boolean)
          .join(' · ')
      : null
  return (
    <div className="status-motor">
      <div className="status-linha">
        <span className={`status-ponto ${tom}`} aria-hidden />
        <span className="status-texto">{texto}</span>
      </div>
      {detalhe && <div className="status-detalhe">{detalhe}</div>}
      {atalho && (
        <div className="status-atalho">
          <span>Ditar</span>
          <Teclas atalho={atalho} pequenas />
        </div>
      )}
    </div>
  )
}
