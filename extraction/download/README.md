# extraction/download

Downloads the SC Judgments India (1950-2024) dataset (~6.4GB zip).

## Setup (one-time)
1. kaggle.com -> Account -> Create New API Token -> downloads `kaggle.json`
2. Place at `~/.kaggle/kaggle.json` (Mac/Linux) or `C:\Users\<you>\.kaggle\kaggle.json` (Windows)

## Run
```
python extraction/download/download_dataset.py
```

## Resume behavior
If the connection drops mid-download, just re-run the same command. It
checks the partial file already on disk (`data/raw/dataset.zip`) and
resumes from that byte offset instead of restarting from 0%. Safe to
re-run as many times as needed.

## Output
- `data/raw/dataset.zip` - the archive (gitignored)
- `data/raw/sc_judgments/` - extracted PDFs (gitignored)
- `data/raw/dataset_path.txt` - pointer read by `extraction/pdf_extraction/`
