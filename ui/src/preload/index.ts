import { contextBridge, ipcRenderer } from 'electron'
import { CANAL_ENVIAR, CANAL_EVENTO, CANAL_PEDIR } from '../shared/protocolo'
import type { ComandoMotor, EventoMotor } from '../shared/protocolo'
import type { GilleVozApi } from './index.d'

const api: GilleVozApi = {
  enviar: (cmd: ComandoMotor) => ipcRenderer.send(CANAL_ENVIAR, cmd),
  pedir: <T = unknown>(tipo: string, dados?: object) =>
    ipcRenderer.invoke(CANAL_PEDIR, tipo, dados) as Promise<T>,
  aoEvento: (cb) => {
    const ouvinte = (_: unknown, e: EventoMotor): void => cb(e)
    ipcRenderer.on(CANAL_EVENTO, ouvinte)
    return () => ipcRenderer.removeListener(CANAL_EVENTO, ouvinte)
  },
  janela: {}
}

contextBridge.exposeInMainWorld('gillevoz', api)
