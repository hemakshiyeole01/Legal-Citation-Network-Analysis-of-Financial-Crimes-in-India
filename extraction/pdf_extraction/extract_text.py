"""
Stage: extraction/pdf_extraction
Extracts raw text from every PDF judgment. Output goes to data/extracted/
(one CSV per year, so a crash doesn't lose everything, and re-runs skip
years that are already done).

Run:
    python extraction/pdf_extraction/extract_text.py
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import pdfplumber
import pandas as pd
from tqdm import tqdm

from config.paths import DATA_RAW, DATA_EXTRACTED


def get_dataset_path() -> str:
    pointer_file = os.path.join(DATA_RAW, "dataset_path.txt")
    if not os.path.exists(pointer_file):
        raise FileNotFoundError(
            "Dataset path not found. Run extraction/download/download_dataset.py first."
        )
    with open(pointer_file) as f:
        return f.read().strip()


def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception:
        return ""
    return text


def process_year(year_dir: str, year: str) -> pd.DataFrame:
    records = []
    failed = []

    pdf_files = [f for f in os.listdir(year_dir) if f.lower().endswith(".pdf")]

    for file_name in tqdm(pdf_files, desc=f"Year {year}", leave=False):
        pdf_path = os.path.join(year_dir, file_name)
        text = extract_text_from_pdf(pdf_path)

        if not text.strip():
            failed.append(file_name)

        records.append({
            "file_name": file_name,
            "year": year,
            "text": text,
            "char_count": len(text),
        })

    if failed:
        print(f"  Warning: {len(failed)} PDFs failed/empty in {year}")

    return pd.DataFrame(records)


def main():
    dataset_path = get_dataset_path()
    print(f"Reading judgments from: {dataset_path}")

    judgments_root = os.path.join(dataset_path, "supreme_court_judgments")
    if not os.path.exists(judgments_root):
        judgments_root = dataset_path

    years = sorted([
        d for d in os.listdir(judgments_root)
        if os.path.isdir(os.path.join(judgments_root, d))
    ])
    print(f"Found {len(years)} year folders")

    for year in years:
        output_path = os.path.join(DATA_EXTRACTED, f"judgments_{year}.csv")

        if os.path.exists(output_path):
            print(f"Skipping {year} (already processed)")
            continue

        year_dir = os.path.join(judgments_root, year)
        df = process_year(year_dir, year)
        df.to_csv(output_path, index=False)
        print(f"Saved {len(df)} judgments -> {output_path}")

    print("\nExtraction complete. Output in data/extracted/")


if __name__ == "__main__":
    main()
