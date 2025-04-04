# yt_scraper/import_playlists.py
# ver 20250404_refactored

import json
import sqlite3
import os
import logging
from datetime import datetime
# Import DB_PATH from config.py
from config import DB_PATH

# Use the DB_PATH from config
# DB_PATH = "youtube.db" # Remove this line or ensure it's commented out
PLAYLISTS_JSON = "playlists.json"

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    # Ensure the database directory exists if DB_PATH includes directories
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir)
            logging.info(f"Created database directory: {db_dir}")
        except OSError as e:
            logging.error(f"❌ Could not create database directory {db_dir}: {e}")
            return

    if not os.path.exists(DB_PATH):
        logging.error(f"❌ Database not found at {DB_PATH}. Run migrate_schema.py first.")
        # Optional: Call migrate_schema if needed? For now, just error out.
        return

    if not os.path.exists(PLAYLISTS_JSON):
        logging.error(f"❌ JSON file not found: {PLAYLISTS_JSON}")
        return

    try:
        with open(PLAYLISTS_JSON, "r", encoding="utf-8") as f:
            playlists = json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"❌ Error reading or parsing {PLAYLISTS_JSON}: {e}")
        return
    except Exception as e:
        logging.error(f"❌ An unexpected error occurred opening {PLAYLISTS_JSON}: {e}")
        return

    conn = None
    inserted = 0
    skipped = 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        for entry in playlists:
            playlist_id = entry.get("playlistId") or entry.get("playlist_id") # Handle potential variations
            title = entry.get("title")
            url = entry.get("url") # Keep original URL if needed

            if not playlist_id or not title:
                logging.warning(f"⚠️ Skipping entry due to missing playlist_id or title: {entry}")
                skipped += 1
                continue

            # Check if it already exists
            cursor.execute("SELECT 1 FROM playlists WHERE playlist_id = ?", (playlist_id,))
            if cursor.fetchone():
                skipped += 1
                # logging.debug(f"Playlist ID {playlist_id} already exists. Skipping.")
                continue

            try:
                cursor.execute("""
                    INSERT INTO playlists (playlist_id, title, url)
                    VALUES (?, ?, ?)
                """, (playlist_id, title, url))
                inserted += 1
                logging.debug(f"Inserted playlist: {title} ({playlist_id})")
            except sqlite3.IntegrityError:
                logging.warning(f"⚠️ Playlist ID {playlist_id} already exists (concurrent insert?). Skipping.")
                skipped += 1
            except sqlite3.Error as e:
                 logging.error(f"❌ Database error inserting {playlist_id}: {e}")
                 skipped += 1


        conn.commit()
        logging.info(f"✅ Import finished. Inserted: {inserted}, Skipped (already present or invalid): {skipped}")

    except sqlite3.Error as e:
        logging.error(f"❌ Database connection or operation error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()