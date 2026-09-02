"""Minimal HTTP/2 client (RFC 7540 + HPACK RFC 7541) — stdlib-only.

Just enough for request/response APIs that *require* HTTP/2 such as Apple
Push Notification service. One TLS connection (ALPN ``h2``), one or more
sequential requests, no server push, no flow-control tuning beyond what a
few-KB request needs.

    >>> with H2Connection("api.push.apple.com") as conn:
    ...     resp = conn.request("POST", "/3/device/abc", headers={...}, body=b"{}")
    ...     resp.status, resp.headers, resp.body
"""

from __future__ import annotations

import socket
import ssl
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"

# Frame types
_DATA, _HEADERS, _PRIORITY, _RST_STREAM, _SETTINGS, _PUSH_PROMISE, _PING, _GOAWAY, _WINDOW_UPDATE, _CONTINUATION = range(10)

# Flags
_END_STREAM = 0x1
_END_HEADERS = 0x4
_PADDED = 0x8
_PRIORITY_FLAG = 0x20
_ACK = 0x1


class H2Error(Exception):
    pass


# ---------------------------------------------------------------------------
# HPACK
# ---------------------------------------------------------------------------

_STATIC_TABLE: List[Tuple[str, str]] = [
    (":authority", ""), (":method", "GET"), (":method", "POST"), (":path", "/"),
    (":path", "/index.html"), (":scheme", "http"), (":scheme", "https"),
    (":status", "200"), (":status", "204"), (":status", "206"), (":status", "304"),
    (":status", "400"), (":status", "404"), (":status", "500"), ("accept-charset", ""),
    ("accept-encoding", "gzip, deflate"), ("accept-language", ""), ("accept-ranges", ""),
    ("accept", ""), ("access-control-allow-origin", ""), ("age", ""), ("allow", ""),
    ("authorization", ""), ("cache-control", ""), ("content-disposition", ""),
    ("content-encoding", ""), ("content-language", ""), ("content-length", ""),
    ("content-location", ""), ("content-range", ""), ("content-type", ""), ("cookie", ""),
    ("date", ""), ("etag", ""), ("expect", ""), ("expires", ""), ("from", ""), ("host", ""),
    ("if-match", ""), ("if-modified-since", ""), ("if-none-match", ""), ("if-range", ""),
    ("if-unmodified-since", ""), ("last-modified", ""), ("link", ""), ("location", ""),
    ("max-forwards", ""), ("proxy-authenticate", ""), ("proxy-authorization", ""),
    ("range", ""), ("referer", ""), ("refresh", ""), ("retry-after", ""), ("server", ""),
    ("set-cookie", ""), ("strict-transport-security", ""), ("transfer-encoding", ""),
    ("user-agent", ""), ("vary", ""), ("via", ""), ("www-authenticate", ""),
]

