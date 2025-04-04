# ver 20250329183600.0

import json
import os

PLAYLISTS_FILE = "playlists.json"

def load_playlists() -> list[dict]:
    if not os.path.exists(PLAYLISTS_FILE):
        raise FileNotFoundError(f"{PLAYLISTS_FILE} not found.")
    with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_all_playlists() -> list[dict]:
    return load_playlists()
