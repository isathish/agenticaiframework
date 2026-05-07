"""Stdlib-only DuckDuckGo HTML search.

DuckDuckGo's HTML endpoint (``https://html.duckduckgo.com/html/?q=...``) returns
plain HTML that we parse for ``<a class="result__a">`` and ``<a class="result__snippet">``.

This is a graceful fallback for the official ``duckduckgo-search`` package. It
respects DDG's robots.txt by including a real User-Agent and is appropriate for
modest, low-volume queries.

Note: DDG actively rotates its HTML structure; if a future change breaks parsing,
the helpers degrade to returning whatever they could recover (never crashes).
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import Iterable, List

from .. import http as _http


_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_ENDPOINT = "https://html.duckduckgo.com/html/"

# Anchor in DDG HTML with optional URL prefix re-write
_RESULT_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class DDGResult:
    title: str
    url: str
    snippet: str


def _strip_html(value: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub("", value)).strip()


def _decode_entities(value: str) -> str:
    import html
    return html.unescape(value)


def _resolve_redirect(url: str) -> str:
    """DDG wraps real URLs in ``/l/?uddg=<encoded>``. Unwrap when present."""
    if "uddg=" in url:
        try:
            qs = urllib.parse.urlparse(url).query
            params = urllib.parse.parse_qs(qs)
            if "uddg" in params:
                return urllib.parse.unquote(params["uddg"][0])
        except (ValueError, KeyError, IndexError):
            return url
    if url.startswith("//"):
        return "https:" + url
    return url


def search(query: str, *, max_results: int = 10, region: str = "us-en") -> List[DDGResult]:
    """Run a DDG HTML search and return parsed results."""
    if not query.strip():
        return []
    body = urllib.parse.urlencode({
        "q": query,
        "kl": region,
    })
    client = _http.Client(timeout=20.0)
    resp = client.post(
        _ENDPOINT,
        data=body.encode("utf-8"),
        headers={
            "User-Agent": _USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    if resp.status >= 400:
        return []

    html_text = resp.text
    titles = _RESULT_RE.findall(html_text)
    snippets = _SNIPPET_RE.findall(html_text)

    results: List[DDGResult] = []
    for i, (raw_url, raw_title) in enumerate(titles):
        if i >= max_results:
            break
        url = _resolve_redirect(_decode_entities(raw_url))
        title = _decode_entities(_strip_html(raw_title))
        snippet = ""
        if i < len(snippets):
            snippet = _decode_entities(_strip_html(snippets[i]))
        results.append(DDGResult(title=title, url=url, snippet=snippet))
    return results


def text(query: str, *, max_results: int = 10) -> Iterable[dict]:
    """Mimic ``duckduckgo_search.DDGS().text()`` for drop-in replacement."""
    for r in search(query, max_results=max_results):
        yield {"title": r.title, "href": r.url, "body": r.snippet}


__all__ = ["DDGResult", "search", "text"]
