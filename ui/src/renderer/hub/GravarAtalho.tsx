// "Gravar novo atalho": a pessoa aperta a combinação e ela vira o atalho na hora (o motor aplica sem
// reiniciar). Também aceita os botões laterais do mouse (mouse4/mouse5). Recusa só modificadores, tecla que o motor não entende, tecla comum sozinha e atalho
// já usado; o erro aparece embaixo do campo. Cada tecla apertada "afunda" 1 px na keycap.
import { useEffect, useState } from 'react'
import { IconKeyboard, IconX } from '@tabler/icons-react'
import { Teclas } from './pecas'
import { useAvisar } from './avisos'
import { botaoParaAtalho, mesmoAtalho, rotulosDoAtalho, teclaParaAtalho } from './atalho'
import type { SalvarAtalho, SuspenderAtalhos } from './Hub'

/** Teclas que só servem como atalho junto com Ctrl/Alt/Shift/Win (sozinhas atrapalham a digitação). */
const PRECISA_MODIFICADOR =
  /^([a-z0-9]|space|enter|tab|backspace|delete|insert|home|end|pageup|pagedown|up|down|left|right|esc)$/

const MODIFICADORES: Record<string, string> = {
  Control: 'Ctrl',
  Alt: 'Alt',
  Shift: 'Shift',
  Meta: 'Win',
  OS: 'Win'
}

export interface OutroAtalho {
  nome: string
  valor: string | null
}

