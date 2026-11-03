param(
    [string]$ScenesPath = "",
    [string]$VoiceName = "",
    [ValidateRange(-5, 5)][int]$Rate = 0,
    [switch]$ListVoices
)

# Offline synthetic narration. Run with Windows PowerShell 5 (powershell.exe).
# No network, external service, API key, or provider request is used.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$taskRoot = Split-Path -Parent $PSScriptRoot
if (-not $ScenesPath) { $ScenesPath = Join-Path $PSScriptRoot 'demo-scenes.json' }
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = @($synth.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo })
$voices | Select-Object Name, Culture, Gender | Format-Table | Out-Host
if ($ListVoices) { $synth.Dispose(); return }
if (-not $VoiceName) {
    $chineseVoice = $voices | Where-Object { $_.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
    if (-not $chineseVoice) {
        $synth.Dispose()
        throw 'No offline zh-CN voice is installed. Use the Chinese scene text as subtitles; do not claim Chinese narration was generated.'
    }
    $VoiceName = $chineseVoice.Name
}
$synth.SelectVoice($VoiceName)
$synth.Volume = 100
$synth.Rate = $Rate
$audioFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$scenes = Get-Content -Raw -LiteralPath $ScenesPath -Encoding UTF8 | ConvertFrom-Json

function Get-WaveDuration([string]$Path) {
    $reader = New-Object System.IO.BinaryReader([System.IO.File]::OpenRead($Path))
    try {
        $null = $reader.ReadBytes(12)
        $byteRate = 0
        $dataSize = 0
        while ($reader.BaseStream.Position + 8 -le $reader.BaseStream.Length) {
            $chunk = [System.Text.Encoding]::ASCII.GetString($reader.ReadBytes(4))
            $size = $reader.ReadUInt32()
            $next = $reader.BaseStream.Position + $size + ($size % 2)
            if ($chunk -eq 'fmt ') {
                $null = $reader.ReadUInt16()
                $null = $reader.ReadUInt16()
                $null = $reader.ReadUInt32()
                $byteRate = $reader.ReadUInt32()
            } elseif ($chunk -eq 'data') {
                $dataSize += $size
            }
            $reader.BaseStream.Position = $next
        }
        if ($byteRate -le 0) { throw 'WAV format has no valid byte rate.' }
        return [math]::Round($dataSize / $byteRate, 3)
    } finally { $reader.Dispose() }
}

$manifest = @()
try {
    foreach ($scene in $scenes) {
        $outputPath = [System.IO.Path]::GetFullPath((Join-Path $taskRoot $scene.file))
        $expectedRoot = [System.IO.Path]::GetFullPath((Join-Path $taskRoot '.local\narration'))
        if (-not $outputPath.StartsWith($expectedRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Narration output must remain under .local/narration: $($scene.id)"
        }
        $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputPath)
        $synth.SetOutputToWaveFile($outputPath, $audioFormat)
        $synth.Speak([string]$scene.text)
        $synth.SetOutputToNull()
        $seconds = Get-WaveDuration $outputPath
        $fits = $seconds -le ([double]$scene.duration - 0.15)
        $manifest += [PSCustomObject]@{
            id = $scene.id; start = $scene.start; duration = $scene.duration
            actual_seconds = $seconds; fits = $fits; file = $scene.file
            voice = $VoiceName; rate = $Rate; synthetic_narration = $true
        }
        Write-Host ("{0}: {1:N3}s / {2}s; fits={3}" -f $scene.id, $seconds, $scene.duration, $fits)
    }
} finally { $synth.Dispose() }
$manifestPath = Join-Path $taskRoot '.local\narration\manifest.json'
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
if (@($manifest | Where-Object { -not $_.fits }).Count -gt 0) {
    throw 'Some narration segments exceed their scene windows. Shorten the corresponding text or raise Rate, then regenerate.'
}
Write-Host "Offline synthetic narration complete. Manifest: $manifestPath"
