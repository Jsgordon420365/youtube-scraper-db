# yt_scraper/main_scraper.py
# ver 20250405_efficient_updates

import sqlite3
import logging
import time
import sys
import os
from datetime import datetime, timezone, timedelta
import dateutil.parser # For parsing ISO format timestamps from DB

# Import necessary components
from config import DB_PATH
# Ensure youtube_utils.py is present and correct
try:
    # This function now handles scraping both metadata and transcript
    from youtube_utils import scrape_and_save_video
except ImportError as e:
    print(f"FATAL ERROR: Could not import 'scrape_and_save_video' from youtube_utils. Error: {e}")
    sys.exit(1)

# Need Playlist for fetching playlist video list
try:
    from pytube import Playlist
    from pytube.exceptions import PytubeError
except ImportError as e:
     print(f"FATAL ERROR: Could not import 'pytube'. Playlist fetching requires pytube. Error: {e}")
     sys.exit(1)

# --- Settings ---
VIDEO_SCRAPE_DELAY_SECONDS = 1.0 # Can potentially reduce delay if skipping many videos
PLAYLIST_FETCH_RETRIES = 3
VIDEO_PROCESS_RETRIES = 2
# Define how old data can be before refreshing (e.g., 7 days)
REFRESH_THRESHOLD_DAYS = 7
REFRESH_THRESHOLD = timedelta(days=REFRESH_THRESHOLD_DAYS)

# --- Logging Setup ---
log_filename = "main_scraper.log"
log_dir = os.path.dirname(log_filename)
if log_dir and not os.path.exists(log_dir):
    try: os.makedirs(log_dir)
    except OSError as e: log_filename = None # Disable file logging if dir fails

try:
    log_handlers = [logging.StreamHandler(sys.stdout)]
    if log_filename: log_handlers.append(logging.FileHandler(log_filename, encoding='utf-8', mode='a'))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=log_handlers
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pytube").setLevel(logging.INFO)
except Exception as e:
    print(f"FATAL ERROR: Failed to configure logging. Error: {e}")
    sys.exit(1)

logger = logging.getLogger(__name__)

