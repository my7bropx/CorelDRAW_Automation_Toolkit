#!/usr/bin/env python3
"""
CorelDRAW Automation Toolkit - Build Script
Creates Windows executable and installer package
Usage:
    python build.py [options]
Options:
    --clean         Clean build directories before building
    --installer     Build installer (requires Inno Setup)
    --zip           Create ZIP distribution package
    --all           Build everything (default)
    --no-deps       Skip dependency installation (faster rebuild)
    --verbose       Show detailed output
Examples:
    python build.py                 # Full build with everything
    python build.py --clean         # Clean build
    python build.py --no-deps       # Quick rebuild without reinstalling deps
    python build.py --zip           # Build executable and ZIP only
"""
import argparse
import subprocess
import sys
import shutil
import os
from pathlib import Path
from datetime import datetime

APP_NAME = "CorelDRAW Automation Toolkit"
APP_VERSION = "0.1.0-beta"
PYTHON_MIN_VERSION = (3, 8)
PYTHON_MAX_VERSION = (3, 11)

class BuildError(Exception):
    """Custom exception for build errors."""
    pass

def log(message, level="INFO"):
    """Print formatted log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    log(f"Detected Python {version.major}.{version.minor}.{version.micro}")
    if version < PYTHON_MIN_VERSION:
        raise BuildError(
            f"Python {PYTHON_MIN_VERSION[0]}.{PYTHON_MIN_VERSION[1]}+ required, "
            f"but {version.major}.{version.minor} found"
        )
    if version > PYTHON_MAX_VERSION:
        log(
            f"Warning: Python {version.major}.{version.minor} may have compatibility issues. "
            f"Recommended: Python {PYTHON_MIN_VERSION[0]}.{PYTHON_MIN_VERSION[1]} - "
            f"{PYTHON_MAX_VERSION[0]}.{PYTHON_MAX_VERSION[1]}",
            "WARNING"
        )
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)


def clean_build_dirs(project_root):
    """Remove build directories."""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    
    for dir_name in dirs_to_clean:
        dir_path = project_root / dir_name
        if dir_path.exists():
            log(f"Cleaning {dir_name}...")
            try:
                shutil.rmtree(dir_path)
            except Exception as e:
                log(f"Warning: Could not remove {dir_name}: {e}", "WARNING")

def create_venv(project_root):
    """Create virtual environment for building."""
    venv_dir = project_root / 'build_venv'
    if venv_dir.exists():
        log("Removing old virtual environment...")
        shutil.rmtree(venv_dir)
    log("Creating virtual environment...")
    try:
        subprocess.run(
            [sys.executable, '-m', 'venv', str(venv_dir)],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        raise BuildError(f"Failed to create virtual environment: {e}")
    return venv_dir

def install_dependencies(venv_dir, skip_deps=False):
    """Install required dependencies."""
    if skip_deps:
        log("Skipping dependency installation (--no-deps)")
        return
    pip = venv_dir / 'Scripts' / 'pip.exe'
    log("Upgrading pip...")
    subprocess.run(
        [str(pip), 'install', '--upgrade', 'pip'],
        check=True
    )
    dependencies = [
        ('PyQt5', '5.15.10'),
        ('pywin32', '306'),
        ('pillow', '10.2.0'),
        ('pyinstaller', '6.3.0'),
    ]
    for package, version in dependencies:
        log(f"Installing {package}=={version}...")
        try:
            subprocess.run(
                [str(pip), 'install', f'{package}=={version}'],
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise BuildError(f"Failed to install {package}: {e}")
    
    log("Running pywin32 post-install...")
    try:
        subprocess.run(
            [str(venv_dir / 'Scripts' / 'python.exe'), '-m', 'pywin32_postinstall', '-install', '-silent'],
            check=False,
            capture_output=True
        )
    except:
        pass 


def build_executable(project_root, venv_dir):
    """Build executable with PyInstaller."""
    log("Building executable with PyInstaller...")
    log("This may take 5-15 minutes depending on your system...")
    
    pyinstaller = venv_dir / 'Scripts' / 'pyinstaller.exe'
    spec_file = project_root / 'CorelDRAW_Automation_Toolkit.spec'
    
    try:
        result = subprocess.run(
            [
                str(pyinstaller),
                str(spec_file),
                '--clean',
                '--noconfirm'
            ],
            check=True,
            capture_output=False
        )
    except subprocess.CalledProcessError as e:
        raise BuildError(
            f"PyInstaller build failed with code {e.returncode}\n"
            "Common issues:\n"
            "  - Missing dependencies\n"
            "  - Permission denied (run as Administrator)\n"
            "  - Antivirus blocking the build"
        )
    
    exe_path = project_root / 'dist' / 'CorelDRAW_Automation_Toolkit' / 'CorelDRAW_Automation_Toolkit.exe'
    if not exe_path.exists():
        raise BuildError("Executable was not created!")
    exe_size = exe_path.stat().st_size
    log(f"Executable created: {exe_path}")
    log(f"Size: {exe_size / (1024*1024):.2f} MB")
    return exe_path
def build_installer(project_root):
    """Build Windows installer with Inno Setup."""
    log("Building installer...")
    inno_path = None
    possible_paths = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 5\ISCC.exe"),
    ]
    for path in possible_paths:
        if path.exists():
            inno_path = path
            break
    if not inno_path:
        try:
            subprocess.run(['iscc', '/?'], check=True, capture_output=True)
            inno_path = 'iscc'
        except:
            log("Inno Setup not found. Skipping installer creation.", "WARNING")
            log("Download from: https://jrsoftware.org/isinfo.php", "INFO")
            return None
    iss_file = project_root / 'installer' / 'inno_setup.iss'
    try:
        subprocess.run(
            [str(inno_path), str(iss_file)],
            check=True,
            capture_output=False
        )
    except subprocess.CalledProcessError as e:
        log(f"Inno Setup failed: {e}", "WARNING")
        return None
    installer_path = project_root / 'dist' / 'installer' / f'CorelDRAW_Automation_Toolkit_Setup_{APP_VERSION}.exe'
    if installer_path.exists():
        log(f"Installer created: {installer_path}")
        installer_size = installer_path.stat().st_size
        log(f"Installer size: {installer_size / (1024*1024):.2f} MB")
        return installer_path
    return None
def create_zip_package(project_root):
    """Create ZIP distribution package."""
    log("Creating ZIP distribution package...")
    
    dist_dir = project_root / 'dist'
    zip_path = dist_dir / f'CorelDRAW_Automation_Toolkit_{APP_VERSION}.zip'
    
    if zip_path.exists():
        zip_path.unlink()
    try:
        import zipfile
        source_dir = dist_dir / 'CorelDRAW_Automation_Toolkit'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)
        zip_size = zip_path.stat().st_size
        log(f"ZIP package created: {zip_path}")
        log(f"ZIP size: {zip_size / (1024*1024):.2f} MB")
        return zip_path
    except Exception as e:
        log(f"Failed to create ZIP: {e}", "WARNING")
        return None
def print_summary(project_root, exe_path, installer_path, zip_path):
    """Print build summary."""
    print("\n" + "="*60)
    print("BUILD COMPLETE")
    print("="*60)
    print("\nOutput files:")
    print("-"*60)
    if exe_path and exe_path.exists():
        print(f"[OK] Executable:")
        print(f"     {exe_path}")
        print(f"     Size: {exe_path.stat().st_size / (1024*1024):.2f} MB")
        print()
    if zip_path and zip_path.exists():
        print(f"[OK] ZIP Package:")
        print(f"     {zip_path}")
        print(f"     Size: {zip_path.stat().st_size / (1024*1024):.2f} MB")
        print()
    if installer_path and installer_path.exists():
        print(f"[OK] Windows Installer:")
        print(f"     {installer_path}")
        print(f"     Size: {installer_path.stat().st_size / (1024*1024):.2f} MB")
        print()
    print("-"*60)
    print("\nDistribution options:")
    print("\nOption 1: Share the ZIP file (Easiest)")
    print("  - Copy the ZIP file and share via email/cloud")
    print("  - User extracts and runs the executable")
    print("\nOption 2: Share the Installer (Professional)")
    print("  - Creates Start Menu shortcuts")
    print("  - Adds uninstall option in Control Panel")
    print("  - Better user experience")
    print("\nOption 3: Share the folder (Development/Testing)")
    print("  - Copy the entire dist/CorelDRAW_Automation_Toolkit folder")
    print("  - Best for testing on other machines")
    print("\nSystem Requirements for end users:")
    print("  - Windows 10/11 64-bit")
    print("  - CorelDRAW 2018 or higher")
    print("  - 4GB RAM minimum")
    print("  - 200MB disk space")
    print("\n" + "="*60)
def main():
    parser = argparse.ArgumentParser(
        description='Build CorelDRAW Automation Toolkit executable and installer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--clean', action='store_true', help='Clean build directories first')
    parser.add_argument('--installer', action='store_true', help='Build installer')
    parser.add_argument('--zip', action='store_true', help='Create ZIP package')
    parser.add_argument('--all', action='store_true', help='Build everything (default)')
    parser.add_argument('--no-deps', action='store_true', help='Skip dependency installation')
    parser.add_argument('--verbose', action='store_true', help='Show detailed output')
    args = parser.parse_args()
    if not (args.installer or args.zip):
        args.all = True
    print("="*60)
    print(f"{APP_NAME} Builder")
    print(f"Version: {APP_VERSION}")
    print("="*60)
    print()
    try:
        project_root = Path(__file__).parent.parent
        check_python_version()
        if args.clean:
            clean_build_dirs(project_root)
        venv_dir = create_venv(project_root)
        install_dependencies(venv_dir, skip_deps=args.no_deps)
        exe_path = build_executable(project_root, venv_dir)
        installer_path = None
        zip_path = None
        if args.all or args.installer:
            installer_path = build_installer(project_root)
        if args.all or args.zip:
            zip_path = create_zip_package(project_root)
        log("Cleaning up...")
        try:
            shutil.rmtree(venv_dir)
        except:
            pass
        print_summary(project_root, exe_path, installer_path, zip_path)
        return 0
    except BuildError as e:
        log(f"Build failed: {e}", "ERROR")
        return 1
    except KeyboardInterrupt:
        log("Build cancelled by user", "WARNING")
        return 130
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return 1
if __name__ == '__main__':
    sys.exit(main())
