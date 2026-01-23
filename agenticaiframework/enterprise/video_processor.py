"""
Enterprise Video Processor Module.

Provides video manipulation including transcoding,
thumbnails, streaming, and metadata extraction.

Example:
    # Create video processor
    videos = create_video_processor()
    
    # Get video info
    info = await videos.get_info(video_bytes)
    
    # Transcode video
    result = await videos.transcode(
        video_bytes,
        output_format=VideoFormat.MP4,
        resolution=Resolution.HD_720,
    )
    
    # Generate thumbnails
    thumbnails = await videos.thumbnails(video_bytes, count=5)
    
    # Extract audio
    audio = await videos.extract_audio(video_bytes, format=AudioFormat.MP3)
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
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
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


class VideoError(Exception):
    """Video processing error."""
    pass


class TranscodeError(VideoError):
    """Transcoding error."""
    pass


class FormatError(VideoError):
    """Format error."""
    pass


class VideoFormat(str, Enum):
    """Video formats."""
    MP4 = "mp4"
    WEBM = "webm"
    AVI = "avi"
    MKV = "mkv"
    MOV = "mov"
    FLV = "flv"
    WMV = "wmv"
    OGV = "ogv"
    M3U8 = "m3u8"  # HLS


class AudioFormat(str, Enum):
    """Audio formats."""
    MP3 = "mp3"
    AAC = "aac"
    WAV = "wav"
    OGG = "ogg"
    FLAC = "flac"
    M4A = "m4a"


class VideoCodec(str, Enum):
    """Video codecs."""
    H264 = "h264"
    H265 = "h265"
    VP8 = "vp8"
    VP9 = "vp9"
    AV1 = "av1"
    MPEG4 = "mpeg4"
    HEVC = "hevc"


class AudioCodec(str, Enum):
    """Audio codecs."""
    AAC = "aac"
    MP3 = "mp3"
    VORBIS = "vorbis"
    OPUS = "opus"
    FLAC = "flac"
    PCM = "pcm"


class Resolution(str, Enum):
    """Common resolutions."""
    SD_480 = "480p"
    HD_720 = "720p"
    HD_1080 = "1080p"
    UHD_4K = "2160p"
    ORIGINAL = "original"


class Preset(str, Enum):
    """Encoding presets."""
    ULTRAFAST = "ultrafast"
    SUPERFAST = "superfast"
    VERYFAST = "veryfast"
    FASTER = "faster"
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    SLOWER = "slower"
    VERYSLOW = "veryslow"


# Resolution mapping
RESOLUTION_MAP = {
    Resolution.SD_480: (854, 480),
    Resolution.HD_720: (1280, 720),
    Resolution.HD_1080: (1920, 1080),
    Resolution.UHD_4K: (3840, 2160),
}


@dataclass
class VideoInfo:
    """Video information."""
    width: int = 0
    height: int = 0
    duration: float = 0.0  # seconds
    fps: float = 0.0
    bitrate: int = 0
    format: VideoFormat = VideoFormat.MP4
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    audio_channels: int = 2
    audio_sample_rate: int = 44100
    size_bytes: int = 0
    has_audio: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscodeOptions:
    """Transcoding options."""
    format: VideoFormat = VideoFormat.MP4
    video_codec: VideoCodec = VideoCodec.H264
    audio_codec: AudioCodec = AudioCodec.AAC
    resolution: Resolution = Resolution.ORIGINAL
    width: Optional[int] = None
    height: Optional[int] = None
    bitrate: Optional[int] = None  # kbps
    fps: Optional[float] = None
    preset: Preset = Preset.MEDIUM
    crf: int = 23  # Quality (0-51, lower is better)
    audio_bitrate: int = 128  # kbps
    two_pass: bool = False
    strip_audio: bool = False


@dataclass
class ThumbnailOptions:
    """Thumbnail options."""
    count: int = 1
    width: int = 320
    height: int = 180
    format: str = "jpeg"
    timestamps: Optional[List[float]] = None  # Specific timestamps
    sprite: bool = False  # Create sprite sheet
    sprite_columns: int = 5


@dataclass
class WatermarkOptions:
    """Video watermark options."""
    text: Optional[str] = None
    image_path: Optional[str] = None
    position: str = "bottom-right"  # top-left, top-right, bottom-left, bottom-right, center
    opacity: float = 0.5
    scale: float = 0.2
    padding: int = 10


@dataclass
class TrimOptions:
    """Video trim options."""
    start: float = 0.0  # seconds
    end: Optional[float] = None  # seconds
    duration: Optional[float] = None  # seconds


@dataclass
class ConcatOptions:
    """Concatenation options."""
    transition: Optional[str] = None  # fade, dissolve, wipe
    transition_duration: float = 0.5


@dataclass
class ProcessedVideo:
    """Processed video result."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: bytes = b""
    format: VideoFormat = VideoFormat.MP4
    width: int = 0
    height: int = 0
    duration: float = 0.0
    size_bytes: int = 0
    operations: List[str] = field(default_factory=list)
    processed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Thumbnail:
    """Generated thumbnail."""
    content: bytes = b""
    timestamp: float = 0.0
    width: int = 0
    height: int = 0
    format: str = "jpeg"


