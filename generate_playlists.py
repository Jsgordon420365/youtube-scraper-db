#!/usr/bin/env python3
"""Generate playlists.json by exporting playlist entries from a Google Sheet."""

import os
import sys
import json

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Configuration
CREDENTIALS_FILE = "axiomatic-genre-455219-i8-02643c013f6e.json"
SPREADSHEET_NAME = "YouTube Playlist Scraper"
WORKSHEET_INDEX = 0
OUTPUT_JSON = "playlists.json"

def main():
    # Check for credentials file
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Credentials file '{CREDENTIALS_FILE}' not found.", file=sys.stderr)
        sys.exit(1)

    # Authenticate with Google Sheets API
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)

    # Open the target worksheet
    try:
        sheet = client.open(SPREADSHEET_NAME).get_worksheet(WORKSHEET_INDEX)
    except Exception as e:
        print(f"Error opening spreadsheet '{SPREADSHEET_NAME}': {e}", file=sys.stderr)
        sys.exit(1)

    # Fetch all records
    records = sheet.get_all_records()
    playlists = []
    for rec in records:
        # Support fields 'id' or 'playlist_id'
        playlist_id = rec.get("id") or rec.get("playlist_id") or rec.get("playlistId")
        title = rec.get("title") or rec.get("name")
        if not playlist_id or not title:
            print(f"Skipping row with missing id/title: {rec}", file=sys.stderr)
            continue
        # Construct URL if not provided
        url = rec.get("url") or f"https://www.youtube.com/playlist?list={playlist_id}"
        playlists.append({"id": playlist_id, "title": title, "url": url})

    if not playlists:
        print("No valid playlist entries found.", file=sys.stderr)
        sys.exit(1)

    # Write output JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(playlists, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(playlists)} playlists to '{OUTPUT_JSON}'.")

if __name__ == "__main__":
    main()