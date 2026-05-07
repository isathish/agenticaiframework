"""Pure-Python list-based linear algebra helpers.

Replaces the framework's only hard ``numpy`` dependency. All operations work
on plain Python ``list[float]`` (1-D) or ``list[list[float]]`` (2-D) and
return the same plain-list types — no array wrappers or dtypes.

Intentionally minimal: only the operations actually used elsewhere in the
codebase (cosine, dot, norm, mean, mat_vec, transpose, top-k).
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

Vector = Sequence[float]
Matrix = Sequence[Sequence[float]]


def dot(a: Vector, b: Vector) -> float:
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    return float(sum(x * y for x, y in zip(a, b)))


def norm(a: Vector) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in a))


def cosine(a: Vector, b: Vector) -> float:
    na = norm(a)
    nb = norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot(a, b) / (na * nb)


def euclidean(a: Vector, b: Vector) -> float:
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def mean(a: Vector) -> float:
    if not a:
        return 0.0
    return float(sum(a) / len(a))


def add(a: Vector, b: Vector) -> List[float]:
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    return [float(x) + float(y) for x, y in zip(a, b)]


def sub(a: Vector, b: Vector) -> List[float]:
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    return [float(x) - float(y) for x, y in zip(a, b)]


def scale(a: Vector, k: float) -> List[float]:
    return [float(x) * k for x in a]


def normalize(a: Vector) -> List[float]:
    n = norm(a)
    if n == 0.0:
        return [0.0 for _ in a]
    return [float(x) / n for x in a]


def mat_vec(m: Matrix, v: Vector) -> List[float]:
    return [dot(row, v) for row in m]


def transpose(m: Matrix) -> List[List[float]]:
    if not m:
        return []
    return [list(col) for col in zip(*m)]


def argmax(values: Iterable[float]) -> int:
    best_i = -1
    best_v = -math.inf
    for i, v in enumerate(values):
        if v > best_v:
            best_v = v
            best_i = i
    return best_i


def topk(values: Sequence[float], k: int) -> List[Tuple[int, float]]:
    """Return the (index, value) pairs for the ``k`` largest values."""
    if k <= 0:
        return []
    indexed = list(enumerate(values))
    indexed.sort(key=lambda x: x[1], reverse=True)
    return indexed[:k]


def zeros(n: int) -> List[float]:
    return [0.0] * n


def ones(n: int) -> List[float]:
    return [1.0] * n


def vector_mean(vectors: Sequence[Vector]) -> List[float]:
    if not vectors:
        return []
    n = len(vectors)
    d = len(vectors[0])
    out = [0.0] * d
    for v in vectors:
        for i in range(d):
            out[i] += float(v[i])
    return [x / n for x in out]


__all__ = [
    "Matrix",
    "Vector",
    "add",
    "argmax",
    "cosine",
    "dot",
    "euclidean",
    "mat_vec",
    "mean",
    "norm",
    "normalize",
    "ones",
    "scale",
    "sub",
    "topk",
    "transpose",
    "vector_mean",
    "zeros",
]