# --- Database Interaction Functions ---
def get_db_connection(read_only=False):
    """Establishes a read-only or read-write connection."""
    # Need read-write for updating playlist_videos table
    mode = 'ro' if read_only else 'rwc' # read-write-create
    db_file = os.path.abspath(DB_PATH)
    if not os.path.exists(db_file) and mode == 'ro':
        logger.error(f"Database file not found for read-only connection: {db_file}")
        return None
    try:
        # Connect using appropriate mode
        conn = sqlite3.connect(f'file:{db_file}?mode={mode}', uri=True, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        logger.debug(f"DB connection established (mode={mode})")
        return conn
    except sqlite3.OperationalError as e:
        if "unable to open database file" in str(e) and mode == 'rwc':
             logger.error(f"Database file could not be opened or created at {db_file}: {e}")
        elif "attempt to write a readonly database" in str(e):
             logger.error(f"Database is opened read-only, but write access is needed: {e}")
        else:
            logger.error(f"Database connection error (mode={mode}): {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting to DB (mode={mode}): {e}")
        return None

def get_playlists_from_db(conn):
    """Fetches playlist details from the database."""
    if not conn: return []
    playlists = []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlists';")
        if not cursor.fetchone():
            logger.error("❌ 'playlists' table not found. Run migration and import first.")
            return []
        cursor.execute("SELECT playlist_id, title FROM playlists ORDER BY title COLLATE NOCASE")
        playlists = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Found {len(playlists)} playlists in the database.")
    except sqlite3.Error as e:
        logger.error(f"❌ Database error fetching playlists: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error fetching playlists: {type(e).__name__} - {e}")
    return playlists

def get_stored_playlist_video_ids(conn, playlist_id):
    """Fetches the set of video IDs currently linked to the playlist in the DB."""
    if not conn: return set()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT video_id FROM playlist_videos WHERE playlist_id = ?", (playlist_id,))
        return {row['video_id'] for row in cursor.fetchall()}
    except sqlite3.Error as e:
        logger.error(f"❌ DB error fetching stored videos for playlist {playlist_id}: {e}")
        return set() # Return empty set on error

def get_video_scrape_status(conn, video_id):
    """Checks timestamps for a video and its transcript."""
    if not conn: return None, None
    metadata_ts = None
    transcript_ts = None
    try:
        cursor = conn.cursor()
        # Check video metadata timestamp
        cursor.execute("SELECT last_scraped_timestamp FROM videos WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        if row and row['last_scraped_timestamp']:
            metadata_ts = dateutil.parser.isoparse(row['last_scraped_timestamp'])

        # Check transcript timestamp
        cursor.execute("SELECT last_fetched_timestamp FROM transcripts WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        if row and row['last_fetched_timestamp']:
            transcript_ts = dateutil.parser.isoparse(row['last_fetched_timestamp'])

    except sqlite3.Error as e:
        logger.error(f"❌ DB error checking scrape status for video {video_id}: {e}")
    except (TypeError, ValueError) as e:
         logger.error(f"❌ Error parsing timestamp for video {video_id}: {e}")
    return metadata_ts, transcript_ts


def sync_playlist_videos_db(conn, playlist_id, current_video_ids_on_yt):
    """Adds new video links and removes old ones from playlist_videos table."""
    if not conn: return False
    success = True
    stored_video_ids = get_stored_playlist_video_ids(conn, playlist_id)
    logger.debug(f" Stored videos: {len(stored_video_ids)}, Current on YT: {len(current_video_ids_on_yt)}")

    ids_to_add = current_video_ids_on_yt - stored_video_ids
    ids_to_remove = stored_video_ids - current_video_ids_on_yt

    cursor = conn.cursor()
    try:
        # Add new links (position might be inaccurate if not fetched from YT playlist directly)
        if ids_to_add:
            logger.info(f"  Adding {len(ids_to_add)} new video links for playlist {playlist_id}.")
            # Assign temporary positions or fetch actual positions if possible
            add_data = [(playlist_id, video_id, idx + 1) for idx, video_id in enumerate(current_video_ids_on_yt) if video_id in ids_to_add]
            cursor.executemany("INSERT OR IGNORE INTO playlist_videos (playlist_id, video_id, position) VALUES (?, ?, ?)", add_data)

        # Remove links for videos no longer in the playlist
        if ids_to_remove:
            logger.info(f"  Removing {len(ids_to_remove)} outdated video links for playlist {playlist_id}.")
            remove_data = [(playlist_id, video_id) for video_id in ids_to_remove]
            cursor.executemany("DELETE FROM playlist_videos WHERE playlist_id = ? AND video_id = ?", remove_data)

        conn.commit()
        logger.debug(f" Sync complete for playlist {playlist_id}. Added: {len(ids_to_add)}, Removed: {len(ids_to_remove)}")

    except sqlite3.Error as e:
        logger.error(f"  ❌ DB error syncing playlist_videos for {playlist_id}: {e}")
        conn.rollback()
        success = False
    finally:
         # Don't close cursor here if conn is managed outside
         pass
    return success


# --- Playlist/Video Fetching --- (Keep using Pytube for playlist contents for now)
def get_video_ids_from_playlist(playlist_id: str):
    """Fetches current video IDs from a YouTube playlist using pytube."""
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    logger.info(f"  Fetching current video IDs from YouTube playlist: {playlist_url}")
    video_ids = set()
    for attempt in range(PLAYLIST_FETCH_RETRIES):
        try:
            pl = Playlist(playlist_url)
            video_urls = pl.video_urls # Fetches the list

            current_ids = set()
            for url in video_urls:
                 try:
                      if "v=" in url:
                           vid_id = url.split("v=")[1].split("&")[0]
                           current_ids.add(vid_id)
                      else: logger.warning(f"  Could not extract video ID from URL format: {url}")
                 except IndexError: logger.warning(f"  Could not parse video ID from URL structure: {url}")
                 except Exception as parse_err: logger.error(f" Error parsing URL {url}: {parse_err}")

            video_ids = current_ids
            logger.info(f"  Found {len(video_ids)} unique videos currently in playlist {playlist_id} on YouTube.")
            return video_ids # Return set of IDs

        except PytubeError as e:
            logger.warning(f"  ⚠️ Pytube error fetching playlist {playlist_id} (Attempt {attempt + 1}/{PLAYLIST_FETCH_RETRIES}): {e}")
        except Exception as e:
            logger.error(f"  ❌ Unexpected error fetching playlist {playlist_id} (Attempt {attempt + 1}/{PLAYLIST_FETCH_RETRIES}): {type(e).__name__} - {e}")
        if attempt < PLAYLIST_FETCH_RETRIES - 1:
            wait_time = 2 ** (attempt + 1)
            logger.info(f"  Retrying playlist fetch in {wait_time} seconds...")
            time.sleep(wait_time)
    logger.error(f"❌ Failed to fetch current video IDs for playlist {playlist_id} after {PLAYLIST_FETCH_RETRIES} attempts.")
    return None # Return None on complete failure


# --- Main Execution Logic ---
def main():
    logger.info("--- Starting YouTube Scraper (Efficient Update Mode) ---")
    overall_start_time = time.time()

    # Use read-write connection for the main process
    db_conn = get_db_connection(read_only=False)
    if not db_conn:
        logger.critical("Failed to establish read-write database connection. Exiting.")
        return # Cannot proceed without DB connection

    # Ensure playlist_pings table exists for tracking playlist visits
    try:
        cursor = db_conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlist_pings (
                ping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id TEXT NOT NULL,
                pinged_timestamp TEXT NOT NULL,
                status TEXT,
                FOREIGN KEY(playlist_id) REFERENCES playlists(playlist_id) ON DELETE CASCADE
            );
        """)
        # Optional index for faster lookup by playlist
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlist_pings_playlist ON playlist_pings(playlist_id);")
        # Ensure playlist metadata columns exist
        cursor.execute("PRAGMA table_info(playlists);")
        cols_info = cursor.fetchall()
        existing_cols = [col[1] for col in cols_info]
        if 'item_count' not in existing_cols:
            cursor.execute("ALTER TABLE playlists ADD COLUMN item_count INTEGER;")
        if 'last_updated' not in existing_cols:
            cursor.execute("ALTER TABLE playlists ADD COLUMN last_updated TEXT;")
        db_conn.commit()
    except Exception as e:
        logger.error(f"Failed to create or verify 'playlist_pings' or metadata columns: {e}")
        # Proceed even if ping or metadata setup fails

    try:
        playlists_in_db = get_playlists_from_db(db_conn)
        if not playlists_in_db:
            logger.warning("No playlists found in the database. Run import_playlists.py first?")
            return

        total_playlists = len(playlists_in_db)
        logger.info(f"Processing {total_playlists} playlists...")
        playlists_processed_count = 0
        videos_scraped_count = 0
        videos_skipped_count = 0
        videos_failed_count = 0

        for i, pl_data in enumerate(playlists_in_db):
            playlist_id = pl_data.get('playlist_id')
            playlist_title = pl_data.get('title', playlist_id)
            pl_start_time = time.time()
            logger.info(f"\n{'='*10} Processing Playlist {i+1}/{total_playlists}: '{playlist_title}' ({playlist_id}) {'='*10}")
            # Record that we're starting processing this playlist
            ping_id = None
            try:
                ping_ts = datetime.now(timezone.utc).isoformat()
                ping_cursor = db_conn.cursor()
                ping_cursor.execute(
                    "INSERT INTO playlist_pings (playlist_id, pinged_timestamp, status) VALUES (?, ?, ?)",
                    (playlist_id, ping_ts, 'started')
                )
                ping_id = ping_cursor.lastrowid
                db_conn.commit()
            except Exception as e:
                logger.warning(f"Could not record ping for playlist {playlist_id}: {e}")

            # 1. Get current video IDs from YouTube
            current_video_ids_on_yt = get_video_ids_from_playlist(playlist_id)
            # Update playlist metadata (item count, last_updated)
            if current_video_ids_on_yt is not None:
                try:
                    meta_ts = datetime.now(timezone.utc).isoformat()
                    count = len(current_video_ids_on_yt)
                    db_conn.execute(
                        "UPDATE playlists SET item_count = ?, last_updated = ? WHERE playlist_id = ?",
                        (count, meta_ts, playlist_id)
                    )
                    db_conn.commit()
                    logger.debug(f"Updated metadata for playlist {playlist_id}: item_count={count}, last_updated={meta_ts}")
                except Exception as e:
                    logger.warning(f"Could not update metadata for playlist {playlist_id}: {e}")

            if current_video_ids_on_yt is None:
                logger.error(f"  Skipping playlist '{playlist_title}' due to failure fetching current videos from YouTube.")
                # Update ping status to failure
                if ping_id:
                    try:
                        db_conn.execute(
                            "UPDATE playlist_pings SET status = ? WHERE ping_id = ?",
                            ('failed_fetch', ping_id)
                        )
                        db_conn.commit()
                    except Exception:
                        pass
                continue  # Skip to the next playlist

            # 2. Sync playlist_videos table (Add new, Remove old)
            if not sync_playlist_videos_db(db_conn, playlist_id, current_video_ids_on_yt):
                logger.error(f" Failed to synchronize playlist_videos table for {playlist_id}. Skipping video processing for this playlist.")
                # Update ping status to sync failure
                if ping_id:
                    try:
                        db_conn.execute(
                            "UPDATE playlist_pings SET status = ? WHERE ping_id = ?",
                            ('sync_failed', ping_id)
                        )
                        db_conn.commit()
                    except Exception:
                        pass
                continue

            # 3. Iterate through current videos and decide whether to scrape
            total_videos_in_playlist = len(current_video_ids_on_yt)
            logger.info(f"  Checking {total_videos_in_playlist} videos for required scraping...")

            for j, video_id in enumerate(current_video_ids_on_yt):
                 logger.info(f"  --> Checking Video {j+1}/{total_videos_in_playlist} (ID: {video_id})")

                 # Check timestamps
                 metadata_ts, transcript_ts = get_video_scrape_status(db_conn, video_id)
                 now_utc = datetime.now(timezone.utc)

                 # Decision logic
                 should_scrape_metadata = True # Default to scrape unless proven otherwise
                 if metadata_ts and (now_utc - metadata_ts) < REFRESH_THRESHOLD:
                      should_scrape_metadata = False

                 should_scrape_transcript = True # Default to scrape unless proven otherwise
                 if transcript_ts and (now_utc - transcript_ts) < REFRESH_THRESHOLD:
                      should_scrape_transcript = False

                 # For now, if either needs scraping, call the main scrape function.
                 # Enhancement: modify scrape_and_save_video to selectively skip parts.
                 if should_scrape_metadata or should_scrape_transcript:
                      logger.info(f"    Scraping needed: Metadata outdated/missing: {should_scrape_metadata}, Transcript outdated/missing: {should_scrape_transcript}")
                      video_processed_successfully = False
                      for attempt in range(VIDEO_PROCESS_RETRIES):
                           if scrape_and_save_video(video_id, DB_PATH): # Pass DB_PATH as youtube_utils doesn't use the conn object
                               video_processed_successfully = True
                               videos_scraped_count += 1
                               break # Success
                           else:
                               logger.warning(f"    Attempt {attempt + 1}/{VIDEO_PROCESS_RETRIES} failed for video {video_id}.")
                               if attempt < VIDEO_PROCESS_RETRIES - 1:
                                   time.sleep(2.0) # Wait before retrying same video

                      if not video_processed_successfully:
                           videos_failed_count += 1
                           logger.error(f"  ❌ Failed to process video {video_id} after {VIDEO_PROCESS_RETRIES} attempts.")
                 else:
                      logger.info(f"    Skipping video {video_id} (Metadata & Transcript up-to-date).")
                      videos_skipped_count += 1

                 # Delay between processing each video check/scrape
                 time.sleep(VIDEO_SCRAPE_DELAY_SECONDS)

            pl_end_time = time.time()
            pl_duration = pl_end_time - pl_start_time
            logger.info(f"{'='*10} Finished Playlist '{playlist_title}' in {pl_duration:.2f}s {'='*10}")
            # Update ping status to completed
            if ping_id:
                try:
                    db_conn.execute(
                        "UPDATE playlist_pings SET status = ? WHERE ping_id = ?",
                        ('completed', ping_id)
                    )
                    db_conn.commit()
                except Exception:
                    pass
            playlists_processed_count += 1

    except Exception as e:
         logger.critical(f"CRITICAL ERROR in main loop: {type(e).__name__} - {e}", exc_info=True)
    finally:
        if db_conn:
            db_conn.close()
            logger.info("Database connection closed.")

    overall_end_time = time.time()
    total_duration = overall_end_time - overall_start_time
    logger.info(f"\n--- Scraper Finished ---")
    logger.info(f"Processed {playlists_processed_count}/{total_playlists} playlists in {total_duration:.2f} seconds.")
    logger.info(f"Videos Scraped/Updated: {videos_scraped_count}")
    logger.info(f"Videos Skipped (Up-to-date): {videos_skipped_count}")
    logger.info(f"Videos Failed: {videos_failed_count}")

# --- Main Execution ---
if __name__ == "__main__":
    # Remove debug prints now that basic operation confirmed
    # print("DEBUG: Entering main execution block...")
    try:
        main()
    except Exception as main_exception:
        # Log any unhandled exception from main() itself more visibly
        logger.critical(f"CRITICAL ERROR: Unhandled exception in main execution: {type(main_exception).__name__} - {main_exception}", exc_info=True)
        print(f"CRITICAL ERROR in main execution: {main_exception}", file=sys.stderr)