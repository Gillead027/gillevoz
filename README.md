# GilleVoz

Ditado por voz para o Windows. Você fala, ele escreve. Tudo roda **no seu PC**, sem internet depois da instalação.

Foi feito para falar com os agentes do Maestri (Claude Code e Codex) em vez de digitar.

## Como instalar

1. Rode **`GilleVoz-Setup.exe`** (não pede administrador; instala em `%LOCALAPPDATA%\Programs\GilleVoz`).
2. Escolha se quer atalho na Área de Trabalho e iniciar com o Windows.
3. Depois de copiar os arquivos abre uma janela que instala as bibliotecas do motor e o modelo de voz.
   Na primeira vez baixa uns 2,5 GB: **precisa de internet** e pode demorar. Se o modelo já estiver no PC
   (cache do Hugging Face), ele é reaproveitado.
4. Abra pelo **Menu Iniciar → GilleVoz**.

Se a janela de preparação der erro, rode **Menu Iniciar → Reparar GilleVoz** (faz tudo de novo, pulando o que já
está pronto). Precisa de placa NVIDIA para a velocidade normal; sem ela o motor cai para a CPU (mais lento).

O instalador fecha o GilleVoz v1 se estiver aberto e o motor tira o atalho antigo da pasta Inicializar, para os
dois não brigarem pelo atalho de teclado. Na primeira vez, `config.json` e `historico\` do v1 são copiados
de `C:\Mudo Tech\gillevoz` para `%APPDATA%\GilleVoz`.

**Desinstalar**: Configurações do Windows → Aplicativos → GilleVoz. Apaga o programa, mas **mantém** seus dados
em `%APPDATA%\GilleVoz` (configuração, histórico e logs).

## Como usar

- **Dê dois cliques em `GilleVoz.vbs`** para abrir sem janela preta. O ícone aparece na bandeja do Windows (perto do relógio).
- **Ctrl+Shift+Espaço**: aperte uma vez para começar a gravar. Aparece a pílula "● gravando" embaixo, no centro. Aperte de novo para parar.
- O texto é transcrito e **colado onde o cursor está**, sem apertar Enter. Você revisa e envia.
- **Esc** cancela a gravação sem colar nada.
- Para usar no meio de um texto já digitado, basta colocar o cursor no lugar certo e ditar.

## Ícone da bandeja

Clique com o botão direito no ícone:

- **Pausar / Ativar**: liga e desliga o atalho.
- **Abrir histórico**: mostra as transcrições guardadas.
- **Abrir config**: abre o arquivo de configuração.
- **Iniciar com o Windows**: liga ou desliga a abertura automática.
- **Sair**: fecha o GilleVoz.

## Configuração

Tudo fica no arquivo **`config.json`**, criado automaticamente na primeira vez. Os campos principais:

| Campo | O que faz | Padrão |
|---|---|---|
| `atalho` | Tecla de atalho para gravar | `ctrl+shift+space` |
| `modo` | `toggle` (aperta e solta) ou `push` (segura para gravar) | `toggle` |
| `auto_enter` | Apertar Enter sozinho depois de colar | `false` |
| `metodo_colagem` | `clipboard` (cola de uma vez) ou `digitar` (letra por letra) | `clipboard` |
| `bips` | Toca um bip no início e no fim | `true` |
| `vocabulario` | Palavras que o reconhecimento deve acertar (nomes próprios) | lista pronta |

Depois de editar, feche e abra o GilleVoz de novo. Se o arquivo ficar com erro de digitação, o app guarda uma cópia com o nome `config.json.invalido-...` e volta para os valores padrão.

## Onde ficam as coisas

Tudo em `%APPDATA%\GilleVoz` (no desenvolvimento, a variável `GILLEVOZ_DADOS` pode apontar outra pasta):

- **`config.json`**: a configuração.
- **`historico/`**: uma pasta com um arquivo por dia (`AAAA-MM-DD.md`). Toda transcrição fica salva com o horário.
- **`logs/gillevoz.log`**: erros e tempos de cada transcrição. Use este arquivo se algo der errado.

## Abrir com console (para ver erros)

Use **`iniciar.bat`**. Ele abre o GilleVoz com uma janela de texto, onde aparecem as mensagens. É útil quando algo não funciona.

## Problemas comuns

- **"O GilleVoz ainda não foi instalado"**: rode o `setup.bat` primeiro.
- **O atalho não faz nada**: confira se o ícone da bandeja não está em "Pausar" (no menu, aparece "Ativar" quando está pausado).
- **O texto não aparece**: confira no `logs/gillevoz.log` se houve erro. Se a transcrição caiu para a CPU, o log avisa.
- **Quer apagar a instalação**: apague a pasta `.venv`. Para tirar da inicialização, desmarque "Iniciar com o Windows" no menu da bandeja.

## Para quem mexe no código

- Python 3.12 (o `setup.bat` cria o `.venv` com ele). **Não use o Python 3.14 do sistema**: faltam pacotes para ele.
- Contrato entre os módulos: `docs/ARQUITETURA.md`. Especificação e critérios de pronto: `docs/SPEC.md`.

### Montar o instalador

Na raiz do projeto: `powershell -ExecutionPolicy Bypass -File instalador\montar.ps1`
(precisa de Node/npm com `npm install` feito em `ui\`, Inno Setup 6 e internet na primeira vez).
Sai em `instalador\saida\GilleVoz-Setup.exe`. Downloads ficam em `instalador\cache\` (fora do git).
O ícone (`instalador\icone.ico` e `ui\resources\gillevoz.png`) é gerado de `docs\icone\b-matriz-led.svg` com
`ui\node_modules\.bin\electron instalador\gerar_icone.cjs`.
