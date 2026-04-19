"""Shared stone-processing helpers for drawing tools."""

from .background_mask import BackgroundMaskBuilder, BackgroundMaskSettings
from .cache_manager import CacheManager
from .color_quantizer import ColorQuantizer
from .decimation import DecimationSettings, StoneDecimator
from .exporter import StoneExporter
from .final_renderer import FinalRenderer
from .image_sampler import ImageSampler
from .preview_renderer import PointillizerPreviewCanvas, PreviewRenderer, PreviewScene
from .progress_controller import OperationCancelled, OperationWorker, ProgressController, ProgressSnapshot
from .size_assignment import SizeAssignmentSettings, StoneSizeAssigner
from .stone_layout import generate_candidate_points
from .structural_detail_extractor import (
    StructuralDetailConfig,
    StructuralDetailExtractor,
    StructuralDetailResult,
    StructuralPath,
)
from .tool_controller import ToolController

__all__ = [
    "BackgroundMaskBuilder",
    "BackgroundMaskSettings",
    "CacheManager",
    "ColorQuantizer",
    "DecimationSettings",
    "FinalRenderer",
    "ImageSampler",
    "OperationCancelled",
    "OperationWorker",
    "PointillizerPreviewCanvas",
    "PreviewRenderer",
    "PreviewScene",
    "ProgressController",
    "ProgressSnapshot",
    "SizeAssignmentSettings",
    "StoneDecimator",
    "StoneExporter",
    "StoneSizeAssigner",
    "StructuralDetailConfig",
    "StructuralDetailExtractor",
    "StructuralDetailResult",
    "StructuralPath",
    "ToolController",
    "generate_candidate_points",
]
