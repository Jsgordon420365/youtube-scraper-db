# YouTube Scraper & Transcript Manager

A comprehensive system for scraping, managing, and searching YouTube videos, playlists, and transcripts.

## Features

- **Scrape YouTube Data**: Automatically fetch videos, metadata, and transcripts from your playlists
- **Searchable Database**: Browse your playlists and search through video transcripts
- **Interactive Dashboard**: Visualize statistics about your YouTube data
- **Transcript Management**: Add, update, and export transcripts with support for timestamps
- **Batch Processing**: Process multiple files through an inbox system
- **Command Line Interface**: Run tools via command line or interactive mode

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Required Python packages (install with `pip install -r requirements.txt`):
  - pytube
  - yt-dlp
  - youtube-transcript-api
  - streamlit
  - pandas
  - plotly
  - requests

### Installation

1. Clone this repository or download the files
2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Scraping YouTube Data

Run the automatic scraper to fetch your YouTube playlists and videos:

```
.\update_youtube_data.bat
```

This will:
1. Check for required dependencies
2. Initialize the database if needed
3. Scrape your channel playlists
4. Download video metadata and transcripts

### Exploring Your Data

Launch the interactive Streamlit app:

```
.\run_streamlit_app.bat
```

Features:
- Dashboard with statistics
- Playlist browser
- Video search
- Transcript viewer
- Manual video/transcript addition

### Managing Transcripts

#### Adding Transcripts

1. **Inbox System**:
   - Place transcript files in the `inbox` folder
   - Run `.\process_transcripts.bat`
   - Files will be processed and removed when done

2. **Command Line**:
   ```
   .\process_transcripts.bat VIDEO_ID
   ```
   or
   ```
   .\process_transcripts.bat https://www.youtube.com/watch?v=VIDEO_ID
   ```

3. **Interactive Mode**:
   - Run `.\process_transcripts.bat` without arguments
   - Follow the prompts to enter video IDs/URLs

#### Transcript File Format

```
TITLE: Your Video Title Here
URL: https://www.youtube.com/watch?v=VIDEO_ID

[00:00] Transcript content with timestamps
[00:15] More content...
```

The system supports various timestamp formats:
- `[00:00]` (square brackets)
- `00:00 - ` (timestamp with dash)
- `<00:00>` (angle brackets)
- Lines starting with timestamps

**Note**: Transcripts with timestamps are always preferred over non-timestamped versions.

#### Exporting Transcripts

Use the export tools to save transcripts for editing:

```
.\export_tools.bat
```

Options:
1. Export a single video transcript
2. Export all transcripts from a playlist

## File Structure

- `youtube.db`: SQLite database storing all data
- `main_scraper.py`: Core scraping functionality
- `youtube_utils.py`: Utilities for interacting with YouTube
- `display.py`: Streamlit app for browsing and searching
- `add_transcripts.py`: Script for adding transcripts
- `export_transcript.py`: Export single transcript
- `export_playlist_transcripts.py`: Export all transcripts from a playlist
- `inbox/`: Directory for batch processing transcript files

## Batch Files

- `update_youtube_data.bat`: Run the YouTube scraper
- `run_streamlit_app.bat`: Launch the interactive app
- `process_transcripts.bat`: Process transcripts from inbox or command line
- `export_tools.bat`: Export transcripts to files

## Database Schema

- **playlists**: Information about YouTube playlists
- **videos**: Video metadata (title, author, duration, etc.)
- **transcripts**: Video transcripts with timestamps
- **playlist_videos**: Links videos to playlists

## Tips & Tricks

- Always use timestamps in your transcripts for better searchability
- The inbox system is useful for batch processing multiple files
- Use the Streamlit app to quickly find specific content in your videos
- Export transcripts before making major edits, then re-import them

## Troubleshooting

- If scraping fails, check your internet connection
- If transcripts aren't being found, try manually adding them
- Ensure transcript files follow the correct format
- Check the log files for detailed error messages

## License

This project is for personal use only.
