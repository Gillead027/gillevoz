# GilleVoz v2 — arquitetura

> Como o código está montado hoje (branch `v2`). O "porquê" das decisões está em [DESENHO-V2.md](DESENHO-V2.md)
> e [REFERENCIAS-UI.md](REFERENCIAS-UI.md). A arquitetura do v1 (Python com bandeja e barra Win32) foi
> substituída por esta; o v1 continua descrito em [SPEC.md](SPEC.md).

## Visão geral
```
Electron (ui/)  ── inicia e vigia ──►  Motor Python (gillevoz/, modo --motor)
  Flow Bar (janela sem foco)            atalhos globais, gravação, Whisper (GPU),
  Menu da barra (janela sem foco)       tempo real, digitação/colagem, histórico, config
  Hub (janela normal)         ◄── JSON ──
  Bandeja do Windows              uma linha por mensagem, stdin/stdout
```
- O **Electron é o dono**: abre o motor (`pythonw -m gillevoz --motor`), reinicia se cair (até 3 vezes em 60 s,
  depois mostra erro). Fechar o Electron encerra o motor.
- O **motor não tem janela**. O stdout dele é só protocolo: no `--motor`, o fd 1 e o handle do Windows são
  desviados para o stderr (log) e o protocolo escreve numa cópia do stdout original.
- O atalho global fica no Python (`RegisterHotKey` + `GetAsyncKeyState` para detectar soltar a tecla).
- Outros modos do mesmo pacote: `python -m gillevoz --testar-wav ARQ [--colar] [--atraso N]` e `--baixar-modelo`
  (usado pelo instalador).

## Protocolo motor ⇄ interface
Uma mensagem JSON por linha, UTF-8. Código: `gillevoz/protocolo.py` (motor) e `ui/src/shared/protocolo.ts` (tipos).

Motor → interface:
| `tipo` | campos | quando |
|---|---|---|
| `pronto` | `dispositivo` (`cuda`/`cpu`), `modelo` | modelo carregado (de novo após trocar modelo) |
| `estado` | `estado` (`ocioso`/`gravando`/`transcrevendo`/`pausado`/`erro`), `msg?` | toda mudança |
| `nivel` | `valor` 0..1 | ~30x/s gravando |
| `parcial` | `confirmado` (texto já digitado) | tempo real, a cada trecho digitado |
| `final` | `texto`, `duracao_audio`, `tempo_transcricao`, `palavras` | ao terminar |
| `historico` | `dia` | histórico mudou (o Hub recarrega) |
| `config` | `cfg` | depois de salvar a configuração |
| `log` | `nivel`, `msg` | erros/avisos para mostrar |

Interface → motor: `iniciar`, `parar`, `cancelar`, `pausar`, `retomar`, `ler_config`, `salvar_config {cfg}`,
`colar_ultima`, `copiar_ultima`, `listar_historico {dia?}`, `estatisticas`, `listar_microfones`, `sair`.
Os que consultam dados (`ler_config`, `listar_historico`, `estatisticas`, `listar_microfones`) aceitam `id` e
respondem com `<tipo>_resposta` carregando o mesmo `id`. Linha inválida é ignorada e vai para o log.
Segurança no Electron: as janelas só podem mandar os comandos de `COMANDOS_DAS_JANELAS` (o `sair` é só do main).

