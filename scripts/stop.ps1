$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (Test-Path '.local\processes.json') {
    $savedProcesses = Get-Content -Raw '.local\processes.json' | ConvertFrom-Json
    foreach ($savedId in @($savedProcesses.backend, $savedProcesses.frontend)) {
        $activeProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$savedId" -ErrorAction SilentlyContinue
        $projectRoot = (Get-Location).Path
        $isCurrentProject = $activeProcess.CommandLine -and $activeProcess.CommandLine.IndexOf($projectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0
        if ($isCurrentProject -and ($activeProcess.CommandLine -match 'uvicorn\s+backend\.app\.main:app|vite[\\/]bin[\\/]vite\.js')) {
            taskkill /PID $savedId /T /F 2>$null | Out-Null
        }
    }
}
