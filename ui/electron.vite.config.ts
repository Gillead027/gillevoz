import { resolve } from 'path'
import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    plugins: [react()],
    build: {
      rollupOptions: {
        // Uma página por janela: Flow Bar e menu da barra (o Hub entra na Tarefa 9).
        input: {
          barra: resolve('src/renderer/barra/index.html'),
          menu: resolve('src/renderer/menu/index.html')
        }
      }
    }
  }
})