@dataclass
class StreamingOptions:
    """Streaming options."""
    format: str = "hls"  # hls, dash
    segment_duration: int = 10  # seconds
    playlist_type: str = "vod"  # vod, live, event
    resolutions: List[Resolution] = field(default_factory=lambda: [
        Resolution.SD_480,
        Resolution.HD_720,
        Resolution.HD_1080,
    ])


@dataclass
class StreamingManifest:
    """Streaming manifest."""
    master_playlist: str = ""
    variant_playlists: Dict[str, str] = field(default_factory=dict)
    segments: Dict[str, List[str]] = field(default_factory=dict)


# Video Backend
class VideoBackend(ABC):
    """Abstract video processing backend."""
    
    @abstractmethod
    async def get_info(self, data: bytes) -> VideoInfo:
        """Get video information."""
        pass
    
    @abstractmethod
    async def transcode(
        self,
        data: bytes,
        options: TranscodeOptions,
    ) -> bytes:
        """Transcode video."""
        pass
    
    @abstractmethod
    async def generate_thumbnails(
        self,
        data: bytes,
        options: ThumbnailOptions,
    ) -> List[Thumbnail]:
        """Generate thumbnails."""
        pass
    
    @abstractmethod
    async def extract_audio(
        self,
        data: bytes,
        format: AudioFormat,
        bitrate: int,
    ) -> bytes:
        """Extract audio from video."""
        pass
    
    @abstractmethod
    async def trim(
        self,
        data: bytes,
        options: TrimOptions,
    ) -> bytes:
        """Trim video."""
        pass
    
    @abstractmethod
    async def concat(
        self,
        videos: List[bytes],
        options: ConcatOptions,
    ) -> bytes:
        """Concatenate videos."""
        pass


class MockVideoBackend(VideoBackend):
    """Mock video backend for testing."""
    
    async def get_info(self, data: bytes) -> VideoInfo:
        """Get mock video info."""
        return VideoInfo(
            width=1920,
            height=1080,
            duration=120.0,
            fps=30.0,
            bitrate=5000000,
            format=VideoFormat.MP4,
            video_codec="h264",
            audio_codec="aac",
            size_bytes=len(data),
        )
    
    async def transcode(
        self,
        data: bytes,
        options: TranscodeOptions,
    ) -> bytes:
        """Mock transcode."""
        info = {
            "operation": "transcode",
            "format": options.format.value,
            "video_codec": options.video_codec.value,
            "resolution": options.resolution.value,
            "preset": options.preset.value,
        }
        return json.dumps(info).encode()
    
    async def generate_thumbnails(
        self,
        data: bytes,
        options: ThumbnailOptions,
    ) -> List[Thumbnail]:
        """Generate mock thumbnails."""
        thumbnails = []
        for i in range(options.count):
            thumbnails.append(Thumbnail(
                content=b"mock_thumbnail",
                timestamp=float(i * 10),
                width=options.width,
                height=options.height,
                format=options.format,
            ))
        return thumbnails
    
    async def extract_audio(
        self,
        data: bytes,
        format: AudioFormat,
        bitrate: int,
    ) -> bytes:
        """Mock extract audio."""
        info = {
            "operation": "extract_audio",
            "format": format.value,
            "bitrate": bitrate,
        }
        return json.dumps(info).encode()
    
    async def trim(
        self,
        data: bytes,
        options: TrimOptions,
    ) -> bytes:
        """Mock trim."""
        info = {
            "operation": "trim",
            "start": options.start,
            "end": options.end,
            "duration": options.duration,
        }
        return json.dumps(info).encode()
    
    async def concat(
        self,
        videos: List[bytes],
        options: ConcatOptions,
    ) -> bytes:
        """Mock concat."""
        info = {
            "operation": "concat",
            "video_count": len(videos),
            "transition": options.transition,
        }
        return json.dumps(info).encode()


