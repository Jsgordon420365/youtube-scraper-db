# gui_app.py
# Streamlit app - Added Playlist Selection

import streamlit as st
import sqlite3
import pandas as pd
import os
from config import DB_PATH # Import database path from config.py

# --- Database Connection ---
@st.cache_resource # Cache the connection itself
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    if not os.path.exists(DB_PATH):
        # Use st.error for user-facing errors in the app
        st.error(f"Database file not found at: {DB_PATH}")
        # Returning None or raising an exception might be better than st.stop() in a cached function
        return None
    try:
        # Connect using the DB_PATH from config.py
        conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True, check_same_thread=False) # Read-only mode for safety?
        # conn = sqlite3.connect(DB_PATH, check_same_thread=False) # Original read-write connection
        return conn
    except sqlite3.Error as e:
        st.error(f"Database connection error: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred connecting to the database: {e}")
        return None

# --- Data Loading Functions ---
# Cache the data loading functions to avoid re-running queries unnecessarily.
# Use a Time-To-Live (ttl) if data might change frequently while the app is open.
# @st.cache_data(ttl=60) # Cache for 60 seconds, for example
@st.cache_data # Basic caching, rerun if code changes
def load_playlists(_conn):
    """Loads playlist titles and IDs from the database."""
    if not _conn:
        return pd.DataFrame() # Return empty DataFrame if no connection
    try:
        # Query the playlists table
        df_playlists = pd.read_sql_query(
            "SELECT title, playlist_id FROM playlists ORDER BY title",
            _conn
        )
        # Add a 'display_name' column for the selectbox if titles might be missing
        df_playlists['display_name'] = df_playlists.apply(lambda row: row['title'] if row['title'] else f"ID: {row['playlist_id']}", axis=1)
        return df_playlists
    except Exception as e:
        st.error(f"Error loading playlists: {e}")
        return pd.DataFrame() # Return empty DataFrame on error

# --- Main App ---
st.set_page_config(layout="wide")
st.title("YouTube Scraper Data Viewer")

conn = get_db_connection()

if conn:
    # Load playlists into a DataFrame
    playlists_df = load_playlists(conn)

    if not playlists_df.empty:
        st.success(f"Successfully connected to DB and loaded {len(playlists_df)} playlists.")

        # --- Sidebar for Playlist Selection ---
        st.sidebar.header("Select Playlist")
        # Create a list of playlist display names for the selectbox
        playlist_options = playlists_df['display_name'].tolist()
        selected_display_name = st.sidebar.selectbox(
            "Choose a playlist:",
            options=playlist_options,
            index=0 # Default to the first playlist
        )

        # Find the playlist_id corresponding to the selected display name
        selected_playlist_id = playlists_df.loc[playlists_df['display_name'] == selected_display_name, 'playlist_id'].iloc[0]

        # --- Main Area ---
        st.markdown("---")
        st.header(f"Videos in Playlist: {selected_display_name}")
        st.caption(f"Playlist ID: {selected_playlist_id}")

        # --- Placeholder for Video List / Details ---
        st.write("(Video list and details will appear here)")

    else:
        st.warning("Successfully connected to DB, but failed to load any playlists or playlist table is empty.")
        st.info("Make sure `import_playlists.py` has run successfully.")

else:
    # Error message is handled within get_db_connection if it returns None
    st.error("Application could not connect to the database.")