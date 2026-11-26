// Peças pequenas do Hub, com os tempos de REFERENCIAS-UI §2 "Hub". Tudo escrito do zero; as ideias
// de origem estão citadas em cada peça e em ui/AVISOS-DE-TERCEIROS.md.
import { forwardRef, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { IconCheck, IconChevronDown, IconSearch, IconTrash, IconX } from '@tabler/icons-react'
import { rotulosDoAtalho } from './atalho'
import { curva, useMarcador } from './ganchos'
import { AvisosContexto, type TipoAviso } from './avisos'

const SAIDA_SUAVE = curva(0.16, 1, 0.3, 1)

// ------------------------------------------------------------------ números que rolam

/** Conta até o valor em 700 ms cubic-bezier(.16,1,.3,1) (ideia: Count Up do MicroKit, MIT). */
export function NumeroRolando({ valor }: { valor: number }): React.JSX.Element {
  const [mostrado, setMostrado] = useState(0)
  const atual = useRef(0)
  useEffect(() => {
    const de = atual.current
    const t0 = performance.now()
    let quadro = 0
    const passo = (agora: number): void => {
      const k = Math.min(1, (agora - t0) / 700)
      atual.current = de + (valor - de) * SAIDA_SUAVE(k)
      setMostrado(Math.round(atual.current))
      if (k < 1) quadro = requestAnimationFrame(passo)
    }
    quadro = requestAnimationFrame(passo)
    return () => cancelAnimationFrame(quadro)
  }, [valor])
  return <>{mostrado.toLocaleString('pt-BR')}</>
}

// ------------------------------------------------------------------ keycaps

/** Teclas de atalho como keycaps (ideia: Raycast via Refero / Kbd do Spell, MIT).
 * `apertadas`: rótulos que estão sendo segurados agora ("afundam" 1 px). */
export function Teclas({
  atalho,
  rotulos,
  apertadas,
  pequenas
}: {
  atalho?: string
  rotulos?: string[]
  apertadas?: Set<string>
  pequenas?: boolean
}): React.JSX.Element {
  const lista = rotulos ?? (atalho ? rotulosDoAtalho(atalho) : [])
  return (
    <span className={`teclas ${pequenas ? 'pequenas' : ''}`}>
      {lista.map((r, i) => (
        <kbd key={`${r}-${i}`} className={`tecla ${apertadas?.has(r) ? 'apertada' : ''}`}>
          {r}
        </kbd>
      ))}
    </span>
  )
}

// ------------------------------------------------------------------ interruptor

/** Interruptor: a bolinha estica 4 px enquanto apertada e volta com mola 600/35; trilho ligado =
 * gradiente térmico (ideia: Squish Switch do React Bits / Halo Switch do cult-ui). */
export function Interruptor({
  ligado,
  aoMudar,
  rotulo,
  desativado
}: {
  ligado: boolean
  aoMudar: (v: boolean) => void
  rotulo: string
  desativado?: boolean
}): React.JSX.Element {
  const [apertado, setApertado] = useState(false)
  const soltar = (): void => setApertado(false)
  const CURSO = 14 // 34 de trilho − 2×3 de folga − 14 da bolinha
  return (
    <button
      type="button"
      role="switch"
      aria-checked={ligado}
      aria-label={rotulo}
      disabled={desativado}
      className={`interruptor ${ligado ? 'ligado' : ''}`}
      onPointerDown={() => setApertado(true)}
      onPointerUp={soltar}
      onPointerLeave={soltar}
      onPointerCancel={soltar}
      onClick={() => aoMudar(!ligado)}
    >
      <span className="trilho-ligado" aria-hidden />
      <motion.span
        className="bolinha"
        aria-hidden
        initial={false}
        animate={{
          x: ligado ? (apertado ? CURSO - 4 : CURSO) : 0,
          width: apertado ? 18 : 14
        }}
        transition={{ type: 'spring', stiffness: 600, damping: 35 }}
      />
    </button>
  )
}

// ------------------------------------------------------------------ apagar segurando

const SEGURAR_MS = 1600

/** Apagar segurando 1600 ms: o botão vai se preenchendo (clip-path linear); soltar antes volta em
 * 500 ms; no fim a lixeira vira ✓ (ideia: Hold to Delete do MicroKit, MIT). Sem janela de confirmação. */
export function BotaoSegurar({
  aoConcluir,
  aoSoltarCedo,
  rotulo = 'Segure para apagar'
}: {
  aoConcluir: () => void
  /** Clique rápido: avisar que precisa segurar. */
  aoSoltarCedo?: () => void
  rotulo?: string
}): React.JSX.Element {
  const [fase, setFase] = useState<'parado' | 'segurando' | 'feito'>('parado')
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const inicio = useRef(0)
  const concluir = useRef(aoConcluir)
  useLayoutEffect(() => {
    concluir.current = aoConcluir
  })

  useEffect(() => () => clearTimeout(timer.current), [])

  const comecar = (): void => {
    if (fase !== 'parado') return
    inicio.current = Date.now()
    setFase('segurando')
    timer.current = setTimeout(() => {
      setFase('feito')
      timer.current = setTimeout(() => concluir.current(), 420)
    }, SEGURAR_MS)
  }
  const soltar = (): void => {
    if (fase !== 'segurando') return
    clearTimeout(timer.current)
    setFase('parado')
    if (Date.now() - inicio.current < 250) aoSoltarCedo?.()
  }

  const Icone = fase === 'feito' ? IconCheck : IconTrash
  return (
    <button
      type="button"
      className={`segurar ${fase}`}
      aria-label={rotulo}
      title={rotulo}
      onPointerDown={(e) => {
        if (e.button === 0) comecar()
      }}
      onPointerUp={soltar}
      onPointerLeave={soltar}
      onPointerCancel={soltar}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) {
          e.preventDefault()
          comecar()
        }
      }}
      onKeyUp={(e) => {
        if (e.key === 'Enter' || e.key === ' ') soltar()
      }}
      onBlur={soltar}
    >
      <Icone size={15} stroke={1.5} />
      <span className="preenchimento" aria-hidden>
        <Icone size={15} stroke={1.75} />
      </span>
    </button>
  )
}

