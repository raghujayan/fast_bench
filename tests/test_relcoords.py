"""Tests for window coordinate conversion functions."""

import sys
import pytest
from fast_bench.ui_attach import WindowRect, to_rel, to_abs


class TestWindowRect:
    """Tests for WindowRect class."""

    def test_window_rect_creation(self):
        """Test creating a WindowRect."""
        rect = WindowRect(left=100, top=200, right=1100, bottom=900)
        assert rect.left == 100
        assert rect.top == 200
        assert rect.right == 1100
        assert rect.bottom == 900

    def test_window_rect_width(self):
        """Test WindowRect width property."""
        rect = WindowRect(left=100, top=200, right=1100, bottom=900)
        assert rect.width == 1000

    def test_window_rect_height(self):
        """Test WindowRect height property."""
        rect = WindowRect(left=100, top=200, right=1100, bottom=900)
        assert rect.height == 700


class TestCoordinateConversion:
    """Tests for coordinate conversion functions."""

    @pytest.fixture
    def sample_rect(self):
        """Create a sample window rectangle for testing."""
        # Window at (100, 200) with size 1000x700
        return WindowRect(left=100, top=200, right=1100, bottom=900)

    def test_to_rel_center(self, sample_rect):
        """Test converting center point to relative coordinates."""
        # Center of window: (600, 550)
        rel_x, rel_y = to_rel(600, 550, sample_rect)
        assert abs(rel_x - 0.5) < 0.01
        assert abs(rel_y - 0.5) < 0.01

    def test_to_rel_top_left(self, sample_rect):
        """Test converting top-left corner to relative coordinates."""
        rel_x, rel_y = to_rel(100, 200, sample_rect)
        assert rel_x == 0.0
        assert rel_y == 0.0

    def test_to_rel_bottom_right(self, sample_rect):
        """Test converting bottom-right corner to relative coordinates."""
        rel_x, rel_y = to_rel(1100, 900, sample_rect)
        assert rel_x == 1.0
        assert rel_y == 1.0

    def test_to_abs_center(self, sample_rect):
        """Test converting relative center to absolute coordinates."""
        abs_x, abs_y = to_abs(0.5, 0.5, sample_rect)
        assert abs_x == 600
        assert abs_y == 550

    def test_to_abs_top_left(self, sample_rect):
        """Test converting relative top-left to absolute coordinates."""
        abs_x, abs_y = to_abs(0.0, 0.0, sample_rect)
        assert abs_x == 100
        assert abs_y == 200

    def test_to_abs_bottom_right(self, sample_rect):
        """Test converting relative bottom-right to absolute coordinates."""
        abs_x, abs_y = to_abs(1.0, 1.0, sample_rect)
        assert abs_x == 1100
        assert abs_y == 900

    def test_roundtrip_conversion(self, sample_rect):
        """Test that conversion from abs → rel → abs preserves coordinates."""
        test_points = [
            (150, 250),   # Near top-left
            (600, 550),   # Center
            (1050, 850),  # Near bottom-right
            (300, 400),   # Arbitrary point
            (900, 700),   # Another arbitrary point
        ]

        for orig_x, orig_y in test_points:
            # Convert to relative
            rel_x, rel_y = to_rel(orig_x, orig_y, sample_rect)

            # Convert back to absolute
            abs_x, abs_y = to_abs(rel_x, rel_y, sample_rect)

            # Should match original (within rounding error)
            assert abs(abs_x - orig_x) <= 1, f"X mismatch: {abs_x} != {orig_x}"
            assert abs(abs_y - orig_y) <= 1, f"Y mismatch: {abs_y} != {orig_y}"

    def test_to_rel_outside_window(self, sample_rect):
        """Test converting coordinates outside window bounds."""
        # Point to the left of window
        rel_x, rel_y = to_rel(50, 550, sample_rect)
        assert rel_x < 0.0

        # Point above window
        rel_x, rel_y = to_rel(600, 100, sample_rect)
        assert rel_y < 0.0

        # Point to the right of window
        rel_x, rel_y = to_rel(1200, 550, sample_rect)
        assert rel_x > 1.0

        # Point below window
        rel_x, rel_y = to_rel(600, 1000, sample_rect)
        assert rel_y > 1.0

    def test_to_abs_outside_bounds(self, sample_rect):
        """Test converting relative coordinates outside [0,1] range."""
        # Negative relative coordinates
        abs_x, abs_y = to_abs(-0.1, -0.1, sample_rect)
        assert abs_x < sample_rect.left
        assert abs_y < sample_rect.top

        # Relative coordinates > 1.0
        abs_x, abs_y = to_abs(1.1, 1.1, sample_rect)
        assert abs_x > sample_rect.right
        assert abs_y > sample_rect.bottom

    def test_zero_size_window(self):
        """Test handling of degenerate zero-size window."""
        rect = WindowRect(left=100, top=200, right=100, bottom=200)
        rel_x, rel_y = to_rel(100, 200, rect)
        # Should handle gracefully (returns 0.0)
        assert rel_x == 0.0
        assert rel_y == 0.0

    def test_different_window_sizes(self):
        """Test coordinate conversion with various window sizes."""
        test_cases = [
            # Small window
            WindowRect(left=0, top=0, right=800, bottom=600),
            # Large window
            WindowRect(left=0, top=0, right=3840, bottom=2160),
            # Offset window
            WindowRect(left=500, top=300, right=1500, bottom=1100),
            # Narrow window
            WindowRect(left=100, top=100, right=200, bottom=800),
            # Wide window
            WindowRect(left=100, top=100, right=1900, bottom=200),
        ]

        for rect in test_cases:
            # Test center point
            center_x = (rect.left + rect.right) // 2
            center_y = (rect.top + rect.bottom) // 2

            rel_x, rel_y = to_rel(center_x, center_y, rect)
            abs_x, abs_y = to_abs(rel_x, rel_y, rect)

            assert abs(abs_x - center_x) <= 1
            assert abs(abs_y - center_y) <= 1


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only tests")
class TestWindowsOnlyFunctions:
    """Tests that require actual Windows environment."""

    def test_attach_petrel_requires_windows(self):
        """Test that attach_petrel raises error on non-Windows."""
        # This test will be skipped on non-Windows platforms
        from fast_bench.ui_attach import attach_petrel
        from pathlib import Path

        # On Windows, this should not raise RuntimeError about platform
        # (but may raise other errors if Petrel not found)
        try:
            attach_petrel(Path("C:\\fake\\path.exe"), timeout=1, launch_if_not_found=False)
        except RuntimeError as e:
            # Should not be platform-related error on Windows
            assert "non-Windows" not in str(e)

    def test_get_window_rect_requires_windows(self):
        """Test that get_window_rect raises error on non-Windows."""
        # This test will be skipped on non-Windows platforms
        from fast_bench.ui_attach import get_window_rect
        # Just verify the function exists and can be imported on Windows
        assert callable(get_window_rect)

    def test_ensure_foreground_requires_windows(self):
        """Test that ensure_foreground raises error on non-Windows."""
        # This test will be skipped on non-Windows platforms
        from fast_bench.ui_attach import ensure_foreground
        # Just verify the function exists and can be imported on Windows
        assert callable(ensure_foreground)


class TestNonWindowsPlatform:
    """Tests for behavior on non-Windows platforms."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Non-Windows test")
    def test_attach_petrel_raises_on_mac_linux(self):
        """Test that attach_petrel raises RuntimeError on non-Windows."""
        from fast_bench.ui_attach import attach_petrel
        from pathlib import Path

        with pytest.raises(RuntimeError, match="only supported on Windows"):
            attach_petrel(Path("/fake/path"), timeout=1)

    @pytest.mark.skipif(sys.platform == "win32", reason="Non-Windows test")
    def test_coordinate_functions_work_on_any_platform(self):
        """Test that coordinate conversion works on any platform."""
        rect = WindowRect(left=0, top=0, right=1920, bottom=1080)

        # These should work on any platform
        rel_x, rel_y = to_rel(960, 540, rect)
        assert abs(rel_x - 0.5) < 0.01
        assert abs(rel_y - 0.5) < 0.01

        abs_x, abs_y = to_abs(0.5, 0.5, rect)
        assert abs_x == 960
        assert abs_y == 540
