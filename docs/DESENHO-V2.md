# GilleVoz v2 — desenho

> 2026-11-25. Base: [SPEC.md](SPEC.md), [ARQUITETURA.md](ARQUITETURA.md).
> Decidido com o Gillezin: funções/estrutura/animações no nível do Wispr Flow, visual próprio,
> **texto em tempo real digitado onde ele escreve**, **Electron na interface + motor Python**,
> direção visual **Espectro térmico**, **instalador .exe só para ele** (leve, Python próprio).

## 1. Por quê
O GilleVoz v1 funciona (atalho → fala → cola), mas a cara é de protótipo: barra Win32 sem animação,
configuração editando `config.json` à mão. O Gillezin quer o acabamento e as funções do Wispr Flow,
mantendo o que o GilleVoz tem de melhor: **100% local, privado, rápido na RTX 4060**. E quer um
instalador `.exe` para reinstalar/levar a outro PC dele.

## 2. Objetivos
1. **Flow Bar nova**: embaixo no centro, arrastável (gruda na esquerda, direita ou embaixo),
   estados animados com mola, onda de som "térmica" que esquenta com o volume. Nunca rouba o foco.
2. **Janela principal (Hub)**: Início (estatísticas + histórico por dia), Dicionário (palavras e trocas),
   Atalhos de texto (snippets) e Configurações em seções.
3. **Tempo real**: as palavras aparecem na janela onde ele escreve enquanto fala.
4. **Instalador** `GilleVoz-Setup.exe` que monta tudo num PC sem Python.

## 3. Não é objetivo (agora)
- IA de texto (estilos formal/casual, formatação inteligente, modo comando): fica para uma v3.
- Conta, nuvem, equipe, reuniões, calendário, conectores.
- Tema claro, outros idiomas de interface (só pt-BR), Mac/Linux.
- Instalador para terceiros (sem placa NVIDIA, sem internet).

## 4. Anti-objetivos (se acontecer, falhou mesmo "funcionando")
- Roubar o foco da janela onde ele escreve (nem por milissegundos).
- Perder o que estava na área de transferência.
- "Tempestade" de apagar e reescrever texto na janela dele durante o tempo real.
- Parecer o Wispr Flow (cores, logo, ilustrações, textos copiados).
- Ficar mais lento que o v1 para colar o texto final.

## 5. Caminhos considerados
| Caminho | Prós | Contras | Decisão |
|---|---|---|---|
| **Electron (interface) + motor Python** | animações/gradientes de nível web; janelas sem foco nativas (`focusable:false`, `showInactive`); mesma base do Wispr | 2 processos; +~100 MB | **Escolhido** |
| Tudo em Python com Qt (PySide6) | uma linguagem | acabamento inferior; sem-foco exige ajuste manual de novo | descartado |
| pywebview | HTML dentro do Python | barra transparente sem foco problemática | descartado |

Instalador: **Inno Setup 6** (já instalado) + **Python 3.12 embutível** (o instalador oficial do Python
conflitaria com o 3.12.10 que ele já tem), bibliotecas baixadas durante a instalação.

## 6. Arquitetura
```
Electron (ui/)  ── inicia e vigia ──►  Motor Python (gillevoz/)  modo --motor
  Flow Bar (janela sem foco)            atalho global (keyboard), gravação, Whisper GPU,
  Hub (janela normal)        ◄── JSON ── tempo real, digitação/colagem, histórico, config
  Bandeja do Windows          linhas por stdin/stdout
```
- **Electron é o dono**: abre o motor como processo filho (`pythonw -m gillevoz --motor`), reinicia se
  ele cair (até 3 vezes em 1 min, depois mostra erro na barra). Fechar o Electron encerra o motor.
- **O motor não tem janela nenhuma.** Saem do Python: `flowbar.py`, `indicator.py`, `tray.py`
  (substituídos pelo Electron). Ficam: `audio`, `transcriber`, `hotkey`, `paste`, `historico`, `config`,
  `cuda_dlls`, `startup` (passa a apontar para o executável do Electron).
- O **atalho global continua no Python** (`hotkey.py` do v1: `RegisterHotKey` + `GetAsyncKeyState` para
  detectar soltar, com a lib `keyboard` de reserva). O `globalShortcut` do Electron não detecta soltar a
  tecla, necessário para "segurar para falar". Todo atalho precisa ter uma tecla comum além dos
  modificadores (nada de só Ctrl+Win), para usar sempre o caminho `RegisterHotKey`.
