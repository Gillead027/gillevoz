# GilleVoz — arquitetura e contrato entre módulos (definido pelo Maestro)

Python: `.venv` criado com `py -V:3.12` (o `Astral/CPython3.12.15` registrado no py aponta para pasta apagada;
setup.bat tenta `-V:Astral/CPython3.12.15` e cai para `-V:3.12`). Nunca o 3.14.
Dependências: `requirements.txt` (dono: Maestro; peça mudanças a ele).

## Pacote `gillevoz/`
| Arquivo | Dono | Contrato |
|---|---|---|
| `config.py` | Claude 2 | `DEFAULTS: dict`; `load_config() -> dict` (cria `config.json` com defaults se não existir, mescla chaves faltantes, nunca apaga as do usuário); `save_config(cfg: dict)`; `ROOT: Path` (raiz do projeto); `CONFIG_PATH` |
| `log.py` | Claude 2 | `setup_logging() -> logging.Logger` (arquivo `logs/gillevoz.log` rotativo + console); logger nomeado `"gillevoz"` |
| `historico.py` | Claude 2 | `salvar(texto: str, duracao_audio: float, tempo_transcricao: float) -> Path` → append em `historico/AAAA-MM-DD.md` com horário; `pasta_historico() -> Path` |
| `indicator.py` | Claude 2 | `class Indicator`: `start()` (thread própria do Tk), `show(texto="● gravando")`, `set_text(texto)`, `hide()`, `stop()`. Thread-safe. Janela sem borda, topmost, **WS_EX_NOACTIVATE + WS_EX_TOOLWINDOW** (não rouba foco, não aparece na barra de tarefas), canto inferior central |
| `tray.py` | Claude 2 | `class Tray(on_toggle_ativo, on_abrir_historico, on_abrir_config, on_toggle_startup, on_sair, startup_ativo: callable->bool)`: `run_detached()`, `set_state("ocioso"|"gravando"|"transcrevendo"|"pausado")`, `notify(msg)`, `stop()`. Ícones gerados com Pillow (cores distintas por estado) |
| `startup.py` | Claude 2 | `ativo() -> bool`, `ativar()`, `desativar()` — atalho `GilleVoz.lnk` na pasta Inicializar do usuário apontando para `GilleVoz.vbs` |
| `cuda_dlls.py` | Claude 1 | `registrar_dlls_cuda()` — adiciona `bin` de nvidia-cublas/cudnn ao PATH e `os.add_dll_directory` |
| `audio.py` | Claude 1 | `class Recorder(samplerate=16000, device=None)`: `start()`, `stop() -> np.ndarray float32 mono`, `cancel()`; `bip(tipo="inicio"|"fim"|"erro")` não bloqueante; `carregar_wav(path) -> np.ndarray` 16 kHz mono |
| `transcriber.py` | Claude 1 | `class Transcriber(cfg)`: carrega 1x na init (cuda/float16 `large-v3-turbo`, fallback CPU `small`/int8 com aviso no log), aquece; `transcrever(audio) -> str`; atributo `device_efetivo` |
| `hotkey.py` | Claude 1 | atalho global (lib `keyboard`) modos `toggle` e `push`; Esc cancela só durante gravação (sem bloquear o Esc fora da gravação) |
| `paste.py` | Claude 1 | `colar(texto, metodo="clipboard"|"digitar", auto_enter=False, espera_ms=150)` — salva clipboard, cola, Ctrl+V, espera, restaura. Não aperta Enter se auto_enter=False |
| `app.py` + `__main__.py` | Claude 1 | Orquestra tudo. CLI: `python -m gillevoz` (app normal), `--testar-wav ARQ [--colar] [--atraso N]` (transcreve wav, loga tempos, salva no histórico, opcionalmente cola na janela em foco após N s), `--baixar-modelo` (baixa/carrega o modelo e sai) |