# RFC 7541 Appendix B — printable ASCII subset (+ EOS). Header values in
# practice are printable; any other prefix triggers a decode error which we
# surface as the raw bytes rather than crash.
_HUFFMAN_CODES: Dict[int, Tuple[int, int]] = {
    32: (0x14, 6), 33: (0x3f8, 10), 34: (0x3f9, 10), 35: (0xffa, 12), 36: (0x1ff9, 13),
    37: (0x15, 6), 38: (0xf8, 8), 39: (0x7fa, 11), 40: (0x3fa, 10), 41: (0x3fb, 10),
    42: (0xf9, 8), 43: (0x7fb, 11), 44: (0xfa, 8), 45: (0x16, 6), 46: (0x17, 6),
    47: (0x18, 6), 48: (0x0, 5), 49: (0x1, 5), 50: (0x2, 5), 51: (0x19, 6),
    52: (0x1a, 6), 53: (0x1b, 6), 54: (0x1c, 6), 55: (0x1d, 6), 56: (0x1e, 6),
    57: (0x1f, 6), 58: (0x5c, 7), 59: (0xfb, 8), 60: (0x7ffc, 15), 61: (0x20, 6),
    62: (0xffb, 12), 63: (0x3fc, 10), 64: (0x1ffa, 13), 65: (0x21, 6), 66: (0x5d, 7),
    67: (0x5e, 7), 68: (0x5f, 7), 69: (0x60, 7), 70: (0x61, 7), 71: (0x62, 7),
    72: (0x63, 7), 73: (0x64, 7), 74: (0x65, 7), 75: (0x66, 7), 76: (0x67, 7),
    77: (0x68, 7), 78: (0x69, 7), 79: (0x6a, 7), 80: (0x6b, 7), 81: (0x6c, 7),
    82: (0x6d, 7), 83: (0x6e, 7), 84: (0x6f, 7), 85: (0x70, 7), 86: (0x71, 7),
    87: (0x72, 7), 88: (0xfc, 8), 89: (0x73, 7), 90: (0xfd, 8), 91: (0x1ffb, 13),
    92: (0x7fff0, 19), 93: (0x1ffc, 13), 94: (0x3ffc, 14), 95: (0x22, 6), 96: (0x7ffd, 15),
    97: (0x3, 5), 98: (0x23, 6), 99: (0x4, 5), 100: (0x24, 6), 101: (0x5, 5),
    102: (0x25, 6), 103: (0x26, 6), 104: (0x27, 6), 105: (0x6, 5), 106: (0x74, 7),
    107: (0x75, 7), 108: (0x28, 6), 109: (0x29, 6), 110: (0x2a, 6), 111: (0x7, 5),
    112: (0x2b, 6), 113: (0x76, 7), 114: (0x2c, 6), 115: (0x8, 5), 116: (0x9, 5),
    117: (0x2d, 6), 118: (0x77, 7), 119: (0x78, 7), 120: (0x79, 7), 121: (0x7a, 7),
    122: (0x7b, 7), 123: (0x7ffe, 15), 124: (0x7fc, 11), 125: (0x3ffd, 14), 126: (0x1ffd, 13),
    256: (0x3fffffff, 30),
}
_HUFFMAN_DECODE: Dict[Tuple[int, int], int] = {(c, l): sym for sym, (c, l) in _HUFFMAN_CODES.items()}


def huffman_decode(data: bytes) -> bytes:
    out = bytearray()
    code, length = 0, 0
    for byte in data:
        for i in range(7, -1, -1):
            code = (code << 1) | ((byte >> i) & 1)
            length += 1
            sym = _HUFFMAN_DECODE.get((code, length))
            if sym is not None:
                if sym == 256:
                    raise H2Error("EOS in Huffman string")
                out.append(sym)
                code, length = 0, 0
            elif length > 30:
                raise H2Error("Unsupported Huffman code")
    # remaining bits must be a prefix of EOS (all ones), < 8 bits
    if length > 7 or code != (1 << length) - 1:
        raise H2Error("Invalid Huffman padding")
    return bytes(out)


