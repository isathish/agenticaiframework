"""Stdlib-only YAML 1.2 *subset* parser/emitter.

Supports the constructs actually used by the framework's config files:

- Block-style mappings ``key: value``
- Block-style sequences ``- item``
- Flow-style mappings ``{a: 1, b: 2}`` and sequences ``[1, 2, 3]``
- Strings (plain, ``"..."``, ``'...'``), integers, floats, ``true``/``false``,
  ``null``/``~``, ISO dates as strings.
- ``#`` line comments
- Multi-line block scalars ``|`` (literal) and ``>`` (folded)

Out of scope (raises :class:`YAMLError` if encountered):
anchors / aliases (``&``/``*``), tags (``!!``), merge keys (``<<``),
multi-document streams (``---`` / ``...``).
"""

from __future__ import annotations

import re
from typing import Any, List, Tuple


class YAMLError(ValueError):
    """Raised when the YAML subset parser encounters unsupported syntax."""


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_FLOAT_RE = re.compile(r"^[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?$")
_INT_RE = re.compile(r"^[-+]?\d+$")
_HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$")


def _coerce_scalar(token: str) -> Any:
    s = token.strip()
    if not s:
        return ""
    if s in ("null", "Null", "NULL", "~"):
        return None
    if s in ("true", "True", "TRUE", "yes", "Yes", "on", "On"):
        return True
    if s in ("false", "False", "FALSE", "no", "No", "off", "Off"):
        return False
    if (s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'"):
        # Strip surrounding quotes and decode common escapes
        inner = s[1:-1]
        if s[0] == '"':
            inner = (
                inner.replace('\\"', '"')
                .replace("\\\\", "\\")
                .replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace("\\r", "\r")
            )
        return inner
    if _INT_RE.match(s):
        return int(s)
    if _HEX_RE.match(s):
        return int(s, 16)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


def _strip_comment(line: str) -> str:
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i].rstrip()
    return line.rstrip()


def _parse_flow(text: str) -> Any:
    """Parse a flow-style scalar/sequence/mapping (e.g. ``[1, 2]``, ``{a: 1}``)."""
    text = text.strip()
    if not text:
        return ""
    if text[0] == "[":
        return _parse_flow_seq(text)
    if text[0] == "{":
        return _parse_flow_map(text)
    return _coerce_scalar(text)


