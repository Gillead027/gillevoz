// Flow Bar (DESENHO-V2 §7): uma única pílula que muda de tamanho entre os estados ("ilha").
// Morfose: ideia da Dynamic Island do cult-ui (MIT) — mola 600/35 no tamanho, conteúdo entra/sai
// com 300/28 e desfoque 4 px → 0, o antigo sai antes do novo entrar. Código próprio.
import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useAnimationControls } from 'motion/react'
import { IconAlertTriangle, IconPlayerStopFilled, IconSettings, IconX } from '@tabler/icons-react'
import type { Situacao } from '../../shared/janelas'
import Onda from './Onda'
import { AnelProcessando, Cronometro, MicAnimado } from './Pecas'

type Visual =
  | 'carregando'
  | 'carregandoHover'
  | 'ocioso'
  | 'hover'
  | 'gravando'
  | 'transcrevendo'
  | 'pronto'
  | 'pausado'
  | 'pausadoAviso'
  | 'erro'

const TAMANHO: Record<Visual, { w: number; h: number }> = {
  carregando: { w: 44, h: 10 },
  carregandoHover: { w: 128, h: 32 },
  ocioso: { w: 44, h: 10 },
  hover: { w: 128, h: 32 },
  gravando: { w: 220, h: 36 },
  transcrevendo: { w: 120, h: 32 },
  pronto: { w: 120, h: 32 },
  pausado: { w: 44, h: 10 },
  pausadoAviso: { w: 104, h: 28 },
  erro: { w: 220, h: 36 }
}

const MOLA_PILULA = { type: 'spring', stiffness: 600, damping: 35 } as const
const MOLA_CONTEUDO = { type: 'spring', stiffness: 300, damping: 28 } as const
// ✓: 120 ms de espera + 240 ms desenhando + 600 ms parado, depois a barra encolhe.
const DURACAO_PRONTO_MS = 960
const DURACAO_AVISO_PAUSADO_MS = 1600
const DURACAO_DICA_MS = 3500
const LIMIAR_ARRASTE_PX = 4
const INTERVALO_SINAL_MS = 250 // sinal de vida do arraste para o main (ele desiste após 3 s sem sinal)

const SITUACAO_INICIAL: Situacao = {
  pronto: false,
  estado: 'ocioso',
  desistiu: false,
  borda: 'embaixo',
  mostrarDica: false,
  microfone: null
}

function useSituacao(): Situacao {
  const [s, setS] = useState<Situacao>(SITUACAO_INICIAL)
  useEffect(() => {
    let vivo = true
    window.gillevoz.janela.situacao().then((v) => vivo && setS(v))
    const parar = window.gillevoz.janela.aoSituacao(setS)
    return () => {
      vivo = false
      parar()
    }
  }, [])
  return s
}

