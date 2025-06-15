# yt_scraper/youtube_utils.py
# ver 20250404_really_use_item_dot_text

import sqlite3
import logging
import time
import json
from datetime import datetime, timezone

# Import yt-dlp and transcript API
try:
    import yt_dlp
    from yt_dlp.utils import DownloadError, ExtractorError
except ImportError:
    print("FATAL ERROR: yt-dlp library not found. Please install it using 'pip install yt-dlp'")
    logger = logging.getLogger(__name__) # Try to get logger even on import error
    if logger: logger.critical("FATAL ERROR: yt-dlp library not found.")
    raise

try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript
except ImportError:
    print("FATAL ERROR: youtube-transcript-api library not found. Please install it using 'pip install youtube-transcript-api'")
    logger = logging.getLogger(__name__)
    if logger: logger.critical("FATAL ERROR: youtube-transcript-api library not found.")
    raise

logger = logging.getLogger(__name__)

def scrape_and_save_video(video_id: str, db_path: str) -> bool:
    """
    Scrapes metadata using yt-dlp and transcript using youtube-transcript-api
    for a given YouTube video ID and saves it to the specified SQLite database.

    Returns:
        bool: True if data was successfully scraped and saved (at least metadata), False otherwise.
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(f"Processing video: {video_url}")

    video_data = {}
    transcript_text = None
    transcript_lang_found = None
    metadata_fetched = False
    transcript_obj_found = None # Initialize here

    # --- Scrape Metadata using yt-dlp ---
    try:
        logger.debug(f"Initializing yt-dlp for {video_id}")
        ydl_opts = {
            'quiet': True, 'no_warnings': True, 'skip_download': True,
            'ignoreerrors': True, 'format': 'bestaudio/best',
            'extract_flat': 'discard_in_playlist',
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
            'socket_timeout': 30,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.debug(f"Extracting info for {video_id} with yt-dlp...")
            info_dict = ydl.extract_info(video_url, download=False)
            logger.debug(f"Finished info extraction for {video_id}")

            if not info_dict:
                 raise ExtractorError(f"yt-dlp returned None for {video_id}", video_id=video_id)

            extractor = info_dict.get('extractor_key') or info_dict.get('ie_key', 'N/A')
            if info_dict.get('_type') == 'UnavailableVideo' or info_dict.get('availability') == 'unavailable':
                 logger.warning(f"  ⚠️ Video {video_id} marked unavailable by yt-dlp extractor '{extractor}'. Availability: {info_dict.get('availability')}")
                 return False
            if not info_dict.get('id'):
                 logger.error(f"  ❌ yt-dlp extracted info for {video_id}, but missing 'id'. Extractor: '{extractor}'.")
                 return False
            if not info_dict.get('title'):
                 logger.warning(f"  ⚠️ yt-dlp extracted info for {video_id}, but missing 'title'. Proceeding with ID {info_dict.get('id')}.")

            pub_date_str = None
            if info_dict.get('upload_date'):
                 try:
                      pub_date_str = datetime.strptime(info_dict['upload_date'], '%Y%m%d').strftime('%Y-%m-%d')
                 except (ValueError, TypeError):
                      logger.warning(f" Could not parse upload_date '{info_dict['upload_date']}' for {video_id}")

            video_data = {
                "video_id": info_dict.get('id'), "title": info_dict.get('title'),
                "description": info_dict.get('description'), "publish_date": pub_date_str,
                "duration_seconds": int(info_dict['duration']) if info_dict.get('duration') else None,
                "view_count": info_dict.get('view_count'),
                "author": info_dict.get('uploader') or info_dict.get('channel'),
                "channel_id": info_dict.get('channel_id'),
                "thumbnail_url": info_dict.get('thumbnail'),
                "video_url": info_dict.get('webpage_url', video_url),
                "last_scraped_timestamp": datetime.now(timezone.utc).isoformat()
            }
            logger.info(
                f"  Successfully fetched metadata for {video_id} using yt-dlp "
                f"(Title: {video_data.get('title')})"
            )
            metadata_fetched = True

    # --- Catch yt-dlp specific and general errors during metadata fetch ---
    except (DownloadError, ExtractorError) as e:
         err_str = str(getattr(e, 'msg', e)).lower()
         if "video is unavailable" in err_str or "private video" in err_str or "copyright" in err_str or "members only" in err_str or "unavailable video" in err_str:
              logger.warning(f"  ⚠️ Video {video_id} unavailable/restricted: {e}")
         elif "unable to download webpage" in err_str or "http error" in err_str or "timeout" in err_str or "handshake" in err_str or "javascript" in err_str or "nsig" in err_str:
             # Catch network, timeout, and potential JS interpreter errors
              logger.error(f"  ❌ yt-dlp network/access/timeout/JS error for {video_id}: {e}")
         else:
             logger.error(f"  ❌ yt-dlp Download/ExtractorError for {video_id}: {e}", exc_info=True)
         metadata_fetched = False # Mark as failed
         # Decide whether to return False immediately or try transcripts anyway
         # Let's return False - if metadata fails, saving later is problematic
         return False

    except Exception as e: # Catch any other unexpected errors from yt-dlp block
        logger.error(f"  ❌ CRITICAL unexpected error during yt-dlp processing for {video_id}: {type(e).__name__} - {e}", exc_info=True)
        metadata_fetched = False
        return False


    # --- Scrape Transcript (using youtube_transcript_api) ---
    # Initialize transcript variables here, before the try block
    transcript_obj_found = None
    transcript_lang_found = None
    transcript_text = None # Ensure transcript_text is None unless successfully processed

    if metadata_fetched: # Only attempt if metadata succeeded
        try:
            logger.debug(f"  Fetching transcript list for {video_id}...")
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            found_langs = [f"{t.language}({t.language_code})" + (' [asr]' if t.is_generated else '') + (' [translatable]' if t.is_translatable else '') for t in transcript_list]
            logger.debug(f"  Available transcript languages for {video_id}: {', '.join(found_langs) if found_langs else 'None'}")

            preferred_langs = ['en', 'en-US', 'en-GB']
            try:
                 transcript_obj_found = transcript_list.find_manually_created_transcript(preferred_langs)
                 transcript_lang_found = transcript_obj_found.language_code
                 logger.info(f"  Found manual '{transcript_lang_found}' transcript.")
            except NoTranscriptFound:
                 logger.info(f"  Manual '{'/'.join(preferred_langs)}' transcript not found. Trying generated.")
                 try:
                     transcript_obj_found = transcript_list.find_generated_transcript(preferred_langs)
                     transcript_lang_found = transcript_obj_found.language_code
                     logger.info(f"  Found generated '{transcript_lang_found}' transcript.")
                 except NoTranscriptFound:
                     logger.warning(f"  Generated '{'/'.join(preferred_langs)}' transcript not found. Trying first available.")
                     available_transcripts = list(transcript_list)
                     if available_transcripts:
                         first_available = available_transcripts[0]
                         try:
                             transcript_obj_found = transcript_list.find_transcript([first_available.language_code])
                             transcript_lang_found = transcript_obj_found.language_code
                             logger.info(f"  Using first available transcript: '{transcript_lang_found}' ({'generated' if transcript_obj_found.is_generated else 'manual'})")
                         except Exception as find_err:
                              logger.error(f" Error finding transcript for language code '{first_available.language_code}': {find_err}")
                              transcript_obj_found = None # Ensure it's None if finding fails
                     else:
                          logger.warning(f"  No transcripts listed as available for {video_id}.")
                          transcript_obj_found = None

            # If a transcript object was found, attempt to fetch and process it
            if transcript_obj_found and transcript_lang_found:
                logger.debug(f"  Fetching transcript content for {video_id} (lang: {transcript_lang_found})...")
                transcript_segments = transcript_obj_found.fetch()
                logger.debug(f"  Fetched transcript content type: {type(transcript_segments)}")

                # --- CORRECTED TRANSCRIPT ITERATION (using item.text) ---
                try:
                    processed_texts = []
                    # Check if it's iterable and not a string
                    if hasattr(transcript_segments, '__iter__') and not isinstance(transcript_segments, str):
                        for item in transcript_segments:
                            # Check if item has a 'text' attribute (safer than assuming dict)
                            if hasattr(item, 'text'):
                                text_segment = getattr(item, 'text', '').strip() # Use getattr for safety
                                if text_segment:
                                     processed_texts.append(text_segment)
                            # If it's a dict (fallback, just in case API changes), use .get()
                            elif isinstance(item, dict):
                                 text_segment = item.get('text', '').strip()
                                 if text_segment:
                                      processed_texts.append(text_segment)
                                 else:
                                      logger.warning(f"  Transcript segment dict missing 'text' key for {video_id}: {item}")
                            # Log unexpected item types
                            else:
                                logger.warning(f"  Unexpected item format IN transcript segment list for {video_id}: {type(item)} - Content: {item}")

                        transcript_text = " ".join(processed_texts)

                        if transcript_text:
                             logger.info(f"  Successfully processed '{transcript_lang_found}' transcript for {video_id} ({len(transcript_text)} chars).")
                        else:
                             logger.warning(f"  Processed transcript for {video_id} but result was empty (lang: {transcript_lang_found}).")
                    else:
                         logger.error(f"  ❌ Fetched transcript segments for {video_id} was not iterable: {type(transcript_segments)}")
                         transcript_text = None # Ensure failure state

                except Exception as e_proc:
                     logger.error(f"  ❌ Unexpected error processing transcript segments for {video_id}: {type(e_proc).__name__} - {e_proc}", exc_info=True)
                     transcript_text = None # Ensure failure state
                # --- END CORRECTED TRANSCRIPT ITERATION ---

            elif transcript_obj_found and not transcript_lang_found:
                 logger.error(f" Found transcript object for {video_id} but failed to determine language code.")

        # Catch API specific errors cleanly
        except TranscriptsDisabled:
            logger.warning(f"  ⚠️ Transcripts are disabled for video {video_id}")
        except NoTranscriptFound:
             logger.warning(f"  ⚠️ No transcript could be found for {video_id} matching criteria.")
        except CouldNotRetrieveTranscript as e:
             logger.error(f"  ❌ Could not retrieve transcript for {video_id} (network/API issue?): {e}")
        # Catch any other unexpected errors during transcript processing
        except Exception as e:
            logger.error(f"  ❌ Unexpected error during transcript processing phase for {video_id}: {type(e).__name__} - {e}", exc_info=True)


    # --- Save to Database ---
    if not metadata_fetched:
         logger.debug(f"  Skipping DB save for {video_id} as metadata fetch failed or skipped.")
         return False

    # Ensure video_id from metadata matches the requested video_id before saving
    # (Redundant if metadata_fetched check is reliable, but good safeguard)
    if not video_data or video_data.get('video_id') != video_id:
         logger.error(f"  ❌ Metadata inconsistent or missing ID. Requested: {video_id}, Fetched: {video_data.get('video_id')}. Aborting save.")
         return False

    conn = None
    success = False
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        cursor = conn.cursor()

        # Insert/Update Video Metadata
        video_columns = list(video_data.keys())
        video_values = list(video_data.values())
        placeholders = ', '.join(['?'] * len(video_columns))
        safe_columns = [f'"{col}"' for col in video_columns]
        sql_video = f"INSERT OR REPLACE INTO videos ({', '.join(safe_columns)}) VALUES ({placeholders})"
        cursor.execute(sql_video, video_values)
        logger.debug(f"  Saved video metadata for {video_id}")

        # Save transcript only if text was successfully extracted *and* language is known
        if transcript_text and transcript_lang_found:
            sql_transcript = """
                INSERT OR REPLACE INTO transcripts
                (video_id, language, transcript, last_fetched_timestamp)
                VALUES (?, ?, ?, ?)
            """
            cursor.execute(sql_transcript, (
                video_id,
                transcript_lang_found,
                transcript_text,
                datetime.now(timezone.utc).isoformat()
            ))
            logger.debug(f"  Saved transcript for {video_id} ({transcript_lang_found})")
        # Log why transcript wasn't saved if processing failed or result was empty
        # Check transcript_obj_found to distinguish between "not found" and "found but failed processing"
        elif transcript_obj_found is not None and not (transcript_text and transcript_lang_found):
             logger.warning(f"  Did not save transcript for {video_id}; processing failed, result was empty, or language unknown.")

        conn.commit()
        success = True
        log_transcript_state = bool(transcript_text and transcript_lang_found)
        logger.info(f"  ✅ Successfully saved data (Metadata:{metadata_fetched}, Transcript:{log_transcript_state}) for {video_id} to DB.")

    except sqlite3.Error as e:
        logger.error(f"  ❌ Database error saving data for {video_id}: {e}", exc_info=True)
        if conn: conn.rollback()
        success = False
    except Exception as e:
        logger.error(f"  ❌ Unexpected error during DB operation for {video_id}: {type(e).__name__} - {e}", exc_info=True)
        if conn: conn.rollback()
        success = False
    finally:
        if conn:
            try:
                conn.close()
                logger.debug(f" DB connection closed for {video_id}")
            except Exception as close_err:
                 logger.error(f" Error closing DB connection for {video_id}: {close_err}")

    return success