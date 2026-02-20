from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from shadowpcagent.tools.shadow_search.index import build_sqlite_index, DEFAULT_DB_PATH
from shadowpcagent.tools.shadow_search.query import search_sqlite


def _cmd_search_index(args: argparse.Namespace) -> int:
    roots = [Path(r) for r in args.roots]
    db_path = Path(args.db_path) if args.db_path else None

    result = build_sqlite_index(
        roots=roots,
        db_path=db_path,
        reset=bool(args.reset),
        ignore_dirnames=args.ignore_dirname,
        ignore_globs=args.ignore_glob,
        follow_symlinks=bool(args.follow_symlinks),
        batch_size=int(args.batch_size),
    )

    files_indexed = int(result.get("files_indexed", 0))
    seconds = float(result.get("seconds", 0.0))
    out_db = result.get("db_path")
    print(f"OK: indexed {files_indexed} files in {seconds:.2f}s -> {out_db}")
    return 0


def _cmd_search_query(args: argparse.Namespace) -> int:
    db_path = Path(args.db_path) if args.db_path else None

    results = search_sqlite(
        term=str(args.term),
        limit=int(args.limit),
        db_path=db_path,
    )

    for r in results:
        if isinstance(r, dict) and "path" in r:
            print(r["path"])
        else:
            print(str(r))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shadowpcagent")
    sub = p.add_subparsers(dest="command", required=True)

    # shadowpcagent search ...
    group = sub.add_parser("search", help="Local file/path search tools")
    subs = group.add_subparsers(dest="search_cmd", required=True)

    # shadowpcagent search index ...
    idx = subs.add_parser("index", help="Build the sqlite path index")
    idx.add_argument("--roots", nargs="+", required=True, help="Root paths to index (e.g. . or C:\\Dev\\agent)")
    idx.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Path to sqlite db file")
    idx.add_argument("--reset", action="store_true", help="Wipe & rebuild index")
    idx.add_argument("--ignore-dirname", action="append", default=None, help="Ignore directory name (repeatable)")
    idx.add_argument("--ignore-glob", action="append", default=None, help="Ignore glob (repeatable)")
    idx.add_argument("--follow-symlinks", action="store_true", help="Follow symlinks while indexing")
    idx.add_argument("--batch-size", type=int, default=2000, help="SQLite insert batch size")
    idx.set_defaults(func=_cmd_search_index)

    # shadowpcagent search query ...
    qry = subs.add_parser("query", help="Query the sqlite path index")
    qry.add_argument("--term", required=True, help="Search term (substring match)")
    qry.add_argument("--limit", type=int, default=50, help="Max results")
    qry.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Path to sqlite db file")
    qry.set_defaults(func=_cmd_search_query)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else None)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
