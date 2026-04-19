#!/usr/bin/env python
"""
Simple Installer Builder for CorelDRAW Automation Toolkit
Creates a Windows installer with desktop/start menu shortcuts
"""

import os
import sys
import shutil
import zipfile
import tempfile
import subprocess
from pathlib import Path

APP_NAME = "CorelDRAW Automation Toolkit"
APP_VERSION = "1.0.0"
EXE_NAME = "CorelDRAW_Automation_Toolkit.exe"
INSTALL_DIR = f"dist\\{APP_NAME}_Setup_{APP_VERSION}.exe"

def create_installer():
    """Create a self-extracting installer."""
    
    dist_dir = Path("dist")
    exe_path = dist_dir / EXE_NAME
    
    if not exe_path.exists():
        print(f"ERROR: Executable not found at {exe_path}")
        print("Please build with PyInstaller first:")
        print("  pyinstaller CorelDRAW_Automation_Toolkit.spec")
        return False
    
    # Create temp directory for installer files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Copy main exe
        shutil.copy2(exe_path, tmppath / EXE_NAME)
        
        # Copy license if exists
        if Path("LICENSE.txt").exists():
            shutil.copy2("LICENSE.txt", tmppath / "LICENSE.txt")
        
        # Create installer script
        installer_script = tmppath / "install.py"
        installer_content = '''#!/usr/bin/env python
import os
import sys
import shutil
import subprocess
from pathlib import Path

APP_NAME = "CorelDRAW Automation Toolkit"
APP_VERSION = "1.0.0"
EXE_NAME = "CorelDRAW_Automation_Toolkit.exe"

def get_install_dir():
    """Get the installation directory."""
    return Path(os.environ.get("PROGRAMFILES", "C:\\\\Program Files")) / APP_NAME

def create_shortcut(path, target, description=""):
    """Create a Windows shortcut using PowerShell."""
    import win32com.client
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(path))
    shortcut.TargetPath = str(target)
    shortcut.Description = description
    shortcut.WorkingDirectory = str(target.parent)
    shortcut.Save()

def install():
    """Install the application."""
    install_dir = get_install_dir()
    
    print(f"Installing {APP_NAME} {APP_VERSION}...")
    print(f"Destination: {install_dir}")
    
    # Create install directory
    install_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy files
    src_dir = Path(sys.executable).parent
    for f in [r"{exe_name}", "LICENSE.txt"]:
        src_file = src_dir / f
        if src_file.exists():
            shutil.copy2(src_file, install_dir / f)
            print(f"  Copied: {f}")
    
    exe_path = install_dir / EXE_NAME
    
    # Create Start Menu shortcuts
    start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
    start_menu.mkdir(parents=True, exist_ok=True)
    
    # Main app shortcut
    create_shortcut(start_menu / f"{APP_NAME}.lnk", exe_path, "Run CorelDRAW Automation Toolkit")
    print(f"  Created Start Menu shortcut")
    
    # Desktop shortcut
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    create_shortcut(desktop / f"{APP_NAME}.lnk", exe_path, "Run CorelDRAW Automation Toolkit")
    print(f"  Created Desktop shortcut")
    
    # Write uninstaller
    uninstall_content = f'''#!/usr/bin/env python
import os
import sys
import shutil
from pathlib import Path
import win32com.client

APP_NAME = "{APP_NAME}"
INSTALL_DIR = Path(os.environ.get("PROGRAMFILES", "C:\\\\Program Files")) / APP_NAME

def uninstall():
    print(f"Uninstalling {{APP_NAME}}...")
    
    # Remove installation directory
    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR)
        print(f"  Removed: {{INSTALL_DIR}}")
    
    # Remove shortcuts
    start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
    if start_menu.exists():
        shutil.rmtree(start_menu)
        print(f"  Removed Start Menu folder")
    
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop" / f"{{APP_NAME}}.lnk"
    if desktop.exists():
        desktop.unlink()
        print(f"  Removed Desktop shortcut")
    
    print("Uninstallation complete!")

if __name__ == "__main__":
    uninstall()
