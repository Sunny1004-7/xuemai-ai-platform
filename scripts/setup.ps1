$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location (Split-Path $PSScriptRoot -Parent)
foreach ($setupPort in @(8000,5173,5174,5175)) {
    if (Get-NetTCPConnection -LocalPort $setupPort -State Listen -ErrorAction SilentlyContinue) {
        throw "端口 $setupPort 的服务仍在运行。请先停止本项目服务，再安装依赖，避免Windows文件占用。"
    }
}
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.13 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '请安装 Python 3.13 后重试。' }
}
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw '后端依赖安装失败' }
Push-Location frontend
npm ci
if ($LASTEXITCODE -ne 0) { throw '前端依赖安装失败' }
Pop-Location
& .\.venv\Scripts\python.exe -m backend.app.db
if ($LASTEXITCODE -ne 0) { throw '数据库初始化失败' }
Write-Host '安装完成，运行 .\scripts\start.ps1 启动。默认使用本地 Mock。'
