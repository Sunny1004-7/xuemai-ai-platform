$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (Test-Path '.local\processes.json') {
    $savedProcesses = Get-Content -Raw '.local\processes.json' | ConvertFrom-Json
    foreach ($savedId in @($savedProcesses.backend, $savedProcesses.frontend)) {
        $activeProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$savedId" -ErrorAction SilentlyContinue
        if ($activeProcess -and ($activeProcess.CommandLine -match 'uvicorn backend.app.main|npm run dev')) {
            taskkill /PID $savedId /T /F 2>$null | Out-Null
        }
    }
}
