[Version]
Class=IEXPRESS
SEDVersion=3

[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimation=0
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=F:\CorelDRAW_Automation_Toolkit\dist\CorelDRAW_Automation_Toolkit_Setup_1.0.0.exe
FriendlyName=CorelDRAW Automation Toolkit Setup
AppLaunched=cmd /c iexpress_install.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=cmd /c iexpress_install.cmd
UserQuietInstCmd=cmd /c iexpress_install.cmd
SourceFiles=SourceFiles

[Strings]
FILE0=CorelDRAW_Automation_Toolkit.exe
FILE1=iexpress_install.cmd
FILE2=iexpress_install.ps1
FILE3=LICENSE
InstallPrompt=
DisplayLicense=
FinishMessage=CorelDRAW Automation Toolkit installer has finished.

[SourceFiles]
SourceFiles0=F:\CorelDRAW_Automation_Toolkit\dist
SourceFiles1=F:\CorelDRAW_Automation_Toolkit\installer
SourceFiles2=F:\CorelDRAW_Automation_Toolkit

[SourceFiles0]
%FILE0%=

[SourceFiles1]
%FILE1%=
%FILE2%=

[SourceFiles2]
%FILE3%=
