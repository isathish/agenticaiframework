"""
Enterprise Image Processor Module.

Provides image manipulation including resize, crop,
watermark, format conversion, and compression.

Example:
    # Create image processor
    images = create_image_processor()
    
    # Resize image
    result = await images.resize(image_bytes, width=800, height=600)
    
    # Add watermark
    result = await images.watermark(
        image_bytes,
        text="© 2024 Company",
        position="bottom-right",
    )
    
    # Create thumbnail
    result = await images.thumbnail(image_bytes, size=200)
    
    # Pipeline processing
    result = await (
        images.pipeline(image_bytes)
        .resize(800, 600)
        .crop(100, 100, 500, 400)
        .watermark("© Company")
        .compress(quality=80)
        .execute()
    )
"""

from __future__ import annotations

import asyncio
import base64
import functools
import io
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class ImageError(Exception):
    """Image processing error."""
    pass


class FormatError(ImageError):
    """Format error."""
    pass


class ProcessingError(ImageError):
    """Processing error."""
    pass


class ImageFormat(str, Enum):
    """Image formats."""
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"
    GIF = "gif"
    BMP = "bmp"
    TIFF = "tiff"
    ICO = "ico"
    AVIF = "avif"


class ResizeMode(str, Enum):
    """Resize modes."""
    FIT = "fit"          # Fit within bounds
    FILL = "fill"        # Fill bounds (may crop)
    STRETCH = "stretch"  # Stretch to exact size
    CONTAIN = "contain"  # Contain with padding
    COVER = "cover"      # Cover bounds


class Position(str, Enum):
    """Position for overlays."""
    CENTER = "center"
    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


class FlipDirection(str, Enum):
    """Flip directions."""
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    BOTH = "both"


@dataclass
class ImageInfo:
    """Image information."""
    width: int = 0
    height: int = 0
    format: ImageFormat = ImageFormat.JPEG
    mode: str = "RGB"  # RGB, RGBA, L, etc.
    size_bytes: int = 0
    has_alpha: bool = False
    is_animated: bool = False
    frame_count: int = 1
    exif: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResizeOptions:
    """Resize options."""
    width: Optional[int] = None
    height: Optional[int] = None
    mode: ResizeMode = ResizeMode.FIT
    upscale: bool = False
    filter: str = "lanczos"  # nearest, bilinear, bicubic, lanczos


@dataclass
class CropOptions:
    """Crop options."""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    # Alternative: aspect ratio crop
    aspect_ratio: Optional[str] = None  # "16:9", "4:3", "1:1"
    gravity: Position = Position.CENTER


@dataclass
class WatermarkOptions:
    """Watermark options."""
    text: Optional[str] = None
    image_path: Optional[str] = None
    image_data: Optional[bytes] = None
    position: Position = Position.BOTTOM_RIGHT
    opacity: float = 0.5
    font_size: int = 24
    font_color: str = "#FFFFFF"
    padding: int = 10
    rotation: int = 0


@dataclass
class CompressionOptions:
    """Compression options."""
    quality: int = 85
    optimize: bool = True
    progressive: bool = False
    strip_metadata: bool = False


@dataclass
class FilterOptions:
    """Image filter options."""
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    sharpness: float = 1.0
    blur: float = 0.0
    grayscale: bool = False
    sepia: bool = False
    invert: bool = False


