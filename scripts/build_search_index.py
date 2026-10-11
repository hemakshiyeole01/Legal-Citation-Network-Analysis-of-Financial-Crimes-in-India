"""Build the full-text search index used by /search?scope=text.

Run from the repository root, after the five *_corpus.csv files are in data/final/:
    python scripts/build_search_index.py

Takes about 10 to 30 seconds and writes a single file (about 280 MB) to
data/index/fulltext.db, which is not committed to Git. Re-run it whenever the corpus
files change. A running API picks up the new file on the next request.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import Settings  # noqa: E402
from src.utils.fulltext import FullTextIndex, build_index  # noqa: E402


def main() -> int:
    defaults = Settings.from_env()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus-dir", type=Path, default=defaults.corpus_dir)
    parser.add_argument("--db", type=Path, default=defaults.fts_db_path)
    args = parser.parse_args()

    started = time.time()
    try:
        count = build_index(args.corpus_dir, args.db, progress=print)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Put the five *_corpus.csv files in that folder, or pass --corpus-dir.", file=sys.stderr)
        return 1
    seconds = time.time() - started
    print(f"Indexed {count} judgments in {seconds:.1f} s -> {args.db} ({args.db.stat().st_size / 1e6:.0f} MB)")

    index = FullTextIndex(args.db)
    hits = index.match("criminal breach of trust")
    print(f"Check: 'criminal breach of trust' matches {len(hits)} judgments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
