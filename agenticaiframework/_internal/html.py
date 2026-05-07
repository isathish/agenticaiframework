"""Stdlib-only HTML parser used as a tiny ``BeautifulSoup`` replacement.

Builds a lightweight DOM tree on top of :class:`html.parser.HTMLParser`.
Only a small CSS-like selector subset is supported (tag, ``.class``,
``#id``, ``tag.cls``, ``tag#id``, descendant combinator), which covers the
framework's web-scraping needs.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Iterator, List, Optional, Sequence


class Element:
    """A DOM node."""

    __slots__ = ("tag", "attrs", "children", "parent", "_text")

    def __init__(self, tag: str = "", attrs: Optional[dict] = None) -> None:
        self.tag = tag.lower()
        self.attrs: dict[str, str] = dict(attrs or {})
        self.children: List["Element | str"] = []
        self.parent: Optional["Element"] = None
        self._text: str = ""

    # -- text ---------------------------------------------------------------

    @property
    def text(self) -> str:
        parts: List[str] = []
        for c in self.children:
            if isinstance(c, str):
                parts.append(c)
            else:
                parts.append(c.text)
        return "".join(parts).strip()

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return self.attrs.get(name.lower(), default)

    # -- traversal ----------------------------------------------------------

    def iter_descendants(self) -> Iterator["Element"]:
        for c in self.children:
            if isinstance(c, Element):
                yield c
                yield from c.iter_descendants()

    def find_all(self, tag: Optional[str] = None, **attr_filters: str) -> List["Element"]:
        out: List[Element] = []
        for el in self.iter_descendants():
            if tag and el.tag != tag.lower():
                continue
            if attr_filters and not all(
                el.attrs.get(k.replace("_", "-").lower()) == v for k, v in attr_filters.items()
            ):
                continue
            out.append(el)
        return out

    def find(self, tag: Optional[str] = None, **attr_filters: str) -> Optional["Element"]:
        for el in self.find_all(tag, **attr_filters):
            return el
        return None

    # -- selectors ----------------------------------------------------------

    def select(self, selector: str) -> List["Element"]:
        return _select(self, selector)

    def select_one(self, selector: str) -> Optional["Element"]:
        results = _select(self, selector)
        return results[0] if results else None

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<Element {self.tag} attrs={self.attrs} children={len(self.children)}>"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class _DOMBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("[document]")
        self._stack: List[Element] = [self.root]

    def handle_starttag(self, tag: str, attrs: list) -> None:
        el = Element(tag, dict(attrs))
        el.parent = self._stack[-1]
        self._stack[-1].children.append(el)
        if tag.lower() not in _VOID_ELEMENTS:
            self._stack.append(el)

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        el = Element(tag, dict(attrs))
        el.parent = self._stack[-1]
        self._stack[-1].children.append(el)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag.lower():
                del self._stack[i:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self._stack[-1].children.append(data)


def parse_html(text: str) -> Element:
    """Parse an HTML document and return the root :class:`Element`."""
    builder = _DOMBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


# ---------------------------------------------------------------------------
# CSS-light selector engine
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\s+")


def _matches(el: Element, simple: str) -> bool:
    """Match a single compound selector (no combinators)."""
    if not simple or simple == "*":
        return True
    pos = 0
    n = len(simple)
    tag = ""
    while pos < n and simple[pos] not in ".#[":
        tag += simple[pos]
        pos += 1
    if tag and el.tag != tag.lower():
        return False
    while pos < n:
        ch = simple[pos]
        if ch == ".":
            pos += 1
            start = pos
            while pos < n and simple[pos] not in ".#[":
                pos += 1
            cls = simple[start:pos]
            classes = (el.attrs.get("class") or "").split()
            if cls not in classes:
                return False
        elif ch == "#":
            pos += 1
            start = pos
            while pos < n and simple[pos] not in ".#[":
                pos += 1
            ident = simple[start:pos]
            if (el.attrs.get("id") or "") != ident:
                return False
        elif ch == "[":
            end = simple.find("]", pos)
            if end == -1:
                return False
            attr_expr = simple[pos + 1 : end]
            pos = end + 1
            if "=" in attr_expr:
                k, _, v = attr_expr.partition("=")
                v = v.strip("\"'")
                if (el.attrs.get(k.strip()) or "") != v:
                    return False
            else:
                if attr_expr.strip() not in el.attrs:
                    return False
        else:
            pos += 1
    return True


def _select(root: Element, selector: str) -> List[Element]:
    parts = [p for p in _TOKEN_RE.split(selector.strip()) if p]
    if not parts:
        return []
    current: List[Element] = [root]
    for compound in parts:
        next_level: List[Element] = []
        for parent in current:
            for desc in parent.iter_descendants():
                if _matches(desc, compound):
                    next_level.append(desc)
        current = next_level
    return current


# Backwards-compatible aliases
def BeautifulSoup(text: str, _features: str = "html.parser") -> Element:  # noqa: N802
    """Compatibility shim — drop-in for ``BeautifulSoup(text, 'html.parser')``."""
    return parse_html(text)


__all__ = [
    "BeautifulSoup",
    "Element",
    "parse_html",
]
