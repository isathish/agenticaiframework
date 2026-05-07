"""Pure-Python DOCX reader — stdlib-only.

DOCX files are ZIP archives containing ``word/document.xml`` (Office Open XML).
We extract paragraph text by walking ``<w:p>`` elements. This covers the vast
majority of "read the text" use cases without pulling in ``python-docx``.

For richer needs (tables, styles, images), users should still install
``python-docx``. This module is purely a fallback.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from typing import List, Optional, Union


_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Paragraph:
    """One ``<w:p>`` paragraph from the document."""
    text: str = ""


class Document:
    """``python-docx``-shaped Document with a ``.paragraphs`` list.

    Constructable from a path or file-like object: ``Document("file.docx")``.
    """

    paragraphs: List[Paragraph]

    def __init__(self, source: Optional[Union[str, bytes, io.IOBase]] = None) -> None:
        self.paragraphs = []
        if source is not None:
            self._load(source)

    # -- loaders -----------------------------------------------------

    def _load(self, source: Union[str, bytes, io.IOBase]) -> None:
        if isinstance(source, (bytes, bytearray)):
            zf = zipfile.ZipFile(io.BytesIO(source))
        else:
            zf = zipfile.ZipFile(source)
        with zf:
            try:
                xml_bytes = zf.read("word/document.xml")
            except KeyError as exc:  # noqa: BLE001
                raise ValueError("Not a valid DOCX file (missing word/document.xml)") from exc
        self.paragraphs = _extract_paragraphs(xml_bytes)

    @classmethod
    def open(cls, source: Union[str, bytes, io.IOBase]) -> "Document":
        return cls(source)


def _extract_paragraphs(xml_bytes: bytes) -> List[Paragraph]:
    root = ET.fromstring(xml_bytes)
    paragraphs: List[Paragraph] = []
    for p in root.iter(f"{_W_NS}p"):
        runs: List[str] = []
        for t in p.iter(f"{_W_NS}t"):
            if t.text:
                runs.append(t.text)
        # paragraph break = newline; preserve empty paragraphs
        paragraphs.append(Paragraph(text="".join(runs)))
    return paragraphs


def open_docx(source: Union[str, bytes, io.IOBase]) -> Document:
    """Open a DOCX file and return a :class:`Document`."""
    return Document(source)


__all__ = ["Document", "Paragraph", "open_docx"]