class VideoProcessor:
    """
    Video processing service.
    """
    
    def __init__(
        self,
        backend: Optional[VideoBackend] = None,
    ):
        self._backend = backend or MockVideoBackend()
    
    async def get_info(self, data: bytes) -> VideoInfo:
        """Get video information."""
        return await self._backend.get_info(data)
    
    async def transcode(
        self,
        data: bytes,
        format: VideoFormat = VideoFormat.MP4,
        video_codec: VideoCodec = VideoCodec.H264,
        audio_codec: AudioCodec = AudioCodec.AAC,
        resolution: Resolution = Resolution.ORIGINAL,
        **kwargs,
    ) -> ProcessedVideo:
        """
        Transcode video.
        
        Args:
            data: Video bytes
            format: Output format
            video_codec: Video codec
            audio_codec: Audio codec
            resolution: Output resolution
            
        Returns:
            Processed video
        """
        options = TranscodeOptions(
            format=format,
            video_codec=video_codec,
            audio_codec=audio_codec,
            resolution=resolution,
            **kwargs,
        )
        
        # Get dimensions
        if resolution != Resolution.ORIGINAL and resolution in RESOLUTION_MAP:
            width, height = RESOLUTION_MAP[resolution]
        else:
            width, height = 0, 0
        
        content = await self._backend.transcode(data, options)
        
        return ProcessedVideo(
            content=content,
            format=format,
            width=width,
            height=height,
            size_bytes=len(content),
            operations=["transcode"],
        )
    
    async def compress(
        self,
        data: bytes,
        target_bitrate: int = 2000,  # kbps
        crf: int = 28,
    ) -> ProcessedVideo:
        """Compress video."""
        return await self.transcode(
            data,
            bitrate=target_bitrate,
            crf=crf,
            preset=Preset.SLOW,
        )
    
    async def to_web(
        self,
        data: bytes,
        format: VideoFormat = VideoFormat.WEBM,
        resolution: Resolution = Resolution.HD_720,
    ) -> ProcessedVideo:
        """Convert video for web."""
        if format == VideoFormat.WEBM:
            return await self.transcode(
                data,
                format=format,
                video_codec=VideoCodec.VP9,
                audio_codec=AudioCodec.OPUS,
                resolution=resolution,
            )
        else:
            return await self.transcode(
                data,
                format=format,
                resolution=resolution,
            )
    
    async def thumbnails(
        self,
        data: bytes,
        count: int = 1,
        width: int = 320,
        height: int = 180,
        format: str = "jpeg",
        timestamps: Optional[List[float]] = None,
    ) -> List[Thumbnail]:
        """
        Generate thumbnails.
        
        Args:
            data: Video bytes
            count: Number of thumbnails
            width: Thumbnail width
            height: Thumbnail height
            format: Image format
            timestamps: Specific timestamps
            
        Returns:
            List of thumbnails
        """
        options = ThumbnailOptions(
            count=count,
            width=width,
            height=height,
            format=format,
            timestamps=timestamps,
        )
        
        return await self._backend.generate_thumbnails(data, options)
    
    async def thumbnail(
        self,
        data: bytes,
        timestamp: Optional[float] = None,
        width: int = 320,
        height: int = 180,
    ) -> Thumbnail:
        """Generate single thumbnail."""
        timestamps = [timestamp] if timestamp is not None else None
        
        thumbnails = await self.thumbnails(
            data,
            count=1,
            width=width,
            height=height,
            timestamps=timestamps,
        )
        
        return thumbnails[0] if thumbnails else Thumbnail()
    
    async def sprite_sheet(
        self,
        data: bytes,
        count: int = 25,
        columns: int = 5,
        thumbnail_width: int = 160,
        thumbnail_height: int = 90,
    ) -> Thumbnail:
        """Generate thumbnail sprite sheet."""
        options = ThumbnailOptions(
            count=count,
            width=thumbnail_width,
            height=thumbnail_height,
            sprite=True,
            sprite_columns=columns,
        )
        
        thumbnails = await self._backend.generate_thumbnails(data, options)
        
        # Return sprite sheet (first item)
        return thumbnails[0] if thumbnails else Thumbnail()
    
    async def extract_audio(
        self,
        data: bytes,
        format: AudioFormat = AudioFormat.MP3,
        bitrate: int = 192,
    ) -> bytes:
        """
        Extract audio from video.
        
        Args:
            data: Video bytes
            format: Audio format
            bitrate: Audio bitrate (kbps)
            
        Returns:
            Audio bytes
        """
        return await self._backend.extract_audio(data, format, bitrate)
    
    async def trim(
        self,
        data: bytes,
        start: float = 0.0,
        end: Optional[float] = None,
        duration: Optional[float] = None,
    ) -> ProcessedVideo:
        """
        Trim video.
        
        Args:
            data: Video bytes
            start: Start time (seconds)
            end: End time (seconds)
            duration: Duration (seconds)
            
        Returns:
            Trimmed video
        """
        options = TrimOptions(
            start=start,
            end=end,
            duration=duration,
        )
        
        content = await self._backend.trim(data, options)
        
        return ProcessedVideo(
            content=content,
            size_bytes=len(content),
            operations=["trim"],
        )
    
    async def concat(
        self,
        videos: List[bytes],
        transition: Optional[str] = None,
        transition_duration: float = 0.5,
    ) -> ProcessedVideo:
        """
        Concatenate videos.
        
        Args:
            videos: List of video bytes
            transition: Transition effect
            transition_duration: Transition duration
            
        Returns:
            Concatenated video
        """
        options = ConcatOptions(
            transition=transition,
            transition_duration=transition_duration,
        )
        
        content = await self._backend.concat(videos, options)
        
        return ProcessedVideo(
            content=content,
            size_bytes=len(content),
            operations=["concat"],
        )
    
    async def generate_hls(
        self,
        data: bytes,
        segment_duration: int = 10,
        resolutions: Optional[List[Resolution]] = None,
    ) -> StreamingManifest:
        """
        Generate HLS streaming manifest.
        
        Args:
            data: Video bytes
            segment_duration: Segment duration
            resolutions: Output resolutions
            
        Returns:
            Streaming manifest
        """
        resolutions = resolutions or [
            Resolution.SD_480,
            Resolution.HD_720,
            Resolution.HD_1080,
        ]
        
        # Generate mock manifest
        manifest = StreamingManifest()
        
        lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
        
        for resolution in resolutions:
            if resolution in RESOLUTION_MAP:
                width, height = RESOLUTION_MAP[resolution]
                bandwidth = {
                    Resolution.SD_480: 1500000,
                    Resolution.HD_720: 4000000,
                    Resolution.HD_1080: 7000000,
                }.get(resolution, 2000000)
                
                lines.append(
                    f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={width}x{height}'
                )
                lines.append(f"{resolution.value}/playlist.m3u8")
        
        manifest.master_playlist = "\n".join(lines)
        
        return manifest
    
    async def save(
        self,
        video: ProcessedVideo,
        path: Union[str, Path],
    ) -> Path:
        """Save processed video."""
        path = Path(path)
        path.write_bytes(video.content)
        return path


