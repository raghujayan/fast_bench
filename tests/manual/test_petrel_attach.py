"""Manual test for Petrel UI automation - Windows only.

Run this script on Windows with Petrel installed to verify:
1. Petrel launches or attaches to existing instance
2. Window rectangle is captured correctly
3. Window can be brought to foreground
4. Coordinate conversion works accurately

Usage:
    python tests/manual/test_petrel_attach.py [config_path]

Example:
    python tests/manual/test_petrel_attach.py config/config.yaml
"""

import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from fast_bench.config_schema import load_config
from fast_bench.ui_attach import (
    attach_petrel,
    get_window_rect,
    to_rel,
    to_abs,
    ensure_foreground,
)


def test_petrel_attach_interactive(config_path: str = "config/config.yaml"):
    """
    Interactive test for Petrel UI automation.

    Args:
        config_path: Path to configuration file
    """
    print("=" * 60)
    print("Petrel UI Automation Test")
    print("=" * 60)

    if sys.platform != "win32":
        print("❌ ERROR: This test must be run on Windows")
        sys.exit(1)

    # Load configuration
    print(f"\n1. Loading configuration from: {config_path}")
    try:
        config = load_config(config_path)
        print(f"   ✓ Petrel executable: {config.petrel.exe_path}")
    except Exception as e:
        print(f"   ❌ Failed to load config: {e}")
        sys.exit(1)

    # Test: Attach to Petrel
    print("\n2. Attaching to Petrel window...")
    print("   (Will launch Petrel if not already running)")
    try:
        petrel_window = attach_petrel(
            config.petrel.exe_path,
            timeout=180,
            launch_if_not_found=True
        )
        print("   ✓ Successfully attached to Petrel")
    except Exception as e:
        print(f"   ❌ Failed to attach: {e}")
        sys.exit(1)

    # Test: Get window rectangle
    print("\n3. Getting window rectangle...")
    try:
        rect = get_window_rect(petrel_window)
        print(f"   ✓ Window position: ({rect.left}, {rect.top})")
        print(f"   ✓ Window size: {rect.width}x{rect.height}")
        print(f"   ✓ Window bounds: left={rect.left}, top={rect.top}, "
              f"right={rect.right}, bottom={rect.bottom}")
    except Exception as e:
        print(f"   ❌ Failed to get window rect: {e}")
        sys.exit(1)

    # Test: Bring window to foreground
    print("\n4. Bringing Petrel to foreground...")
    try:
        ensure_foreground(petrel_window)
        time.sleep(1)  # Give window time to come to front
        print("   ✓ Window should now be in foreground")
        print("   → Please verify that Petrel is now the active window")
    except Exception as e:
        print(f"   ❌ Failed to bring window to foreground: {e}")

    # Test: Coordinate conversion
    print("\n5. Testing coordinate conversion...")
    test_points = [
        (rect.left, rect.top, "Top-left corner"),
        (rect.right, rect.bottom, "Bottom-right corner"),
        ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2, "Center"),
        (rect.left + rect.width // 4, rect.top + rect.height // 4, "Quarter point"),
    ]

    for abs_x, abs_y, label in test_points:
        # Convert to relative
        rel_x, rel_y = to_rel(abs_x, abs_y, rect)

        # Convert back to absolute
        back_x, back_y = to_abs(rel_x, rel_y, rect)

        # Check round-trip accuracy
        error_x = abs(back_x - abs_x)
        error_y = abs(back_y - abs_y)

        if error_x <= 1 and error_y <= 1:
            print(f"   ✓ {label}")
            print(f"     Absolute: ({abs_x}, {abs_y})")
            print(f"     Relative: ({rel_x:.3f}, {rel_y:.3f})")
            print(f"     Round-trip error: ({error_x}, {error_y}) pixels")
        else:
            print(f"   ❌ {label} - Round-trip error too large!")
            print(f"     Expected: ({abs_x}, {abs_y})")
            print(f"     Got back: ({back_x}, {back_y})")
            print(f"     Error: ({error_x}, {error_y}) pixels")

    # Test: Coordinate boundary cases
    print("\n6. Testing coordinate boundaries...")
    boundary_tests = [
        (0.0, 0.0, "Relative (0.0, 0.0)"),
        (1.0, 1.0, "Relative (1.0, 1.0)"),
        (0.5, 0.5, "Relative (0.5, 0.5)"),
    ]

    for rel_x, rel_y, label in boundary_tests:
        abs_x, abs_y = to_abs(rel_x, rel_y, rect)
        back_rel_x, back_rel_y = to_rel(abs_x, abs_y, rect)

        error_x = abs(back_rel_x - rel_x)
        error_y = abs(back_rel_y - rel_y)

        if error_x < 0.001 and error_y < 0.001:
            print(f"   ✓ {label} → ({abs_x}, {abs_y}) → "
                  f"({back_rel_x:.3f}, {back_rel_y:.3f})")
        else:
            print(f"   ❌ {label} - Error: ({error_x:.6f}, {error_y:.6f})")

    # Summary
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
    print("\nManual verification checklist:")
    print("  □ Petrel window is visible and in foreground")
    print("  □ Window dimensions match what you see on screen")
    print("  □ All coordinate conversions passed with <1px error")
    print("\nIf all items above are checked, Phase 2 acceptance criteria are met!")
    print("=" * 60)


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/config.yaml"
    test_petrel_attach_interactive(config_path)