'''
    
    with open(install_dir / "uninstall.py", "w") as f:
        f.write(uninstall_content)
    
    # Register with Windows
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "CorelDRAW Automation Team")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'python "{install_dir}\\uninstall.py"')
        winreg.CloseKey(key)
        print(f"  Registered with Windows")
    except Exception as e:
        print(f"  Warning: Could not register with Windows: {e}")
    
    print(f"\\nInstallation complete!")
    print(f"Launch from Desktop shortcut or Start Menu")
    
    # Ask to launch
    if input("\\nLaunch now? (Y/n): ").lower() != 'n':
        subprocess.Popen([str(exe_path)])

def uninstall():
    """Uninstall the application."""
    install_dir = get_install_dir()
    
    if not install_dir.exists():
        print("Application not installed.")
        return
    
    # Run uninstaller
    uninstaller = install_dir / "uninstall.py"
    if uninstaller.exists():
        subprocess.Popen([sys.executable, str(uninstaller)])
    else:
        # Manual cleanup
        import win32com.client
        import winreg
        
        shutil.rmtree(install_dir)
        
        start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
        if start_menu.exists():
            shutil.rmtree(start_menu)
        
        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop" / f"{APP_NAME}.lnk"
        if desktop.exists():
            desktop.unlink()
        
        print("Uninstallation complete!")

if __name__ == "__main__":
    # Check if running from extracted installer
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        uninstall()
    else:
        install()
'''.format(exe_name=EXE_NAME, APP_NAME=APP_NAME, APP_VERSION=APP_VERSION)
        
        with open(installer_script, "w") as f:
            f.write(installer_content)
        
        # Create launcher batch file
        launcher_bat = tmppath / "install.bat"
        with open(launcher_bat, "w") as f:
            f.write(f'''@echo off
python "%~dp0install.py" %*
''')
        
        # Create zip file
        zip_path = Path("dist") / f"{APP_NAME}_Setup_{APP_VERSION}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(exe_path, EXE_NAME)
            zf.write(installer_script, "install.py")
            zf.write(launcher_bat, "install.bat")
            if Path("LICENSE.txt").exists():
                zf.write("LICENSE.txt", "LICENSE.txt")
        
        print(f"Created: {zip_path}")
        
        # Create self-extracting archive using PowerShell
        sfx_script = tmppath / "make_sfx.ps1"
        with open(sfx_script, "w") as f:
            f.write(f'''
$zipPath = "{zip_path}"
$outputPath = "{INSTALL_DIR}"

# Read the zip file
$zipBytes = [System.IO.File]::ReadAllBytes($zipPath)

# Create a self-extracting exe
$exeTemplate = @'
using System;
using System.IO;
using System.Diagnostics;
using System.IO.Compression;

class Installer
{{
    static void Main(string[] args)
    {{
        string tempZip = Path.Combine(Path.GetTempPath(), "install.zip");
        string appDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "CorelDRAW Automation Toolkit");
        
        // Extract embedded zip
        var assembly = System.Reflection.Assembly.GetExecutingAssembly();
        using (var stream = assembly.GetManifestResourceStream("install.zip"))
        {{
            using (var fileStream = new FileStream(tempZip, FileMode.Create))
            {{
                stream.CopyTo(fileStream);
            }}
        }}
        
        // Extract zip
        ZipFile.ExtractToDirectory(tempZip, appDir);
        File.Delete(tempZip);
        
        // Create shortcuts
        CreateShortcut(Environment.GetFolderPath(Environment.SpecialFolder.Desktop), "CorelDRAW Automation Toolkit.lnk", Path.Combine(appDir, "CorelDRAW_Automation_Toolkit.exe"));
        string startMenu = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.StartMenu), "Programs", "CorelDRAW Automation Toolkit");
        Directory.CreateDirectory(startMenu);
        CreateShortcut(Path.Combine(startMenu, "CorelDRAW Automation Toolkit.lnk"), Path.Combine(appDir, "CorelDRAW_Automation_Toolkit.exe"));
        
        // Launch app
        Process.Start(Path.Combine(appDir, "CorelDRAW_Automation_Toolkit.exe"));
    }}
    
    static void CreateShortcut(string path, string name, string target)
    {{
        // Using WScript for shortcut creation
        var shell = new COMObject("WScript.Shell");
        var shortcut = (IWshShortcut)shell.CreateShortcut(Path.Combine(path, name));
        shortcut.TargetPath = target;
        shortcut.Save();
    }}
}}
'@

# For simplicity, let's just copy the zip as a "portable" installer
Copy-Item $zipPath $outputPath -Force
Write-Host "Installer created at: $outputPath"
''')
        
        # Since creating a true SFX is complex, let's just provide instructions
        print(f"""
========================================
Installer Package Created Successfully!
========================================

Location: {zip_path}

To distribute:
1. Share the zip file with users
2. Users extract and run install.py

For a proper Windows installer, you'll need NSIS.
Download from: https://nsis.sourceforge.io/Download

Current options:
- Portable: dist\\{EXE_NAME}
- Zip package: {zip_path}
""")
        
    return True

if __name__ == "__main__":
    create_installer()
