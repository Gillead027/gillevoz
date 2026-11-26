import { join } from 'node:path'

/**
 * Pasta dos arquivos internos do Chromium (userData): cache, armazenamento e a trava de instância única.
 * Instalado: %LOCALAPPDATA%\GilleVoz (o desinstalador apaga). O padrão do Electron seria
 * %APPDATA%\GilleVoz, a pasta de dados do motor: criá-la antes do motor impediria a migração do v1
 * (DESENHO-V2 §11) e misturaria cache com os dados.
 * Desenvolvimento: %LOCALAPPDATA%\GilleVoz-dev, para o `npm run dev` não dividir perfil e trava com o
 * app instalado (um fecharia o outro) nem perder o perfil quando o instalado for desinstalado.
 */
export function pastaPerfil(
  empacotado: boolean,
  localAppData: string | undefined,
  temp: string
): string {
  return join(localAppData || temp, empacotado ? 'GilleVoz' : 'GilleVoz-dev')
}
