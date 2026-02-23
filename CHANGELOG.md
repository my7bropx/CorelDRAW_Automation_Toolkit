# Changelog

All notable changes to the CorelDRAW Automation Toolkit will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0-beta] - 2026-02-17

### Added
- **Advanced Curve Filler Tool**
  - Multiple spacing modes: Fixed, Percentage, Auto-fit, Random
  - Angle control: Follow curve, Fixed, Random, Incremental, Perpendicular
  - Pattern modes: Single, Sequence, Random, Alternating
  - Scale options: Uniform, Gradient, Random
  - Collision detection to prevent overlap
  - Smart corner handling
  - Post-fill editing with dynamic element count adjustment
  - Start/end padding support
  - Offset from curve support

- **Core Application Features**
  - Modern PyQt5 interface with professional design
  - Dark and light theme support
  - Comprehensive preset management system
  - Preset categories, favorites, and search
  - Import/Export presets for sharing
  - CorelDRAW COM/Automation integration (2018-2024)
  - Connection status indicator
  - Multi-monitor and high-DPI support
  - Auto-save functionality
  - Recent files tracking
  - Customizable keyboard shortcuts
  - Comprehensive logging system
  - Undo/Redo support through CorelDRAW
  - Window geometry persistence

- **Build System**
  - PyInstaller build script for Windows executable
  - Inno Setup script for Windows installer
  - setup.py for pip installation
  - requirements.txt with dependencies

- **Quality Assurance**
  - Unit tests for core modules
  - Test coverage for Curve Filler Engine
  - Test coverage for Preset Manager
  - Test coverage for Configuration Manager
  - Test coverage for Logger utilities

### Technical Details
- Python 3.8+ support
- PyQt5 5.15+ for UI
- pywin32 for COM automation
- Modular architecture with plugin support
- JSON-based configuration and presets
- MIT License

### Known Issues
- Preview canvas not yet implemented
- Rhinestone Designer, Batch Processor, Object Tools, Typography - UI present but core functionality in development

---

## [1.0.0] - 2024-XX-XX

### Added
- **Advanced Curve Filler Tool**
  - Multiple spacing modes: Fixed, Percentage, Auto-fit, Random
  - Angle control: Follow curve, Fixed, Random, Incremental, Perpendicular
  - Pattern modes: Single, Sequence, Random, Alternating
  - Scale options: Uniform, Gradient, Random
  - Collision detection to prevent overlap
  - Smart corner handling
  - Post-fill editing with dynamic element count adjustment
  - Start/end padding support
  - Offset from curve support

- **Rhinestone Design Automation**
  - Pre-defined stone library (SS6-SS48)
  - Multiple fill patterns: Hexagonal, Square, Circular, Outline, Random
  - Density and gap optimization
  - Cost calculator with customizable pricing
  - Export for stone setting machines
  - Application template generation

- **Batch Processing System**
  - Multi-file queue management
  - Apply presets to multiple files
  - Multi-format export (PDF, SVG, AI, EPS, PNG, JPEG)
  - Watch folder automation
  - Auto-backup with versioning
  - Parallel processing support
  - Progress tracking

- **Advanced Object Manipulation Tools**
  - Array duplication (Linear, Grid, Circular, Along Path)
  - Smart alignment and distribution
  - Transform tools (Scale, Rotate, Skew, Mirror)
  - Path offset with corner options (Miter, Round, Bevel)
  - Blend between shapes
  - Boolean operations helper

- **Text & Typography Tools**
  - Advanced text on path with positioning options
  - Character, word, and line spacing controls
  - Text effects (Arc, Wave, Perspective, Envelope)
  - Stylistic variations (Random rotation, size, baseline)
  - Font preview and character map
  - Convert text to curves
  - Break apart characters

- **Core Application Features**
  - Modern PyQt5 interface with professional design
  - Dark and light theme support
  - Comprehensive preset management system
  - Preset categories, favorites, and search
  - Import/Export presets for sharing
  - CorelDRAW COM/Automation integration (2018-2024)
  - Connection status indicator
  - Multi-monitor and high-DPI support
  - Auto-save functionality
  - Recent files tracking
  - Customizable keyboard shortcuts
  - Comprehensive logging system
  - Undo/Redo support through CorelDRAW

- **Documentation**
  - Comprehensive README
  - Quick Start Guide
  - Detailed Curve Filler Guide
  - API Reference structure
  - Installation instructions
  - Troubleshooting guide

- **Build System**
  - PyInstaller build script for Windows executable
  - Inno Setup script for Windows installer
  - setup.py for pip installation
  - requirements.txt with dependencies

- **Quality Assurance**
  - Unit tests for core modules
  - Test coverage for Curve Filler Engine
  - Test coverage for Preset Manager
  - Code structure for pytest

### Technical Details
- Python 3.8+ support
- PyQt5 5.15+ for UI
- pywin32 for COM automation
- Modular architecture with plugin support
- JSON-based configuration and presets
- MIT License

---

## [Unreleased]

### Planned Features
- Live preview canvas in Curve Filler
- More rhinestone fill algorithms
- Plugin marketplace
- Cloud preset sharing
- Macro recorder
- More text effects
- Performance profiling
- Localization support

### Known Issues
- Preview canvas not yet implemented
- Some advanced features marked as "in progress"
- Requires manual CorelDRAW connection

---

## Version History

- **0.1.0-beta** - First beta release with Curve Filler core functionality
- **1.0.0** - Initial release with full feature set