- **stdout do motor é só do protocolo.** Qualquer `print` (ex.: em `config.py`) vira log; no modo
  `--motor`, `sys.stdout` é redirecionado para o log e o protocolo escreve num handle próprio.
- `python -m gillevoz --testar-wav` e `--baixar-modelo` continuam existindo (testes e instalador).

### 6.1 Protocolo motor ⇄ interface (uma mensagem JSON por linha, UTF-8)
Motor → interface:
| `tipo` | campos | quando |
|---|---|---|
| `pronto` | `dispositivo` ("cuda"/"cpu"), `modelo` | modelo carregado |
| `estado` | `estado`: `ocioso`/`gravando`/`transcrevendo`/`pausado`/`erro`, `msg?` | toda mudança |
| `nivel` | `valor` 0..1 | ~30x/s gravando |
| `parcial` | `confirmado` (texto já digitado até agora) | tempo real, a cada palavra confirmada |
| `final` | `texto`, `duracao_audio`, `tempo_transcricao`, `palavras` | ao terminar |
| `historico` | `dia` | histórico mudou (o Hub recarrega) |
| `config` | `cfg` | resposta a `ler_config` ou após salvar |
| `log` | `nivel`, `msg` | erros relevantes para mostrar |

Interface → motor: `iniciar`, `parar`, `cancelar`, `pausar`, `retomar`, `ler_config`,
`salvar_config {cfg}`, `colar_ultima`, `copiar_ultima`, `listar_historico {dia?}`,
`estatisticas`, `listar_microfones`, `sair`.
Respostas de consulta usam o mesmo `tipo` do pedido + `_resposta` (ex.: `estatisticas_resposta`)
e carregam o `id` que veio no pedido.

## 7. Flow Bar
- **Janela**: transparente, sem moldura, `focusable:false`, `alwaysOnTop` nível `screen-saver`,
  `skipTaskbar`, aberta com `showInactive()`. Tamanho fixo maior que a pílula (para caber a animação);
  a área transparente deixa o clique passar (`setIgnoreMouseEvents(true, {forward:true})`, desligado
  quando o mouse entra na pílula).
- **Posição**: padrão embaixo no centro da área útil do monitor do mouse, 14 px acima da barra de tarefas.
  Arrastar: ao soltar, gruda na borda mais próxima entre **esquerda / embaixo / direita**; salva no config.
- **Estados e tamanhos (aprox.)**
  | Estado | Pílula | Conteúdo |
  |---|---|---|
  | ocioso | 44×10, quase preta, 60% de opacidade | nada (discreta) |
  | mouse em cima | 128×32 | botão mic + botão engrenagem (abre o Hub) |
  | gravando | 220×36 | X cancelar · onda térmica (14 barras) · cronômetro · ■ parar |
  | transcrevendo | 120×32 | faixa térmica "correndo" |
  | pausado | 44×10 com risco | clique mostra "pausado" |
  | erro | 220×36, borda #BB3754 | mensagem curta 3 s, volta a ocioso |
- **Animações**: biblioteca Motion (mola). Tamanho da pílula: rigidez 600 / amortecimento 35.
  Entrada/saída de botões e textos: rigidez 300 / amortecimento 28 ou 0,15–0,3 s.
  Onda = **"termômetro de LED"** (14 colunas × 5 LEDs, cor térmica pela altura). Detalhes, tempos e
  micro-interações de todas as peças: **[REFERENCIAS-UI.md](REFERENCIAS-UI.md)** (vale como parte deste desenho).
- **Menu do clique direito**: Esconder por 1 hora · Microfone ▸ · Abrir GilleVoz · Pausar/Retomar · Sair.
  Menu nativo do Windows exige que a janela dona vá para a frente, o que roubaria o foco. Por isso o menu
  é **HTML próprio**, desenhado numa janela sem foco (mesma técnica da barra). Testar isso logo no início.
- Dica na primeira vez: "Arraste para mudar de lugar".

## 8. Hub (janela principal)
Janela normal, 960×640, sem moldura do Windows (barra de título própria). **O Hub pode ter foco** (tem
campos de texto); abrir o Hub é uma ação de "ir mexer no app", não de ditar. Por isso os itens do
histórico têm só **Copiar** (colar de novo é pelo atalho "colar última", que cola na janela em foco).
Menu lateral:
- **Início**: "E aí, Gillezin" + atalho atual; cartões de estatística (palavras hoje, palavras no total,
  ditados, palavras por minuto falado, sequência de dias); histórico agrupado por dia (Hoje, Ontem, data),
  cada item com horário, texto e copiar.
