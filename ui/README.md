# GilleVoz — interface (Electron)

Flow Bar, menu, Hub e ícone da bandeja do GilleVoz. O motor de voz é o pacote Python `gillevoz`
na raiz do projeto; esta interface o inicia com `-m gillevoz --motor` e conversa com ele por JSON
(veja `docs/DESENHO-V2.md`).

## Comandos (dentro de `ui/`)

```bash
npm install          # primeira vez
npm run dev          # abre o app em desenvolvimento (usa o .venv da raiz)
npm test             # testes (vitest)
npm run build        # confere os tipos e compila para out/
npm run build:unpack # compila e empacota em dist/win-unpacked (GilleVoz.exe)
```

O instalador completo (`GilleVoz-Setup.exe`) é montado por `instalador\montar.ps1`, na raiz.