## Módulos do motor (`gillevoz/`)
| Módulo | Contrato (uma linha) |
|---|---|
| `config.py` | `load_config()`/`save_config()` do `config.json` em `PASTA_DADOS`; `DEFAULTS`; `limpar()` corrige tipos; `migrar_v1()` copia config e histórico do v1 na primeira vez |
| `historico.py` | `salvar()` grava `AAAA-MM-DD.md` (leitura humana) + `.jsonl` (dados); `listar(dia)`, `dias()`, `estatisticas()` |
| `texto.py` | Funções puras: `aplicar_trocas`, `achar_gatilho` (atalhos de texto), `maior_k`, `tirar_comando_enter` ("pressione enter" no fim) |
| `tempo_real.py` | `Concordancia` (palavra só vale quando duas leituras seguidas concordam) e `Digitador` (segura as últimas K palavras, aplica trocas/gatilhos e só então digita) |
| `transcriber.py` | `Transcriber`: faster-whisper (GPU, cai para CPU), `transcrever`, `transcrever_palavras` (com tempos), `montar_prompt`, `recarregar` |
| `audio.py` | `Recorder` (16 kHz mono, `nivel()`, `amostras()`), `RecorderWav` (simula microfone com um WAV), `bip()`, `carregar_wav()` |
| `paste.py` | Entrega do texto: `digitar` (SendInput), `colar` (área de transferência com backup/restauração), `GuardaJanela`, guarda de modificadores, `enviar_enter`, `apagar` |
| `hotkey.py` | `Hotkey` (mãos livres/segurar) e `AtalhoAcao` (colar/copiar última); `parse_atalho`, `validar_atalho` |
| `som.py` | `Silenciador`: silencia o áudio do PC enquanto grava (pycaw) e restaura; nunca levanta exceção |
| `startup.py` | `remover_v1()`: apaga o atalho antigo `GilleVoz.lnk` da pasta Inicializar. (`ativar/desativar` são do v1; no v2 "iniciar com o Windows" é feito pelo Electron) |
| `protocolo.py` | `Canal.enviar()` (thread-safe) e `ler()` (comandos do stdin) |
| `motor.py` | `Motor`: junta tudo, trata os comandos, mantém o estado, grava, roda o tempo real e entrega o texto |
| `app.py` | Resto do v1 (`testar_wav`, `baixar_modelo`); o app em si agora é `motor.py` + Electron |
| `log.py`, `cuda_dlls.py`, `__main__.py` | log rotativo; DLLs da NVIDIA no PATH; entrada (`--motor`, `--testar-wav`, `--baixar-modelo`) |

## Tempo real (digitar enquanto fala)
**Quando vale:** só no modo "mãos livres". No "segurar para falar" (modificadores apertados) o texto é colado no
final, porque letras digitadas virariam atalhos de outros apps. Com `tempo_real` desligado = comportamento do v1.

**Fluxo:** a cada ~0,8 s o motor transcreve o áudio ainda não confirmado (com timestamps de palavra) → `Concordancia`
confirma palavras → `Digitador` segura as últimas K (para trocas/atalhos de texto de várias palavras) e libera o resto →
`paste.digitar`. O texto digitado nunca é apagado; o que foi digitado é o texto oficial (histórico, `final`, estatísticas).
Ao parar, a transcrição final digita só o que faltou. Áudio não confirmado acima de ~25 s é cortado na última palavra
confirmada.

**Como digita (`paste.digitar`):**
- **Tecla a tecla** com `SendInput` Unicode: pausa de **15 ms** depois de letra/número e **80 ms** depois de
  espaço/pontuação (inclusive no fim do trecho). Mandar a palavra inteira de uma vez foi medido e errava 20–50% das
  frases no Bloco de Notas do Windows 11; tecla a tecla acertou 33/33 parado e 8/8 com a CPU ocupada.
- **Guarda de modificadores:** antes de cada tecla espera Ctrl/Alt/Shift/Win serem soltos. No tempo real nunca
  solta por conta própria; na entrega final solta depois de 0,6 s.
- **Guarda de janela (`GuardaJanela`):** antes de cada tecla confere que há janela em foco, que não é interface do
  Windows (Iniciar, Alt+Tab...) e que não acabou de mudar (0,15 s). Espera no máximo 3 s, **uma vez por entrega**
  e por janela (depois digita mesmo assim, para não travar por minutos).
- **Trava única (`_lock_digitar`):** só uma thread entrega texto por vez (trechos, final, espaço, Enter, colar última).
- **Interrompível:** cancelar/parar sinaliza um evento; a digitação para antes da próxima tecla e o que sobrou é
  entregue pelo final (ou descartado no cancelar).
- **Quebra de linha:** digitar `\n` apertaria Enter (e mandaria a mensagem em chats e terminais). Trecho com
  quebra de linha é **colado** pela área de transferência.

## Lado Electron (`ui/`)
React + Vite + TypeScript (electron-vite), animações com Motion, fontes e ícones locais.

