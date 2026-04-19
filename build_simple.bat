@echo off
REM Simple Build Script for CorelDRAW Automation Toolkit
REM This is a simpler alternative to build.bat

title Building CorelDRAW Automation Toolkit...

echo ========================================
echo CorelDRAW Automation Toolkit - Quick Build
echo ========================================
echo.

cd /d "%~dp0"

REM Check for Python
set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
)
if not defined PYTHON_EXE (
    for %%V in (311 310 39 38) do (
        if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" (
            "%LocalAppData%\Programs\Python\Python%%V\python.exe" --version >nul 2>&1
            if not errorlevel 1 set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python%%V\python.exe"
        )
    )
)
if not defined PYTHON_EXE set "PYTHON_EXE=python"

"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.8-3.11, add it to PATH, or create .venv in the project root
    pause
    exit /b 1
)

echo Python found:
"%PYTHON_EXE%" --version
echo.

REM Clean old builds
echo Cleaning old builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Check/Install PyInstaller
echo.
echo Checking PyInstaller...
"%PYTHON_EXE%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    "%PYTHON_EXE%" -m pip install pyinstaller
)

echo Installing runtime dependencies...
"%PYTHON_EXE%" -m pip install PyQt5 pywin32 pillow numpy opencv-python svgwrite
if errorlevel 1 (
    echo ERROR: Failed to install runtime dependencies!
    pause
    exit /b 1
)

REM Build
echo.
echo ========================================
echo Building executable...
echo ========================================
echo This will take 5-10 minutes...
echo.

"%PYTHON_EXE%" -m PyInstaller CorelDRAW_Automation_Toolkit.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    echo.
    echo Try installing dependencies manually:
    echo   pip install PyQt5 pywin32 pillow pyinstaller
    echo.
    pause
    exit /b 1
)

REM Check result
if exist "dist\CorelDRAW_Automation_Toolkit\CorelDRAW_Automation_Toolkit.exe" (
    echo.
    echo ========================================
    echo BUILD SUCCESSFUL!
    echo ========================================
    echo.
    echo Your new executable is at:
    echo   dist\CorelDRAW_Automation_Toolkit\CorelDRAW_Automation_Toolkit.exe
    echo.
    echo To share:
    echo   1. ZIP the folder: dist\CorelDRAW_Automation_Toolkit
    echo   2. Send the ZIP file to users
    echo   3. Users extract and run the .exe
    echo.
) else (
    echo ERROR: Executable not found!
    echo Build may have failed.
    pause
    exit /b 1
)

pause
