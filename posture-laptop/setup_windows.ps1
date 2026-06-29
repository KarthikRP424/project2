# PostureGuard Setup Script for Windows PowerShell
# This script sets up a Python 3.11 virtual environment and installs all necessary dependencies.

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🧘 PostureGuard - Setup & Installation Wizard" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Locate or install Python 3.11
Write-Host "[1/4] Checking for Python 3.11..." -ForegroundColor Yellow

$python311Paths = @(
    "C:\Users\DELL\AppData\Local\Programs\Python\Python311\python.exe",
    "$env:USERPROFILE\AppData\Local\Programs\Python\Python311\python.exe",
    "C:\Program Files\Python311\python.exe",
    "C:\Program Files (x86)\Python311\python.exe"
)

$pythonExe = $null

foreach ($path in $python311Paths) {
    if (Test-Path $path) {
        $pythonExe = $path
        break
    }
}

if ($null -eq $pythonExe) {
    # Try searching path or winget registry
    $wherePython = Get-Command python.exe -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -like "*Python311*" }
    if ($wherePython) {
        $pythonExe = $wherePython[0].Source
    }
}

if ($null -eq $pythonExe) {
    Write-Host "Python 3.11 was not detected on your system." -ForegroundColor Cyan
    Write-Host "Attempting to install Python 3.11 automatically using winget..." -ForegroundColor Cyan
    try {
        winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements --scope user
        # Verify install location
        $userProfilePath = "$env:USERPROFILE\AppData\Local\Programs\Python\Python311\python.exe"
        if (Test-Path $userProfilePath) {
            $pythonExe = $userProfilePath
        } else {
            throw "Python 3.11 installed but python.exe not found at standard path."
        }
    } catch {
        Write-Host "Automatic installation failed. Please download and install Python 3.11 manually from:" -ForegroundColor Red
        Write-Host "https://www.python.org/downloads/release/python-3119/" -ForegroundColor Red
        Exit
    }
}

Write-Host "Using Python 3.11 path: $pythonExe" -ForegroundColor Green
$ver = & $pythonExe --version
Write-Host "Python version: $ver" -ForegroundColor Green

# 2. Recreate virtual environment
Write-Host "`n[2/4] Setting up clean virtual environment (venv)..." -ForegroundColor Yellow
if (Test-Path ".\venv") {
    Write-Host "Removing existing virtual environment..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force .\venv
}
Write-Host "Creating new virtual environment using Python 3.11..." -ForegroundColor Cyan
& $pythonExe -m venv venv
Write-Host "Virtual environment created successfully." -ForegroundColor Green

# 3. Install requirements
Write-Host "`n[3/4] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
$venvPython = ".\venv\Scripts\python.exe"

Write-Host "Upgrading pip..." -ForegroundColor DarkGray
& $venvPython -m pip install --upgrade pip

Write-Host "Installing requirements..." -ForegroundColor DarkGray
& $venvPython -m pip install -r requirements.txt
Write-Host "All dependencies installed successfully!" -ForegroundColor Green

# 4. Ready to run
Write-Host "`n[4/4] Setup complete!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "To run the application:" -ForegroundColor Yellow
Write-Host "1. Activate virtual environment:  .\venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "2. Start application:             python main.py" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# Ask if they want to run now
$response = Read-Host "`nWould you like to run the PostureGuard application now? (Y/N)"
if ($response -eq "Y" -or $response -eq "y") {
    Write-Host "Launching PostureGuard..." -ForegroundColor Green
    & $venvPython main.py
}
