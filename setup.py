#!/usr/bin/env python3
"""
Setup script for CorelDRAW Automation Toolkit
Supports both pip installation and PyInstaller building.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding='utf-8') if readme_path.exists() else ""

setup(
    name="coreldraw-automation-toolkit",
    version="0.1.0-beta",
    author="CorelDRAW Automation Team",
    author_email="support@coreldraw-automation.com",
    description="Professional automation suite for CorelDRAW 2018+",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-repo/CorelDRAW_Automation_Toolkit",
    project_urls={
        "Bug Tracker": "https://github.com/your-repo/CorelDRAW_Automation_Toolkit/issues",
        "Documentation": "https://github.com/your-repo/CorelDRAW_Automation_Toolkit/docs",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Graphics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: Microsoft :: Windows",
        "Environment :: Win32 (MS Windows)",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=[
        "PyQt5>=5.15.0",
        "pywin32>=300",
        "pillow>=9.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-qt>=4.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.950",
        ],
        "build": [
            "pyinstaller>=5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "coreldraw-toolkit=main:main",
        ],
        "gui_scripts": [
            "coreldraw-toolkit-gui=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.json", "*.md", "*.txt"],
        "resources": ["icons/*", "themes/*", "presets/*"],
    },
    zip_safe=False,
)
