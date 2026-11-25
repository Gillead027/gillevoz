// Peças pequenas da Flow Bar: microfone com ondas, cronômetro com números rolando e o anel
// "processando → ✓". Tempos de REFERENCIAS-UI §2.
import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'

/** Microfone (traço do Tabler, MIT) com duas ondas de cada lado que aparecem em sequência
 * (60 ms entre elas) quando `ativo` — ideia dos ícones animados do 21st.dev, código próprio. */
export function MicAnimado({
  ativo,
  tamanho = 16
}: {
  ativo: boolean
  tamanho?: number
}): React.JSX.Element {
  const onda = (atraso: number): object => ({
    initial: false,
    animate: { opacity: ativo ? 1 : 0, pathLength: ativo ? 1 : 0 },
    transition: { duration: 0.16, delay: ativo ? atraso : 0, ease: 'easeOut' }
  })
  return (
    <svg
      width={tamanho * (30 / 24)}
      height={tamanho}
      viewBox="-3 0 30 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M9 5a3 3 0 0 1 6 0v5a3 3 0 0 1 -6 0z" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <path d="M8 21h8" />
      <path d="M12 17v4" />
      <motion.path d="M5.2 3.2q-1.6 2.6 0 5.2" {...onda(0)} />
      <motion.path d="M18.8 3.2q1.6 2.6 0 5.2" {...onda(0)} />
      <motion.path d="M2.4 1.6q-2.8 4.2 0 8.4" {...onda(0.06)} />
      <motion.path d="M21.6 1.6q2.8 4.2 0 8.4" {...onda(0.06)} />
    </svg>
  )
}

function Digito({ d }: { d: string }): React.JSX.Element {
  return (
    <span className="digito">
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={d}
          initial={{ y: '-100%', opacity: 0 }}
          animate={{ y: '0%', opacity: 1 }}
          exit={{ y: '100%', opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        >
          {d}
        </motion.span>
      </AnimatePresence>
    </span>
  )
}

/** Cronômetro m:ss em Red Hat Mono; cada dígito rola ao mudar. */
export function Cronometro(): React.JSX.Element {
  // Monta junto com o conteúdo de "gravando": o início da gravação é o momento da montagem.
  const [desde] = useState(() => Date.now())
  const [agora, setAgora] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), 250)
    return () => clearInterval(t)
  }, [])
  const s = Math.max(0, Math.floor((agora - desde) / 1000))
  const texto = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  return (
    <span className="cronometro" aria-label={`gravando há ${texto}`}>
      {texto
        .split('')
        .map((c, i) => (c === ':' ? <span key={i}>:</span> : <Digito key={i} d={c} />))}
    </span>
  )
}

const CURVA_CHECK = [0.23, 1, 0.32, 1] as const

/** Arco girando (linear 1100 ms); quando `pronto`, vira um ✓ desenhado em 240 ms após 120 ms.
 * Adaptado da ideia do Progress Ring Check do MicroKit (MIT) — ver AVISOS-DE-TERCEIROS.md. */
export function AnelProcessando({ pronto }: { pronto: boolean }): React.JSX.Element {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx={8} cy={8} r={6.5} stroke="#241e30" strokeWidth={1.5} />
      {pronto ? (
        <>
          <motion.circle
            cx={8}
            cy={8}
            r={6.5}
            stroke="#fbb61a"
            strokeWidth={1.5}
            initial={{ pathLength: 0.28 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.12, ease: 'linear' }}
          />
          <motion.path
            d="M5.2 8.2l1.9 1.9l3.7 -3.8"
            stroke="#fcffa4"
            strokeWidth={1.6}
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.24, delay: 0.12, ease: CURVA_CHECK }}
          />
        </>
      ) : (
        <motion.circle
          cx={8}
          cy={8}
          r={6.5}
          stroke="#ed6925"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeDasharray="11.4 40.8"
          style={{ originX: '50%', originY: '50%' }}
          animate={{ rotate: 360 }}
          transition={{ duration: 1.1, ease: 'linear', repeat: Infinity }}
        />
      )}
    </svg>
  )
}
