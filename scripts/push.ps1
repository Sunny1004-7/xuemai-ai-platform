$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& .\.venv\Scripts\python.exe scripts/check_secrets.py
if ($LASTEXITCODE -ne 0) { throw '密钥扫描未通过，停止推送' }
# 开发机系统 Git 缺少 HTTPS helper；有本机官方 MinGit 时使用它。
$gitProgram = if (Test-Path '.local\mingit\cmd\git.exe') { (Resolve-Path '.local\mingit\cmd\git.exe').Path } else { 'git' }
# Windows 证书库避免中文目录下 CA 文件路径兼容问题，仍启用 TLS 验证。
& $gitProgram -c http.sslBackend=schannel push -u origin main
if ($LASTEXITCODE -ne 0) { throw '推送失败，请检查 GitHub 认证与网络' }
& $gitProgram -c http.sslBackend=schannel ls-remote origin refs/heads/main
if ($LASTEXITCODE -ne 0) { throw '远程提交校验失败' }
