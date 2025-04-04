# ver 20250329182300.0

import argparse
import datetime
import subprocess
import sys
import os
import sqlite3
import logging

# Ensure UTF-8 encoding if supported
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

DB_PATH = "ytdata.db"

def get_playlist_id_from_args():
    parser = argparse.ArgumentParser(description="Scrape a specific playlist by ID")
    parser.add_argument("--playlist", type=str, required=True, help="Playlist ID to scrape")
    args = parser.parse_args()
    return args.playlist

def fetch_playlist_by_id(playlist_id):
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM playlists WHERE playlist_id = ?", (playlist_id,))
    result = cursor.fetchone()

    conn.close()
    return result

def run_scraper(playlist_id):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logging.info(f"[RUN] Scraping playlist ID: {playlist_id}")
    logging.info(f"[TIME] Timestamp: {timestamp}")

    result = subprocess.run(
        [sys.executable, "scrape.py", "--playlist", playlist_id],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        logging.error(f"[SCRAPER ERROR] stdout:\n{result.stdout}")
        logging.error(f"[SCRAPER ERROR] stderr:\n{result.stderr}")
        raise Exception(f"Scraper failed for playlist {playlist_id} with exit {result.returncode}")

    logging.info(f"[DONE] Successfully scraped: {playlist_id}")

def main():
    playlist_id = get_playlist_id_from_args()
    playlist = fetch_playlist_by_id(playlist_id)

    if not playlist:
        print(f"[ERROR] Playlist ID not found in DB: {playlist_id}")
        return

    title = playlist['title']
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"\n[STARTING] Playlist: {title} ({playlist_id}) at {timestamp}")

    try:
        run_scraper(playlist_id)
        print(f"[SUCCESS] Scraped and updated {title} ({playlist_id}) at {timestamp}")
    except Exception as e:
        print(f"[FAILURE] {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    main()
