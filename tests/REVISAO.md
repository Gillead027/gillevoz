# Revisão GilleVoz — 25/11/2026

Nenhum arquivo de produção foi editado. Python utilizado: `.venv\Scripts\python.exe`, versão 3.12.10.

## Bugs reproduzidos nos testes

| Gravidade | Local | Falha e correção sugerida |
|---|---|---|
| Alta | `gillevoz/paste.py:259-268` | Depois de colocar o ditado no clipboard, um erro em `enviar_ctrl_v`, leitura da sequência ou espera impede a restauração. Teste injeta erro e encontra `ditado` no lugar do original. Proteger toda a alteração com `try/finally`, incluindo falha parcial de `colocar_texto`; manter a proteção contra conteúdo novo de outro app. |
| Alta | `gillevoz/paste.py:169-171` | Arquivos copiados no Explorer usam CF_HDROP: pywin32 devolve tupla, ignorada pelo backup que aceita só bytes/str. Depois de ditar, a lista de arquivos desaparece do clipboard. Reproduzido com CF_HDROP real. Serializar DROPFILES ou copiar o HGLOBAL original; não apagar conteúdo que não foi possível salvar. |
| Média | `gillevoz/audio.py:48` | Se `InputStream.start()` falhar, o stream criado não é fechado, e a próxima tentativa sobrescreve a referência. Fechar e limpar `_stream` na exceção antes de propagar o erro. |
| Alta | `gillevoz/audio.py:55-59` | Se `s.stop()` falhar, `s.close()` nunca executa, embora `_stream` já tenha sido descartado. O recurso pode continuar aberto após falha do dispositivo. Colocar `close()` em `finally`, com tratamento separado para suas falhas. |
| Média | `gillevoz/app.py:162-163,186` | `show()` ocorre fora do lock: cancelamento concorrente (fallback de Esc, push ou pausa pela bandeja) pode executar `hide()` antes desse `show()`, deixando a pílula gravando enquanto o estado já está ocioso. Reproduzido com escalonamento determinístico, sem janela real. Enfileirar estado e indicador sob a mesma sincronização, ou usar identificador de sessão. |

## Outros problemas identificados por leitura

| Gravidade | Local | Evidência e correção sugerida |
|---|---|---|
| Alta | `gillevoz/app.py:177-178,259-272` | A thread de transcrição/colagem é daemon e não é aguardada no encerramento. Sair durante a espera de colagem pode terminar o processo antes de restaurar o clipboard; sair durante transcrição pode perder o texto ou permitir colagem depois da solicitação de saída. Guardar a thread, impedir nova colagem após `_sair`, e aguardar o trecho crítico de restauração antes de encerrar. Não foi provocado no desktop para preservar o clipboard. |
| Média | `gillevoz/hotkey.py:187-188,222-223` | No fallback `keyboard`, o callback é registrado em key-down, sem trava até key-up. A repetição automática de uma tecla mantida aciona toggle novamente e encerra a gravação sem uma segunda pressão física. O caminho nativo evita isso com MOD_NOREPEAT. Aplicar trava down/up também no fallback. Não foi instalado hook real na sessão do usuário. |

## Foco e Esc: limite da revisão

`indicator.py:92-105`: `tk.Tk()` é criado e `update_idletasks()` executa antes de aplicar WS_EX_NOACTIVATE e esconder a janela. Há risco de primeira exibição/ativação antes dos estilos. Aplicar `withdraw()` imediatamente e validar a criação oculta antes de mostrar com SW_SHOWNOACTIVATE. Este item é risco de revisão, não falha de foco observada: não abri a UI para não roubar o foco do usuário.

O Esc nativo é registrado com modificadores zero (`hotkey.py:162`). Não cobre Ctrl/Alt/Win/Shift+Esc enquanto o usuário ainda segura o atalho. Falha no registro de Esc apenas gera warning; não aciona fallback. Validar essas condições no teste manual do produto. Não houve teste físico de Esc nem desconexão física do microfone.

## Testes

Comando: `.venv\Scripts\python.exe -m pytest -q`

Resultado final: **19 passaram, 5 falharam em 0,47 s**. Os cinco testes vermelhos reproduzem os cinco bugs da primeira tabela; não foram mascarados com xfail.

Arquivos: `tests/test_config.py`, `test_historico.py`, `test_paste.py`, `test_audio.py`, `test_app.py`.

- Config: criação, mesclagem sem perder valores, cópia de JSON inválido e preservação do arquivo anterior se a troca atômica falha.
- Histórico: acentos, várias linhas, append, tempos e separação por dia.
- Clipboard real: texto disponível no instante de Ctrl+V simulado, restauração, conteúdo novo de outro app, ausência de Enter automático e Enter explícito, espaço final em clipboard e digitação, erro e CF_HDROP. Nenhuma tecla enviada, nenhuma janela aberta. Fixture restaura o clipboard original em `finally`; pula os testes se o clipboard original do usuário contiver arquivos que o backup atual não consegue preservar.
- `espaco_final` já estava presente e integrado no app/config ao concluir. Passou com false, true e texto já terminado em espaço ou quebra de linha.
- Cinco minutos simulados por callbacks: 4.800.000 amostras float32, 19.200.000 bytes (18,31 MiB) de payload, íntegros após stop. Concatenação exige temporariamente aproximadamente outro payload, além dos objetos/blocos e do modelo. Não é medição do RSS nem captura real de cinco minutos. Não há limite curto; memória cresce linearmente para gravações indefinidas.
- Mutex real: primeira chamada criou handle válido, segunda detectou instância existente. Não iniciei o app completo.
- CUDA real: DLLs de cuBLAS, cuDNN e NVRTC registradas; três processos completaram na GPU. Fallback CPU foi revisado, sem provocar falha real de CUDA.

## Desempenho

Comando executado três vezes, sequencialmente: `.venv\Scripts\python.exe -m gillevoz --testar-wav testes_audio\fala20s.wav`.

| Execução | Áudio | Carga/aquecimento | Transcrição | Dispositivo/modelo |
|---|---:|---:|---:|---|
| 1 | 19,3 s | 2,7 s | 0,70 s | CUDA / large-v3-turbo / float16 |
| 2 | 19,3 s | 2,5 s | 0,59 s | CUDA / large-v3-turbo / float16 |
| 3 | 19,3 s | 2,4 s | 0,58 s | CUDA / large-v3-turbo / float16 |

Média dos tempos de transcrição arredondados: **0,62 s**, abaixo da meta de 3 s nas três rodadas. Modelo carregado novamente em cada processo; estes tempos de transcrição excluem carga/aquecimento. O CLI salvou automaticamente as três transcrições no histórico e escreveu logs, conforme sua implementação. Não usei `--colar`.

Pendências: donos corrigirem os bugs e rodarem novamente a suíte; validar foco, Esc físico, microfone desconectado e captura/transcrição real longa. Maestro é responsável por atualizar a nota no cérebro.
