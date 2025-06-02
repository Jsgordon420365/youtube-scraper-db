import sqlite3
from config import DB_PATH

def get_all_playlists():
    """Fetches all playlists from the database."""
    try:
        conn = sqlite3.connect(
            f'file:{DB_PATH}?mode=ro', uri=True, check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT playlist_id, title FROM playlists ORDER BY title COLLATE NOCASE"
        )
        playlists = [dict(row) for row in cursor.fetchall()]
        return playlists
    except sqlite3.Error as e:
        print(f"Error fetching playlists from database: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()
