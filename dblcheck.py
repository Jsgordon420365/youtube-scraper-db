import sqlite3

conn = sqlite3.connect("youtube.db")
cursor = conn.cursor()

for row in cursor.execute("SELECT title, playlist_id FROM playlists LIMIT 10"):
    print(row)
