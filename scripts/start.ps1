param([switch]$RealAI, [switch]$ReuseExisting)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot

function Get-ProjectService {
    param([int]$Port, [string]$CommandPattern, [switch]$AllowExisting)
    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if (-not $listeners.Count) { return $null }
    if (-not ($ReuseExisting -or $AllowExisting)) {
        throw "端口 $Port 已有服务。可双击根目录启动入口复用服务，或先运行 scripts\stop.ps1。"
    }
    $ownerIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($ownerIds.Count -ne 1) { throw "端口 $Port 存在多个监听进程，请先检查端口占用。" }
    $service = Get-CimInstance Win32_Process -Filter "ProcessId=$($ownerIds[0])"
    $belongsToProject = $service.CommandLine -and $service.CommandLine.IndexOf($projectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0
    if (-not $belongsToProject -or $service.CommandLine -notmatch $CommandPattern) {
        throw "端口 $Port 已被其他程序占用，请关闭该程序后重新启动。"
    }
    return [int]$ownerIds[0]
}

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    throw '请先双击根目录启动入口准备依赖，或运行 scripts\setup.ps1。'
}
$frontendEntry = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $frontendEntry)) { throw '前端依赖未就绪，请运行 scripts\setup.ps1。' }
$nodeCommand = Get-Command node.exe -ErrorAction Stop
$backendId = Get-ProjectService -Port 8000 -CommandPattern 'uvicorn\s+backend\.app\.main:app'
$frontendId = Get-ProjectService -Port 5173 -CommandPattern 'vite[\\/]bin[\\/]vite\.js'
$env:AI_MODE = if ($RealAI) { 'real' } else { 'mock' }
New-Item -ItemType Directory -Force -Path '.local' | Out-Null
$started = @()

try {
    if (-not $backendId) {
        $process = Start-Process -FilePath "$projectRoot\.venv\Scripts\python.exe" -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput "$projectRoot\.local\backend.log" -RedirectStandardError "$projectRoot\.local\backend-error.log" -PassThru
        $started += $process
        $backendId = $process.Id
    }
    if (-not $frontendId) {
        $process = Start-Process -FilePath $nodeCommand.Source -ArgumentList @(('"' + $frontendEntry + '"'), '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory "$projectRoot\frontend" -WindowStyle Hidden -RedirectStandardOutput "$projectRoot\.local\frontend.log" -RedirectStandardError "$projectRoot\.local\frontend-error.log" -PassThru
        $started += $process
        $frontendId = $process.Id
    }
    $ready = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        foreach ($process in $started) {
            $process.Refresh()
            if ($process.HasExited) { throw '服务启动进程已退出，请查看 .local 中对应的错误日志。' }
        }
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
            $front = Invoke-WebRequest 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq 'ok' -and $front.Content.Contains('XueMai')) {
                $ready = $true
                break
            }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw '服务未在等待时间内就绪，请查看 .local 中的启动日志。' }
    # Windows虚拟环境的启动器可能派生实际监听进程，停止记录采用监听进程ID。
    $backendId = Get-ProjectService -Port 8000 -CommandPattern 'uvicorn\s+backend\.app\.main:app' -AllowExisting
    $frontendId = Get-ProjectService -Port 5173 -CommandPattern 'vite[\\/]bin[\\/]vite\.js' -AllowExisting
    @{ backend = $backendId; frontend = $frontendId } | ConvertTo-Json | Set-Content -LiteralPath '.local\processes.json' -Encoding UTF8
} catch {
    foreach ($process in $started) {
        $process.Refresh()
        if (-not $process.HasExited) { taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null }
    }
    throw
}

Write-Host '学脉已就绪 http://127.0.0.1:5173'
Write-Host '接口文档 http://127.0.0.1:8000/docs'
Write-Host '服务在后台运行。停止请运行 scripts\stop.ps1。'
