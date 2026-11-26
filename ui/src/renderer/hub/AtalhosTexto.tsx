// Atalhos de texto (DESENHO-V2 §8): gatilho falado → texto pronto. Buscar, adicionar, editar, apagar.
import { useState } from 'react'
import { Busca } from './pecas'
import ListaEditavel from './ListaEditavel'
import { pares, type ConfigHub } from './useConfig'
import { useBuscaComAtalho } from './useBuscaComAtalho'

export default function AtalhosTexto({ cfg, salvar }: ConfigHub): React.JSX.Element {
  const [busca, setBusca] = useState('')
  const campoBusca = useBuscaComAtalho()
  const atalhos = pares(cfg?.['atalhos_texto'], 'gatilho', 'texto')

  return (
    <div className="pagina">
      <header className="pagina-topo">
        <div>
          <h1>Atalhos de texto</h1>
          <p className="pagina-sub">
            Fale o gatilho enquanto dita e o GilleVoz escreve o texto pronto no lugar.
          </p>
        </div>
      </header>

      <div className="barra-ferramentas">
        <span className="contagem">
          {atalhos.length} {atalhos.length === 1 ? 'atalho' : 'atalhos'}
        </span>
        <Busca ref={campoBusca} valor={busca} aoMudar={setBusca} dica="Buscar atalho" />
      </div>

      <ListaEditavel
        carregando={!cfg}
        colunas={[
          {
            chave: 'gatilho',
            titulo: 'Quando eu disser',
            dica: 'Quando eu disser… ex.: meu email'
          },
          { chave: 'texto', titulo: 'Escrever', dica: 'Escrever… ex.: voce@exemplo.com' }
        ]}
        itens={atalhos}
        busca={busca}
        rotuloAdicionar="Adicionar"
        vazio="Nenhum atalho ainda. Ex.: “meu endereço” → seu endereço completo."
        aoSalvar={(novos, adiar) =>
          salvar(
            { atalhos_texto: novos.map((r) => ({ gatilho: r.gatilho, texto: r.texto })) },
            { adiar }
          )
        }
      />
    </div>
  )
}
