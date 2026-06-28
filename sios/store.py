"""SQLite-backed persistent key-value store for Pydantic models.

Replaces in-memory dicts in sios/api/routes.py so findings, PVCs,
transactions and spores survive server restarts.

Usage::

    store = SqliteStore("findings", Finding)
    store.set("abc", finding_obj)          # upsert
    obj = store.get("abc")                 # None if missing
    for obj in store.values(): ...
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Generic, Iterator, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_DB_PATH = os.environ.get("SIOS_DB_PATH", "sios.db")
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(_DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    return con


class SqliteStore(Generic[T]):
    """Thread-safe SQLite-backed store with dict-like API."""

    def __init__(self, table: str, model: Type[T]) -> None:
        self._table = table
        self._model = model
        with _lock, _conn() as con:
            con.execute(
                f"CREATE TABLE IF NOT EXISTS {table} "
                "(id TEXT PRIMARY KEY, data JSON NOT NULL)"
            )

    # ── Write ──────────────────────────────────────────────────────────────

    def set(self, key: str, value: T) -> None:
        with _lock, _conn() as con:
            con.execute(
                f"INSERT OR REPLACE INTO {self._table}(id, data) VALUES (?,?)",
                (key, value.model_dump_json()),
            )

    def __setitem__(self, key: str, value: T) -> None:
        self.set(key, value)

    def delete(self, key: str) -> None:
        with _lock, _conn() as con:
            con.execute(f"DELETE FROM {self._table} WHERE id=?", (key,))

    def clear(self) -> int:
        with _lock, _conn() as con:
            cur = con.execute(f"SELECT COUNT(*) FROM {self._table}")
            n = cur.fetchone()[0]
            con.execute(f"DELETE FROM {self._table}")
        return n

    # ── Read ───────────────────────────────────────────────────────────────

    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        with _lock, _conn() as con:
            cur = con.execute(
                f"SELECT data FROM {self._table} WHERE id=?", (key,)
            )
            row = cur.fetchone()
        if row is None:
            return default
        return self._model.model_validate_json(row[0])

    def __getitem__(self, key: str) -> T:
        obj = self.get(key)
        if obj is None:
            raise KeyError(key)
        return obj

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def values(self) -> List[T]:
        with _lock, _conn() as con:
            cur = con.execute(f"SELECT data FROM {self._table}")
            rows = cur.fetchall()
        return [self._model.model_validate_json(r[0]) for r in rows]

    def items(self) -> List[Tuple[str, T]]:
        with _lock, _conn() as con:
            cur = con.execute(f"SELECT id, data FROM {self._table}")
            rows = cur.fetchall()
        return [(r[0], self._model.model_validate_json(r[1])) for r in rows]

    def __len__(self) -> int:
        with _lock, _conn() as con:
            cur = con.execute(f"SELECT COUNT(*) FROM {self._table}")
            return cur.fetchone()[0]

    # ── JSON field query (idempotency support) ─────────────────────────────

    def find_by_json(self, json_path: str, value: str) -> List[T]:
        """Return all rows where json_extract(data, json_path) = value."""
        with _lock, _conn() as con:
            cur = con.execute(
                f"SELECT data FROM {self._table} "
                f"WHERE json_extract(data, ?) = ?",
                (json_path, value),
            )
            rows = cur.fetchall()
        return [self._model.model_validate_json(r[0]) for r in rows]
