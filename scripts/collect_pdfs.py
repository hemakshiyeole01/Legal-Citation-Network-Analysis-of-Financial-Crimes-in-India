"""Copy only the judgments used in this project into a small folder.

The full Kaggle download is ~6.9 GB. The query interface only needs the ~4,200
judgments that appear in the five domain corpora, so this script copies just those
PDFs into data/final/pdfs/ (which the API checks before the raw folder). Share that
folder (or a zip of it) instead of the whole dataset.

Usage, from the repository root, on the machine that has the raw data:
    python scripts/collect_pdfs.py                      # default folders
    python scripts/collect_pdfs.py --dry-run            # report only, copy nothing
    python scripts/collect_pdfs.py --raw D:/data/sc_judgments --dest data/final/pdfs
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import PROJECT_ROOT, Settings  # noqa: E402
from src.utils.domains import COMBINED  # noqa: E402
from src.utils.pdf_store import PdfStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", type=Path, default=PROJECT_ROOT / "data" / "raw" / "sc_judgments",
                        help="folder with the raw judgment PDFs (searched recursively)")
    parser.add_argument("--dest", type=Path, default=PROJECT_ROOT / "data" / "final" / "pdfs")
    parser.add_argument("--node-metrics", type=Path, default=Settings.from_env().node_metrics_path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.raw.is_dir():
        print(f"Raw PDF folder not found: {args.raw}", file=sys.stderr)
        return 1
    nodes = pd.read_csv(args.node_metrics, usecols=["domain", "file_name"])
    wanted = sorted(set(nodes.loc[nodes["domain"] == COMBINED.name, "file_name"]))
    print(f"{len(wanted)} judgments needed; scanning {args.raw} for PDFs (this can take a minute) ...")
    store = PdfStore([args.raw], progress=print)
    print(f"{len(store)} PDFs found in the raw folder")

    missing, copied, skipped = [], 0, 0
    for name in wanted:
        source = store.find(name)
        if source is None:
            missing.append(name)
            continue
        target = args.dest / source.name
        if target.exists():
            skipped += 1
            continue
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        copied += 1

    verb = "would copy" if args.dry_run else "copied"
    print(f"{verb} {copied}, already present {skipped}, missing {len(missing)}")
    if missing:
        report = args.dest.parent / "pdfs_missing.txt"
        if not args.dry_run:
            report.write_text("\n".join(missing), encoding="utf-8")
            print(f"List of missing files written to {report}")
        print("First few missing:", *missing[:5], sep="\n  ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
