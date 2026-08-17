"""
Stage: extraction/pdf_extraction (utility)
Combines all per-year CSVs from data/extracted/ into one master file
in data/processed/, ready for the preprocessing stage.

Run:
    python extraction/pdf_extraction/combine_years.py
"""

import sys
import os
import glob

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
from config.paths import DATA_EXTRACTED, DATA_PROCESSED


def main():
    csv_files = glob.glob(os.path.join(DATA_EXTRACTED, "judgments_*.csv"))
    print(f"Found {len(csv_files)} year files to combine")

    dfs = [pd.read_csv(f) for f in csv_files]
    combined = pd.concat(dfs, ignore_index=True)

    output_path = os.path.join(DATA_PROCESSED, "all_judgments_raw_text.csv")
    combined.to_csv(output_path, index=False)

    print(f"Combined {len(combined)} total judgments -> {output_path}")
    print(f"Empty/failed extractions: {(combined['char_count'] == 0).sum()}")


if __name__ == "__main__":
    main()
