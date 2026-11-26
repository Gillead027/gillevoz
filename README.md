# GilleVoz

Ditado por voz para o Windows. Você fala, ele escreve. Tudo roda **no seu PC**, sem internet depois da instalação.

Foi feito para falar com os agentes do Maestri (Claude Code e Codex) em vez de digitar. A versão atual é a **v2**:
barra flutuante (Flow Bar), janela principal (Hub) com histórico, dicionário e atalhos de texto, e o texto aparece
**enquanto você fala** (tempo real).

## Como instalar, reparar e desinstalar

1. Rode **`GilleVoz-Setup.exe`** (não pede administrador; instala em `%LOCALAPPDATA%\Programs\GilleVoz`).
2. Escolha se quer atalho na Área de Trabalho e iniciar com o Windows.
3. Depois de copiar os arquivos abre uma janela que instala as bibliotecas do motor e o modelo de voz.
   Na primeira vez baixa uns 2,5 GB: **precisa de internet** e pode demorar. Se o modelo já estiver no PC
   (cache do Hugging Face), ele é reaproveitado.
4. Abra pelo **Menu Iniciar → GilleVoz**.

**Reparar**: se a janela de preparação der erro, rode **Menu Iniciar → Reparar GilleVoz** (refaz tudo, pulando o que
já está pronto). Precisa de placa NVIDIA para a velocidade normal; sem ela o motor cai para a CPU (mais lento).

**Desinstalar**: Configurações do Windows → Aplicativos → GilleVoz. Apaga o programa, mas **mantém** seus dados
em `%APPDATA%\GilleVoz` (configuração, histórico e logs).

O instalador fecha o GilleVoz v1 se estiver aberto e o motor tira o atalho antigo da pasta Inicializar, para os dois
não brigarem pelo atalho de teclado. Na primeira vez, `config.json` e `historico\` do v1 são copiados de
`C:\Mudo Tech\gillevoz` para `%APPDATA%\GilleVoz`.

## Como usar

- Abra o GilleVoz pelo Menu Iniciar. A **barra** aparece embaixo, no centro (arraste para outro lugar: ela gruda
  na esquerda, na direita ou embaixo). O ícone fica na bandeja do Windows.
- **Ctrl+Shift+Espaço**: aperte uma vez para começar a gravar e de novo para parar (mãos livres).
  Enquanto você fala, o texto vai sendo digitado onde o cursor está. Não aperta Enter sozinho.
- **Esc** (ou o X da barra) cancela. Clique na engrenagem da barra para abrir o **Hub**.
- No Hub: **Início** (estatísticas e histórico), **Dicionário** (palavras e trocas), **Atalhos de texto** e
  **Configurações** (atalhos, microfone, tempo real, sons, motor). Tudo é salvo na hora.
- Clique direito na barra: esconder por 1 hora, escolher microfone, abrir o GilleVoz, pausar, sair.
- Segurar para falar, "colar última" e "copiar última" existem, mas vêm desligados: ligue em Configurações → Atalhos.
  No "segurar para falar" não há tempo real (o texto é colado no final).

## Onde ficam as coisas

- **`%APPDATA%\GilleVoz`** (ou a pasta em `GILLEVOZ_DADOS`): `config.json`, `historico\` (um `.md` e um `.jsonl` por
  dia) e `logs\gillevoz.log`. Use o log se algo der errado.
- **`%LOCALAPPDATA%\Programs\GilleVoz`**: o programa instalado.

## Para quem mexe no código

Python 3.12 (**não** use o 3.14 do sistema: faltam pacotes) e Node/npm. Contrato dos módulos e como a digitação
funciona: [docs/ARQUITETURA.md](docs/ARQUITETURA.md). Desenho e decisões do v2: [docs/DESENHO-V2.md](docs/DESENHO-V2.md)
e [docs/REFERENCIAS-UI.md](docs/REFERENCIAS-UI.md).

### Rodar em desenvolvimento
1. Uma vez: `setup.bat` (cria o `.venv` com Python 3.12 e instala `requirements.txt`) e `npm install` dentro de `ui\`.
2. Dentro de `ui\`: `npm run dev`. O Electron abre a barra e inicia o motor com `.venv\Scripts\pythonw.exe -m gillevoz --motor`.
   O dev usa um perfil separado (`%LOCALAPPDATA%\GilleVoz-dev`) para não brigar com o app instalado.
3. Para testar sem falar: defina `GILLEVOZ_WAV_SIMULADO` com o caminho de um WAV (o motor usa o arquivo como microfone);
   `tools\gerar_wav_teste.ps1` gera um. `GILLEVOZ_DADOS` aponta os dados para outra pasta.

### Rodar os testes
- Python (na raiz): `.venv\Scripts\python.exe -m pytest -m "not gpu"` (o marcador `gpu` precisa de placa e modelo).
- Interface (em `ui\`): `npx vitest run`. Também há `npm run typecheck` e `npm run lint`.

### Montar o instalador
Na raiz: `powershell -ExecutionPolicy Bypass -File instalador\montar.ps1`
(precisa de Node/npm com `npm install` feito em `ui\`, Inno Setup 6 e internet na primeira vez).
Sai em `instalador\saida\GilleVoz-Setup.exe`. Downloads ficam em `instalador\cache\` (fora do git).
O ícone (`instalador\icone.ico` e `ui\resources\gillevoz.png`) é gerado de `docs\icone\b-matriz-led.svg` com
`ui\node_modules\.bin\electron instalador\gerar_icone.cjs`.

### Teste de digitação (`tools\teste_digitacao.py`)
Abre janelas **próprias** (Bloco de Notas, uma caixa de texto do PowerShell e o Edge), digita uma frase com acentos
trecho a trecho como o tempo real faz, lê de volta e compara:
`.venv\Scripts\python.exe tools\teste_digitacao.py [--alvos bloco,winforms,edge] [--rodadas 3] [--carga]`
(`--carga` enche a CPU, o caso em que o Bloco de Notas trocava letras). Não use o PC enquanto roda (~1 min).

**Regra de segurança:** o alvo `bloco` **se recusa a rodar** se já houver um Bloco de Notas aberto ou uma sessão
guardada dele (abas restauradas), para nunca mexer em texto seu. Antes de cada palavra o teste confere que a
janela em foco é a dele; se não for, para na hora.

### Limitações e pontos em aberto
- **Teste com voz real ainda pendente**: o tempo real foi validado com WAV simulado e com o teste de digitação,
  não ditando de verdade num terminal do Maestri.
- **Bloco de Notas do Windows 11** troca/perde letras se a digitação for rápida; por isso a digitação é tecla a tecla
  com margem de tempo (15 ms por letra, 80 ms depois de espaço/pontuação). Fica ~1 s mais lenta a cada 100 caracteres.
- **Trocas perdem pontuação inicial** da palavra (ex.: `(` ou aspas antes da palavra trocada).
- **Atalho de texto curto vence o longo** quando começam igual (ex.: "meu pix" × "meu pix novo").
- **Gravar um atalho novo (Configurações) pausa o app** enquanto você aperta as teclas.
- **O teste de digitação é de uso único no Bloco de Notas**: cada aba de teste fechada fica na sessão do Bloco de
  Notas, e a regra de segurança acima passa a recusar. Para repetir, limpe a sessão do Bloco de Notas à mão.
- Fechar o app durante uma gravação cancela em vez de terminar o ditado.
- `GilleVoz.vbs`, `iniciar.bat` e a bandeja Python são do **v1 (legado)**: não iniciam mais o app. No v2 se abre
  pelo Menu Iniciar (ou `npm run dev` no desenvolvimento).
