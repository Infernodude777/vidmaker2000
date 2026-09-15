"""Persistent media library index.

Uses sqlite3 (stdlib) so a large library can be searched without loading every
row into memory. If the database cannot be opened, an in-memory list keeps the
API working, so the editor never dies because of a bad path.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
    path TEXT PRIMARY KEY,
    name TEXT,
    kind TEXT,
    duration REAL,
    fps REAL,
    width INTEGER,
    height INTEGER,
    added REAL,
    tags TEXT
)
"""


class MediaIndex:
    """Searchable media library with an optional on-disk backing store."""

    def __init__(self, db_path=None):
        self.db_path = str(db_path) if db_path else None
        self.rows: list[dict] = []
        self._conn = None
        if self.db_path:
            try:
                self._conn = sqlite3.connect(self.db_path)
                self._conn.execute(SCHEMA)
                self._conn.commit()
            except sqlite3.Error:
                self._conn = None

    # ── write ────────────────────────────────────────────────────────────
    def add(self, path: str, kind: str = "video", duration: float = 0.0,
            fps: float = 30.0, width: int = 0, height: int = 0,
            tags=()) -> dict:
        """Insert or update a media row. Returns the stored row."""
        row = {
            "path": str(path),
            "name": os.path.basename(str(path)),
            "kind": kind,
            "duration": float(duration or 0.0),
            "fps": float(fps or 30.0),
            "width": int(width or 0),
            "height": int(height or 0),
            "added": time.time(),
            "tags": ",".join(str(t) for t in (tags or ())),
        }
        if self._conn is not None:
            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO media "
                    "(path, name, kind, duration, fps, width, height, added, tags) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (row["path"], row["name"], row["kind"], row["duration"],
                     row["fps"], row["width"], row["height"], row["added"],
                     row["tags"]),
                )
                self._conn.commit()
                return row
            except sqlite3.Error:
                self._conn = None
        self.rows = [r for r in self.rows if r.get("path") != row["path"]]
        self.rows.append(row)
        return row

    def remove(self, path: str) -> bool:
        """Delete a row by path."""
        if self._conn is not None:
            try:
                cur = self._conn.execute("DELETE FROM media WHERE path=?", (str(path),))
                self._conn.commit()
                return bool(cur.rowcount)
            except sqlite3.Error:
                self._conn = None
        before = len(self.rows)
        self.rows = [r for r in self.rows if r.get("path") != str(path)]
        return len(self.rows) != before

    # ── read ─────────────────────────────────────────────────────────────
    def all(self) -> list[dict]:
        """Every row, newest first."""
        if self._conn is not None:
            try:
                cur = self._conn.execute(
                    "SELECT path, name, kind, duration, fps, width, height, added, tags "
                    "FROM media ORDER BY added DESC"
                )
                return [self._row(r) for r in cur.fetchall()]
            except sqlite3.Error:
                self._conn = None
        return sorted(self.rows, key=lambda r: r.get("added", 0), reverse=True)

    def search(self, query: str, limit: int = 50) -> list[dict]:
        """Substring search over name/path/tags (case-insensitive)."""
        needle = (query or "").strip().lower()
        if not needle:
            return self.all()[:max(1, int(limit))]
        if self._conn is not None:
            try:
                like = f"%{needle}%"
                cur = self._conn.execute(
                    "SELECT path, name, kind, duration, fps, width, height, added, tags "
                    "FROM media WHERE lower(name) LIKE ? OR lower(path) LIKE ? "
                    "OR lower(tags) LIKE ? ORDER BY added DESC LIMIT ?",
                    (like, like, like, max(1, int(limit))),
                )
                return [self._row(r) for r in cur.fetchall()]
            except sqlite3.Error:
                self._conn = None
        return [r for r in self.all()
                if needle in f"{r.get('name','')} {r.get('path','')} {r.get('tags','')}".lower()][:max(1, int(limit))]

    @staticmethod
    def _row(raw) -> dict:
        keys = ("path", "name", "kind", "duration", "fps", "width", "height", "added", "tags")
        return dict(zip(keys, raw))

    def count(self) -> int:
        if self._conn is not None:
            try:
                cur = self._conn.execute("SELECT COUNT(*) FROM media")
                return int(cur.fetchone()[0])
            except sqlite3.Error:
                self._conn = None
        return len(self.rows)

    def export_json(self) -> str:
        """Whole index as a JSON string (for a project sidecar)."""
        return json.dumps(self.all(), indent=2)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            finally:
                self._conn = None
