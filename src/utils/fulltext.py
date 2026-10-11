"""Full-text search inside the judgments, using SQLite's built-in FTS5.

The index is built once from the five *_corpus.csv files (scripts/build_search_index.py)
and lives in a single file outside Git (data/index/fulltext.db). The API opens it
read-only, so it can never change the index.

Queries are written the way people type them: every word must appear, and words in
"double quotes" must appear together in that order. Every term is quoted before it
reaches SQLite, so FTS5 operators typed by a user (OR, NEAR, *, :, -) are plain words
and can never cause a syntax error.

Filler words such as "the", "of" or "to" are ignored unless they sit inside a quoted
phrase that also has a real word in it. They occur thousands of times in every judgment,
so searching for them is slow and tells you nothing ("criminal breach of trust" in quotes
still works as an exact phrase). A time limit stops any unexpectedly heavy query.
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from src.utils.domains import DOMAINS

log = logging.getLogger(__name__)

# Private-use control characters that cannot occur in a judgment; SQLite wraps each match
# in them and parse_snippet() turns them into structured parts, so the API never emits HTML.
MARK_OPEN, MARK_CLOSE = "\x02", "\x03"

_PHRASE_RE = re.compile(r'"([^"]*)"')
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)

QUERY_TIME_LIMIT_SECONDS = 5.0

STOPWORDS = frozenset(
    "a an and are as at be been but by for from had has have he her his i if in into is it its of on "
    "or she so than that the their them then there these they this to was we were which who will with "
    "not no".split()
)


class FullTextError(ValueError):
    """The search text has nothing to search for."""


class IndexUnavailable(RuntimeError):
    """The full-text index has not been built (or cannot be read)."""


def to_fts_query(text: str) -> str:
    """Turn what a person typed into a safe FTS5 query (all terms ANDed, filler words ignored)."""
    terms: list[str] = []
    saw_words = False
    for match in _PHRASE_RE.finditer(text):
        words = _WORD_RE.findall(match.group(1))
        saw_words = saw_words or bool(words)
        if any(w.lower() not in STOPWORDS for w in words):
            terms.append('"' + " ".join(words) + '"')
    for word in _WORD_RE.findall(_PHRASE_RE.sub(" ", text)):
        saw_words = True
        if word.lower() not in STOPWORDS:
            terms.append(f'"{word}"')
    if not terms:
        if saw_words:
            raise FullTextError("Those words are too common to search for. Add a more specific word")
        raise FullTextError("Enter at least one word to search for inside the judgments")
    return " AND ".join(terms)


def parse_snippet(raw: str | None) -> list[dict[str, Any]]:
    """'... the [bank] manager ...' (marker characters) -> [{'text': ..., 'match': bool}, ...]."""
    if not raw:
        return []
    raw = re.sub(r"\s+", " ", raw).strip()
    parts: list[dict[str, Any]] = []
    pos = 0
    for m in re.finditer(f"{MARK_OPEN}(.*?){MARK_CLOSE}", raw):
        if m.start() > pos:
            parts.append({"text": raw[pos:m.start()], "match": False})
        parts.append({"text": m.group(1), "match": True})
        pos = m.end()
    if pos < len(raw):
        parts.append({"text": raw[pos:], "match": False})
    return parts


def build_index(corpus_dir: Path, db_path: Path, progress: Callable[[str], None] | None = None) -> int:
    """(Re)build the index from the *_corpus.csv files. Returns the number of judgments indexed.

    A judgment that sits in several domain corpora is indexed once. The new index is written
    to a temporary file and swapped in at the end, so a failed build never damages a working one.
    """
    say = progress or (lambda _msg: None)
    corpus_dir, db_path = Path(corpus_dir), Path(db_path)
    sources = [corpus_dir / f"{d.edge_prefix}_corpus.csv" for d in DOMAINS]
    found = [p for p in sources if p.is_file()]
    if not found:
        raise FileNotFoundError(f"No *_corpus.csv files found in {corpus_dir}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_name(db_path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    try:
        con.execute("CREATE VIRTUAL TABLE judgments USING fts5("
                    "file_name UNINDEXED, text, tokenize='porter unicode61')")
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        seen: set[str] = set()
        for path in found:
            frame = pd.read_csv(path, usecols=["file_name", "text"])
            frame = frame.dropna(subset=["text"]).drop_duplicates("file_name")
            frame = frame[~frame["file_name"].isin(seen)]
            texts = frame["text"].str.replace(f"[{MARK_OPEN}{MARK_CLOSE}]", " ", regex=True)
            con.executemany("INSERT INTO judgments (file_name, text) VALUES (?, ?)",
                            zip(frame["file_name"], texts))
            seen.update(frame["file_name"])
            say(f"{path.name}: {len(frame)} new judgments indexed")
        con.execute("INSERT INTO judgments (judgments) VALUES ('optimize')")
        con.executemany("INSERT INTO meta VALUES (?, ?)", [
            ("built_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
            ("documents", str(len(seen))),
        ])
        con.commit()
    except BaseException:
        con.close()
        tmp.unlink(missing_ok=True)
        raise
    con.close()
    os.replace(tmp, db_path)
    return len(seen)


class FullTextIndex:
    """Read-only handle on the index. A fresh connection is opened per query, which is cheap
    and keeps it safe to use from FastAPI's worker threads."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    @property
    def available(self) -> bool:
        return self.db_path.is_file()

    def _connect(self, time_limit: float | None = None) -> sqlite3.Connection:
        if not self.available:
            raise IndexUnavailable(
                "The full-text index has not been built. Run: python scripts/build_search_index.py")
        con = sqlite3.connect(self.db_path.resolve().as_uri() + "?mode=ro", uri=True)
        if time_limit:
            deadline = time.monotonic() + time_limit
            con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 20000)
        return con

    def info(self) -> dict[str, Any]:
        if not self.available:
            return {"available": False, "documents": None, "built_at": None}
        try:
            with closing(self._connect()) as con:
                meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
            return {"available": True, "documents": int(meta.get("documents", 0)),
                    "built_at": meta.get("built_at")}
        except (sqlite3.Error, IndexUnavailable) as exc:
            log.warning("Full-text index unreadable: %s", exc)
            return {"available": False, "documents": None, "built_at": None}

    def match(self, query: str) -> list[str]:
        """File names of every judgment containing all the terms, best match first."""
        fts = to_fts_query(query)
        try:
            with closing(self._connect(QUERY_TIME_LIMIT_SECONDS)) as con:
                rows = con.execute(
                    "SELECT file_name FROM judgments WHERE judgments MATCH ? ORDER BY rank", (fts,)
                ).fetchall()
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc):
                raise FullTextError("This search is too broad and took too long. "
                                    "Add a more specific word and try again") from exc
            raise IndexUnavailable(f"The full-text index could not be read: {exc}") from exc
        except sqlite3.Error as exc:
            raise IndexUnavailable(f"The full-text index could not be read: {exc}") from exc
        return [r[0] for r in rows]

    def snippets(self, query: str, file_names: list[str], words: int = 24) -> dict[str, list[dict[str, Any]]]:
        """A highlighted extract for each given judgment (only call this for one page of results)."""
        if not file_names:
            return {}
        fts = to_fts_query(query)
        marks = ",".join("?" * len(file_names))
        sql = (f"SELECT file_name, snippet(judgments, 1, '{MARK_OPEN}', '{MARK_CLOSE}', ' … ', {int(words)}) "
               f"FROM judgments WHERE judgments MATCH ? AND file_name IN ({marks})")
        try:
            with closing(self._connect(QUERY_TIME_LIMIT_SECONDS)) as con:
                rows = con.execute(sql, [fts, *file_names]).fetchall()
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc):
                return {}  # show the results without extracts rather than failing the whole search
            raise IndexUnavailable(f"The full-text index could not be read: {exc}") from exc
        except sqlite3.Error as exc:
            raise IndexUnavailable(f"The full-text index could not be read: {exc}") from exc
        return {name: parse_snippet(raw) for name, raw in rows}
