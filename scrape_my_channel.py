#!/usr/bin/env python3
"""
Comprehensive YouTube channel scraper that:
1. Fetches all playlists from a given channel
2. Saves playlist info to the database
3. Scrapes all videos from those playlists that aren't already in the database

Usage:
  python scrape_my_channel.py @YOUR_CHANNEL_HANDLE

Example:
  python scrape_my_channel.py @jsgordon420
"""

import os
import sys
import json
import time
import sqlite3
import logging
import re
import requests
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("channel_scraper.log", encoding='utf-8', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Try importing required libraries
try:
    import yt_dlp
    from yt_dlp.utils import DownloadError, ExtractorError
except ImportError:
    logger.critical("FATAL ERROR: yt-dlp library not found. Install with 'pip install yt-dlp'")
    sys.exit(1)

try:
    from pytube import Playlist
    from pytube.exceptions import PytubeError
except ImportError:
    logger.critical("FATAL ERROR: pytube library not found. Install with 'pip install pytube'")
    sys.exit(1)

try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript
except ImportError:
    logger.critical("FATAL ERROR: youtube-transcript-api library not found. Install with 'pip install youtube-transcript-api'")
    sys.exit(1)

# Constants
DB_PATH = os.path.join(os.path.dirname(__file__), "youtube.db")
VIDEO_SCRAPE_DELAY = 1.0  # Seconds between scraping videos
PLAYLIST_FETCH_RETRIES = 3
VIDEO_PROCESS_RETRIES = 2

# --- Database Functions ---

def ensure_database_ready():
    """Initialize database if it doesn't exist"""
    if not os.path.exists(DB_PATH):
        logger.info(f"Database not found at {DB_PATH}, initializing...")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
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
        
        # Create transcripts table
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
        conn.close()
        logger.info("Database initialized successfully")
    else:
        logger.info(f"Database found at {DB_PATH}")

def get_db_connection():
    """Get a database connection"""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn

def get_stored_video_ids(conn):
    """Get all video IDs that are already in the database"""
    cursor = conn.cursor()
    cursor.execute("SELECT video_id FROM videos")
    return {row['video_id'] for row in cursor.fetchall()}

def get_stored_playlist_video_ids(conn, playlist_id):
    """Get all video IDs in a specific playlist stored in the database"""
    cursor = conn.cursor()
    cursor.execute("SELECT video_id FROM playlist_videos WHERE playlist_id = ?", (playlist_id,))
    return {row['video_id'] for row in cursor.fetchall()}

def save_playlists_to_db(conn, playlists):
    """Save playlist information to the database"""
    cursor = conn.cursor()
    count = 0
    
    for playlist in playlists:
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO playlists 
                (playlist_id, title, url, last_updated) 
                VALUES (?, ?, ?, ?)
                """, 
                (
                    playlist['playlist_id'],
                    playlist['title'],
                    playlist['url'],
                    datetime.now(timezone.utc).isoformat()
                )
            )
            count += 1
        except sqlite3.Error as e:
            logger.error(f"Error saving playlist {playlist.get('playlist_id')}: {e}")
    
    conn.commit()
    logger.info(f"Saved {count} playlists to database")
    return count

def sync_playlist_videos(conn, playlist_id, video_ids_with_positions):
    """Update playlist_videos table with current video IDs and positions"""
    if not conn:
        return False
        
    success = True
    stored_video_ids = get_stored_playlist_video_ids(conn, playlist_id)
    current_video_ids = {video_id for video_id, _ in video_ids_with_positions}
    
    # Calculate what to add and remove
    ids_to_add = current_video_ids - stored_video_ids
    ids_to_remove = stored_video_ids - current_video_ids
    
    cursor = conn.cursor()
    try:
        # Add new videos
        if ids_to_add:
            logger.info(f"Adding {len(ids_to_add)} new videos to playlist {playlist_id}")
            add_data = [
                (playlist_id, video_id, position) 
                for video_id, position in video_ids_with_positions 
                if video_id in ids_to_add
            ]
            cursor.executemany(
                "INSERT OR IGNORE INTO playlist_videos (playlist_id, video_id, position) VALUES (?, ?, ?)",
                add_data
            )
            
        # Remove videos no longer in the playlist
        if ids_to_remove:
            logger.info(f"Removing {len(ids_to_remove)} videos from playlist {playlist_id}")
            remove_data = [(playlist_id, video_id) for video_id in ids_to_remove]
            cursor.executemany(
                "DELETE FROM playlist_videos WHERE playlist_id = ? AND video_id = ?",
                remove_data
            )
            
        # Update playlist item count
        cursor.execute(
            "UPDATE playlists SET item_count = ? WHERE playlist_id = ?",
            (len(current_video_ids), playlist_id)
        )
            
        conn.commit()
        logger.info(f"Synced playlist_videos for {playlist_id}. Added: {len(ids_to_add)}, Removed: {len(ids_to_remove)}")
    except sqlite3.Error as e:
        logger.error(f"Database error syncing playlist_videos for {playlist_id}: {e}")
        conn.rollback()
        success = False
        
    return success

# --- YouTube Channel/Playlist Functions ---

def resolve_channel_url(spec):
    """Resolve a channel handle, user, or ID to a /channel/ URL."""
    # Handle empty input
    if not spec:
        logger.error("Empty channel specification provided")
        return "https://www.youtube.com/@jsgordon420"  # Default fallback
    
    # Raw channel ID
    if spec.startswith('UC') and len(spec) > 10:  # YouTube channel IDs are typically longer
        logger.info(f"Treating '{spec}' as a raw channel ID")
        return f"https://www.youtube.com/channel/{spec}"
    
    # Full URL as provided
    if spec.startswith('http'):
        url = spec.split('?')[0].rstrip('/')
        logger.info(f"Using provided URL: {url}")
    else:
        # Handle shorthand e.g. @handle or user/name
        if spec.startswith('@'):
            url = f"https://www.youtube.com/{spec}"
        else:
            url = spec if spec.startswith('/') else f"/{spec}"
            url = f"https://www.youtube.com{url}"
        
        url = url.split('?')[0].rstrip('/')
        logger.info(f"Constructed URL from specification: {url}")
    
    # If it's a handle (contains @), fetch page to extract channel ID
    if '/@' in url:
        logger.info(f"Resolving channel handle URL: {url}")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml'
            }
            r = requests.get(url, headers=headers, timeout=15.0)
            r.raise_for_status()
            
            # Try multiple patterns to find channel ID
            patterns = [
                r'externalId"\s*:\s*"(UC[^"]+)',
                r'channelId"\s*:\s*"(UC[^"]+)',
                r'channel\/([^"\\\?]+)',
                r'channel_id=([^"&]+)'
            ]
            
            for pattern in patterns:
                m = re.search(pattern, r.text)
                if m:
                    channel_id = m.group(1)
                    if channel_id.startswith('UC'):
                        logger.info(f"Resolved channel ID: {channel_id} using pattern '{pattern}'")
                        return f"https://www.youtube.com/channel/{channel_id}"
            
            # If we couldn't find the channel ID but got a valid page, just return the handle URL
            # YouTube can often show playlists for handle URLs even without a channel ID
            logger.warning(f"Could not extract channel ID from {url}, but the page exists - will use as is")
            return url
            
        except Exception as e:
            logger.error(f"Failed to resolve handle {spec}: {e}")
            # Since we couldn't resolve, we'll try hardcoded channel ID next
    
    # Accept /c/, /channel/, /user/ URLs directly
    if any(part in url for part in ['/channel/', '/c/', '/user/']):
        logger.info(f"Using direct channel URL format: {url}")
        # Normalize to channel ID if user or c
        if '/channel/' in url:
            return url
        # For /c/ or /user/, YouTube can handle it
        return url
    
    # Additional fallback for jsgordon420 channel - useful when all else fails
    if 'jsgordon420' in spec.lower() or 'jsgordon' in spec.lower():
        logger.info("Using hardcoded channel ID for jsgordon420")
        return "https://www.youtube.com/channel/UC8Pu_P4gRSQzYoN82QhoAkA"
    
    # Fallback: treat as channel ID
    logger.warning(f"Treating '{spec}' as a channel ID by default")
    return f"https://www.youtube.com/channel/{spec}"

def fetch_playlists(channel_url):
    """Fetch playlist IDs and titles from a channel's /playlists page."""
    # Try different URL formats to find playlists
    channel_id = None
    
    # Extract channel ID if URL contains it
    if '/channel/' in channel_url:
        channel_id = channel_url.split('/channel/')[1].split('/')[0].split('?')[0]
    elif '/@' in channel_url:
        # Handle @username format
        username = channel_url.split('/@')[1].split('/')[0].split('?')[0]
        logger.info(f"Extracted username: {username}")
    
    # Try alternative URL formats
    urls_to_try = [
        f"{channel_url.rstrip('/')}/playlists",
        f"https://www.youtube.com/channel/{channel_id}/playlists" if channel_id else None,
        f"https://www.youtube.com/@{username}/playlists" if 'username' in locals() else None
    ]
    
    # Filter out None values
    urls_to_try = [url for url in urls_to_try if url]
    
    # If all URLs failed, try a direct approach
    if not urls_to_try:
        urls_to_try = ["https://www.youtube.com/@jsgordon420/playlists"]
    
    logger.info(f"Will try these URLs to find playlists: {urls_to_try}")
    
    # Try each URL format
    html = ""
    success = False
    
    for url in urls_to_try:
        try:
            logger.info(f"Trying to fetch playlists from: {url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml'
            }
            r = requests.get(url, headers=headers, timeout=15.0)
            r.raise_for_status()
            html = r.text
            logger.info(f"Successfully fetched content from {url} (length: {len(html)})")
            
            # Save the HTML for debugging
            with open("channel_page.html", "w", encoding="utf-8") as f:
                f.write(html)
                
            # If we get a response and it seems to have content, stop trying
            if len(html) > 1000:
                success = True
                break
                
        except Exception as e:
            logger.warning(f"Failed to fetch playlists from {url}: {e}")
    
    if not success or not html:
        logger.error("Could not fetch playlist page from any URL")
        return []
    
    # Try multiple regex patterns to find playlist IDs
    patterns = [
        r'href="/playlist\?list=([A-Za-z0-9_-]+)"',  # Standard pattern
        r'list=([A-Za-z0-9_-]+)',                      # Broader pattern
        r'"playlistId":"([A-Za-z0-9_-]+)"'           # JSON format inside page
    ]
    
    all_ids = []
    for pattern in patterns:
        ids = re.findall(pattern, html)
        if ids:
            all_ids.extend(ids)
            logger.info(f"Found {len(ids)} playlist IDs using pattern '{pattern}'")
    
    # Unique preserving order
    seen = set()
    unique_ids = []
    for pid in all_ids:
        if pid not in seen and len(pid) > 8:  # Minimum valid playlist ID length
            seen.add(pid)
            unique_ids.append(pid)
    
    logger.info(f"Found {len(unique_ids)} unique playlist IDs")
    
    # Handle the case of finding no playlists
    if not unique_ids:
        # As a fallback, use playlists from a previous run if available
        try:
            with open('playlists.json', 'r') as f:
                playlists = json.load(f)
                logger.info(f"Loaded {len(playlists)} playlists from saved file as fallback")
                return playlists
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load playlists from file: {e}")
            
            # Last resort - try hardcoded playlists file
            try:
                with open('scrape_all_playlists.json', 'r') as f:
                    playlists = json.load(f)
                    logger.info(f"Loaded {len(playlists)} playlists from scrape_all_playlists.json")
                    return playlists
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load playlists from scrape_all_playlists.json: {e}")
        
        logger.error("No playlists found and no fallback available")
        return []
    
    playlists = []
    for pid in unique_ids:
        url = f"https://www.youtube.com/playlist?list={pid}"
        title = ''
        try:
            pl = Playlist(url)
            title = pl.title or ''
            logger.info(f"Fetched title for playlist {pid}: {title}")
        except Exception as e:
            logger.warning(f"Could not fetch title for playlist {pid}: {e}")
            # Use a default title if we can't fetch it
            title = f"Playlist {pid}"
        
        playlists.append({'playlist_id': pid, 'title': title, 'url': url})
    
    # Save playlists to file for future use
    try:
        with open('playlists.json', 'w', encoding='utf-8') as f:
            json.dump(playlists, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(playlists)} playlists to file for future use")
    except Exception as e:
        logger.warning(f"Could not save playlists to file: {e}")
    
    return playlists

def get_video_ids_from_playlist(playlist_id):
    """Fetches video IDs and their positions from a YouTube playlist."""
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    logger.info(f"Fetching video IDs from playlist: {playlist_url}")
    
    for attempt in range(PLAYLIST_FETCH_RETRIES):
        try:
            pl = Playlist(playlist_url)
            video_urls = pl.video_urls  # Fetches the list
            
            video_ids_with_positions = []
            for position, url in enumerate(video_urls, start=1):
                try:
                    if "v=" in url:
                        vid_id = url.split("v=")[1].split("&")[0]
                        video_ids_with_positions.append((vid_id, position))
                    else:
                        logger.warning(f"Could not extract video ID from URL format: {url}")
                except Exception as e:
                    logger.error(f"Error parsing URL {url}: {e}")
                    
            logger.info(f"Found {len(video_ids_with_positions)} videos in playlist {playlist_id}")
            return video_ids_with_positions
            
        except PytubeError as e:
            logger.warning(f"Pytube error fetching playlist {playlist_id} (Attempt {attempt+1}/{PLAYLIST_FETCH_RETRIES}): {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching playlist {playlist_id} (Attempt {attempt+1}/{PLAYLIST_FETCH_RETRIES}): {e}")
            
        if attempt < PLAYLIST_FETCH_RETRIES - 1:
            wait_time = 2 ** (attempt + 1)
            logger.info(f"Retrying playlist fetch in {wait_time} seconds...")
            time.sleep(wait_time)
            
    logger.error(f"Failed to fetch video IDs for playlist {playlist_id} after {PLAYLIST_FETCH_RETRIES} attempts")
    return []

# --- Video Scraping Function ---

def scrape_video(video_id):
    """Scrape metadata and transcript for a YouTube video."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(f"Processing video: {video_url}")
    
    video_data = {}
    transcript_text = None
    transcript_lang = None
    
    # --- Scrape Metadata using yt-dlp ---
    try:
        ydl_opts = {
            'quiet': True, 
            'no_warnings': True, 
            'skip_download': True,
            'ignoreerrors': True, 
            'format': 'bestaudio/best',
            'extract_flat': 'discard_in_playlist',
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            
            if not info_dict:
                raise ExtractorError(f"yt-dlp returned None for {video_id}")
                
            if info_dict.get('_type') == 'UnavailableVideo' or info_dict.get('availability') == 'unavailable':
                logger.warning(f"Video {video_id} is unavailable")
                return None, None
                
            pub_date_str = None
            if info_dict.get('upload_date'):
                try:
                    pub_date_str = datetime.strptime(info_dict['upload_date'], '%Y%m%d').strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse upload_date '{info_dict['upload_date']}' for {video_id}")
                    
            video_data = {
                "video_id": info_dict.get('id'),
                "title": info_dict.get('title'),
                "description": info_dict.get('description'),
                "publish_date": pub_date_str,
                "duration_seconds": int(info_dict['duration']) if info_dict.get('duration') else None,
                "view_count": info_dict.get('view_count'),
                "author": info_dict.get('uploader') or info_dict.get('channel'),
                "channel_id": info_dict.get('channel_id'),
                "thumbnail_url": info_dict.get('thumbnail'),
                "video_url": info_dict.get('webpage_url', video_url),
                "last_scraped_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Successfully fetched metadata for {video_id}")
            
    except (DownloadError, ExtractorError) as e:
        logger.error(f"yt-dlp error for {video_id}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Unexpected error during yt-dlp processing for {video_id}: {e}")
        return None, None
        
    # --- Scrape Transcript ---
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try English transcripts first, then fall back to others
        preferred_langs = ['en', 'en-US', 'en-GB']
        transcript_obj = None
        
        try:
            transcript_obj = transcript_list.find_manually_created_transcript(preferred_langs)
            transcript_lang = transcript_obj.language_code
            logger.info(f"Found manual '{transcript_lang}' transcript")
        except NoTranscriptFound:
            try:
                transcript_obj = transcript_list.find_generated_transcript(preferred_langs)
                transcript_lang = transcript_obj.language_code
                logger.info(f"Found generated '{transcript_lang}' transcript")
            except NoTranscriptFound:
                available_transcripts = list(transcript_list)
                if available_transcripts:
                    first_available = available_transcripts[0]
                    transcript_obj = transcript_list.find_transcript([first_available.language_code])
                    transcript_lang = transcript_obj.language_code
                    logger.info(f"Using first available transcript: '{transcript_lang}'")
                else:
                    logger.warning(f"No transcripts available for {video_id}")
        
        if transcript_obj and transcript_lang:
            transcript_segments = transcript_obj.fetch()
            processed_texts = []
            
            for item in transcript_segments:
                if isinstance(item, dict):
                    text_segment = item.get('text', '').strip()
                    if text_segment:
                        processed_texts.append(text_segment)
                else:
                    text_segment = getattr(item, 'text', '').strip()
                    if text_segment:
                        processed_texts.append(text_segment)
                        
            transcript_text = " ".join(processed_texts)
            
            if transcript_text:
                logger.info(f"Successfully processed '{transcript_lang}' transcript for {video_id} ({len(transcript_text)} chars)")
            else:
                logger.warning(f"Processed transcript for {video_id} but result was empty")
                
    except TranscriptsDisabled:
        logger.warning(f"Transcripts are disabled for video {video_id}")
    except NoTranscriptFound:
        logger.warning(f"No transcript found for video {video_id}")
    except CouldNotRetrieveTranscript as e:
        logger.error(f"Could not retrieve transcript for {video_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during transcript processing for {video_id}: {e}")
        
    return video_data, (transcript_text, transcript_lang)

def save_video_to_db(conn, video_data, transcript_info):
    """Save video metadata and transcript to the database."""
    if not conn or not video_data:
        return False
        
    try:
        cursor = conn.cursor()
        
        # Insert video metadata
        video_columns = list(video_data.keys())
        video_values = list(video_data.values())
        placeholders = ', '.join(['?'] * len(video_columns))
        columns_str = ', '.join([f'"{col}"' for col in video_columns])
        
        sql_video = f'INSERT OR REPLACE INTO videos ({columns_str}) VALUES ({placeholders})'
        cursor.execute(sql_video, video_values)
        
        # Save transcript if available
        transcript_text, transcript_lang = transcript_info
        if transcript_text and transcript_lang:
            sql_transcript = """
                INSERT OR REPLACE INTO transcripts 
                (video_id, language, transcript, last_fetched_timestamp) 
                VALUES (?, ?, ?, ?)
            """
            cursor.execute(sql_transcript, (
                video_data['video_id'],
                transcript_lang,
                transcript_text,
                datetime.now(timezone.utc).isoformat()
            ))
            
        conn.commit()
        logger.info(f"✅ Saved data for video {video_data['video_id']} to database")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Database error saving video {video_data.get('video_id', 'unknown')}: {e}")
        conn.rollback()
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving video {video_data.get('video_id', 'unknown')}: {e}")
        conn.rollback()
        return False

# --- Main Function ---

def main():
    if len(sys.argv) < 2:
        logger.error("Please provide a YouTube channel handle, ID, or URL")
        print(f"Usage: {sys.argv[0]} @YourChannelHandle")
        sys.exit(1)
        
    channel_spec = sys.argv[1]
    
    # Step 1: Ensure database is ready
    ensure_database_ready()
    
    # Step 2: Resolve channel URL and fetch playlists
    try:
        channel_url = resolve_channel_url(channel_spec)
        logger.info(f"Resolved channel URL: {channel_url}")
        
        playlists = fetch_playlists(channel_url)
        logger.info(f"Found {len(playlists)} playlists for channel")
        
        if not playlists:
            logger.warning(f"No playlists found for channel {channel_spec}")
            sys.exit(1)
            
        # Step 3: Save playlists to database
        conn = get_db_connection()
        save_playlists_to_db(conn, playlists)
        
        # Step 4: Get existing video IDs to avoid re-scraping
        existing_video_ids = get_stored_video_ids(conn)
        logger.info(f"Found {len(existing_video_ids)} videos already in database")
        
        # Step 5: Process each playlist
        for index, playlist in enumerate(playlists, start=1):
            playlist_id = playlist['playlist_id']
            playlist_title = playlist['title']
            
            logger.info(f"\n[{index}/{len(playlists)}] Processing playlist: {playlist_title} ({playlist_id})")
            
            # Get video IDs with positions
            video_ids_with_positions = get_video_ids_from_playlist(playlist_id)
            
            if not video_ids_with_positions:
                logger.warning(f"No videos found in playlist {playlist_id}, skipping")
                continue
                
            # Sync playlist_videos table
            if not sync_playlist_videos(conn, playlist_id, video_ids_with_positions):
                logger.error(f"Failed to sync playlist_videos for {playlist_id}, skipping video scraping")
                continue
                
            # Process videos not already in the database
            videos_to_scrape = [
                vid_id for vid_id, _ in video_ids_with_positions 
                if vid_id not in existing_video_ids
            ]
            
            logger.info(f"Found {len(videos_to_scrape)} new videos to scrape in playlist {playlist_id}")
            
            for i, video_id in enumerate(videos_to_scrape, start=1):
                logger.info(f"[{i}/{len(videos_to_scrape)}] Scraping video {video_id}")
                
                for attempt in range(VIDEO_PROCESS_RETRIES):
                    video_data, transcript_info = scrape_video(video_id)
                    
                    if video_data:
                        if save_video_to_db(conn, video_data, transcript_info):
                            # Add to existing video IDs to avoid duplicating if video appears in multiple playlists
                            existing_video_ids.add(video_id)
                            break
                    else:
                        logger.warning(f"Attempt {attempt+1}/{VIDEO_PROCESS_RETRIES} failed for video {video_id}")
                        if attempt < VIDEO_PROCESS_RETRIES - 1:
                            time.sleep(2.0)  # Wait before retry
                
                # Delay between processing videos
                time.sleep(VIDEO_SCRAPE_DELAY)
        
        conn.close()
        logger.info("All playlists processed successfully!")
        
    except Exception as e:
        logger.critical(f"Error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
