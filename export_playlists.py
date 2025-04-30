#!/usr/bin/env python3
"""
Export playlists and their video IDs to JSON.
Usage:
  python export_playlists.py [output_file]
If output_file is provided, JSON is written there; otherwise, printed to stdout.
"""
import sqlite3
import json
import os
import sys

from config import DB_PATH

def main(output_file=None):
    # Determine database path
    db_path = DB_PATH
    if not os.path.isabs(db_path):
        # DB_PATH is relative to this script's directory
        db_path = os.path.join(os.path.dirname(__file__), db_path)
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Verify playlists table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlists';")
    if cursor.fetchone() is None:
        print("Error: 'playlists' table not found in database.", file=sys.stderr)
        sys.exit(1)

    # Fetch playlist entries
    cursor.execute("SELECT playlist_id, title, url FROM playlists ORDER BY title COLLATE NOCASE;")
    playlists = []
    for row in cursor.fetchall():
        playlist_id = row["playlist_id"]
        title = row["title"]
        url = row["url"]
        # Fetch associated video IDs in order
        cursor.execute(
            "SELECT video_id FROM playlist_videos WHERE playlist_id = ? ORDER BY position ASC;",
            (playlist_id,)
        )
        video_ids = [r["video_id"] for r in cursor.fetchall()]
        playlists.append({
            "playlist_id": playlist_id,
            "title": title,
            "url": url,
            "video_ids": video_ids,
        })

    conn.close()

    output_json = json.dumps(playlists, indent=2)
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Exported {len(playlists)} playlists to {output_file}")
    else:
        print(output_json)

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else None
    main(out)