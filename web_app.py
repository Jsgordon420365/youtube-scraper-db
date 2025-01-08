from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('youtube_data.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    videos = conn.execute('SELECT * FROM videos').fetchall()
    conn.close()
    return render_template('index.html', videos=videos)

@app.route('/add', methods=('GET', 'POST'))
def add():
    if request.method == 'POST':
        title = request.form['title']
        url = request.form['url']
        views = request.form['views']
        upload_date = request.form['upload_date']

        conn = get_db_connection()
        conn.execute('INSERT INTO videos (title, url, views, upload_date) VALUES (?, ?, ?, ?)',
                     (title, url, views, upload_date))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    return render_template('add.html')

@app.route('/edit/<int:id>', methods=('GET', 'POST'))
def edit(id):
    conn = get_db_connection()
    video = conn.execute('SELECT * FROM videos WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        title = request.form['title']
        url = request.form['url']
        views = request.form['views']
        upload_date = request.form['upload_date']

        conn.execute('UPDATE videos SET title = ?, url = ?, views = ?, upload_date = ? WHERE id = ?',
                     (title, url, views, upload_date, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('edit.html', video=video)

@app.route('/delete/<int:id>', methods=('POST',))
def delete(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM videos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
