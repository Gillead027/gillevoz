# Revisão da Flow Bar — 25/11/2026

Somente arquivos em `tests/` foram escritos. O GilleVoz real (pythonw) permaneceu rodando. A medição criou apenas uma FlowBar de teste em (20,20), sem App, atalho, microfone, modelo, config ou clipboard. Não foi aberto Bloco de Notas.

## Achados

| Gravidade | Arquivo:linha | Evidência e correção sugerida |
|---|---|---|
| **Alta** | `gillevoz/flowbar.py:360-365,586-593,387-391` | `stop()` não cancela `_timer_ocultar`. Ao vencer, o timer chama `mostrar()` e `_enfileirar()` reinicia a thread/janela encerrada. **Reproduzido nativamente**: esconder por 0,3 s, parar, esperar 0,7 s → janela e thread reaparecem. Cancelar o timer no encerramento e usar um estado de lifecycle que rejeite posts/restarts após stop; proteger também callback de timer já disparado. A instância de teste foi encerrada novamente e limpa. |
| **Média** | `gillevoz/flowbar.py:367-372,553-554,567-584` | Atualização de `_estado` é protegida, mas o enqueue fica fora do lock. Dois chamadores podem produzir `_estado=pausado` e fila `pausado, gravando`. Resultado: desenho usa estado pausado, enquanto tamanho/timer ficam em gravação. Teste determinístico reproduz a inversão. Serializar alteração e publicação, ou atualizar o estado exclusivamente na thread da UI ao consumir comandos. O app normalmente serializa `_set_estado` com seu RLock; a falha está no contrato público thread-safe da FlowBar. |
| **Média** | `gillevoz/flowbar.py:351-358,387-391,430-435` | Durante startup, `_thread.is_alive()` já é true, mas `_hwnd` ainda pode ser None. Uma chamada concorrente publica em `PostMessageW(NULL,...)`, que não acorda a janela futura; a fila não é drenada ao criar a janela. O comando fica pendente até outra notificação. Teste reproduz o estado intermediário e detecta post para NULL. Sincronizar start com lock, aguardar readiness/erro para todos os chamadores, validar HWND/retorno de PostMessage e drenar comandos iniciais. Também evitar duas inicializações simultâneas. |
| **Média** | `gillevoz/flowbar.py:351-358,419-429`; integração `gillevoz/app.py:102-107` | Erro de `CreateWindowExW` ocorre somente na thread da janela. `start()` retorna sem levantar erro, então o app assume sucesso e não usa o indicador de fallback. Injetar criação retornando NULL reproduz que o chamador não recebe OSError. Guardar erro da thread e propagá-lo após `_pronto.wait`; tratar timeout; garantir finally e encerrar o trabalhador de callbacks se a UI falhar. |
| **Média** | `gillevoz/flowbar.py:478-485,494-532` | Não trata `WM_CAPTURECHANGED` nem `WM_CANCELMODE`: se outra janela capturar o mouse, `_arraste` fica ativo e o button-up pode não chegar, impedindo finalização/salvamento da posição. Teste de perda de captura deixa `_arraste` preenchido. Tratar perda/cancelamento de captura, limpar o arraste e decidir se persiste posição final. Há ainda uma limitação documentada do SetCapture em janela sem foreground; ver observação abaixo. |
| **Baixa** | `gillevoz/flowbar.py:586-593,474-476,580-583` | Esconder durante gravação/transcrição não suspende o timer de animação. **Medição real: 42 ticks em 2 s escondida**, sem repaints e sem CPU mensurável nessa amostra. Suspender timer enquanto invisível e retomá-lo ao mostrar, conforme estado atual. Não confundir com ociosidade: quando ociosa o timer realmente é desligado. |

### Captura do mouse e foco

Barra e menu retornaram `MA_NOACTIVATE=3`. A janela em foreground permaneceu a mesma antes/depois de criar a barra, abrir o menu próprio e executar SetCapture/ReleaseCapture na thread da janela. Não houve SetForegroundWindow ou movimentação do cursor real.

