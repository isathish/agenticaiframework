"""Stdlib-only PDF reader & writer (best-effort).

This is intentionally a tiny subset of ISO 32000-1:

* :class:`PdfReader` — opens a PDF, parses xref + trailer, extracts text from
  uncompressed and FlateDecode-compressed content streams. No CMap unicode
  remapping, no hyphenation handling — output is best-effort plain text
  suitable for indexing / RAG.
* :class:`PdfWriter` — produces a single-page PDF per ``add_page(text)`` call
  using built-in Helvetica (font #1). Supports manual line breaks; long lines
  are wrapped at ``page_width / char_width``.

Sufficient to replace ``pypdf`` + ``reportlab`` for indexing and small-report
generation. Not a substitute for full PDF rendering libraries.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

_OBJ_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj\s*(.*?)\s*endobj", re.DOTALL)
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_FILTER_RE = re.compile(rb"/Filter\s*(?:\[\s*)?/([A-Za-z0-9]+)")
_TEXT_SHOW_RE = re.compile(rb"\(((?:\\\)|\\\(|[^()])*?)\)\s*Tj")
_TEXT_ARRAY_RE = re.compile(rb"\[(.*?)\]\s*TJ", re.DOTALL)
_TEXT_QUOTE_RE = re.compile(rb"\(((?:\\\)|\\\(|[^()])*?)\)\s*'")


def _decode_pdf_string(raw: bytes) -> str:
    out = bytearray()
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == 0x5C and i + 1 < len(raw):  # backslash escape
            nxt = raw[i + 1]
            mapping = {0x6E: 0x0A, 0x72: 0x0D, 0x74: 0x09, 0x62: 0x08,
                       0x66: 0x0C, 0x28: 0x28, 0x29: 0x29, 0x5C: 0x5C}
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
                continue
            if 0x30 <= nxt <= 0x37:  # octal up to 3 digits
                j = i + 1
                end = min(i + 4, len(raw))
                while j < end and 0x30 <= raw[j] <= 0x37:
                    j += 1
                out.append(int(raw[i + 1: j], 8) & 0xFF)
                i = j
                continue
            i += 2
            continue
        out.append(c)
        i += 1
    try:
        return out.decode("latin-1")
    except Exception:  # noqa: BLE001
        return out.decode("utf-8", errors="replace")


@dataclass
class PdfPage:
    index: int
    text: str


@dataclass
class PdfReader:
    """Read text from a PDF file or bytes object."""

    path: Optional[str] = None
    data: Optional[bytes] = None
    pages: List[PdfPage] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.data is None:
            if not self.path:
                raise ValueError("PdfReader requires path= or data=")
            with open(self.path, "rb") as f:
                self.data = f.read()
        self._parse()

    # -- parsing ------------------------------------------------------

    def _parse(self) -> None:
        assert self.data is not None
        objects: Dict[Tuple[int, int], bytes] = {}
        for m in _OBJ_RE.finditer(self.data):
            obj_num = int(m.group(1))
            gen_num = int(m.group(2))
            objects[(obj_num, gen_num)] = m.group(3)

        page_streams: List[bytes] = []
        for body in objects.values():
            if b"/Type /Page" in body and b"/Type /Pages" not in body:
                stream = self._collect_text_streams(body, objects)
                page_streams.append(stream)

        if not page_streams:
            # Some PDFs don't tag pages cleanly — fall back to all streams.
            for body in objects.values():
                stream = self._extract_stream(body)
                if stream:
                    page_streams.append(stream)

        for i, stream in enumerate(page_streams):
            text = self._extract_text(stream)
            self.pages.append(PdfPage(index=i, text=text))

    def _collect_text_streams(self, page_body: bytes, objects: Dict[Tuple[int, int], bytes]) -> bytes:
        """Resolve ``/Contents`` reference(s) for a page object."""
        contents_match = re.search(rb"/Contents\s+(\d+)\s+(\d+)\s+R", page_body)
        if not contents_match:
            # Inline content
            return self._extract_stream(page_body)
        ref = (int(contents_match.group(1)), int(contents_match.group(2)))
        body = objects.get(ref)
        if body is None:
            return b""
        return self._extract_stream(body)

    def _extract_stream(self, body: bytes) -> bytes:
        m = _STREAM_RE.search(body)
        if not m:
            return b""
        raw = m.group(1)
        filters = [f.lower() for f in _FILTER_RE.findall(body)]
        if b"flatedecode" in filters:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                return b""
        return raw

    def _extract_text(self, stream: bytes) -> str:
        chunks: List[str] = []
        for m in _TEXT_SHOW_RE.finditer(stream):
            chunks.append(_decode_pdf_string(m.group(1)))
        for m in _TEXT_QUOTE_RE.finditer(stream):
            chunks.append("\n" + _decode_pdf_string(m.group(1)))
        for m in _TEXT_ARRAY_RE.finditer(stream):
            inner = m.group(1)
            for sub in re.finditer(rb"\(((?:\\\)|\\\(|[^()])*?)\)", inner):
                chunks.append(_decode_pdf_string(sub.group(1)))
        return " ".join(chunks).strip()

    # -- public -------------------------------------------------------

    def extract_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)

    @property
    def num_pages(self) -> int:
        return len(self.pages)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class PdfWriter:
    """Minimal multi-page PDF generator using built-in Helvetica."""

    def __init__(self, *, page_size: Tuple[int, int] = (612, 792)) -> None:
        self.page_width, self.page_height = page_size
        self._pages: List[List[str]] = []  # list of lines per page

    def add_page(self, text: str, *, font_size: int = 12) -> None:
        # Wrap manually using a conservative average char width of font_size * 0.5
        max_chars = max(20, int((self.page_width - 100) / (font_size * 0.5)))
        lines: List[str] = []
        for line in text.splitlines() or [""]:
            if not line:
                lines.append("")
                continue
            while len(line) > max_chars:
                cut = line.rfind(" ", 0, max_chars)
                if cut <= 0:
                    cut = max_chars
                lines.append(line[:cut])
                line = line[cut:].lstrip()
            lines.append(line)
        self._pages.append(lines)

    def save(self, path: str, *, font_size: int = 12) -> None:
        with open(path, "wb") as f:
            f.write(self.to_bytes(font_size=font_size))

    def to_bytes(self, *, font_size: int = 12) -> bytes:
        objects: List[bytes] = []
        offsets: List[int] = []

        def add(body: bytes) -> int:
            objects.append(body)
            return len(objects)

        # Object 1: catalog
        catalog_id = add(b"<< /Type /Catalog /Pages 2 0 R >>")
        # Object 2: pages tree (filled in below)
        pages_id = add(b"PLACEHOLDER")
        # Object 3: shared font
        font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

        page_ids: List[int] = []
        for lines in self._pages:
            content = self._build_content_stream(lines, font_size=font_size)
            content_id = add(
                b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream"
            )
            page_obj = (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
                + f"{self.page_width} {self.page_height}".encode("ascii")
                + b"] /Resources << /Font << /F1 " + str(font_id).encode("ascii") + b" 0 R >> >> "
                + b"/Contents " + str(content_id).encode("ascii") + b" 0 R >>"
            )
            page_ids.append(add(page_obj))

        kids = b" ".join(f"{pid} 0 R".encode("ascii") for pid in page_ids)
        pages_body = (
            b"<< /Type /Pages /Count " + str(len(page_ids)).encode("ascii") + b" "
            b"/Kids [" + kids + b"] >>"
        )
        objects[pages_id - 1] = pages_body  # replace placeholder

        # Assemble file
        out = bytearray()
        out.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        for i, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out.extend(f"{i} 0 obj\n".encode("ascii"))
            out.extend(body)
            out.extend(b"\nendobj\n")

        xref_pos = len(out)
        out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        out.extend(b"0000000000 65535 f \n")
        for off in offsets:
            out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
        out.extend(
            b"trailer\n<< /Size " + str(len(objects) + 1).encode("ascii")
            + b" /Root " + str(catalog_id).encode("ascii") + b" 0 R >>\n"
            b"startxref\n" + str(xref_pos).encode("ascii") + b"\n%%EOF\n"
        )
        return bytes(out)

    # -- helpers ------------------------------------------------------

    def _build_content_stream(self, lines: List[str], *, font_size: int) -> bytes:
        leading = int(font_size * 1.2)
        x = 50
        y = self.page_height - 60
        parts: List[bytes] = [b"BT", f"/F1 {font_size} Tf".encode("ascii"),
                              f"{leading} TL".encode("ascii"),
                              f"{x} {y} Td".encode("ascii")]
        for i, line in enumerate(lines):
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if i == 0:
                parts.append(f"({escaped}) Tj".encode("latin-1", errors="replace"))
            else:
                parts.append(f"T*\n({escaped}) Tj".encode("latin-1", errors="replace"))
        parts.append(b"ET")
        return b"\n".join(parts)


__all__ = ["PdfReader", "PdfWriter", "PdfPage"]
