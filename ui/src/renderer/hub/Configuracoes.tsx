// Configurações (DESENHO-V2 §8): Geral, Atalhos, Ditado, Sons, Motor e Sobre numa página só, com as
// seções num índice fixo no topo. Tudo salva na hora; o motor aplica sem reiniciar (menos modelo e
// dispositivo, que recarregam o modelo com aviso).
import { useEffect, useRef, useState } from 'react'
import { IconFolder, IconRefresh, IconFileText } from '@tabler/icons-react'
import type { InfoHub, Situacao } from '../../shared/janelas'
import { Interruptor, Segmentado, Selecao, Teclas, type Opcao } from './pecas'
import { useAvisar } from './avisos'
import GravarAtalho, { type OutroAtalho } from './GravarAtalho'
import type { ConfigHub } from './useConfig'
import type { SalvarAtalho, SuspenderAtalhos } from './Hub'

type Secao = 'geral' | 'atalhos' | 'ditado' | 'sons' | 'motor' | 'sobre'

const SECOES: Array<{ valor: Secao; rotulo: string }> = [
  { valor: 'geral', rotulo: 'Geral' },
  { valor: 'atalhos', rotulo: 'Atalhos' },
  { valor: 'ditado', rotulo: 'Ditado' },
  { valor: 'sons', rotulo: 'Sons' },
  { valor: 'motor', rotulo: 'Motor' },
  { valor: 'sobre', rotulo: 'Sobre' }
]

const IDIOMAS: Opcao[] = [
  { valor: 'pt', rotulo: 'Português' },
  { valor: 'en', rotulo: 'Inglês' },
  { valor: 'es', rotulo: 'Espanhol' }
]

const MODELOS: Opcao[] = [
  { valor: 'large-v3-turbo', rotulo: 'large-v3-turbo', detalhe: 'rápido e preciso' },
  { valor: 'large-v3', rotulo: 'large-v3', detalhe: 'mais preciso, mais lento' },
  { valor: 'medium', rotulo: 'medium', detalhe: 'meio-termo' },
  { valor: 'small', rotulo: 'small', detalhe: 'leve' },
  { valor: 'base', rotulo: 'base', detalhe: 'mais leve' }
]

const ATALHOS: Array<{ chave: string; nome: string; descricao: string; opcional: boolean }> = [
  {
    chave: 'atalho',
    nome: 'Mãos livres',
    descricao: 'Aperta para começar, aperta de novo para parar.',
    opcional: false
  },
  {
    chave: 'atalho_push',
    nome: 'Segurar para falar',
    descricao: 'Grava enquanto você segura. Cola no final (sem tempo real).',
    opcional: true
  },
  {
    chave: 'atalho_colar_ultima',
    nome: 'Colar última',
    descricao: 'Cola de novo o último ditado na janela em foco.',
    opcional: true
  },
  {
    chave: 'atalho_copiar_ultima',
    nome: 'Copiar última',
    descricao: 'Copia o último ditado para a área de transferência.',
    opcional: true
  }
]

interface Microfone {
  indice: number
  nome: string
}

