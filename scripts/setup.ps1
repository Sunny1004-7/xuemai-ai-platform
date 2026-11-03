$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location (Split-Path $PSScriptRoot -Parent)
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
