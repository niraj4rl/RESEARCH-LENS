# ResearchLens Single-Command Launcher for PowerShell
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "        Starting ResearchLens (One-Command Launcher)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$RootPath = $PSScriptRoot
Set-Location $RootPath

# Detect Python
$PythonExe = Join-Path $RootPath "backend\venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $LocalPy = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $LocalPy) {
        $PythonExe = $LocalPy
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonExe = "python"
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe = "py"
    } else {
        Write-Host "[ERROR] Python not found. Please install Python 3.10+." -ForegroundColor Red
        exit 1
    }
}

& $PythonExe (Join-Path $RootPath "run.py")
