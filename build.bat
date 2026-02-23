@echo off
setlocal EnableDelayedExpansion
REM CorelDRAW Automation Toolkit - Complete Build Script
REM Creates a shareable installer with auto-dependency installation

title CorelDRAW Automation Toolkit Builder

echo ========================================
echo CorelDRAW Automation Toolkit Builder
echo Version: 0.1.0-beta
echo ========================================
echo.

REM Store original directory
set "ORIGINAL_DIR=%CD%"
cd /d "%~dp0"
set "PROJECT_ROOT=%CD%"

REM Try to auto-fix Python PATH before checks
call :ensure_python_path

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Please install Python 3.8 or higher:
    echo   1. Visit https://python.org/downloads/
    echo   2. Download Python 3.8 - 3.11 (NOT 3.12+)
    echo   3. Check "Add Python to PATH" during installation
    echo   4. Restart this script
    echo.
    pause
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%I in ('python --version 2^>^&1') do set PYTHON_VERSION=%%I
echo [INFO] Found Python %PYTHON_VERSION%

REM Check Python version (3.8 - 3.11 recommended)
python -c "import sys; v=sys.version_info; exit(0 if v.major==3 and v.minor>=8 and v.minor<=11 else 1)" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Python version %PYTHON_VERSION% may have compatibility issues
    echo [WARNING] Recommended: Python 3.8 - 3.11
    echo.
    choice /C YN /M "Continue anyway"
    if errorlevel 2 exit /b 1
)

echo.
echo ========================================
echo [1/7] Creating build environment...
echo ========================================
echo.

REM Clean previous build environment
if exist "build_venv" (
    echo Cleaning previous build environment...
    rmdir /s /q "build_venv" 2>nul
    if exist "build_venv" (
        echo [WARNING] Could not remove build_venv completely
        echo [WARNING] Please close any programs using it and retry
        pause
    )
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv "build_venv"
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

REM Activate virtual environment
call "build_venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

echo.
echo ========================================
echo [2/7] Installing dependencies...
echo ========================================
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip
    goto :cleanup_error
)

REM Install core dependencies
echo Installing PyQt5...
pip install PyQt5==5.15.10
if errorlevel 1 (
    echo [ERROR] Failed to install PyQt5
    goto :cleanup_error
)

echo Installing pywin32...
pip install pywin32==306
if errorlevel 1 (
    echo [ERROR] Failed to install pywin32
    goto :cleanup_error
)

REM Install pywin32 post-install hooks
python -m pywin32_postinstall -install -silent >nul 2>&1

echo Installing pillow...
pip install pillow==10.2.0
if errorlevel 1 (
    echo [ERROR] Failed to install pillow
    goto :cleanup_error
)

echo.
echo ========================================
echo [3/7] Installing PyInstaller...
echo ========================================
echo.

echo Installing PyInstaller...
pip install pyinstaller==6.3.0
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller
    goto :cleanup_error
)

echo.
echo ========================================
echo [4/7] Building executable...
echo ========================================
echo.
echo This may take 5-15 minutes depending on your system...
echo.

REM Clean previous builds
echo Cleaning previous builds...
if exist "dist" rmdir /s /q "dist" 2>nul
if exist "build" rmdir /s /q "build" 2>nul

REM Build with PyInstaller
echo Starting PyInstaller build...
pyinstaller CorelDRAW_Automation_Toolkit.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed!
    echo.
    echo Common issues:
    echo   1. Missing dependencies - check output above
    echo   2. Permission denied - run as Administrator
    echo   3. Antivirus blocking - temporarily disable AV
    echo.
    goto :cleanup_error
)

REM Check if executable was created
if not exist "dist\CorelDRAW_Automation_Toolkit\CorelDRAW_Automation_Toolkit.exe" (
    echo [ERROR] Executable was not created!
    echo [ERROR] Check build output for errors
    goto :cleanup_error
)

echo.
echo ========================================
echo [5/7] Creating installer directory...
echo ========================================
echo.

if not exist "dist\installer" mkdir "dist\installer"

REM Calculate file size
set "EXE_PATH=dist\CorelDRAW_Automation_Toolkit\CorelDRAW_Automation_Toolkit.exe"
for %%I in ("%EXE_PATH%") do set EXE_SIZE=%%~zI

echo Executable created successfully!
echo Size: %EXE_SIZE% bytes
echo.

echo Cleaning unused cache files...
for %%S in (src installer docs examples scripts) do (
    if exist "%%S" (
        for /d /r "%%S" %%D in (__pycache__) do rmdir /s /q "%%D" >nul 2>&1
        for /r "%%S" %%F in (*.pyc) do del /q "%%F" >nul 2>&1
        for /r "%%S" %%F in (*.pyo) do del /q "%%F" >nul 2>&1
    )
)
if exist "sys" del /q "sys" >nul 2>&1

echo ========================================
echo [6/7] Building installer...
echo ========================================
echo.

