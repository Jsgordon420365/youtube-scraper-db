# gui_app.py
# Streamlit app - Added Video Detail View

import streamlit as st
import sqlite3
import pandas as pd
import os
from config import DB_PATH # Import database path from config.py
import textwrap # For formatting description

# --- Database Connection ---
@st.cache_resource
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    if not os.path.exists(DB_PATH):
        st.error(f"Database file not found at: {DB_PATH}")
        return None
    try:
        # Connect in read-only mode for safety from the GUI
        conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True, check_same_thread=False)
        # Set row_factory to access columns by name
        conn.row_factory = sqlite3.Row
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
    """Loads playlist titles/IDs and checks for processed videos."""
    if not _conn: return pd.DataFrame()
    query = """
    SELECT p.title, p.playlist_id, COUNT(pv.video_id) as video_count
    FROM playlists p LEFT JOIN playlist_videos pv ON p.playlist_id = pv.playlist_id
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
        st.error(f"Error loading playlists: {e}")
        return pd.DataFrame()

@st.cache_data
def load_videos_for_playlist(_conn, playlist_id):
    """Loads essential video details for listing within a playlist."""
    if not _conn or not playlist_id: return pd.DataFrame()
    query = """
    SELECT
        pv.position, v.video_id, v.title, v.author, v.publish_date, v.duration_seconds,
        (SELECT COUNT(*) FROM transcripts t WHERE t.video_id = v.video_id AND t.transcript IS NOT NULL AND t.transcript != '') > 0 as has_transcript
    FROM playlist_videos pv JOIN videos v ON pv.video_id = v.video_id
    WHERE pv.playlist_id = ?
    ORDER BY pv.position ASC, v.publish_date DESC;
    """
    try:
        df_videos = pd.read_sql_query(query, _conn, params=(playlist_id,))
        return df_videos
    except Exception as e:
        st.error(f"Error loading videos for playlist {playlist_id}: {e}")
        return pd.DataFrame()

# --- NEW: Function to load full metadata for ONE video ---
@st.cache_data
def load_video_metadata(_conn, video_id):
    """Loads all metadata for a single video ID."""
    if not _conn or not video_id: return None
    query = "SELECT * FROM videos WHERE video_id = ?"
    try:
        cursor = _conn.cursor()
        result = cursor.execute(query, (video_id,)).fetchone()
        return result # Returns a sqlite3.Row object (acts like a dict) or None
    except Exception as e:
        st.error(f"Error loading metadata for video {video_id}: {e}")
        return None

# --- NEW: Function to load transcript for ONE video ---
@st.cache_data
def load_transcript(_conn, video_id):
    """Loads the transcript text for a single video ID (first language found)."""
    if not _conn or not video_id: return None
    # Fetch the first available transcript for this video ID
    query = "SELECT transcript FROM transcripts WHERE video_id = ? AND transcript IS NOT NULL AND transcript != '' LIMIT 1"
    try:
        cursor = _conn.cursor()
        result = cursor.execute(query, (video_id,)).fetchone()
        return result['transcript'] if result else None # Return text or None
    except Exception as e:
        st.error(f"Error loading transcript for video {video_id}: {e}")
        return None

# --- Helper Function ---
def format_duration(seconds):
    """Formats seconds into HH:MM:SS or MM:SS"""
    if seconds is None: return "N/A"
    try:
        seconds = int(seconds)
        if seconds < 0: return "N/A"
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:01d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    except (ValueError, TypeError):
        return "N/A"


# --- Main App ---
st.set_page_config(layout="wide")
st.title("YouTube Scraper Data Viewer")

conn = get_db_connection()

if conn:
    playlists_df = load_playlists_with_status(conn)

    if not playlists_df.empty:
        # --- Sidebar ---
        st.sidebar.header("Select Playlist")
        playlist_options = playlists_df['display_name'].tolist()
        # Use session state to keep selection stable if possible
        if 'playlist_index' not in st.session_state:
             st.session_state.playlist_index = 0

        selected_display_name = st.sidebar.selectbox(
            "Choose a playlist:",
            options=playlist_options,
            index=st.session_state.playlist_index,
            key="playlist_selector"
        )
        # Update session state index if selection changes
        st.session_state.playlist_index = playlist_options.index(selected_display_name)

        selected_row = playlists_df[playlists_df['display_name'] == selected_display_name].iloc[0]
        selected_playlist_id = selected_row['playlist_id']
        selected_playlist_title = selected_row['title'] if pd.notna(selected_row['title']) and selected_row['title'].strip() else f"ID: {selected_playlist_id}"

        # --- Main Area ---
        st.header(f"Videos in Playlist: {selected_playlist_title}")
        st.caption(f"Playlist ID: {selected_playlist_id}")

        videos_df = load_videos_for_playlist(conn, selected_playlist_id)

        if not videos_df.empty:
            st.info(f"Found {len(videos_df)} videos processed for this playlist.")
            st.markdown("Click on a video title below to view details.")

            # --- Display Videos with Expanders ---
            for index, video in videos_df.iterrows():
                video_id = video['video_id']
                video_title = video['title'] if pd.notna(video['title']) and video['title'].strip() else f"Video ID: {video_id}"
                has_transcript_flag = video['has_transcript']

                # Use an expander for each video
                with st.expander(f"{video_title} {'(📄)' if has_transcript_flag else ''}"):
                    st.subheader("Details")
                    # Load full metadata only when expanded
                    metadata = load_video_metadata(conn, video_id)
                    if metadata:
                        # Display Metadata
                        col1, col2 = st.columns([3, 1]) # Create columns for layout
                        with col1:
                             st.markdown(f"**Title:** {metadata['title']}")
                             st.markdown(f"**Channel:** {metadata['author']}")
                             # Make video URL clickable, opening in new tab
                             if metadata['video_url']:
                                 st.markdown(f"**URL:** [{metadata['video_url']}]({metadata['video_url']})", unsafe_allow_html=True) # Target _blank implied
                                 # Or use link_button: st.link_button("Open Video", metadata['video_url'])
                             st.markdown(f"**Video ID:** `{metadata['video_id']}`")
                        with col2:
                             st.markdown(f"**Published:** {metadata['publish_date'] if metadata['publish_date'] else 'N/A'}")
                             st.markdown(f"**Duration:** {format_duration(metadata['duration_seconds'])}")
                             st.markdown(f"**Views:** {metadata['view_count']:,}" if metadata['view_count'] is not None else 'N/A')
                             st.markdown(f"**Metadata Scraped:** {metadata['metadata_last_scraped_timestamp'][:19]}" if metadata.get('metadata_last_scraped_timestamp') else 'N/A')

                        # Display Description (use textwrap and markdown/code block)
                        if metadata['description']:
                            st.subheader("Description")
                            # Use markdown with <pre> for better formatting control, or st.text_area
                            # wrapped_description = textwrap.fill(metadata['description'], width=100) # Adjust width as needed
                            # st.text_area("Description", wrapped_description, height=200, disabled=True)
                            st.markdown(f"```\n{metadata['description']}\n```") # Code block preserves formatting
                        else:
                            st.markdown("*No description available.*")

                        # Load and Display Transcript
                        transcript = load_transcript(conn, video_id)
                        st.subheader("Transcript")
                        if transcript:
                            st.text_area("Transcript Text", transcript, height=300, disabled=True, key=f"transcript_{video_id}")
                            # Placeholder for future: Add Edit button here
                        else:
                            # Check if scraper *tried* to get it vs transcript disabled
                            # This requires status column added later. For now:
                            st.markdown("*Transcript not found or not available.*")

                    else:
                        st.error(f"Could not load metadata for video ID: {video_id}")
        else:
            if selected_row['video_count'] > 0:
                st.warning("Found links for videos, but failed to load details (scraper might be processing).")
            else:
                st.info("No videos processed for this playlist yet.")
    else:
        st.warning("Could not load playlists. Ensure `import_playlists.py` ran.")
else:
    st.error("Application could not connect to the database.")