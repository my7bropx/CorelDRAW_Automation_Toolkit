#!/usr/bin/env python3
"""
Example: Basic Curve Fill
Demonstrates how to use the Curve Filler Engine programmatically.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.corel_interface import corel
from tools.curve_filler.curve_filler_engine import (
    CurveFillerEngine, FillSettings, SpacingMode, AngleMode
)


def main():
    """Basic curve fill example."""
    print("CorelDRAW Automation Toolkit - Basic Curve Fill Example")
    print("=" * 60)

    # Step 1: Connect to CorelDRAW
    print("\n[1] Connecting to CorelDRAW...")
    try:
        corel.connect()
        print(f"    Connected to CorelDRAW {corel.version}")
    except Exception as e:
        print(f"    ERROR: {e}")
        print("    Make sure CorelDRAW is running!")
        return

    print("\n[2] Please select:")
    print("    - First: Select a CURVE/PATH (container)")
    print("    - Second: Select ELEMENT(s) to fill with")
    input("    Press Enter when ready...")

    try:
        selection = corel.get_selection()
        print(f"    Selected {selection.Count} object(s)")

        if selection.Count < 2:
            print("    ERROR: Need at least 2 objects selected")
            print("           (1 curve + 1 or more fill elements)")
            return

        # First object is container, rest are fill elements
        container = selection[1]
        fill_shapes = corel.app.CreateShapeRange()
        for i in range(2, selection.Count + 1):
            fill_shapes.Add(selection[i])

        print(f"    Container: {container.Type}")
        print(f"    Fill elements: {fill_shapes.Count}")

    except Exception as e:
        print(f"    ERROR: {e}")
        return

    print("\n[3] Initializing Curve Filler Engine...")
    engine = CurveFillerEngine()

    try:
        engine.set_container(container)
        engine.set_fill_elements(fill_shapes)
        print("    Engine configured successfully")
    except Exception as e:
        print(f"    ERROR: {e}")
        return

    print("\n[4] Configuring fill settings...")
    settings = FillSettings(
        spacing_mode=SpacingMode.FIXED,
        spacing_value=15.0,  # 15mm spacing
        angle_mode=AngleMode.FOLLOW_CURVE,  # Rotate with curve
        collision_detection=True,  # Prevent overlap
    )
    print(f"    Spacing: {settings.spacing_value}mm (fixed)")
    print(f"    Angle: Follow curve")
    print(f"    Collision detection: ON")

    print("\n[5] Calculating placements...")
    try:
        placements = engine.calculate_placements(settings)
        print(f"    Will place {len(placements)} elements")
    except Exception as e:
        print(f"    ERROR: {e}")
        return

    confirm = input("\n[6] Execute fill? (y/n): ")
    if confirm.lower() != 'y':
        print("    Cancelled.")
        return

    print("    Executing fill operation...")
    try:
        shapes = engine.execute_fill(placements, settings)
        print(f"    SUCCESS! Created {len(shapes)} elements")
    except Exception as e:
        print(f"    ERROR: {e}")
        return

    print("\n[7] Post-fill options:")
    print("    - Group all placed elements? (g)")
    print("    - Select all placed elements? (s)")
    print("    - Clear all placed elements? (c)")
    print("    - Done (d)")

    while True:
        choice = input("    Choice: ").lower()
        if choice == 'g':
            engine.group_placed_elements()
            print("    Elements grouped!")
        elif choice == 's':
            engine.select_placed_elements()
            print("    Elements selected!")
        elif choice == 'c':
            engine.clear_placed_elements()
            print("    Elements cleared!")
        elif choice == 'd':
            break

    print("\n" + "=" * 60)
    print("Example completed. Check CorelDRAW for results.")
    print("=" * 60)


if __name__ == "__main__":
    main()
