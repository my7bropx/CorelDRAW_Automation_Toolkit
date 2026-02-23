"""
CorelDRAW COM Interface Module
Provides a Python wrapper for CorelDRAW's COM/Automation API.
Supports CorelDRAW versions 2018-2024+.
"""

import logging
from typing import Any, List, Optional, Tuple, Dict
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager
import math

try:
    import win32com.client
    import pythoncom
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False
    win32com = None
    pythoncom = None
logger = logging.getLogger(__name__)
class CorelDRAWError(Exception):
    """Base exception for CorelDRAW-related errors."""
    pass
class CorelDRAWNotFoundError(CorelDRAWError):
    """Raised when CorelDRAW is not found or not installed."""
    pass
class CorelDRAWConnectionError(CorelDRAWError):
    """Raised when unable to connect to CorelDRAW."""
    pass
class NoDocumentError(CorelDRAWError):
    """Raised when no document is open in CorelDRAW."""
    pass
class NoSelectionError(CorelDRAWError):
    """Raised when no objects are selected."""
    pass

class ShapeType(Enum):
    """CorelDRAW shape types."""
    CURVE = 1
    RECTANGLE = 2
    ELLIPSE = 3
    POLYGON = 4
    TEXT = 5
    BITMAP = 6
    GROUP = 7
    SYMBOL = 8
    CONNECTOR = 9
    OLE = 10
    CUSTOM = 11


