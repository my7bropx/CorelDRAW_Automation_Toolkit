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
InstallPrompt=
DisplayLicense=
FinishMessage=CorelDRAW Automation Toolkit installer has finished.
TargetName=F:\CorelDRAW_Automation_Toolkit\dist\CorelDRAW_Automation_Toolkit_Setup_0.1.0-beta.exe
FriendlyName=CorelDRAW Automation Toolkit Setup
AppLaunched=cmd /c iexpress_install_zip.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=cmd /c iexpress_install_zip.cmd
UserQuietInstCmd=cmd /c iexpress_install_zip.cmd
SourceFiles=SourceFiles

[Strings]
FILE0=CorelDRAW_Automation_Toolkit_payload.zip
FILE1=iexpress_install_zip.cmd
FILE2=iexpress_install_zip.ps1
FILE3=LICENSE

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