export default function GravarAtalho({
  chave,
  valor,
  opcional,
  outros,
  salvarAtalho,
  suspenderAtalhos,
  desativado
}: {
  chave: string
  valor: string | null
  /** Pode ficar desligado (null). */
  opcional?: boolean
  /** Os outros atalhos, para recusar repetido. */
  outros: OutroAtalho[]
  salvarAtalho: SalvarAtalho
  suspenderAtalhos: SuspenderAtalhos
  desativado?: boolean
}): React.JSX.Element {
  const avisar = useAvisar()
  const [gravando, setGravando] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [apertadas, setApertadas] = useState<string[]>([])

  const gravar = async (novo: string | null): Promise<void> => {
    setSalvando(true)
    const e = await salvarAtalho(chave, novo)
    setSalvando(false)
    setErro(e)
    if (!e) avisar(novo ? 'Atalho salvo — já vale' : 'Atalho desligado')
  }

  useEffect(() => {
    if (!gravando) return
    // Enquanto grava, os atalhos do GilleVoz não podem disparar (o Windows os entregaria ao motor).
    const retomar = suspenderAtalhos()
    // Teclas cujo "apertar" chegou aqui. Um atalho já registrado no Windows (do GilleVoz ou de outro
    // programa) some no apertar e só o "soltar" chega: é assim que dá para avisar que está em uso.
    const vistas = new Set<string>()
    const parar = (): void => {
      setGravando(false)
      setApertadas([])
    }
    const modificadores = (e: KeyboardEvent): string[] =>
      [e.ctrlKey && 'Ctrl', e.altKey && 'Alt', e.shiftKey && 'Shift', e.metaKey && 'Win'].filter(
        (x): x is string => !!x
      )
    const desce = (e: KeyboardEvent): void => {
      e.preventDefault()
      e.stopPropagation()
      vistas.add(e.code || e.key)
      if (e.repeat) return
      const semMods = !e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey
      if (e.key === 'Escape' && semMods) return parar()
      if (MODIFICADORES[e.key]) {
        setApertadas(modificadores(e))
        return
      }
      const atalho = teclaParaAtalho(e)
      if (!atalho) {
        // "Unidentified": tecla fantasma que o motor manda junto de atalhos com Alt/Win; ignora.
        if (e.key !== 'Unidentified') {
          setErro('Essa tecla não serve. Use uma letra, um número, F1–F24, Espaço ou Enter.')
        }
        return
      }
      setApertadas(rotulosDoAtalho(atalho))
      const principal = atalho.split('+').pop()!
      const soShift = e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey
      if ((semMods || soShift) && PRECISA_MODIFICADOR.test(principal)) {
        setErro(
          soShift
            ? 'Shift com essa tecla atrapalharia a digitação (maiúsculas). Use Ctrl, Alt ou Win.'
            : 'Use junto com Ctrl, Alt ou Win — sozinha essa tecla atrapalharia a digitação.'
        )
        return
      }
      aceitar(atalho)
    }
    /** Atalho completo: recusa repetido, senão grava (se mudou). */
    const aceitar = (atalho: string): void => {
      const repetido = outros.find((o) => o.valor && mesmoAtalho(o.valor, atalho))
      if (repetido) {
        setErro(`Esse atalho já é usado em “${repetido.nome}”.`)
        return
      }
      parar()
      if (valor && mesmoAtalho(valor, atalho)) {
        setErro(null)
        return
      }
      void gravar(atalho)
    }
    // Botões laterais do mouse (o esquerdo fica livre para clicar em "Cancelar").
    const lateral = (e: MouseEvent): boolean => e.button === 3 || e.button === 4
    const mouseDesce = (e: MouseEvent): void => {
      if (e.button === 0) return
      e.preventDefault()
      e.stopPropagation()
      const atalho = botaoParaAtalho(e)
      if (!atalho) {
        setErro('Use um botão lateral do mouse.')
        return
      }
      setApertadas(rotulosDoAtalho(atalho))
      aceitar(atalho)
    }
    // Não deixa o botão lateral "voltar/avançar" nem o do meio colar/rolar enquanto grava.
    const mouseEngole = (e: MouseEvent): void => {
      if (e.button === 0) return
      e.preventDefault()
      if (lateral(e)) e.stopPropagation()
    }
    const sobe = (e: KeyboardEvent): void => {
      e.preventDefault()
      const apertou = vistas.delete(e.code || e.key)
      setApertadas(modificadores(e))
      if (apertou || MODIFICADORES[e.key]) return
      const atalho = teclaParaAtalho(e)
      if (!atalho) return
      setApertadas(rotulosDoAtalho(atalho))
      const dono = [{ nome: 'este atalho', valor }, ...outros].find(
        (o) => o.valor && mesmoAtalho(o.valor, atalho)
      )
      if (dono?.nome === 'este atalho') {
        setErro(null)
        parar()
      } else if (dono) setErro(`Esse atalho já é usado em “${dono.nome}”.`)
      else setErro('Esse atalho já é usado por outro programa. Escolha outra combinação.')
    }
    window.addEventListener('keydown', desce, true)
    window.addEventListener('keyup', sobe, true)
    window.addEventListener('blur', parar)
    window.addEventListener('mousedown', mouseDesce, true)
    window.addEventListener('mouseup', mouseEngole, true)
    window.addEventListener('auxclick', mouseEngole, true)
    return () => {
      retomar()
      window.removeEventListener('keydown', desce, true)
      window.removeEventListener('keyup', sobe, true)
      window.removeEventListener('mousedown', mouseDesce, true)
      window.removeEventListener('mouseup', mouseEngole, true)
      window.removeEventListener('auxclick', mouseEngole, true)
      window.removeEventListener('blur', parar)
    }
    // gravar/outros/valor mudam a cada render; o que importa é ligar/desligar a escuta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gravando])

  const comecar = (): void => {
    setErro(null)
    setApertadas([])
    setGravando(true)
  }

  return (
    <div className="gravar">
      <div className="gravar-controle">
        {gravando ? (
          <div className="gravador" role="status" aria-live="polite">
            {apertadas.length ? (
              <Teclas rotulos={apertadas} apertadas={new Set(apertadas)} />
            ) : (
              <span className="gravador-dica">Aperte as teclas ou um botão lateral do mouse…</span>
            )}
            <span className="gravador-esc">
              <kbd className="tecla mini">Esc</kbd> cancela
            </span>
          </div>
        ) : (
          <button
            type="button"
            className={`atalho-atual ${valor ? '' : 'desligado'}`}
            onClick={comecar}
            disabled={desativado || salvando}
            title="Gravar novo atalho"
          >
            {salvando ? (
              <span className="gravador-dica">Salvando…</span>
            ) : valor ? (
              <Teclas atalho={valor} />
            ) : (
              <span>Desligado</span>
            )}
          </button>
        )}
        {gravando ? (
          <button
            type="button"
            className="botao secundario pequeno"
            onClick={() => {
              setGravando(false)
              setApertadas([])
            }}
          >
            Cancelar
          </button>
        ) : (
          <button
            type="button"
            className="botao secundario pequeno"
            onClick={comecar}
            disabled={desativado || salvando}
          >
            <IconKeyboard size={14} stroke={1.5} />
            {valor ? 'Gravar novo' : 'Definir'}
          </button>
        )}
        {opcional && valor && !gravando && (
          <button
            type="button"
            className="icone-botao"
            aria-label="Desligar este atalho"
            title="Desligar"
            disabled={desativado || salvando}
            onClick={() => void gravar(null)}
          >
            <IconX size={14} stroke={1.5} />
          </button>
        )}
      </div>
      {erro && (
        <p className="gravar-erro" role="alert">
          {erro}
        </p>
      )}
    </div>
  )
}
