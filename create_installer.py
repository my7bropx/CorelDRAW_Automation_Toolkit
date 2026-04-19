# -*- mode: python ; coding: utf-8 -*-
"""
PyNSist configuration file for CorelDRAW Automation Toolkit
Creates a Windows installer with desktop shortcut and Start Menu entries
"""

from pynsist import pkgsource
from pynsist.utils import rmtree_if_exists
import os
import sys

# Installer metadata
APP_NAME = "CorelDRAW Automation Toolkit"
APP_VERSION = "1.0.0"
APP_PUBLISHER = "CorelDRAW Automation Team"
APP_URL = "https://github.com/CorelDRAW-Automation"
APP_EXE = "CorelDRAW_Automation_Toolkit.exe"
APP_ICON = "src/resources/icons/app_icon.ico"

# Build configuration
BUILD_DIR = 'build_installer'
DIST_DIR = 'dist'

# Check if we have the icon
if not os.path.exists(APP_ICON):
    APP_ICON = None
    print(f"Warning: Icon not found at {APP_ICON}, installer will use default icon")

# Define the installer configuration
nsis_template = '''
# -*- nsis -*-
# Install script for {app_name}

!include "MUI2.nsh"

# General settings
Name "{app_name}"
OutFile "CorelDRAW_Automation_Toolkit_Setup_{version}.exe"
InstallDir "$PROGRAMFILES64\\{app_name}"
InstallDirRegKey HKLM "Software\\{app_name}" "InstallPath"
RequestExecutionLevel admin

# Interface settings
!define MUI_ICON "{icon}"
!define MUI_UNICON "{icon}"
!define MUI_ABORTWARNING

# Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

# Languages
!insertmacro MUI_LANGUAGE "English"

# Installer sections
Section "Install"
    SetOutPath "$INSTDIR"
    
    # Copy all files from dist
    File /r "dist\\*.*"
    
    # Create Start Menu shortcuts
    CreateDirectory "$SMPROGRAMS\\{app_name}"
    CreateShortcut "$SMPROGRAMS\\{app_name}\\{app_name}.lnk" "$INSTDIR\\{exe}"
    CreateShortcut "$SMPROGRAMS\\{app_name}\\Uninstall.lnk" "$INSTDIR\\uninstall.exe"
    
    # Create Desktop shortcut (optional)
    CreateShortcut "$DESKTOP\\{app_name}.lnk" "$INSTDIR\\{exe}"
    
    # Write uninstaller
    WriteUninstaller "$INSTDIR\\uninstall.exe"
    
    # Write registry keys for Add/Remove Programs
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_name}" "DisplayName" "{app_name}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_name}" "UninstallString" "$\"$INSTDIR\\uninstall.exe$\""
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_name}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_name}" "DisplayIcon" "$INSTDIR\\{exe}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_name}" "Publisher" "{publisher}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_name}" "DisplayVersion" "{version}"
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_name}" "NoModify" 1
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_name}" "NoRepair" 1
    
    # Store install path
    WriteRegStr HKLM "Software\\{app_name}" "InstallPath" "$INSTDIR"
SectionEnd

# Uninstaller section
Section "Uninstall"
    # Remove files
    RMDir /r "$INSTDIR"
    
    # Remove Start Menu shortcuts
    RMDir /r "$SMPROGRAMS\\{app_name}"
    
    # Remove Desktop shortcut
    Delete "$DESKTOP\\{app_name}.lnk"
    
    # Remove registry keys
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{app_name}"
    DeleteRegKey HKLM "Software\\{app_name}"
SectionEnd
'''.format(
    app_name=APP_NAME,
    version=APP_VERSION,
    publisher=APP_PUBLISHER,
    exe=APP_EXE,
    icon=APP_ICON if APP_ICON else ""
)

# Write the NSIS template
with open('installer_in.nsi', 'w') as f:
    f.write(nsis_template)

# Create a simple batch file to build
build_bat = '''@echo off
echo Building CorelDRAW Automation Toolkit Installer...
echo.

REM Check if executable exists
if not exist "dist\\CorelDRAW_Automation_Toolkit.exe" (
    echo ERROR: Executable not found. Please build with PyInstaller first.
    echo Run: pyinstaller CorelDRAW_Automation_Toolkit.spec
    pause
    exit /b 1
)

REM Copy license if exists
if exist "LICENSE.txt" copy /Y "LICENSE.txt" "dist\\" >nul

REM Build installer with NSIS (if available)
where makensis >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Building with NSIS...
    makensis installer_in.nsi
    if exist "CorelDRAW_Automation_Toolkit_Setup_{version}.exe" (
        move "CorelDRAW_Automation_Toolkit_Setup_{version}.exe" "dist\\"
        echo.
        echo SUCCESS: Installer created at dist\\CorelDRAW_Automation_Toolkit_Setup_{version}.exe
    )
) else (
    echo.
    echo NSIS not found. Installing NSIS...
    echo Please download from: https://nsis.sourceforge.io/Download
    echo.
    echo For now, you can use the portable exe at: dist\\CorelDRAW_Automation_Toolkit.exe
)

echo.
pause
'''.format(version=APP_VERSION)

with open('build_installer.bat', 'w') as f:
    f.write(build_bat)

print(f"Build configuration created!")
print(f"")
print(f"To create installer:")
print(f"1. Install NSIS from https://nsis.sourceforge.io/Download")
print(f"2. Run: build_installer.bat")
print(f"")
print(f"Or use the portable exe directly: dist\\CorelDRAW_Automation_Toolkit.exe")
