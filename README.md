# GilleVoz

Ditado por voz para o Windows. Você fala, ele escreve. Tudo roda **no seu PC**, sem internet depois da instalação.

Foi feito para falar com os agentes do Maestri (Claude Code e Codex) em vez de digitar.

## Como instalar (primeira vez)

1. Abra a pasta do projeto.
2. Dê dois cliques em **`setup.bat`**.
3. Espere terminar. Na primeira vez ele baixa as bibliotecas e o modelo de voz, então pode demorar.

Se aparecer um aviso sobre o modelo, rode o `setup.bat` de novo. Ele pula o que já está pronto.

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
