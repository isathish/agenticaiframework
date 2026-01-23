"""
Enterprise Audio Processor Module.

Provides audio manipulation including transcoding,
waveform generation, and speech integration.

Example:
    # Create audio processor
    audio = create_audio_processor()
    
    # Get audio info
    info = await audio.get_info(audio_bytes)
    
    # Transcode audio
    result = await audio.transcode(
        audio_bytes,
        format=AudioFormat.MP3,
        bitrate=192,
    )
    
    # Generate waveform
    waveform = await audio.waveform(audio_bytes, width=800, height=200)
    
    # Merge audio files
    merged = await audio.merge([audio1, audio2, audio3])
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


class AudioError(Exception):
    """Audio processing error."""
    pass


class TranscodeError(AudioError):
    """Transcoding error."""
    pass


class FormatError(AudioError):
    """Format error."""
    pass


class AudioFormat(str, Enum):
    """Audio formats."""
    MP3 = "mp3"
    WAV = "wav"
    AAC = "aac"
    OGG = "ogg"
    FLAC = "flac"
    M4A = "m4a"
    WMA = "wma"
    AIFF = "aiff"
    OPUS = "opus"
    WEBM = "webm"


class AudioCodec(str, Enum):
    """Audio codecs."""
    MP3 = "libmp3lame"
    AAC = "aac"
    VORBIS = "libvorbis"
    OPUS = "libopus"
    FLAC = "flac"
    PCM = "pcm_s16le"
    ALAC = "alac"


class SampleRate(int, Enum):
    """Common sample rates."""
    RATE_8000 = 8000    # Phone quality
    RATE_16000 = 16000  # Wideband
    RATE_22050 = 22050  # Low quality music
    RATE_44100 = 44100  # CD quality
    RATE_48000 = 48000  # Professional
    RATE_96000 = 96000  # High-res
    RATE_192000 = 192000  # Studio


class BitDepth(int, Enum):
    """Bit depths."""
    BIT_8 = 8
    BIT_16 = 16
    BIT_24 = 24
    BIT_32 = 32


class ChannelLayout(str, Enum):
    """Channel layouts."""
    MONO = "mono"
    STEREO = "stereo"
    SURROUND_5_1 = "5.1"
    SURROUND_7_1 = "7.1"


@dataclass
class AudioInfo:
    """Audio information."""
    format: AudioFormat = AudioFormat.MP3
    codec: Optional[str] = None
    duration: float = 0.0  # seconds
    sample_rate: int = 44100
    channels: int = 2
    bit_depth: int = 16
    bitrate: int = 0  # kbps
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscodeOptions:
    """Transcoding options."""
    format: AudioFormat = AudioFormat.MP3
    codec: Optional[AudioCodec] = None
    bitrate: int = 192  # kbps
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_depth: Optional[int] = None
    quality: int = 5  # 0-9, lower is better
    normalize: bool = False
    fade_in: float = 0.0  # seconds
    fade_out: float = 0.0  # seconds


@dataclass
class TrimOptions:
    """Trim options."""
    start: float = 0.0  # seconds
    end: Optional[float] = None
    duration: Optional[float] = None


@dataclass
class EffectOptions:
    """Audio effect options."""
    volume: float = 1.0
    speed: float = 1.0
    pitch: float = 1.0
    tempo: float = 1.0
    reverb: float = 0.0
    normalize: bool = False
    noise_reduction: bool = False


@dataclass
class WaveformOptions:
    """Waveform visualization options."""
    width: int = 800
    height: int = 200
    color: str = "#3498db"
    background: str = "#FFFFFF"
    line_width: int = 1
    samples_per_pixel: int = 100
    format: str = "png"


@dataclass
class ProcessedAudio:
    """Processed audio result."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: bytes = b""
    format: AudioFormat = AudioFormat.MP3
    duration: float = 0.0
    sample_rate: int = 44100
    channels: int = 2
    bitrate: int = 192
    size_bytes: int = 0
    operations: List[str] = field(default_factory=list)
    processed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Waveform:
    """Waveform visualization."""
    content: bytes = b""
    format: str = "png"
    width: int = 800
    height: int = 200
    peaks: List[float] = field(default_factory=list)


@dataclass
class AudioSegment:
    """Audio segment for timeline."""
    start: float = 0.0
    end: float = 0.0
    label: str = ""
    content: Optional[bytes] = None


