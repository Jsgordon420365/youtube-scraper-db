# yt_scraper/main_scraper.py (previously scrape_all_playlists.py)
# ver 20250404_refactored_debug

import sqlite3
import logging
import time
import sys
import os
from datetime import datetime, timezone

# >>> ADDED DEBUG PRINT <<<
print("DEBUG: Starting imports...")

# Import necessary components
from config import DB_PATH # Make sure DB_PATH is correctly defined in config.py
# Ensure youtube_utils.py is present and correct
try:
    from youtube_utils import scrape_and_save_video
except ImportError as e:
    print(f"FATAL ERROR: Could not import 'scrape_and_save_video' from youtube_utils. Error: {e}")
    print("Please ensure youtube_utils.py exists and has no syntax errors.")
    sys.exit(1) # Exit if essential import fails

# Check if Pytube exists (though youtube_utils now might use yt-dlp)
try:
    from pytube import Playlist
    from pytube.exceptions import PytubeError
except ImportError as e:
     print(f"WARNING: Could not import 'pytube'. If using yt-dlp in youtube_utils, this might be okay. Error: {e}")
     # Assign dummy classes if needed, or let youtube_utils handle it
     Playlist = None
     PytubeError = Exception # Define as base exception if pytube isn't used

# >>> ADDED DEBUG PRINT <<<
print("DEBUG: Imports finished. Setting up logging...")

# Settings
VIDEO_SCRAPE_DELAY_SECONDS = 1.5 # Increase delay slightly
PLAYLIST_FETCH_RETRIES = 3
VIDEO_PROCESS_RETRIES = 2 # Retries for scraping *a single video*

# Setup logging
log_filename = "main_scraper.log"
# Ensure log directory exists if specified in config or path
log_dir = os.path.dirname(log_filename)
if log_dir and not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir)
    except OSError as e:
        print(f"ERROR: Could not create log directory '{log_dir}'. Error: {e}")
        # Continue without file logging? Or exit? Let's try continuing.
        log_filename = None # Disable file logging if dir creation fails

try:
    log_handlers = [logging.StreamHandler(sys.stdout)] # Always log to console
    if log_filename:
        log_handlers.append(logging.FileHandler(log_filename, encoding='utf-8', mode='a'))

    logging.basicConfig(
        level=logging.INFO, # Set base level
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=log_handlers
    )
    # Optionally reduce verbosity of libraries if they were imported
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    try:
        logging.getLogger("pytube").setLevel(logging.INFO) # Can set higher if too noisy
    except Exception: pass # Ignore if pytube wasn't imported

except Exception as e:
    print(f"FATAL ERROR: Failed to configure logging. Error: {e}")
    sys.exit(1)


# Get a logger for this specific module
logger = logging.getLogger(__name__)

# >>> ADDED DEBUG PRINT <<<
print("DEBUG: Logging configured. Defining functions...")


def get_playlists_from_db(db_path: str) -> list[dict]:
    """Fetches playlist details from the database."""
    conn = None
    playlists = []
    if not os.path.exists(db_path):
        logger.error(f"❌ Database file not found at {db_path}. Cannot fetch playlists.")
        return []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
        cursor = conn.cursor()
        # Ensure the playlists table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlists';")
        if not cursor.fetchone():
            logger.error("❌ 'playlists' table not found in the database. Run migration and import first.")
            return []

        cursor.execute("SELECT playlist_id, title, url FROM playlists ORDER BY title")
        playlists = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Found {len(playlists)} playlists in the database.")
    except sqlite3.Error as e:
        logger.error(f"❌ Database error fetching playlists: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error fetching playlists: {type(e).__name__} - {e}")
        playlists = [] # Ensure empty list is returned on unexpected error
    finally:
        if conn:
            conn.close()
    return playlists

