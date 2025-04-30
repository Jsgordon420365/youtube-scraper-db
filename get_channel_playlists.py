#!/usr/bin/env python3
"""
Fetch all playlists from a YouTube channel (handle, user, or ID) and write to JSON.

Usage:
  python get_channel_playlists.py CHANNEL [OUTPUT_JSON]

Examples:
  python get_channel_playlists.py @jsgordon420 playlists.json
  python get_channel_playlists.py https://www.youtube.com/channel/UC… playlists.json
"""
import re
import sys
import json
import logging

try:
    import requests
except ImportError:
    sys.stderr.write("Error: 'requests' library is required. Install via 'pip install requests'\n")
    sys.exit(1)
from pytube import Playlist

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def resolve_channel_url(spec: str) -> str:
    """Resolve a channel handle, user, or ID to a /channel/ URL."""
    # Raw channel ID
    if spec.startswith('UC') and len(spec) > 2:
        return f"https://www.youtube.com/channel/{spec}"
    # Full URL as provided
    if spec.startswith('http'):
        url = spec.split('?')[0].rstrip('/')
    else:
        # Handle shorthand e.g. @handle or user/name
        url = spec if spec.startswith('/') else f"/{spec}"
        url = f"https://www.youtube.com{url}".split('?')[0].rstrip('/')
    # If it's a handle (contains @), fetch page to extract channel ID
    if '/@' in url:
        try:
            headers = { 'User-Agent': 'Mozilla/5.0' }
            r = requests.get(url, headers=headers, timeout=10.0)
            r.raise_for_status()
            # Look for externalId in embedded JSON
            m = re.search(r'externalId"\s*:\s*"(UC[^"]+)', r.text)
            if m:
                channel_id = m.group(1)
                return f"https://www.youtube.com/channel/{channel_id}"
        except Exception as e:
            logger.error(f"Failed to resolve handle {spec}: {e}")
        logger.critical(f"Could not resolve channel ID from handle: {spec}")
        sys.exit(1)
    # Accept /c/, /channel/, /user/ URLs directly
    if any(part in url for part in ['/channel/', '/c/', '/user/']):
        # Normalize to channel ID if user or c
        if '/channel/' in url:
            return url
        # For /c/ or /user/, Pytube.Channel can handle it
        return url
    # Fallback: treat as channel ID
    return f"https://www.youtube.com/channel/{spec}"

def fetch_playlists(channel_url: str) -> list[dict]:
    """Fetch playlist IDs and titles from a channel's /playlists page."""
    playlists_page = channel_url.rstrip('/') + '/playlists'
    logger.info(f"Fetching playlists page: {playlists_page}")
    headers = { 'User-Agent': 'Mozilla/5.0' }
    r = requests.get(playlists_page, headers=headers, timeout=10.0)
    r.raise_for_status()
    html = r.text
    # Find playlist list IDs via href attributes
    ids = re.findall(r'href="/playlist\?list=([A-Za-z0-9_-]+)"', html)
    # Unique preserving order
    seen = set()
    unique_ids = []
    for pid in ids:
        if pid not in seen:
            seen.add(pid)
            unique_ids.append(pid)
    playlists = []
    for pid in unique_ids:
        url = f"https://www.youtube.com/playlist?list={pid}"
        title = ''
        try:
            pl = Playlist(url)
            title = pl.title or ''
        except Exception as e:
            logger.warning(f"Could not fetch title for playlist {pid}: {e}")
        playlists.append({ 'playlist_id': pid, 'title': title, 'url': url })
    return playlists

def main():
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__)
        sys.exit(1)
    spec = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else 'playlists.json'
    channel_url = resolve_channel_url(spec)
    playlists = fetch_playlists(channel_url)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(playlists, f, indent=2, ensure_ascii=False)
    logger.info(f"Wrote {len(playlists)} playlists to {out_file}")

if __name__ == '__main__':
    main()