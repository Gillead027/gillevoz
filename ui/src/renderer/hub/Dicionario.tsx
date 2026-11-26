// Dicionário (DESENHO-V2 §8): Palavras (= `vocabulario`, ajudam o Whisper a reconhecer) e Trocas
// ("o que o Whisper escreve" → "como deve ficar"). Buscar, adicionar, editar e apagar.
import { useState } from 'react'
import { Busca, Segmentado } from './pecas'
import ListaEditavel from './ListaEditavel'
import { pares, textos, type ConfigHub } from './useConfig'
import { useBuscaComAtalho } from './useBuscaComAtalho'

type Aba = 'palavras' | 'trocas'

export default function Dicionario({ cfg, salvar }: ConfigHub): React.JSX.Element {
  const [aba, setAba] = useState<Aba>('palavras')
  const [busca, setBusca] = useState('')
  const campoBusca = useBuscaComAtalho()
  const palavras = textos(cfg?.['vocabulario'])
  const trocas = pares(cfg?.['trocas'], 'de', 'para')

  return (
    <div className="pagina">
      <header className="pagina-topo">
        <div>
          <h1>Dicionário</h1>
          <p className="pagina-sub">
            {aba === 'palavras'
              ? 'Nomes e termos que o Whisper deve reconhecer do jeito certo.'
              : 'Quando o Whisper escrever algo errado, o GilleVoz troca antes de digitar.'}
          </p>
        </div>
      </header>

      <div className="barra-ferramentas">
        <Segmentado<Aba>
          rotulo="Listas do dicionário"
          valor={aba}
          aoMudar={setAba}
          opcoes={[
            { valor: 'palavras', rotulo: 'Palavras', extra: palavras.length },
            { valor: 'trocas', rotulo: 'Trocas', extra: trocas.length }
          ]}
        />
        <Busca
          ref={campoBusca}
          valor={busca}
          aoMudar={setBusca}
          dica={aba === 'palavras' ? 'Buscar palavra' : 'Buscar troca'}
        />
      </div>

      {aba === 'palavras' ? (
        <ListaEditavel
          key="palavras"
          carregando={!cfg}
          colunas={[{ chave: 'palavra', titulo: 'Palavra', dica: 'Nova palavra, ex.: Supabase' }]}
          itens={palavras.map((palavra) => ({ palavra }))}
          busca={busca}
          rotuloAdicionar="Adicionar"
          vazio="Nenhuma palavra ainda. Adicione nomes próprios, marcas e gírias que você usa."
          aoSalvar={(novos, adiar) =>
            salvar({ vocabulario: novos.map((r) => r.palavra) }, { adiar })
          }
        />
      ) : (
        <ListaEditavel
          key="trocas"
          carregando={!cfg}
          colunas={[
            {
              chave: 'de',
              titulo: 'O Whisper escreve',
              dica: 'O Whisper escreve… ex.: cloud code'
            },
            {
              chave: 'para',
              titulo: 'Fica assim',
              dica: 'Fica assim… ex.: Claude Code',
              vazioOk: true
            }
          ]}
          itens={trocas}
          busca={busca}
          rotuloAdicionar="Adicionar"
          vazio="Nenhuma troca ainda. Ex.: “cloud code” → “Claude Code”."
          aoSalvar={(novos, adiar) =>
            salvar({ trocas: novos.map((r) => ({ de: r.de, para: r.para })) }, { adiar })
          }
        />
      )}
    </div>
  )
}
