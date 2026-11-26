<#
  Fecha o GilleVoz antes de instalar ou desinstalar (chamado pelo gillevoz.iss, sem janela).
  - Todo GilleVoz.exe (a interface; dois ao mesmo tempo brigariam pelo atalho de teclado).
  - Todo python/pythonw que roda de dentro da pasta da instalação (o motor e a pós-instalação).
  - Com -V1: o GilleVoz v1 (pythonw.exe "-m gillevoz", sem --motor, da pasta C:\Mudo Tech\gillevoz).
  Uso: powershell -NoProfile -ExecutionPolicy Bypass -File encerrar.ps1 -Pasta "<instalação>" [-V1]
#>
param(
    [Parameter(Mandatory = $true)][string]$Pasta,
    [switch]$V1
)
$ErrorActionPreference = 'Continue'

$prefixo = [System.IO.Path]::GetFullPath($Pasta).TrimEnd('\') + '\'
$pastaV1 = 'C:\Mudo Tech\gillevoz\'

function Encerrar([object]$Processo, [string]$Motivo) {
    Write-Output "Fechando $($Processo.Name) (PID $($Processo.ProcessId)): $Motivo"
    # /T leva junto os filhos (o pythonw do .venv do v1 abre o Python de verdade como filho).
    & taskkill.exe /PID $Processo.ProcessId /T /F 2>&1 | Out-Null
}

$filtro = "Name='GilleVoz.exe' OR Name='pythonw.exe' OR Name='python.exe'"
foreach ($p in @(Get-CimInstance Win32_Process -Filter $filtro)) {
    $exe = [string]$p.ExecutablePath
    $linha = [string]$p.CommandLine
    if ($p.Name -eq 'GilleVoz.exe') {
        Encerrar $p 'interface do GilleVoz'
    }
    elseif ($exe -and $exe.StartsWith($prefixo, [System.StringComparison]::OrdinalIgnoreCase)) {
        Encerrar $p 'Python da instalação'
    }
    elseif ($V1 -and $p.Name -eq 'pythonw.exe' -and $linha -match '-m\s+gillevoz\s*$' -and
            ($exe.StartsWith($pastaV1, [System.StringComparison]::OrdinalIgnoreCase) -or
             $linha.IndexOf($pastaV1, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)) {
        Encerrar $p 'GilleVoz v1'
    }
}
# Dá um instante para o Windows soltar os arquivos dos processos fechados.
Start-Sleep -Milliseconds 500
exit 0
