#!/usr/bin/env python3
"""
Export all transcripts from a playlist to individual text files.

Usage:
  python export_playlist_transcripts.py PLAYLIST_ID [OUTPUT_DIR]

If OUTPUT_DIR is not specified, files will be saved in a directory named after the playlist ID.
"""

import sys
import os
import sqlite3
from datetime import datetime
import shutil
import re

# Configure database path
DB_PATH = os.path.join(os.path.dirname(__file__), "youtube.db")

def get_playlist_info(playlist_id):
    """Get playlist information from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get playlist info
    cursor.execute("""
        SELECT title
        FROM playlists
        WHERE playlist_id = ?
    """, (playlist_id,))
    
    playlist_info = cursor.fetchone()
    
    if not playlist_info:
        print(f"Playlist with ID {playlist_id} not found in the database.")
        conn.close()
        return None, []
    
    # Get videos in playlist with transcripts
    cursor.execute("""
        SELECT v.video_id, v.title, v.video_url, v.author, v.publish_date,
               t.transcript, t.language
        FROM playlist_videos pv
        JOIN videos v ON pv.video_id = v.video_id
        JOIN transcripts t ON v.video_id = t.video_id
        WHERE pv.playlist_id = ?
        ORDER BY pv.position
    """, (playlist_id,))
    
    videos_with_transcripts = cursor.fetchall()
    conn.close()
    
    return playlist_info, videos_with_transcripts

def sanitize_filename(title):
    """Create a safe filename from a title"""
    # Replace problematic characters
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)
    # Limit length
    safe_title = safe_title[:100] if len(safe_title) > 100 else safe_title
    # Ensure it's not empty
    return safe_title if safe_title else "untitled"

def export_playlist_transcripts(playlist_id, output_dir=None):
    """Export all transcripts from a playlist to individual text files"""
    # Get playlist info
    playlist_info, videos = get_playlist_info(playlist_id)
    
    if not playlist_info:
        return False
        
    # Determine output directory
    if not output_dir:
        playlist_title = sanitize_filename(playlist_info['title'])
        output_dir = f"transcripts_{playlist_id}_{playlist_title}"
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")
    
    # Export each transcript
    success_count = 0
    for video in videos:
        video_id = video['video_id']
        video_title = sanitize_filename(video['title'])
        filename = os.path.join(output_dir, f"{video_id}_{video_title}.txt")
        
        # Format the output
        content = f"TITLE: {video['title']}\n"
        content += f"URL: {video['video_url']}\n"
        
        # Add optional metadata as comments
        content += f"# AUTHOR: {video['author'] if video['author'] else 'Unknown'}\n"
        content += f"# LANGUAGE: {video['language']}\n"
        content += f"# EXPORTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        if video['publish_date']:
            content += f"# PUBLISHED: {video['publish_date']}\n"
        
        # Add blank line before transcript
        content += "\n"
        
        # Add transcript
        content += video['transcript']
        
        # Write to file
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Exported: {filename}")
            success_count += 1
        except Exception as e:
            print(f"Error writing to file {filename}: {e}")
    
    print(f"\nExported {success_count} of {len(videos)} transcripts to {output_dir}")
    return success_count > 0

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
        
    playlist_id = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not export_playlist_transcripts(playlist_id, output_dir):
        sys.exit(1)

if __name__ == "__main__":
    main()
