"""
Enterprise Compression Module.

Provides data compression, context compression, and
response optimization for agent operations.

Example:
    # Compress data
    compressor = Compressor(algorithm=CompressionAlgorithm.GZIP)
    compressed = compressor.compress(data)
    decompressed = compressor.decompress(compressed)
    
    # Context compression for LLM
    context_compressor = ContextCompressor(max_tokens=4000)
    compressed_context = context_compressor.compress(long_context)
    
    # Decorators
    @compress_response()
    async def get_large_data():
        ...
"""

from __future__ import annotations

import asyncio
import gzip
import zlib
import bz2
import lzma
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)
from datetime import datetime
from functools import wraps
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CompressionError(Exception):
    """Compression error."""
    pass


class DecompressionError(Exception):
    """Decompression error."""
    pass


class CompressionAlgorithm(str, Enum):
    """Compression algorithms."""
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    BZ2 = "bz2"
    LZMA = "lzma"


@dataclass
class CompressionResult:
    """Result of compression."""
    compressed_data: bytes
    original_size: int
    compressed_size: int
    algorithm: CompressionAlgorithm
    compression_ratio: float
    
    @property
    def savings_percent(self) -> float:
        """Get compression savings percentage."""
        if self.original_size == 0:
            return 0
        return (1 - self.compression_ratio) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "algorithm": self.algorithm.value,
            "compression_ratio": round(self.compression_ratio, 4),
            "savings_percent": round(self.savings_percent, 2),
        }


@dataclass
class CompressionStats:
    """Compression statistics."""
    total_compressed: int = 0
    total_original_bytes: int = 0
    total_compressed_bytes: int = 0
    
    @property
    def average_ratio(self) -> float:
        """Get average compression ratio."""
        if self.total_original_bytes == 0:
            return 1.0
        return self.total_compressed_bytes / self.total_original_bytes
    
    @property
    def total_savings_bytes(self) -> int:
        """Get total bytes saved."""
        return self.total_original_bytes - self.total_compressed_bytes
    
    def record(self, result: CompressionResult) -> None:
        """Record a compression result."""
        self.total_compressed += 1
        self.total_original_bytes += result.original_size
        self.total_compressed_bytes += result.compressed_size
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_compressed": self.total_compressed,
            "total_original_bytes": self.total_original_bytes,
            "total_compressed_bytes": self.total_compressed_bytes,
            "average_ratio": round(self.average_ratio, 4),
            "total_savings_bytes": self.total_savings_bytes,
        }


class Compressor(ABC):
    """Abstract compressor."""
    
    @property
    @abstractmethod
    def algorithm(self) -> CompressionAlgorithm:
        """Get compression algorithm."""
        pass
    
    @abstractmethod
    def compress(self, data: bytes) -> CompressionResult:
        """Compress data."""
        pass
    
    @abstractmethod
    def decompress(self, data: bytes) -> bytes:
        """Decompress data."""
        pass
    
    def compress_string(self, text: str, encoding: str = 'utf-8') -> CompressionResult:
        """Compress a string."""
        return self.compress(text.encode(encoding))
    
    def decompress_string(self, data: bytes, encoding: str = 'utf-8') -> str:
        """Decompress to string."""
        return self.decompress(data).decode(encoding)


class NoCompressor(Compressor):
    """No-op compressor."""
    
    @property
    def algorithm(self) -> CompressionAlgorithm:
        return CompressionAlgorithm.NONE
    
    def compress(self, data: bytes) -> CompressionResult:
        return CompressionResult(
            compressed_data=data,
            original_size=len(data),
            compressed_size=len(data),
            algorithm=self.algorithm,
            compression_ratio=1.0,
        )
    
    def decompress(self, data: bytes) -> bytes:
        return data


class GzipCompressor(Compressor):
    """GZIP compressor."""
    
    def __init__(self, level: int = 9):
        """
        Initialize GZIP compressor.
        
        Args:
            level: Compression level (0-9)
        """
        self.level = level
    
    @property
    def algorithm(self) -> CompressionAlgorithm:
        return CompressionAlgorithm.GZIP
    
    def compress(self, data: bytes) -> CompressionResult:
        """Compress with GZIP."""
        original_size = len(data)
        compressed = gzip.compress(data, compresslevel=self.level)
        compressed_size = len(compressed)
        
        return CompressionResult(
            compressed_data=compressed,
            original_size=original_size,
            compressed_size=compressed_size,
            algorithm=self.algorithm,
            compression_ratio=compressed_size / original_size if original_size > 0 else 1.0,
        )
    
    def decompress(self, data: bytes) -> bytes:
        """Decompress GZIP data."""
        try:
            return gzip.decompress(data)
        except Exception as e:
            raise DecompressionError(f"GZIP decompression failed: {e}")