**Processo principal (`ui/src/main/`)**
| Arquivo | Função |
|---|---|
| `index.ts` | Inicia tudo, instância única, escolhe perfil e pasta de dados, liga motor ↔ janelas (IPC) |
| `motor.ts` | `MotorProcess`: abre o Python (dev: `.venv\Scripts\pythonw.exe`; instalado: `python\` + `motor\`), lê/escreve JSON, `pedir()` com `id` e limite de 10 s, reinicia ao cair, `sair` com espera |
| `janelas/barra.ts` | Janela da Flow Bar: transparente, sem foco (`focusable:false`), sempre no topo, 360×120, clique atravessa fora da pílula |
| `janelas/menu.ts` | Menu do clique direito em HTML, também sem foco (menu nativo roubaria o foco); fecha quando o mouse sai por 600 ms |
| `janelas/hub.ts` | Hub 960×640 sem moldura, pode ter foco; fechar só esconde; "iniciar com o Windows" (chave `Run`, valor `GilleVoz`) |
| `arraste.ts` | Máquina de estados do arraste da barra (segue o cursor; sem sinal por 3 s, termina sozinho) |
| `posicao.ts` | Posição da barra na área útil do monitor; gruda em esquerda / embaixo / direita (`barra_borda`, `barra_pos`) |
| `perfil.ts` | Pasta do perfil do Chromium: instalado `%LOCALAPPDATA%\GilleVoz`, dev `%LOCALAPPDATA%\GilleVoz-dev` |
| `bandeja.ts` | Ícone da bandeja (matriz 5×5 de LEDs) com a cor do estado |

**Preload (`ui/src/preload/`)** expõe `window.api` (contexto isolado, sem Node): `enviar(cmd)`, `pedir(tipo, dados)`,
`aoEvento(cb)`, `janela.*` (situação, arrastar, abrir menu/Hub, reiniciar motor...) e `hub.*` (info, janela, abrir
pasta, iniciar com o Windows, recarregar motor, copiar). Tipos em `index.d.ts`; canais em `shared/`.

**Renderers (`ui/src/renderer/`)**: `barra/` (pílula, onda térmica "termômetro de LED", estados), `menu/` (menu da barra),
`hub/` (Início, Dicionário, Atalhos de texto, Configurações; salva só as chaves alteradas, uma por vez).
`tema.css` tem as cores do Espectro térmico.

## Onde ficam os dados
| O quê | Onde |
|---|---|
| Config, histórico (`.md` + `.jsonl`), logs | `%APPDATA%\GilleVoz` (ou a pasta em `GILLEVOZ_DADOS`) |
| Perfil do Chromium (Electron) instalado | `%LOCALAPPDATA%\GilleVoz` (o desinstalador apaga) |
| Perfil do Chromium em desenvolvimento | `%LOCALAPPDATA%\GilleVoz-dev` |
| Programa instalado | `%LOCALAPPDATA%\Programs\GilleVoz` |

Variáveis de ambiente de desenvolvimento/teste: `GILLEVOZ_DADOS` (outra pasta de dados) e `GILLEVOZ_WAV_SIMULADO`
(caminho de um WAV: o motor usa ele como microfone, para testar o tempo real sem falar).
Migração: na primeira execução, se `%APPDATA%\GilleVoz` não existir, copia `config.json` e `historico\` de
`C:\Mudo Tech\gillevoz` (v1).

## Instalador (`instalador/`)
| Arquivo | Função |
|---|---|
| `montar.ps1` | Compila a interface e empacota (`ui\dist\win-unpacked`), baixa para `cache\` o Python 3.12 embutível (SHA-256 conferido) e o `get-pip.py`, monta `cache\motor\`, roda o Inno Setup |
| `gillevoz.iss` | Define o `GilleVoz-Setup.exe` (saída em `instalador\saida\`): atalhos, tarefa "iniciar com o Windows", desinstalação |
| `pos_instalacao.ps1` | Instala o pip, as bibliotecas do motor e o modelo de voz; também é o atalho "Reparar GilleVoz" |
| `encerrar.ps1` | Fecha o app e o motor antes de atualizar/desinstalar |
| `gerar_icone.cjs`, `icone.ico` | Geram/guardam o ícone (de `docs/icone/b-matriz-led.svg`) |

Estrutura instalada em `%LOCALAPPDATA%\Programs\GilleVoz`: `app\` (Electron, `GilleVoz.exe`), `python\` (3.12 embutido,
com `python312._pth` ajustado), `motor\` (pacote `gillevoz` + `requirements.txt`), `pos_instalacao.ps1`, `encerrar.ps1`.
Desinstalar apaga isso e o perfil em `%LOCALAPPDATA%\GilleVoz`, mas **mantém** `%APPDATA%\GilleVoz`.

## Testes
- Python: `tests/` (pytest; marcador `gpu` para o que precisa de GPU/modelo).
- Interface: testes `*.test.ts` ao lado do código (vitest).
- Digitação em janelas reais: `tools/teste_digitacao.py` (ver README).
