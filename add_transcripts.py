#!/usr/bin/env python3
"""
Add transcripts to the YouTube database by processing text files.

Usage:
  python add_transcripts.py [VIDEO_ID or URL]

If no argument is provided, the script will:
1. Prompt for a video ID or URL input
2. Process all transcript files in the "./inbox" folder

The script will automatically remove files from the inbox after successful processing.
"""

import sys
import os
import re
import sqlite3
import argparse
import glob
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Constants
DB_PATH = os.path.join(os.path.dirname(__file__), "youtube.db")
INBOX_DIR = os.path.join(os.path.dirname(__file__), "inbox")

def extract_video_id(youtube_url):
    """Extract the YouTube video ID from various URL formats"""
    if not youtube_url:
        return None
        
    # If it's already a video ID (11 characters of letters, numbers, hyphens, and underscores)
    if re.match(r'^[A-Za-z0-9_-]{11}$', youtube_url):
        return youtube_url
        
    # For URLs like: https://www.youtube.com/watch?v=VIDEO_ID
    parsed_url = urlparse(youtube_url)
    if 'youtube.com' in parsed_url.netloc and '/watch' in parsed_url.path:
        query_params = parse_qs(parsed_url.query)
        return query_params.get('v', [None])[0]
    
    # For URLs like: https://youtu.be/VIDEO_ID
    if 'youtu.be' in parsed_url.netloc:
        return parsed_url.path.strip('/')
    
    return None

def has_timestamps(transcript_text):
    """Check if the transcript has timestamps"""
    # Look for time patterns like [00:00] or [00:00:00] or 00:00 - or 00:00:00 -
    timestamp_patterns = [
        r'\[\d{1,2}:\d{2}(:\d{2})?\]',  # [MM:SS] or [HH:MM:SS]
        r'\d{1,2}:\d{2}(:\d{2})?\s+-',   # MM:SS - or HH:MM:SS -
        r'^\d{1,2}:\d{2}(:\d{2})?\s',    # Lines starting with MM:SS or HH:MM:SS
        r'<\d{1,2}:\d{2}(:\d{2})?>'      # <MM:SS> or <HH:MM:SS>
    ]
    
    for pattern in timestamp_patterns:
        if re.search(pattern, transcript_text):
            return True
    
    return False

