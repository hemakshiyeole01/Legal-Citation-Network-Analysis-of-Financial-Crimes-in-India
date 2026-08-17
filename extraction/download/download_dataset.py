"""
Stage: extraction/download

Resumable download of the Kaggle dataset using the Kaggle API directly.
kagglehub does not resume interrupted downloads - a dropped connection
means starting over from 0%. This script uses HTTP Range requests so
re-running it after a failure continues from where it left off.

Run:
    python extraction/download/download_dataset.py
"""

import sys
import os
import json
import time
import zipfile

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import requests
from tqdm import tqdm

from config.paths import KAGGLE_DATASET_ID, DATA_RAW

KAGGLE_JSON_CANDIDATES = [
    os.path.expanduser("~/.kaggle/kaggle.json"),
    os.path.join(os.environ.get("APPDATA", ""), "kaggle", "kaggle.json") if os.name == "nt" else None,
]

ARCHIVE_PATH = os.path.join(DATA_RAW, "dataset.zip")
EXTRACT_DIR = os.path.join(DATA_RAW, "sc_judgments")
MAX_RETRIES = 10
RETRY_DELAY_SECONDS = 10


TOKEN_FILE_CANDIDATES = [
    os.path.expanduser("~/.kaggle/access_token"),
]

KAGGLE_JSON_CANDIDATES = [
    os.path.expanduser("~/.kaggle/kaggle.json"),
    os.path.join(os.environ.get("APPDATA", ""), "kaggle", "kaggle.json") if os.name == "nt" else None,
]


def get_kaggle_auth():
    """
    Returns either ("bearer", token) for the newer token format,
    or ("basic", (username, key)) for the older kaggle.json format.
    """
    # Newer token format (preferred)
    env_token = os.environ.get("KAGGLE_API_TOKEN")
    if env_token:
        return ("bearer", env_token)

    for path in TOKEN_FILE_CANDIDATES:
        if os.path.exists(path):
            with open(path) as f:
                token = f.read().strip()
            if token:
                return ("bearer", token)

    # Older username/key format (fallback)
    env_user = os.environ.get("KAGGLE_USERNAME")
    env_key = os.environ.get("KAGGLE_KEY")
    if env_user and env_key:
        return ("basic", (env_user, env_key))

    for path in KAGGLE_JSON_CANDIDATES:
        if path and os.path.exists(path):
            with open(path) as f:
                creds = json.load(f)
            return ("basic", (creds["username"], creds["key"]))

    raise FileNotFoundError(
        "Kaggle credentials not found. Either:\n"
        "  1) Save your token to C:\\Users\\<you>\\.kaggle\\access_token, OR\n"
        "  2) Set environment variable KAGGLE_API_TOKEN\n"
        "Get a token from kaggle.com -> Settings -> API -> Create New Token"
    )


def get_download_url():
    owner, dataset = KAGGLE_DATASET_ID.split("/")
    return f"https://www.kaggle.com/api/v1/datasets/download/{owner}/{dataset}"


def download_with_resume():
    auth_type, auth_value = get_kaggle_auth()
    url = get_download_url()

    os.makedirs(DATA_RAW, exist_ok=True)

    for attempt in range(1, MAX_RETRIES + 1):
        resume_pos = os.path.getsize(ARCHIVE_PATH) if os.path.exists(ARCHIVE_PATH) else 0
        headers = {}
        if resume_pos:
            headers["Range"] = f"bytes={resume_pos}-"

        request_kwargs = {"headers": headers, "stream": True, "timeout": 60}
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {auth_value}"
        else:
            request_kwargs["auth"] = auth_value

        try:
            with requests.get(url, **request_kwargs) as r:
                if r.status_code not in (200, 206):
                    raise requests.exceptions.RequestException(f"Status code: {r.status_code}")

                total_size = int(r.headers.get("content-length", 0)) + resume_pos
                mode = "ab" if resume_pos else "wb"

                with open(ARCHIVE_PATH, mode) as f, tqdm(
                    total=total_size, initial=resume_pos,
                    unit="B", unit_scale=True, desc="Downloading dataset",
                ) as pbar:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            print("Download complete.")
            return

        except (requests.exceptions.RequestException, ConnectionError) as e:
            print(f"\nAttempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt == MAX_RETRIES:
                raise
            print(f"Retrying in {RETRY_DELAY_SECONDS}s (resuming from {resume_pos / 1e9:.2f} GB)...")
            time.sleep(RETRY_DELAY_SECONDS)


def extract_archive():
    if os.path.exists(EXTRACT_DIR) and os.listdir(EXTRACT_DIR):
        print(f"Already extracted at {EXTRACT_DIR}, skipping.")
        return

    print("Extracting archive...")
    with zipfile.ZipFile(ARCHIVE_PATH, "r") as zf:
        for member in tqdm(zf.infolist(), desc="Unzipping"):
            zf.extract(member, EXTRACT_DIR)
    print(f"Extracted to {EXTRACT_DIR}")


def main():
    download_with_resume()
    extract_archive()

    pointer_file = os.path.join(DATA_RAW, "dataset_path.txt")
    with open(pointer_file, "w") as f:
        f.write(EXTRACT_DIR)
    print(f"Path recorded at: {pointer_file}")


if __name__ == "__main__":
    main()
