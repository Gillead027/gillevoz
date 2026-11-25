# Projeto GilleVoz
App de ditado por voz para o Windows do Gillezin (100% local). Pasta: C:\Mudo Tech\gillevoz
- Antes de começar: leia docs/SPEC.md.
- Quem escreve no cérebro (C:\Users\GILLEZIN\Desktop\GilleTech\cerebro-gillezin) é o Maestro. Os outros terminais mexem só no código deste projeto.

## Papéis no canvas
| Terminal | Papel | Foco |
|---|---|---|
| Maestro | Orquestrador (Claude Opus) | Planeja, distribui, revisa, testa, entrega |
| Claude 1 | Dev Core (Claude Opus) | Áudio, transcrição, atalho global, colagem |
| Claude 2 | Interface e setup (Claude Haiku) | Bandeja, indicador, config, histórico, instaladores |
| Codex | Revisão e testes (Codex) | Code review, testes, desempenho, bugs do Windows |

## Regras para todos os terminais (menos o Maestro)
- **Tarefas vêm do Maestro.** Faça só o que foi pedido. Ambíguo ou dependente de algo que não existe: pergunte ao Maestro.
- **Python 3.12 do projeto** (`.venv` criado com `py -V:Astral/CPython3.12.15`). Nunca o `python` 3.14 do sistema.
- **Não roube o foco da janela do usuário** e sempre restaure a área de transferência.
- **Ao terminar, reporte ao Maestro:** 1. o que foi feito (arquivos); 2. como testou e o resultado; 3. pendências.
- Nada de senha, token ou chave em arquivo. O app não usa internet depois de baixar o modelo.

## Papel do Codex
Você é o terminal **Codex** = **Revisão e testes**: revisa o código do Dev Core e da Interface, escreve testes automatizados onde der (config, histórico, colagem com área de transferência), mede o tempo de transcrição e procura bugs típicos do Windows (atalho global, foco, DLLs do CUDA).
