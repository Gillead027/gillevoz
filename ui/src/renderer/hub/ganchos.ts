// Ganchos e curvas do Hub (sem componentes, para o recarregamento rápido do Vite).
import { useCallback, useLayoutEffect, useRef, useState } from 'react'

// ------------------------------------------------------------------ curvas

/** cubic-bezier(x1,y1,x2,y2) como função de 0..1 → 0..1 (para animar números fora do CSS). */
export function curva(x1: number, y1: number, x2: number, y2: number): (t: number) => number {
  const bx = (t: number): number => 3 * x1 * t * (1 - t) ** 2 + 3 * x2 * t ** 2 * (1 - t) + t ** 3
  const by = (t: number): number => 3 * y1 * t * (1 - t) ** 2 + 3 * y2 * t ** 2 * (1 - t) + t ** 3
  return (x) => {
    if (x <= 0) return 0
    if (x >= 1) return 1
    let lo = 0
    let hi = 1
    for (let i = 0; i < 24; i++) {
      const meio = (lo + hi) / 2
      if (bx(meio) < x) lo = meio
      else hi = meio
    }
    return by((lo + hi) / 2)
  }
}

// ------------------------------------------------------------------ marcador que desliza

/** Mede o elemento ativo de uma lista para um marcador que desliza até ele. */
export function useMarcador<T extends HTMLElement>(
  ativo: string | null,
  eixo: 'x' | 'y'
): {
  registrar: (id: string) => (el: T | null) => void
  marcador: { pos: number; tam: number } | null
} {
  const els = useRef(new Map<string, T>())
  const [marcador, setMarcador] = useState<{ pos: number; tam: number } | null>(null)
  const medir = useCallback(() => {
    const el = ativo ? els.current.get(ativo) : undefined
    if (!el) return setMarcador(null)
    setMarcador(
      eixo === 'y'
        ? { pos: el.offsetTop, tam: el.offsetHeight }
        : { pos: el.offsetLeft, tam: el.offsetWidth }
    )
  }, [ativo, eixo])
  useLayoutEffect(() => {
    medir()
    // As fontes locais carregam depois do primeiro desenho e mudam as larguras.
    void document.fonts?.ready.then(medir)
    window.addEventListener('resize', medir)
    return () => window.removeEventListener('resize', medir)
  }, [medir])
  const registrar = useCallback(
    (id: string) => (el: T | null) => {
      if (el) els.current.set(id, el)
      else els.current.delete(id)
    },
    []
  )
  return { registrar, marcador }
}
