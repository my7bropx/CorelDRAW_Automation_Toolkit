# CorelDRAW Automation Toolkit

A comprehensive, professional-grade automation suite for CorelDRAW 2018 and later versions.

## Features

### Advanced Curve Filler
- Fill open or closed curves with selected elements
- Multiple spacing modes: Fixed, Percentage, Auto-fit, Random
- Angle control: Follow curve, Fixed, Random, Incremental, Perpendicular
- Pattern modes: Single, Sequence, Random, Alternating
- Scale gradients and collision detection
- Post-fill editing with dynamic element count adjustment
- Full undo/redo support

### Rhinestone Design Automation
- Pre-defined stone sizes (SS6 to SS48)
- Pattern fill: Hexagonal, Square Grid, Circular, Outline
- Density and gap optimization
- Cost calculator
- Export for stone setting machines
- Application template generation

### Batch Processing System
- Process multiple CDR files automatically
- Apply presets to batches
- Multi-format export (PDF, SVG, AI, EPS, PNG, JPEG)
- Watch folder automation
- Auto-backup with versioning
- Parallel processing support

### Advanced Object Manipulation
- Array duplication (Linear, Grid, Circular, Along Path)
- Smart alignment and distribution
- Transform tools (Scale, Rotate, Skew, Mirror)
- Path offset with corner options
- Blend between shapes
- Boolean operations helper

### Text & Typography Tools
- Advanced text on path options
- Character, word, and line spacing controls
- Text effects (Arc, Wave, Perspective, Envelope)
- Stylistic variations (Random rotation, size, baseline)
- Font preview and character map
- Convert to curves and break apart

### Professional Features
- Modern PyQt5 interface with dark/light themes
- Preset management system with categories and favorites
- Real-time preview capabilities
- Multi-monitor and high-DPI support
- Comprehensive logging and error handling
- Plugin architecture for extensions

## System Requirements

- **Operating System:** Windows 10 or later
- **CorelDRAW:** 2018, 2019, 2020, 2021, 2022, 2023, or 2024
- **Python:** 3.8 or later (if running from source)
- **RAM:** 4 GB minimum (8 GB recommended)
- **Disk Space:** 100 MB

## Installation

### From Source

1. Clone the repository:
```bash
git clone https://github.com/your-repo/CorelDRAW_Automation_Toolkit.git
cd CorelDRAW_Automation_Toolkit
```

2. Create a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python src/main.py
```

### From Installer

1. Download the latest installer from Releases
2. Run `CorelDRAW_Automation_Toolkit_Setup.exe`
3. Follow the installation wizard
4. Launch from Start Menu or Desktop shortcut

## Quick Start

1. **Launch the application**
2. **Connect to CorelDRAW** (must be running)
3. **Select a tool** from the tabs (Curve Filler, Rhinestone, etc.)
4. **Configure settings** using the control panel
5. **Execute operations** with Apply/Fill buttons

### Basic Curve Fill Example

1. In CorelDRAW, draw a curve/path
2. Draw element(s) you want to duplicate along the path
3. In the Toolkit, click "Set Container" after selecting the curve
4. Click "Set Fill Elements" after selecting your element(s)
5. Adjust spacing, angle, and other options
6. Click "Fill Curve"

## Configuration

Settings are stored in:
- Windows: `%APPDATA%\CorelDRAW_Automation_Toolkit\settings.json`

### Preset Management

- Presets are stored in the `presets` subdirectory
- Import/Export presets for sharing
- Mark favorites for quick access
- Search presets by name, description, or tags

## Keyboard Shortcuts

- `Ctrl+F` - Fill curve
- `Ctrl+P` - Preview
- `Ctrl+Z` - Undo
- `Ctrl+Y` - Redo
- `Ctrl+S` - Save preset
- `Ctrl+O` - Load preset
- `F5` - Refresh CorelDRAW
- `Ctrl+,` - Settings

## Architecture

```
CorelDRAW_Automation_Toolkit/
├── src/
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration management
│   ├── core/                # Core modules
│   │   ├── corel_interface.py  # CorelDRAW COM integration
│   │   └── preset_manager.py   # Preset system
│   ├── ui/                  # User interface
│   │   ├── main_window.py
│   │   ├── widgets/
│   │   └── dialogs/
│   └── tools/               # Individual tools
│       ├── curve_filler/
│       ├── rhinestone/
│       ├── batch_processor/
│       ├── object_manipulation/
│       └── typography/
├── tests/                   # Unit and integration tests
├── docs/                    # Documentation
├── installer/               # Installer files
└── requirements.txt
```

## Plugin Development

The toolkit supports custom plugins. See `docs/plugin_development.md` for details.

## Troubleshooting

### Common Issues

**"CorelDRAW not found"**
- Ensure CorelDRAW is running before connecting
- Check that you have CorelDRAW 2018 or later installed

**"No selection"**
- Make sure objects are selected in CorelDRAW
- Try clicking directly in CorelDRAW window first

**"Operation failed"**
- Check the log file in `%APPDATA%\CorelDRAW_Automation_Toolkit\logs\`
- Ensure sufficient memory available
- Try with smaller operations first

## Building from Source

### Create Executable

Using PyInstaller:
```bash
pyinstaller --name="CorelDRAW_Automation_Toolkit" --windowed --icon=resources/icons/app_icon.ico src/main.py
```

### Create Installer

Using NSIS or Inno Setup with the provided installer scripts.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation:** See the `docs/` folder
- **Issues:** Report bugs on GitHub Issues
- **Feature Requests:** Use GitHub Issues with the "enhancement" label

## Changelog

### Version 1.0.0 (2024)
- Initial release
- Advanced Curve Filler with comprehensive options
- Rhinestone Design Automation
- Batch Processing System
- Object Manipulation Tools
- Typography Tools
- Preset Management System
- Modern PyQt5 Interface

## Credits

- Developed with Python 3, PyQt5, and pywin32
- CorelDRAW COM/Automation API integration
- Open-source community contributions

## Disclaimer

This software is provided as-is. Always backup your work before using automation tools. The developers are not responsible for any data loss or damage.

---

**Made with dedication for the CorelDRAW community**
