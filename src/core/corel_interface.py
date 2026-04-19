"""
CorelDRAW COM Interface Module
Provides a Python wrapper for CorelDRAW's COM/Automation API.
Supports CorelDRAW versions 2018-2024+.
"""

import logging
import threading
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
    """
    CorelDRAW shape types — matched to actual COM constants.
    Use shape.Type to compare against these values.
    cdrLineShape=1, cdrCurveShape=2, cdrRectangleShape=3,
    cdrEllipseShape=4, cdrTextShape=5, cdrGroupShape=6,
    cdrBitmapShape=7
    """
    LINE      = 1   # cdrLineShape
    CURVE     = 2   # cdrCurveShape
    RECTANGLE = 3   # cdrRectangleShape
    ELLIPSE   = 4   # cdrEllipseShape
    TEXT      = 5   # cdrTextShape
    GROUP     = 6   # cdrGroupShape
    BITMAP    = 7   # cdrBitmapShape
    SYMBOL    = 8
    CONNECTOR = 9
    OLE       = 10
    CUSTOM    = 11


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
        self._app = None
        self._app_thread_id = None
        self._connected = False
        self._version = None
        self._active_progid = None
        self._available = HAS_WIN32COM
        self._unavailable_reason = None
        if not HAS_WIN32COM:
            self._unavailable_reason = (
                "pywin32 is required for CorelDRAW integration. "
                "Install with: pip install pywin32"
            )
            logger.warning(self._unavailable_reason)
        logger.info("CorelDRAW interface initialized.")

    def _current_thread_id(self) -> int:
        return threading.get_ident()

    def _attach_to_app(self, progid: str):
        """Attach the current thread to a running CorelDRAW COM server."""
        last_error = None
        try:
            return win32com.client.GetActiveObject(progid)
        except Exception as exc:
            last_error = exc
        try:
            return win32com.client.Dispatch(progid)
        except Exception as exc:
            if last_error is not None:
                logger.debug("Corel attach fallback failed for %s after GetActiveObject error: %s / %s", progid, last_error, exc)
            raise

    def _bind_current_thread(self, progid: str):
        app = self._attach_to_app(progid)
        self._app = app
        self._app_thread_id = self._current_thread_id()
        self._active_progid = progid
        return app

    def _ensure_thread_app(self):
        """
        Ensure the current thread has a valid COM proxy.

        CorelDRAW COM proxies are thread-affine. Worker threads must reattach to
        the running CorelDRAW instance instead of reusing the main-thread proxy.
        """
        if not self._connected or self._app is None:
            return None
        if self._app_thread_id == self._current_thread_id():
            return self._app
        if not self._active_progid:
            return None
        try:
            return self._bind_current_thread(self._active_progid)
        except Exception as exc:
            logger.warning("Failed to bind CorelDRAW COM proxy on thread %s: %s", self._current_thread_id(), exc)
            self._connected = False
            self._app = None
            self._app_thread_id = None
            return None

    def connect(self, preferred_version: str = None) -> bool:
        """
        Connect to a running CorelDRAW instance.

        Args:
            preferred_version: Specific version to connect to (e.g., "2020", "2024").
                             If None, connects to any available version.

        Returns:
            bool: True if connected successfully.

        Raises:
            CorelDRAWNotFoundError: If CorelDRAW is not found.
            CorelDRAWConnectionError: If connection fails.
        """
        if not self._available:
            raise CorelDRAWConnectionError(self._unavailable_reason or "CorelDRAW integration is unavailable.")

        pythoncom.CoInitialize()
        
        version_clsid_map = {
            "2024": "CorelDRAW.Application.26",
            "2023": "CorelDRAW.Application.25",
            "2022": "CorelDRAW.Application.24",
            "2021": "CorelDRAW.Application.23",
            "2020": "CorelDRAW.Application.22",
            "2019": "CorelDRAW.Application.21",
            "2018": "CorelDRAW.Application.20",
        }
        
        clsids = [
            "CorelDRAW.Application.26",  # 2024
            "CorelDRAW.Application.25",  # 2023
            "CorelDRAW.Application.24",  # 2022
            "CorelDRAW.Application.23",  # 2021
            "CorelDRAW.Application.22",  # 2020
            "CorelDRAW.Application.21",  # 2019
            "CorelDRAW.Application.20",  # 2018
        ]
        
        # If a specific version is requested, try that first
        if preferred_version and preferred_version in version_clsid_map:
            preferred_clsid = version_clsid_map[preferred_version]
            try:
                self._bind_current_thread(preferred_clsid)
                self._connected = True
                self._version = self._get_version()
                logger.info(f"Connected to CorelDRAW {self._version} (requested: {preferred_version})")
                return True
            except Exception as e:
                logger.warning(f"Could not connect to preferred version {preferred_version}: {e}")
        
        # Try generic "CorelDRAW.Application" first (works for any recent version)
        try:
            self._bind_current_thread("CorelDRAW.Application")
            self._connected = True
            self._version = self._get_version()
            logger.info(f"Connected to CorelDRAW {self._version}")
            return True
        except Exception:
            pass
        
        # Fall back to version-specific CLSIDs
        for clsid in clsids:
            try:
                self._bind_current_thread(clsid)
                self._connected = True
                self._version = self._get_version()
                logger.info(f"Connected to CorelDRAW {self._version}")
                return True
            except Exception:
                continue
        
        self._connected = False
        raise CorelDRAWConnectionError("Could not connect to any CorelDRAW version (2018-2024)")

    @classmethod
    def detect_installed_versions(cls) -> List[Dict[str, str]]:
        """
        Detect installed CorelDRAW versions on the system.
        
        Returns:
            List of dicts with 'year', 'version', 'clsid' keys.
        """
        if not HAS_WIN32COM:
            return []
        
        pythoncom.CoInitialize()
        
        version_map = {
            "26": {"year": "2024", "version": "2024", "clsid": "CorelDRAW.Application.26"},
            "25": {"year": "2023", "version": "2023", "clsid": "CorelDRAW.Application.25"},
            "24": {"year": "2022", "version": "2022", "clsid": "CorelDRAW.Application.24"},
            "23": {"year": "2021", "version": "2021", "clsid": "CorelDRAW.Application.23"},
            "22": {"year": "2020", "version": "2020", "clsid": "CorelDRAW.Application.22"},
            "21": {"year": "2019", "version": "2019", "clsid": "CorelDRAW.Application.21"},
            "20": {"year": "2018", "version": "2018", "clsid": "CorelDRAW.Application.20"},
        }
        
        installed = []
        
        for clsid_ver, info in version_map.items():
            try:
                app = win32com.client.Dispatch(info["clsid"])
                actual_ver = f"{app.VersionMajor}.{app.VersionMinor}"
                installed.append({
                    "year": info["year"],
                    "version": info["version"],
                    "clsid": info["clsid"],
                    "actual_version": actual_ver
                })
                app = None
            except Exception:
                pass
        
        try:
            pythoncom.CoUninitialize()
        except:
            pass
        
        return installed

    def disconnect(self):
        """Disconnect from CorelDRAW."""
        self._app = None
        self._app_thread_id = None
        self._connected = False
        self._active_progid = None
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
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
        """
        Check if connected to CorelDRAW.

        Does a real COM ping — not just a flag check. If CorelDRAW has been
        closed since we connected, `self._app` holds a stale COM reference
        that will raise COMError on any access. We detect that here and reset
        the connection state so callers get a clean False instead of a crash.
        """
        if not self._connected:
            return False
        app = self._ensure_thread_app()
        if app is None:
            return False
        try:
            # Lightweight property read — raises immediately if COM object is stale
            _ = app.Visible
            return True
        except Exception:
            # CorelDRAW was closed or COM reference became invalid
            self._connected = False
            self._app = None
            self._app_thread_id = None
            logger.warning("CorelDRAW connection lost (COM object is stale).")
            return False

    def get_document_units(self) -> str:
        """
        Return the unit system of the active document as a string.

        Possible values: 'mm', 'inch', 'point', 'pica', 'cm', 'pixel', 'unknown'.
        All engine calculations assume mm. Call this on connect and warn the
        user if the document is not in millimeters.
        """
        # CorelDRAW unit constants (cdrUnit enum)
        UNIT_MAP = {
            0: 'inch',
            1: 'mm',
            2: 'point',
            3: 'pica',
            4: 'cm',
            5: 'pixel',
        }
        try:
            unit_id = self.active_document.Unit
            return UNIT_MAP.get(unit_id, 'unknown')
        except Exception:
            return 'unknown'

    def validate_document_units(self) -> bool:
        """
        Return True if the active document is in millimeters.
        Logs a clear warning if not. Call this before any engine operation.
        """
        units = self.get_document_units()
        if units != 'mm':
            logger.warning(
                f"Document unit is '{units}', not 'mm'. "
                "All engine calculations assume millimeters — "
                "sizes and positions will be wrong. "
                "Change your document units to mm in CorelDRAW before proceeding."
            )
            return False
        return True

    @property
    def version(self) -> str:
        """Get CorelDRAW version."""
        if self._connected:
            self._ensure_thread_app()
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
        self._ensure_thread_app()

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

    def get_or_create_layer(self, layer_name: str):
        """Return a named layer on the active page, creating it if needed."""
        page = self.active_page
        for index in range(1, page.Layers.Count + 1):
            layer = page.Layers(index)
            if getattr(layer, "Name", "") == layer_name:
                return layer
        return page.CreateLayer(layer_name)

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
            shape_range = self._get_selection_shape_range()
            if shape_range is None or shape_range.Count == 0:
                raise NoSelectionError("No objects are selected.")
            return shape_range
        except Exception as e:
            logger.error(f"Error getting selection: {e}")
            raise NoSelectionError(f"Could not get selection: {e}")

    def get_selection_count(self) -> int:
        """Get the number of selected objects."""
        try:
            selection = self._get_selection_shape_range()
            return selection.Count if selection is not None else 0
        except:
            return 0

    def has_selection(self) -> bool:
        """Check if there is any selection."""
        return self.get_selection_count() > 0

    def get_selected_shapes(self):
        """Get the currently selected shapes as a list."""
        try:
            selection = self._get_selection_shape_range()
            if selection is None or selection.Count == 0:
                return []
            shapes = []
            for i in range(1, selection.Count + 1):
                shapes.append(selection.Item(i))
            return shapes
        except:
            return []

    def run_macro(self, macro_name: str, argument: Optional[str] = None):
        """
        Execute a CorelDRAW VBA/GMS macro with an optional string argument.

        The exact COM entry point differs between CorelDRAW versions, so this
        method tries the supported automation routes in order and fails clearly
        if none of them are available.
        """
        self.ensure_document()
        attempted = []

        try:
            gms_manager = getattr(self._app, "GMSManager", None)
            if gms_manager is not None:
                if argument is not None:
                    try:
                        return gms_manager.RunMacro(macro_name, argument)
                    except Exception as exc:
                        attempted.append(f"GMSManager.RunMacro(name,arg): {exc}")
                try:
                    return gms_manager.RunMacro(macro_name)
                except Exception as exc:
                    attempted.append(f"GMSManager.RunMacro(name): {exc}")
        except Exception as exc:
            attempted.append(f"GMSManager access: {exc}")

        try:
            if argument is not None:
                try:
                    return self._app.RunMacro(macro_name, argument)
                except Exception as exc:
                    attempted.append(f"Application.RunMacro(name,arg): {exc}")
            return self._app.RunMacro(macro_name)
        except Exception as exc:
            attempted.append(f"Application.RunMacro(name): {exc}")

        message = "; ".join(attempted) if attempted else "No macro entry points were available."
        logger.error("Failed to run CorelDRAW macro '%s': %s", macro_name, message)
        raise CorelDRAWError(f"Could not run CorelDRAW macro '{macro_name}': {message}")

    def _get_selection_shape_range(self):
        """
        Return the current selection as a CorelDRAW ShapeRange-like COM object.

        CorelDRAW can expose the current object through different properties
        depending on the active tool or edit mode. In node-edit mode, for
        example, ActiveSelection.Shapes may be empty while ActiveShape is still
        the selected curve. This helper normalizes those cases.
        """
        self.ensure_document()

        # 1. Standard selection object
        try:
            selection = self._app.ActiveSelection
            if selection is not None:
                shapes = getattr(selection, "Shapes", None)
                if shapes is not None and shapes.Count > 0:
                    return shapes
        except Exception:
            pass

        # 2. Some CorelDRAW versions expose the selection directly as a range
        try:
            selection_range = getattr(self._app, "ActiveSelectionRange", None)
            if selection_range is not None and selection_range.Count > 0:
                return selection_range
        except Exception:
            pass

        # 3. Fallback for node-edit / active-object mode
        try:
            active_shape = getattr(self._app, "ActiveShape", None)
            if active_shape is not None:
                shape_range = self._app.CreateShapeRange()
                shape_range.Add(active_shape)
                if shape_range.Count > 0:
                    return shape_range
        except Exception:
            pass

        return None

    def get_active_document_name(self) -> str:
        """Get the name of the active document."""
        try:
            if self._app.Documents.Count > 0:
                return self._app.ActiveDocument.Name
            return ""
        except:
            return ""

    def has_active_document(self) -> bool:
        """Check if there is an active document."""
        try:
            return self._app.Documents.Count > 0
        except:
            return False

    def begin_command_group(self, name: str = "Automation"):
        """Begin a command group for undo support."""
        self.ensure_document()
        self.active_document.BeginCommandGroup(name)

    def end_command_group(self):
        """End the current command group."""
        self.ensure_document()
        self.active_document.EndCommandGroup()

    def get_active_document(self):
        """
        Get the active document as a callable method.
        Safe wrapper around the active_document property.
        Returns None instead of raising if no document is open.
        """
        try:
            return self.active_document
        except Exception:
            return None

    def _corel_to_mm(self, value: float) -> float:
        """Convert CorelDRAW geometry values from internal units to millimeters."""
        return float(value) * 25.4

    def _mm_to_corel(self, value: float) -> float:
        """Convert millimeters to CorelDRAW internal geometry units."""
        return float(value) / 25.4

    def _outline_width_mm(self, shape) -> float:
        """Best-effort outline width in millimeters."""
        try:
            outline = getattr(shape, "Outline", None)
            if outline is None:
                return 0.0
            width = getattr(outline, "Width", 0.0) or 0.0
            return self._corel_to_mm(width)
        except Exception:
            return 0.0

    def describe_shape_metrics(self, shape) -> Dict[str, Any]:
        """Return a diagnostic snapshot of raw and normalized shape metrics."""
        raw_left = float(shape.LeftX)
        raw_bottom = float(shape.BottomY)
        raw_right = float(shape.RightX)
        raw_top = float(shape.TopY)
        raw_width = float(shape.SizeWidth)
        raw_height = float(shape.SizeHeight)

        bounds = BoundingBox(
            left=self._corel_to_mm(raw_left),
            bottom=self._corel_to_mm(raw_bottom),
            right=self._corel_to_mm(raw_right),
            top=self._corel_to_mm(raw_top),
        )

        true_width = self._corel_to_mm(raw_width)
        true_height = self._corel_to_mm(raw_height)

        return {
            "name": getattr(shape, "Name", "Unnamed shape") or "Unnamed shape",
            "type": getattr(shape, "Type", "Unknown"),
            "document_units": self.get_document_units(),
            "raw_true_width": raw_width,
            "raw_true_height": raw_height,
            "raw_bounds_width": raw_right - raw_left,
            "raw_bounds_height": raw_top - raw_bottom,
            "true_width_mm": true_width,
            "true_height_mm": true_height,
            "bounds_width_mm": bounds.width,
            "bounds_height_mm": bounds.height,
            "outline_width_mm": self._outline_width_mm(shape),
        }

    def log_shape_metrics(self, shape, prefix: str = "Shape metrics") -> None:
        """Log raw and normalized shape metrics for debugging."""
        try:
            metrics = self.describe_shape_metrics(shape)
            logger.info(
                "%s: name=%s type=%s doc_units=%s true_mm=(%.4f, %.4f) bounds_mm=(%.4f, %.4f) "
                "outline_mm=%.4f raw_true=(%.4f, %.4f) raw_bounds=(%.4f, %.4f)",
                prefix,
                metrics["name"],
                metrics["type"],
                metrics["document_units"],
                metrics["true_width_mm"],
                metrics["true_height_mm"],
                metrics["bounds_width_mm"],
                metrics["bounds_height_mm"],
                metrics["outline_width_mm"],
                metrics["raw_true_width"],
                metrics["raw_true_height"],
                metrics["raw_bounds_width"],
                metrics["raw_bounds_height"],
            )
        except Exception as exc:
            logger.warning("%s: failed to log shape metrics: %s", prefix, exc)

    def get_shape_bounds(self, shape) -> BoundingBox:
        """
        Get the axis-aligned bounding box of a shape in millimeters.
        Bounds are for placement extents, not for user-facing true size.
        """
        try:
            bounds = BoundingBox(
                left=self._corel_to_mm(shape.LeftX),
                bottom=self._corel_to_mm(shape.BottomY),
                right=self._corel_to_mm(shape.RightX),
                top=self._corel_to_mm(shape.TopY),
            )
        except Exception as exc:
            raise CorelDRAWError(
                f"Could not read bounds for shape '{getattr(shape, 'Name', 'Unnamed shape')}': {exc}"
            )

        if bounds.width <= 0 or bounds.height <= 0:
            self.log_shape_metrics(shape, "Invalid bounds")
            raise CorelDRAWError(
                f"Invalid bounds for shape '{getattr(shape, 'Name', 'Unnamed shape')}'."
            )

        return bounds

    def get_true_size(self, shape) -> Tuple[float, float]:
        """
        Get rotation-independent intrinsic size in millimeters.
        This is the correct source for user-facing size labels.
        """
        try:
            width = self._corel_to_mm(shape.SizeWidth)
            height = self._corel_to_mm(shape.SizeHeight)
        except Exception as exc:
            raise CorelDRAWError(
                f"Could not read true size for shape '{getattr(shape, 'Name', 'Unnamed shape')}': {exc}"
            )

        if width <= 0 or height <= 0:
            self.log_shape_metrics(shape, "Invalid true size")
            raise CorelDRAWError(
                f"Invalid true size for shape '{getattr(shape, 'Name', 'Unnamed shape')}'."
            )

        return (width, height)

    def resize_shape(self, shape, new_width: float, new_height: float,
                     keep_center: bool = True):
        """
        Resize a shape to exact dimensions in document units (mm).

        Uses SetSize() which operates on the shape's intrinsic axes — rotation
        is fully preserved. This is the ONLY correct resize method that ignores
        bounding-box inflation from rotation.

        Args:
            shape:       CorelDRAW COM shape object.
            new_width:   Target width in mm (document units).
            new_height:  Target height in mm (document units).
            keep_center: If True, the shape's visual center stays in place.
        """
        if keep_center:
            cx = shape.CenterX
            cy = shape.CenterY

        # SetSize works on the shape's own intrinsic axes — rotation-safe.
        shape.SetSize(self._mm_to_corel(new_width), self._mm_to_corel(new_height))

        if keep_center:
            dx = cx - shape.CenterX
            dy = cy - shape.CenterY
            if abs(dx) > 0.0001 or abs(dy) > 0.0001:
                shape.Move(dx, dy)

    def create_line(self, start: 'Point', end: 'Point'):
        """
        Create a straight line between two points on the active layer.

        Args:
            start: Start Point.
            end:   End Point.

        Returns:
            The created line shape, or None on failure.
        """
        try:
            doc = self.get_active_document()
            if not doc:
                return None
            layer = doc.ActiveLayer
            line = layer.CreateLineSegment(
                self._mm_to_corel(start.x),
                self._mm_to_corel(start.y),
                self._mm_to_corel(end.x),
                self._mm_to_corel(end.y),
            )
            return line
        except Exception as e:
            logger.error(f"create_line failed: {e}")
            return None

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
            new_shape.Move(self._mm_to_corel(offset_x), self._mm_to_corel(offset_y))
        return new_shape

    def move_shape_by(self, shape, delta_x: float, delta_y: float):
        """Move a shape by a relative offset in millimeters."""
        if delta_x != 0 or delta_y != 0:
            shape.Move(self._mm_to_corel(delta_x), self._mm_to_corel(delta_y))

    def move_shape(self, shape, x: float, y: float):
        """Move a shape to absolute coordinates."""
        shape.SetPosition(self._mm_to_corel(x), self._mm_to_corel(y))

    def center_shape_at_origin(self, shape):
        """Move a shape so its center is at (0, 0) in mm."""
        center = self.get_shape_center(shape)
        self.move_shape_by(shape, -center.x, -center.y)
        return shape

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
            shape.RotateEx(angle, self._mm_to_corel(center_x), self._mm_to_corel(center_y))
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

    def _curve_segment_from_com(self, seg) -> CurveSegment:
        """Convert a CorelDRAW COM segment into a CurveSegment in millimeters."""
        start_node = seg.StartNode
        end_node = seg.EndNode

        start_point = Point(
            self._corel_to_mm(start_node.PositionX),
            self._corel_to_mm(start_node.PositionY),
        )
        end_point = Point(
            self._corel_to_mm(end_node.PositionX),
            self._corel_to_mm(end_node.PositionY),
        )
        is_bezier = seg.Type == 2
        control1 = None
        control2 = None

        if is_bezier:
            try:
                control1 = Point(
                    self._corel_to_mm(start_node.PositionX + seg.StartingControlPointOffset[0]),
                    self._corel_to_mm(start_node.PositionY + seg.StartingControlPointOffset[1]),
                )
                control2 = Point(
                    self._corel_to_mm(end_node.PositionX + seg.EndingControlPointOffset[0]),
                    self._corel_to_mm(end_node.PositionY + seg.EndingControlPointOffset[1]),
                )
            except Exception:
                is_bezier = False

        return CurveSegment(
            start=start_point,
            end=end_point,
            control1=control1,
            control2=control2,
            is_bezier=is_bezier,
        )

    def get_curve_subpaths(self, shape, require_closed: bool = False) -> List[List[CurveSegment]]:
        """
        Extract curve data as separate subpaths in millimeters.

        Args:
            shape: CorelDRAW shape to extract.
            require_closed: When True, raises if any subpath is open.

        Returns:
            A list of subpaths, each containing CurveSegment objects.
        """
        subpaths: List[List[CurveSegment]] = []

        try:
            if not hasattr(shape, 'Curve') or shape.Curve is None:
                shape.ConvertToCurves()

            curve = shape.Curve
            if curve is None:
                logger.warning("Shape has no curve data.")
                return subpaths

            for subpath_idx in range(1, curve.SubPaths.Count + 1):
                subpath = curve.SubPaths.Item(subpath_idx)
                is_closed = bool(getattr(subpath, "Closed", False))
                if require_closed and not is_closed:
                    raise CorelDRAWError(
                        f"Shape '{getattr(shape, 'Name', 'Unnamed shape')}' contains an open contour."
                    )

                segments: List[CurveSegment] = []
                for seg_idx in range(1, subpath.Segments.Count + 1):
                    segments.append(self._curve_segment_from_com(subpath.Segments.Item(seg_idx)))

                if segments:
                    subpaths.append(segments)
        except Exception as exc:
            logger.error(f"Error extracting curve subpaths: {exc}")
            if require_closed:
                raise

        return subpaths

    def get_curve_path(self, shape) -> List[CurveSegment]:
        """
        Extract path data from a curve shape in millimeters.
        """
        segments: List[CurveSegment] = []
        for subpath in self.get_curve_subpaths(shape, require_closed=False):
            segments.extend(subpath)
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
            return shape.IsPointInside(self._mm_to_corel(point.x), self._mm_to_corel(point.y))
        except Exception:
            bounds = self.get_shape_bounds(shape)
            return bounds.contains_point(point)

    def get_shape_center(self, shape) -> Point:
        """Get the center point of a shape."""
        return Point(self._corel_to_mm(shape.CenterX), self._corel_to_mm(shape.CenterY))

    def create_ellipse(self, layer, center_x: float, center_y: float, radius_x: float, radius_y: float):
        """Create an ellipse on the supplied layer using mm coordinates."""
        return layer.CreateEllipse(
            self._mm_to_corel(center_x - radius_x),
            self._mm_to_corel(center_y - radius_y),
            self._mm_to_corel(center_x + radius_x),
            self._mm_to_corel(center_y + radius_y),
        )

    def set_shape_no_fill(self, shape):
        """Apply no-fill styling to a shape."""
        try:
            shape.Fill.Type = 0
        except Exception:
            pass

    def set_shape_fill_color(self, shape, color_rgb: Tuple[int, int, int]):
        """Apply fill color to a shape when supported by the shape type."""
        try:
            shape.Fill.UniformColor.RGBAssign(*color_rgb)
        except Exception:
            pass

    def set_shape_outline(self, shape, width_mm: float = None, color_rgb: Tuple[int, int, int] = None):
        """Apply outline width/color in one place using mm inputs where possible."""
        try:
            if width_mm is not None:
                shape.Outline.Width = self._mm_to_corel(width_mm)
        except Exception:
            pass

    def set_shape_no_outline(self, shape):
        """Best-effort removal of a shape outline."""
        try:
            shape.Outline.Width = 0
        except Exception:
            pass
        try:
            if hasattr(shape.Outline, "Type"):
                shape.Outline.Type = 0
        except Exception:
            pass
        try:
            if color_rgb is not None:
                shape.Outline.Color.RGBAssign(*color_rgb)
        except Exception:
            pass

    def create_circle_template(
        self,
        layer,
        diameter_mm: float,
        outline_width_mm: float = None,
        outline_rgb: Tuple[int, int, int] = None,
        no_fill: bool = True,
    ):
        """Create a centered circle template that can be duplicated cheaply."""
        radius = max(0.0, float(diameter_mm) / 2.0)
        shape = self.create_ellipse(layer, 0.0, 0.0, radius, radius)
        if no_fill:
            self.set_shape_no_fill(shape)
        if outline_width_mm is not None or outline_rgb is not None:
            self.set_shape_outline(shape, width_mm=outline_width_mm, color_rgb=outline_rgb)
        return shape

    def duplicate_centered_template(self, template_shape, x_mm: float, y_mm: float, rotation: float = 0.0):
        """
        Duplicate a template shape that is already centered at origin.
        Rotation is applied around the template center before translation.
        """
        shape = template_shape.Duplicate()
        if rotation:
            shape.Rotate(rotation)
        if x_mm != 0 or y_mm != 0:
            shape.Move(self._mm_to_corel(x_mm), self._mm_to_corel(y_mm))
        return shape

    def create_group(self, shapes) -> Any:
        """Create a group from multiple shapes."""
        self.ensure_document()
        return shapes.Group()

    def create_shape_range(self):
        """Create an empty shape range on the current application."""
        self.ensure_document()
        return self.app.CreateShapeRange()

    def try_set_shape_name(self, shape, name: str) -> None:
        """Best-effort shape naming without failing the operation."""
        try:
            shape.Name = name
        except Exception:
            pass

    def import_file(self, file_path: str, layer=None):
        """Import a file into the active document, preferring the provided layer."""
        self.ensure_document()
        target_layer = layer or self.active_layer
        for method_name in ("ImportEx", "Import"):
            method = getattr(target_layer, method_name, None)
            if not callable(method):
                continue
            try:
                imported = method(file_path)
                if hasattr(imported, "Finish") and callable(imported.Finish):
                    imported = imported.Finish()
                return imported
            except Exception as exc:
                logger.debug("Layer %s failed for %s: %s", method_name, file_path, exc)

        active_layer = getattr(self.active_document, "ActiveLayer", None)
        for method_name in ("ImportEx", "Import"):
            method = getattr(active_layer, method_name, None)
            if not callable(method):
                continue
            try:
                imported = method(file_path)
                if hasattr(imported, "Finish") and callable(imported.Finish):
                    imported = imported.Finish()
                return imported
            except Exception as exc:
                logger.debug("Active layer %s failed for %s: %s", method_name, file_path, exc)
        raise CorelDRAWError(f"Could not import file into CorelDRAW: {file_path}")

    def import_svg_to_layer(self, file_path: str, layer_name: str):
        """Import an SVG into the named layer and return the imported object or range."""
        layer = self.get_or_create_layer(layer_name)
        return self.import_file(file_path, layer=layer)

    def try_group_or_weld_by_color(self, imported_shape, weld: bool = False):
        """Best-effort grouping or welding for imported SVG output."""
        if imported_shape is None:
            return None
        try:
            if hasattr(imported_shape, "UngroupAllEx"):
                imported_shape = imported_shape.UngroupAllEx()
        except Exception:
            pass
        try:
            if hasattr(imported_shape, "Group"):
                grouped = imported_shape.Group()
            else:
                grouped = imported_shape
        except Exception:
            grouped = imported_shape

        if weld:
            try:
                if hasattr(grouped, "Shapes") and grouped.Shapes.Count > 1:
                    shape_range = self.app.CreateShapeRange()
                    for index in range(1, grouped.Shapes.Count + 1):
                        shape_range.Add(grouped.Shapes.Item(index))
                    return shape_range.Combine()
            except Exception as exc:
                logger.warning("Weld/combine failed: %s", exc)
        return grouped

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
        if not self.is_connected:
            return

        try:
            self._app.Refresh()
        except Exception as e:
            logger.warning(f"Failed to refresh CorelDRAW: {e}")
        try:
            active_window = getattr(self._app, "ActiveWindow", None)
            if active_window is not None:
                active_window.Refresh()
        except Exception as e:
            logger.debug(f"Active window refresh failed: {e}")
        try:
            refresh_ex = getattr(self._app, "RefreshEx", None)
            if callable(refresh_ex):
                refresh_ex()
        except Exception as e:
            logger.debug(f"Extended refresh failed: {e}")
        try:
            active_window = getattr(self._app, "ActiveWindow", None)
            if active_window is not None:
                try:
                    active_window.Refresh()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if pythoncom is not None:
                pythoncom.PumpWaitingMessages()
        except Exception:
            pass
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
                    return shape.IsPointInside(self._mm_to_corel(x), self._mm_to_corel(y))
            except Exception:
                pass
            doc = self.get_active_document()
            if doc:
                point = doc.ActiveLayer.CreateRectangle(
                    self._mm_to_corel(x),
                    self._mm_to_corel(y),
                    self._mm_to_corel(x + 0.1),
                    self._mm_to_corel(y + 0.1),
                )
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
