import '../fontes'
import '../tema.css'
import './barra.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MotionConfig } from 'motion/react'
import Barra from './Barra'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <Barra />
    </MotionConfig>
  </StrictMode>
)
