; CorelDRAW Automation Toolkit - Inno Setup Script
; This script creates a professional Windows installer (.exe)
; Requires Inno Setup 6.0+ from https://jrsoftware.org/isinfo.php

#define MyAppName "CorelDRAW Automation Toolkit"
#define MyAppVersion "0.1.0-beta"
#define MyAppPublisher "CorelDRAW Automation Team"
#define MyAppURL "https://github.com/your-repo/CorelDRAW_Automation_Toolkit"
#define MyAppExeName "CorelDRAW_Automation_Toolkit.exe"
#define MyAppId "{{B8F5A2C3-D4E6-4F7A-8B9C-0D1E2F3A4B5C}"

[Setup]
; Basic app info
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppCopyright=Copyright (c) 2024 {#MyAppPublisher}
VersionInfoVersion=0.1.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

; Default installation settings
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=no
DisableProgramGroupPage=no

; Output settings
OutputDir=..\dist\installer
OutputBaseFilename=CorelDRAW_Automation_Toolkit_Setup_{#MyAppVersion}
SetupIconFile=..\src\resources\icons\app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMADictionarySize=1048576
LZMANumFastBytes=273

; Installer appearance
WizardStyle=modern
WizardSizePercent=100,100
WizardResizable=yes

; Permissions and architecture
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0.17763

; Other settings
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
UninstallFilesDir={app}\uninstall
ShowLanguageDialog=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Desktop shortcut
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "Shortcuts:"; Flags: unchecked

; Start Menu shortcuts
Name: "startmenu"; Description: "Create Start Menu shortcuts"; GroupDescription: "Shortcuts:"; Flags: checked

; File associations (optional)
Name: "fileassoc"; Description: "Register file associations for .cdap project files"; GroupDescription: "Integration:"; Flags: unchecked

[Files]
; Main executable and all dependencies
Source: "..\dist\CorelDRAW_Automation_Toolkit\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\CorelDRAW_Automation_Toolkit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Documentation
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs

; Examples
Source: "..\examples\*.py"; DestDir: "{app}\examples"; Flags: ignoreversion

[Icons]
; Start Menu icons
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenu
Name: "{group}\User Manual"; Filename: "{app}\docs\user_manual\QUICKSTART.md"; Tasks: startmenu
Name: "{group}\Curve Filler Guide"; Filename: "{app}\docs\user_manual\CURVE_FILLER_GUIDE.md"; Tasks: startmenu
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; Tasks: startmenu

; Desktop icon
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Launch after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; Open documentation
Filename: "{app}\docs\user_manual\QUICKSTART.md"; Description: "View Quick Start Guide"; Flags: nowait postinstall skipifsilent unchecked

[Registry]
; Register application
Root: HKLM; Subkey: "SOFTWARE\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

; Register uninstall info for Windows Settings app
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}"; ValueType: string; ValueName: "DisplayName"; ValueData: "{#MyAppName}"
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}"; ValueType: string; ValueName: "DisplayVersion"; ValueData: "{#MyAppVersion}"
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}"; ValueType: string; ValueName: "Publisher"; ValueData: "{#MyAppPublisher}"
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}"; ValueType: string; ValueName: "URLInfoAbout"; ValueData: "{#MyAppURL}"

; File association (optional)
Root: HKLM; Subkey: "SOFTWARE\Classes\.cdap"; ValueType: string; ValueName: ""; ValueData: "CorelDRAWAutomationProject"; Tasks: fileassoc
Root: HKLM; Subkey: "SOFTWARE\Classes\CorelDRAWAutomationProject"; ValueType: string; ValueName: ""; ValueData: "CorelDRAW Automation Toolkit Project"; Tasks: fileassoc
Root: HKLM; Subkey: "SOFTWARE\Classes\CorelDRAWAutomationProject\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc

[Code]
// Check if CorelDRAW is installed
function HasCorelSubkeys(const RootKey: Integer; const BaseKey: string): Boolean;
var
  Subkeys: TArrayOfString;
begin
  Result := False;
  if RegGetSubkeyNames(RootKey, BaseKey, Subkeys) then
  begin
    Result := GetArrayLength(Subkeys) > 0;
  end;
end;

function IsCorelDRAWInstalled(): Boolean;
begin
  Result := False;
  if HasCorelSubkeys(HKEY_LOCAL_MACHINE, 'SOFTWARE\Corel\CorelDRAW') then Result := True;
  if HasCorelSubkeys(HKEY_LOCAL_MACHINE, 'SOFTWARE\WOW6432Node\Corel\CorelDRAW') then Result := True;
end;

// Initialize setup
procedure InitializeWizard();
begin
  // You can add custom pages here if needed
end;

// Before installation starts
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  
  if CurPageID = wpWelcome then
  begin
    // Check for CorelDRAW (optional warning)
    if not IsCorelDRAWInstalled() then
    begin
      if MsgBox('CorelDRAW 2018 or higher was not detected on this system.' + #13#10 +
                'The application requires CorelDRAW to function properly.' + #13#10 + #13#10 +
                'Do you want to continue with installation anyway?', 
                mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False;
      end;
    end;
  end;
end;

// After installation completes
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Post-installation tasks
    Log('Installation completed successfully');
  end;
end;

// Before uninstallation
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    // Could show warning about data loss, etc.
  end;
end;

[Messages]
; Custom messages
WelcomeLabel1=Welcome to the [name] Setup Wizard
WelcomeLabel2=This will install [name/ver] on your computer.%n%nThe application requires CorelDRAW 2018 or higher.%n%nIt is recommended that you close all other applications before continuing.

[CustomMessages]
; Additional custom messages can be added here
