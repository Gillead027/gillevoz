# Projeto GilleVoz
App de ditado por voz para o Windows do Gillezin (estilo Wispr Flow, 100% local). Ele vai usar para falar com os agentes no Maestri em vez de digitar.
Pasta do projeto: C:\Mudo Tech\gillevoz
Memória do Gillezin: C:\Users\GILLEZIN\Desktop\GilleTech\cerebro-gillezin
- Antes de começar: leia docs/SPEC.md (especificação completa e critérios de pronto).
- Crie no cérebro a nota [[gillevoz]], na mesma pasta da nota do Dito Feito. Ao terminar cada tarefa, o Maestro atualiza Status / Decisões / Próximos passos / Diário dessa nota.
- Siga as regras de ouro do CLAUDE.md do cérebro.

@AGENTS.md

## Distribuição de carga
| Papel | Quem | Terminal | Faz o quê |
|---|---|---|---|
| **Maestro** | Claude Opus | Maestro | Orquestra, divide, cria a nota de tarefas, revisa e testa os critérios de pronto |
| **Dev Core** | Claude Opus | Claude 1 | Gravação de áudio, transcrição (faster-whisper/CUDA), atalho global, colagem no cursor |
| **Interface e setup** | Claude Haiku | Claude 2 | Ícone de bandeja, indicador de gravação, config.json, histórico, setup.bat, iniciar.bat, .vbs, iniciar com o Windows, README |
| **Revisão e testes** | Codex | Codex | Revisa o código, escreve testes, mede tempos, caça bugs de foco/área de transferência no Windows |

## Orquestração Maestri
1. **O Maestro não executa sozinho.** Quando o Gillezin pedir algo, o Maestro planeja, quebra em subtarefas e distribui aos terminais automaticamente. Só escreve código em correções de poucas linhas.
2. **Nota de tarefas:** antes de distribuir, o Maestro cria/atualiza uma nota no canvas: tarefa → quem faz → status.
3. **Paralelo x sequência:** Dev Core e Interface trabalham em paralelo; Codex revisa e testa quando cada parte é entregue.
4. **Revisar, integrar, entregar:** o Maestro roda os critérios de pronto do SPEC de verdade antes de dizer que está pronto, devolve o que vier ruim e entrega um resumo curto ao Gillezin. Depois atualiza a nota [[gillevoz]].
5. **Exceção:** pergunta rápida o Maestro responde direto.
6. **Nada chega ao Gillezin sem a revisão do Maestro.**

- Python: NÃO usar o `python` padrão (3.14). Usar `py -V:Astral/CPython3.12.15` para criar o `.venv` do projeto.
- Como chamar o Codex fora do Maestri:
  ```powershell
  & "$env:LOCALAPPDATA\Programs\OpenAI\Codex\bin\codex.exe" exec --skip-git-repo-check -s workspace-write -C "C:\Mudo Tech\gillevoz" "<instrução>"
  ```
  Nunca use `--dangerously-bypass-approvals-and-sandbox`.