export default function Barra(): React.JSX.Element {
  const s = useSituacao()
  const api = window.gillevoz
  const [hover, setHover] = useState(false)
  const [mostrandoPronto, setMostrandoPronto] = useState(false)
  const [avisoPausado, setAvisoPausado] = useState(false)
  const [dica, setDica] = useState(false)
  const [estadoVisto, setEstadoVisto] = useState(s.estado)
  const dicaMostrada = useRef(false)
  const pilula = useRef<HTMLDivElement>(null)
  const tremida = useAnimationControls()

  // Transições de estado do motor (ajuste durante a renderização, sem efeito):
  // o ✓ aparece só quando a transcrição termina; o aviso de pausado some ao sair do pausado.
  if (estadoVisto !== s.estado) {
    setEstadoVisto(s.estado)
    setMostrandoPronto(estadoVisto === 'transcrevendo' && s.estado === 'ocioso')
    if (s.estado !== 'pausado') setAvisoPausado(false)
  }

  useEffect(() => {
    if (!mostrandoPronto) return
    const t = setTimeout(() => setMostrandoPronto(false), DURACAO_PRONTO_MS)
    return () => clearTimeout(t)
  }, [mostrandoPronto])

  let visual: Visual
  if (s.desistiu || s.estado === 'erro') visual = 'erro'
  else if (s.estado === 'gravando') visual = 'gravando'
  else if (s.estado === 'transcrevendo') visual = 'transcrevendo'
  else if (mostrandoPronto) visual = 'pronto'
  else if (s.estado === 'pausado') visual = avisoPausado ? 'pausadoAviso' : 'pausado'
  else if (!s.pronto) visual = hover ? 'carregandoHover' : 'carregando'
  else visual = hover ? 'hover' : 'ocioso'

  // Erro: a pílula treme 2× (±3 px, 240 ms).
  useEffect(() => {
    if (visual !== 'erro') return
    tremida.start({ x: [0, -3, 3, -3, 3, 0], transition: { duration: 0.24, ease: 'easeInOut' } })
  }, [visual, tremida])

  useEffect(() => {
    if (!avisoPausado) return
    const t = setTimeout(() => setAvisoPausado(false), DURACAO_AVISO_PAUSADO_MS)
    return () => clearTimeout(t)
  }, [avisoPausado])

  // ---- Mouse: clique atravessando fora da pílula, arraste e clique direito ----
  const arraste = useRef<{ x: number; y: number; ativo: boolean } | null>(null)
  // Sinal de vida do arraste para o main enquanto o botão está apertado (mesmo com o mouse parado).
  const sinalArraste = useRef<number | undefined>(undefined)
  const acabouDeArrastar = useRef(false)

  const mouseDentro = useRef(false)
  const entrar = useCallback(() => {
    mouseDentro.current = true
    setHover(true)
    api.janela.mouseNaPilula(true)
    // Dica "Arraste para mudar de lugar": na primeira vez que o mouse passa pela barra.
    if (s.mostrarDica && !dicaMostrada.current) {
      dicaMostrada.current = true
      setDica(true)
      setTimeout(() => {
        setDica(false)
        api.janela.dicaVista()
      }, DURACAO_DICA_MS)
    }
  }, [api, s.mostrarDica])
  const sair = useCallback(() => {
    mouseDentro.current = false
    setHover(false)
    if (!arraste.current) api.janela.mouseNaPilula(false)
  }, [api])

  const aoSoltar = useCallback((): void => {
    const a = arraste.current
    arraste.current = null
    clearInterval(sinalArraste.current)
    sinalArraste.current = undefined
    if (!a?.ativo) return
    acabouDeArrastar.current = true
    api.janela.arrastar('fim', 0, 0)
    setDica(false)
  }, [api])
  const aoApertar = (e: React.PointerEvent): void => {
    if (e.button !== 0) return
    if (arraste.current?.ativo) aoSoltar() // um arraste anterior perdeu a soltura: termina antes
    arraste.current = { x: e.screenX, y: e.screenY, ativo: false }
    acabouDeArrastar.current = false
  }
  const aoMover = useCallback(
    (e: PointerEvent): void => {
      const a = arraste.current
      if (!a) return
      if (a.ativo) {
        // Botão já solto (a soltura caiu fora da janela): termina o arraste agora.
        if (e.buttons === 0) aoSoltar()
        return
      }
      const dx = e.screenX - a.x
      const dy = e.screenY - a.y
      if (Math.hypot(dx, dy) < LIMIAR_ARRASTE_PX) return
      // Passou do limiar: vira arraste. Daqui em diante o main move a janela seguindo o cursor.
      a.ativo = true
      api.janela.arrastar('inicio', dx, dy)
      clearInterval(sinalArraste.current)
      sinalArraste.current = window.setInterval(
        () => api.janela.arrastar('segue', 0, 0),
        INTERVALO_SINAL_MS
      )
    },
    [api, aoSoltar]
  )

  useEffect(
    () =>
      api.janela.aoMouseFora(() => {
        mouseDentro.current = false
        setHover(false)
      }),
    [api]
  )

  // Movimento e soltura são ouvidos na janela toda: um movimento rápido sai da pílula antes de
  // passar do limiar. Depois do limiar a janela segue o cursor (main), então a soltura cai nela.
  useEffect(() => {
    window.addEventListener('pointermove', aoMover)
    window.addEventListener('pointerup', aoSoltar)
    return () => {
      clearInterval(sinalArraste.current)
      window.removeEventListener('pointermove', aoMover)
      window.removeEventListener('pointerup', aoSoltar)
    }
  }, [aoMover, aoSoltar])

  /** Envolve a ação de um botão: um arraste que termina em cima do botão não conta como clique. */
  const clique = (acao: () => void) => (e: React.MouseEvent) => {
    e.stopPropagation()
    if (acabouDeArrastar.current) return
    acao()
  }

  const aoClicarPilula = (): void => {
    if (acabouDeArrastar.current) return
    if (s.desistiu) api.janela.reiniciarMotor()
    else if (s.estado === 'pausado') setAvisoPausado(true)
  }

  const abrirMenu = (e: React.MouseEvent): void => {
    e.preventDefault()
    const r = pilula.current?.getBoundingClientRect()
    if (r) api.janela.abrirMenu({ x: r.x, y: r.y, width: r.width, height: r.height })
  }

  const { w, h } = TAMANHO[visual]
  const expandida = !['ocioso', 'carregando', 'pausado'].includes(visual)

  return (
    <div className={`palco borda-${s.borda}`}>
      <div
        className="zona"
        onMouseEnter={entrar}
        onMouseLeave={sair}
        // Garantia: se um "sair" falso religou o clique atravessando, o próximo movimento desliga.
        onMouseMove={() => mouseDentro.current || entrar()}
        onContextMenu={abrirMenu}
      >
        <AnimatePresence>
          {dica && (visual === 'hover' || visual === 'carregandoHover') && (
            <motion.div
              className="dica"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
            >
              Arraste para mudar de lugar
            </motion.div>
          )}
        </AnimatePresence>
        <motion.div animate={tremida}>
          <motion.div
            ref={pilula}
            className={`pilula ${expandida ? 'expandida' : 'recolhida'} v-${visual}`}
            initial={false}
            animate={{ width: w, height: h }}
            transition={MOLA_PILULA}
            onPointerDown={aoApertar}
            onPointerCancel={aoSoltar}
            onClick={aoClicarPilula}
          >
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.div
                key={conteudoDe(visual)}
                className="conteudo"
                initial={{ opacity: 0, filter: 'blur(4px)', scale: 0.96 }}
                animate={{ opacity: 1, filter: 'blur(0px)', scale: 1 }}
                exit={{ opacity: 0, filter: 'blur(4px)', scale: 0.96 }}
                transition={{
                  default: MOLA_CONTEUDO,
                  opacity: { duration: 0.15 },
                  filter: { duration: 0.2 }
                }}
              >
                {renderizarConteudo(visual, { s, clique, api })}
              </motion.div>
            </AnimatePresence>
          </motion.div>
        </motion.div>
      </div>
    </div>
  )
}

