import sqlite3
from flask import Flask, render_template, jsonify # Added jsonify for later API calls
import logging

# Assuming config.py is in the same directory or Python path
try:
    from config import DB_PATH
except ImportError:
    logging.error("FATAL ERROR: Could not import DB_PATH from config.py. Ensure config.py exists.")
    exit(1) # Can't run without DB path

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Database Helper Functions ---
def get_db_connection():
    """Establishes a read-only connection to the database."""
    try:
        # Connect in read-only mode ('ro')
        conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
        logger.debug("Read-only DB connection established.")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error (read-only): {e}")
        return None

def get_all_playlists():
    """Fetches all playlists ordered by title."""
    conn = get_db_connection()
    playlists = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT playlist_id, title FROM playlists ORDER BY title COLLATE NOCASE")
            playlists = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Fetched {len(playlists)} playlists from DB.")
        except sqlite3.Error as e:
            logger.error(f"Error fetching playlists: {e}")
        finally:
            conn.close()
            logger.debug("Read-only DB connection closed.")
    return playlists

# --- Flask Routes ---
@app.route('/')
def index():
    """Main route to display the viewer page."""
    playlists = get_all_playlists()
    return render_template('index.html', playlists=playlists)

# --- Run the App ---
if __name__ == '__main__':
    # Use host='0.0.0.0' to make it accessible on the network
    # Use debug=True for development (auto-reloads, provides debugger)
    # Be cautious using debug=True in production
    app.run(debug=True, host='0.0.0.0', port=5001) # Use a port other than default 5000 if needed 