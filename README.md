# YouTube Scraper & Transcript Manager

A comprehensive tool for scraping, managing, and exploring YouTube playlists, videos, and transcripts.

## Overview

This project allows you to:
1. Scrape your YouTube channel playlists and videos
2. Store video metadata and transcripts in a SQLite database
3. Browse and search your video collection through a web interface
4. Add transcripts manually or through text files
5. Export transcripts for editing or sharing

## Getting Started

### Prerequisites
- Python 3.8 or higher
- Virtual environment (recommended)

### Installation

1. Clone this repository:
```
git clone <repository-url>
cd yt_scraper
```

2. Create and activate a virtual environment:
```
python -m venv venv
venv\Scripts\activate
```

3. Install required packages:
```
pip install -r requirements.txt
pip install -r streamlit_requirements.txt
```

## Quick Start Guide

The project includes several batch files for easy use:

- `update_youtube_data.bat` - Scrape YouTube data and update the database
- `run_streamlit_app.bat` - Launch the web interface to explore your data
- `process_transcripts.bat` - Process transcript files from the inbox folder
- `export_tools.bat` - Export transcripts from the database

## Components

### 1. Data Collection

#### Automatic Scraping
- `scrape_my_channel.py` - Scrape playlists and videos from a YouTube channel
- `main_scraper.py` - Update existing playlists and videos
- `youtube_utils.py` - Core functions for interacting with YouTube

#### Manual Addition
- `add_transcripts.py` - Add transcripts from text files or manual input
- `process_transcripts.bat` - Batch script for processing transcript files

### 2. Data Visualization

- `display.py` - Streamlit application for browsing and searching data
- `run_streamlit_app.bat` - Script to start the Streamlit app

### 3. Data Export

- `export_transcript.py` - Export a single video transcript
- `export_playlist_transcripts.py` - Export all transcripts from a playlist
- `export_tools.bat` - Menu-driven interface for export functions

## Usage Instructions

### Scraping YouTube Data

1. Run `update_youtube_data.bat`
2. The script will:
   - Check for dependencies
   - Initialize the database if needed
   - Scrape your channel playlists
   - Fetch video metadata and transcripts

### Exploring Your Data

1. Run `run_streamlit_app.bat`
2. The web interface provides:
   - Dashboard with statistics
   - Playlist browser
   - Search functionality for videos and transcripts
   - Video details viewer with transcripts

### Adding Transcripts Manually

#### Option 1: Using the Inbox Folder
1. Place transcript files in the `inbox` folder
2. Files should follow this format:
```
TITLE: Video Title
URL: https://www.youtube.com/watch?v=VIDEO_ID

Transcript content here...
```
3. Run `process_transcripts.bat`
4. Files will be processed and removed upon success

#### Option 2: Command Line
```
process_transcripts.bat https://www.youtube.com/watch?v=VIDEO_ID
```

#### Option 3: Using the Web Interface
1. Launch the Streamlit app with `run_streamlit_app.bat`
2. Navigate to the "Add Video" tab
3. Upload a transcript file or enter details manually

### Working with Timestamped Transcripts

The system prioritizes transcripts with timestamps. Timestamp formats:
- `[00:00]` format (square brackets)
- `00:00 - ` format (timestamp followed by dash)
- Lines starting with timestamps
- `<00:00>` format (angle brackets)

Example of a transcript with timestamps:
```
TITLE: Video Title
URL: https://www.youtube.com/watch?v=VIDEO_ID

[00:00] Introduction to the topic
[01:30] Main points discussion
[05:45] Conclusion and summary
```

### Exporting Transcripts

1. Run `export_tools.bat`
2. Choose from:
   - Export a single video transcript
   - Export all transcripts from a playlist

Exported transcripts are formatted for easy re-importing.

## Database Structure

The SQLite database (`youtube.db`) contains these main tables:
- `playlists` - Information about YouTube playlists
- `videos` - Video metadata
- `playlist_videos` - Relationship between playlists and videos
- `transcripts` - Video transcripts

## Project Structure

```
yt_scraper/
├── inbox/                # Place transcript files here for processing
├── venv/                 # Virtual environment (not tracked in git)
│
├── update_youtube_data.bat    # Scrape YouTube data
├── run_streamlit_app.bat      # Launch web interface
├── process_transcripts.bat    # Process transcript files
├── export_tools.bat           # Export transcripts
│
├── scrape_my_channel.py       # Channel scraper
├── main_scraper.py            # Update playlists and videos
├── youtube_utils.py           # YouTube utility functions
│
├── add_transcripts.py         # Process transcript files
├── display.py                 # Streamlit web interface
│
├── export_transcript.py       # Export single transcript
├── export_playlist_transcripts.py  # Export playlist transcripts
│
├── requirements.txt           # Core dependencies
├── streamlit_requirements.txt # Web interface dependencies
│
├── README.md                  # This file
└── youtube.db                 # SQLite database (not tracked in git)
```

## Tips and Tricks

1. **Timestamped Transcripts**: Always use timestamps when possible - they make navigation easier and are prioritized by the system.

2. **Batch Processing**: Drop multiple transcript files in the `inbox` folder for efficient batch processing.

3. **Regular Updates**: Run `update_youtube_data.bat` periodically to keep your database up-to-date with YouTube.

4. **Database Backup**: Export important transcripts occasionally as a backup using the export tools.

5. **Search Optimization**: When searching transcripts, try different phrases as the search is literal (not semantic).

## Troubleshooting

- **Missing Dependencies**: Run `pip install -r requirements.txt` and `pip install -r streamlit_requirements.txt`
- **Database Issues**: If the database gets corrupted, delete `youtube.db` and run `update_youtube_data.bat` to rebuild it
- **Scraping Failures**: YouTube may rate-limit frequent requests - wait and try again later
- **Transcript Processing Errors**: Check the format of your transcript files against the sample file

## License

This project is provided as-is for personal use.

## Acknowledgments

- Built with Python, SQLite, Streamlit, pytube, yt-dlp, and youtube-transcript-api
