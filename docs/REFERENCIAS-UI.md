# Referências de interface — o que entra no GilleVoz

> 2026-11-25. Estudo dos 15 sites enviados pelo Gillezin. Critério: ferramenta de **trabalho**, bonita,
> limpa, organizada, 100% funcional, **sem cara de IA e sem efeito de vitrine**.
> Tudo é adaptado à identidade **Espectro térmico** ([DESENHO-V2.md](DESENHO-V2.md) §10).

## 1. Os sites, em uma linha cada
| Site | O que é | Código pode ser usado? | Veredito |
|---|---|---|---|
| reactbits.dev | componentes animados (React) | Sim: MIT + Commons Clause (usar em app próprio ok; não revender os componentes; manter o aviso) | **Usar ideias + código pontual** (Voice Pill, Glide Select, Swipe Toast) |
| cult-ui.com | componentes shadcn com Motion | Sim: MIT | **Usar** (Dynamic Island como base da barra, Halo Switch/Toast como referência) |
| microkit.co | micro-interações | Sim: MIT | **Usar** (Glide Pill Tabs, Progress Ring Check, Hold to Delete, Count Up) — tempos exatos abaixo |
| spell.sh | componentes shadcn | Sim: MIT | Kbd e spinner como referência; o resto é decorativo |
| bencho.dev | blocos de micro-interação | grátis = MIT; Dynamic Island é Pro | Voice note (onda de barras) como referência; Pro não |
| skiper-ui.com | componentes shadcn | grátis exige crédito; Pro pago | **Só referência** (Dynamic Island, Expandable tabs) |
| 21st.dev | registro da comunidade | licença por autor, limite de cópias | **Só referência** (rail sidebar, ícones animados) |
| uiverse.io | elementos CSS da comunidade | MIT | descartado: estética chamativa demais para trabalho |
| originkit.dev | efeitos 3D/WebGL de site | grátis | descartado: efeito de vitrine, pesado |
| styles.refero.design | "DNA" de estilos de sites reais | sem licença clara | **Só referência** de disciplina (Linear, Raycast) |
| inspora.design | galeria de inspiração | obras dos criadores | **Só referência** (visualizador de voz em matriz de LED) |
| 60fps.design | gravações de interações de apps | pode recriar o movimento, não a marca | **Só referência** (pulsos de microfone, onda) |
| details.so | snippets pagos | pago | não usado |
| curated.design | galeria de sites/seções | Pro pago | não usado (seções de landing page) |
| getlayers.ai | prompts de sites | prompts não podem ser copiados | não usado (sites de marketing) |

## 2. O que entra, peça por peça

### Flow Bar
- **Morfose tipo "ilha"** (ideia: Dynamic Island do cult-ui, MIT): uma única pílula que muda de tamanho
  entre os estados com `layout` do Motion, mola 600/35; o conteúdo interno entra/sai com 300/28 e
  leve desfoque de 4 px → 0. Nada pisca: o conteúdo antigo sai antes do novo entrar (`AnimatePresence mode="popLayout"`).
- **Gravando = "termômetro de LED"** (assinatura do GilleVoz; ideias: Voice Pill do React Bits + visualizador
  em matriz de LED do Inspora): 14 colunas, cada uma com até 5 "LEDs" quadrados de 3 px com 1 px de vão.
  O volume acende LEDs de baixo para cima; cada LED aceso tem a cor da escala térmica **pela altura**
  (baixo `#781C6D` → topo `#FCFFA4`). LED apagado = `#14111C`. Cronômetro em Red Hat Mono com números rolando.
- **Pulso do microfone** (ideia: 60fps, "hold mic pulse"): ao começar a gravar, um anel `#ED6925` sai do
  botão e some em 420 ms (escala 1→1,6, opacidade 0,5→0, `easeOut`).
