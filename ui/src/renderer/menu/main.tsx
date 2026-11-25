import '../fontes'
import '../tema.css'
import './menu.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import Menu from './Menu'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Menu />
  </StrictMode>
)