def get_video_ids_from_playlist(playlist_id: str) -> list[str] | None:
    """Fetches video IDs from a YouTube playlist using pytube or another method if adapted."""
    # This function currently relies on Pytube. If switching youtube_utils to yt-dlp
    # for *metadata*, this function might still use Pytube just for playlist contents,
    # or it could also be adapted to use yt-dlp's playlist fetching.
    # For now, assuming Pytube is still used here. Check if Playlist was imported.
    if not Playlist:
        logger.error("❌ Pytube Playlist class not available. Cannot fetch video IDs.")
        return None

    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    logger.info(f"  Fetching video IDs for playlist: {playlist_url}")
    video_ids = []
    for attempt in range(PLAYLIST_FETCH_RETRIES):
        try:
            pl = Playlist(playlist_url)
            # Accessing video_urls fetches the playlist data
            video_urls = pl.video_urls # Fetch the list of URLs

            # Extract video IDs from the URLs more safely
            current_ids = []
            for url in video_urls:
                 try:
                      if "v=" in url:
                           vid_id = url.split("v=")[1].split("&")[0]
                           current_ids.append(vid_id)
                      else:
                            # Handle potential short URLs or other formats if needed
                            logger.warning(f"  Could not extract video ID from URL format: {url}")
                 except IndexError:
                     logger.warning(f"  Could not parse video ID from URL structure: {url}")
                 except Exception as parse_err:
                      logger.error(f" Error parsing URL {url}: {parse_err}")

            video_ids = current_ids # Assign the successfully parsed IDs
            logger.info(f"  Found {len(video_ids)} videos (out of {len(video_urls)} URLs) in playlist {playlist_id}.")

            if not video_ids and len(video_urls) > 0:
                 logger.warning(f"  Could not parse any video IDs from the URLs in playlist {playlist_id}.")
            elif not video_ids:
                 # Try getting playlist title for better logging
                 try:
                    pl_title = pl.title
                 except Exception:
                    pl_title = "(Title unavailable)"
                 logger.warning(f"  Playlist {playlist_id} ('{pl_title}') appears to be empty or inaccessible.")
            return video_ids # Return list of IDs (could be empty)

        except PytubeError as e: # Catch Pytube specific errors
            logger.warning(f"  ⚠️ Pytube error fetching playlist {playlist_id} (Attempt {attempt + 1}/{PLAYLIST_FETCH_RETRIES}): {e}")
        except Exception as e:
            # Catch potential network errors, other unexpected issues during playlist fetch
            logger.error(f"  ❌ Unexpected error fetching playlist {playlist_id} (Attempt {attempt + 1}/{PLAYLIST_FETCH_RETRIES}): {type(e).__name__} - {e}")

        if attempt < PLAYLIST_FETCH_RETRIES - 1:
            wait_time = 2 ** (attempt + 1) # Exponential backoff (2, 4 seconds)
            logger.info(f"  Retrying playlist fetch in {wait_time} seconds...")
            time.sleep(wait_time)

    logger.error(f"❌ Failed to fetch video IDs for playlist {playlist_id} after {PLAYLIST_FETCH_RETRIES} attempts.")
    return None # Return None on complete failure


def check_video_already_processed(video_id: str, playlist_id: str, db_path: str) -> bool:
    """Checks if a video-playlist link already exists in the database."""
    conn = None
    exists = False
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Check if this specific playlist-video combination exists
        sql = "SELECT 1 FROM playlist_videos WHERE playlist_id = ? AND video_id = ?"
        cursor.execute(sql, (playlist_id, video_id))
        if cursor.fetchone():
            exists = True
            logger.debug(f"  Video {video_id} already linked to playlist {playlist_id} in DB.")
    except sqlite3.Error as e:
        logger.error(f"  ❌ Database error checking playlist_videos link for P:{playlist_id} V:{video_id}: {e}")
        exists = True # Treat DB error as "don't process again now" to be safe
    except Exception as e:
        logger.error(f"  ❌ Unexpected error checking playlist_videos link for P:{playlist_id} V:{video_id}: {e}")
        exists = True # Treat unexpected error same as DB error for safety
    finally:
        if conn:
            conn.close()
    return exists