export default function Configuracoes({
  cfg,
  salvar,
  salvarAtalho,
  suspenderAtalhos,
  situacao,
  info,
  aoMudarInfo
}: ConfigHub & {
  salvarAtalho: SalvarAtalho
  suspenderAtalhos: SuspenderAtalhos
  situacao: Situacao | null
  info: InfoHub | null
  aoMudarInfo: (i: InfoHub) => void
}): React.JSX.Element {
  const api = window.gillevoz
  const avisar = useAvisar()
  const [secao, setSecao] = useState<Secao>('geral')
  const [mics, setMics] = useState<Microfone[] | null>(null)
  const rolandoPara = useRef<Secao | null>(null)
  const carregando = !cfg

  // Microfones (o motor só responde depois de pronto).
  useEffect(() => {
    if (!situacao?.pronto) return
    api
      .pedir<{ itens?: Microfone[] }>('listar_microfones')
      .then((r) => setMics(Array.isArray(r.itens) ? r.itens : []))
      .catch(() => setMics([]))
  }, [api, situacao?.pronto])

  // Seção visível acompanha a rolagem.
  useEffect(() => {
    const rolagem = document.querySelector('.hub-pagina')
    if (!rolagem) return
    const aoRolar = (): void => {
      if (rolandoPara.current) return
      const topo = rolagem.getBoundingClientRect().top + 72
      let atual: Secao = 'geral'
      for (const s of SECOES) {
        const el = document.getElementById(`secao-${s.valor}`)
        if (el && el.getBoundingClientRect().top <= topo) atual = s.valor
      }
      if (rolagem.scrollTop + rolagem.clientHeight >= rolagem.scrollHeight - 4) atual = 'sobre'
      setSecao(atual)
    }
    const fim = (): void => {
      rolandoPara.current = null
    }
    rolagem.addEventListener('scroll', aoRolar, { passive: true })
    rolagem.addEventListener('scrollend', fim)
    return () => {
      rolagem.removeEventListener('scroll', aoRolar)
      rolagem.removeEventListener('scrollend', fim)
    }
  }, [])

  const irPara = (s: Secao): void => {
    setSecao(s)
    rolandoPara.current = s
    document.getElementById(`secao-${s}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const bool = (chave: string, padrao: boolean): boolean =>
    typeof cfg?.[chave] === 'boolean' ? (cfg[chave] as boolean) : padrao
  const texto = (chave: string): string | null =>
    typeof cfg?.[chave] === 'string' ? (cfg[chave] as string) : null
  const interruptor = (chave: string, padrao: boolean, rotulo: string): React.JSX.Element => (
    <Interruptor
      rotulo={rotulo}
      ligado={bool(chave, padrao)}
      desativado={carregando}
      aoMudar={(v) => void salvar({ [chave]: v })}
    />
  )

  // Microfone: o config guarda o nome (ou o índice, vindo do v1); null = padrão do sistema.
  const micCfg = cfg?.['microfone']
  const micAtual =
    micCfg === null || micCfg === undefined
      ? 'padrao'
      : typeof micCfg === 'number'
        ? (mics?.find((m) => m.indice === micCfg)?.nome ?? String(micCfg))
        : String(micCfg)
  const opcoesMic: Opcao[] = [
    { valor: 'padrao', rotulo: 'Padrão do sistema' },
    ...(mics ?? []).map((m) => ({ valor: m.nome, rotulo: m.nome })),
    ...(micAtual !== 'padrao' && mics && !mics.some((m) => m.nome === micAtual)
      ? [{ valor: micAtual, rotulo: micAtual, detalhe: 'não encontrado' }]
      : [])
  ]

  const dispositivo = texto('dispositivo') === 'cpu' ? 'cpu' : 'cuda'
  const chaveModelo = dispositivo === 'cpu' ? 'modelo_cpu' : 'modelo'
  const modeloAtual = texto(chaveModelo) ?? (dispositivo === 'cpu' ? 'small' : 'large-v3-turbo')
  const opcoesModelo = MODELOS.some((m) => m.valor === modeloAtual)
    ? MODELOS
    : [...MODELOS, { valor: modeloAtual, rotulo: modeloAtual }]
  const trocarMotor = (mudanca: Record<string, unknown>): void => {
    void salvar(mudanca)
    avisar('Recarregando o modelo — leva alguns segundos', 'info')
  }

  const outros = (chave: string): OutroAtalho[] =>
    ATALHOS.filter((a) => a.chave !== chave).map((a) => ({ nome: a.nome, valor: texto(a.chave) }))

  const efetivo = info?.motor
  const statusMotor = situacao?.desistiu
    ? { tom: 'erro', texto: 'Parou depois de cair várias vezes' }
    : !situacao?.pronto || !efetivo
      ? { tom: 'carregando', texto: 'Carregando o modelo…' }
      : {
          tom: 'ocioso',
          texto: `${efetivo.dispositivo === 'cuda' ? 'Placa de vídeo (CUDA)' : 'Processador (CPU)'} · ${efetivo.modelo ?? '?'}`
        }
  const caiuParaCpu = situacao?.pronto && efetivo?.dispositivo === 'cpu' && dispositivo === 'cuda'

  return (
    <div className="pagina configuracoes">
      <header className="pagina-topo">
        <div>
          <h1>Configurações</h1>
          <p className="pagina-sub">Tudo salva na hora.</p>
        </div>
      </header>

      <div className="indice-secoes">
        <Segmentado<Secao> rotulo="Seções" valor={secao} aoMudar={irPara} opcoes={SECOES} />
      </div>

      <Bloco id="geral" titulo="Geral">
        <Linha titulo="Microfone" descricao="De onde vem a sua voz.">
          <Selecao
            rotulo="Microfone"
            valor={micAtual}
            opcoes={opcoesMic}
            largura={260}
            aoMudar={(v) => void salvar({ microfone: v === 'padrao' ? null : v })}
          />
        </Linha>
        <Linha titulo="Idioma da fala" descricao="O idioma em que você dita.">
          <Selecao
            rotulo="Idioma da fala"
            valor={texto('idioma') ?? 'pt'}
            opcoes={IDIOMAS}
            largura={180}
            aoMudar={(v) => void salvar({ idioma: v })}
          />
        </Linha>
        <Linha titulo="Iniciar com o Windows" descricao="Abre o GilleVoz quando você liga o PC.">
          <Interruptor
            rotulo="Iniciar com o Windows"
            ligado={info?.iniciarComWindows ?? false}
            desativado={!info}
            aoMudar={(v) => {
              api.hub
                .iniciarComWindows(v)
                .then((ficou) => info && aoMudarInfo({ ...info, iniciarComWindows: ficou }))
                .catch(() => avisar('Não consegui mudar o início com o Windows.', 'erro'))
            }}
          />
        </Linha>
        <Linha
          titulo="Mostrar a barra sempre"
          descricao="Desligado: a barra só aparece enquanto você dita."
        >
          {interruptor('barra_ativa', true, 'Mostrar a barra sempre')}
        </Linha>
      </Bloco>

      <Bloco id="atalhos" titulo="Atalhos">
        {ATALHOS.slice(0, 2).map((a) => (
          <Linha key={a.chave} titulo={a.nome} descricao={a.descricao}>
            <GravarAtalho
              chave={a.chave}
              valor={texto(a.chave)}
              opcional={a.opcional}
              outros={outros(a.chave)}
              salvarAtalho={salvarAtalho}
              suspenderAtalhos={suspenderAtalhos}
              desativado={carregando}
            />
          </Linha>
        ))}
        <Linha titulo="Cancelar" descricao="Durante o ditado, descarta o que está gravando.">
          <span className="atalho-fixo">
            <Teclas rotulos={['Esc']} />
            <span className="fixo">fixo</span>
          </span>
        </Linha>
        {ATALHOS.slice(2).map((a) => (
          <Linha key={a.chave} titulo={a.nome} descricao={a.descricao}>
            <GravarAtalho
              chave={a.chave}
              valor={texto(a.chave)}
              opcional={a.opcional}
              outros={outros(a.chave)}
              salvarAtalho={salvarAtalho}
              suspenderAtalhos={suspenderAtalhos}
              desativado={carregando}
            />
          </Linha>
        ))}
      </Bloco>

      <Bloco id="ditado" titulo="Ditado">
        <Linha
          titulo="Tempo real"
          descricao="Digita enquanto você fala (no modo mãos livres). Desligado: cola tudo no final."
        >
          {interruptor('tempo_real', true, 'Tempo real')}
        </Linha>
        <Linha
          titulo="Espaço no final"
          descricao="Deixa um espaço depois do texto, pronto para continuar."
        >
          {interruptor('espaco_final', true, 'Espaço no final')}
        </Linha>
        <Linha titulo="Enter automático" descricao="Aperta Enter quando termina de escrever.">
          {interruptor('auto_enter', false, 'Enter automático')}
        </Linha>
        <Linha
          titulo="Comando “pressione enter”"
          descricao="Falar “pressione enter” no fim do ditado aperta Enter em vez de escrever."
        >
          {interruptor('comando_enter', true, 'Comando pressione enter')}
        </Linha>
      </Bloco>

      <Bloco id="sons" titulo="Sons">
        <Linha titulo="Bipes" descricao="Um bipe curto ao começar e ao terminar de gravar.">
          {interruptor('bips', true, 'Bipes')}
        </Linha>
        <Linha
          titulo="Silenciar o PC enquanto dita"
          descricao="Tira o som do computador e devolve o volume quando termina."
        >
          {interruptor('silenciar_pc', false, 'Silenciar o PC enquanto dita')}
        </Linha>
      </Bloco>

      <Bloco id="motor" titulo="Motor">
        <Linha
          titulo="Processar em"
          descricao="A placa de vídeo é bem mais rápida; o processador serve sem ela."
        >
          <Segmentado<'cuda' | 'cpu'>
            rotulo="Processar em"
            valor={dispositivo}
            aoMudar={(v) => trocarMotor({ dispositivo: v })}
            opcoes={[
              { valor: 'cuda', rotulo: 'Placa de vídeo' },
              { valor: 'cpu', rotulo: 'Processador' }
            ]}
          />
        </Linha>
        <Linha
          titulo="Modelo"
          descricao={`Usado ${dispositivo === 'cpu' ? 'no processador' : 'na placa de vídeo'}. Um modelo novo é baixado só na primeira vez.`}
        >
          <Selecao
            rotulo="Modelo"
            valor={modeloAtual}
            opcoes={opcoesModelo}
            largura={260}
            aoMudar={(v) => trocarMotor({ [chaveModelo]: v })}
          />
        </Linha>
        <Linha
          titulo="Status"
          descricao={
            caiuParaCpu
              ? 'A placa de vídeo falhou; está rodando no processador.'
              : 'O que está rodando agora.'
          }
        >
          <span className="status-motor-linha">
            <span className={`status-ponto ${statusMotor.tom}`} aria-hidden />
            <span className="mono">{statusMotor.texto}</span>
          </span>
        </Linha>
        <Linha titulo="Recarregar motor" descricao="Reinicia o motor e carrega o modelo de novo.">
          <button
            type="button"
            className="botao secundario"
            onClick={() => {
              api.hub.recarregarMotor()
              avisar('Recarregando o motor…', 'info')
            }}
          >
            <IconRefresh size={14} stroke={1.5} />
            Recarregar
          </button>
        </Linha>
      </Bloco>

      <Bloco id="sobre" titulo="Sobre">
        <Linha titulo="Versão">
          <span className="mono">{info?.versao ?? '—'}</span>
        </Linha>
        <Linha titulo="Pasta dos dados" descricao={info?.pastaDados ?? '—'} descricaoMono>
          <button
            type="button"
            className="botao secundario"
            onClick={() => api.hub.abrirPasta('dados')}
          >
            <IconFolder size={14} stroke={1.5} />
            Abrir pasta
          </button>
        </Linha>
        <Linha titulo="Logs" descricao="Para quando algo der errado.">
          <button
            type="button"
            className="botao secundario"
            onClick={() => api.hub.abrirPasta('logs')}
          >
            <IconFileText size={14} stroke={1.5} />
            Abrir logs
          </button>
        </Linha>
      </Bloco>
      <p className="rodape">GilleVoz · ditado local — sua voz não sai do seu PC.</p>
    </div>
  )
}

const Bloco = ({
  id,
  titulo,
  children
}: {
  id: Secao
  titulo: string
  children: React.ReactNode
}): React.JSX.Element => (
  <section className="secao" id={`secao-${id}`}>
    <h2 className="secao-titulo">{titulo}</h2>
    <div className="secao-cartao">{children}</div>
  </section>
)

function Linha({
  titulo,
  descricao,
  descricaoMono,
  children
}: {
  titulo: string
  descricao?: string
  descricaoMono?: boolean
  children: React.ReactNode
}): React.JSX.Element {
  return (
    <div className="ajuste">
      <div className="ajuste-texto">
        <div className="ajuste-titulo">{titulo}</div>
        {descricao && (
          <div
            className={`ajuste-descricao ${descricaoMono ? 'mono' : ''}`}
            title={descricaoMono ? descricao : undefined}
          >
            {descricao}
          </div>
        )}
      </div>
      <div className="ajuste-controle">{children}</div>
    </div>
  )
}
