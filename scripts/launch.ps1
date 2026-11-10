param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot

try {
    if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
        throw '请先安装 Node.js 20.18 或更高版本，然后重新双击启动入口。'
    }
    $pythonReady = Test-Path -LiteralPath '.venv\Scripts\python.exe'
    $frontendReady = Test-Path -LiteralPath 'frontend\node_modules\vite\bin\vite.js'
    if (-not ($pythonReady -and $frontendReady)) {
        Write-Host '首次启动正在准备依赖，请保持窗口打开。'
        & (Join-Path $PSScriptRoot 'setup.ps1')
    }

    & (Join-Path $PSScriptRoot 'start.ps1') -ReuseExisting
    if (-not $NoBrowser) {
        Start-Process 'http://127.0.0.1:5173'
    }
    Write-Host '演示账号 student1、teacher，密码均为 Xuemai123!。'
} catch {
    Write-Host ('启动失败。' + $_.Exception.Message) -ForegroundColor Red
    Write-Host '可查看 .local 目录下的前后端日志。'
    exit 1
}