def process_transcript_file(file_path):
    """Process a transcript file and add it to the database"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse the file content
        lines = content.splitlines()
        title = None
        url = None
        video_id = None
        transcript_start_line = 0
        
        for i, line in enumerate(lines):
            # Extract title
            if line.startswith("TITLE:"):
                title = line[6:].strip()
            # Extract URL and video ID
            elif line.startswith("URL:"):
                url = line[4:].strip()
                video_id = extract_video_id(url)
            # Check if this is an ID line    
            elif line.startswith("ID:"):
                extracted_id = line[3:].strip()
                # Only use this if we haven't found a video ID from the URL
                if not video_id:
                    video_id = extracted_id
            
            # Assume transcript starts after a blank line, following metadata
            if (title or video_id) and line.strip() == "":
                transcript_start_line = i + 1
                break
        
        # Verify we have the necessary information
        if not video_id:
            print(f"Error: Could not find video ID in file: {file_path}")
            return False
            
        if not title:
            title = f"Video {video_id}"
            print(f"Warning: No title found in file: {file_path}. Using '{title}'")
        
        if not url:
            url = f"https://www.youtube.com/watch?v={video_id}"
            print(f"Warning: No URL found in file: {file_path}. Using '{url}'")
        
        # Extract transcript
        transcript = "\n".join(lines[transcript_start_line:])
        if not transcript.strip():
            print(f"Error: No transcript content found in file: {file_path}")
            return False
            
        # Check if this transcript has timestamps
        has_times = has_timestamps(transcript)
        if has_times:
            print(f"Found transcript with timestamps for video {video_id}")
        
        # Add to database
        if save_to_database(video_id, title, url, transcript, has_timestamps=has_times):
            print(f"Successfully processed: {file_path}")
            return True
        else:
            print(f"Failed to save to database: {file_path}")
            return False
        
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return False

def save_to_database(video_id, title, url, transcript, language='en', has_timestamps=False):
    """Save video and transcript to the database"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current time
        timestamp = datetime.now().isoformat()
        
        # Check if video already exists
        cursor.execute("SELECT video_id FROM videos WHERE video_id = ?", (video_id,))
        video_exists = cursor.fetchone() is not None
        
        if video_exists:
            # Update existing video
            cursor.execute(
                """UPDATE videos 
                   SET title = ?, video_url = ?, last_scraped_timestamp = ?
                   WHERE video_id = ?""",
                (title, url, timestamp, video_id)
            )
            print(f"Updated existing video: {title}")
        else:
            # Insert new video
            cursor.execute(
                """INSERT INTO videos 
                   (video_id, title, video_url, last_scraped_timestamp)
                   VALUES (?, ?, ?, ?)""",
                (video_id, title, url, timestamp)
            )
            print(f"Added new video: {title}")
        
        # Check if transcript already exists
        cursor.execute("SELECT video_id, transcript, language FROM transcripts WHERE video_id = ?", (video_id,))
        existing_transcript = cursor.fetchone()
        
        if existing_transcript:
            existing_has_timestamps = has_timestamps(existing_transcript[1])
            
            # Only overwrite if the new transcript has timestamps and the old one doesn't,
            # or if both or neither have timestamps
            if has_timestamps or not existing_has_timestamps:
                cursor.execute(
                    """UPDATE transcripts 
                       SET language = ?, transcript = ?, last_fetched_timestamp = ?
                       WHERE video_id = ?""",
                    (language, transcript, timestamp, video_id)
                )
                print(f"Updated transcript for {video_id}" + 
                      " (overwrote non-timestamped version)" if has_timestamps and not existing_has_timestamps else "")
            else:
                print(f"Kept existing timestamped transcript for {video_id} (new version has no timestamps)")
        else:
            # Insert new transcript
            cursor.execute(
                """INSERT INTO transcripts 
                   (video_id, language, transcript, last_fetched_timestamp)
                   VALUES (?, ?, ?, ?)""",
                (video_id, language, transcript, timestamp)
            )
            print(f"Added new transcript for {video_id}")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def process_inbox_folder():
    """Process all transcript files in the inbox folder"""
    # Create inbox folder if it doesn't exist
    if not os.path.exists(INBOX_DIR):
        os.makedirs(INBOX_DIR)
        print(f"Created inbox directory: {INBOX_DIR}")
        return 0
    
    # Get all text files
    file_patterns = ["*.txt", "*.srt", "*.vtt"]
    files = []
    for pattern in file_patterns:
        files.extend(glob.glob(os.path.join(INBOX_DIR, pattern)))
    
    if not files:
        print(f"No transcript files found in {INBOX_DIR}")
        return 0
    
    print(f"Found {len(files)} transcript files in inbox")
    
    # Process each file
    success_count = 0
    for file_path in files:
        print(f"\nProcessing {os.path.basename(file_path)}...")
        if process_transcript_file(file_path):
            success_count += 1
            # Remove the file after successful processing
            try:
                os.remove(file_path)
                print(f"Removed processed file: {file_path}")
            except Exception as e:
                print(f"Warning: Could not remove file {file_path}: {e}")
    
    print(f"\nSuccessfully processed {success_count} of {len(files)} files from inbox")
    return success_count

def process_single_video(video_input):
    """Process a single video transcript from user input"""
    video_id = extract_video_id(video_input)
    
    if not video_id:
        print(f"Error: Invalid YouTube video ID or URL: {video_input}")
        return False
    
    # Prompt for title and transcript
    print(f"Processing video ID: {video_id}")
    title = input("Enter video title (or press Enter to use video ID as title): ")
    if not title:
        title = f"Video {video_id}"
    
    print("Enter transcript (end with a line containing only '.' or Ctrl+D):")
    transcript_lines = []
    
    try:
        while True:
            line = input()
            if line == '.':
                break
            transcript_lines.append(line)
    except EOFError:
        pass
    
    transcript = '\n'.join(transcript_lines)
    
    if not transcript.strip():
        print("Error: No transcript provided")
        return False
    
    # Save to database
    url = f"https://www.youtube.com/watch?v={video_id}"
    has_times = has_timestamps(transcript)
    if has_times:
        print("Detected transcript with timestamps")
        
    return save_to_database(video_id, title, url, transcript, has_timestamps=has_times)

def main():
    parser = argparse.ArgumentParser(description='Add transcripts to the YouTube database.')
    parser.add_argument('video_id', nargs='?', help='YouTube video ID or URL (optional)')
    args = parser.parse_args()
    
    # Always process the inbox folder
    inbox_count = process_inbox_folder()
    
    # If a video ID/URL was provided, process it
    if args.video_id:
        if process_single_video(args.video_id):
            print(f"Successfully processed video {args.video_id}")
    # If no ID/URL and no files were processed from inbox, prompt user
    elif inbox_count == 0:
        print("\nNo video ID provided and no files in inbox.")
        while True:
            user_input = input("Enter a YouTube video ID/URL or 'q' to quit: ")
            if user_input.lower() == 'q':
                break
            if process_single_video(user_input):
                print(f"Successfully processed video {user_input}")
            
            another = input("Process another video? (y/n): ")
            if another.lower() != 'y':
                break

if __name__ == "__main__":
    main()
