# Quick Start Guide

Get started with CorelDRAW Automation Toolkit in 5 minutes!

## Step 1: Installation

### Option A: From Source (Developers)
```bash
pip install -r requirements.txt
python src/main.py
```

### Option B: From Installer (End Users)
Run `CorelDRAW_Automation_Toolkit_Setup.exe` and follow prompts.

## Step 2: First Launch

1. **Open CorelDRAW** first (2018 or later)
2. **Launch the Toolkit**
3. Click **"Connect"** in the toolbar
4. Verify the green indicator shows "Connected"

## Step 3: Your First Curve Fill

### In CorelDRAW:
1. Draw a **curved path** (use Freehand or Bezier tool)
2. Draw a **small shape** (circle, star, etc.) to duplicate

### In the Toolkit:
1. Select the **Curve Filler** tab
2. Click in CorelDRAW and select your **curve**
3. Click **"Set Container"** in the Toolkit
4. Click in CorelDRAW and select your **shape**
5. Click **"Set Fill Elements"** in the Toolkit
6. Set **Distance** to 10mm
7. Click **"Fill Curve"**

## Step 4: Adjust Results

- Use **+10/-10 buttons** to add/remove elements
- **Group Results** to keep them together
- **Select All Placed** to modify them
- **Clear All Placed** to start over

## Step 5: Save as Preset

1. Click **"Save"** in the Presets section
2. Enter a name like "My First Fill"
3. Your settings are now saved for reuse!

## Basic Controls Reference

| Control | Function |
|---------|----------|
| Spacing Mode | How elements are spaced apart |
| Distance | Space between elements (in mm) |
| Angle Mode | How elements are rotated |
| Element Count | Override automatic counting |
| Collision Detection | Prevent overlapping |

## Next Steps

- Try **different angle modes** (Follow Curve is great!)
- Experiment with **multiple fill elements** (patterns)
- Explore **Rhinestone Designer** for textile projects
- Use **Batch Processor** for multiple files

## Need Help?

- Press **F1** for the full user manual
- Check **docs**
- Report issues on GitHub
