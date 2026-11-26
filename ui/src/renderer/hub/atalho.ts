// Converte uma tecla apertada no formato de atalho que o motor entende (gillevoz/hotkey.py
// `parse_atalho`): minúsculas, modificadores na ordem ctrl, alt, shift, win, e a tecla comum no fim.

/** O que precisamos de um KeyboardEvent (facilita testar sem DOM). */
export type TeclaApertada = Pick<
  KeyboardEvent,
  'code' | 'key' | 'ctrlKey' | 'altKey' | 'shiftKey' | 'metaKey'
>

// Pela tecla física (`code`): Alt+G no Windows pode virar '©' em `key`, mas o código é sempre KeyG.
const NOMES: Record<string, string> = {
  Space: 'space',
  Enter: 'enter',
  Tab: 'tab',
  Escape: 'esc',
  Backspace: 'backspace',
  Insert: 'insert',
  Delete: 'delete',
  Home: 'home',
  End: 'end',
  PageUp: 'pageup',
  PageDown: 'pagedown',
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  Pause: 'pause',
  ScrollLock: 'scrolllock',
  PrintScreen: 'printscreen'
}

/** Sem `code` (tecla sintética, algumas ferramentas de acessibilidade): usa o nome da tecla. */
function pelaTecla(key: string): string | undefined {
  if (key === ' ') return 'space'
  if (/^[a-z0-9]$/i.test(key)) return key.toLowerCase()
  if (/^F([1-9]|1[0-9]|2[0-4])$/.test(key)) return key.toLowerCase()
  return NOMES[key] // Enter, Tab, Escape, ArrowUp… têm o mesmo nome em key e code
}

/** Atalho no formato do motor (`ctrl+shift+space`, `f9`, `alt+g`), ou null se ainda só há
 * modificadores apertados ou a tecla não é uma que o motor entende. */
export function teclaParaAtalho(e: TeclaApertada): string | null {
  const code = e.code ?? ''
  let principal: string | undefined = NOMES[code]
  if (!principal) {
    const m = /^(?:Key([A-Z])|Digit([0-9])|F([1-9]|1[0-9]|2[0-4]))$/.exec(code)
    if (m) principal = m[1] ? m[1].toLowerCase() : m[2] ? m[2] : `f${m[3]}`
  }
  if (!principal && !code) principal = pelaTecla(e.key ?? '')
  if (!principal) return null
  const partes: string[] = []
  if (e.ctrlKey) partes.push('ctrl')
  if (e.altKey) partes.push('alt')
  if (e.shiftKey) partes.push('shift')
  if (e.metaKey) partes.push('win')
  partes.push(principal)
  return partes.join('+')
}

const ROTULOS: Record<string, string> = {
  ctrl: 'Ctrl',
  control: 'Ctrl',
  alt: 'Alt',
  shift: 'Shift',
  win: 'Win',
  windows: 'Win',
  super: 'Win',
  space: 'Espaço',
  espaço: 'Espaço',
  espaco: 'Espaço',
  enter: 'Enter',
  tab: 'Tab',
  esc: 'Esc',
  backspace: '⌫',
  insert: 'Insert',
  delete: 'Delete',
  home: 'Home',
  end: 'End',
  pageup: 'PgUp',
  pagedown: 'PgDn',
  up: '↑',
  down: '↓',
  left: '←',
  right: '→',
  pause: 'Pause',
  capslock: 'Caps',
  scrolllock: 'ScrLk',
  printscreen: 'PrtSc'
}

/** "ctrl+shift+space" → ["Ctrl", "Shift", "Espaço"] (para desenhar as keycaps). */
export function rotulosDoAtalho(atalho: string): string[] {
  return atalho
    .split('+')
    .map((p) => p.trim().toLowerCase())
    .filter(Boolean)
    .map((p) => ROTULOS[p] ?? p.toUpperCase())
}

/** Mesmo atalho escrito de jeitos diferentes ("Shift+Ctrl+Space" = "ctrl+shift+space")? */
export function mesmoAtalho(a: string, b: string): boolean {
  const normal = (s: string): string =>
    s
      .split('+')
      .map((p) => p.trim().toLowerCase())
      .map((p) =>
        p === 'control'
          ? 'ctrl'
          : p === 'windows' || p === 'super'
            ? 'win'
            : p.replace(/^espa[çc]o$/, 'space')
      )
      .sort()
      .join('+')
  return normal(a) === normal(b)
}
