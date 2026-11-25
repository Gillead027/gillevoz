<#
  Gera um WAV de teste (16 kHz, 16-bit, mono) com a voz pt-BR "Microsoft Maria Desktop".
  Uso: powershell -ExecutionPolicy Bypass -File tools\gerar_wav_teste.ps1 -Texto "ação, coração" -Saida teste.wav
#>
param(
    [Parameter(Mandatory = $true)][string]$Texto,
    [Parameter(Mandatory = $true)][string]$Saida,
    [string]$Voz = "Microsoft Maria Desktop",
    [int]$Velocidade = 0
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech

$saidaAbs = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Saida))
$pasta = Split-Path $saidaAbs -Parent
if (-not (Test-Path $pasta)) { New-Item -ItemType Directory -Force $pasta | Out-Null }

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    try { $synth.SelectVoice($Voz) }
    catch {
        $nomes = ($synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }) -join ", "
        throw "Voz '$Voz' não encontrada. Instaladas: $nomes"
    }
    $synth.Rate = $Velocidade
    $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $synth.SetOutputToWaveFile($saidaAbs, $fmt)
    $synth.Speak($Texto)
}
finally {
    $synth.SetOutputToNull()
    $synth.Dispose()
}
Write-Output "WAV gerado: $saidaAbs"
