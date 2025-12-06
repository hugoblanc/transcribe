# Transcribe - Windows Installation Script
# Run with: powershell -ExecutionPolicy Bypass -File install_windows.ps1

Write-Host "=== Installing Transcribe ===" -ForegroundColor Cyan
Write-Host ""

# Check Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host "Please install Python 3.9+ from https://python.org"
    exit 1
}
Write-Host "Found: $pythonVersion" -ForegroundColor Green

# Check if in project directory
if (-not (Test-Path "pyproject.toml")) {
    Write-Host "ERROR: Run this script from the project directory" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "[1/3] Creating virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
}

# Activate venv
Write-Host "[2/3] Activating environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "[3/3] Installing dependencies (this may take a few minutes)..." -ForegroundColor Yellow
pip install --upgrade pip -q
pip install -e . -q

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "To use Transcribe:" -ForegroundColor Cyan
Write-Host "  1. Activate: .\venv\Scripts\Activate.ps1"
Write-Host "  2. Check:    transcribe check"
Write-Host "  3. Devices:  transcribe devices"
Write-Host "  4. Record:   transcribe start"
Write-Host ""
Write-Host "For system audio capture, you may need to:" -ForegroundColor Yellow
Write-Host "  - Enable 'Stereo Mix' in Windows Sound settings"
Write-Host "  - Or use a virtual audio cable"
Write-Host ""
