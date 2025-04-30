#!/usr/bin/env python3
"""
This script combines the functionality of:
1. get_channel_playlists.py - Getting playlists from a channel
2. import_playlists.py - Loading playlists into the database
3. main_scraper.py - Scraping videos from those playlists

This is a simpler, all-in-one solution to keep your YouTube data up to date.

Usage:
  python run_me.py
"""

import os
import sqlite3
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("run_me.log", encoding='utf-8', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Constants
DB_PATH = os.path.join(os.path.dirname(__file__), "youtube.db")
PLAYLISTS_JSON = os.path.join(os.path.dirname(__file__), "playlists.json")

def check_dependencies():
    """Check for required dependencies and install them if missing"""
    try:
        import pytube
        import yt_dlp
        import youtube_transcript_api
        logger.info("All required packages are installed")
    except ImportError as e:
        logger.warning(f"Missing dependency: {e}")
        logger.info("Attempting to install missing dependencies...")
        
        requirements = [
            "pytube>=12.1.0",
            "requests>=2.28.0", 
            "yt-dlp>=2023.3.4",
            "youtube-transcript-api>=0.6.0",
            "python-dateutil>=2.8.2"
        ]
        
        with open("requirements.txt", "w") as f:
            f.write("\n".join(requirements))
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            logger.info("Successfully installed dependencies")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e}")
            sys.exit(1)

def ensure_database_ready():
    """Initialize database if it doesn't exist or is missing tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlists'")
    if not cursor.fetchone():
        logger.info("Creating database tables...")
        
        # Create playlists table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                playlist_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                item_count INTEGER,
                last_updated TEXT
            )
        """)
        
        # Create videos table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                channel TEXT,
                publish_date TEXT,
                duration_seconds INTEGER,
                view_count INTEGER,
                author TEXT,
                channel_id TEXT,
                thumbnail_url TEXT,
                video_url TEXT,
                last_scraped_timestamp TEXT
            )
        """)
        
        # Create playlist_videos table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlist_videos (
                playlist_id TEXT,
                video_id TEXT,
                position INTEGER,
                PRIMARY KEY (playlist_id, video_id),
                FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id),
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            )
        """)
        
        # Create transcripts table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                video_id TEXT PRIMARY KEY,
                language TEXT,
                transcript TEXT,
                last_fetched_timestamp TEXT,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            )
        """)
        
        conn.commit()
        logger.info("Database tables created successfully")
    
    conn.close()

def import_playlists_to_db():
    """Import playlists from playlists.json to the database"""
    if not os.path.exists(PLAYLISTS_JSON):
        logger.error(f"Playlists file not found: {PLAYLISTS_JSON}")
        return False
    
    try:
        with open(PLAYLISTS_JSON, 'r') as f:
            playlists = json.load(f)
        
        if not playlists:
            logger.warning("No playlists found in the JSON file")
            return False
        
        logger.info(f"Found {len(playlists)} playlists in the JSON file")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        count = 0
        for playlist in playlists:
            playlist_id = playlist.get('playlist_id')
            title = playlist.get('title') 
            url = playlist.get('url')
            
            if not all([playlist_id, title, url]):
                logger.warning(f"Skipping invalid playlist data: {playlist}")
                continue
            
            try:
                cursor.execute(
                    "INSERT OR REPLACE INTO playlists (playlist_id, title, url, last_updated) VALUES (?, ?, ?, ?)",
                    (playlist_id, title, url, datetime.now(timezone.utc).isoformat())
                )
                count += 1
            except sqlite3.Error as e:
                logger.error(f"Error importing playlist {playlist_id}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Successfully imported {count} playlists to the database")
        return True
    
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error reading playlists file: {e}")
        return False

def get_existing_playlists():
    """Get list of playlists already in the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT playlist_id, title FROM playlists")
    playlists = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return playlists

def run_main_scraper():
    """Run the main scraper script"""
    if os.path.exists("main_scraper.py"):
        logger.info("Running main_scraper.py...")
        try:
            subprocess.check_call([sys.executable, "main_scraper.py"])
            logger.info("main_scraper.py completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running main_scraper.py: {e}")
            return False
    else:
        logger.error("main_scraper.py not found")
        return False

def run_scrape_my_channel():
    """Run scrape_my_channel.py if it exists"""
    if os.path.exists("scrape_my_channel.py"):
        logger.info("Running scrape_my_channel.py...")
        try:
            # Use the channel ID directly to avoid resolution issues
            channel_id = "UC8Pu_P4gRSQzYoN82QhoAkA"
            subprocess.check_call([sys.executable, "scrape_my_channel.py", channel_id])
            logger.info("scrape_my_channel.py completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running scrape_my_channel.py: {e}")
            return False
    else:
        logger.info("scrape_my_channel.py not found, skipping")
        return False

def main():
    """Main function to run the whole process"""
    logger.info("Starting YouTube scraper process...")
    
    # Step 1: Check dependencies
    check_dependencies()
    
    # Step 2: Ensure database is ready
    ensure_database_ready()
    
    # Step 3: Try running scrape_my_channel.py first if it exists
    if run_scrape_my_channel():
        logger.info("Successfully updated data with scrape_my_channel.py")
    else:
        # If scrape_my_channel fails or doesn't exist, fall back to previous method
        logger.info("Falling back to using the existing playlists in the database")
        
        # First check if we have playlists in the json file
        if os.path.exists(PLAYLISTS_JSON):
            import_playlists_to_db()
        
        # Check if we have playlists in the database
        playlists = get_existing_playlists()
        if not playlists:
            logger.error("No playlists found in the database. Cannot proceed.")
            sys.exit(1)
        
        logger.info(f"Found {len(playlists)} playlists in the database")
        
        # Run the main scraper
        run_main_scraper()
    
    logger.info("YouTube scraper process completed")

if __name__ == "__main__":
    main()