def huffman_encode(data: bytes) -> bytes:
    bits, nbits = 0, 0
    for b in data:
        code, length = _HUFFMAN_CODES.get(b, (None, 0))
        if code is None:
            raise H2Error("Non-printable byte in Huffman encode")
        bits = (bits << length) | code
        nbits += length
    pad = (8 - nbits % 8) % 8
    bits = (bits << pad) | ((1 << pad) - 1)
    nbits += pad
    return bits.to_bytes(nbits // 8, "big") if nbits else b""


def _encode_int(value: int, prefix_bits: int, first_byte: int = 0) -> bytes:
    limit = (1 << prefix_bits) - 1
    if value < limit:
        return bytes([first_byte | value])
    out = bytearray([first_byte | limit])
    value -= limit
    while value >= 128:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _decode_int(data: bytes, idx: int, prefix_bits: int) -> Tuple[int, int]:
    limit = (1 << prefix_bits) - 1
    value = data[idx] & limit
    idx += 1
    if value < limit:
        return value, idx
    shift = 0
    while True:
        b = data[idx]
        idx += 1
        value += (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return value, idx


def _encode_string(s: str) -> bytes:
    raw = s.encode("utf-8")
    return _encode_int(len(raw), 7, 0x00) + raw


def _decode_string(data: bytes, idx: int) -> Tuple[str, int]:
    huff = bool(data[idx] & 0x80)
    length, idx = _decode_int(data, idx, 7)
    raw = data[idx: idx + length]
    idx += length
    if huff:
        try:
            raw = huffman_decode(raw)
        except H2Error:
            return "<huffman:" + raw.hex() + ">", idx
    return raw.decode("utf-8", errors="replace"), idx


class HPACKDecoder:
    def __init__(self, max_size: int = 4096) -> None:
        self._dynamic: List[Tuple[str, str]] = []
        self._max_size = max_size

    def _lookup(self, index: int) -> Tuple[str, str]:
        if index <= 0:
            raise H2Error("HPACK index 0")
        if index <= len(_STATIC_TABLE):
            return _STATIC_TABLE[index - 1]
        d = index - len(_STATIC_TABLE) - 1
        if d >= len(self._dynamic):
            raise H2Error("HPACK dynamic index out of range")
        return self._dynamic[d]

    def _add(self, name: str, value: str) -> None:
        self._dynamic.insert(0, (name, value))
        size = sum(len(n) + len(v) + 32 for n, v in self._dynamic)
        while size > self._max_size and self._dynamic:
            n, v = self._dynamic.pop()
            size -= len(n) + len(v) + 32

    def decode(self, block: bytes) -> List[Tuple[str, str]]:
        headers: List[Tuple[str, str]] = []
        idx = 0
        while idx < len(block):
            b = block[idx]
            if b & 0x80:  # indexed
                index, idx = _decode_int(block, idx, 7)
                headers.append(self._lookup(index))
            elif b & 0x40:  # literal with incremental indexing
                index, idx = _decode_int(block, idx, 6)
                name = self._lookup(index)[0] if index else None
                if name is None:
                    name, idx = _decode_string(block, idx)
                value, idx = _decode_string(block, idx)
                self._add(name, value)
                headers.append((name, value))
            elif b & 0x20:  # dynamic table size update
                self._max_size, idx = _decode_int(block, idx, 5)
                self._add("", "")  # trigger eviction
                self._dynamic.pop(0)
            else:  # literal without indexing / never indexed
                index, idx = _decode_int(block, idx, 4)
                name = self._lookup(index)[0] if index else None
                if name is None:
                    name, idx = _decode_string(block, idx)
                value, idx = _decode_string(block, idx)
                headers.append((name, value))
        return headers


def hpack_encode(headers: List[Tuple[str, str]]) -> bytes:
    """Encode using literal-without-indexing (stateless, always valid)."""
    out = bytearray()
    static_index = {kv: i + 1 for i, kv in enumerate(_STATIC_TABLE)}
    static_name = {}
    for i, (n, _v) in enumerate(_STATIC_TABLE):
        static_name.setdefault(n, i + 1)
    for name, value in headers:
        name = name.lower()
        idx = static_index.get((name, value))
        if idx:
            out += _encode_int(idx, 7, 0x80)
            continue
        nidx = static_name.get(name)
        if nidx:
            out += _encode_int(nidx, 4, 0x00)
        else:
            out += b"\x00" + _encode_string(name)
        out += _encode_string(value)
    return bytes(out)


# ---------------------------------------------------------------------------
# Frames / connection
# ---------------------------------------------------------------------------

def _frame(ftype: int, flags: int, stream_id: int, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload))[1:] + bytes([ftype, flags]) + struct.pack(">I", stream_id & 0x7FFFFFFF) + payload


@dataclass
class H2Response:
    status: int
    headers: Dict[str, str]
    body: bytes = b""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self):
        import json
        return json.loads(self.text) if self.body else None


