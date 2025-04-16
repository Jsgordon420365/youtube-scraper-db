# gui_app.py
# Streamlit app - Fixed serialization error for cached functions

import streamlit as st
import sqlite3
import pandas as pd
import os
import webbrowser
from config import DB_PATH # Import database path from config.py

# --- Database Connection ---
@st.cache_resource
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    db_file = os.path.abspath(DB_PATH)
    if not os.path.exists(db_file):
        st.error(f"Database file not found at: {db_file}")
        return None
    try:
        conn = sqlite3.connect(f'file:{db_file}?mode=ro', uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
        return conn
    except sqlite3.Error as e:
        st.error(f"Database connection error: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred connecting to the database: {e}")
        return None

# --- Data Loading Functions ---
@st.cache_data
def load_playlists_with_status(_conn):
    """Loads playlist titles/IDs and checks if any videos have been processed."""
    if not _conn: return pd.DataFrame()
    query = """
    SELECT p.title, p.playlist_id, COUNT(pv.video_id) as video_count
    FROM playlists p
    LEFT JOIN playlist_videos pv ON p.playlist_id = pv.playlist_id
    GROUP BY p.playlist_id, p.title ORDER BY p.title COLLATE NOCASE;
    """
    try:
        df_playlists = pd.read_sql_query(query, _conn)
        def create_display_name(row):
            base_title = row['title'] if pd.notna(row['title']) and row['title'].strip() else f"ID: {row['playlist_id']}"
            return f"✅ {base_title}" if row['video_count'] > 0 else base_title
        df_playlists['display_name'] = df_playlists.apply(create_display_name, axis=1)
        return df_playlists
    except Exception as e:
        st.error(f"Error loading playlists with status: {e}")
        return pd.DataFrame()

@st.cache_data
def load_videos_for_playlist(_conn, playlist_id):
    """Loads video list (ID, Title) for a given playlist ID."""
    if not _conn or not playlist_id: return pd.DataFrame()
    query = """
    SELECT
        pv.position, v.video_id, v.title, v.video_url, v.author,
        CASE WHEN t.video_id IS NOT NULL THEN '✅' ELSE ' ' END as transcript_status
    FROM playlist_videos pv
    JOIN videos v ON pv.video_id = v.video_id
    LEFT JOIN transcripts t ON v.video_id = t.video_id AND t.transcript IS NOT NULL AND t.transcript != ''
    WHERE pv.playlist_id = ?
    GROUP BY pv.playlist_id, v.video_id
    ORDER BY pv.position ASC, v.publish_date DESC;
    """
    try:
        df_videos = pd.read_sql_query(query, _conn, params=(playlist_id,))
        return df_videos
    except Exception as e:
        st.error(f"Error loading videos for playlist {playlist_id}: {e}")
        return pd.DataFrame()

@st.cache_data
def load_video_metadata(_conn, video_id):
    """Loads all metadata for a specific video ID."""
    if not _conn or not video_id: return None
    try:
        cursor = _conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,))
        video_data = cursor.fetchone()
        # Ensure conversion to dict happens reliably
        return dict(video_data) if video_data else None
    except Exception as e:
        st.error(f"Error loading metadata for video {video_id}: {e}")
        return None

@st.cache_data
def load_transcript(_conn, video_id):
    """Loads transcript text for a specific video ID."""
    if not _conn or not video_id: return None
    try:
        cursor = _conn.cursor()
        cursor.execute("SELECT transcript, language FROM transcripts WHERE video_id = ? LIMIT 1", (video_id,))
        transcript_data = cursor.fetchone()
        # --- FIX: Convert sqlite3.Row to dict before returning ---
        return dict(transcript_data) if transcript_data else None
    except Exception as e:
        st.error(f"Error loading transcript for video {video_id}: {e}")
        return None

# --- Main App ---
st.set_page_config(layout="wide")
st.title("YouTube Scraper Data Viewer")

# Initialize session state
if 'selected_video_id' not in st.session_state:
    st.session_state.selected_video_id = None

conn = get_db_connection()