def add_playlist_video_link(playlist_id: str, video_id: str, position: int, db_path: str):
    """Adds the link between a playlist and a video in the database."""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10) # Added timeout
        cursor = conn.cursor()
        # Use INSERT OR IGNORE to avoid errors if the link already exists
        sql = """
            INSERT OR IGNORE INTO playlist_videos (playlist_id, video_id, position)
            VALUES (?, ?, ?)
        """
        cursor.execute(sql, (playlist_id, video_id, position))
        conn.commit()
        logger.debug(f"  Added/confirmed link for Playlist: {playlist_id}, Video: {video_id}, Position: {position}")
    except sqlite3.Error as e:
        logger.error(f"  ❌ Database error adding playlist_videos link for P:{playlist_id} V:{video_id}: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        logger.error(f"  ❌ Unexpected error adding playlist_videos link for P:{playlist_id} V:{video_id}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def main():
    # Ensure the logger is available
    global logger
    if not logger:
        print("FATAL: Logger not initialized before main()")
        sys.exit(1)

    logger.info("--- Starting YouTube Scraper ---")

    # Ensure the database directory exists if DB_PATH includes directories
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir)
            logger.info(f"Created database directory: {db_dir}")
        except OSError as e:
            logger.error(f"❌ Could not create database directory {db_dir}: {e}")
            return # Cannot proceed without DB path

    playlists = get_playlists_from_db(DB_PATH)
    if not playlists:
        logger.warning("No playlists found in the database to process. Ensure migrate_schema.py and import_playlists.py ran successfully.")
        return

    total_playlists = len(playlists)
    overall_start_time = time.time()
    logger.info(f"Starting processing for {total_playlists} playlists...")

    for i, pl_data in enumerate(playlists):
        playlist_id = pl_data.get('playlist_id')
        playlist_title = pl_data.get('title', playlist_id) # Use ID as fallback title

        # Basic check for valid playlist_id format (optional)
        if not playlist_id or not isinstance(playlist_id, str) or len(playlist_id) < 10:
             logger.warning(f"⚠️ Skipping playlist entry {i+1} due to invalid/missing playlist_id: {pl_data}")
             continue

        pl_start_time = time.time()
        logger.info(f"\n{'='*10} Processing Playlist {i+1}/{total_playlists}: '{playlist_title}' ({playlist_id}) {'='*10}")

        video_ids = get_video_ids_from_playlist(playlist_id)

        if video_ids is None:
            logger.error(f"  Skipping playlist '{playlist_title}' due to video ID fetch error.")
            continue # Skip to the next playlist

        if not video_ids:
             logger.info(f"  Playlist '{playlist_title}' contains no videos or IDs could not be parsed. Skipping.")
             continue

        total_videos_in_playlist = len(video_ids)
        logger.info(f"  Processing {total_videos_in_playlist} videos for playlist '{playlist_title}'...")

        playlist_videos_succeeded = 0
        playlist_videos_failed = 0
        playlist_videos_skipped = 0

        for j, video_id in enumerate(video_ids):
             # Basic check for valid video_id format (optional)
             if not video_id or not isinstance(video_id, str) or len(video_id) < 10:
                  logger.warning(f"  ⚠️ Skipping invalid video_id found at position {j+1} in playlist {playlist_id}: '{video_id}'")
                  playlist_videos_failed += 1 # Count as failure
                  continue

             logger.info(f"  --> Video {j+1}/{total_videos_in_playlist} (ID: {video_id})")

             # Check if this video-playlist link already exists (basic check)
             if check_video_already_processed(video_id, playlist_id, DB_PATH):
                  logger.info(f"  Skipping video {video_id} as it's already linked to playlist {playlist_id}.")
                  # Ensure link exists even if skipping scrape (in case it was missed before)
                  add_playlist_video_link(playlist_id, video_id, j + 1, DB_PATH)
                  playlist_videos_skipped += 1
                  # Apply delay even when skipping
                  logger.debug(f"  Pausing for {VIDEO_SCRAPE_DELAY_SECONDS}s...")
                  time.sleep(VIDEO_SCRAPE_DELAY_SECONDS)
                  continue

             video_processed_successfully = False
             for attempt in range(VIDEO_PROCESS_RETRIES):
                 try:
                     # scrape_and_save_video returns True on DB success, False otherwise
                     if scrape_and_save_video(video_id, DB_PATH):
                         video_processed_successfully = True
                         # Link only after successful scrape and save
                         add_playlist_video_link(playlist_id, video_id, j + 1, DB_PATH)
                         break # Success, move to next video
                     else:
                         # If scrape_and_save_video returns False, it logged the specific error
                         logger.warning(f"    Attempt {attempt + 1}/{VIDEO_PROCESS_RETRIES} failed for video {video_id} (check previous logs).")
                         if attempt < VIDEO_PROCESS_RETRIES - 1:
                             wait_time = 2.0
                             logger.info(f"    Retrying video scrape in {wait_time} seconds...")
                             time.sleep(wait_time)

                 except Exception as scrape_exec_error:
                      # Catch unexpected errors *during the call* to scrape_and_save_video itself
                      logger.error(f"  ❌ CRITICAL error executing scrape_and_save_video for {video_id} (Attempt {attempt + 1}): {type(scrape_exec_error).__name__} - {scrape_exec_error}")
                      # Break the retry loop for this video if the call itself fails catastrophically
                      break


             if video_processed_successfully:
                 playlist_videos_succeeded += 1
             else:
                 playlist_videos_failed += 1
                 # Log final failure only if it wasn't due to a critical execution error caught above
                 if 'scrape_exec_error' not in locals():
                      logger.error(f"  ❌ Failed to process video {video_id} after {VIDEO_PROCESS_RETRIES} attempts.")

             # Delay between processing videos
             logger.debug(f"  Pausing for {VIDEO_SCRAPE_DELAY_SECONDS}s...")
             time.sleep(VIDEO_SCRAPE_DELAY_SECONDS)

        pl_end_time = time.time()
        pl_duration = pl_end_time - pl_start_time
        logger.info(f"{'='*10} Finished Playlist '{playlist_title}': {playlist_videos_succeeded} Succeeded, {playlist_videos_failed} Failed, {playlist_videos_skipped} Skipped in {pl_duration:.2f}s {'='*10}")

    overall_end_time = time.time()
    total_duration = overall_end_time - overall_start_time
    logger.info(f"\n--- YouTube Scraper Finished ---")
    logger.info(f"Processed {total_playlists} playlists in {total_duration:.2f} seconds.")


# >>> ADDED DEBUG PRINT <<<
print("DEBUG: Functions defined. Entering main execution block...")

if __name__ == "__main__":
    # Ensure imports and logging setup happened without fatal errors
    # >>> ADDED DEBUG PRINT <<<
    print("DEBUG: Inside __main__ block. Calling main()...")
    try:
        main()
    except Exception as main_exception:
        # Log any unhandled exception from main() itself
        logger.critical(f"CRITICAL ERROR: Unhandled exception in main(): {type(main_exception).__name__} - {main_exception}", exc_info=True)
        print(f"CRITICAL ERROR in main(): {main_exception}", file=sys.stderr)

    # Removed the print statement that was here to avoid issues if main() crashed early