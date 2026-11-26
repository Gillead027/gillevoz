// Contexto dos avisos (toasts) do Hub; o componente que desenha fica em pecas.tsx.
import { createContext, useContext } from 'react'

export type TipoAviso = 'ok' | 'erro' | 'info'
export const AvisosContexto = createContext<(texto: string, tipo?: TipoAviso) => void>(() => {})

/** Avisa algo no canto inferior direito do Hub. */
export const useAvisar = (): ((texto: string, tipo?: TipoAviso) => void) =>
  useContext(AvisosContexto)
