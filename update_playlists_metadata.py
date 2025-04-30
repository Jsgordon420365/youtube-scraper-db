#!/usr/bin/env python3
"""
Update playlist metadata (item_count, last_updated) for all playlists.

Usage:
  python update_playlists_metadata.py
"""
import sqlite3
import os
import sys
from datetime import datetime, timezone

# Setup import path to include this directory
script_dir = os.path.dirname(__file__)
sys.path.insert(0, script_dir)

from config import DB_PATH
# Import pytube for fetching playlist video IDs
try:
    from pytube import Playlist
    from pytube.exceptions import PytubeError
except ImportError as e:
    print(f"FATAL ERROR: pytube is required: {e}", file=sys.stderr)
    sys.exit(1)

def get_video_ids_from_playlist(playlist_id):
    """Fetch current video IDs from a YouTube playlist via pytube."""
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    try:
        pl = Playlist(playlist_url)
        ids = set()
        for url in pl.video_urls:
            if "v=" in url:
                vid = url.split("v=")[1].split("&")[0]
                ids.add(vid)
        return ids
    except PytubeError as e:
        print(f"Error fetching playlist {playlist_id}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Unexpected error fetching playlist {playlist_id}: {e}", file=sys.stderr)
        return None

def ensure_metadata_columns(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(playlists)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'item_count' not in cols:
        cursor.execute("ALTER TABLE playlists ADD COLUMN item_count INTEGER")
    if 'last_updated' not in cols:
        cursor.execute("ALTER TABLE playlists ADD COLUMN last_updated TEXT")
    conn.commit()

def main():
    # Resolve absolute DB path
    db_path = DB_PATH
    if not os.path.isabs(db_path):
        db_path = os.path.join(script_dir, db_path)
    if not os.path.exists(db_path):
        print(f"Error: DB file not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Ensure metadata columns exist
    ensure_metadata_columns(conn)

    cursor = conn.cursor()
    cursor.execute("SELECT playlist_id, title FROM playlists ORDER BY title COLLATE NOCASE")
    playlists = cursor.fetchall()
    total = len(playlists)
    print(f"Updating metadata for {total} playlists...")
    for idx, row in enumerate(playlists, 1):
        pid = row['playlist_id']
        title = row['title']
        print(f"[{idx}/{total}] {pid} ({title})... ", end='')
        video_ids = get_video_ids_from_playlist(pid)
        if video_ids is None:
            print("FAILED to fetch")
            continue
        count = len(video_ids)
        ts = datetime.now(timezone.utc).isoformat()
        try:
            cursor.execute(
                "UPDATE playlists SET item_count = ?, last_updated = ? WHERE playlist_id = ?",
                (count, ts, pid)
            )
            conn.commit()
            print(f"{count} items, updated at {ts}")
        except Exception as e:
            print(f"Error updating metadata: {e}")
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()