"""Pure-Python MessagePack (https://github.com/msgpack/msgpack) — stdlib-only.

Implements the subset of the MessagePack spec needed for round-tripping
JSON-shaped Python objects: nil, bool, int, float (single + double),
str, bin, array, map. Exposes ``packb`` and ``unpackb`` to mirror the
shape of the third-party ``msgpack`` package.

References:
- https://github.com/msgpack/msgpack/blob/master/spec.md
"""

from __future__ import annotations

import struct
from typing import Any, List, Tuple, Union


class MsgpackError(Exception):
    """Raised on encode/decode errors."""


# ---------------------------------------------------------------------------
# Encoder
# ---------------------------------------------------------------------------

def packb(obj: Any, *, use_bin_type: bool = True) -> bytes:
    """Encode a Python object to MessagePack bytes."""
    out = bytearray()
    _pack(out, obj, use_bin_type=use_bin_type)
    return bytes(out)


def _pack(out: bytearray, obj: Any, *, use_bin_type: bool) -> None:
    if obj is None:
        out.append(0xC0)
        return
    if obj is True:
        out.append(0xC3)
        return
    if obj is False:
        out.append(0xC2)
        return
    if isinstance(obj, int):
        _pack_int(out, obj)
        return
    if isinstance(obj, float):
        # Always emit float64 for safety.
        out.append(0xCB)
        out.extend(struct.pack(">d", obj))
        return
    if isinstance(obj, str):
        data = obj.encode("utf-8")
        n = len(data)
        if n <= 31:
            out.append(0xA0 | n)
        elif n <= 0xFF:
            out.append(0xD9)
            out.append(n)
        elif n <= 0xFFFF:
            out.append(0xDA)
            out.extend(struct.pack(">H", n))
        elif n <= 0xFFFFFFFF:
            out.append(0xDB)
            out.extend(struct.pack(">I", n))
        else:
            raise MsgpackError("string too long")
        out.extend(data)
        return
    if isinstance(obj, (bytes, bytearray, memoryview)):
        data = bytes(obj)
        n = len(data)
        if not use_bin_type:
            # Emit as str type for legacy decoders.
            return _pack(out, data.decode("latin-1"), use_bin_type=False)
        if n <= 0xFF:
            out.append(0xC4)
            out.append(n)
        elif n <= 0xFFFF:
            out.append(0xC5)
            out.extend(struct.pack(">H", n))
        elif n <= 0xFFFFFFFF:
            out.append(0xC6)
            out.extend(struct.pack(">I", n))
        else:
            raise MsgpackError("bin too long")
        out.extend(data)
        return
    if isinstance(obj, (list, tuple)):
        n = len(obj)
        if n <= 15:
            out.append(0x90 | n)
        elif n <= 0xFFFF:
            out.append(0xDC)
            out.extend(struct.pack(">H", n))
        elif n <= 0xFFFFFFFF:
            out.append(0xDD)
            out.extend(struct.pack(">I", n))
        else:
            raise MsgpackError("array too long")
        for item in obj:
            _pack(out, item, use_bin_type=use_bin_type)
        return
    if isinstance(obj, dict):
        n = len(obj)
        if n <= 15:
            out.append(0x80 | n)
        elif n <= 0xFFFF:
            out.append(0xDE)
            out.extend(struct.pack(">H", n))
        elif n <= 0xFFFFFFFF:
            out.append(0xDF)
            out.extend(struct.pack(">I", n))
        else:
            raise MsgpackError("map too long")
        for k, v in obj.items():
            _pack(out, k, use_bin_type=use_bin_type)
            _pack(out, v, use_bin_type=use_bin_type)
        return
    raise MsgpackError(f"unsupported type: {type(obj).__name__}")


def _pack_int(out: bytearray, n: int) -> None:
    if 0 <= n <= 0x7F:
        out.append(n)
        return
    if -32 <= n < 0:
        out.append(0xE0 | (n & 0x1F))
        return
    if 0 <= n <= 0xFF:
        out.append(0xCC); out.append(n); return
    if 0 <= n <= 0xFFFF:
        out.append(0xCD); out.extend(struct.pack(">H", n)); return
    if 0 <= n <= 0xFFFFFFFF:
        out.append(0xCE); out.extend(struct.pack(">I", n)); return
    if 0 <= n <= 0xFFFFFFFFFFFFFFFF:
        out.append(0xCF); out.extend(struct.pack(">Q", n)); return
    if -0x80 <= n < 0:
        out.append(0xD0); out.extend(struct.pack(">b", n)); return
    if -0x8000 <= n < 0:
        out.append(0xD1); out.extend(struct.pack(">h", n)); return
    if -0x80000000 <= n < 0:
        out.append(0xD2); out.extend(struct.pack(">i", n)); return
    if -0x8000000000000000 <= n < 0:
        out.append(0xD3); out.extend(struct.pack(">q", n)); return
    raise MsgpackError("integer out of range")


# ---------------------------------------------------------------------------
# Decoder
# ---------------------------------------------------------------------------

