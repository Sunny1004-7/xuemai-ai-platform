$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:AI_MODE = 'mock'
& .\.venv\Scripts\python.exe -m pytest backend/tests -q
if ($LASTEXITCODE -ne 0) { throw '后端测试失败' }
& .\.venv\Scripts\python.exe scripts/check_secrets.py
if ($LASTEXITCODE -ne 0) { throw '敏感信息检查失败' }
Push-Location frontend
npm run build
if ($LASTEXITCODE -ne 0) { throw '前端构建失败' }
npm run test:e2e
if ($LASTEXITCODE -ne 0) { throw '端到端测试失败' }
Pop-Location