## Raiz
`setup.bat`, `iniciar.bat`, `GilleVoz.vbs`, `README.md` (Claude 2) · `tools/gerar_wav_teste.ps1` (Claude 1; voz Microsoft Maria pt-BR via System.Speech → wav 16 kHz mono) · `tests/` (Codex)

## config.json (chaves)
`atalho` ("ctrl+shift+space"), `modo` ("toggle"|"push"), `modelo` ("large-v3-turbo"), `dispositivo` ("cuda"), `compute_type` ("float16"), `modelo_cpu` ("small"), `idioma` ("pt"), `vocabulario` (lista do SPEC), `metodo_colagem` ("clipboard"|"digitar"), `auto_enter` (false), `microfone` (null = padrão), `bips` (true), `ativo` (true)

## Flow Bar (2026-11-25) — substitui o indicator.py
Barrinha flutuante sempre visível, estilo Flow Bar do Wispr Flow.

| Arquivo | Dono | Contrato |
|---|---|---|
| `flowbar.py` | Claude 2 | `class FlowBar(on_mic, on_parar, on_cancelar, on_config, on_sair, on_mover, posicao=None)`; `start()`, `stop()` (thread própria com loop de mensagens Win32, sem Tk); `set_state("ocioso"\|"gravando"\|"transcrevendo"\|"pausado")`; `set_level(nivel: float 0..1)` (chamado ~30x/s durante a gravação); `esconder_por(segundos)`; `mostrar()`. Todos os métodos públicos são thread-safe (fila + PostMessage). `on_mover(x, y)` é chamado ao SOLTAR o arraste (o app salva no config). `posicao=None` = centro inferior acima da barra de tarefas. |
| `audio.py` | Claude 1 | `Recorder.nivel() -> float` 0..1 (RMS do último bloco, normalizado p/ fala, com leve suavização) |
| `app.py` | Claude 1 | Troca Indicator por FlowBar; clique no mic = mesmo caminho do atalho (toggle); X = cancelar (igual Esc); thread a ~30 Hz envia `recorder.nivel()` à barra enquanto grava; `on_config` abre o config.json; `on_sair` = Sair da bandeja; salva `barra_x`/`barra_y` no config em `on_mover`; tray Pausar ⇒ `set_state("pausado")`. Atalho continua funcionando junto. |

Comportamento da barra
- Janela Win32 pura: `WS_POPUP`, ex-styles `WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST` (+ `WS_EX_LAYERED` se usar transparência). Tratar `WM_MOUSEACTIVATE` → `MA_NOACTIVATE`. Mostrar só com `SW_SHOWNOACTIVATE` / `SetWindowPos(SWP_NOACTIVATE)`. Fora da barra de tarefas e do Alt+Tab.
- Ocioso: pequena (ex.: ~48×24) com ícone de microfone. Gravando: expande (ex.: ~190×32) com [X cancelar] [onda animada pelo volume] [■ parar]. Transcrevendo: animação discreta (pontos/barra correndo). Pausado: mic esmaecido (clique não grava).
- Arrastar: segurar e mover (>4 px = arraste, senão é clique), sem ativar a janela (SetCapture). Mantém dentro da área visível dos monitores.
- Clique direito: menu Esconder por 1 hora · Configurações · Sair. O menu não pode deixar o foco fora da janela original: se usar TrackPopupMenu, guardar GetForegroundWindow antes e devolver o foco depois (ou fazer menu próprio sem ativação).
- Visual: fundo #0E0E0E, laranja #FF4D12 gravando, texto/ícones #E9E6E1, cantos RETOS, borda 1 px sutil (#2A2A2A). Desenho com double-buffer (sem piscar). Ícones: fonte "Segoe Fluent Icons"/"Segoe MDL2 Assets" (mic E720, stop E71A, X E711) ou desenhados.
- config.json: `barra_ativa` (true), `barra_x`, `barra_y` (null = padrão).