if conn:
    playlists_df = load_playlists_with_status(conn)

    if not playlists_df.empty:
        # --- Sidebar ---
        st.sidebar.header("Select Playlist")
        playlist_options = playlists_df['display_name'].tolist()
        # Check if previous selection is still valid, otherwise reset index
        try:
            current_index = playlist_options.index(st.session_state.get("playlist_selector", playlist_options[0]))
        except ValueError:
            current_index = 0 # Default to first item if previous selection invalid

        selected_display_name = st.sidebar.selectbox(
            "Choose a playlist:", options=playlist_options, index=current_index, key="playlist_selector"
        )

        # Clear selected video when playlist changes
        if st.session_state.get("current_playlist_display_name") != selected_display_name:
            st.session_state.selected_video_id = None
            st.session_state.current_playlist_display_name = selected_display_name # Store current selection

        selected_row = playlists_df[playlists_df['display_name'] == selected_display_name].iloc[0]
        selected_playlist_id = selected_row['playlist_id']
        selected_playlist_title = selected_row['title'] if pd.notna(selected_row['title']) and selected_row['title'].strip() else f"ID: {selected_playlist_id}"

        # --- Main Area ---
        st.header(f"Playlist: {selected_playlist_title}")
        st.caption(f"ID: {selected_playlist_id}")
        st.markdown("---")

        # --- Load and Display Video List ---
        videos_df = load_videos_for_playlist(conn, selected_playlist_id)

        if not videos_df.empty:
            st.subheader(f"Videos ({len(videos_df)})")
            col1, col2 = st.columns([3, 1])
            with col1: st.write("**Title / Channel**")
            with col2: st.write("**Actions**")

            for index, row_data in videos_df.iterrows():
                # Convert pandas row Series to dictionary for easier access
                row = row_data.to_dict()
                video_title = row.get('title', f"ID: {row.get('video_id', 'N/A')}")
                video_id = row.get('video_id')
                video_url = row.get('video_url')
                author = row.get('author', "Unknown Channel")
                transcript_indicator = row.get('transcript_status', ' ')

                if not video_id: continue # Skip if video_id is missing for some reason

                colA, colB = st.columns([3, 1])
                with colA:
                     link = f"[{transcript_indicator} {video_title}]({video_url})" if video_url else f"{transcript_indicator} {video_title}"
                     st.markdown(link, unsafe_allow_html=False)
                     st.caption(f"{author} ({video_id})")
                with colB:
                     if st.button("View Details", key=f"view_{video_id}"):
                          st.session_state.selected_video_id = video_id
                          # Optionally use st.rerun() here if needed, but often state updates handle it

            st.markdown("---")

            # --- Display Selected Video Details ---
            if st.session_state.selected_video_id:
                st.subheader("Selected Video Details")
                # Load data using the selected ID from session state
                video_meta = load_video_metadata(conn, st.session_state.selected_video_id)
                transcript_data = load_transcript(conn, st.session_state.selected_video_id)

                if video_meta:
                    # Display metadata fields safely using .get()
                    st.markdown(f"**Title:** {video_meta.get('title', 'N/A')}")
                    st.markdown(f"**Video ID:** {video_meta.get('video_id')}")
                    st.markdown(f"**Channel:** {video_meta.get('author', 'N/A')} ({video_meta.get('channel_id', 'N/A')})")
                    st.markdown(f"**Published:** {video_meta.get('publish_date', 'N/A')}")
                    duration_s = video_meta.get('duration_seconds')
                    duration_str = f"{duration_s // 60}m {duration_s % 60}s" if isinstance(duration_s, (int, float)) else "N/A"
                    st.markdown(f"**Duration:** {duration_str}")
                    st.markdown(f"**Views:** {video_meta.get('view_count', 'N/A')}")
                    vid_url = video_meta.get('video_url')
                    if vid_url: st.markdown(f"**Video URL:** [{vid_url}]({vid_url})")
                    thumb_url = video_meta.get('thumbnail_url')
                    if thumb_url: st.image(thumb_url, caption="Thumbnail")

                    with st.expander("Description", expanded=False): # Keep collapsed initially
                        st.markdown(video_meta.get('description', '*No description available.*'))

                    with st.expander("Transcript", expanded=True): # Expand transcript by default
                        if transcript_data:
                            st.caption(f"Language: {transcript_data.get('language', 'N/A')}")
                            st.text_area("", value=transcript_data.get('transcript', 'No transcript text found.'), height=300, disabled=True, label_visibility="collapsed")
                        else:
                            st.info("Transcript not found or not scraped for this video.")
                else:
                    st.error(f"Could not load metadata for selected video ID: {st.session_state.selected_video_id}")

        else:
            if selected_row['video_count'] > 0:
                st.warning("Links found, but failed to load video details.")
            else:
                st.info("No videos processed for this playlist yet.")

    else:
        st.warning("Connected to DB, but failed to load playlists.")
        st.info("Make sure `import_playlists.py` ran.")

else:
    st.error("Application could not connect to the database.")