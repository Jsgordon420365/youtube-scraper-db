# migrate_schema.py
# ver 20250404_fix_custom

import sqlite3
import os
import logging
# Use DB_PATH from config.py for consistency
from config import DB_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def init_db():
    # Delete old database if it exists to ensure a clean schema
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            logging.info(f"Deleted old database at {DB_PATH}")
        except OSError as e:
            logging.error(f"Error deleting database {DB_PATH}: {e}")
            return # Stop if we can't delete the old DB

    logging.info(f"Attempting to create new database at {DB_PATH}")
    conn = None # Initialize conn to None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        logging.info("Creating table: playlists")
        # Keep playlists table as it was, populated by import_playlists.py
        cursor.execute("""
            CREATE TABLE playlists (
                playlist_id TEXT PRIMARY KEY,
                title TEXT,
                url TEXT
            )
        """)

        logging.info("Creating table: videos")
        # Add fields for metadata we'll scrape
        cursor.execute("""
            CREATE TABLE videos (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                publish_date TEXT, -- Store as TEXT (YYYY-MM-DD) or ISO format
                duration_seconds INTEGER,
                view_count INTEGER,
                author TEXT, -- Channel Title from pytube
                channel_id TEXT,
                thumbnail_url TEXT,
                video_url TEXT,
                last_scraped_timestamp TEXT -- Track when video metadata was scraped
            )
        """)

        logging.info("Creating table: playlist_videos")
        # Keep playlist_videos linking table
        cursor.execute("""
            CREATE TABLE playlist_videos (
                playlist_id TEXT,
                video_id TEXT,
                position INTEGER, -- Optional: track order in playlist
                PRIMARY KEY (playlist_id, video_id),
                FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id) ON DELETE CASCADE,
                FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
            )
        """)

        logging.info("Creating table: transcripts")
        cursor.execute("""
            CREATE TABLE transcripts (
                video_id TEXT,
                language TEXT,
                transcript TEXT NOT NULL,
                last_fetched_timestamp TEXT,
                PRIMARY KEY (video_id, language),
                FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
            )
        """)

        conn.commit()
        logging.info("✅ Database initialized successfully with updated schema.")

    except sqlite3.Error as e:
        logging.error(f"Database error during initialization: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")

if __name__ == "__main__":
    init_db()