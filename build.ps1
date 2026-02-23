# CorelDRAW Automation Toolkit - PowerShell Build Script
# Run with: .\build.ps1

param(
    [switch]$Clean,
    [switch]$NoDeps,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
CorelDRAW Automation Toolkit Build Script

Usage:
    .\build.ps1           - Full build
    .\build.ps1 -Clean    - Clean build (remove old files)
    .\build.ps1 -NoDeps   - Skip dependency check
    .\build.ps1 -Help     - Show this help

Requirements:
    - Python 3.8-3.11
    - pip
    - ~500MB free disk space

Output:
    - dist\CorelDRAW_Automation_Toolkit\CorelDRAW_Automation_Toolkit.exe
"@
    exit
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CorelDRAW Automation Toolkit Builder" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host "Please install Python 3.8-3.11 from https://python.org"
    Write-Host "Make sure to check 'Add Python to PATH'"
    exit 1
}

# Clean if requested
if ($Clean) {
    Write-Host ""
    Write-Host "Cleaning old builds..." -ForegroundColor Yellow
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    Write-Host "Clean complete" -ForegroundColor Green
}

# Install dependencies
if (-not $NoDeps) {
    Write-Host ""
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    
    $deps = @("PyQt5", "pywin32", "pillow", "pyinstaller")
    foreach ($dep in $deps) {
        Write-Host "  Installing $dep..." -ForegroundColor Gray
        pip install $dep -q
    }
    
    # Run pywin32 post-install
    python -m pywin32_postinstall -install -silent 2>$null
    
    Write-Host "Dependencies installed" -ForegroundColor Green
}

# Build
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building executable..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "This will take 5-10 minutes..." -ForegroundColor Yellow
Write-Host ""

pyinstaller CorelDRAW_Automation_Toolkit.spec --clean --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Build failed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Try running these commands manually:" -ForegroundColor Yellow
    Write-Host "  pip install PyQt5 pywin32 pillow pyinstaller"
    Write-Host "  pyinstaller CorelDRAW_Automation_Toolkit.spec --clean"
    exit 1
}

# Check result
$exePath = "dist\CorelDRAW_Automation_Toolkit\CorelDRAW_Automation_Toolkit.exe"
if (Test-Path $exePath) {
    $exeSize = (Get-Item $exePath).Length / 1MB
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable: $exePath" -ForegroundColor White
    Write-Host "Size: $([math]::Round($exeSize, 2)) MB" -ForegroundColor White
    Write-Host ""
    Write-Host "To share with others:" -ForegroundColor Yellow
    Write-Host "  1. ZIP the folder: dist\CorelDRAW_Automation_Toolkit" -ForegroundColor White
    Write-Host "  2. Send the ZIP file" -ForegroundColor White
    Write-Host "  3. Users extract and run CorelDRAW_Automation_Toolkit.exe" -ForegroundColor White
    Write-Host ""
    
    # Create ZIP
    $zipPath = "dist\CorelDRAW_Automation_Toolkit.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath }
    
    Write-Host "Creating ZIP package..." -ForegroundColor Yellow
    Compress-Archive -Path "dist\CorelDRAW_Automation_Toolkit" -DestinationPath $zipPath -Force
    
    $zipSize = (Get-Item $zipPath).Length / 1MB
    Write-Host "ZIP created: $zipPath ($([math]::Round($zipSize, 2)) MB)" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "ERROR: Executable not found!" -ForegroundColor Red
    exit 1
}

Write-Host "Press any key to continue..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
