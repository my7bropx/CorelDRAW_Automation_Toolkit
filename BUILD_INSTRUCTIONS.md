# Build Instructions for CorelDRAW Automation Toolkit

## Quick Start (Windows)

### Option 1: Double-Click Build (Easiest)
1. Double-click `build.bat`
2. Wait 10-15 minutes
3. Get your files in `dist\` folder

### Option 2: Command Line Build
```batch
# Full build with everything
python installer\build.py

# Quick rebuild (skip dependency installation)
python installer\build.py --no-deps

# Build only executable
python installer\build.py --zip

# Build only installer (requires Inno Setup)
python installer\build.py --installer

# Clean build (remove old files first)
python installer\build.py --clean
```

## Prerequisites

### Required
- **Windows 10/11** (64-bit)
- **Python 3.8 - 3.11** (3.12+ may have issues)
- **4GB RAM** minimum
- **500MB** free disk space

### Optional (for installer)
- **Inno Setup 6.0+** from https://jrsoftware.org/isinfo.php

## Detailed Setup

### Step 1: Install Python

1. Download Python 3.11 from https://www.python.org/downloads/
2. **IMPORTANT**: Check "Add Python to PATH" during installation
3. Verify installation:
   ```cmd
   python --version
   ```

### Step 2: Get the Source Code

Extract the project to a folder, e.g.:
```
C:\Projects\CorelDRAW_Automation_Toolkit\
```

### Step 3: Run the Build

#### Method A: Using build.bat (Recommended)
```cmd
cd C:\Projects\CorelDRAW_Automation_Toolkit
build.bat
```

The script will:
1. Create a clean build environment
2. Install all dependencies
3. Build the executable
4. Create ZIP package
5. Build Windows installer (if Inno Setup installed)
6. Show you all output files

#### Method B: Using Python Script
```cmd
cd C:\Projects\CorelDRAW_Automation_Toolkit
python installer\build.py --all
```

## Output Files

After successful build, you'll find:

```
dist\
├── CorelDRAW_Automation_Toolkit\
│   ├── CorelDRAW_Automation_Toolkit.exe  (Main executable)
│   └── [supporting files]
├── CorelDRAW_Automation_Toolkit_0.1.0-beta.zip  (ZIP package)
└── installer\
    └── CorelDRAW_Automation_Toolkit_Setup_0.1.0-beta.exe  (Installer)
```

## Distribution Options

### Option 1: Share the ZIP File (Easiest)
- **Best for**: Quick sharing via email, cloud storage
- **Pros**: Single file, no installation needed
- **Cons**: No shortcuts, manual extraction
- **How**: Share `dist\CorelDRAW_Automation_Toolkit_0.1.0-beta.zip`

### Option 2: Share the Installer (Professional)
- **Best for**: End users, professional distribution
- **Pros**: Creates shortcuts, Start Menu entries, easy uninstall
- **Cons**: Requires Inno Setup to build
- **How**: Share `dist\installer\CorelDRAW_Automation_Toolkit_Setup_0.1.0-beta.exe`

### Option 3: Share the Folder
- **Best for**: Testing, development
- **Pros**: Direct access to all files
- **Cons**: Many files to copy
- **How**: Copy entire `dist\CorelDRAW_Automation_Toolkit` folder

## System Requirements for End Users

- Windows 10/11 64-bit
- CorelDRAW 2018 or higher (must be installed)
- 4GB RAM minimum
- 200MB disk space

## Troubleshooting

### Build fails with "Python not found"
- Install Python from https://python.org
- Make sure to check "Add Python to PATH"
- Restart Command Prompt after installation

### "Access denied" errors
- Run Command Prompt as Administrator
- Or run `build.bat` as Administrator

### PyInstaller build fails
```cmd
# Try clean build
python installer\build.py --clean

# Or manually clean
rmdir /s /q build	rmdir /s /q dist
python installer\build.py
```

### Missing DLLs in built executable
Edit `CorelDRAW_Automation_Toolkit.spec` and add to `hiddenimports`:
```python
hiddenimports += [
    'missing_module_name',
]
```

### Inno Setup not found
The installer will be skipped but the executable will still be built.
To create installer:
1. Download Inno Setup from https://jrsoftware.org/isinfo.php
2. Install with default settings
3. Run build again

### Build takes too long
- First build: 10-15 minutes (normal)
- Subsequent builds: 2-5 minutes
- Use `--no-deps` flag to skip dependency installation

### Antivirus blocking
- Temporarily disable real-time scanning
- Add project folder to antivirus exclusions
- Re-enable after build

## Advanced Usage

### Custom Build Options

```cmd
# Show all options
python installer\build.py --help

# Build without creating virtual environment (faster)
# Requires dependencies already installed
pip install pyinstaller pywin32 PyQt5 pillow
pyinstaller CorelDRAW_Automation_Toolkit.spec --clean
```

### Debugging Build Issues

1. Enable verbose output:
   ```cmd
   python installer\build.py --verbose
   ```

2. Check PyInstaller logs:
   - `build\CurveFiller\warn-CurveFiller.txt`
   - `build\CurveFiller\xref-CurveFiller.html`

3. Test executable directly:
   ```cmd
   dist\CorelDRAW_Automation_Toolkit\CorelDRAW_Automation_Toolkit.exe
   ```

## Build Configuration

### Modifying the Spec File

The build is controlled by `CorelDRAW_Automation_Toolkit.spec`:

- **Add resources**: Add to `datas` list
- **Add hidden imports**: Add to `hiddenimports` list
- **Change icon**: Place icon at `src\resources\icons\app_icon.ico`
- **Version info**: Automatically generated in spec file

### Version Numbers

Update version in these locations:
1. `setup.py` - line 17
2. `installer\inno_setup.iss` - line 5
3. `src\main.py` - line 111
4. `CorelDRAW_Automation_Toolkit.spec` - update `filevers` and `prodvers`

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review build logs in `build\` directory
3. Ensure all prerequisites are met
4. Try a clean build with `--clean` flag

## License

This build system is part of CorelDRAW Automation Toolkit.
See LICENSE file for details.
