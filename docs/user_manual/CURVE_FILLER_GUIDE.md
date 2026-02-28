# Advanced Curve Filler - Complete Guide

The Curve Filler is the flagship tool of the CorelDRAW Automation Toolkit. This guide covers all features in detail.

## Overview

The Curve Filler places copies of selected elements along any curve or path in CorelDRAW. It supports:
- Open and closed curves
- Single or multiple fill elements
- Various spacing and rotation modes
- Real-time adjustment of results

## Interface Layout

```
┌─────────────────────────────────────────────────┐
│ Preview Area       │  Control Panel              │
│                    │  ├─ Selection               │
│ Instructions &     │  ├─ Spacing                 │
│ Status Display     │  ├─ Rotation                │
│                    │  ├─ Element Count           │
│                    │  ├─ Advanced Options        │
│                    │  └─ Actions                 │
└─────────────────────────────────────────────────┘
```

## Setting Up

### 1. Set Container (The Curve)

1. In CorelDRAW, select any curve/path
2. Click **"Set Container (Curve/Path)"**
3. Status updates to "Container: Set"

**Supported Containers:**
- Freehand curves
- Bezier curves
- Artistic text paths
- Rectangle/Ellipse outlines (converted)
- Compound paths
- Text converted to curves

### 2. Set Fill Elements

1. Select one or more shapes in CorelDRAW
2. Click **"Set Fill Elements"**
3. Status shows element count

**Tips:**
- Select multiple elements for pattern sequences
- Group complex elements first for better performance
- Original elements are preserved (duplicates are created)

## Spacing Controls

### Spacing Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **Fixed Distance** | Exact spacing in mm | Precise layouts, technical drawings |
| **Percentage** | Based on element size | Responsive scaling |
| **Auto-fit** | Fill entire curve | Maximizing coverage |
| **Random** | Variable spacing | Organic, natural looks |

### Fixed Distance Mode
- Set exact spacing between element centers
- Values in millimeters (or current unit)
- Typical range: 3mm (dense) to 50mm (sparse)

### Percentage Mode
- Spacing = Element Size × Percentage
- 100% = elements touch edge-to-edge
- 150% = 50% gap between elements
- Values < 100% cause overlap

### Auto-fit Mode
- Automatically calculates spacing to fill curve
- Specify element count or let system optimize
- Great for consistent distribution

### Random Mode
- Set minimum and maximum spacing
- Each spacing randomly selected
- Creates organic, hand-placed appearance

### Padding

- **Start Padding**: Distance from curve start before first element
- **End Padding**: Distance from curve end after last element
- Useful for leaving space at curve endpoints

## Rotation Controls

### Angle Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| **Follow Curve** | Rotates to match curve tangent | Flowing designs, natural paths |
| **Fixed Angle** | Same angle for all elements | Uniform orientation |
| **Random** | Random angle per element | Scattered, chaotic effects |
| **Incremental** | Each element rotates more | Spinning patterns |
| **Perpendicular** | 90° to curve direction | Standing elements |

### Follow Curve (Recommended)
- Elements rotate to follow the path direction
- Most natural-looking results
- Works beautifully with curved paths

### Fixed Angle
- All elements maintain same rotation
- Set angle in degrees (0-360)
- Useful for uniform appearance

### Random Angle
- Set minimum and maximum angles
- Full range: 0° to 360°
- Creates variety and interest

### Incremental
- Each element rotates by increment amount
- Creates spinning/twisting effects
- Try 15° increments for gradual rotation

## Element Count

### Automatic (Default)
- Set to 0 for automatic calculation
- Count based on curve length and spacing
- Recommended for most uses

### Manual Override
- Specify exact number of elements
- System adjusts spacing to fit
- Use with "Distribute evenly" for perfect spacing

### Quick Adjust Slider
- Fast way to set approximate count
- Range: 1-100 (adjustable)
- Updates element count field

