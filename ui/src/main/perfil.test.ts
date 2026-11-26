import { describe, expect, it } from 'vitest'
import { pastaPerfil } from './perfil'

describe('pastaPerfil (userData do Chromium)', () => {
  const LOCAL = 'C:\\Users\\Fulano\\AppData\\Local'

  it('instalado: %LOCALAPPDATA%\\GilleVoz (a pasta que o desinstalador apaga)', () => {
    expect(pastaPerfil(true, LOCAL, 'C:\\Temp')).toBe(`${LOCAL}\\GilleVoz`)
  })

  it('desenvolvimento: %LOCALAPPDATA%\\GilleVoz-dev (não divide perfil nem trava com o instalado)', () => {
    expect(pastaPerfil(false, LOCAL, 'C:\\Temp')).toBe(`${LOCAL}\\GilleVoz-dev`)
  })

  it('sem LOCALAPPDATA usa a pasta temporária', () => {
    expect(pastaPerfil(true, undefined, 'C:\\Temp')).toBe('C:\\Temp\\GilleVoz')
    expect(pastaPerfil(false, '', 'C:\\Temp')).toBe('C:\\Temp\\GilleVoz-dev')
  })
})