// ------------------------------------------------------------------ busca

/** Busca: borda #781C6D e brilho sutil ao focar (ideia: Focus Input do MicroKit, MIT). */
export const Busca = forwardRef<
  HTMLInputElement,
  { valor: string; aoMudar: (v: string) => void; dica: string }
>(function Busca({ valor, aoMudar, dica }, ref) {
  return (
    <label className="busca">
      <IconSearch size={15} stroke={1.5} className="busca-icone" />
      <input
        ref={ref}
        value={valor}
        placeholder={dica}
        spellCheck={false}
        onChange={(e) => aoMudar(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape' && valor) {
            e.stopPropagation()
            aoMudar('')
          }
        }}
      />
      {valor ? (
        <button
          type="button"
          className="busca-limpar"
          aria-label="Limpar"
          onClick={() => aoMudar('')}
        >
          <IconX size={13} stroke={1.75} />
        </button>
      ) : (
        <kbd className="tecla mini">Ctrl F</kbd>
      )}
    </label>
  )
})

// ------------------------------------------------------------------ abas

/** Abas com a pílula que desliza (ideia: Glide Pill Tabs do MicroKit, MIT). */
export function Segmentado<V extends string>({
  opcoes,
  valor,
  aoMudar,
  rotulo
}: {
  opcoes: Array<{ valor: V; rotulo: string; extra?: React.ReactNode }>
  valor: V
  aoMudar: (v: V) => void
  rotulo: string
}): React.JSX.Element {
  const { registrar, marcador } = useMarcador<HTMLButtonElement>(valor, 'x')
  return (
    <div className="segmentado" role="tablist" aria-label={rotulo}>
      <span
        className="segmentado-marcador"
        aria-hidden
        style={{
          opacity: marcador ? 1 : 0,
          width: marcador?.tam ?? 0,
          transform: `translateX(${marcador?.pos ?? 0}px)`
        }}
      />
      {opcoes.map((o) => (
        <button
          key={o.valor}
          ref={registrar(o.valor)}
          type="button"
          role="tab"
          aria-selected={o.valor === valor}
          className={`segmento ${o.valor === valor ? 'ativo' : ''}`}
          onClick={() => aoMudar(o.valor)}
        >
          {o.rotulo}
          {o.extra !== undefined && <span className="segmento-extra">{o.extra}</span>}
        </button>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ seleção

export interface Opcao {
  valor: string
  rotulo: string
  detalhe?: string
}

/** Lista de escolha própria (o select nativo não segue o tema): destaque que desliza 300 ms
 * cubic-bezier(.32,.72,0,1), aparece com fade 180 ms (ideia: Glide Select do React Bits). */
export function Selecao({
  valor,
  opcoes,
  aoMudar,
  rotulo,
  largura = 240
}: {
  valor: string
  opcoes: Opcao[]
  aoMudar: (v: string) => void
  rotulo: string
  largura?: number
}): React.JSX.Element {
  const [aberta, setAberta] = useState(false)
  const [foco, setFoco] = useState<string | null>(null)
  const raiz = useRef<HTMLDivElement>(null)
  const { registrar, marcador } = useMarcador<HTMLButtonElement>(aberta ? foco : null, 'y')
  const atual = opcoes.find((o) => o.valor === valor)

  useEffect(() => {
    if (!aberta) return
    const fora = (e: PointerEvent): void => {
      if (!raiz.current?.contains(e.target as Node)) setAberta(false)
    }
    window.addEventListener('pointerdown', fora)
    return () => window.removeEventListener('pointerdown', fora)
  }, [aberta])

  const abrir = (): void => {
    setFoco(valor)
    setAberta(true)
  }
  const escolher = (v: string): void => {
    setAberta(false)
    if (v !== valor) aoMudar(v)
  }
  const mover = (passo: number): void => {
    const i = opcoes.findIndex((o) => o.valor === foco)
    const j = Math.min(opcoes.length - 1, Math.max(0, i + passo))
    setFoco(opcoes[j]?.valor ?? null)
  }

  return (
    <div className="selecao" ref={raiz} style={{ width: largura }}>
      <button
        type="button"
        className={`selecao-botao ${aberta ? 'aberta' : ''}`}
        aria-haspopup="listbox"
        aria-expanded={aberta}
        aria-label={rotulo}
        onClick={() => (aberta ? setAberta(false) : abrir())}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault()
            if (!aberta) abrir()
            else mover(e.key === 'ArrowDown' ? 1 : -1)
          } else if (e.key === 'Enter' && aberta && foco !== null) {
            e.preventDefault()
            escolher(foco)
          } else if (e.key === 'Escape' && aberta) {
            e.stopPropagation()
            setAberta(false)
          }
        }}
      >
        <span className="selecao-texto">{atual?.rotulo ?? '—'}</span>
        <IconChevronDown size={14} stroke={1.5} className="selecao-seta" />
      </button>
      <AnimatePresence>
        {aberta && (
          <motion.div
            className="selecao-lista"
            role="listbox"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18, ease: [0.32, 0.72, 0, 1] }}
            onMouseLeave={() => setFoco(null)}
          >
            <span
              className="selecao-destaque"
              aria-hidden
              style={{
                opacity: marcador ? 1 : 0,
                height: marcador?.tam ?? 0,
                transform: `translateY(${marcador?.pos ?? 0}px)`
              }}
            />
            {opcoes.map((o) => (
              <button
                key={o.valor}
                ref={registrar(o.valor)}
                type="button"
                role="option"
                aria-selected={o.valor === valor}
                className="selecao-item"
                onMouseEnter={() => setFoco(o.valor)}
                onClick={() => escolher(o.valor)}
              >
                <span className="selecao-item-texto">
                  {o.rotulo}
                  {o.detalhe && <span className="selecao-detalhe">{o.detalhe}</span>}
                </span>
                {o.valor === valor && <IconCheck size={14} stroke={1.75} className="marca" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ------------------------------------------------------------------ avisos (toasts)

interface Aviso {
  id: number
  texto: string
  tipo: TipoAviso
}

/** Avisos empilhados no canto inferior direito: entram subindo 8 px + fade 200 ms, somem sozinhos
 * em 3 s ou arrastando para o lado (ideia: Swipe Toast do React Bits / Halo Toast do cult-ui). */
export function Avisos({ children }: { children: React.ReactNode }): React.JSX.Element {
  const [avisos, setAvisos] = useState<Aviso[]>([])
  const proximo = useRef(1)
  const tirar = useCallback((id: number) => setAvisos((a) => a.filter((x) => x.id !== id)), [])
  const avisar = useCallback(
    (texto: string, tipo: TipoAviso = 'ok') => {
      const id = proximo.current++
      // O mesmo texto duas vezes seguidas não empilha.
      setAvisos((a) => [...a.filter((x) => x.texto !== texto), { id, texto, tipo }].slice(-4))
      setTimeout(() => tirar(id), 3000)
    },
    [tirar]
  )
  return (
    <AvisosContexto.Provider value={avisar}>
      {children}
      <div className="avisos" aria-live="polite">
        <AnimatePresence initial={false}>
          {avisos.map((a) => (
            <motion.div
              key={a.id}
              layout
              className={`aviso ${a.tipo}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0, x: 0 }}
              exit={{ opacity: 0, transition: { duration: 0.16 } }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              drag="x"
              dragSnapToOrigin
              dragElastic={0.6}
              onDragEnd={(_, info) => {
                if (Math.abs(info.offset.x) > 60) tirar(a.id)
              }}
            >
              <span className="aviso-ponto" aria-hidden />
              {a.texto}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </AvisosContexto.Provider>
  )
}
