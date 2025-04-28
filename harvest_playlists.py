import sqlite3

conn = sqlite3.connect("youtube.db")
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM playlists")
print(cursor.fetchone())
