// Início (DESENHO-V2 §8): saudação + atalho atual, cartões de estatística (números que rolam) e o
// histórico agrupado por dia. Recarrega quando o motor avisa `historico`.
import { useEffect, useRef, useState } from 'react'
import {
  IconCheck,
  IconCopy,
  IconFlame,
  IconGauge,
  IconMessage2,
  IconSum,
  IconSunHigh
} from '@tabler/icons-react'
import { NumeroRolando, Teclas } from './pecas'
import { useAvisar } from './avisos'

interface Estatisticas {
  palavras_hoje: number
  palavras_total: number
  ditados_total: number
  ppm: number
  sequencia_dias: number
}

interface Item {
  hora: string
  texto: string
  duracao_audio?: number
  tempo_transcricao?: number
  palavras?: number
}

interface Dia {
  dia: string
  itens: Item[]
}

interface RespostaHistorico {
  dia: string
  itens: Item[]
  dias: string[]
}

const DIAS_POR_VEZ = 4

function hojeLocal(deslocamento = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + deslocamento)
  const p = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

function nomeDoDia(dia: string): string {
  if (dia === hojeLocal()) return 'Hoje'
  if (dia === hojeLocal(-1)) return 'Ontem'
  const texto = new Date(`${dia}T12:00:00`).toLocaleDateString('pt-BR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long'
  })
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

const numero = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0)

interface Dados {
  stats: Estatisticas
  /** Dias carregados que têm ditado. */
  dias: Dia[]
  /** Todos os dias com histórico. */
  todos: string[]
}

/** Estatísticas + hoje + os `quantos - 1` dias anteriores com histórico. */
async function buscar(quantos: number): Promise<Dados> {
  const api = window.gillevoz
  const [s, hoje] = await Promise.all([
    api.pedir<Estatisticas>('estatisticas'),
    api.pedir<RespostaHistorico>('listar_historico')
  ])
  const todos = Array.isArray(hoje.dias) ? hoje.dias : []
  const anteriores = todos.filter((d) => d !== hoje.dia).slice(0, quantos - 1)
  const resto = await Promise.all(
    anteriores.map((dia) => api.pedir<RespostaHistorico>('listar_historico', { dia }))
  )
  const dias = [hoje, ...resto]
    .map((r) => ({ dia: r.dia, itens: Array.isArray(r.itens) ? r.itens : [] }))
    .filter((d) => d.itens.length > 0)
  return {
    stats: {
      palavras_hoje: numero(s.palavras_hoje),
      palavras_total: numero(s.palavras_total),
      ditados_total: numero(s.ditados_total),
      ppm: numero(s.ppm),
      sequencia_dias: numero(s.sequencia_dias)
    },
    dias,
    todos
  }
}

