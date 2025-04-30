#!/usr/bin/env python3
"""
Export transcript from database to text file.

Usage:
  python export_transcript.py VIDEO_ID [OUTPUT_FILE]

If OUTPUT_FILE is not specified, it will be saved as VIDEO_ID.txt
"""

import sys
import os
import sqlite3
from datetime import datetime

# Configure database path
DB_PATH = os.path.join(os.path.dirname(__file__), "youtube.db")

def get_video_info(video_id):
    """Get video information from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get video info
    cursor.execute("""
        SELECT v.title, v.video_url, v.author, v.publish_date
        FROM videos v
        WHERE v.video_id = ?
    """, (video_id,))
    
    video_info = cursor.fetchone()
    
    # Get transcript
    cursor.execute("""
        SELECT transcript, language
        FROM transcripts
        WHERE video_id = ?
    """, (video_id,))
    
    transcript_info = cursor.fetchone()
    conn.close()
    
    if not video_info:
        return None, None
        
    return video_info, transcript_info

def export_transcript(video_id, output_file=None):
    """Export transcript to a text file"""
    if not output_file:
        output_file = f"{video_id}.txt"
    
    video_info, transcript_info = get_video_info(video_id)
    
    if not video_info:
        print(f"Video with ID {video_id} not found in the database.")
        return False
    
    if not transcript_info:
        print(f"No transcript found for video {video_id}.")
        return False
    
    # Format the output
    content = f"TITLE: {video_info['title']}\n"
    content += f"URL: {video_info['video_url']}\n"
    
    # Add optional metadata as comments
    content += f"# AUTHOR: {video_info['author'] if video_info['author'] else 'Unknown'}\n"
    content += f"# LANGUAGE: {transcript_info['language']}\n"
    content += f"# EXPORTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    if video_info['publish_date']:
        content += f"# PUBLISHED: {video_info['publish_date']}\n"
    
    # Add blank line before transcript
    content += "\n"
    
    # Add transcript
    content += transcript_info['transcript']
    
    # Write to file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Transcript successfully exported to {output_file}")
        return True
    except Exception as e:
        print(f"Error writing to file: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
        
    video_id = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not export_transcript(video_id, output_file):
        sys.exit(1)

if __name__ == "__main__":
    main()