class ZlibCompressor(Compressor):
    """ZLIB compressor."""
    
    def __init__(self, level: int = 9):
        self.level = level
    
    @property
    def algorithm(self) -> CompressionAlgorithm:
        return CompressionAlgorithm.ZLIB
    
    def compress(self, data: bytes) -> CompressionResult:
        """Compress with ZLIB."""
        original_size = len(data)
        compressed = zlib.compress(data, level=self.level)
        compressed_size = len(compressed)
        
        return CompressionResult(
            compressed_data=compressed,
            original_size=original_size,
            compressed_size=compressed_size,
            algorithm=self.algorithm,
            compression_ratio=compressed_size / original_size if original_size > 0 else 1.0,
        )
    
    def decompress(self, data: bytes) -> bytes:
        """Decompress ZLIB data."""
        try:
            return zlib.decompress(data)
        except Exception as e:
            raise DecompressionError(f"ZLIB decompression failed: {e}")


class Bz2Compressor(Compressor):
    """BZ2 compressor."""
    
    def __init__(self, level: int = 9):
        self.level = level
    
    @property
    def algorithm(self) -> CompressionAlgorithm:
        return CompressionAlgorithm.BZ2
    
    def compress(self, data: bytes) -> CompressionResult:
        """Compress with BZ2."""
        original_size = len(data)
        compressed = bz2.compress(data, compresslevel=self.level)
        compressed_size = len(compressed)
        
        return CompressionResult(
            compressed_data=compressed,
            original_size=original_size,
            compressed_size=compressed_size,
            algorithm=self.algorithm,
            compression_ratio=compressed_size / original_size if original_size > 0 else 1.0,
        )
    
    def decompress(self, data: bytes) -> bytes:
        """Decompress BZ2 data."""
        try:
            return bz2.decompress(data)
        except Exception as e:
            raise DecompressionError(f"BZ2 decompression failed: {e}")


class LzmaCompressor(Compressor):
    """LZMA compressor."""
    
    def __init__(self, preset: int = 6):
        self.preset = preset
    
    @property
    def algorithm(self) -> CompressionAlgorithm:
        return CompressionAlgorithm.LZMA
    
    def compress(self, data: bytes) -> CompressionResult:
        """Compress with LZMA."""
        original_size = len(data)
        compressed = lzma.compress(data, preset=self.preset)
        compressed_size = len(compressed)
        
        return CompressionResult(
            compressed_data=compressed,
            original_size=original_size,
            compressed_size=compressed_size,
            algorithm=self.algorithm,
            compression_ratio=compressed_size / original_size if original_size > 0 else 1.0,
        )
    
    def decompress(self, data: bytes) -> bytes:
        """Decompress LZMA data."""
        try:
            return lzma.decompress(data)
        except Exception as e:
            raise DecompressionError(f"LZMA decompression failed: {e}")


