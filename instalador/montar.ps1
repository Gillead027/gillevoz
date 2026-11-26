<#
  Monta o instalador do GilleVoz: instalador\saida\GilleVoz-Setup.exe
  Uso (na raiz do projeto):  powershell -ExecutionPolicy Bypass -File instalador\montar.ps1
  Precisa de: Node/npm (dependências do ui\ já instaladas), Inno Setup 6 e internet na primeira vez.
  Etapas:
    1. compila a interface e empacota com o electron-builder (alvo dir) -> ui\dist\win-unpacked
    2. baixa para instalador\cache\ (só se ainda não tiver) o Python 3.12 embutível e o get-pip.py
    3. monta instalador\cache\motor\ (pacote gillevoz + requirements.txt sem pytest)
    4. compila gillevoz.iss com o ISCC
#>
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'  # a barra de progresso deixa o Invoke-WebRequest muito lento
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$instalador = $PSScriptRoot
$raiz = Split-Path -Parent $instalador
$ui = Join-Path $raiz 'ui'
$cache = Join-Path $instalador 'cache'

$PYTHON_VERSAO = '3.12.10'
$PYTHON_ZIP = "python-$PYTHON_VERSAO-embed-amd64.zip"
$PYTHON_URL = "https://www.python.org/ftp/python/$PYTHON_VERSAO/$PYTHON_ZIP"
# SHA-256 do zip. O python.org só publica o MD5 (fe8ef205f2e9c3ba44d0cf9954e1abd3): baixei, conferi o MD5
# e fixei aqui o SHA-256 do mesmo arquivo.
$PYTHON_SHA256 = '4ACBED6DD1C744B0376E3B1CF57CE906F9DC9E95E68824584C8099A63025A3C3'
$GETPIP_URL = 'https://bootstrap.pypa.io/get-pip.py'

function Etapa([string]$Texto) {
    Write-Host ''
    Write-Host "== $Texto" -ForegroundColor Cyan
}

function Rodar([string]$Programa, [string[]]$Argumentos) {
    & $Programa @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "Falhou ($LASTEXITCODE): $Programa $($Argumentos -join ' ')" }
}

function Baixar([string]$Url, [string]$Destino) {
    if (Test-Path $Destino) {
        Write-Host "Já está no cache: $(Split-Path -Leaf $Destino)"
        return
    }
    Write-Host "Baixando $Url"
    $temporario = "$Destino.baixando"
    Invoke-WebRequest -Uri $Url -OutFile $temporario -UseBasicParsing
    Move-Item -Force $temporario $Destino
}

# ---------------------------------------------------------------- 1. interface (Electron)
Etapa '1/4 Compilando e empacotando a interface (electron-builder --dir)'
Push-Location $ui
try {
    $dist = Join-Path $ui 'dist'
    if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
    Rodar 'npm.cmd' @('run', 'build')
    Rodar 'npx.cmd' @('electron-builder', '--win', '--dir')
}
finally {
    Pop-Location
}
$exeApp = Join-Path $ui 'dist\win-unpacked\GilleVoz.exe'
if (-not (Test-Path $exeApp)) { throw "O electron-builder não gerou $exeApp" }

# ---------------------------------------------------------------- 2. downloads
Etapa '2/4 Python embutível e get-pip.py'
New-Item -ItemType Directory -Force $cache | Out-Null
$zip = Join-Path $cache $PYTHON_ZIP
Baixar $PYTHON_URL $zip
$hash = (Get-FileHash -Algorithm SHA256 $zip).Hash
if ($hash -ne $PYTHON_SHA256) {
    Remove-Item -Force $zip
    throw "SHA-256 do $PYTHON_ZIP não confere (veio $hash, esperado $PYTHON_SHA256). Apaguei o arquivo; rode de novo."
}
Write-Host "SHA-256 confere: $hash"
$pastaPython = Join-Path $cache 'python'
if (Test-Path $pastaPython) { Remove-Item -Recurse -Force $pastaPython }
Expand-Archive -Path $zip -DestinationPath $pastaPython
Baixar $GETPIP_URL (Join-Path $cache 'get-pip.py')

# ---------------------------------------------------------------- 3. motor
Etapa '3/4 Pacote do motor'
$motor = Join-Path $cache 'motor'
if (Test-Path $motor) { Remove-Item -Recurse -Force $motor }
New-Item -ItemType Directory -Force (Join-Path $motor 'gillevoz') | Out-Null
Get-ChildItem (Join-Path $raiz 'gillevoz') -File -Filter '*.py' |
    Copy-Item -Destination (Join-Path $motor 'gillevoz')
# requirements.txt sem o pytest (só serve para os testes).
$requisitos = Get-Content (Join-Path $raiz 'requirements.txt') |
    Where-Object { $_.Trim() -and ($_ -notmatch '^\s*pytest') }
Set-Content -Path (Join-Path $motor 'requirements.txt') -Value $requisitos -Encoding ASCII
Write-Host "Requisitos: $($requisitos -join ', ')"

# ---------------------------------------------------------------- 4. Inno Setup
Etapa '4/4 Compilando o instalador (Inno Setup)'
$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path $iscc)) { throw "Não achei o Inno Setup 6 em $iscc" }
$versao = (Get-Content (Join-Path $ui 'package.json') -Raw | ConvertFrom-Json).version
Rodar $iscc @("/DVersao=$versao", (Join-Path $instalador 'gillevoz.iss'))

$saida = Join-Path $instalador 'saida\GilleVoz-Setup.exe'
$mb = [math]::Round((Get-Item $saida).Length / 1MB, 1)
Write-Host ''
Write-Host "Pronto: $saida ($mb MB)" -ForegroundColor Green
