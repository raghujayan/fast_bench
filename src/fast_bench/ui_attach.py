"""Petrel UI automation and window management using pywinauto."""

import sys
import time
import subprocess
from pathlib import Path
from typing import Tuple, Optional, NamedTuple

# Platform check for Windows-only imports
if sys.platform == "win32":
    from pywinauto import Application, Desktop
    from pywinauto.application import WindowSpecification
else:
    # Mock types for non-Windows platforms (development on Mac)
    Application = None
    Desktop = None
    WindowSpecification = object


class WindowRect(NamedTuple):
    """Window rectangle coordinates."""
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        """Window width in pixels."""
        return self.right - self.left

    @property
    def height(self) -> int:
        """Window height in pixels."""
        return self.bottom - self.top


def attach_petrel(
    petrel_exe_path: Path,
    timeout: int = 180,
    launch_if_not_found: bool = True
) -> Optional[WindowSpecification]:
    """
    Attach to Petrel window, optionally launching if not running.

    Args:
        petrel_exe_path: Path to Petrel.exe
        timeout: Maximum seconds to wait for Petrel window (default: 180s)
        launch_if_not_found: Launch Petrel if not already running

    Returns:
        Petrel window specification, or None if failed

    Raises:
        RuntimeError: If running on non-Windows platform
        TimeoutError: If Petrel window not found within timeout
    """
    if sys.platform != "win32":
        raise RuntimeError("Petrel UI automation is only supported on Windows")

    start_time = time.time()
    petrel_process = None

    # Try to find existing Petrel window (main window, not File Explorer)
    try:
        # Find main Petrel window, excluding "File Explorer" windows
        app = Application(backend="uia").connect(title_re=".*Petrel.*", timeout=5)
        # Look for the main Petrel window (has project name in brackets or "Platform")
        for window in app.windows():
            title = window.window_text()
            if "Petrel" in title and "File Explorer" not in title:
                print(f"✓ Attached to existing Petrel window: {title}")
                return window
    except Exception as e:
        pass  # Not running, will launch if requested

    # Launch Petrel if not found and launch_if_not_found is True
    if launch_if_not_found:
        print(f"Launching Petrel from: {petrel_exe_path}")
        try:
            petrel_process = subprocess.Popen([str(petrel_exe_path)])
        except Exception as e:
            raise RuntimeError(f"Failed to launch Petrel: {e}")

    # Wait for Petrel window to appear
    print(f"Waiting for Petrel window (timeout: {timeout}s)...")
    while time.time() - start_time < timeout:
        try:
            app = Application(backend="uia").connect(title_re=".*Petrel.*", timeout=2)
            # Look for the main Petrel window (exclude File Explorer)
            for window in app.windows():
                title = window.window_text()
                if "Petrel" in title and "File Explorer" not in title:
                    elapsed = time.time() - start_time
                    print(f"✓ Petrel window found after {elapsed:.1f}s: {title}")
                    return window
        except Exception:
            pass  # Keep waiting

        time.sleep(2)

    raise TimeoutError(f"Petrel window not found within {timeout}s")


def get_window_rect(window: WindowSpecification) -> WindowRect:
    """
    Get window rectangle coordinates.

    Args:
        window: pywinauto window specification

    Returns:
        WindowRect with left, top, right, bottom coordinates

    Raises:
        RuntimeError: If running on non-Windows platform
    """
    if sys.platform != "win32":
        raise RuntimeError("Window operations are only supported on Windows")

    rect = window.rectangle()
    return WindowRect(
        left=rect.left,
        top=rect.top,
        right=rect.right,
        bottom=rect.bottom
    )


def to_rel(x: int, y: int, rect: WindowRect) -> Tuple[float, float]:
    """
    Convert absolute screen coordinates to window-relative coordinates (0.0-1.0).

    Args:
        x: Absolute X coordinate (pixels)
        y: Absolute Y coordinate (pixels)
        rect: Window rectangle

    Returns:
        Tuple of (rel_x, rel_y) in range [0.0, 1.0]
    """
    rel_x = (x - rect.left) / rect.width if rect.width > 0 else 0.0
    rel_y = (y - rect.top) / rect.height if rect.height > 0 else 0.0
    return (rel_x, rel_y)


def to_abs(rel_x: float, rel_y: float, rect: WindowRect) -> Tuple[int, int]:
    """
    Convert window-relative coordinates (0.0-1.0) to absolute screen coordinates.

    Args:
        rel_x: Relative X coordinate (0.0-1.0)
        rel_y: Relative Y coordinate (0.0-1.0)
        rect: Window rectangle

    Returns:
        Tuple of (abs_x, abs_y) in screen pixel coordinates
    """
    abs_x = int(rect.left + rel_x * rect.width)
    abs_y = int(rect.top + rel_y * rect.height)
    return (abs_x, abs_y)


def ensure_foreground(window: WindowSpecification) -> None:
    """
    Bring Petrel window to foreground.

    Args:
        window: pywinauto window specification

    Raises:
        RuntimeError: If running on non-Windows platform
    """
    if sys.platform != "win32":
        raise RuntimeError("Window operations are only supported on Windows")

    try:
        if window.is_minimized():
            window.restore()
        window.set_focus()
    except Exception as e:
        # Fallback: try different methods
        try:
            window.set_focus()
        except Exception:
            print(f"Warning: Could not bring Petrel to foreground: {e}")


def set_window_rect(
    window: WindowSpecification,
    left: int,
    top: int,
    width: int,
    height: int
) -> None:
    """
    Set window position and size (optional feature).

    Args:
        window: pywinauto window specification
        left: Window left position
        top: Window top position
        width: Window width
        height: Window height

    Raises:
        RuntimeError: If running on non-Windows platform
    """
    if sys.platform != "win32":
        raise RuntimeError("Window operations are only supported on Windows")

    try:
        window.move_window(x=left, y=top, width=width, height=height)
    except Exception as e:
        print(f"Warning: Could not set window rect: {e}")