- **Dicionário**: duas listas — *Palavras* (= `vocabulario`, ajudam o Whisper) e *Trocas*
  ("o que o Whisper escreve" → "como deve ficar"). Buscar, adicionar, editar, apagar.
- **Atalhos de texto**: gatilho falado → texto pronto. Buscar, adicionar, editar, apagar.
- **Configurações** (página com seções):
  - *Geral*: microfone (lista), idioma da fala, iniciar com o Windows, mostrar a barra sempre.
  - *Atalhos*: mãos livres (aperta/aperta, padrão **Ctrl+Shift+Espaço**), segurar para falar (padrão
    desligado), cancelar (Esc), colar última (padrão desligado), copiar última (padrão desligado).
    Cada um com "gravar novo atalho"; recusa combinação só de modificadores ou já usada.
  - *Ditado*: tempo real liga/desliga, espaço no final, Enter automático, comando falado "pressione enter".
  - *Sons*: bipes liga/desliga, silenciar o áudio do PC enquanto dita (nova dependência `pycaw`, que
    entra no `requirements.txt`; restaura o volume ao terminar, mesmo se der erro).
  - *Motor*: GPU/CPU, modelo, status (dispositivo efetivo), botão "recarregar motor".
  - *Sobre*: versão, pasta dos dados, abrir logs.
- Salvar é imediato (sem botão "Salvar"); o motor aplica sem reiniciar, exceto troca de modelo/dispositivo
  (recarrega o modelo com aviso).

## 9. Tempo real (digitar enquanto fala)
- Enquanto grava, a cada ~0,8 s o motor transcreve o áudio acumulado desde o último ponto confirmado
  (com `word_timestamps`). Contexto (`initial_prompt`, limite ~224 tokens do Whisper): vocabulário do
  dicionário **+** o fim do texto confirmado, cortando o texto confirmado primeiro para caber.
- **Confirmação por concordância**: uma palavra só é digitada quando duas leituras seguidas concordam
  com ela no mesmo lugar (prefixo comum). Palavras confirmadas nunca são apagadas.
- Digitação via `SendInput` com caracteres Unicode (não usa a área de transferência no tempo real).
- Ao parar: transcrição final do trecho ainda não confirmado; digita só o que falta. Se o final
  divergir do que já foi digitado, **mantém o digitado** e acrescenta o restante (sem apagar).
- Falas longas: quando o áudio não confirmado passar de ~25 s, corta o buffer no fim da última palavra
  confirmada (timestamps) para não estourar a janela de 30 s do Whisper.
- Trocas e gatilhos podem ter **várias palavras**; comparação ignora maiúsculas, acentos não, e
  pontuação nas pontas. Para isso o tempo real **segura as últimas K palavras confirmadas** antes de
  digitar (K = tamanho, em palavras, da maior troca/gatilho; normalmente 1–3 → atraso pequeno).
  Assim a troca/gatilho é aplicada **antes** de digitar e nunca é preciso apagar nada.
- **O texto oficial é o que foi digitado**: é ele que vai para o histórico, `final.texto`, estatísticas,
  colar/copiar última.
- **Segurar para falar = sem tempo real**: com os modificadores apertados, letras digitadas viram atalhos
  de outros apps. Nesse modo o texto é colado no final (como no v1). Tempo real vale para "mãos livres".
- Enter: "Enter automático" aperta Enter depois do último trecho. O comando falado "pressione enter"
  só vale **no fim** do ditado (é tirado do texto e aperta Enter no final); no meio da fala é texto comum.
- Cancelar (Esc/X) no tempo real: para de digitar; o que já foi digitado fica (dá para Ctrl+Z).
- Tempo real desligado = comportamento do v1 (cola tudo no final pela área de transferência).
- Aviso: se ele trocar de janela no meio da fala, o resto vai para a janela nova (aceito).

## 10. Identidade visual — Espectro térmico
- Fundo base `#000004`; superfícies `#0B0912` e `#14111C`; bordas `#241E30`; texto `#F3EFE6`,
  texto secundário `#9A93A8`.
- Escala térmica (paleta "inferno"): `#000004 → #320A5E → #781C6D → #BB3754 → #ED6925 → #FBB61A → #FCFFA4`.
  Usos: onda de som (cor pelo volume), estado gravando (ponto `#FCFFA4`), destaques e botões primários
  (gradiente `#781C6D → #ED6925`), erro `#BB3754`.
- Fontes: **Chakra Petch** (títulos e interface) + **Red Hat Mono** (números, atalhos, cronômetro),
  arquivos locais (licença OFL) — sem internet.