@dataclass
class ProcessedImage:
    """Processed image result."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: bytes = b""
    format: ImageFormat = ImageFormat.JPEG
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    operations: List[str] = field(default_factory=list)
    processed_at: datetime = field(default_factory=datetime.utcnow)


# Image Backend
class ImageBackend(ABC):
    """Abstract image processing backend."""
    
    @abstractmethod
    async def get_info(self, data: bytes) -> ImageInfo:
        """Get image information."""
        pass
    
    @abstractmethod
    async def resize(
        self,
        data: bytes,
        options: ResizeOptions,
    ) -> bytes:
        """Resize image."""
        pass
    
    @abstractmethod
    async def crop(
        self,
        data: bytes,
        options: CropOptions,
    ) -> bytes:
        """Crop image."""
        pass
    
    @abstractmethod
    async def watermark(
        self,
        data: bytes,
        options: WatermarkOptions,
    ) -> bytes:
        """Add watermark."""
        pass
    
    @abstractmethod
    async def convert(
        self,
        data: bytes,
        target_format: ImageFormat,
        options: Optional[CompressionOptions] = None,
    ) -> bytes:
        """Convert format."""
        pass
    
    @abstractmethod
    async def apply_filters(
        self,
        data: bytes,
        options: FilterOptions,
    ) -> bytes:
        """Apply filters."""
        pass


class MockImageBackend(ImageBackend):
    """Mock image backend for testing."""
    
    async def get_info(self, data: bytes) -> ImageInfo:
        """Get mock image info."""
        return ImageInfo(
            width=800,
            height=600,
            format=ImageFormat.JPEG,
            mode="RGB",
            size_bytes=len(data),
        )
    
    async def resize(
        self,
        data: bytes,
        options: ResizeOptions,
    ) -> bytes:
        """Mock resize."""
        info = {
            "operation": "resize",
            "width": options.width,
            "height": options.height,
            "mode": options.mode.value,
            "original_size": len(data),
        }
        return json.dumps(info).encode()
    
    async def crop(
        self,
        data: bytes,
        options: CropOptions,
    ) -> bytes:
        """Mock crop."""
        info = {
            "operation": "crop",
            "x": options.x,
            "y": options.y,
            "width": options.width,
            "height": options.height,
        }
        return json.dumps(info).encode()
    
    async def watermark(
        self,
        data: bytes,
        options: WatermarkOptions,
    ) -> bytes:
        """Mock watermark."""
        info = {
            "operation": "watermark",
            "text": options.text,
            "position": options.position.value,
            "opacity": options.opacity,
        }
        return json.dumps(info).encode()
    
    async def convert(
        self,
        data: bytes,
        target_format: ImageFormat,
        options: Optional[CompressionOptions] = None,
    ) -> bytes:
        """Mock convert."""
        info = {
            "operation": "convert",
            "target_format": target_format.value,
            "quality": options.quality if options else 85,
        }
        return json.dumps(info).encode()
    
    async def apply_filters(
        self,
        data: bytes,
        options: FilterOptions,
    ) -> bytes:
        """Mock apply filters."""
        info = {
            "operation": "filter",
            "brightness": options.brightness,
            "contrast": options.contrast,
            "grayscale": options.grayscale,
        }
        return json.dumps(info).encode()


class ImagePipeline:
    """Fluent image processing pipeline."""
    
    def __init__(
        self,
        processor: "ImageProcessor",
        data: bytes,
    ):
        self._processor = processor
        self._data = data
        self._operations: List[Tuple[str, Any]] = []
    
    def resize(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        mode: ResizeMode = ResizeMode.FIT,
    ) -> "ImagePipeline":
        """Add resize operation."""
        self._operations.append((
            "resize",
            ResizeOptions(width=width, height=height, mode=mode),
        ))
        return self
    
    def crop(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> "ImagePipeline":
        """Add crop operation."""
        self._operations.append((
            "crop",
            CropOptions(x=x, y=y, width=width, height=height),
        ))
        return self
    
    def watermark(
        self,
        text: str,
        position: Position = Position.BOTTOM_RIGHT,
        opacity: float = 0.5,
    ) -> "ImagePipeline":
        """Add watermark operation."""
        self._operations.append((
            "watermark",
            WatermarkOptions(text=text, position=position, opacity=opacity),
        ))
        return self
    
    def convert(
        self,
        format: ImageFormat,
    ) -> "ImagePipeline":
        """Add format conversion."""
        self._operations.append(("convert", format))
        return self
    
    def compress(
        self,
        quality: int = 85,
    ) -> "ImagePipeline":
        """Add compression."""
        self._operations.append((
            "compress",
            CompressionOptions(quality=quality),
        ))
        return self
    
    def filter(
        self,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        grayscale: bool = False,
    ) -> "ImagePipeline":
        """Add filter operation."""
        self._operations.append((
            "filter",
            FilterOptions(
                brightness=brightness,
                contrast=contrast,
                saturation=saturation,
                grayscale=grayscale,
            ),
        ))
        return self
    
    def rotate(self, degrees: int) -> "ImagePipeline":
        """Add rotation."""
        self._operations.append(("rotate", degrees))
        return self
    
    def flip(self, direction: FlipDirection) -> "ImagePipeline":
        """Add flip operation."""
        self._operations.append(("flip", direction))
        return self
    
    async def execute(self) -> ProcessedImage:
        """Execute pipeline."""
        data = self._data
        operations = []
        
        for op_name, op_args in self._operations:
            if op_name == "resize":
                data = await self._processor.backend.resize(data, op_args)
            elif op_name == "crop":
                data = await self._processor.backend.crop(data, op_args)
            elif op_name == "watermark":
                data = await self._processor.backend.watermark(data, op_args)
            elif op_name == "convert":
                data = await self._processor.backend.convert(data, op_args)
            elif op_name == "compress":
                data = await self._processor.backend.convert(
                    data, ImageFormat.JPEG, op_args
                )
            elif op_name == "filter":
                data = await self._processor.backend.apply_filters(data, op_args)
            
            operations.append(op_name)
        
        return ProcessedImage(
            content=data,
            size_bytes=len(data),
            operations=operations,
        )


class ImageProcessor:
    """
    Image processing service.
    """
    
    def __init__(
        self,
        backend: Optional[ImageBackend] = None,
    ):
        self._backend = backend or MockImageBackend()
    
    @property
    def backend(self) -> ImageBackend:
        """Get backend."""
        return self._backend
    
    def pipeline(self, data: bytes) -> ImagePipeline:
        """Create processing pipeline."""
        return ImagePipeline(self, data)
    
    async def get_info(self, data: bytes) -> ImageInfo:
        """Get image information."""
        return await self._backend.get_info(data)
    
    async def resize(
        self,
        data: bytes,
        width: Optional[int] = None,
        height: Optional[int] = None,
        mode: ResizeMode = ResizeMode.FIT,
        **kwargs,
    ) -> ProcessedImage:
        """
        Resize image.
        
        Args:
            data: Image bytes
            width: Target width
            height: Target height
            mode: Resize mode
            
        Returns:
            Processed image
        """
        options = ResizeOptions(
            width=width,
            height=height,
            mode=mode,
            **kwargs,
        )
        
        content = await self._backend.resize(data, options)
        
        return ProcessedImage(
            content=content,
            width=width or 0,
            height=height or 0,
            size_bytes=len(content),
            operations=["resize"],
        )
    
    async def thumbnail(
        self,
        data: bytes,
        size: int = 150,
        mode: ResizeMode = ResizeMode.FIT,
    ) -> ProcessedImage:
        """Create thumbnail."""
        return await self.resize(data, width=size, height=size, mode=mode)
    
    async def crop(
        self,
        data: bytes,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> ProcessedImage:
        """
        Crop image.
        
        Args:
            data: Image bytes
            x: Left position
            y: Top position
            width: Crop width
            height: Crop height
            
        Returns:
            Processed image
        """
        options = CropOptions(x=x, y=y, width=width, height=height)
        content = await self._backend.crop(data, options)
        
        return ProcessedImage(
            content=content,
            width=width,
            height=height,
            size_bytes=len(content),
            operations=["crop"],
        )
    
    async def crop_aspect(
        self,
        data: bytes,
        aspect_ratio: str = "1:1",
        gravity: Position = Position.CENTER,
    ) -> ProcessedImage:
        """Crop to aspect ratio."""
        options = CropOptions(aspect_ratio=aspect_ratio, gravity=gravity)
        content = await self._backend.crop(data, options)
        
        return ProcessedImage(
            content=content,
            size_bytes=len(content),
            operations=["crop_aspect"],
        )
    
    async def watermark(
        self,
        data: bytes,
        text: Optional[str] = None,
        image_path: Optional[str] = None,
        image_data: Optional[bytes] = None,
        position: Position = Position.BOTTOM_RIGHT,
        opacity: float = 0.5,
        **kwargs,
    ) -> ProcessedImage:
        """
        Add watermark.
        
        Args:
            data: Image bytes
            text: Watermark text
            image_path: Watermark image path
            image_data: Watermark image bytes
            position: Watermark position
            opacity: Watermark opacity
            
        Returns:
            Processed image
        """
        options = WatermarkOptions(
            text=text,
            image_path=image_path,
            image_data=image_data,
            position=position,
            opacity=opacity,
            **kwargs,
        )
        
        content = await self._backend.watermark(data, options)
        
        return ProcessedImage(
            content=content,
            size_bytes=len(content),
            operations=["watermark"],
        )
    
    async def convert(
        self,
        data: bytes,
        target_format: ImageFormat,
        quality: int = 85,
    ) -> ProcessedImage:
        """
        Convert image format.
        
        Args:
            data: Image bytes
            target_format: Target format
            quality: Compression quality
            
        Returns:
            Processed image
        """
        options = CompressionOptions(quality=quality)
        content = await self._backend.convert(data, target_format, options)
        
        return ProcessedImage(
            content=content,
            format=target_format,
            size_bytes=len(content),
            operations=["convert"],
        )
    
    async def compress(
        self,
        data: bytes,
        quality: int = 85,
        format: Optional[ImageFormat] = None,
    ) -> ProcessedImage:
        """
        Compress image.
        
        Args:
            data: Image bytes
            quality: Compression quality (1-100)
            format: Target format
            
        Returns:
            Processed image
        """
        target = format or ImageFormat.JPEG
        options = CompressionOptions(quality=quality, optimize=True)
        content = await self._backend.convert(data, target, options)
        
        return ProcessedImage(
            content=content,
            format=target,
            size_bytes=len(content),
            operations=["compress"],
        )
    
    async def apply_filter(
        self,
        data: bytes,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        grayscale: bool = False,
        **kwargs,
    ) -> ProcessedImage:
        """
        Apply filters.
        
        Args:
            data: Image bytes
            brightness: Brightness adjustment
            contrast: Contrast adjustment
            saturation: Saturation adjustment
            grayscale: Convert to grayscale
            
        Returns:
            Processed image
        """
        options = FilterOptions(
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            grayscale=grayscale,
            **kwargs,
        )
        
        content = await self._backend.apply_filters(data, options)
        
        return ProcessedImage(
            content=content,
            size_bytes=len(content),
            operations=["filter"],
        )
    
    async def optimize(
        self,
        data: bytes,
        max_width: int = 1920,
        max_height: int = 1080,
        quality: int = 80,
        format: ImageFormat = ImageFormat.WEBP,
    ) -> ProcessedImage:
        """
        Optimize image for web.
        
        Args:
            data: Image bytes
            max_width: Maximum width
            max_height: Maximum height
            quality: Compression quality
            format: Target format (WEBP recommended)
            
        Returns:
            Optimized image
        """
        # Get info
        info = await self.get_info(data)
        
        result = data
        operations = []
        
        # Resize if needed
        if info.width > max_width or info.height > max_height:
            resize_result = await self.resize(
                result,
                width=max_width,
                height=max_height,
                mode=ResizeMode.FIT,
            )
            result = resize_result.content
            operations.append("resize")
        
        # Convert and compress
        convert_result = await self.convert(result, format, quality)
        result = convert_result.content
        operations.append("convert")
        
        return ProcessedImage(
            content=result,
            format=format,
            size_bytes=len(result),
            operations=operations,
        )
    
    async def save(
        self,
        image: ProcessedImage,
        path: Union[str, Path],
    ) -> Path:
        """Save processed image."""
        path = Path(path)
        path.write_bytes(image.content)
        return path
    
    def to_base64(self, image: ProcessedImage) -> str:
        """Convert to base64."""
        return base64.b64encode(image.content).decode()
    
    def to_data_uri(self, image: ProcessedImage) -> str:
        """Convert to data URI."""
        b64 = self.to_base64(image)
        mime = f"image/{image.format.value}"
        return f"data:{mime};base64,{b64}"


# Decorators
def image_response(
    format: ImageFormat = ImageFormat.JPEG,
) -> Callable:
    """Decorator for image response."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, ProcessedImage):
                return {
                    "content": result.content,
                    "content_type": f"image/{result.format.value}",
                }
            
            return result
        
        return wrapper
    return decorator


