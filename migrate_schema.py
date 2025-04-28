# ver 20250329191000.0

import sqlite3
import os
from config import DB_PATH

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Deleted old database at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE playlists (
            playlist_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE videos (
            video_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            channel TEXT,
            publish_date TEXT,
            duration TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE playlist_videos (
            playlist_id TEXT,
            video_id TEXT,
            PRIMARY KEY (playlist_id, video_id),
            FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id),
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized with schema.")

if __name__ == "__main__":
    print(f"Creating new database at {DB_PATH}")
    init_db()