### Distribute Evenly
- When enabled: elements spaced equally
- Ensures first and last element at curve ends
- Best with specified element count

## Advanced Options

### Offset from Curve
- Positive: elements above/outside curve
- Negative: elements below/inside curve
- Measured perpendicular to curve
- Great for outlines and borders

### Collision Detection
- Prevents element overlap
- Removes placements that would collide
- Slightly slower but cleaner results

### Smart Corner Handling
- Adjusts placement at sharp corners
- Prevents bunching at tight curves
- Recommended for complex paths

### Scale Options

**Uniform**: All elements same size
- Scale Factor: multiply original size

**Gradient**: Size changes along path
- Scale Start: size at beginning
- Scale End: size at end
- Creates growth/shrink effect

**Random**: Variable sizes
- Scale Min/Max: size range
- Natural, varied appearance

### Pattern Modes

**Single Element**: Only uses first element

**Sequence**: Cycles through elements (A, B, C, A, B, C...)

**Random**: Randomly selects from available elements

**Alternating**: Same as sequence, emphasis on A/B alternation

## Executing the Fill

### Preview Button
- Shows how many elements will be placed
- No changes made to document
- Quick validation before committing

### Fill Curve Button
- Creates all element duplicates
- Applies transformations
- Wrapped in undo group (single Ctrl+Z)

### Progress Indicator
- Shows in status bar for large operations
- Percentage complete
- Can take time for 1000+ elements

## Post-Fill Editing

### Adjusting Count
- Click **+10** or **-10** buttons
- Recalculates entire fill
- Maintains current settings

### Group Results
- Groups all placed elements together
- Easier to move/transform as unit
- Original elements stay separate

### Select All Placed
- Selects every created element
- Useful for applying effects
- Change colors, add outlines, etc.

### Clear All Placed
- Removes all created elements
- Confirmation dialog appears
- Original elements preserved

## Presets

### Saving Presets
1. Configure all settings
2. Click **Save** in Presets section
3. Enter descriptive name
4. Preset stored for later use

### Loading Presets
1. Use Preset Browser (dock on right)
2. Double-click preset to apply
3. Or select and click Apply

### Built-in Presets

| Preset | Description |
|--------|-------------|
| Basic Grid Fill | Simple uniform spacing |
| Path Following | Elements rotate with curve |
| Decorative Scatter | Random spacing and angles |
| Dense Fill | Tight spacing for coverage |
| Gradient Scale | Elements grow along path |

## Practical Examples

### Example 1: Chain Links
1. Draw circular path
2. Create single chain link shape
3. Set spacing to link length
4. Angle mode: Follow Curve
5. Fill curve

### Example 2: Decorative Border
1. Draw rectangle path
2. Create ornamental element
3. Use Auto-fit mode
4. Set count to 20
5. Enable Distribute Evenly

### Example 3: Scattered Stars
1. Draw wavy path
2. Create star shape
3. Spacing: Random (5-15mm)
4. Angle: Random (0-360°)
5. Scale: Random (0.8-1.2)

### Example 4: Growing Pattern
1. Draw spiral path
2. Create circle element
3. Scale Mode: Gradient
4. Scale Start: 0.3
5. Scale End: 1.5

## Performance Tips

- Start with fewer elements to test settings
- Group complex elements before setting
- Use collision detection only when needed
- Preview before large operations
- Close other CorelDRAW documents

## Troubleshooting

**"No container curve set"**
- Select curve in CorelDRAW first
- Click Set Container button

**Elements not appearing**
- Check curve isn't too short
- Verify spacing isn't larger than curve
- Ensure elements are set

**Elements overlapping**
- Enable Collision Detection
- Increase spacing value
- Use larger percentage

**Operation very slow**
- Reduce element count
- Disable collision detection
- Simplify fill elements

## Keyboard Shortcuts

- `Ctrl+F` - Execute fill
- `Ctrl+P` - Preview
- `Ctrl+Z` - Undo fill (in CorelDRAW)