class AdaptiveCompressor(Compressor):
    """
    Adaptive compressor that selects the best algorithm.
    """
    
    def __init__(
        self,
        algorithms: Optional[List[CompressionAlgorithm]] = None,
    ):
        """
        Initialize adaptive compressor.
        
        Args:
            algorithms: Algorithms to try
        """
        self._algorithms = algorithms or [
            CompressionAlgorithm.GZIP,
            CompressionAlgorithm.ZLIB,
            CompressionAlgorithm.BZ2,
        ]
        self._compressors = {
            CompressionAlgorithm.NONE: NoCompressor(),
            CompressionAlgorithm.GZIP: GzipCompressor(),
            CompressionAlgorithm.ZLIB: ZlibCompressor(),
            CompressionAlgorithm.BZ2: Bz2Compressor(),
            CompressionAlgorithm.LZMA: LzmaCompressor(),
        }
        self._last_algorithm: Optional[CompressionAlgorithm] = None
    
    @property
    def algorithm(self) -> CompressionAlgorithm:
        return self._last_algorithm or CompressionAlgorithm.GZIP
    
    def compress(self, data: bytes) -> CompressionResult:
        """Compress with the best algorithm."""
        best_result: Optional[CompressionResult] = None
        
        for algo in self._algorithms:
            compressor = self._compressors.get(algo)
            if compressor:
                result = compressor.compress(data)
                
                if best_result is None or result.compression_ratio < best_result.compression_ratio:
                    best_result = result
        
        if best_result:
            self._last_algorithm = best_result.algorithm
            return best_result
        
        # Fallback to no compression
        return NoCompressor().compress(data)
    
    def decompress(self, data: bytes) -> bytes:
        """Decompress with the last used algorithm."""
        if self._last_algorithm:
            compressor = self._compressors.get(self._last_algorithm)
            if compressor:
                return compressor.decompress(data)
        
        # Try all algorithms
        for algo in self._algorithms:
            compressor = self._compressors.get(algo)
            if compressor:
                try:
                    return compressor.decompress(data)
                except DecompressionError:
                    continue
        
        raise DecompressionError("Could not decompress with any algorithm")