class H2Connection:
    def __init__(self, host: str, port: int = 443, *, timeout: float = 30.0,
                 verify: bool = True) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        ctx.set_alpn_protocols(["h2"])
        raw = socket.create_connection((host, port), timeout=timeout)
        self._sock = ctx.wrap_socket(raw, server_hostname=host)
        if self._sock.selected_alpn_protocol() != "h2":
            self._sock.close()
            raise H2Error(f"{host} did not negotiate HTTP/2 via ALPN")
        self._decoder = HPACKDecoder()
        self._next_stream = 1
        self._max_frame = 16384
        self._sock.sendall(_PREFACE + _frame(_SETTINGS, 0, 0, b""))
        self._buf = b""

    # -- context manager ------------------------------------------------------

    def __enter__(self) -> "H2Connection":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._sock.sendall(_frame(_GOAWAY, 0, 0, struct.pack(">II", 0, 0)))
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass

    # -- I/O ------------------------------------------------------------------

    def _read_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise H2Error("Connection closed by peer")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _read_frame(self) -> Tuple[int, int, int, bytes]:
        head = self._read_exact(9)
        length = int.from_bytes(head[:3], "big")
        ftype, flags = head[3], head[4]
        stream_id = struct.unpack(">I", head[5:9])[0] & 0x7FFFFFFF
        return ftype, flags, stream_id, self._read_exact(length)

    def request(self, method: str, path: str, *, headers: Optional[Dict[str, str]] = None,
                body: bytes = b"") -> H2Response:
        stream_id = self._next_stream
        self._next_stream += 2
        hdrs: List[Tuple[str, str]] = [
            (":method", method.upper()), (":scheme", "https"),
            (":authority", self.host), (":path", path),
        ]
        for k, v in (headers or {}).items():
            if k.lower() in ("connection", "host", "transfer-encoding"):
                continue
            hdrs.append((k.lower(), str(v)))
        if body:
            hdrs.append(("content-length", str(len(body))))
        block = hpack_encode(hdrs)
        flags = _END_HEADERS | (0 if body else _END_STREAM)
        out = _frame(_HEADERS, flags, stream_id, block)
        for i in range(0, len(body), self._max_frame):
            chunk = body[i:i + self._max_frame]
            last = i + self._max_frame >= len(body)
            out += _frame(_DATA, _END_STREAM if last else 0, stream_id, chunk)
        self._sock.sendall(out)

        resp_headers: List[Tuple[str, str]] = []
        header_block = b""
        body_buf = bytearray()
        done = False
        while not done:
            ftype, fflags, sid, payload = self._read_frame()
            if ftype == _SETTINGS:
                if not fflags & _ACK:
                    for i in range(0, len(payload), 6):
                        ident, val = struct.unpack(">HI", payload[i:i + 6])
                        if ident == 0x5:
                            self._max_frame = val
                        elif ident == 0x1:
                            self._decoder._max_size = val  # noqa: SLF001
                    self._sock.sendall(_frame(_SETTINGS, _ACK, 0, b""))
                continue
            if ftype == _PING:
                if not fflags & _ACK:
                    self._sock.sendall(_frame(_PING, _ACK, 0, payload))
                continue
            if ftype == _GOAWAY:
                _last, code = struct.unpack(">II", payload[:8])
                raise H2Error(f"GOAWAY error_code={code} debug={payload[8:]!r}")
            if ftype == _WINDOW_UPDATE or ftype == _PRIORITY:
                continue
            if sid != stream_id:
                continue
            if ftype == _RST_STREAM:
                raise H2Error(f"RST_STREAM error_code={struct.unpack('>I', payload)[0]}")
            if ftype in (_HEADERS, _CONTINUATION):
                data = payload
                if ftype == _HEADERS:
                    if fflags & _PADDED:
                        pad = data[0]
                        data = data[1:len(data) - pad]
                    if fflags & _PRIORITY_FLAG:
                        data = data[5:]
                header_block += data
                if fflags & _END_HEADERS:
                    resp_headers.extend(self._decoder.decode(header_block))
                    header_block = b""
                if fflags & _END_STREAM:
                    done = True
            elif ftype == _DATA:
                data = payload
                if fflags & _PADDED:
                    pad = data[0]
                    data = data[1:len(data) - pad]
                body_buf += data
                if len(data):
                    inc = struct.pack(">I", len(data))
                    self._sock.sendall(_frame(_WINDOW_UPDATE, 0, 0, inc) + _frame(_WINDOW_UPDATE, 0, stream_id, inc))
                if fflags & _END_STREAM:
                    done = True

        hdr_map: Dict[str, str] = {}
        status = 0
        for k, v in resp_headers:
            if k == ":status":
                try:
                    status = int(v)
                except ValueError:
                    status = 0
            else:
                hdr_map[k] = v
        return H2Response(status=status, headers=hdr_map, body=bytes(body_buf))


def request(method: str, url: str, *, headers: Optional[Dict[str, str]] = None,
            body: bytes = b"", timeout: float = 30.0, verify: bool = True) -> H2Response:
    """One-shot HTTP/2 request."""
    import urllib.parse
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        raise H2Error("HTTP/2 client requires https URL")
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    with H2Connection(parsed.hostname or "", parsed.port or 443, timeout=timeout, verify=verify) as conn:
        return conn.request(method, path, headers=headers, body=body)


__all__ = ["H2Connection", "H2Response", "H2Error", "request", "hpack_encode", "HPACKDecoder",
           "huffman_decode", "huffman_encode"]
