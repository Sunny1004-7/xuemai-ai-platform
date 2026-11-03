param([switch]$RealAI)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw '请先运行 scripts\setup.ps1' }
foreach ($servicePort in @(8000,5173)) {
    if (Get-NetTCPConnection -LocalPort $servicePort -State Listen -ErrorAction SilentlyContinue) {
        throw "端口 $servicePort 已有服务。若学脉已启动，请直接打开网页；切换AI模式前运行 scripts\stop.ps1。"
    }
}
$env:AI_MODE = if ($RealAI) { 'real' } else { 'mock' }
New-Item -ItemType Directory -Force -Path '.local' | Out-Null
$backendProcess = Start-Process -FilePath "$projectRoot\.venv\Scripts\python.exe" -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput "$projectRoot\.local\backend.log" -RedirectStandardError "$projectRoot\.local\backend-error.log" -PassThru
$frontendProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','npm run dev -- --host 127.0.0.1 --port 5173 --strictPort' -WorkingDirectory "$projectRoot\frontend" -WindowStyle Hidden -RedirectStandardOutput "$projectRoot\.local\frontend.log" -RedirectStandardError "$projectRoot\.local\frontend-error.log" -PassThru
@{backend=$backendProcess.Id; frontend=$frontendProcess.Id} | ConvertTo-Json | Set-Content '.local\processes.json'
$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        $front = Invoke-WebRequest 'http://127.0.0.1:5173' -TimeoutSec 2
        if ($health.status -eq 'ok' -and $front.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) { throw '服务未就绪，请查看 .local 中的启动日志。' }
Write-Host '学脉：http://127.0.0.1:5173  接口：http://127.0.0.1:8000/docs'
Write-Host '服务在后台运行。停止请运行 scripts\stop.ps1。'
