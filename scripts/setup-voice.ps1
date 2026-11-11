$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& .venv/Scripts/python.exe -m pip install -r scripts/requirements-voice.txt
if ($LASTEXITCODE -ne 0) { throw '语音依赖安装失败' }
$env:HF_HUB_DISABLE_XET = '1'
if (-not $env:HF_ENDPOINT) { $env:HF_ENDPOINT = 'https://hf-mirror.com' }
& .venv/Scripts/python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small', local_dir='.local/models/faster-whisper-small', allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.*'])"
if ($LASTEXITCODE -ne 0) { throw '语音模型下载失败，请检查网络后重新运行' }
Write-Host '本地语音识别已就绪'