/** Visuais que mostram o mesmo conteúdo não trocam de elemento (ex.: transcrevendo → ✓). */
function conteudoDe(v: Visual): string {
  return v === 'pronto' ? 'transcrevendo' : v
}

interface Contexto {
  s: Situacao
  clique: (acao: () => void) => (e: React.MouseEvent) => void
  api: Window['gillevoz']
}

function renderizarConteudo(v: Visual, c: Contexto): React.ReactNode {
  switch (v) {
    case 'carregando':
      return <span className="respiro" />
    case 'ocioso':
      return null
    case 'pausado':
      return <span className="risco" />
    case 'carregandoHover':
      return <span className="rotulo secundario">Carregando…</span>
    case 'hover':
      return <ConteudoHover c={c} />
    case 'gravando':
      return (
        <div className="linha gravando">
          <button
            className="botao fantasma"
            aria-label="Cancelar"
            onClick={c.clique(() => c.api.enviar({ tipo: 'cancelar' }))}
          >
            <IconX size={16} stroke={1.5} />
          </button>
          <span className="meio">
            <Onda />
            <span className="tempo">
              <span className="ponto-gravando" />
              <Cronometro />
            </span>
          </span>
          <button
            className="botao primario"
            aria-label="Parar"
            onClick={c.clique(() => c.api.enviar({ tipo: 'parar' }))}
          >
            {/* Pulso do mic: anel #ED6925, escala 1→1,6, opacidade 0,5→0, 420 ms (ideia: 60fps) */}
            <motion.span
              className="anel"
              initial={{ scale: 1, opacity: 0.5 }}
              animate={{ scale: 1.6, opacity: 0 }}
              transition={{ duration: 0.42, ease: 'easeOut' }}
            />
            <IconPlayerStopFilled size={11} />
          </button>
        </div>
      )
    case 'transcrevendo':
    case 'pronto':
      return <ConteudoProcessando pronto={v === 'pronto'} />
    case 'pausadoAviso':
      return <span className="rotulo secundario">Pausado</span>
    case 'erro':
      return (
        <div className="linha erro">
          <IconAlertTriangle size={15} stroke={1.5} className="icone-erro" />
          <span className="mensagem">
            {c.s.desistiu ? 'Motor parou' : c.s.msg || 'Algo deu errado'}
          </span>
          {c.s.desistiu && <span className="acao-erro">Clique para reiniciar</span>}
        </div>
      )
  }
}

function ConteudoHover({ c }: { c: Contexto }): React.JSX.Element {
  const [sobreMic, setSobreMic] = useState(false)
  return (
    <div className="linha hover">
      <button
        className="botao mic"
        aria-label="Começar a ditar"
        onMouseEnter={() => setSobreMic(true)}
        onMouseLeave={() => setSobreMic(false)}
        onClick={c.clique(() => c.api.enviar({ tipo: 'iniciar' }))}
      >
        <MicAnimado ativo={sobreMic} />
        <span>Ditar</span>
      </button>
      <span className="divisor" />
      <button
        className="botao fantasma"
        aria-label="Abrir GilleVoz"
        onClick={c.clique(() => c.api.janela.abrirHub())}
      >
        <IconSettings size={16} stroke={1.5} />
      </button>
    </div>
  )
}

function ConteudoProcessando({ pronto }: { pronto: boolean }): React.JSX.Element {
  return (
    <div className="linha processando">
      <AnelProcessando pronto={pronto} />
      <span className={`faixa ${pronto ? 'parada' : ''}`} />
    </div>
  )
}
