import sqlite3
from flask import Flask, jsonify, render_template
from config import DB_PATH

# Initialize Flask app with custom template and static folders
app = Flask(__name__, template_folder='templates', static_folder='static')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')
@app.route('/playlist')
def playlist_page():
    return render_template('playlist.html')

@app.route('/video')
def video_page():
    return render_template('video.html')

@app.route('/api/playlists')
def api_playlists():
    conn = get_db_connection()
    playlists = conn.execute(
        """
        SELECT p.playlist_id, p.title, p.url,
               (SELECT COUNT(*) FROM playlist_videos pv WHERE pv.playlist_id = p.playlist_id) AS song_count,
               (SELECT MIN(v.publish_date) FROM videos v
                   JOIN playlist_videos pv2 ON pv2.video_id = v.video_id
                   AND pv2.playlist_id = p.playlist_id
               ) AS date_created,
               (SELECT MAX(v.last_scraped_timestamp) FROM videos v
                   JOIN playlist_videos pv3 ON pv3.video_id = v.video_id
                   AND pv3.playlist_id = p.playlist_id
               ) AS date_updated
        FROM playlists p
        """
    ).fetchall()
    conn.close()
    return jsonify([dict(p) for p in playlists])

@app.route('/api/playlists/<playlist_id>/videos')
def api_playlist_videos(playlist_id):
    conn = get_db_connection()
    rows = conn.execute(
        'SELECT v.video_id, v.title, v.publish_date, v.duration_seconds, v.view_count'
        ' FROM videos v JOIN playlist_videos pv'
        ' ON pv.video_id = v.video_id'
        ' WHERE pv.playlist_id = ?'
        ' ORDER BY pv.position',
        (playlist_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/videos/<video_id>')
def api_video(video_id):
    conn = get_db_connection()
    video = conn.execute(
        'SELECT * FROM videos WHERE video_id = ?', (video_id,)
    ).fetchone()
    transcript = conn.execute(
        'SELECT language, transcript FROM transcripts WHERE video_id = ?', (video_id,)
    ).fetchone()
    conn.close()
    if not video:
        return jsonify({'error': 'Video not found'}), 404
    result = dict(video)
    if transcript:
        result['transcript'] = transcript['transcript']
        result['transcript_language'] = transcript['language']
    return jsonify(result)

if __name__ == '__main__':
    # Run development server
    app.run(host='0.0.0.0', port=8000, debug=True)