- Ícones: Tabler (traço), locais. Cantos: pílula na barra; 6 px em botões/campos, 12 px nos cartões do Hub.
- Ícone do app: próprio, **`docs/icone/b-matriz-led.svg`** (escolhido pelo Gillezin em 2026-11-25:
  matriz 5×5 de LEDs em onda, cor térmica pela altura), exportado em `.ico` (16–256 px) e PNG.
- Proibido: roxo→azul, glassmorphism, emoji como ícone, qualquer asset do Wispr Flow.

## 11. Dados do usuário
- Passam para `%APPDATA%\GilleVoz\`: `config.json`, `historico\` (`AAAA-MM-DD.md` como hoje +
  `AAAA-MM-DD.jsonl` com texto, horário, duração, tempo, palavras — usado pelas estatísticas), `logs\`.
- Na primeira execução, se `%APPDATA%\GilleVoz` não existir, copia `config.json` e `historico\` da pasta do
  projeto (`C:\Mudo Tech\gillevoz`) — migração do v1. Histórico antigo em `.md` entra nas estatísticas
  só com contagem de palavras.
- `config.json` ganha: `tempo_real` (true), `trocas` ([]), `atalhos_texto` ([]), `atalho_push`,
  `atalho_colar_ultima`, `atalho_copiar_ultima`, `silenciar_pc` (false), `comando_enter` (true),
  `barra_borda` ("embaixo"|"esquerda"|"direita"), `barra_pos` (0..1 ao longo da borda).
  Somem `barra_x`/`barra_y` (convertidos na migração).

## 12. Instalador
- `instalador\gillevoz.iss` (Inno Setup) → `instalador\saida\GilleVoz-Setup.exe`.
- Instala em `%LOCALAPPDATA%\Programs\GilleVoz` (só o usuário, sem administrador):
  `app\` (Electron empacotado com electron-builder, alvo `dir`), `python\` (3.12 embutível),
  `motor\` (pacote `gillevoz` + `requirements.txt` sem pytest).
- O Python embutível **não traz pip**: o instalador leva `get-pip.py` e edita `python312._pth`
  (descomenta `import site` e acrescenta `..\motor`, porque o `._pth` ignora `PYTHONPATH` e a pasta atual).
- **v2 substitui o v1**: o instalador (e o primeiro uso) fecha o v1 se estiver rodando e remove o atalho
  antigo `GilleVoz.lnk` da pasta Inicializar, para os dois não brigarem pelo atalho de teclado.
  A pasta `C:\Mudo Tech\gillevoz` continua sendo a pasta de desenvolvimento.
- Pós-instalação: janela de progresso roda `pip install` e `--baixar-modelo` (reaproveita o cache do
  Hugging Face se já existir). Falhou → mensagem clara + botão "tentar de novo" (atalho "Reparar GilleVoz").
- Atalhos: Menu Iniciar; opcionais Área de Trabalho e iniciar com o Windows.
- Desinstalar: fecha o app e o motor, apaga a pasta do programa, **mantém** `%APPDATA%\GilleVoz`.

## 13. Critérios de pronto (testar de verdade)
1. Barra aparece embaixo no centro; arrastar e soltar gruda na borda e lembra ao reabrir.
2. Clicar na barra (gravar, parar, cancelar) e abrir/fechar o menu dela não tira o foco do Bloco de Notas
   (testar digitando depois). O Hub pode ter foco.
3. Tempo real: falar (ou tocar um .wav) com o Bloco de Notas em foco → palavras aparecem durante a fala;
   nenhum texto apagado; texto final completo.
4. Tempo real desligado: comportamento do v1, área de transferência restaurada.
5. Hub: estatísticas batem com o histórico; trocas e atalhos de texto funcionam num ditado.
6. Configurações salvas aplicam sem reiniciar (atalho novo funciona na hora).
7. Motor morto à força → Electron reinicia e a barra volta a ocioso.
8. Instalar do zero (pasta limpa) → abrir pelo Menu Iniciar → ditado funciona → desinstalar mantém os dados.
9. Testes automáticos do motor passando (atuais + concordância do tempo real, trocas, atalhos, protocolo).

## 14. Ordem de construção
1. Motor sem janela + protocolo + migração de dados (testável sozinho).
2. Electron: Flow Bar + bandeja + ligação com o motor.
3. Hub e Configurações.
4. Tempo real.
5. Instalador.

## 15. Fica a critério de quem constrói
Estrutura interna do `ui/` (React + Vite + TypeScript sugerido), nomes de componentes, detalhes de
espaçamento dentro da identidade, formato interno dos testes, intervalo exato do tempo real (0,6–1,0 s)
desde que o critério 3 passe.