def unpackb(data: bytes, *, raw: bool = False) -> Any:
    """Decode MessagePack bytes to a Python object.

    ``raw=False`` decodes ``str`` family as ``str``; ``raw=True`` decodes them
    as raw ``bytes`` (mirrors ``msgpack``'s legacy ``raw`` flag).
    """
    obj, off = _unpack(memoryview(data), 0, raw=raw)
    if off != len(data):
        raise MsgpackError("trailing bytes after value")
    return obj


def _unpack(buf: memoryview, off: int, *, raw: bool) -> Tuple[Any, int]:
    if off >= len(buf):
        raise MsgpackError("unexpected end of buffer")
    b = buf[off]
    off += 1

    # positive fixint
    if b <= 0x7F:
        return b, off
    # fixmap
    if 0x80 <= b <= 0x8F:
        return _unpack_map(buf, off, b & 0x0F, raw=raw)
    # fixarray
    if 0x90 <= b <= 0x9F:
        return _unpack_array(buf, off, b & 0x0F, raw=raw)
    # fixstr
    if 0xA0 <= b <= 0xBF:
        return _unpack_str(buf, off, b & 0x1F, raw=raw)
    # negative fixint
    if b >= 0xE0:
        return b - 0x100, off

    if b == 0xC0:  # nil
        return None, off
    if b == 0xC2:  # false
        return False, off
    if b == 0xC3:  # true
        return True, off
    if b == 0xC4:  # bin 8
        n = buf[off]; off += 1
        return bytes(buf[off:off + n]), off + n
    if b == 0xC5:  # bin 16
        n = struct.unpack_from(">H", buf, off)[0]; off += 2
        return bytes(buf[off:off + n]), off + n
    if b == 0xC6:  # bin 32
        n = struct.unpack_from(">I", buf, off)[0]; off += 4
        return bytes(buf[off:off + n]), off + n
    if b == 0xCA:  # float 32
        v = struct.unpack_from(">f", buf, off)[0]; return v, off + 4
    if b == 0xCB:  # float 64
        v = struct.unpack_from(">d", buf, off)[0]; return v, off + 8
    if b == 0xCC:  # uint 8
        return buf[off], off + 1
    if b == 0xCD:  # uint 16
        return struct.unpack_from(">H", buf, off)[0], off + 2
    if b == 0xCE:  # uint 32
        return struct.unpack_from(">I", buf, off)[0], off + 4
    if b == 0xCF:  # uint 64
        return struct.unpack_from(">Q", buf, off)[0], off + 8
    if b == 0xD0:  # int 8
        return struct.unpack_from(">b", buf, off)[0], off + 1
    if b == 0xD1:  # int 16
        return struct.unpack_from(">h", buf, off)[0], off + 2
    if b == 0xD2:  # int 32
        return struct.unpack_from(">i", buf, off)[0], off + 4
    if b == 0xD3:  # int 64
        return struct.unpack_from(">q", buf, off)[0], off + 8
    if b == 0xD9:  # str 8
        n = buf[off]; off += 1
        return _unpack_str(buf, off, n, raw=raw)
    if b == 0xDA:  # str 16
        n = struct.unpack_from(">H", buf, off)[0]; off += 2
        return _unpack_str(buf, off, n, raw=raw)
    if b == 0xDB:  # str 32
        n = struct.unpack_from(">I", buf, off)[0]; off += 4
        return _unpack_str(buf, off, n, raw=raw)
    if b == 0xDC:  # array 16
        n = struct.unpack_from(">H", buf, off)[0]; off += 2
        return _unpack_array(buf, off, n, raw=raw)
    if b == 0xDD:  # array 32
        n = struct.unpack_from(">I", buf, off)[0]; off += 4
        return _unpack_array(buf, off, n, raw=raw)
    if b == 0xDE:  # map 16
        n = struct.unpack_from(">H", buf, off)[0]; off += 2
        return _unpack_map(buf, off, n, raw=raw)
    if b == 0xDF:  # map 32
        n = struct.unpack_from(">I", buf, off)[0]; off += 4
        return _unpack_map(buf, off, n, raw=raw)

    raise MsgpackError(f"unsupported type byte: 0x{b:02X}")


def _unpack_str(buf: memoryview, off: int, n: int, *, raw: bool) -> Tuple[Union[str, bytes], int]:
    raw_bytes = bytes(buf[off:off + n])
    if raw:
        return raw_bytes, off + n
    return raw_bytes.decode("utf-8"), off + n


def _unpack_array(buf: memoryview, off: int, n: int, *, raw: bool) -> Tuple[List[Any], int]:
    items: List[Any] = []
    for _ in range(n):
        item, off = _unpack(buf, off, raw=raw)
        items.append(item)
    return items, off


def _unpack_map(buf: memoryview, off: int, n: int, *, raw: bool) -> Tuple[dict, int]:
    out: dict = {}
    for _ in range(n):
        k, off = _unpack(buf, off, raw=raw)
        v, off = _unpack(buf, off, raw=raw)
        out[k] = v
    return out, off


__all__ = ["packb", "unpackb", "MsgpackError"]