- **Processando → pronto** (Progress Ring Check do MicroKit, MIT): arco girando linear 1100 ms; ao terminar,
  o arco vira um ✓ desenhado em 240 ms `cubic-bezier(.23,1,.32,1)` após 120 ms; fica 600 ms e a barra encolhe.
- **Erro**: pílula treme 2× (±3 px, 240 ms) com borda `#BB3754`.

### Menu da barra e selects
- **Destaque que desliza** entre as linhas (Glide Select do React Bits / Glide Pill Tabs do MicroKit):
  fundo `#14111C` que se move com `transform` 300 ms `cubic-bezier(.32,.72,0,1)`; aparece com fade 180 ms.

### Hub — estrutura e acabamento
- **Disciplina tipo Linear/Raycast** (Refero): bordas finas de 1 px em vez de sombras, densidade compacta
  (texto 13–14 px), raio 6 px em botões/campos, 12 px em cartões, pílula só onde é pílula,
  **um** destaque de cor por tela (o botão primário com o gradiente térmico).
- **Menu lateral** com marcador que desliza (Glide Pill Tabs, MIT): 380 ms `cubic-bezier(.32,.72,0,1)`;
  realce de hover desliza em 300 ms; cor do texto muda em 280 ms `cubic-bezier(.4,0,.2,1)`.
- **Teclas de atalho como "keycaps"** (Raycast via Refero / Kbd do Spell): tecla em `#14111C`, borda 1 px
  `#241E30`, brilho interno no topo `inset 0 1px 0 rgba(255,255,255,.06)`, sombra interna embaixo
  `inset 0 -1px 0 rgba(0,0,0,.4)`, Red Hat Mono 12 px. Ao gravar um atalho novo, cada tecla "afunda" 1 px quando apertada.
- **Números do Início que rolam** (Count Up do MicroKit, MIT): ao abrir, contam até o valor em 700 ms
  `cubic-bezier(.16,1,.3,1)`.
- **Apagar segurando** (Hold to Delete do MicroKit, MIT) em itens do histórico, dicionário e atalhos:
  segurar 1600 ms preenche o botão (clip-path linear); soltar volta em 500 ms `cubic-bezier(.16,1,.3,1)`;
  apertar reduz para 0,97; lixeira vira ✓. Evita janela de confirmação.
- **Interruptores** (ideia: Squish Switch do React Bits / Halo Switch do cult-ui): bolinha estica 4 px
  enquanto pressionada e volta com mola 600/35; trilho ligado = gradiente térmico.
- **Avisos (toasts)** (Swipe Toast do React Bits / Halo Toast do cult-ui): empilham no canto inferior
  direito do Hub, entram subindo 8 px + fade 200 ms, somem sozinhos em 3 s ou arrastando para o lado.
- **Busca** nas listas: campo que ganha borda `#781C6D` e um brilho sutil ao focar (Focus Input, MicroKit).

### Ícones
- Interface: **Tabler** (traço), 1,5 px, 16/20 px. Só o ícone do microfone tem animação no hover
  (ideia: ícones animados do 21st.dev): as "ondas" do mic aparecem em sequência, 60 ms entre elas.
- **Ícone do app: próprio** (ver `docs/icone/`).

## 3. O que fica de fora (e por quê)
Fundos WebGL, partículas, raios de luz, "liquid glass", vidro fosco, 3D, cursor com rastro, brilho que
segue o mouse, confete, texto que explode: tudo isso é efeito de vitrine, distrai no trabalho e dá cara de
"site feito por IA".

## 4. Licenças
Código copiado/adaptado só de **cult-ui (MIT)**, **MicroKit (MIT)**, **Spell (MIT)** e **React Bits
(MIT + Commons Clause)**. Cada arquivo adaptado leva um comentário com a origem, e
`ui/AVISOS-DE-TERCEIROS.md` guarda os avisos de licença. Skiper, 21st, Details, Curated, Getlayers,
Refero, Inspora e 60fps: só ideias, nenhum código ou arquivo.