REM Check for Inno Setup
where iscc >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Inno Setup not found in PATH
    echo.
    echo The standalone executable is ready at:
    echo   dist\CorelDRAW_Automation_Toolkit\CorelDRAW_Automation_Toolkit.exe
    echo.
    echo To create an installer:
    echo   1. Download Inno Setup from https://jrsoftware.org/isinfo.php
    echo   2. Install it with default settings
    echo   3. Run this script again
    echo.
    goto :skip_installer
)

echo Found Inno Setup, building installer...
iscc installer\inno_setup.iss
if errorlevel 1 (
    echo [WARNING] Inno Setup compilation failed
    echo [WARNING] The executable is still available
    goto :skip_installer
)

echo.
echo Installer created successfully!
echo.

:skip_installer

echo.
echo ========================================
echo [7/7] Creating distribution package...
echo ========================================
echo.

REM Create ZIP package
echo Creating ZIP archive...
if exist "dist\CorelDRAW_Automation_Toolkit_0.1.0-beta.zip" del "dist\CorelDRAW_Automation_Toolkit_0.1.0-beta.zip"

powershell -Command "Compress-Archive -Path 'dist\CorelDRAW_Automation_Toolkit' -DestinationPath 'dist\CorelDRAW_Automation_Toolkit_0.1.0-beta.zip' -Force"
if errorlevel 1 (
    echo [WARNING] Failed to create ZIP archive
) else (
    echo ZIP archive created: dist\CorelDRAW_Automation_Toolkit_0.1.0-beta.zip
)

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Output files:
echo ----------------------------------------
if exist "dist\CorelDRAW_Automation_Toolkit\CorelDRAW_Automation_Toolkit.exe" (
    echo [OK] Standalone Executable:
    echo    dist\CorelDRAW_Automation_Toolkit\CorelDRAW_Automation_Toolkit.exe
    echo.
)
if exist "dist\CorelDRAW_Automation_Toolkit_0.1.0-beta.zip" (
    echo [OK] ZIP Package:
    echo    dist\CorelDRAW_Automation_Toolkit_0.1.0-beta.zip
    echo.
)
if exist "dist\installer\CorelDRAW_Automation_Toolkit_Setup_0.1.0-beta.exe" (
    echo [OK] Windows Installer:
    echo    dist\installer\CorelDRAW_Automation_Toolkit_Setup_0.1.0-beta.exe
    echo.
)
echo ----------------------------------------
echo.
echo Distribution options:
echo.
echo Option 1: Share the ZIP file
echo   - Easy to share via email/cloud
echo   - User extracts and runs
echo.
echo Option 2: Share the Installer
echo   - Professional installation experience
echo   - Creates shortcuts and Start Menu entries
echo   - Easy uninstall via Control Panel
echo.
echo Option 3: Share the entire folder
echo   - Best for development/testing
echo   - Copy dist\CorelDRAW_Automation_Toolkit folder
echo.
echo System Requirements for users:
echo   - Windows 10/11 64-bit
echo   - CorelDRAW 2018 or higher
echo   - 4GB RAM minimum
echo   - 200MB disk space
echo.

REM Cleanup
echo Cleaning up...
call "build_venv\Scripts\deactivate.bat" 2>nul
rmdir /s /q "build_venv" 2>nul

choice /C YN /M "Launch executable now"
if errorlevel 2 (
    echo [INFO] Skipped auto-launch.
) else (
    echo Launching executable...
    start "" "%PROJECT_ROOT%\%EXE_PATH%"
    if errorlevel 1 (
        echo [WARNING] Could not launch executable automatically.
        echo [INFO] Run manually: %EXE_PATH%
    )
)

echo Done!
echo.
cd /d "%ORIGINAL_DIR%"
pause
exit /b 0

:ensure_python_path
where python >nul 2>&1
if not errorlevel 1 goto :eof

set "PY_EXE="
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%P"
if not defined PY_EXE goto :eof

for %%I in ("%PY_EXE%") do set "PY_DIR=%%~dpI"
if not defined PY_DIR goto :eof
set "PY_DIR=%PY_DIR:~0,-1%"
set "SCRIPTS_DIR=%PY_DIR%\Scripts"

echo [INFO] Found Python via launcher. Adding Python to PATH automatically...
echo %PATH% | find /I "%PY_DIR%" >nul || set "PATH=%PY_DIR%;%PATH%"
if exist "%SCRIPTS_DIR%" (
    echo %PATH% | find /I "%SCRIPTS_DIR%" >nul || set "PATH=%SCRIPTS_DIR%;%PATH%"
)
echo [INFO] PATH updated for this build session.
goto :eof

:cleanup_error
echo.
echo Cleaning up after error...
call "build_venv\Scripts\deactivate.bat" 2>nul
rmdir /s /q "build_venv" 2>nul
cd /d "%ORIGINAL_DIR%"
pause
exit /b 1
