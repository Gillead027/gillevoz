import { contextBridge, ipcRenderer } from 'electron'
import { CANAL_ENVIAR, CANAL_EVENTO, CANAL_PEDIR } from '../shared/protocolo'
import type { ComandoMotor, EventoMotor } from '../shared/protocolo'
import {
  CANAL_ABRIR_HUB,
  CANAL_ABRIR_MENU,
  CANAL_ARRASTE,
  CANAL_DICA_VISTA,
  CANAL_HUB_ABRIR_PASTA,
  CANAL_HUB_COPIAR,
  CANAL_HUB_INFO,
  CANAL_HUB_INICIAR_WINDOWS,
  CANAL_HUB_JANELA,
  CANAL_HUB_RECARREGAR_MOTOR,
  CANAL_MENU_ABERTO,
  CANAL_MENU_ACAO,
  CANAL_MENU_ALTURA,
  CANAL_MOUSE_PILULA,
  CANAL_REINICIAR_MOTOR,
  CANAL_SITUACAO
} from '../shared/janelas'
import type { InfoHub, Situacao } from '../shared/janelas'
import type { GilleVozApi } from './index.d'

function assinar<T>(canal: string, cb: (v: T) => void): () => void {
  const ouvinte = (_: unknown, v: T): void => cb(v)
  ipcRenderer.on(canal, ouvinte)
  return () => ipcRenderer.removeListener(canal, ouvinte)
}

const api: GilleVozApi = {
  enviar: (cmd: ComandoMotor) => ipcRenderer.send(CANAL_ENVIAR, cmd),
  pedir: <T = unknown>(tipo: string, dados?: object) =>
    ipcRenderer.invoke(CANAL_PEDIR, tipo, dados) as Promise<T>,
  aoEvento: (cb) => assinar<EventoMotor>(CANAL_EVENTO, cb),
  janela: {
    situacao: () => ipcRenderer.invoke(CANAL_SITUACAO) as Promise<Situacao>,
    aoSituacao: (cb) => assinar<Situacao>(CANAL_SITUACAO, cb),
    mouseNaPilula: (dentro) => ipcRenderer.send(CANAL_MOUSE_PILULA, dentro),
    aoMouseFora: (cb) => assinar<boolean>(CANAL_MOUSE_PILULA, () => cb()),
    arrastar: (fase, dx, dy) => ipcRenderer.send(CANAL_ARRASTE, fase, dx, dy),
    abrirMenu: (pilula) => ipcRenderer.send(CANAL_ABRIR_MENU, pilula),
    abrirHub: () => ipcRenderer.send(CANAL_ABRIR_HUB),
    dicaVista: () => ipcRenderer.send(CANAL_DICA_VISTA),
    reiniciarMotor: () => ipcRenderer.send(CANAL_REINICIAR_MOTOR),
    acaoMenu: (a) => ipcRenderer.send(CANAL_MENU_ACAO, a),
    alturaMenu: (altura) => ipcRenderer.send(CANAL_MENU_ALTURA, altura),
    aoAbrirMenu: (cb) => assinar<void>(CANAL_MENU_ABERTO, () => cb())
  },
  hub: {
    info: () => ipcRenderer.invoke(CANAL_HUB_INFO) as Promise<InfoHub>,
    janela: (acao) => ipcRenderer.send(CANAL_HUB_JANELA, acao),
    abrirPasta: (qual) => ipcRenderer.send(CANAL_HUB_ABRIR_PASTA, qual),
    iniciarComWindows: (ligar) =>
      ipcRenderer.invoke(CANAL_HUB_INICIAR_WINDOWS, ligar) as Promise<boolean>,
    recarregarMotor: () => ipcRenderer.send(CANAL_HUB_RECARREGAR_MOTOR),
    copiar: (texto) => ipcRenderer.send(CANAL_HUB_COPIAR, texto)
  }
}

contextBridge.exposeInMainWorld('gillevoz', api)