@dataclass
class Point:
    """Represents a 2D point."""
    x: float
    y: float

    def distance_to(self, other: 'Point') -> float:
        """Calculate distance to another point."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def angle_to(self, other: 'Point') -> float:
        """Calculate angle to another point in degrees."""
        return math.degrees(math.atan2(other.y - self.y, other.x - self.x))

    def to_tuple(self) -> Tuple[float, float]:
        """Convert to tuple."""
        return (self.x, self.y)

@dataclass
class BoundingBox:
    """Represents a bounding box."""
    left: float
    bottom: float
    right: float
    top: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    @property
    def center(self) -> Point:
        return Point(
            (self.left + self.right) / 2,
            (self.bottom + self.top) / 2
        )

    def contains_point(self, point: Point) -> bool:
        """Check if point is inside bounding box."""
        return (self.left <= point.x <= self.right and
                self.bottom <= point.y <= self.top)

@dataclass
class CurveNode:
    """Represents a node on a curve."""
    position: Point
    type: str = "cusp"
    segment_type: str = "line"  # line, curve

@dataclass
class CurveSegment:
    """Represents a segment of a curve."""
    start: Point
    end: Point
    control1: Optional[Point] = None
    control2: Optional[Point] = None
    is_bezier: bool = False

    def get_point_at_t(self, t: float) -> Point:
        """
        Get point at parameter t (0 to 1) along the segment.
        Uses cubic Bezier interpolation for curved segments.
        """
        if not self.is_bezier or not self.control1 or not self.control2:
            return Point(
                self.start.x + t * (self.end.x - self.start.x),
                self.start.y + t * (self.end.y - self.start.y)
            )

        # Cubic Bezier interpolation
        t2 = t * t
        t3 = t2 * t
        mt = 1 - t
        mt2 = mt * mt
        mt3 = mt2 * mt

        x = (mt3 * self.start.x +
             3 * mt2 * t * self.control1.x +
             3 * mt * t2 * self.control2.x +
             t3 * self.end.x)
        y = (mt3 * self.start.y +
             3 * mt2 * t * self.control1.y +
             3 * mt * t2 * self.control2.y +
             t3 * self.end.y)

        return Point(x, y)

    def get_tangent_at_t(self, t: float) -> float:
        """Get tangent angle at parameter t (in degrees)."""
        delta = 0.001
        t1 = max(0, t - delta)
        t2 = min(1, t + delta)

        p1 = self.get_point_at_t(t1)
        p2 = self.get_point_at_t(t2)

        return p1.angle_to(p2)

    @property
    def length(self) -> float:
        """Approximate segment length."""
        if not self.is_bezier:
            return self.start.distance_to(self.end)

        # Approximate with multiple samples
        total = 0.0
        steps = 20
        prev = self.start
        for i in range(1, steps + 1):
            t = i / steps
            curr = self.get_point_at_t(t)
            total += prev.distance_to(curr)
            prev = curr
        return total


class CorelDRAWInterface:
    """
    Main interface for CorelDRAW COM automation.
    Provides high-level methods for document manipulation.
    """

    def __init__(self):
        """Initialize the CorelDRAW interface."""
        if not HAS_WIN32COM:
            raise ImportError(
                "pywin32 is required for CorelDRAW integration. "
                "Install with: pip install pywin32"
            )

        self._app = None
        self._connected = False
        self._version = None
        logger.info("CorelDRAW interface initialized.")

    def connect(self) -> bool:
        """
        Connect to a running CorelDRAW instance.

        Returns:
            bool: True if connected successfully.

        Raises:
            CorelDRAWNotFoundError: If CorelDRAW is not found.
            CorelDRAWConnectionError: If connection fails.
        """
        pythoncom.CoInitialize()
        
        # Try most recent versions first (faster connection)
        clsids = [
            "CorelDRAW.Application.26",  # 2024
            "CorelDRAW.Application.25",  # 2023
            "CorelDRAW.Application.24",  # 2022
            "CorelDRAW.Application.23",  # 2021
            "CorelDRAW.Application.22",  # 2020
            "CorelDRAW.Application.21",  # 2019
            "CorelDRAW.Application.20",  # 2018
        ]
        
        # Try generic "CorelDRAW.Application" first (works for any recent version)
        try:
            self._app = win32com.client.Dispatch("CorelDRAW.Application")
            self._connected = True
            self._version = self._get_version()
            logger.info(f"Connected to CorelDRAW {self._version}")
            return True
        except Exception:
            pass
        
        # Fall back to version-specific CLSIDs
        for clsid in clsids:
            try:
                self._app = win32com.client.Dispatch(clsid)
                self._connected = True
                self._version = self._get_version()
                logger.info(f"Connected to CorelDRAW {self._version}")
                return True
            except Exception:
                continue
        
        self._connected = False
        raise CorelDRAWConnectionError("Could not connect to any CorelDRAW version (2018-2024)")

    def disconnect(self):
        """Disconnect from CorelDRAW."""
        self._app = None
        self._connected = False
        try:
            pythoncom.CoUninitialize()
        except:
            pass
        logger.info("Disconnected from CorelDRAW.")

    def _get_version(self) -> str:
        """Get CorelDRAW version string."""
        try:
            version_major = self._app.VersionMajor
            version_minor = self._app.VersionMinor
            return f"{version_major}.{version_minor}"
        except:
            return "Unknown"

    @property
    def is_connected(self) -> bool:
        """Check if connected to CorelDRAW."""
        return self._connected and self._app is not None

    @property
    def version(self) -> str:
        """Get CorelDRAW version."""
        return self._version or "Not connected"

    @property
    def app(self):
        """Get the raw CorelDRAW application object."""
        if not self.is_connected:
            raise CorelDRAWConnectionError("Not connected to CorelDRAW.")
        return self._app

    def ensure_document(self):
        """
        Ensure a document is open.

        Raises:
            NoDocumentError: If no document is open.
        """
        if not self.is_connected:
            raise CorelDRAWConnectionError("Not connected to CorelDRAW.")

        if self._app.Documents.Count == 0:
            raise NoDocumentError("No document is open in CorelDRAW.")
    @property
    def active_document(self):
        """Get the active document."""
        self.ensure_document()
        return self._app.ActiveDocument

    @property
    def active_layer(self):
        """Get the active layer."""
        return self.active_document.ActiveLayer

    @property
    def active_page(self):
        """Get the active page."""
        return self.active_document.ActivePage

    def get_selection(self):
        """
        Get the current selection.

        Returns:
            ShapeRange object containing selected shapes.

        Raises:
            NoSelectionError: If nothing is selected.
        """
        self.ensure_document()
        try:
            sel = self._app.ActiveSelection
            if sel is None or sel.Shapes is None or sel.Shapes.Count == 0:
                raise NoSelectionError("No objects are selected.")
            return sel.Shapes
        except Exception as e:
            logger.error(f"Error getting selection: {e}")
            raise NoSelectionError(f"Could not get selection: {e}")

    def get_selection_count(self) -> int:
        """Get the number of selected objects."""
        try:
            return self._app.ActiveSelection.Shapes.Count
        except:
            return 0

    def begin_command_group(self, name: str = "Automation"):
        """Begin a command group for undo support."""
        self.ensure_document()
        self.active_document.BeginCommandGroup(name)

    def end_command_group(self):
        """End the current command group."""
        self.ensure_document()
        self.active_document.EndCommandGroup()

    def get_shape_bounds(self, shape) -> BoundingBox:
        """Get bounding box of a shape."""
        return BoundingBox(
            shape.LeftX,
            shape.BottomY,
            shape.RightX,
            shape.TopY
        )

    def duplicate_shape(self, shape, offset_x: float = 0, offset_y: float = 0):
        """
        Duplicate a shape with optional offset.

        Args:
            shape: Shape to duplicate.
            offset_x: X offset for the duplicate.
            offset_y: Y offset for the duplicate.

        Returns:
            The duplicated shape.
        """
        new_shape = shape.Duplicate()
        if offset_x != 0 or offset_y != 0:
            new_shape.Move(offset_x, offset_y)
        return new_shape

    def move_shape(self, shape, x: float, y: float):
        """Move a shape to absolute coordinates."""
        shape.SetPosition(x, y)

    def rotate_shape(self, shape, angle: float, center_x: float = None, center_y: float = None):
        """
        Rotate a shape by the given angle.

        Args:
            shape: Shape to rotate.
            angle: Rotation angle in degrees.
            center_x: X coordinate of rotation center (optional).
            center_y: Y coordinate of rotation center (optional).
        """
        if center_x is not None and center_y is not None:
            shape.RotateEx(angle, center_x, center_y)
        else:
            shape.Rotate(angle)

    def scale_shape(self, shape, scale_x: float, scale_y: float = None):
        """
        Scale a shape.

        Args:
            shape: Shape to scale.
            scale_x: Horizontal scale factor (1.0 = 100%).
            scale_y: Vertical scale factor (defaults to scale_x).
        """
        if scale_y is None:
            scale_y = scale_x
        shape.Stretch(scale_x, scale_y)

    def get_curve_path(self, shape) -> List[CurveSegment]:
        """
        Extract path data from a curve shape.

        Args:
            shape: The curve shape to extract path from.

        Returns:
            List of CurveSegment objects describing the path.
        """
        segments = []

        try:
            # Convert to curve if not already
            if not hasattr(shape, 'Curve') or shape.Curve is None:
                shape.ConvertToCurves()

            curve = shape.Curve
            if curve is None:
                logger.warning("Shape has no curve data.")
                return segments

            # Iterate through subpaths
            for subpath_idx in range(1, curve.SubPaths.Count + 1):
                subpath = curve.SubPaths.Item(subpath_idx)

                # Iterate through segments
                for seg_idx in range(1, subpath.Segments.Count + 1):
                    seg = subpath.Segments.Item(seg_idx)
                    start_node = seg.StartNode
                    start_point = Point(start_node.PositionX, start_node.PositionY)
                    end_node = seg.EndNode
                    end_point = Point(end_node.PositionX, end_node.PositionY)
                    is_bezier = seg.Type == 2  # cdrCurveSegment
                    control1 = None
                    control2 = None

                    if is_bezier:
                        try:
                            ctrl1_x = start_node.PositionX + seg.StartingControlPointOffset[0]
                            ctrl1_y = start_node.PositionY + seg.StartingControlPointOffset[1]
                            control1 = Point(ctrl1_x, ctrl1_y)

                            ctrl2_x = end_node.PositionX + seg.EndingControlPointOffset[0]
                            ctrl2_y = end_node.PositionY + seg.EndingControlPointOffset[1]
                            control2 = Point(ctrl2_x, ctrl2_y)
                        except:
                            is_bezier = False
                    segment = CurveSegment(
                        start=start_point,
                        end=end_point,
                        control1=control1,
                        control2=control2,
                        is_bezier=is_bezier
                    )
                    segments.append(segment)
        except Exception as e:
            logger.error(f"Error extracting curve path: {e}")
        return segments

    def get_curve_total_length(self, segments: List[CurveSegment]) -> float:
        """Calculate total length of curve from segments."""
        return sum(seg.length for seg in segments)

    def get_point_on_curve(self, segments: List[CurveSegment], distance: float) -> Tuple[Point, float]:
        """
        Get a point on the curve at a specific distance from start.

        Args:
            segments: List of curve segments.
            distance: Distance along the curve.

        Returns:
            Tuple of (Point, tangent_angle).
        """
        current_dist = 0.0

        for seg in segments:
            seg_len = seg.length
            if current_dist + seg_len >= distance:
                # Point is in this segment
                remaining = distance - current_dist
                t = remaining / seg_len if seg_len > 0 else 0
                point = seg.get_point_at_t(t)
                angle = seg.get_tangent_at_t(t)
                return (point, angle)
            current_dist += seg_len

        # If distance exceeds curve length, return end point
        if segments:
            last_seg = segments[-1]
            return (last_seg.end, last_seg.get_tangent_at_t(1.0))

        return (Point(0, 0), 0.0)

    def is_point_inside_shape(self, shape, point: Point) -> bool:
        """
        Check if a point is inside a closed shape.

        Args:
            shape: The shape to check.
            point: The point to test.

        Returns:
            bool: True if point is inside shape.
        """
        try:
            return shape.IsPointInside(point.x, point.y)
        except:
            # Fallback to bounding box check
            bounds = self.get_shape_bounds(shape)
            return bounds.contains_point(point)

    def get_shape_center(self, shape) -> Point:
        """Get the center point of a shape."""
        return Point(shape.CenterX, shape.CenterY)

    def create_group(self, shapes) -> Any:
        """Create a group from multiple shapes."""
        self.ensure_document()
        return shapes.Group()

    def ungroup(self, group):
        """Ungroup a group shape."""
        return group.Ungroup()

    def delete_shape(self, shape):
        """Delete a shape."""
        shape.Delete()

    @contextmanager
    def optimization_mode(self):
        """
        Context manager for performance optimization.
        Automatically enables optimization and ensures it's disabled on exit.
        Usage:
            with corel.optimization_mode():
                # perform multiple operations
                pass
        """
        self.enable_optimization()
        try:
            yield
        finally:
            self.disable_optimization()

    @contextmanager
    def command_group(self, name: str = "Automation"):
        """
        Context manager for command grouping (undo support).
        
        Usage:
            with corel.command_group("My Operation"):
                # perform multiple operations
                pass
        """
        self.begin_command_group(name)
        try:
            yield
        except Exception as e:
            logger.error(f"Command group '{name}' failed: {e}")
            raise
        finally:
            self.end_command_group()
    def refresh(self):
        """Refresh the CorelDRAW display."""
        try:
            self._app.Refresh()
        except Exception as e:
            logger.warning(f"Failed to refresh CorelDRAW: {e}")
    def enable_optimization(self):
        """Enable performance optimization mode."""
        try:
            self._app.Optimization = True
            self._app.EventsEnabled = False
        except Exception as e:
            logger.warning(f"Failed to enable optimization: {e}")

    def disable_optimization(self):
        """Disable performance optimization mode."""
        try:
            self._app.Optimization = False
            self._app.EventsEnabled = True
            self.refresh()
        except Exception as e:
            logger.warning(f"Failed to disable optimization: {e}")
    def is_point_in_shape(self, x: float, y: float, shape=None) -> bool:
        """
        Check if a point is inside a shape.
        Args:
            x: X coordinate.
            y: Y coordinate.
            shape: Shape to check (optional, uses selection if not provided).
        Returns:
            True if point is inside the shape.
        """
        try:
            if shape is None:
                selection = self.get_selection()
                if selection.Count == 0:
                    return True
                shape = selection.Item(1)
            # Prefer direct point test when available (much faster than temp shapes).
            try:
                if hasattr(shape, "IsPointInside"):
                    return shape.IsPointInside(x, y)
            except Exception:
                pass
            doc = self.get_active_document()
            if doc:
                point = doc.ActiveLayer.CreateRectangle(x, y, x + 0.1, y + 0.1)
                try:
                    result = shape.IsIntersecting(point)
                    point.Delete()
                    return result
                except:
                    point.Delete()
                    return True
            return True
        except Exception as e:
            logger.debug(f"Point check error: {e}")
            return True
corel = CorelDRAWInterface()
