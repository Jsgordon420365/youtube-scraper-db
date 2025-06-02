# ver 20250329191300.0
import json
import sqlite3
import os
import sys

DB_PATH = "youtube.db"
# Allow overriding JSON file via command-line arg
PLAYLISTS_JSON = sys.argv[1] if len(sys.argv) > 1 else "playlists.json"

def log_message(msg):
    from datetime import datetime
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}")

def main():
    if not os.path.exists(DB_PATH):
        log_message(f"❌ Database not found: {DB_PATH}")
        return

    if not os.path.exists(PLAYLISTS_JSON):
        log_message(f"❌ JSON file not found: {PLAYLISTS_JSON}")
        return

    with open(PLAYLISTS_JSON, "r", encoding="utf-8") as f:
        playlists = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    for entry in playlists:
        # Handle key variants: 'playlist_id' or generic 'id'
        playlist_id = entry.get("playlist_id") or entry.get("id")
        title = entry.get("title")
        # Use provided URL or construct from ID
        url = entry.get("url") or (f"https://www.youtube.com/playlist?list={playlist_id}" if playlist_id else None)
        if not playlist_id or not title:
            log_message(f"❌ Skipping entry with missing id/title: {entry}")
            continue

        # Check if it already exists
        cursor.execute("SELECT 1 FROM playlists WHERE playlist_id = ?", (playlist_id,))
        if cursor.fetchone():
            continue

        cursor.execute("""
            INSERT INTO playlists (playlist_id, title, url)
            VALUES (?, ?, ?)
        """, (playlist_id, title, url))
        inserted += 1

    conn.commit()
    conn.close()

    log_message(f"✅ Imported {inserted} new playlists into {DB_PATH}")

if __name__ == "__main__":
    main()
