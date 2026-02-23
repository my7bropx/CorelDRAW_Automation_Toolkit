#!/usr/bin/env python3
"""
Build script for creating Windows executable and installer.
Uses PyInstaller to create standalone .exe file.
"""

import subprocess
import sys
import shutil
from pathlib import Path


def main():
    """Build the Windows executable."""
    print("=" * 60)
    print("CorelDRAW Automation Toolkit - Build Script")
    print("=" * 60)

    # Paths
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"

    # Clean previous builds
    print("\n[1/5] Cleaning previous builds...")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # Check for PyInstaller
    print("[2/5] Checking PyInstaller...")
    try:
        import PyInstaller
        print(f"  PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("  PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Build executable
    print("[3/5] Building executable with PyInstaller...")

    pyinstaller_args = [
        "pyinstaller",
        "--name=CorelDRAW_Automation_Toolkit",
        "--windowed",  # No console window
        "--onedir",  # Create directory (faster startup than onefile)
        "--noconfirm",  # Overwrite without asking
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--specpath={build_dir}",
        # Add data files
        f"--add-data={project_root / 'README.md'};.",
        f"--add-data={project_root / 'LICENSE'};.",
        # Hidden imports for COM
        "--hidden-import=win32com.gen_py",
        "--hidden-import=pythoncom",
        "--hidden-import=pywintypes",
        # Entry point
        str(src_dir / "main.py"),
    ]

    # Add icon if exists
    icon_path = src_dir / "resources" / "icons" / "app_icon.ico"
    if icon_path.exists():
        pyinstaller_args.insert(-1, f"--icon={icon_path}")

    result = subprocess.run(pyinstaller_args, cwd=project_root)

    if result.returncode != 0:
        print("ERROR: PyInstaller build failed!")
        return 1

    print("[4/5] Copying additional files...")
    # Copy documentation
    dist_app_dir = dist_dir / "CorelDRAW_Automation_Toolkit"
    docs_dest = dist_app_dir / "docs"
    docs_dest.mkdir(exist_ok=True)

    if (project_root / "docs").exists():
        shutil.copytree(
            project_root / "docs",
            docs_dest,
            dirs_exist_ok=True
        )

    # Copy presets
    presets_dest = dist_app_dir / "presets"
    presets_dest.mkdir(exist_ok=True)

    # Create default config
    config_dir = dist_app_dir / "config"
    config_dir.mkdir(exist_ok=True)

    print("[5/5] Build complete!")
    print(f"\nExecutable created at: {dist_app_dir}")
    print(f"Run: {dist_app_dir / 'CorelDRAW_Automation_Toolkit.exe'}")

    # Size report
    total_size = sum(f.stat().st_size for f in dist_app_dir.rglob('*') if f.is_file())
    print(f"\nTotal size: {total_size / (1024*1024):.1f} MB")

    print("\n" + "=" * 60)
    print("Next steps:")
    print("1. Test the executable on a clean system")
    print("2. Create installer using NSIS or Inno Setup")
    print("3. Sign the executable (for distribution)")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