export default function Inicio({
  pronto,
  atalho
}: {
  pronto: boolean
  atalho: string | null
}): React.JSX.Element {
  const api = window.gillevoz
  const [dados, setDados] = useState<Dados | null>(null)
  /** Quantos dias com histórico mostrar (hoje conta como um). */
  const [quantos, setQuantos] = useState(DIAS_POR_VEZ)
  const [recargas, setRecargas] = useState(0)

  useEffect(() => {
    if (!pronto) return
    let vivo = true
    buscar(quantos)
      .then((d) => vivo && setDados(d))
      .catch(() => {}) // motor reiniciando: tenta de novo quando ficar pronto
    return () => {
      vivo = false
    }
  }, [pronto, quantos, recargas])

  // O motor avisa quando um ditado entra no histórico.
  useEffect(
    () =>
      api.aoEvento((e) => {
        if (e.tipo === 'historico') setRecargas((n) => n + 1)
      }),
    [api]
  )

  const stats = dados?.stats
  const dias = dados?.dias ?? []
  const anteriores = (dados?.todos ?? []).filter((d) => d !== hojeLocal()).length
  const temMais = !!dados && quantos - 1 < anteriores
  const carregou = !!dados
  const maisDias = (): void => setQuantos((n) => n + DIAS_POR_VEZ)

  return (
    <div className="pagina">
      <header className="pagina-topo">
        <div>
          <h1>E aí, Gillezin</h1>
          <p className="pagina-sub">
            {atalho ? (
              <>
                Aperte <Teclas atalho={atalho} pequenas /> para ditar em qualquer lugar.
              </>
            ) : (
              'Carregando o atalho…'
            )}
          </p>
        </div>
      </header>

      <section className="cartoes" aria-label="Estatísticas">
        <Cartao
          icone={<IconSunHigh size={14} stroke={1.5} />}
          rotulo="Palavras hoje"
          dica="Palavras ditadas hoje"
          valor={stats?.palavras_hoje}
        />
        <Cartao
          icone={<IconSum size={14} stroke={1.5} />}
          rotulo="No total"
          dica="Palavras no total"
          valor={stats?.palavras_total}
        />
        <Cartao
          icone={<IconMessage2 size={14} stroke={1.5} />}
          rotulo="Ditados"
          valor={stats?.ditados_total}
        />
        <Cartao
          icone={<IconGauge size={14} stroke={1.5} />}
          rotulo="Por minuto"
          valor={stats?.ppm}
          dica="Palavras por minuto falado"
        />
        <Cartao
          icone={<IconFlame size={14} stroke={1.5} />}
          rotulo="Sequência"
          valor={stats?.sequencia_dias}
          unidade={stats?.sequencia_dias === 1 ? 'dia' : 'dias'}
        />
      </section>

      <section className="historico" aria-label="Histórico">
        <h2 className="secao-titulo">Histórico</h2>
        {!carregou ? (
          <div className="vazio">
            {pronto ? 'Carregando…' : 'O motor está carregando o modelo…'}
          </div>
        ) : dias.length === 0 ? (
          <div className="vazio">
            <strong>Nenhum ditado ainda.</strong>
            {atalho && (
              <span>
                Aperte <Teclas atalho={atalho} pequenas /> em qualquer janela e fale.
              </span>
            )}
          </div>
        ) : (
          dias.map((d) => <GrupoDia key={d.dia} dia={d} />)
        )}
        {temMais && (
          <button type="button" className="botao fantasma mais-dias" onClick={maisDias}>
            Mostrar dias anteriores
          </button>
        )}
      </section>
    </div>
  )
}

function Cartao({
  icone,
  rotulo,
  valor,
  unidade,
  dica
}: {
  icone: React.ReactNode
  rotulo: string
  valor: number | undefined
  unidade?: string
  dica?: string
}): React.JSX.Element {
  return (
    <div className="cartao" title={dica}>
      <div className="cartao-rotulo">
        {icone}
        <span>{rotulo}</span>
      </div>
      <div className="cartao-valor">
        {valor === undefined ? <span className="apagado">—</span> : <NumeroRolando valor={valor} />}
        {unidade && valor !== undefined && <span className="cartao-unidade">{unidade}</span>}
      </div>
    </div>
  )
}

function GrupoDia({ dia }: { dia: Dia }): React.JSX.Element {
  const palavras = dia.itens.reduce((s, i) => s + numero(i.palavras), 0)
  const n = dia.itens.length
  return (
    <div className="dia">
      <div className="dia-topo">
        <span className="dia-nome">{nomeDoDia(dia.dia)}</span>
        <span className="dia-resumo">
          {n} {n === 1 ? 'ditado' : 'ditados'} · {palavras.toLocaleString('pt-BR')} palavras
        </span>
      </div>
      <ul className="lista">
        {dia.itens.map((item, i) => (
          <ItemHistorico key={`${item.hora}-${i}`} item={item} />
        ))}
      </ul>
    </div>
  )
}

function ItemHistorico({ item }: { item: Item }): React.JSX.Element {
  const avisar = useAvisar()
  const [copiado, setCopiado] = useState(false)
  const [aberto, setAberto] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])

  const copiar = (): void => {
    window.gillevoz.hub.copiar(item.texto)
    setCopiado(true)
    avisar('Copiado')
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setCopiado(false), 1400)
  }
  const segundos = numero(item.duracao_audio)
  return (
    <li className="linha item-historico">
      <span className="item-hora">{(item.hora ?? '').slice(0, 5)}</span>
      <p
        className={`item-texto ${aberto ? 'aberto' : ''}`}
        onClick={() => setAberto((a) => !a)}
        title={aberto ? undefined : 'Clique para ver tudo'}
      >
        {item.texto}
      </p>
      <span className="item-meta">
        {numero(item.palavras)} pal ·{' '}
        {segundos.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s
      </span>
      <button
        type="button"
        className={`icone-botao ${copiado ? 'feito' : ''}`}
        aria-label="Copiar"
        title="Copiar"
        onClick={copiar}
      >
        {copiado ? <IconCheck size={15} stroke={1.75} /> : <IconCopy size={15} stroke={1.5} />}
      </button>
    </li>
  )
}
