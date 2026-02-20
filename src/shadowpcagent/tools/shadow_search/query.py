from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Sequence

from .index import DEFAULT_DB_PATH


def search_sqlite(
    term: str,
    limit: int = 50,
    db_path: str | Path | None = None,
) -> list[dict]:
    """
    Simple path search (case-insensitive) over the SQLite index.
    Returns: [{"path": "..."}]
    """
    if not term:
        return []

    dbp = Path(db_path) if db_path else Path(DEFAULT_DB_PATH)
    if not dbp.exists():
        return []

    conn = sqlite3.connect(str(dbp))
    try:
        like = f"%{term}%"
        rows = conn.execute(
            "SELECT path FROM files WHERE path LIKE ? COLLATE NOCASE ORDER BY mtime DESC LIMIT ?;",
            (like, int(limit)),
        ).fetchall()
        return [{"path": r[0]} for r in rows]
    finally:
        conn.close()