# Audio Backend
class AudioBackend(ABC):
    """Abstract audio processing backend."""
    
    @abstractmethod
    async def get_info(self, data: bytes) -> AudioInfo:
        """Get audio information."""
        pass
    
    @abstractmethod
    async def transcode(
        self,
        data: bytes,
        options: TranscodeOptions,
    ) -> bytes:
        """Transcode audio."""
        pass
    
    @abstractmethod
    async def trim(
        self,
        data: bytes,
        options: TrimOptions,
    ) -> bytes:
        """Trim audio."""
        pass
    
    @abstractmethod
    async def apply_effects(
        self,
        data: bytes,
        options: EffectOptions,
    ) -> bytes:
        """Apply effects."""
        pass
    
    @abstractmethod
    async def generate_waveform(
        self,
        data: bytes,
        options: WaveformOptions,
    ) -> Waveform:
        """Generate waveform visualization."""
        pass
    
    @abstractmethod
    async def merge(
        self,
        audio_list: List[bytes],
        crossfade: float,
    ) -> bytes:
        """Merge audio files."""
        pass


class MockAudioBackend(AudioBackend):
    """Mock audio backend for testing."""
    
    async def get_info(self, data: bytes) -> AudioInfo:
        """Get mock audio info."""
        return AudioInfo(
            format=AudioFormat.MP3,
            codec="mp3",
            duration=180.0,
            sample_rate=44100,
            channels=2,
            bit_depth=16,
            bitrate=192,
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
            "bitrate": options.bitrate,
            "sample_rate": options.sample_rate,
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
    
    async def apply_effects(
        self,
        data: bytes,
        options: EffectOptions,
    ) -> bytes:
        """Mock apply effects."""
        info = {
            "operation": "effects",
            "volume": options.volume,
            "speed": options.speed,
            "normalize": options.normalize,
        }
        return json.dumps(info).encode()
    
    async def generate_waveform(
        self,
        data: bytes,
        options: WaveformOptions,
    ) -> Waveform:
        """Generate mock waveform."""
        import random
        peaks = [random.random() for _ in range(options.width)]
        
        # Generate simple SVG waveform
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{options.width}" height="{options.height}">',
            f'<rect width="100%" height="100%" fill="{options.background}"/>',
        ]
        
        mid = options.height // 2
        for i, peak in enumerate(peaks):
            h = int(peak * mid)
            svg_parts.append(
                f'<line x1="{i}" y1="{mid-h}" x2="{i}" y2="{mid+h}" '
                f'stroke="{options.color}" stroke-width="{options.line_width}"/>'
            )
        
        svg_parts.append('</svg>')
        
        return Waveform(
            content="\n".join(svg_parts).encode(),
            format="svg",
            width=options.width,
            height=options.height,
            peaks=peaks,
        )
    
    async def merge(
        self,
        audio_list: List[bytes],
        crossfade: float,
    ) -> bytes:
        """Mock merge."""
        info = {
            "operation": "merge",
            "file_count": len(audio_list),
            "crossfade": crossfade,
        }
        return json.dumps(info).encode()


