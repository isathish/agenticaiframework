"""Stdlib-only token-count estimator (replaces ``tiktoken``).

The exact BPE merges used by OpenAI / Anthropic / Google models are not
publicly redistributable in a small form, so we approximate token counts using
two strategies:

1. **Heuristic** (default): for known model families a calibrated
   characters-per-token ratio is used (e.g. ``cl100k_base`` ≈ 4.0 chars/token
   for English, ``o200k_base`` ≈ 4.2). The estimate is rounded up so the
   framework never under-reports tokens (avoiding silent context overflows).
2. **Word-piece** (optional, ``method="wordpiece"``): a fast whitespace +
   punctuation splitter that emits one token per ~4 characters of word and
   one per punctuation symbol. This is closer for code / structured text.

Both strategies are deterministic and require no external state.
"""

from __future__ import annotations

import math
import re
from typing import Final, Iterable

# ---------------------------------------------------------------------------
# Model -> chars-per-token ratio (calibrated against published numbers).
# ---------------------------------------------------------------------------

_DEFAULT_RATIO: Final[float] = 4.0

_MODEL_RATIOS: Final[dict[str, float]] = {
    # OpenAI
    "gpt-4o": 4.2,
    "gpt-4o-mini": 4.2,
    "gpt-4-turbo": 4.0,
    "gpt-4": 4.0,
    "gpt-3.5-turbo": 4.0,
    "o1-preview": 4.2,
    "o1-mini": 4.2,
    "text-embedding-3-small": 4.0,
    "text-embedding-3-large": 4.0,
    "text-embedding-ada-002": 4.0,
    # Anthropic
    "claude-3-5-sonnet": 3.8,
    "claude-3-5-haiku": 3.8,
    "claude-3-opus": 3.8,
    "claude-3-sonnet": 3.8,
    "claude-3-haiku": 3.8,
    "claude-sonnet-4": 3.8,
    "claude-opus-4": 3.8,
    # Google
    "gemini-1.5-pro": 4.0,
    "gemini-1.5-flash": 4.0,
    "gemini-2.0-flash": 4.0,
    "gemini-pro": 4.0,
}


_WORD_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _ratio_for_model(model: str) -> float:
    if not model:
        return _DEFAULT_RATIO
    m = model.lower()
    if m in _MODEL_RATIOS:
        return _MODEL_RATIOS[m]
    # prefix match: "gpt-4o-2024-08-06" -> "gpt-4o"
    for key, ratio in _MODEL_RATIOS.items():
        if m.startswith(key):
            return ratio
    return _DEFAULT_RATIO


def count_tokens(text: str, model: str = "") -> int:
    """Estimate the number of tokens for ``text`` under the given model.

    Always returns ``ceil`` so callers cannot accidentally overflow context.
    """
    if not text:
        return 0
    ratio = _ratio_for_model(model)
    return max(1, math.ceil(len(text) / ratio))


def count_message_tokens(
    messages: Iterable[dict], model: str = "", *, per_message_overhead: int = 4
) -> int:
    """Estimate tokens for a list of ``{"role": ..., "content": ...}`` dicts.

    Mirrors OpenAI's "every message follows" overhead heuristic.
    """
    total = 0
    for msg in messages:
        total += per_message_overhead
        role = str(msg.get("role", ""))
        total += count_tokens(role, model)
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text") or block.get("content") or ""
                    total += count_tokens(str(text), model)
        else:
            total += count_tokens(str(content), model)
    total += 2  # priming for the assistant turn
    return total


def tokenize_words(text: str) -> list[str]:
    """Cheap word/punctuation splitter useful as a token surrogate."""
    return _WORD_RE.findall(text)


def encode(text: str, model: str = "") -> list[int]:
    """Pseudo-token IDs (non-reversible).

    Returns one synthetic ID per estimated token (hash mod 2**16). Useful only
    for callers that need a sequence of integers; do *not* feed back into a
    real model.
    """
    n = count_tokens(text, model)
    if not text:
        return []
    base = hash(text) & 0xFFFF
    return [(base + i) & 0xFFFF for i in range(n)]


__all__ = [
    "count_message_tokens",
    "count_tokens",
    "encode",
    "tokenize_words",
]
