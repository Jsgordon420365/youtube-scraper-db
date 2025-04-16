# ver 20250329182700.3

import os
import sys
import time
import logging
import datetime
import subprocess

from harvest_playlists import get_all_playlists

# Settings
WRAPPER_SCRIPT = "scrape_playlist_id.py"
MAX_RETRIES = 5
RETRY_DELAY = 0.25

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def run_scraper_with_retries(playlist_id: str) -> bool:
    if not os.path.isfile(WRAPPER_SCRIPT):
        logging.error(f"[ERROR] Wrapper script '{WRAPPER_SCRIPT}' not found.")
        return False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"[ATTEMPT {attempt}/{MAX_RETRIES}] Scraping {playlist_id}")
            result = subprocess.run(
                [sys.executable, WRAPPER_SCRIPT, "--playlist", playlist_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ.copy()
            )
            if result.returncode == 0:
                logging.info(f"[OK] Scraped {playlist_id}")
                return True
            else:
                logging.warning(f"[RETRY {attempt}/{MAX_RETRIES}] Failed to scrape {playlist_id}: Exit code {result.returncode}")
                logging.warning(f"STDOUT:\n{result.stdout}")
                logging.warning(f"STDERR:\n{result.stderr}")
        except FileNotFoundError as e:
            logging.error(f"[ERROR] Failed to execute wrapper script: {e}")
            return False
        except Exception as e:
            logging.error(f"[EXCEPTION] Attempt {attempt}: {e}")
        time.sleep(RETRY_DELAY)
    logging.error(f"[FAIL] Giving up after {MAX_RETRIES} attempts: {playlist_id}")
    return False

def main():
    playlists = get_all_playlists()
    if not playlists:
        logging.error("No playlists found. Exiting.")
        return

    total = len(playlists)
    for index, p in enumerate(playlists, start=1):
        playlist_id = p.get("playlist_id")
        playlist_name = p.get("title", "Unknown Playlist")
        if not playlist_id:
            logging.warning(f"[SKIP] Missing playlist_id for entry: {p}")
            continue
        logging.info(f"[{index}/{total}] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Processing: {playlist_name} ({playlist_id})")
        logging.info(f"[START] Scraping: {playlist_name} ({playlist_id})")
        success = run_scraper_with_retries(playlist_id)
        if not success:
            logging.error(f"[FAILED] Could not scrape playlist: {playlist_name} ({playlist_id})")
            continue
        logging.info(f"[DONE] {playlist_name} ✅\n")
        time.sleep(0.2)

if __name__ == "__main__":
    main()