class AudioProcessor:
    """
    Audio processing service.
    """
    
    def __init__(
        self,
        backend: Optional[AudioBackend] = None,
    ):
        self._backend = backend or MockAudioBackend()
    
    async def get_info(self, data: bytes) -> AudioInfo:
        """Get audio information."""
        return await self._backend.get_info(data)
    
    async def transcode(
        self,
        data: bytes,
        format: AudioFormat = AudioFormat.MP3,
        bitrate: int = 192,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        **kwargs,
    ) -> ProcessedAudio:
        """
        Transcode audio.
        
        Args:
            data: Audio bytes
            format: Output format
            bitrate: Target bitrate (kbps)
            sample_rate: Target sample rate
            channels: Target channels
            
        Returns:
            Processed audio
        """
        options = TranscodeOptions(
            format=format,
            bitrate=bitrate,
            sample_rate=sample_rate,
            channels=channels,
            **kwargs,
        )
        
        content = await self._backend.transcode(data, options)
        
        return ProcessedAudio(
            content=content,
            format=format,
            bitrate=bitrate,
            sample_rate=sample_rate or 44100,
            channels=channels or 2,
            size_bytes=len(content),
            operations=["transcode"],
        )
    
    async def to_mp3(
        self,
        data: bytes,
        bitrate: int = 192,
        **kwargs,
    ) -> ProcessedAudio:
        """Convert to MP3."""
        return await self.transcode(
            data,
            format=AudioFormat.MP3,
            bitrate=bitrate,
            **kwargs,
        )
    
    async def to_wav(
        self,
        data: bytes,
        sample_rate: int = 44100,
        **kwargs,
    ) -> ProcessedAudio:
        """Convert to WAV."""
        return await self.transcode(
            data,
            format=AudioFormat.WAV,
            sample_rate=sample_rate,
            **kwargs,
        )
    
    async def to_ogg(
        self,
        data: bytes,
        bitrate: int = 128,
        **kwargs,
    ) -> ProcessedAudio:
        """Convert to OGG."""
        return await self.transcode(
            data,
            format=AudioFormat.OGG,
            bitrate=bitrate,
            **kwargs,
        )
    
    async def compress(
        self,
        data: bytes,
        bitrate: int = 96,
        format: AudioFormat = AudioFormat.MP3,
    ) -> ProcessedAudio:
        """Compress audio."""
        return await self.transcode(data, format=format, bitrate=bitrate)
    
    async def trim(
        self,
        data: bytes,
        start: float = 0.0,
        end: Optional[float] = None,
        duration: Optional[float] = None,
    ) -> ProcessedAudio:
        """
        Trim audio.
        
        Args:
            data: Audio bytes
            start: Start time (seconds)
            end: End time (seconds)
            duration: Duration (seconds)
            
        Returns:
            Trimmed audio
        """
        options = TrimOptions(
            start=start,
            end=end,
            duration=duration,
        )
        
        content = await self._backend.trim(data, options)
        
        return ProcessedAudio(
            content=content,
            size_bytes=len(content),
            operations=["trim"],
        )
    
    async def split(
        self,
        data: bytes,
        segments: List[Tuple[float, float]],
    ) -> List[ProcessedAudio]:
        """
        Split audio into segments.
        
        Args:
            data: Audio bytes
            segments: List of (start, end) tuples
            
        Returns:
            List of audio segments
        """
        results = []
        
        for start, end in segments:
            segment = await self.trim(data, start=start, end=end)
            results.append(segment)
        
        return results
    
    async def split_by_duration(
        self,
        data: bytes,
        duration: float = 30.0,
    ) -> List[ProcessedAudio]:
        """Split audio into equal duration segments."""
        info = await self.get_info(data)
        
        segments = []
        start = 0.0
        
        while start < info.duration:
            end = min(start + duration, info.duration)
            segments.append((start, end))
            start = end
        
        return await self.split(data, segments)
    
    async def apply_effects(
        self,
        data: bytes,
        volume: float = 1.0,
        speed: float = 1.0,
        pitch: float = 1.0,
        normalize: bool = False,
        **kwargs,
    ) -> ProcessedAudio:
        """
        Apply audio effects.
        
        Args:
            data: Audio bytes
            volume: Volume multiplier
            speed: Speed multiplier
            pitch: Pitch adjustment
            normalize: Normalize volume
            
        Returns:
            Processed audio
        """
        options = EffectOptions(
            volume=volume,
            speed=speed,
            pitch=pitch,
            normalize=normalize,
            **kwargs,
        )
        
        content = await self._backend.apply_effects(data, options)
        
        return ProcessedAudio(
            content=content,
            size_bytes=len(content),
            operations=["effects"],
        )
    
    async def normalize(self, data: bytes) -> ProcessedAudio:
        """Normalize audio volume."""
        return await self.apply_effects(data, normalize=True)
    
    async def change_speed(
        self,
        data: bytes,
        speed: float = 1.0,
        preserve_pitch: bool = True,
    ) -> ProcessedAudio:
        """Change audio speed."""
        if preserve_pitch:
            return await self.apply_effects(data, tempo=speed)
        else:
            return await self.apply_effects(data, speed=speed)
    
    async def fade(
        self,
        data: bytes,
        fade_in: float = 0.0,
        fade_out: float = 0.0,
    ) -> ProcessedAudio:
        """Apply fade in/out."""
        options = TranscodeOptions(fade_in=fade_in, fade_out=fade_out)
        content = await self._backend.transcode(data, options)
        
        return ProcessedAudio(
            content=content,
            size_bytes=len(content),
            operations=["fade"],
        )
    
    async def waveform(
        self,
        data: bytes,
        width: int = 800,
        height: int = 200,
        color: str = "#3498db",
        background: str = "#FFFFFF",
        format: str = "png",
    ) -> Waveform:
        """
        Generate waveform visualization.
        
        Args:
            data: Audio bytes
            width: Image width
            height: Image height
            color: Waveform color
            background: Background color
            format: Image format
            
        Returns:
            Waveform image
        """
        options = WaveformOptions(
            width=width,
            height=height,
            color=color,
            background=background,
            format=format,
        )
        
        return await self._backend.generate_waveform(data, options)
    
    async def merge(
        self,
        audio_list: List[bytes],
        crossfade: float = 0.0,
    ) -> ProcessedAudio:
        """
        Merge audio files.
        
        Args:
            audio_list: List of audio bytes
            crossfade: Crossfade duration (seconds)
            
        Returns:
            Merged audio
        """
        content = await self._backend.merge(audio_list, crossfade)
        
        return ProcessedAudio(
            content=content,
            size_bytes=len(content),
            operations=["merge"],
        )
    
    async def mix(
        self,
        tracks: List[Tuple[bytes, float]],
    ) -> ProcessedAudio:
        """
        Mix multiple audio tracks.
        
        Args:
            tracks: List of (audio, volume) tuples
            
        Returns:
            Mixed audio
        """
        # Adjust volume for each track
        adjusted = []
        for audio, volume in tracks:
            result = await self.apply_effects(audio, volume=volume)
            adjusted.append(result.content)
        
        # Merge all tracks
        return await self.merge(adjusted)
    
    async def to_mono(self, data: bytes) -> ProcessedAudio:
        """Convert to mono."""
        return await self.transcode(data, channels=1)
    
    async def to_stereo(self, data: bytes) -> ProcessedAudio:
        """Convert to stereo."""
        return await self.transcode(data, channels=2)
    
    async def save(
        self,
        audio: ProcessedAudio,
        path: Union[str, Path],
    ) -> Path:
        """Save processed audio."""
        path = Path(path)
        path.write_bytes(audio.content)
        return path


