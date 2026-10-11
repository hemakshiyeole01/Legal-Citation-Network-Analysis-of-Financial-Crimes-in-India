"""Locate the original judgment PDFs on disk.

The `file_name` values in the corpus / edge CSVs are the PDF file names themselves
(e.g. 'Mrs_Maneka_Gandhi_vs_Union_Of_India_Uoi_And_Anr_on_25_January_1978_1.PDF'),
so the lookup is a case-insensitive file-name match. The user never supplies a path:
the API checks the name against the case index first and then asks this class, which
only returns files it found while scanning the configured folders. That rules out
path traversal.

The scan uses os.walk, which reads each folder listing once and does not ask the
operating system about every file separately. That matters on Windows, where checking
~27,000 files one by one can take minutes.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Iterable

log = logging.getLogger(__name__)


class PdfStore:
    def __init__(self, directories: Iterable[Path], progress: Callable[[str], None] | None = None):
        self.directories = [Path(d) for d in directories]
        self._progress = progress
        self._index: dict[str, Path] = {}
        self._scan()

    def _scan(self) -> None:
        for directory in self.directories:
            if not directory.is_dir():
                continue
            next_report = 5000
            for folder, _subfolders, files in os.walk(directory):
                for name in files:
                    if name[-4:].lower() == ".pdf":
                        # first directory wins, so the small curated folder beats the raw dump
                        self._index.setdefault(name.lower(), Path(folder) / name)
                if self._progress and len(self._index) >= next_report:
                    self._progress(f"  ... {len(self._index)} PDFs found so far")
                    next_report = (len(self._index) // 5000 + 1) * 5000
        log.info("PdfStore indexed %d PDFs", len(self._index))

    def __len__(self) -> int:
        return len(self._index)

    def find(self, file_name: str) -> Path | None:
        return self._index.get(file_name.lower())

    def has(self, file_name: str) -> bool:
        return file_name.lower() in self._index
