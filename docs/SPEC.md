# GilleVoz — especificação

> **Nota (2026-11-26):** este documento descreve o **v1** (Python com bandeja e barra Win32) e foi mantido como histórico.
> O **v2** (Electron + motor Python, tempo real, Hub, instalador) é descrito em [DESENHO-V2.md](DESENHO-V2.md)
> (com [REFERENCIAS-UI.md](REFERENCIAS-UI.md)); como o código está montado hoje: [ARQUITETURA.md](ARQUITETURA.md).

App de ditado por voz para o Windows do Gillezin, no estilo Wispr Flow, rodando 100% no PC. Uso principal: falar com os agentes no Maestri (terminais Claude Code e Codex) em vez de digitar, inclusive no meio de um texto já digitado.

## Máquina
- Windows 11, GPU NVIDIA GeForce RTX 4060 (8 GB).
- `python` padrão é 3.14 — NÃO usar (faltam wheels de ctranslate2). Usar Python 3.12: `py -V:Astral/CPython3.12.15` (já instalado).
- Criar o venv dentro do projeto: `py -V:Astral/CPython3.12.15 -m venv .venv`.

## Como funciona (fluxo)
1. O app fica rodando em segundo plano, com ícone na bandeja do Windows.
2. Atalho global **Ctrl+Alt+Espaço** (configurável): aperta uma vez = começa a gravar; aperta de novo = para.
   - Modo opcional push-to-talk (segurar o atalho), escolhido no config.
3. Enquanto grava: um indicador pequeno e discreto aparece na tela (ex.: pílula "● gravando" no canto inferior central, sempre no topo, sem roubar o foco) e toca um bip curto no início e no fim.
4. Ao parar: transcreve localmente com **faster-whisper** em português e **cola o texto onde o cursor estiver**, na janela que estava em foco (não pode roubar o foco).
5. Colagem: salva o conteúdo atual da área de transferência, coloca o texto, envia Ctrl+V, espera ~150 ms e restaura a área de transferência original. Fallback configurável: digitar caractere por caractere.
6. NÃO aperta Enter sozinho (o Gillezin revisa antes de enviar). Opção no config: `auto_enter: false`.
7. Esc durante a gravação cancela sem colar nada.

## Transcrição
- faster-whisper, idioma fixo `pt`.
- Modelo padrão `large-v3-turbo` na GPU (`device="cuda"`, `compute_type="float16"`). Se CUDA falhar, cai automaticamente para CPU com modelo `small` e `int8`, e avisa no log.
- CUDA no Windows: instalar `nvidia-cublas-cu12` e `nvidia-cudnn-cu12` via pip e adicionar as pastas `bin` desses pacotes ao PATH/`os.add_dll_directory` antes de carregar o modelo.
- Carregar o modelo uma vez só, na inicialização (pré-aquecido), para a resposta ser rápida.
- `vad_filter=True` para cortar silêncio.
- `initial_prompt` com o vocabulário do Gillezin (lista em `config.json`), para acertar nomes próprios. Vocabulário inicial: Maestri, Maestro, Claude, Claude Code, Codex, Opus, Haiku, Gillezin, Cariacica, capixaba, 027, Batalha do STN, Delux MC, Vercel, Supabase, Next.js, Tailwind, deploy, commit, prompt, workspace, front-end, back-end, Dito Feito, Ponte Cultural, NÃO MORRO FÁLIDO, OUTFIT, D.A.P.A.
- Gravação: 16 kHz mono via `sounddevice`. Sem limite curto de tempo (aceitar pelo menos 5 minutos de fala).

## Bandeja (pystray)
- Ícone muda de cor: ocioso / gravando / transcrevendo.
- Menu: Ativar/Pausar · Abrir histórico · Abrir config · Iniciar com o Windows (liga/desliga) · Sair.

## Arquivos
- `config.json` — atalho, modo (toggle/push), modelo, dispositivo, vocabulário, método de colagem, auto_enter, microfone (padrão do sistema).
- `historico/AAAA-MM-DD.md` — toda transcrição salva com horário, para nunca perder uma ideia.
- `logs/gillevoz.log` — erros e tempos (duração do áudio x tempo de transcrição).
- `iniciar.bat` (com console, para debug) e `GilleVoz.vbs` (sem janela, para uso diário).
- "Iniciar com o Windows": atalho na pasta Inicializar do usuário apontando para o `.vbs`.

## Bibliotecas sugeridas
faster-whisper, sounddevice, numpy, keyboard (atalho global), pyperclip, pystray, Pillow, nvidia-cublas-cu12, nvidia-cudnn-cu12. Indicador de gravação: janela Win32 pura via ctypes (decisão de 2026-11-25: o Tkinter roubava o foco por alguns ms ao criar a janela).

## Critérios de pronto (testar de verdade antes de entregar)
1. Instala do zero com um comando (`setup.bat`) e abre com `GilleVoz.vbs`.
2. Bloco de Notas: ditar uma frase com acentos ("ação, coração, não morro fálido") → texto correto colado.
3. Ditar NO MEIO de um texto já digitado → o texto entra na posição do cursor, sem apagar nada.
4. Terminal do Maestri (Claude Code): ditar → texto aparece na caixa de prompt, sem enviar sozinho.
5. Área de transferência original é restaurada depois de colar.
6. Tempo: 20 s de fala transcritos em menos de 3 s na GPU (registrar no log).
7. Esc cancela a gravação.
8. Fechar e abrir de novo mantém o config.