# Factory functions
def create_image_processor(
    backend: Optional[ImageBackend] = None,
) -> ImageProcessor:
    """Create image processor."""
    return ImageProcessor(backend)


def create_resize_options(
    width: Optional[int] = None,
    height: Optional[int] = None,
    mode: ResizeMode = ResizeMode.FIT,
    **kwargs,
) -> ResizeOptions:
    """Create resize options."""
    return ResizeOptions(width=width, height=height, mode=mode, **kwargs)


def create_watermark_options(
    text: Optional[str] = None,
    position: Position = Position.BOTTOM_RIGHT,
    opacity: float = 0.5,
    **kwargs,
) -> WatermarkOptions:
    """Create watermark options."""
    return WatermarkOptions(
        text=text,
        position=position,
        opacity=opacity,
        **kwargs,
    )


def create_filter_options(
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    **kwargs,
) -> FilterOptions:
    """Create filter options."""
    return FilterOptions(
        brightness=brightness,
        contrast=contrast,
        saturation=saturation,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "ImageError",
    "FormatError",
    "ProcessingError",
    # Enums
    "ImageFormat",
    "ResizeMode",
    "Position",
    "FlipDirection",
    # Data classes
    "ImageInfo",
    "ResizeOptions",
    "CropOptions",
    "WatermarkOptions",
    "CompressionOptions",
    "FilterOptions",
    "ProcessedImage",
    # Backend
    "ImageBackend",
    "MockImageBackend",
    # Pipeline
    "ImagePipeline",
    # Processor
    "ImageProcessor",
    # Decorators
    "image_response",
    # Factory functions
    "create_image_processor",
    "create_resize_options",
    "create_watermark_options",
    "create_filter_options",
]
