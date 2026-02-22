from __future__ import annotations

import fnmatch
import os
import sqlite3
import time
from pathlib import Path
from typing import Iterable, Sequence

# repo_root = ...\ShadowPCAgent (because this file lives at src/shadowpcagent/tools/shadow_search/index.py)
REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "shadow_search.sqlite"

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

DEFAULT_IGNORE_GLOBS = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.dll",
    "*.exe",
    "*.bin",
    "*.zip",
    "*.7z",
    "*.rar",
    "*.mp4",
    "*.mkv",
    "*.mov",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.webp",
]


def _norm_roots(roots: Sequence[str | os.PathLike]) -> list[Path]:
    out: list[Path] = []
    for r in roots:
        p = Path(r).expanduser()
        try:
            p = p.resolve()
        except Exception:
            p = p.absolute()
        out.append(p)
    return out


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            mtime INTEGER NOT NULL,
            size INTEGER NOT NULL
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime);")


def _is_ignored_name(name: str, ignore_dirnames: set[str]) -> bool:
    return name in ignore_dirnames


def _is_ignored_file(path: Path, ignore_globs: Sequence[str]) -> bool:
    n = path.name
    for pat in ignore_globs:
        if fnmatch.fnmatch(n, pat):
            return True
    return False


def build_sqlite_index(
    roots: Sequence[str | os.PathLike],
    db_path: str | os.PathLike | None = None,
    *,
    reset: bool = True,
    ignore_dirnames: set[str] | None = None,
    ignore_globs: Sequence[str] | None = None,
    follow_symlinks: bool = False,
    batch_size: int = 2000,
) -> dict:
    """
    Build a simple SQLite index of file paths under the provided roots.

    - Stores: absolute path, mtime (unix), size
    - Default DB: <repo>/data/shadow_search.sqlite
    - Default: reset=True (wipe and rebuild)
    """
    t0 = time.time()

    roots_n = _norm_roots(roots)
    if not roots_n:
        raise ValueError("roots must not be empty")

    ignore_dirnames = ignore_dirnames or set(DEFAULT_IGNORE_DIRS)
    ignore_globs = ignore_globs or list(DEFAULT_IGNORE_GLOBS)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dbp = Path(db_path) if db_path else DEFAULT_DB_PATH
    dbp = Path(dbp).expanduser()
    dbp.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(dbp))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        _ensure_schema(conn)

        if reset:
            conn.execute("DELETE FROM files;")
            conn.commit()

        to_insert: list[tuple[str, int, int]] = []
        count = 0

        for root in roots_n:
            if not root.exists():
                continue

            # If root is a file, just index it
            if root.is_file():
                try:
                    st = root.stat()
                    to_insert.append((str(root), int(st.st_mtime), int(st.st_size)))
                    count += 1
                except Exception:
                    pass
            else:
                for dirpath, dirnames, filenames in os.walk(str(root), topdown=True, followlinks=follow_symlinks):
                    # prune ignored dirs in-place
                    dirnames[:] = [d for d in dirnames if not _is_ignored_name(d, ignore_dirnames)]

                    for fn in filenames:
                        try:
                            fp = Path(dirpath) / fn
                            if _is_ignored_file(fp, ignore_globs):
                                continue
                            st = fp.stat()
                            to_insert.append((str(fp), int(st.st_mtime), int(st.st_size)))
                            count += 1

                            if len(to_insert) >= batch_size:
                                conn.executemany(
                                    "INSERT OR REPLACE INTO files(path, mtime, size) VALUES (?, ?, ?);",
                                    to_insert,
                                )
                                conn.commit()
                                to_insert.clear()
                        except KeyboardInterrupt:
                            raise
                        except Exception:
                            continue

        if to_insert:
            conn.executemany(
                "INSERT OR REPLACE INTO files(path, mtime, size) VALUES (?, ?, ?);",
                to_insert,
            )
            conn.commit()

        return {
            "db_path": str(dbp),
            "roots": [str(r) for r in roots_n],
            "files_indexed": count,
            "seconds": round(time.time() - t0, 3),
            "reset": reset,
        }
    finally:
        conn.close()