class ContextCompressor:
    """
    Compressor for LLM context to fit within token limits.
    """
    
    def __init__(
        self,
        max_tokens: int = 4000,
        chars_per_token: float = 4.0,
        preserve_recent: bool = True,
        summarize: bool = False,
        summarizer: Optional[Callable[[str], str]] = None,
    ):
        """
        Initialize context compressor.
        
        Args:
            max_tokens: Maximum tokens allowed
            chars_per_token: Estimated characters per token
            preserve_recent: Keep recent messages intact
            summarize: Enable summarization
            summarizer: Custom summarization function
        """
        self.max_tokens = max_tokens
        self.chars_per_token = chars_per_token
        self.preserve_recent = preserve_recent
        self.summarize = summarize
        self._summarizer = summarizer
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return int(len(text) / self.chars_per_token)
    
    def compress(
        self,
        context: Union[str, List[str], List[Dict[str, str]]],
    ) -> Union[str, List[str], List[Dict[str, str]]]:
        """
        Compress context to fit within token limits.
        
        Args:
            context: Context to compress (string, list of strings, or messages)
            
        Returns:
            Compressed context
        """
        if isinstance(context, str):
            return self._compress_string(context)
        
        if isinstance(context, list):
            if context and isinstance(context[0], dict):
                return self._compress_messages(context)
            return self._compress_list(context)
        
        return context
    
    def _compress_string(self, text: str) -> str:
        """Compress a string."""
        estimated_tokens = self.estimate_tokens(text)
        
        if estimated_tokens <= self.max_tokens:
            return text
        
        # Simple truncation
        max_chars = int(self.max_tokens * self.chars_per_token)
        
        if self.preserve_recent:
            # Keep the end
            return "..." + text[-max_chars:]
        else:
            # Keep the start
            return text[:max_chars] + "..."
    
    def _compress_list(self, texts: List[str]) -> List[str]:
        """Compress a list of texts."""
        total_tokens = sum(self.estimate_tokens(t) for t in texts)
        
        if total_tokens <= self.max_tokens:
            return texts
        
        # Keep recent items, trim older ones
        result = []
        remaining_tokens = self.max_tokens
        
        for text in reversed(texts):
            tokens = self.estimate_tokens(text)
            
            if tokens <= remaining_tokens:
                result.insert(0, text)
                remaining_tokens -= tokens
            else:
                # Truncate this item
                available_chars = int(remaining_tokens * self.chars_per_token)
                if available_chars > 50:  # Only include if meaningful
                    result.insert(0, text[:available_chars] + "...")
                break
        
        return result
    
    def _compress_messages(
        self,
        messages: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Compress a list of messages."""
        total_tokens = sum(
            self.estimate_tokens(m.get("content", ""))
            for m in messages
        )
        
        if total_tokens <= self.max_tokens:
            return messages
        
        # Keep system message and recent messages
        result = []
        remaining_tokens = self.max_tokens
        
        # Always include system message if present
        for msg in messages:
            if msg.get("role") == "system":
                tokens = self.estimate_tokens(msg.get("content", ""))
                result.append(msg)
                remaining_tokens -= tokens
                break
        
        # Add recent messages from the end
        for msg in reversed(messages):
            if msg.get("role") == "system":
                continue
            
            content = msg.get("content", "")
            tokens = self.estimate_tokens(content)
            
            if tokens <= remaining_tokens:
                result.insert(1 if result and result[0].get("role") == "system" else 0, msg)
                remaining_tokens -= tokens
            else:
                # Maybe add a summary placeholder
                if remaining_tokens > 20:
                    result.insert(
                        1 if result and result[0].get("role") == "system" else 0,
                        {"role": "system", "content": "[Earlier conversation summarized]"},
                    )
                break
        
        return result


class ResponseCompressor:
    """
    Compress responses for storage or transmission.
    """
    
    def __init__(
        self,
        compressor: Optional[Compressor] = None,
        threshold_bytes: int = 1024,
        encode_base64: bool = True,
    ):
        """
        Initialize response compressor.
        
        Args:
            compressor: Compression algorithm to use
            threshold_bytes: Only compress if larger than this
            encode_base64: Encode compressed data as base64
        """
        self._compressor = compressor or GzipCompressor()
        self._threshold = threshold_bytes
        self._encode_base64 = encode_base64
    
    def compress(self, data: Any) -> Dict[str, Any]:
        """
        Compress response data.
        
        Returns:
            Dictionary with compressed data and metadata
        """
        # Serialize to JSON
        json_str = json.dumps(data, default=str)
        json_bytes = json_str.encode('utf-8')
        
        if len(json_bytes) < self._threshold:
            return {
                "compressed": False,
                "data": data,
            }
        
        result = self._compressor.compress(json_bytes)
        
        compressed_data = result.compressed_data
        if self._encode_base64:
            compressed_data = base64.b64encode(compressed_data).decode('ascii')
        
        return {
            "compressed": True,
            "algorithm": result.algorithm.value,
            "original_size": result.original_size,
            "compressed_size": result.compressed_size,
            "data": compressed_data,
        }
    
    def decompress(self, data: Dict[str, Any]) -> Any:
        """Decompress response data."""
        if not data.get("compressed"):
            return data.get("data")
        
        compressed_data = data["data"]
        
        if isinstance(compressed_data, str):
            compressed_data = base64.b64decode(compressed_data)
        
        decompressed = self._compressor.decompress(compressed_data)
        return json.loads(decompressed.decode('utf-8'))


def create_compressor(
    algorithm: Union[str, CompressionAlgorithm] = CompressionAlgorithm.GZIP,
    level: int = 9,
) -> Compressor:
    """
    Factory function to create a compressor.
    
    Args:
        algorithm: Compression algorithm
        level: Compression level
        
    Returns:
        Compressor instance
    """
    if isinstance(algorithm, str):
        algorithm = CompressionAlgorithm(algorithm.lower())
    
    if algorithm == CompressionAlgorithm.NONE:
        return NoCompressor()
    elif algorithm == CompressionAlgorithm.GZIP:
        return GzipCompressor(level)
    elif algorithm == CompressionAlgorithm.ZLIB:
        return ZlibCompressor(level)
    elif algorithm == CompressionAlgorithm.BZ2:
        return Bz2Compressor(level)
    elif algorithm == CompressionAlgorithm.LZMA:
        return LzmaCompressor(level)
    else:
        return GzipCompressor(level)


def compress_response(
    algorithm: CompressionAlgorithm = CompressionAlgorithm.GZIP,
    threshold: int = 1024,
) -> Callable:
    """
    Decorator to compress function response.
    
    Example:
        @compress_response()
        async def get_large_data():
            return large_data
    """
    compressor = ResponseCompressor(
        compressor=create_compressor(algorithm),
        threshold_bytes=threshold,
    )
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            result = await func(*args, **kwargs)
            return compressor.compress(result)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            result = func(*args, **kwargs)
            return compressor.compress(result)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


__all__ = [
    # Exceptions
    "CompressionError",
    "DecompressionError",
    # Enums
    "CompressionAlgorithm",
    # Data classes
    "CompressionResult",
    "CompressionStats",
    # Compressors
    "Compressor",
    "NoCompressor",
    "GzipCompressor",
    "ZlibCompressor",
    "Bz2Compressor",
    "LzmaCompressor",
    "AdaptiveCompressor",
    # Context
    "ContextCompressor",
    "ResponseCompressor",
    # Factory
    "create_compressor",
    # Decorators
    "compress_response",
]
