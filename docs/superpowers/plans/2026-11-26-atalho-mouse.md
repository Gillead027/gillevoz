# Atalho com botão lateral do mouse — plano curto

**Pedido do Gillezin (2026-11-26):** poder usar o botão lateral do mouse como atalho, principalmente no "segurar para falar". Hoje o gravador de atalho só aceita teclado.

## Decisões
- Botões aceitos: **laterais** `mouse4` (XBUTTON1, "Voltar") e `mouse5` (XBUTTON2, "Avançar"), sozinhos ou com modificadores (`ctrl+mouse4`). Botão esquerdo/direito/meio: recusados (atrapalhariam o uso normal).
- Vale para **todos** os atalhos (`atalho`, `atalho_push`, `atalho_colar_ultima`, `atalho_copiar_ultima`). Botão do mouse sozinho é permitido (exceção à regra "precisa de tecla comum além dos modificadores").
- **Enquanto o botão estiver configurado como atalho, a função normal dele é engolida** (não volta página no navegador). Sem atalho no botão → volta ao normal. (Decisão do controlador, informada ao usuário.)
- Rótulo na interface: "Mouse 4" / "Mouse 5" em keycap.

## Motor (Python)
- `hotkey.py`:
  - `parse_atalho` reconhece `mouse4`/`mouse5` (devolve um marcador que diferencia mouse de VK de teclado; ex. novo `parse_atalho_mouse(atalho) -> tuple[int, int] | None` com (mods, botão 1|2)).
  - `validar_atalho`: aceita `mouse4`/`mouse5` com ou sem modificadores; continua recusando só-modificadores, teclas desconhecidas, `mouse1/2/3`.
  - Novo `GanchoMouse` (um único gancho global **WH_MOUSE_LL** numa thread com laço de mensagens, criado sob demanda): registra assinantes `(mods, botao, on_apertar, on_soltar)`; em `WM_XBUTTONDOWN/UP` confere o botão (HIWORD de mouseData) e os modificadores físicos (GetAsyncKeyState); se casar com um assinante, chama o callback **fora** do gancho (fila para uma thread trabalhadora — o callback do gancho tem que retornar rápido, < ~200 ms, senão o Windows remove o gancho) e **retorna 1** (engole o clique). Sem assinantes → `CallNextHookEx` sempre. Ignora eventos injetados (`LLMHF_INJECTED`).
  - `Hotkey` e `AtalhoAcao` usam o `GanchoMouse` quando o atalho é de mouse: toggle (apertar alterna), push (apertar inicia, soltar para — o soltar vem do `WM_XBUTTONUP`, não de GetAsyncKeyState), ação (apertar chama). Esc continua igual.
  - `stop()` remove o assinante; o gancho é desinstalado quando não sobra assinante.
- `motor.py`: nada muda além de aceitar os novos atalhos (re-registro já existe). Conferir que trocar de teclado para mouse e de volta funciona sem reiniciar.
- Testes (pytest, sem gancho real): `parse`/`validar` com mouse; a lógica de casamento/decisão do gancho extraída em função pura (`decidir_evento(msg, mouse_data, mods_fisicos, assinantes) -> (engolir: bool, chamadas)`), incluindo: botão certo engole e chama apertar; soltar chama on_soltar; modificador exigido ausente não casa e não engole; sem assinantes nunca engole; evento injetado ignorado.

## Interface (Electron)
- `ui/src/renderer/hub/atalho.ts`: `teclaParaAtalho` continua; novo `botaoParaAtalho(e: {button:number, ctrlKey, shiftKey, altKey, metaKey}) -> string | null` (button 3 → `mouse4`, 4 → `mouse5`, outros → null), com modificadores na mesma ordem do teclado. `rotulosDoAtalho` mostra "Mouse 4"/"Mouse 5".
- `GravarAtalho.tsx`: enquanto grava, escuta `mousedown`/`auxclick`/`mouseup` (fase de captura, `preventDefault` para não navegar), aceita botões laterais; mensagem para outros botões: "Use um botão lateral do mouse". Continua recusando duplicados. Dica no campo: "Aperte as teclas ou um botão lateral do mouse".
- Testes vitest para `botaoParaAtalho` e rótulos.

## Verificação real
- Sem usar o Bloco de Notas do usuário: com `npm run dev`, `GILLEVOZ_DADOS` temporário e `GILLEVOZ_WAV_SIMULADO`, configurar `atalho_push = mouse4` pelo Hub (simulando o botão com `SendInput` MOUSEEVENTF_XDOWN/XUP — atenção: eventos injetados são ignorados pelo gancho, então para o teste real usar um parâmetro/variável de teste que permita injetados, ex. `GILLEVOZ_ACEITAR_INJETADO=1`, ou testar o gancho com evento real se não der), confirmar: apertar inicia, soltar para e cola; com atalho no botão, ele não navega "voltar" numa página do Edge aberta pelo teste; tirando o atalho, volta a navegar.
- pytest + vitest + typecheck + build.