# Decorators
def video_response(
    format: VideoFormat = VideoFormat.MP4,
) -> Callable:
    """Decorator for video response."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, ProcessedVideo):
                return {
                    "content": result.content,
                    "content_type": f"video/{result.format.value}",
                }
            
            return result
        
        return wrapper
    return decorator


# Factory functions
def create_video_processor(
    backend: Optional[VideoBackend] = None,
) -> VideoProcessor:
    """Create video processor."""
    return VideoProcessor(backend)


def create_transcode_options(
    format: VideoFormat = VideoFormat.MP4,
    resolution: Resolution = Resolution.ORIGINAL,
    **kwargs,
) -> TranscodeOptions:
    """Create transcode options."""
    return TranscodeOptions(format=format, resolution=resolution, **kwargs)


def create_thumbnail_options(
    count: int = 1,
    width: int = 320,
    height: int = 180,
    **kwargs,
) -> ThumbnailOptions:
    """Create thumbnail options."""
    return ThumbnailOptions(count=count, width=width, height=height, **kwargs)


def create_trim_options(
    start: float = 0.0,
    end: Optional[float] = None,
    duration: Optional[float] = None,
) -> TrimOptions:
    """Create trim options."""
    return TrimOptions(start=start, end=end, duration=duration)


__all__ = [
    # Exceptions
    "VideoError",
    "TranscodeError",
    "FormatError",
    # Enums
    "VideoFormat",
    "AudioFormat",
    "VideoCodec",
    "AudioCodec",
    "Resolution",
    "Preset",
    # Data classes
    "VideoInfo",
    "TranscodeOptions",
    "ThumbnailOptions",
    "WatermarkOptions",
    "TrimOptions",
    "ConcatOptions",
    "ProcessedVideo",
    "Thumbnail",
    "StreamingOptions",
    "StreamingManifest",
    # Backend
    "VideoBackend",
    "MockVideoBackend",
    # Processor
    "VideoProcessor",
    # Decorators
    "video_response",
    # Factory functions
    "create_video_processor",
    "create_transcode_options",
    "create_thumbnail_options",
    "create_trim_options",
]