O teste de SetCapture confirmou ownership, **não** a entrega física de eventos fora da barra. A [documentação oficial de SetCapture](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setcapture) limita a captura de janelas em background à sua região visível. Como a barra deliberadamente não vira foreground, inferimos risco de arraste rápido sair da barra e perder movimento/button-up. Não foi reproduzido com mouse físico, para não interferir no usuário. Sugerido acompanhar cursor e botão durante o arraste por timer/entrada apropriada, sem ativar a janela, além de tratar perda de captura. Isso é distinto da ausência de WM_CAPTURECHANGED, reproduzida por mensagem no teste.

## Testes e limites

1. Comando solicitado, antes dos testes novos: `.venv\Scripts\python.exe -m pytest -q` → **24 passaram, 9 erros** de setup: WinError 5 ao remover `.pytest_tmp`. Não alterei ACL nem apaguei pasta compartilhada.
2. Mesma suíte com diretório exclusivo: `--basetemp=tests/.tmp_flowbar_review_01 --tb=short` → **33 passaram em 2,85 s**.
3. Suíte final com regressões: `.venv\Scripts\python.exe -m pytest -q --basetemp=tests/.tmp_flowbar_review_03 --tb=short` → **34 passaram, 6 falharam em 2,82 s**. Falhas são os seis achados da tabela, sem xfail. Basetemp exclusivo evita também conflito com testes de outros terminais.

Arquivo novo de testes: `tests/test_flowbar_review.py`. Além das seis regressões, contém 20 rodadas de clique na barra e chamada de início pelo atalho simultâneos, usando Recorder falso e transcrição simulada: sem deadlock, sem dupla abertura do microfone, no máximo um stop. Dois comandos toggle podem legitimamente iniciar e parar; o teste não exige que sejam fundidos em um único comando.

Os testes existentes de integração e Recorder.nivel passaram. Não medi latência da captura física; o teste do nível usa blocos sintéticos. Não houve mudanças em produção.

## Medições nativas GDI/CPU

Script reproduzível: `.venv\Scripts\python.exe tests\probe_flowbar.py`.

Resultados completos em `tests/flowbar_metrics.json` e `tests/flowbar_lifecycle_metrics.json`.

| Medição | Resultado |
|---|---|
| GDI, 300 repaints animados de gravação | **6 → 6** objetos, sem crescimento |
| Animação | 300 repaints em 14,0496 s; CPU de processo 0,046875 s (~0,334% de um núcleo) |
| GDI, 300 repaints adicionais do menu | **6 → 6** objetos, sem crescimento |
| Ociosa, 2 s | 0 ticks, 0 repaints, CPU 0,000000 s medida |
| Ociosa após animação, 2,0004 s | 0 ticks, 1 repaint residual, CPU 0,000000 s medida |
| Escondida/transcrevendo, 2,0005 s | 42 ticks, 0 repaints, CPU 0,000000 s medida |
| Retorno após esconder | Funcionou com 0,15 s; usa o mesmo caminho de timer dos 3600 s. Não esperei uma hora. |
| Posição salva fora de monitores | (1.000.000, 1.000.000) corrigida para (3788,1006), dentro da área útil do monitor mais próximo |
| Stop sem timer pendente | Thread da janela encerrada e HWND destruído |
| Stop com retorno pendente | Thread/HDWN encerrados imediatamente, mas recriados após vencer o timer: bug confirmado |
| Cinco ciclos adicionais de start/stop | 6 objetos GDI aberta / 3 após stop em **todos** os ciclos, nenhuma thread `gillevoz-flowbar*` restante |

Contagem por `GetGuiResources(GetCurrentProcess(),0)`, amostrada na thread da UI entre desenhos para não contar recursos temporários. O processo começou com 0 e estabilizou em 3 após o primeiro ciclo; não houve crescimento por repaint ou pelos cinco ciclos seguintes. Não atribuí os três objetos persistentes a vazamento sem evidência de crescimento.

CPU medida com `time.process_time()` do processo isolado, não do GilleVoz real. A resolução observada é em torno de 15,6 ms; zero numa janela de 2 s significa abaixo da resolução, não prova de custo absolutamente nulo. Ociosa, adicionalmente, a contagem de ticks comprova que o timer está parado.

Pendências: donos corrigirem lifecycle, publicação/readiness, propagação de falha e arraste; rerodar testes; validar mouse físico fora da barra sem roubar foco. A nota do cérebro continua sob responsabilidade do Maestro.
