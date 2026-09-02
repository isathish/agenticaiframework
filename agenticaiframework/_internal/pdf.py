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


# ---------------------------------------------------------------------------
# Object-level document model (merge / split / stamp / encrypt)
# ---------------------------------------------------------------------------

_OBJ_HEAD_RE = re.compile(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b")
_REF_RE = re.compile(rb"(?<![0-9.])(\d+)\s+(\d+)\s+R\b")
_WS = b"\x00\t\n\x0c\r "


class PdfError(Exception):
    pass


class PdfDocument:
    """Editable in-memory PDF (classic xref tables, uncompressed object
    layout). Object streams (``/ObjStm``) are not supported; callers should
    fall back to ``pypdf`` for those files."""

    def __init__(self) -> None:
        self.objects: Dict[int, bytes] = {}  # object number -> body (between "obj" and "endobj")
        self.trailer: Dict[bytes, bytes] = {}
        self.root: int = 0
        self.version: bytes = b"1.4"

    # -- parsing ----------------------------------------------------------------

    @classmethod
    def parse(cls, data: bytes) -> "PdfDocument":
        doc = cls()
        m = re.match(rb"%PDF-(\d\.\d)", data)
        if m:
            doc.version = m.group(1)
        if b"/ObjStm" in data:
            raise PdfError("PDF uses compressed object streams; install pypdf for this file")
        pos = 0
        while True:
            m = _OBJ_HEAD_RE.search(data, pos)
            if not m:
                break
            num = int(m.group(1))
            start = m.end()
            body_end = cls._find_endobj(data, start)
            body = data[start:body_end].strip(_WS)
            doc.objects[num] = body  # later definitions (incremental updates) win
            pos = body_end
        for tm in re.finditer(rb"trailer\s*<<", data):
            dict_bytes = _read_dict(data, tm.end() - 2)
            doc.trailer.update(_parse_dict_entries(dict_bytes))
        if b"/Root" not in doc.trailer:
            # xref-stream PDFs keep /Root in the stream dictionary.
            for num, body in doc.objects.items():
                if b"/Type" in body and b"/XRef" in body and b"/Root" in body:
                    doc.trailer.update(_parse_dict_entries(_read_dict(body, body.find(b"<<"))))
                    break
        root_ref = _REF_RE.search(doc.trailer.get(b"/Root", b""))
        if not root_ref:
            for num, body in doc.objects.items():
                if b"/Type" in body and b"/Catalog" in body:
                    doc.root = num
                    break
        else:
            doc.root = int(root_ref.group(1))
        if not doc.root or doc.root not in doc.objects:
            raise PdfError("Could not locate /Catalog")
        return doc

    @staticmethod
    def _find_endobj(data: bytes, start: int) -> int:
        stream_pos = data.find(b"stream", start)
        endobj_pos = data.find(b"endobj", start)
        if endobj_pos == -1:
            return len(data)
        if stream_pos != -1 and stream_pos < endobj_pos:
            # honour /Length so binary stream data containing "endobj" is safe
            dict_part = data[start:stream_pos]
            lm = re.search(rb"/Length\s+(\d+)(?:\s+0\s+R)?", dict_part)
            if lm and b" 0 R" not in dict_part[lm.start():lm.end()]:
                body_start = stream_pos + len(b"stream")
                if data[body_start:body_start + 2] == b"\r\n":
                    body_start += 2
                elif data[body_start:body_start + 1] == b"\n":
                    body_start += 1
                end_stream = data.find(b"endstream", body_start + int(lm.group(1)))
            else:
                end_stream = data.find(b"endstream", stream_pos)
            if end_stream != -1:
                endobj_pos = data.find(b"endobj", end_stream)
                if endobj_pos == -1:
                    return len(data)
        return endobj_pos

    # -- navigation -------------------------------------------------------------

    def dict_of(self, num: int) -> Dict[bytes, bytes]:
        body = self.objects[num]
        idx = body.find(b"<<")
        return _parse_dict_entries(_read_dict(body, idx)) if idx != -1 else {}

    def resolve_ref(self, value: bytes) -> Optional[int]:
        m = _REF_RE.fullmatch(value.strip())
        return int(m.group(1)) if m else None

    def page_numbers(self) -> List[int]:
        """Object numbers of pages in document order."""
        catalog = self.dict_of(self.root)
        pages_root = self.resolve_ref(catalog.get(b"/Pages", b""))
        if pages_root is None:
            raise PdfError("Catalog has no /Pages")
        out: List[int] = []
        seen = set()

        def walk(num: int) -> None:
            if num in seen or num not in self.objects:
                return
            seen.add(num)
            d = self.dict_of(num)
            if d.get(b"/Type", b"").strip() == b"/Page":
                out.append(num)
                return
            for ref in _REF_RE.finditer(d.get(b"/Kids", b"")):
                walk(int(ref.group(1)))

        walk(pages_root)
        return out

    @property
    def num_pages(self) -> int:
        return len(self.page_numbers())

    def new_object(self, body: bytes) -> int:
        num = max(self.objects) + 1 if self.objects else 1
        self.objects[num] = body
        return num

    def set_dict_entry(self, num: int, key: bytes, value: bytes) -> None:
        body = self.objects[num]
        idx = body.find(b"<<")
        raw = _read_dict(body, idx)
        entries = _parse_dict_entries(raw)
        entries[key] = value
        new_dict = b"<< " + b" ".join(k + b" " + v for k, v in entries.items()) + b" >>"
        self.objects[num] = body[:idx] + new_dict + body[idx + len(raw):]

    # -- serialisation ----------------------------------------------------------

    def to_bytes(self, extra_trailer: Optional[Dict[bytes, bytes]] = None) -> bytes:
        nums = sorted(self.objects)
        out = bytearray(b"%PDF-" + self.version + b"\n%\xe2\xe3\xcf\xd3\n")
        offsets: Dict[int, int] = {}
        for num in nums:
            offsets[num] = len(out)
            out.extend(f"{num} 0 obj\n".encode())
            out.extend(self.objects[num])
            out.extend(b"\nendobj\n")
        xref_pos = len(out)
        size = (nums[-1] + 1) if nums else 1
        out.extend(f"xref\n0 {size}\n".encode())
        out.extend(b"0000000000 65535 f \n")
        for num in range(1, size):
            if num in offsets:
                out.extend(f"{offsets[num]:010d} 00000 n \n".encode())
            else:
                out.extend(b"0000000000 65535 f \n")
        trailer = {b"/Size": str(size).encode(), b"/Root": f"{self.root} 0 R".encode()}
        if b"/Info" in self.trailer:
            trailer[b"/Info"] = self.trailer[b"/Info"]
        if extra_trailer:
            trailer.update(extra_trailer)
        out.extend(b"trailer\n<< " + b" ".join(k + b" " + v for k, v in trailer.items()) + b" >>\n")
        out.extend(f"startxref\n{xref_pos}\n%%EOF\n".encode())
        return bytes(out)

    # -- operations -------------------------------------------------------------

    def renumbered(self, offset: int) -> "PdfDocument":
        """Copy with every object number shifted by ``offset``."""
        doc = PdfDocument()
        doc.version = self.version

        def shift(body: bytes) -> bytes:
            return _REF_RE.sub(lambda m: f"{int(m.group(1)) + offset} {m.group(2).decode()} R".encode(), body)

        for num, body in self.objects.items():
            doc.objects[num + offset] = shift(body)
        doc.root = self.root + offset
        doc.trailer = {k: shift(v) for k, v in self.trailer.items()}
        return doc

    def with_pages(self, page_nums: List[int]) -> "PdfDocument":
        """Copy whose page tree contains only ``page_nums`` (object numbers)."""
        doc = PdfDocument()
        doc.version = self.version
        doc.objects = dict(self.objects)
        doc.trailer = dict(self.trailer)
        kids = b" ".join(f"{n} 0 R".encode() for n in page_nums)
        pages_id = doc.new_object(b"<< /Type /Pages /Count " + str(len(page_nums)).encode() + b" /Kids [" + kids + b"] >>")
        for n in page_nums:
            doc.set_dict_entry(n, b"/Parent", f"{pages_id} 0 R".encode())
        catalog = self.dict_of(self.root)
        catalog[b"/Pages"] = f"{pages_id} 0 R".encode()
        catalog.pop(b"/Outlines", None)
        catalog.pop(b"/PageLabels", None)
        doc.root = doc.new_object(b"<< " + b" ".join(k + b" " + v for k, v in catalog.items()) + b" >>")
        return doc

    def page_size(self, page_num: int) -> Tuple[float, float]:
        d = self.dict_of(page_num)
        box = d.get(b"/MediaBox")
        parent = self.resolve_ref(d.get(b"/Parent", b""))
        while box is None and parent is not None:
            pd = self.dict_of(parent)
            box = pd.get(b"/MediaBox")
            parent = self.resolve_ref(pd.get(b"/Parent", b""))
        if box is None:
            return 612.0, 792.0
        nums = [float(x) for x in re.findall(rb"[-+]?\d*\.?\d+", box)]
        if len(nums) != 4:
            return 612.0, 792.0
        return abs(nums[2] - nums[0]), abs(nums[3] - nums[1])

    def stamp_pages(self, content_fn, *, font: bytes = b"/Helvetica") -> None:
        """Append a content stream (built by ``content_fn(index, total, width, height) -> bytes``)
        to every page; a shared Helvetica font resource is registered as ``/AAFStamp``."""
        font_id = self.new_object(b"<< /Type /Font /Subtype /Type1 /BaseFont " + font + b" /Encoding /WinAnsiEncoding >>")
        gs_id = self.new_object(b"<< /Type /ExtGState /ca 0.5 /CA 0.5 >>")
        pages = self.page_numbers()
        for idx, pnum in enumerate(pages):
            w, h = self.page_size(pnum)
            content = content_fn(idx, len(pages), w, h)
            cid = self.new_object(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
            d = self.dict_of(pnum)
            existing = d.get(b"/Contents", b"").strip()
            if existing.startswith(b"["):
                new_contents = existing[:-1].rstrip() + f" {cid} 0 R]".encode()
            elif existing:
                new_contents = b"[" + existing + f" {cid} 0 R]".encode()
            else:
                new_contents = f"{cid} 0 R".encode()
            self.set_dict_entry(pnum, b"/Contents", new_contents)
            # Merge font into page resources (inherit-or-create).
            res = d.get(b"/Resources", b"").strip()
            res_ref = self.resolve_ref(res) if res else None
            if res_ref is not None:
                res_dict = self.dict_of(res_ref)
                target_num: Optional[int] = res_ref
            elif res.startswith(b"<<"):
                res_dict = _parse_dict_entries(res)
                target_num = None
            else:
                res_dict = {}
                target_num = None
            fonts = res_dict.get(b"/Font", b"").strip()
            font_ref = self.resolve_ref(fonts) if fonts else None
            if font_ref is not None:
                self.set_dict_entry(font_ref, b"/AAFStamp", f"{font_id} 0 R".encode())
            else:
                fd = _parse_dict_entries(fonts) if fonts.startswith(b"<<") else {}
                fd[b"/AAFStamp"] = f"{font_id} 0 R".encode()
                res_dict[b"/Font"] = b"<< " + b" ".join(k + b" " + v for k, v in fd.items()) + b" >>"
            egs = res_dict.get(b"/ExtGState", b"").strip()
            egs_ref = self.resolve_ref(egs) if egs else None
            if egs_ref is not None:
                self.set_dict_entry(egs_ref, b"/AAFStampGS", f"{gs_id} 0 R".encode())
            else:
                ed = _parse_dict_entries(egs) if egs.startswith(b"<<") else {}
                ed[b"/AAFStampGS"] = f"{gs_id} 0 R".encode()
                res_dict[b"/ExtGState"] = b"<< " + b" ".join(k + b" " + v for k, v in ed.items()) + b" >>"
            new_res = b"<< " + b" ".join(k + b" " + v for k, v in res_dict.items()) + b" >>"
            if target_num is not None:
                self.objects[target_num] = new_res
            else:
                self.set_dict_entry(pnum, b"/Resources", new_res)

    def set_info(self, **fields: str) -> None:
        """Set /Info dictionary entries (Title, Author, Subject, Keywords, Producer...)."""
        entries = {}
        info_ref = self.resolve_ref(self.trailer.get(b"/Info", b""))
        if info_ref is not None and info_ref in self.objects:
            entries = self.dict_of(info_ref)
        for k, v in fields.items():
            if v:
                entries[b"/" + k.encode()] = _pdf_string(v)
        body = b"<< " + b" ".join(k + b" " + v for k, v in entries.items()) + b" >>"
        if info_ref is not None and info_ref in self.objects:
            self.objects[info_ref] = body
        else:
            self.trailer[b"/Info"] = f"{self.new_object(body)} 0 R".encode()

    def encrypt_rc4(self, user_password: str, owner_password: Optional[str] = None,
                    permissions: int = -1) -> bytes:
        """Serialise with the standard security handler (R3, RC4 128-bit)."""
        import hashlib
        import secrets

        owner_password = owner_password or user_password
        doc_id = secrets.token_bytes(16)
        o_entry = _compute_o_entry(owner_password, user_password)
        key = _compute_key(user_password, o_entry, permissions, doc_id)
        u_entry = _compute_u_entry(key, doc_id)

        enc_id = max(self.objects) + 1
        encrypted: Dict[int, bytes] = {}
        for num, body in self.objects.items():
            obj_key = hashlib.md5(key + num.to_bytes(3, "little") + b"\x00\x00").digest()[:16]
            encrypted[num] = _encrypt_object_body(body, obj_key)
        self.objects = encrypted
        signed_perms = permissions - (1 << 32) if permissions >= (1 << 31) else permissions
        self.objects[enc_id] = (
            b"<< /Filter /Standard /V 2 /R 3 /Length 128 /P " + str(signed_perms).encode()
            + b" /O " + _hex_string(o_entry) + b" /U " + _hex_string(u_entry) + b" >>"
        )
        return self.to_bytes(extra_trailer={
            b"/Encrypt": f"{enc_id} 0 R".encode(),
            b"/ID": b"[" + _hex_string(doc_id) + b" " + _hex_string(doc_id) + b"]",
        })


def merge_documents(docs: List["PdfDocument"]) -> "PdfDocument":
    if not docs:
        raise PdfError("nothing to merge")
    merged = PdfDocument()
    merged.version = max(d.version for d in docs)
    offset = 0
    all_pages: List[int] = []
    for doc in docs:
        shifted = doc.renumbered(offset)
        merged.objects.update(shifted.objects)
        all_pages.extend(shifted.page_numbers())
        offset = max(merged.objects)
    kids = b" ".join(f"{n} 0 R".encode() for n in all_pages)
    pages_id = merged.new_object(b"<< /Type /Pages /Count " + str(len(all_pages)).encode() + b" /Kids [" + kids + b"] >>")
    for n in all_pages:
        merged.set_dict_entry(n, b"/Parent", f"{pages_id} 0 R".encode())
    merged.root = merged.new_object(b"<< /Type /Catalog /Pages " + f"{pages_id} 0 R".encode() + b" >>")
    return merged


# -- low-level helpers -------------------------------------------------------------

def _read_dict(data: bytes, start: int) -> bytes:
    """Return the bytes of the balanced ``<< ... >>`` starting at ``start``."""
    depth = 0
    i = start
    n = len(data)
    while i < n:
        if data[i:i + 2] == b"<<":
            depth += 1
            i += 2
        elif data[i:i + 2] == b">>":
            depth -= 1
            i += 2
            if depth == 0:
                return data[start:i]
        elif data[i:i + 1] == b"(":
            i = _skip_literal_string(data, i)
        elif data[i:i + 1] == b"%":
            while i < n and data[i:i + 1] not in (b"\n", b"\r"):
                i += 1
        else:
            i += 1
    return data[start:]


def _skip_literal_string(data: bytes, i: int) -> int:
    depth = 0
    n = len(data)
    while i < n:
        c = data[i:i + 1]
        if c == b"\\":
            i += 2
            continue
        if c == b"(":
            depth += 1
        elif c == b")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _parse_dict_entries(raw: bytes) -> Dict[bytes, bytes]:
    """Split ``<< /K v /K2 v2 >>`` into an ordered mapping of raw byte values."""
    inner = raw.strip()
    if inner.startswith(b"<<"):
        inner = inner[2:]
    if inner.endswith(b">>"):
        inner = inner[:-2]
    entries: Dict[bytes, bytes] = {}
    i = 0
    n = len(inner)
    while i < n:
        while i < n and inner[i] in _WS:
            i += 1
        if i >= n or inner[i:i + 1] != b"/":
            break
        j = i + 1
        while j < n and inner[j] not in _WS and inner[j:j + 1] not in (b"/", b"[", b"<", b"(", b">", b"]"):
            j += 1
        key = inner[i:j]
        i = j
        while i < n and inner[i] in _WS:
            i += 1
        vstart = i
        i = _skip_value(inner, i)
        entries[key] = inner[vstart:i].strip()
    return entries


def _skip_value(data: bytes, i: int) -> int:
    n = len(data)
    if i >= n:
        return i
    c = data[i:i + 1]
    if data[i:i + 2] == b"<<":
        return i + len(_read_dict(data, i))
    if c == b"[":
        depth = 0
        while i < n:
            ch = data[i:i + 1]
            if ch == b"[":
                depth += 1
            elif ch == b"]":
                depth -= 1
                if depth == 0:
                    return i + 1
            elif ch == b"(":
                i = _skip_literal_string(data, i)
                continue
            elif data[i:i + 2] == b"<<":
                i += len(_read_dict(data, i))
                continue
            i += 1
        return n
    if c == b"(":
        return _skip_literal_string(data, i)
    if c == b"<":
        end = data.find(b">", i)
        return n if end == -1 else end + 1
    if c == b"/":
        j = i + 1
        while j < n and data[j] not in _WS and data[j:j + 1] not in (b"/", b"[", b"<", b"(", b">", b"]"):
            j += 1
        return j
    # number / bool / null / reference "n g R"
    m = re.match(rb"[-+]?\d*\.?\d+\s+\d+\s+R|[-+]?\d*\.?\d+|true|false|null", data[i:])
    return i + (m.end() if m else 1)


def _pdf_string(text: str) -> bytes:
    try:
        raw = text.encode("latin-1")
    except UnicodeEncodeError:
        raw = b"\xfe\xff" + text.encode("utf-16-be")
        return b"<" + raw.hex().encode() + b">"
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def _hex_string(raw: bytes) -> bytes:
    return b"<" + raw.hex().encode() + b">"


def escape_pdf_text(text: str) -> bytes:
    raw = text.encode("cp1252", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


# -- RC4 + standard security handler (Algorithms 2, 3.3, 3.4/3.5 of PDF 1.7 §7.6) ------

_PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")


def rc4(key: bytes, data: bytes) -> bytes:
    S = list(range(256))
    j = 0
    klen = len(key)
    for i in range(256):
        j = (j + S[i] + key[i % klen]) & 0xFF
        S[i], S[j] = S[j], S[i]
    out = bytearray(len(data))
    i = j = 0
    for k, byte in enumerate(data):
        i = (i + 1) & 0xFF
        j = (j + S[i]) & 0xFF
        S[i], S[j] = S[j], S[i]
        out[k] = byte ^ S[(S[i] + S[j]) & 0xFF]
    return bytes(out)


def _pad_password(pw: str) -> bytes:
    raw = pw.encode("latin-1", errors="replace")
    return (raw + _PAD)[:32]


def _compute_o_entry(owner_pw: str, user_pw: str) -> bytes:
    import hashlib
    key = hashlib.md5(_pad_password(owner_pw)).digest()
    for _ in range(50):
        key = hashlib.md5(key).digest()
    out = rc4(key, _pad_password(user_pw))
    for i in range(1, 20):
        out = rc4(bytes(b ^ i for b in key), out)
    return out


def _compute_key(user_pw: str, o_entry: bytes, permissions: int, doc_id: bytes) -> bytes:
    import hashlib
    import struct
    signed = permissions - (1 << 32) if permissions >= (1 << 31) else permissions
    p_bytes = struct.pack("<i", signed)
    h = hashlib.md5(_pad_password(user_pw) + o_entry + p_bytes + doc_id).digest()
    for _ in range(50):
        h = hashlib.md5(h[:16]).digest()
    return h[:16]


def _compute_u_entry(key: bytes, doc_id: bytes) -> bytes:
    import hashlib
    h = hashlib.md5(_PAD + doc_id).digest()
    out = rc4(key, h)
    for i in range(1, 20):
        out = rc4(bytes(b ^ i for b in key), out)
    return out + b"\x00" * 16


def _encrypt_object_body(body: bytes, obj_key: bytes) -> bytes:
    """RC4-encrypt every literal/hex string and the stream payload in one object."""
    stream_pos = body.find(b"stream")
    dict_part, rest = (body, b"") if stream_pos == -1 else (body[:stream_pos], body[stream_pos:])

    def enc_literal(m: re.Match) -> bytes:
        raw = _unescape_literal(m.group(0)[1:-1])
        return b"<" + rc4(obj_key, raw).hex().encode() + b">"

    def enc_hex(m: re.Match) -> bytes:
        raw = bytes.fromhex(re.sub(rb"\s", b"", m.group(1)).decode() or "")
        return b"<" + rc4(obj_key, raw).hex().encode() + b">"

    # Literal strings (balanced parens, escapes) then hex strings not part of << >>.
    dict_part = re.sub(rb"\((?:[^()\\]|\\.|\((?:[^()\\]|\\.)*\))*\)", enc_literal, dict_part)
    dict_part = re.sub(rb"(?<!<)<([0-9A-Fa-f\s]*)>(?!>)", enc_hex, dict_part)
    if not rest:
        return dict_part
    start = len(b"stream")
    if rest[start:start + 2] == b"\r\n":
        start += 2
    elif rest[start:start + 1] == b"\n":
        start += 1
    end = rest.rfind(b"endstream")
    payload = rest[start:end].rstrip(b"\r\n") if end != -1 else rest[start:]
    lm = re.search(rb"/Length\s+(\d+)\b(?!\s+0\s+R)", dict_part)
    if lm:
        payload = rest[start:start + int(lm.group(1))]
    enc = rc4(obj_key, payload)
    dict_part = re.sub(rb"/Length\s+\d+\b(?!\s+0\s+R)", b"/Length " + str(len(enc)).encode(), dict_part, count=1)
    return dict_part + b"stream\n" + enc + b"\nendstream"


def _unescape_literal(raw: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(raw):
        c = raw[i:i + 1]
        if c == b"\\" and i + 1 < len(raw):
            nxt = raw[i + 1:i + 2]
            mapping = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f", b"(": b"(", b")": b")", b"\\": b"\\"}
            if nxt in mapping:
                out += mapping[nxt]
                i += 2
                continue
            if nxt.isdigit():
                oct_digits = re.match(rb"[0-7]{1,3}", raw[i + 1:]).group(0)
                out.append(int(oct_digits, 8) & 0xFF)
                i += 1 + len(oct_digits)
                continue
        out += c
        i += 1
    return bytes(out)


__all__ = ["PdfReader", "PdfWriter", "PdfPage", "PdfDocument", "PdfError", "merge_documents",
           "escape_pdf_text", "rc4"]
