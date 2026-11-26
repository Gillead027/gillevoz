import { useEffect, useRef } from 'react'

/** Ctrl+F leva o foco para a busca da página. */
export function useBuscaComAtalho(): React.RefObject<HTMLInputElement | null> {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const tecla = (e: KeyboardEvent): void => {
      if (e.ctrlKey && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'f') {
        e.preventDefault()
        ref.current?.focus()
        ref.current?.select()
      }
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [])
  return ref
}
