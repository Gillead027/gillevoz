<#
  Pós-instalação do GilleVoz (também é o atalho "Reparar GilleVoz" do Menu Iniciar).
  Roda na pasta da instalação, numa janela visível:
    1. instala o pip no Python embutido (get-pip.py);
    2. instala as bibliotecas do motor (motor\requirements.txt; ~2,3 GB com as do CUDA);
    3. baixa o modelo de voz (reaproveita o cache do Hugging Face se já existir).
  Pode rodar de novo quantas vezes precisar: o que já está pronto é pulado ou só conferido.
  Sai com código 0 se deu tudo certo; com outro código (e a mensagem do erro) se não.
#>
$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'GilleVoz: preparando o motor de voz'

$pasta = $PSScriptRoot
$python = Join-Path $pasta 'python\python.exe'
$total = 3

function Etapa([int]$Numero, [string]$Texto) {
    Write-Host ''
    Write-Host "[$Numero/$total] $Texto" -ForegroundColor Cyan
}

function Falhar([string]$Texto) {
    Write-Host ''
    Write-Host "ERRO: $Texto" -ForegroundColor Red
    Write-Host "Rode 'Reparar GilleVoz' no Menu Iniciar para tentar de novo." -ForegroundColor Yellow
    Write-Host '(Precisa de internet. Se o erro continuar, veja a mensagem acima.)'
    Read-Host 'Aperte Enter para fechar' | Out-Null
    exit 1
}

# Roda o Python embutido; erro se o código de saída não for 0.
function Python([string[]]$Argumentos, [string]$SeFalhar) {
    & $python @Argumentos
    if ($LASTEXITCODE -ne 0) { Falhar "$SeFalhar (código $LASTEXITCODE)." }
}

Write-Host 'GilleVoz: preparando o motor de voz.' -ForegroundColor White
Write-Host 'Não feche esta janela. Na primeira vez pode demorar bastante (baixa uns 2,5 GB).'

try {
    Set-Location $pasta
    if (-not (Test-Path $python)) { Falhar "Não achei o Python da instalação em $python. Reinstale o GilleVoz." }

    # "Reparar" com o app aberto: o motor prende arquivos do Python e o pip não consegue trocá-los.
    Write-Host 'Fechando o GilleVoz, se estiver aberto...'
    & (Join-Path $pasta 'encerrar.ps1') -Pasta $pasta | Out-Null

    Etapa 1 'Instalando o pip (instalador de bibliotecas do Python)...'
    # No PowerShell 5.1, stderr redirecionado com 'Stop' vira exceção: confere o pip com 'Continue'.
    $ErrorActionPreference = 'Continue'
    & $python -m pip --version 2>$null | Out-Null
    $temPip = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = 'Stop'
    if ($temPip) {
        Write-Host 'O pip já está instalado.'
    }
    else {
        Python @((Join-Path $pasta 'get-pip.py'), '--no-warn-script-location', '--disable-pip-version-check') `
            'Não consegui instalar o pip'
    }

    Etapa 2 'Instalando as bibliotecas do motor (faster-whisper, CUDA...). É a parte mais demorada.'
    $instalarLibs = @('-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location',
        '-r', (Join-Path $pasta 'motor\requirements.txt'))
    & $python @instalarLibs
    if ($LASTEXITCODE -ne 0) {
        # Um pip quebrado (instalação interrompida) é a causa mais comum: reinstala o pip e tenta mais uma vez.
        Write-Host ''
        Write-Host 'Não deu certo. Reinstalando o pip e tentando de novo...' -ForegroundColor Yellow
        Python @((Join-Path $pasta 'get-pip.py'), '--force-reinstall', '--no-warn-script-location',
            '--disable-pip-version-check') 'Não consegui reinstalar o pip'
        Python $instalarLibs 'Não consegui instalar as bibliotecas do motor'
    }

    Etapa 3 'Baixando o modelo de voz (se já estiver no PC, só confere)...'
    Set-Location (Join-Path $pasta 'motor')
    Python @('-m', 'gillevoz', '--baixar-modelo') 'Não consegui baixar ou carregar o modelo de voz'
}
catch {
    Falhar $_.Exception.Message
}

Write-Host ''
Write-Host 'Pronto! O GilleVoz está instalado. Abra pelo Menu Iniciar.' -ForegroundColor Green
Start-Sleep -Seconds 4
exit 0
