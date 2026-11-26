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
        // Uma página por janela: Flow Bar, menu da barra e Hub.
        input: {
          barra: resolve('src/renderer/barra/index.html'),
          menu: resolve('src/renderer/menu/index.html'),
          hub: resolve('src/renderer/hub/index.html')
        }
      }
    }
  }
})
