import { describe, expect, it } from 'vitest'
import {
  botaoParaAtalho,
  rotulosDoAtalho,
  teclaParaAtalho,
  type BotaoApertado,
  type TeclaApertada
} from './atalho'

const tecla = (code: string, key: string, mods: Partial<TeclaApertada> = {}): TeclaApertada => ({
  code,
  key,
  ctrlKey: false,
  altKey: false,
  shiftKey: false,
  metaKey: false,
  ...mods
})

describe('teclaParaAtalho', () => {
  it('Ctrl+Shift+Espaço vira "ctrl+shift+space"', () => {
    expect(teclaParaAtalho(tecla('Space', ' ', { ctrlKey: true, shiftKey: true }))).toBe(
      'ctrl+shift+space'
    )
  })

  it('só Ctrl apertado (ainda sem tecla comum) devolve null', () => {
    expect(teclaParaAtalho(tecla('ControlLeft', 'Control', { ctrlKey: true }))).toBeNull()
    expect(
      teclaParaAtalho(tecla('ShiftRight', 'Shift', { ctrlKey: true, shiftKey: true }))
    ).toBeNull()
  })

  it('F9 sozinho vira "f9"', () => {
    expect(teclaParaAtalho(tecla('F9', 'F9'))).toBe('f9')
  })

  it('Alt+G vira "alt+g" (usa a tecla física, não o caractere)', () => {
    expect(teclaParaAtalho(tecla('KeyG', '©', { altKey: true }))).toBe('alt+g')
  })

  it('ordem fixa dos modificadores: ctrl, alt, shift, win', () => {
    expect(
      teclaParaAtalho(
        tecla('Digit1', '!', { shiftKey: true, metaKey: true, altKey: true, ctrlKey: true })
      )
    ).toBe('ctrl+alt+shift+win+1')
  })

  it('teclas com nome seguem o parse_atalho do motor', () => {
    expect(teclaParaAtalho(tecla('ArrowUp', 'ArrowUp', { ctrlKey: true }))).toBe('ctrl+up')
    expect(teclaParaAtalho(tecla('PageDown', 'PageDown', { altKey: true }))).toBe('alt+pagedown')
    expect(teclaParaAtalho(tecla('Enter', 'Enter', { ctrlKey: true }))).toBe('ctrl+enter')
  })

  it('sem código físico (tecla sintética), usa o nome da tecla', () => {
    expect(teclaParaAtalho(tecla('', 'g', { ctrlKey: true, altKey: true }))).toBe('ctrl+alt+g')
    expect(teclaParaAtalho(tecla('', 'F9'))).toBe('f9')
    expect(teclaParaAtalho(tecla('', ' ', { ctrlKey: true }))).toBe('ctrl+space')
    expect(teclaParaAtalho(tecla('', 'Control', { ctrlKey: true }))).toBeNull()
  })

  it('tecla que o motor não entende devolve null', () => {
    expect(teclaParaAtalho(tecla('Numpad5', '5', { ctrlKey: true }))).toBeNull()
    expect(teclaParaAtalho(tecla('IntlRo', '/', { ctrlKey: true }))).toBeNull()
  })
})

describe('botaoParaAtalho', () => {
  const botao = (button: number, mods: Partial<BotaoApertado> = {}): BotaoApertado => ({
    button,
    ctrlKey: false,
    altKey: false,
    shiftKey: false,
    metaKey: false,
    ...mods
  })

  it('botões laterais viram mouse4/mouse5', () => {
    expect(botaoParaAtalho(botao(3))).toBe('mouse4')
    expect(botaoParaAtalho(botao(4))).toBe('mouse5')
  })

  it('modificadores na mesma ordem do teclado', () => {
    expect(botaoParaAtalho(botao(3, { shiftKey: true, ctrlKey: true }))).toBe('ctrl+shift+mouse4')
  })

  it('esquerdo, meio e direito não servem', () => {
    expect(botaoParaAtalho(botao(0))).toBeNull()
    expect(botaoParaAtalho(botao(1))).toBeNull()
    expect(botaoParaAtalho(botao(2))).toBeNull()
  })
})

describe('rotulosDoAtalho com mouse', () => {
  it('mostra "Mouse 4"/"Mouse 5"', () => {
    expect(rotulosDoAtalho('ctrl+mouse4')).toEqual(['Ctrl', 'Mouse 4'])
    expect(rotulosDoAtalho('mouse5')).toEqual(['Mouse 5'])
  })
})
