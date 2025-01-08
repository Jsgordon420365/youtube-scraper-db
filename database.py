import sqlite3

def create_database():
    conn = sqlite3.connect('youtube_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY,
            title TEXT,
            url TEXT,
            views TEXT,
            upload_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_video(title, url, views, upload_date):
    conn = sqlite3.connect('youtube_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO videos (title, url, views, upload_date)
        VALUES (?, ?, ?, ?)
    ''', (title, url, views, upload_date))
    conn.commit()
    conn.close()

def update_video(video_id, title=None, url=None, views=None, upload_date=None):
    conn = sqlite3.connect('youtube_data.db')
    cursor = conn.cursor()
    query = 'UPDATE videos SET '
    params = []
    if title:
        query += 'title = ?, '
        params.append(title)
    if url:
        query += 'url = ?, '
        params.append(url)
    if views:
        query += 'views = ?, '
        params.append(views)
    if upload_date:
        query += 'upload_date = ? '
        params.append(upload_date)
    query = query.rstrip(', ')
    query += ' WHERE id = ?'
    params.append(video_id)
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def query_videos():
    conn = sqlite3.connect('youtube_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM videos')
    rows = cursor.fetchall()
    conn.close()
    return rows