# Decorators
def audio_response(
    format: AudioFormat = AudioFormat.MP3,
) -> Callable:
    """Decorator for audio response."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, ProcessedAudio):
                return {
                    "content": result.content,
                    "content_type": f"audio/{result.format.value}",
                }
            
            return result
        
        return wrapper
    return decorator


# Factory functions
def create_audio_processor(
    backend: Optional[AudioBackend] = None,
) -> AudioProcessor:
    """Create audio processor."""
    return AudioProcessor(backend)


def create_transcode_options(
    format: AudioFormat = AudioFormat.MP3,
    bitrate: int = 192,
    **kwargs,
) -> TranscodeOptions:
    """Create transcode options."""
    return TranscodeOptions(format=format, bitrate=bitrate, **kwargs)


def create_trim_options(
    start: float = 0.0,
    end: Optional[float] = None,
    duration: Optional[float] = None,
) -> TrimOptions:
    """Create trim options."""
    return TrimOptions(start=start, end=end, duration=duration)


def create_effect_options(
    volume: float = 1.0,
    speed: float = 1.0,
    **kwargs,
) -> EffectOptions:
    """Create effect options."""
    return EffectOptions(volume=volume, speed=speed, **kwargs)


def create_waveform_options(
    width: int = 800,
    height: int = 200,
    color: str = "#3498db",
    **kwargs,
) -> WaveformOptions:
    """Create waveform options."""
    return WaveformOptions(width=width, height=height, color=color, **kwargs)


__all__ = [
    # Exceptions
    "AudioError",
    "TranscodeError",
    "FormatError",
    # Enums
    "AudioFormat",
    "AudioCodec",
    "SampleRate",
    "BitDepth",
    "ChannelLayout",
    # Data classes
    "AudioInfo",
    "TranscodeOptions",
    "TrimOptions",
    "EffectOptions",
    "WaveformOptions",
    "ProcessedAudio",
    "Waveform",
    "AudioSegment",
    # Backend
    "AudioBackend",
    "MockAudioBackend",
    # Processor
    "AudioProcessor",
    # Decorators
    "audio_response",
    # Factory functions
    "create_audio_processor",
    "create_transcode_options",
    "create_trim_options",
    "create_effect_options",
    "create_waveform_options",
]
