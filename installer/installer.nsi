; CorelDRAW Automation Toolkit - NSIS Installer Script
; Creates installer with desktop and start menu shortcuts

!include "MUI2.nsh"
!include "FileFunc.nsh"

; General
Name "CorelDRAW Automation Toolkit"
OutFile "dist\CorelDRAW_Automation_Toolkit_Setup_1.0.0.exe"
InstallDir "$PROGRAMFILES64\CorelDRAW Automation Toolkit"
InstallDirRegKey HKLM "Software\CorelDRAW Automation Toolkit" "InstallPath"
RequestExecutionLevel admin

; Version info
VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "CorelDRAW Automation Toolkit"
VIAddVersionKey "CompanyName" "CorelDRAW Automation Team"
VIAddVersionKey "FileDescription" "CorelDRAW Automation Toolkit Installer"
VIAddVersionKey "FileVersion" "1.0.0"
VIAddVersionKey "ProductVersion" "1.0.0"
VIAddVersionKey "LegalCopyright" "Copyright (c) 2024"

; Interface Settings
!define MUI_ABORTWARNING
!define MUI_ICON "src\resources\icons\app_icon.ico"
!define MUI_UNICON "src\resources\icons\app_icon.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Language
!insertmacro MUI_LANGUAGE "English"

; Installer Section
Section "Install"
    SetOutPath "$INSTDIR"
    
    ; Copy main executable
    File "dist\CorelDRAW_Automation_Toolkit.exe"
    
    ; Copy license if exists
    File /oname=LICENSE.txt "LICENSE.txt"
    
    ; Create Start Menu folder and shortcuts
    CreateDirectory "$SMPROGRAMS\CorelDRAW Automation Toolkit"
    CreateShortcut "$SMPROGRAMS\CorelDRAW Automation Toolkit\CorelDRAW Automation Toolkit.lnk" "$INSTDIR\CorelDRAW_Automation_Toolkit.exe"
    CreateShortcut "$SMPROGRAMS\CorelDRAW Automation Toolkit\Uninstall.lnk" "$INSTDIR\uninstall.exe"
    
    ; Create Desktop shortcut
    CreateShortcut "$DESKTOP\CorelDRAW Automation Toolkit.lnk" "$INSTDIR\CorelDRAW_Automation_Toolkit.exe"
    
    ; Write uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"
    
    ; Write registry for Add/Remove Programs
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit" "DisplayName" "CorelDRAW Automation Toolkit"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit" "DisplayIcon" "$INSTDIR\CorelDRAW_Automation_Toolkit.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit" "Publisher" "CorelDRAW Automation Team"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit" "DisplayVersion" "1.0.0"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit" "NoRepair" 1
    
    ; Get installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit" "EstimatedSize" "$0"
    
    ; Store install path
    WriteRegStr HKLM "Software\CorelDRAW Automation Toolkit" "InstallPath" "$INSTDIR"
SectionEnd

; Uninstaller Section
Section "Uninstall"
    ; Remove files
    Delete "$INSTDIR\CorelDRAW_Automation_Toolkit.exe"
    Delete "$INSTDIR\LICENSE.txt"
    Delete "$INSTDIR\uninstall.exe"
    RMDir "$INSTDIR"
    
    ; Remove Start Menu shortcuts
    Delete "$SMPROGRAMS\CorelDRAW Automation Toolkit\CorelDRAW Automation Toolkit.lnk"
    Delete "$SMPROGRAMS\CorelDRAW Automation Toolkit\Uninstall.lnk"
    RMDir "$SMPROGRAMS\CorelDRAW Automation Toolkit"
    
    ; Remove Desktop shortcut
    Delete "$DESKTOP\CorelDRAW Automation Toolkit.lnk"
    
    ; Remove registry keys
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\CorelDRAW_Automation_Toolkit"
    DeleteRegKey HKLM "Software\CorelDRAW Automation Toolkit"
SectionEnd
