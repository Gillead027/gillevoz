// Lista editável do Dicionário e dos Atalhos de texto: adicionar no topo, editar no lugar (salva
// 400 ms depois de parar de digitar) e apagar segurando. Usada com 1 coluna (palavras) ou 2 (pares).
import { useEffect, useRef, useState } from 'react'
import { IconArrowRight, IconPlus } from '@tabler/icons-react'
import { BotaoSegurar } from './pecas'
import { useAvisar } from './avisos'
import { normalizar } from './useConfig'

export interface Coluna {
  chave: string
  titulo: string
  dica: string
  /** Pode ficar vazio (ex.: troca que apaga a palavra). */
  vazioOk?: boolean
}

type Registro = Record<string, string>

export default function ListaEditavel({
  colunas,
  itens,
  busca,
  aoSalvar,
  rotuloAdicionar,
  vazio,
  carregando
}: {
  colunas: Coluna[]
  itens: Registro[]
  busca: string
  aoSalvar: (novos: Registro[], adiar?: boolean) => void
  rotuloAdicionar: string
  vazio: React.ReactNode
  carregando: boolean
}): React.JSX.Element {
  const avisar = useAvisar()
  const novoVazio = (): Registro => Object.fromEntries(colunas.map((c) => [c.chave, '']))
  const [novo, setNovo] = useState<Registro>(novoVazio)
  const campos = useRef<Array<HTMLInputElement | null>>([])
  const primeira = colunas[0].chave
  // Chave estável de cada linha (o índice muda ao apagar e o texto muda ao editar).
  const [chaves, setChaves] = useState(() => ({
    ids: itens.map((_, i) => i + 1),
    proximo: itens.length + 1
  }))
  let ids = chaves.ids
  if (ids.length !== itens.length) {
    // A lista mudou por fora (ex.: outra janela): chaves novas para todas.
    const novas = {
      ids: itens.map((_, i) => chaves.proximo + i),
      proximo: chaves.proximo + itens.length
    }
    setChaves(novas)
    ids = novas.ids
  }

  const valido = (r: Registro): boolean =>
    colunas.every((c) => c.vazioOk || r[c.chave].trim().length > 0)
  const repetido = (r: Registro, ignorar = -1): boolean =>
    itens.some((x, i) => i !== ignorar && normalizar(x[primeira]) === normalizar(r[primeira]))

  const adicionar = (): void => {
    const limpo = Object.fromEntries(colunas.map((c) => [c.chave, novo[c.chave].trim()]))
    if (!valido(limpo)) {
      const falta = colunas.findIndex((c) => !c.vazioOk && !limpo[c.chave])
      campos.current[falta]?.focus()
      return
    }
    if (repetido(limpo)) {
      avisar(`"${limpo[primeira]}" já está na lista`, 'info')
      return
    }
    setChaves({ ids: [chaves.proximo, ...ids], proximo: chaves.proximo + 1 })
    aoSalvar([limpo, ...itens])
    setNovo(novoVazio())
    campos.current[0]?.focus()
  }

  const termo = normalizar(busca)
  const visiveis = itens
    .map((item, indice) => ({ item, indice }))
    .filter(({ item }) => !termo || colunas.some((c) => normalizar(item[c.chave]).includes(termo)))

  return (
    <div className="lista-editavel">
      <form
        className={`linha-nova ${colunas.length === 1 ? 'uma' : 'duas'}`}
        onSubmit={(e) => {
          e.preventDefault()
          adicionar()
        }}
      >
        {colunas.map((c, i) => (
          <div key={c.chave} className="linha-nova-campo">
            {i > 0 && <IconArrowRight size={14} stroke={1.5} className="seta" aria-hidden />}
            <input
              ref={(el) => {
                campos.current[i] = el
              }}
              className="campo"
              value={novo[c.chave]}
              placeholder={c.dica}
              aria-label={c.titulo}
              spellCheck={false}
              disabled={carregando}
              onChange={(e) => setNovo((n) => ({ ...n, [c.chave]: e.target.value }))}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && i < colunas.length - 1) {
                  e.preventDefault()
                  campos.current[i + 1]?.focus()
                }
              }}
            />
          </div>
        ))}
        <button
          type="submit"
          className="botao primario quadrado"
          disabled={carregando}
          aria-label={rotuloAdicionar}
          title={`${rotuloAdicionar} (Enter)`}
        >
          <IconPlus size={16} stroke={2} />
        </button>
      </form>

      {colunas.length > 1 && visiveis.length > 0 && (
        <div className="lista-cabecalho" aria-hidden>
          <span>{colunas[0].titulo}</span>
          <span className="segunda">{colunas[1].titulo}</span>
          <span />
        </div>
      )}

      {carregando ? (
        <div className="vazio">O motor está carregando o modelo…</div>
      ) : visiveis.length === 0 ? (
        <div className="vazio">{termo ? <>Nada encontrado para “{busca.trim()}”.</> : vazio}</div>
      ) : (
        <ul className={`lista ${colunas.length === 1 ? 'uma' : 'duas'}`}>
          {visiveis.map(({ item, indice }) => (
            <LinhaEditavel
              key={ids[indice]}
              colunas={colunas}
              item={item}
              aoMudar={(r) => {
                if (!valido(r)) return // espera ficar válido (vazio some do config)
                if (repetido(r, indice)) return
                aoSalvar(
                  itens.map((x, i) => (i === indice ? r : x)),
                  true
                )
              }}
              aoApagar={() => {
                setChaves({ ids: ids.filter((_, i) => i !== indice), proximo: chaves.proximo })
                aoSalvar(itens.filter((_, i) => i !== indice))
                avisar(`"${item[primeira]}" apagado`)
              }}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function LinhaEditavel({
  colunas,
  item,
  aoMudar,
  aoApagar
}: {
  colunas: Coluna[]
  item: Registro
  aoMudar: (r: Registro) => void
  aoApagar: () => void
}): React.JSX.Element {
  const avisar = useAvisar()
  const [rascunho, setRascunho] = useState<Registro>(item)
  const editando = useRef(false)

  // O config mudou por fora (ex.: outra janela): acompanha, a não ser que esteja digitando.
  useEffect(() => {
    if (!editando.current) setRascunho(item)
  }, [item])

  return (
    <li className="linha">
      {colunas.map((c, i) => (
        <div key={c.chave} className="linha-campo">
          {i > 0 && <IconArrowRight size={14} stroke={1.5} className="seta" aria-hidden />}
          <input
            className="campo-no-lugar"
            value={rascunho[c.chave]}
            aria-label={c.titulo}
            spellCheck={false}
            placeholder={c.vazioOk ? '(apagar)' : ''}
            onFocus={() => (editando.current = true)}
            onBlur={() => {
              editando.current = false
              // Ficou inválido (campo obrigatório vazio): volta ao que está salvo.
              if (colunas.some((k) => !k.vazioOk && !rascunho[k.chave].trim())) setRascunho(item)
            }}
            onChange={(e) => {
              const r = { ...rascunho, [c.chave]: e.target.value }
              setRascunho(r)
              aoMudar(Object.fromEntries(colunas.map((k) => [k.chave, r[k.chave].trim()])))
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === 'Escape') (e.target as HTMLInputElement).blur()
            }}
          />
        </div>
      ))}
      <BotaoSegurar
        aoConcluir={aoApagar}
        aoSoltarCedo={() => avisar('Segure para apagar', 'info')}
      />
    </li>
  )
}
