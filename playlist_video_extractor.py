import sqlite3
import logging
import time
import sys
import os
from typing import List, Optional

# Import necessary components
from config import DB_PATH
from youtube_utils import scrape_and_save_video
from pytube import Playlist
from pytube.exceptions import PytubeError

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def create_processed_playlists_table(conn):
    """Create a table to track processed playlists if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_playlists (
            playlist_url TEXT PRIMARY KEY,
            processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

def is_playlist_processed(conn, playlist_url: str) -> bool:
    """Check if a playlist has already been processed."""
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM processed_playlists WHERE playlist_url = ?', (playlist_url,))
    return cursor.fetchone() is not None

def mark_playlist_processed(conn, playlist_url: str):
    """Mark a playlist as processed."""
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO processed_playlists (playlist_url) VALUES (?)', (playlist_url,))
    conn.commit()

def extract_video_ids_from_playlist(playlist_url: str, max_retries: int = 3) -> Optional[List[str]]:
    """
    Extract video IDs from a YouTube playlist.
    
    Args:
        playlist_url (str): URL of the YouTube playlist
        max_retries (int): Number of retry attempts if playlist fetch fails
    
    Returns:
        Optional[List[str]]: List of video IDs or None if extraction fails
    """
    for attempt in range(max_retries):
        try:
            playlist = Playlist(playlist_url)
            video_ids = [video_url.split('=')[-1] for video_url in playlist.video_urls]
            return video_ids
        except PytubeError as e:
            logger.warning(f"Playlist extraction attempt {attempt + 1} failed: {e}")
            time.sleep(2)  # Wait before retrying
    
    logger.error(f"Failed to extract video IDs from playlist: {playlist_url}")
    return None

def process_playlist(conn, playlist_url: str):
    """
    Process a playlist by extracting video IDs and scraping each video.
    
    Args:
        conn (sqlite3.Connection): Database connection
        playlist_url (str): URL of the YouTube playlist
    """
    if is_playlist_processed(conn, playlist_url):
        logger.info(f"Playlist already processed: {playlist_url}")
        return

    video_ids = extract_video_ids_from_playlist(playlist_url)
    if not video_ids:
        return

    logger.info(f"Found {len(video_ids)} videos in playlist: {playlist_url}")
    
    for video_id in video_ids:
        try:
            scrape_and_save_video(video_id)
            time.sleep(1)  # Delay between video scrapes
        except Exception as e:
            logger.error(f"Error scraping video {video_id}: {e}")
    
    mark_playlist_processed(conn, playlist_url)

def main(playlist_urls: List[str]):
    """
    Main function to process multiple playlist URLs.
    
    Args:
        playlist_urls (List[str]): List of YouTube playlist URLs
    """
    with sqlite3.connect(DB_PATH) as conn:
        create_processed_playlists_table(conn)
        
        for playlist_url in playlist_urls:
            try:
                process_playlist(conn, playlist_url)
            except Exception as e:
                logger.error(f"Error processing playlist {playlist_url}: {e}")

if __name__ == '__main__':
    # Example usage: python playlist_video_extractor.py "playlist_url1" "playlist_url2"
    if len(sys.argv) < 2:
        print("Usage: python playlist_video_extractor.py <playlist_url1> [playlist_url2] ...")
        sys.exit(1)
    
    playlist_urls = sys.argv[1:]
    main(playlist_urls)
