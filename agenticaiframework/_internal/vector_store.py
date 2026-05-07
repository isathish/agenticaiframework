"""Stdlib-only vector store backends.

Provides three brute-force backends — ``memory`` (in-process dict),
``jsonl`` (newline-delimited JSON file) and ``sqlite`` (single-file DB).
All backends share the same API and use ``_internal.array`` for math.

This module is intentionally minimal — it implements correct cosine /
Euclidean / dot-product nearest-neighbour search without external indexes.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import array as _array


@dataclass
class VectorEntry:
    id: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


class _BaseStore:
    metric: str = "cosine"

    def upsert(self, entry: VectorEntry) -> None:
        raise NotImplementedError

    def delete(self, id_: str) -> bool:
        raise NotImplementedError

    def get(self, id_: str) -> Optional[VectorEntry]:
        raise NotImplementedError

    def search(
        self,
        query: Sequence[float],
        top_k: int = 10,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[Tuple[VectorEntry, float]]:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    # -- common ranking ----------------------------------------------

    def _score(self, q: Sequence[float], v: Sequence[float]) -> float:
        if self.metric == "cosine":
            return float(_array.cosine(q, v))
        if self.metric == "dot":
            return float(_array.dot(q, v))
        if self.metric == "euclidean":
            return -float(_array.euclidean(q, v))
        raise ValueError(f"Unknown metric: {self.metric}")


class MemoryVectorStore(_BaseStore):
    def __init__(self, metric: str = "cosine") -> None:
        self.metric = metric
        self._entries: Dict[str, VectorEntry] = {}

    def upsert(self, entry: VectorEntry) -> None:
        self._entries[entry.id] = entry

    def delete(self, id_: str) -> bool:
        return self._entries.pop(id_, None) is not None

    def get(self, id_: str) -> Optional[VectorEntry]:
        return self._entries.get(id_)

    def search(self, query, top_k=10, filter_fn=None):
        scored: List[Tuple[VectorEntry, float]] = []
        for entry in self._entries.values():
            if filter_fn is not None and not filter_fn(entry.metadata):
                continue
            scored.append((entry, self._score(query, entry.vector)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self._entries)


class JSONLVectorStore(MemoryVectorStore):
    def __init__(self, path: str, metric: str = "cosine") -> None:
        super().__init__(metric=metric)
        self.path = path
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    self._entries[obj["id"]] = VectorEntry(
                        id=obj["id"],
                        vector=list(obj["vector"]),
                        metadata=obj.get("metadata", {}),
                    )

    def _flush(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for entry in self._entries.values():
                f.write(json.dumps({
                    "id": entry.id,
                    "vector": list(entry.vector),
                    "metadata": entry.metadata,
                }) + "\n")
        os.replace(tmp, self.path)

    def upsert(self, entry: VectorEntry) -> None:
        super().upsert(entry)
        self._flush()

    def delete(self, id_: str) -> bool:
        ok = super().delete(id_)
        if ok:
            self._flush()
        return ok


class SQLiteVectorStore(_BaseStore):
    def __init__(self, path: str, metric: str = "cosine") -> None:
        self.metric = metric
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS vectors ("
            "id TEXT PRIMARY KEY, vector TEXT NOT NULL, metadata TEXT NOT NULL"
            ")"
        )
        self._conn.commit()

    def upsert(self, entry: VectorEntry) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO vectors (id, vector, metadata) VALUES (?, ?, ?)",
            (entry.id, json.dumps(list(entry.vector)), json.dumps(entry.metadata)),
        )
        self._conn.commit()

    def delete(self, id_: str) -> bool:
        cur = self._conn.execute("DELETE FROM vectors WHERE id = ?", (id_,))
        self._conn.commit()
        return cur.rowcount > 0

    def get(self, id_: str) -> Optional[VectorEntry]:
        row = self._conn.execute(
            "SELECT id, vector, metadata FROM vectors WHERE id = ?", (id_,)
        ).fetchone()
        if row is None:
            return None
        return VectorEntry(id=row[0], vector=json.loads(row[1]), metadata=json.loads(row[2]))

    def search(self, query, top_k=10, filter_fn=None):
        cur = self._conn.execute("SELECT id, vector, metadata FROM vectors")
        scored: List[Tuple[VectorEntry, float]] = []
        for id_, vec_json, meta_json in cur:
            metadata = json.loads(meta_json)
            if filter_fn is not None and not filter_fn(metadata):
                continue
            entry = VectorEntry(id=id_, vector=json.loads(vec_json), metadata=metadata)
            scored.append((entry, self._score(query, entry.vector)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0])

    def close(self) -> None:
        self._conn.close()


def create_store(backend: str = "memory", *, path: Optional[str] = None,
                 metric: str = "cosine") -> _BaseStore:
    backend = backend.lower()
    if backend == "memory":
        return MemoryVectorStore(metric=metric)
    if backend == "jsonl":
        if not path:
            raise ValueError("jsonl backend requires 'path'")
        return JSONLVectorStore(path=path, metric=metric)
    if backend == "sqlite":
        if not path:
            raise ValueError("sqlite backend requires 'path'")
        return SQLiteVectorStore(path=path, metric=metric)
    raise ValueError(f"Unknown vector-store backend: {backend}")


__all__ = [
    "VectorEntry",
    "MemoryVectorStore",
    "JSONLVectorStore",
    "SQLiteVectorStore",
    "create_store",
]