def _split_flow(body: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    in_s = in_d = False
    cur: List[str] = []
    for ch in body:
        if ch == "'" and not in_d:
            in_s = not in_s
            cur.append(ch)
        elif ch == '"' and not in_s:
            in_d = not in_d
            cur.append(ch)
        elif not in_s and not in_d and ch in "[{":
            depth += 1
            cur.append(ch)
        elif not in_s and not in_d and ch in "]}":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0 and not in_s and not in_d:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return [p for p in parts if p]


def _parse_flow_seq(text: str) -> List[Any]:
    if not (text.startswith("[") and text.endswith("]")):
        raise YAMLError(f"Bad flow sequence: {text}")
    return [_parse_flow(p) for p in _split_flow(text[1:-1])]


def _parse_flow_map(text: str) -> dict[str, Any]:
    if not (text.startswith("{") and text.endswith("}")):
        raise YAMLError(f"Bad flow mapping: {text}")
    out: dict[str, Any] = {}
    for entry in _split_flow(text[1:-1]):
        if ":" not in entry:
            raise YAMLError(f"Flow mapping entry missing ':' -> {entry}")
        key, _, value = entry.partition(":")
        out[_coerce_scalar(key.strip()) if not (key.strip().startswith(("\"", "'"))) else _coerce_scalar(key.strip())] = _parse_flow(value)
    return out


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_block(lines: List[str], idx: int, indent: int) -> Tuple[Any, int]:
    """Parse a block starting at ``lines[idx]`` whose own indent is ``indent``.

    Returns the parsed value and the index of the first unconsumed line.
    """
    if idx >= len(lines):
        return None, idx

    first = lines[idx]
    stripped = first.lstrip(" ")
    if stripped.startswith("- "):
        # block sequence
        seq: List[Any] = []
        while idx < len(lines):
            line = lines[idx]
            if not line.strip():
                idx += 1
                continue
            li = _indent_of(line)
            if li < indent:
                break
            if li > indent:
                # belongs to previous item
                idx += 1
                continue
            s = line.lstrip(" ")
            if not s.startswith("-"):
                break
            after = s[1:].lstrip(" ")
            if not after:
                # nested block on next line
                value, idx = _parse_block(lines, idx + 1, indent + 2)
                seq.append(value)
                continue
            if after.startswith("[") or after.startswith("{"):
                seq.append(_parse_flow(after))
                idx += 1
                continue
            if ":" in after and not after.startswith(("\"", "'")):
                # Inline mapping starts on this dash:  - key: val
                key_part, _, value_part = after.partition(":")
                key = _coerce_scalar(key_part.strip())
                if value_part.strip() == "":
                    # nested block mapping
                    sub_map: dict[Any, Any] = {}
                    next_idx = idx + 1
                    new_indent = indent + 2
                    sub_value, next_idx = _parse_block(lines, next_idx, new_indent)
                    if isinstance(sub_value, dict):
                        sub_map = {key: None, **sub_value}
                        sub_map[key] = sub_value.pop(key, None) if False else None
                        sub_map = {key: sub_value if not sub_value else sub_value, **{}}
                        # simpler: treat nested as the value of `key`
                        sub_map = {key: sub_value}
                    else:
                        sub_map = {key: sub_value}
                    seq.append(sub_map)
                    idx = next_idx
                    continue
                # Possibly a series of inline keys; parse as a one-line mapping
                m: dict[Any, Any] = {key: _parse_flow(value_part)}
                # Look ahead for further keys at indent + 2
                idx += 1
                deeper = indent + 2
                while idx < len(lines):
                    lookahead = lines[idx]
                    if not lookahead.strip():
                        idx += 1
                        continue
                    li2 = _indent_of(lookahead)
                    if li2 < deeper:
                        break
                    s2 = lookahead.lstrip(" ")
                    if s2.startswith("-"):
                        break
                    if ":" in s2:
                        k2, _, v2 = s2.partition(":")
                        if v2.strip() == "":
                            sub_value, idx = _parse_block(lines, idx + 1, deeper + 2)
                            m[_coerce_scalar(k2.strip())] = sub_value
                        else:
                            m[_coerce_scalar(k2.strip())] = _parse_flow(v2)
                            idx += 1
                    else:
                        break
                seq.append(m)
                continue
            seq.append(_coerce_scalar(after))
            idx += 1
        return seq, idx

    # block mapping
    mapping: dict[Any, Any] = {}
    while idx < len(lines):
        line = lines[idx]
        if not line.strip():
            idx += 1
            continue
        li = _indent_of(line)
        if li < indent:
            break
        if li > indent:
            idx += 1
            continue
        s = line.lstrip(" ")
        if s.startswith("- "):
            # parent expected mapping but found sequence — return empty dict
            break
        if ":" not in s:
            raise YAMLError(f"Expected key:value, got: {s!r}")
        key_part, _, value_part = s.partition(":")
        key = _coerce_scalar(key_part.strip())
        rest = value_part.strip()
        if rest in ("|", ">"):
            literal = rest == "|"
            block_lines: List[str] = []
            idx += 1
            block_indent = None
            while idx < len(lines):
                ln = lines[idx]
                if not ln.strip():
                    block_lines.append("")
                    idx += 1
                    continue
                li2 = _indent_of(ln)
                if block_indent is None:
                    block_indent = li2
                if li2 < (block_indent or 0):
                    break
                block_lines.append(ln[block_indent or 0 :])
                idx += 1
            if literal:
                mapping[key] = "\n".join(block_lines).rstrip("\n") + ("\n" if block_lines else "")
            else:
                mapping[key] = " ".join(b.strip() for b in block_lines if b.strip())
            continue
        if not rest:
            value, idx = _parse_block(lines, idx + 1, indent + 2)
            mapping[key] = value if value is not None else {}
            continue
        if rest.startswith(("[", "{")):
            mapping[key] = _parse_flow(rest)
            idx += 1
            continue
        mapping[key] = _coerce_scalar(rest)
        idx += 1
    return mapping, idx


def safe_load(text: str) -> Any:
    """Parse a YAML subset document and return Python objects."""
    if text is None:
        return None
    if not text.strip():
        return None
    if "---" in text.split("\n", 1)[0] and text.lstrip().startswith("---"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    raw_lines = [_strip_comment(ln) for ln in text.splitlines()]
    # trim trailing blank lines
    while raw_lines and not raw_lines[-1].strip():
        raw_lines.pop()
    if not raw_lines:
        return None
    # First non-blank line determines whether top-level is sequence or mapping.
    base_indent = 0
    for ln in raw_lines:
        if ln.strip():
            base_indent = _indent_of(ln)
            break
    value, _ = _parse_block(raw_lines, 0, base_indent)
    return value


# ---------------------------------------------------------------------------
# Dumper
# ---------------------------------------------------------------------------

def _dump_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        if v == "" or any(c in v for c in [":", "#", "\n", '"', "'", "{", "}", "[", "]"]) or v.strip() != v:
            escaped = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
            return f'"{escaped}"'
        return v
    return str(v)


def _dump(value: Any, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(value, dict):
        if not value:
            return pad + "{}"
        out: List[str] = []
        for k, v in value.items():
            key = _dump_scalar(k)
            if isinstance(v, (dict, list)) and v:
                out.append(f"{pad}{key}:")
                out.append(_dump(v, indent + 2))
            else:
                out.append(f"{pad}{key}: {_dump_scalar(v) if not isinstance(v, (dict, list)) else '{}' if isinstance(v, dict) else '[]'}")
        return "\n".join(out)
    if isinstance(value, list):
        if not value:
            return pad + "[]"
        out = []
        for item in value:
            if isinstance(item, (dict, list)) and item:
                out.append(f"{pad}-")
                out.append(_dump(item, indent + 2))
            else:
                out.append(f"{pad}- {_dump_scalar(item)}")
        return "\n".join(out)
    return pad + _dump_scalar(value)


def dump(data: Any) -> str:
    """Serialize ``data`` into a YAML subset string."""
    return _dump(data, 0) + "\n"


# Aliases compatible with PyYAML
load = safe_load
safe_dump = dump


__all__ = [
    "YAMLError",
    "dump",
    "load",
    "safe_dump",
    "safe_load",
]
