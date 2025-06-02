import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import os
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Constants
DB_PATH = os.path.join(os.path.dirname(__file__), "youtube.db")

# Set page configuration
st.set_page_config(
    page_title="YouTube Data Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Robust DB Connection and Table Check ---
def get_db_connection():
    db_file = os.path.abspath(DB_PATH)
    if not os.path.exists(db_file):
        st.error(f"Database file not found at: {db_file}")
        return None
    try:
        conn = sqlite3.connect(f'file:{db_file}?mode=ro', uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        st.error(f"Database connection error: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error connecting to DB: {e}")
        return None

def table_exists(conn, table_name):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cursor.fetchone() is not None
    except Exception:
        return False

# Create a connection to the database
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def get_transcript(conn, video_id):
    try:
        if not table_exists(conn, 'transcripts'):
            st.error("Transcripts table missing.")
            return None
        query = """
        SELECT video_id, language, transcript, last_fetched_timestamp
        FROM transcripts
        WHERE video_id = ?
        """
        df = pd.read_sql_query(query, conn, params=(video_id,))
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except Exception as e:
        st.error(f"Error loading transcript: {e}")
        return None

def get_playlists(conn):
    try:
        if not table_exists(conn, 'playlists') or not table_exists(conn, 'playlist_videos'):
            st.error("Required tables missing for playlists page.")
            return pd.DataFrame()
        query = """
        SELECT p.playlist_id, p.title, p.url, \
               COUNT(pv.video_id) as video_count,\
               p.last_updated
        FROM playlists p
        LEFT JOIN playlist_videos pv ON p.playlist_id = pv.playlist_id
        GROUP BY p.playlist_id
        ORDER BY video_count DESC
        """
        return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error loading playlists: {e}")
        return pd.DataFrame()

def get_playlist_videos(conn, playlist_id):
    try:
        if not table_exists(conn, 'playlist_videos') or not table_exists(conn, 'videos'):
            st.error("Required tables missing for playlist videos.")
            return pd.DataFrame()
        query = """
        SELECT v.video_id, v.title, v.publish_date, v.duration_seconds, \
               v.view_count, v.author, v.video_url,\
               v.last_scraped_timestamp,\
               CASE WHEN t.video_id IS NOT NULL THEN 1 ELSE 0 END as has_transcript
        FROM playlist_videos pv
        JOIN videos v ON pv.video_id = v.video_id
        LEFT JOIN transcripts t ON v.video_id = t.video_id
        WHERE pv.playlist_id = ?
        ORDER BY v.publish_date DESC
        """
        return pd.read_sql_query(query, conn, params=(playlist_id,))
    except Exception as e:
        st.error(f"Error loading playlist videos: {e}")
        return pd.DataFrame()

def get_video_playlists(conn, video_id):
    try:
        if not table_exists(conn, 'playlists') or not table_exists(conn, 'playlist_videos'):
            st.error("Required tables missing for video playlists.")
            return pd.DataFrame()
        query = """
        SELECT p.playlist_id, p.title, p.url
        FROM playlists p
        JOIN playlist_videos pv ON p.playlist_id = pv.playlist_id
        WHERE pv.video_id = ?
        ORDER BY p.title
        """
        return pd.read_sql_query(query, conn, params=(video_id,))
    except Exception as e:
        st.error(f"Error loading video playlists: {e}")
        return pd.DataFrame()

def get_duplicate_videos(conn):
    try:
        if not table_exists(conn, 'videos') or not table_exists(conn, 'playlist_videos'):
            st.error("Required tables missing for cross-links.")
            return pd.DataFrame()
        query = """
        SELECT v.video_id, v.title, v.author, v.publish_date, v.video_url,\
               COUNT(DISTINCT pv.playlist_id) as playlist_count
        FROM videos v
        JOIN playlist_videos pv ON v.video_id = pv.video_id
        GROUP BY v.video_id
        HAVING COUNT(DISTINCT pv.playlist_id) > 1
        ORDER BY playlist_count DESC, v.title
        """
        return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error loading duplicate videos: {e}")
        return pd.DataFrame()

def get_summary_stats(conn):
    stats = {}
    try:
        required = ['playlists','videos','transcripts','playlist_videos']
        if not all(table_exists(conn, t) for t in required):
            st.error("One or more required tables are missing from the database. Please run the migration and import scripts.")
            return {k: 'N/A' for k in ['total_playlists','total_videos','videos_with_transcripts','cross_linked_videos','last_update','top_channels']}
        # Total playlists
        query = "SELECT COUNT(*) as count FROM playlists"
        stats['total_playlists'] = pd.read_sql_query(query, conn).iloc[0]['count']
        # Total videos
        query = "SELECT COUNT(*) as count FROM videos"
        stats['total_videos'] = pd.read_sql_query(query, conn).iloc[0]['count']
        # Videos with transcripts
        query = "SELECT COUNT(*) as count FROM transcripts"
        stats['videos_with_transcripts'] = pd.read_sql_query(query, conn).iloc[0]['count']
        # Cross-linked videos (videos in multiple playlists)
        query = """
        SELECT COUNT(DISTINCT v.video_id) as count
        FROM videos v
        JOIN playlist_videos pv ON v.video_id = pv.video_id
        GROUP BY v.video_id
        HAVING COUNT(DISTINCT pv.playlist_id) > 1
        """
        cross_linked = pd.read_sql_query(query, conn)
        stats['cross_linked_videos'] = len(cross_linked) if not cross_linked.empty else 0
        # Last update time
        query = """
        SELECT MAX(last_scraped_timestamp) as last_update 
        FROM videos
        WHERE last_scraped_timestamp IS NOT NULL
        """
        last_update = pd.read_sql_query(query, conn).iloc[0]['last_update']
        stats['last_update'] = last_update if last_update else "Never"
        # Top 5 channels
        query = """
        SELECT author, COUNT(*) as video_count
        FROM videos
        WHERE author IS NOT NULL
        GROUP BY author
        ORDER BY video_count DESC
        LIMIT 5
        """
        stats['top_channels'] = pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error loading summary stats: {e}")
        stats = {k: 'N/A' for k in ['total_playlists','total_videos','videos_with_transcripts','cross_linked_videos','last_update','top_channels']}
        stats['top_channels'] = pd.DataFrame()
    return stats

def format_duration(seconds):
    if not seconds:
        return "Unknown"
    
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def extract_video_id(youtube_url):
    """Extract the YouTube video ID from various URL formats"""
    if not youtube_url:
        return None
        
    # For URLs like: https://www.youtube.com/watch?v=VIDEO_ID
    parsed_url = urlparse(youtube_url)
    if 'youtube.com' in parsed_url.netloc and '/watch' in parsed_url.path:
        query_params = parse_qs(parsed_url.query)
        return query_params.get('v', [None])[0]
    
    # For URLs like: https://youtu.be/VIDEO_ID
    if 'youtu.be' in parsed_url.netloc:
        return parsed_url.path.strip('/')
    
    # If it's just the ID itself
    if re.match(r'^[A-Za-z0-9_-]{11}$', youtube_url):
        return youtube_url
    
    return None

def get_playlists_for_selection(conn):
    try:
        if not table_exists(conn, 'playlists'):
            return None
        cursor = conn.cursor()
        cursor.execute("SELECT playlist_id, title FROM playlists ORDER BY title")
        playlists = cursor.fetchall()
        if not playlists:
            return None
        return {playlist[0]: playlist[1] for playlist in playlists}
    except Exception:
        return None

def process_video_data(title, video_url, transcript, language='en'):
    video_id = extract_video_id(video_url)
    if not video_id:
        st.error(f"Could not extract video ID from URL: {video_url}")
        return False
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        timestamp = datetime.now().isoformat()
        cursor.execute("SELECT video_id FROM videos WHERE video_id = ?", (video_id,))
        video_exists = cursor.fetchone() is not None
        if video_exists:
            cursor.execute(
                """UPDATE videos 
                   SET title = ?, video_url = ?, last_scraped_timestamp = ?
                   WHERE video_id = ?""",
                (title, video_url, timestamp, video_id)
            )
            st.success(f"Updated existing video: {title}")
        else:
            cursor.execute(
                """INSERT INTO videos 
                   (video_id, title, video_url, last_scraped_timestamp)
                   VALUES (?, ?, ?, ?)""",
                (video_id, title, video_url, timestamp)
            )
            st.success(f"Added new video: {title}")
        cursor.execute("SELECT video_id FROM transcripts WHERE video_id = ?", (video_id,))
        transcript_exists = cursor.fetchone() is not None
        if transcript_exists:
            cursor.execute(
                """UPDATE transcripts 
                   SET language = ?, transcript = ?, last_fetched_timestamp = ?
                   WHERE video_id = ?""",
                (language, transcript, timestamp, video_id)
            )
            st.success("Updated existing transcript")
        else:
            cursor.execute(
                """INSERT INTO transcripts 
                   (video_id, language, transcript, last_fetched_timestamp)
                   VALUES (?, ?, ?, ?)""",
                (video_id, language, transcript, timestamp)
            )
            st.success("Added new transcript")
        playlist_options = get_playlists_for_selection(conn)
        if playlist_options:
            st.subheader("Add this video to a playlist")
            selected_playlist = st.selectbox(
                "Select a playlist:",
                options=list(playlist_options.keys()),
                format_func=lambda x: playlist_options[x]
            )
            if selected_playlist and st.button("Add to Playlist", key="add_to_playlist_button"):
                cursor.execute(
                    "SELECT * FROM playlist_videos WHERE playlist_id = ? AND video_id = ?",
                    (selected_playlist, video_id)
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        "SELECT MAX(position) FROM playlist_videos WHERE playlist_id = ?",
                        (selected_playlist,)
                    )
                    max_position = cursor.fetchone()[0] or 0
                    cursor.execute(
                        "INSERT INTO playlist_videos (playlist_id, video_id, position) VALUES (?, ?, ?)",
                        (selected_playlist, video_id, max_position + 1)
                    )
                    st.success(f"Added to playlist: {playlist_options[selected_playlist]}")
                else:
                    st.info("This video is already in the selected playlist")
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Error adding video to database: {e}")
        import traceback
        st.code(traceback.format_exc())
        return False
    finally:
        conn.close()

def create_sample_file():
    """Create a sample transcript file for download"""
    sample_content = """TITLE: Sample Video Title
URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ

This is a sample transcript.
It can contain multiple lines.
You can replace this with the actual transcript of your video.
The entire text after the URL line will be treated as the transcript content.
"""
    return sample_content

def main():
    st.title("YouTube Data Explorer")
    
    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Dashboard", "Playlists", "Search", "Cross-Links", "Add Video"])
    
    conn = get_db_connection()
    if not conn:
        st.stop()

    # Dashboard Page
    if page == "Dashboard":
        st.header("YouTube Data Dashboard")
        
        stats = get_summary_stats(conn)
        
        # Create three columns for the metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Playlists", stats['total_playlists'])
        
        with col2:
            st.metric("Total Videos", stats['total_videos'])
        
        with col3:
            st.metric("Videos with Transcripts", stats['videos_with_transcripts'])
        
        with col4:
            st.metric("Cross-Linked Videos", stats['cross_linked_videos'])
        
        st.subheader("Last Update")
        if stats['last_update'] != "Never":
            try:
                last_update_dt = pd.to_datetime(stats['last_update'])
                st.info(f"Database was last updated on {last_update_dt.strftime('%B %d, %Y at %H:%M:%S UTC')}")
            except:
                st.info(f"Database was last updated: {stats['last_update']}")
        else:
            st.warning("Database has never been updated. Run the scraper to collect data.")
        
        # Top channels chart
        if isinstance(stats['top_channels'], pd.DataFrame) and not stats['top_channels'].empty:
            st.subheader("Top Channels")
            fig = px.bar(stats['top_channels'], x='author', y='video_count', color='video_count',
                         labels={'author': 'Channel', 'video_count': 'Number of Videos'},
                         title="Top 5 Channels by Video Count")
            st.plotly_chart(fig, use_container_width=True)
        
        # Instructions for updating
        st.subheader("How to Update Data")
        st.markdown("""
        To update the database with the latest YouTube data:
        
        1. Open a terminal/PowerShell window in the project directory
        2. Run the batch file: `.\\update_youtube_data.bat`
        3. Wait for the process to complete
        4. Refresh this page to see the latest data
        """)
    
    # Playlists Page
    elif page == "Playlists":
        st.header("Your YouTube Playlists")
        
        # Get all playlists
        try:
            playlists_df = get_playlists(conn)
            
            if playlists_df.empty:
                st.warning("No playlists found in the database. Run the scraper first.")
                return
            
            # Display a summary of playlists
            st.write(f"Found {len(playlists_df)} playlists in the database.")
            
            # Search box for playlists
            search = st.text_input("Search playlists by title:")
            if search:
                filtered_df = playlists_df[playlists_df['title'].str.contains(search, case=False, na=False)]
                display_df = filtered_df
            else:
                display_df = playlists_df
            
            # Add interactive table for playlists
            st.dataframe(
                display_df,
                column_config={
                    "playlist_id": None,  # Hide playlist_id column
                    "title": "Playlist Title",
                    "url": st.column_config.LinkColumn("URL"),
                    "video_count": "Videos Count",
                    "last_updated": "Last Updated"
                },
                hide_index=True
            )
            
            # Playlist Selector
            selected_playlist = st.selectbox(
                "Select a playlist to view its videos:",
                options=display_df['playlist_id'].tolist(),
                format_func=lambda x: display_df[display_df['playlist_id'] == x]['title'].iloc[0]
            )
            
            if selected_playlist:
                # Get videos for the selected playlist
                videos_df = get_playlist_videos(conn, selected_playlist)
                
                if videos_df.empty:
                    st.info(f"No videos found for playlist: {display_df[display_df['playlist_id'] == selected_playlist]['title'].iloc[0]}")
                    return
                
                # Process the data
                videos_df['duration_formatted'] = videos_df['duration_seconds'].apply(format_duration)
                
                # Convert timestamps to datetime for better display
                try:
                    videos_df['publish_date'] = pd.to_datetime(videos_df['publish_date'])
                except:
                    pass
                
                # Display videos
                st.subheader(f"Videos in '{display_df[display_df['playlist_id'] == selected_playlist]['title'].iloc[0]}'")
                st.write(f"Found {len(videos_df)} videos in this playlist.")
                
                # Interactive table for videos
                st.dataframe(
                    videos_df,
                    column_config={
                        "video_id": None,  # Hide video_id column
                        "title": "Video Title",
                        "publish_date": st.column_config.DateColumn("Publish Date"),
                        "duration_seconds": None,  # Hide raw duration
                        "duration_formatted": "Duration",
                        "view_count": "Views",
                        "author": "Channel",
                        "video_url": st.column_config.LinkColumn("Video Link"),
                        "last_scraped_timestamp": "Last Scraped",
                        "has_transcript": st.column_config.CheckboxColumn("Has Transcript")
                    },
                    hide_index=True
                )
                
                # Get video details when selected
                st.subheader("Video Details")
                selected_video = st.selectbox(
                    "Select a video to view details:",
                    options=videos_df['video_id'].tolist(),
                    format_func=lambda x: videos_df[videos_df['video_id'] == x]['title'].iloc[0]
                )
                
                if selected_video:
                    video_row = videos_df[videos_df['video_id'] == selected_video].iloc[0]
                    
                    # Create two columns for details
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Title:**", video_row['title'])
                        st.write("**Channel:**", video_row['author'] if not pd.isna(video_row['author']) else "Unknown")
                        st.write("**Published:**", video_row['publish_date'])
                        st.write("**Duration:**", video_row['duration_formatted'])
                    
                    with col2:
                        st.write("**Views:**", f"{video_row['view_count']:,}" if not pd.isna(video_row['view_count']) else "Unknown")
                        st.write("**Last Scraped:**", video_row['last_scraped_timestamp'])
                        st.write("**Video Link:**", f"[Watch on YouTube]({video_row['video_url']})")
                    
                    # Display transcript if available
                    if video_row['has_transcript']:
                        st.subheader("Video Transcript")
                        transcript_data = get_transcript(conn, selected_video)
                        
                        if transcript_data:
                            st.write(f"**Language:** {transcript_data['language']}")
                            st.write(f"**Last Updated:** {transcript_data['last_fetched_timestamp']}")
                            
                            with st.expander("Show Transcript"):
                                st.text_area("Transcript", transcript_data['transcript'], height=300)
                        else:
                            st.info("Transcript marked as available but not found in database.")
                    else:
                        st.info("No transcript available for this video.")
                        
        except Exception as e:
            st.error(f"Error loading playlists: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # Search Page
    elif page == "Search":
        st.header("Search YouTube Data")
        
        search_options = st.radio(
            "Search in:",
            ["Video Titles", "Transcripts", "Both"]
        )
        
        search_query = st.text_input("Enter search terms:")
        
        if search_query:
            conn = get_connection()
            
            if search_options == "Video Titles" or search_options == "Both":
                st.subheader("Videos Matching Search")
                
                query = """
                SELECT v.video_id, v.title, v.author, v.publish_date, v.duration_seconds,
                       v.video_url, p.title as playlist_title, p.playlist_id
                FROM videos v
                JOIN playlist_videos pv ON v.video_id = pv.video_id
                JOIN playlists p ON pv.playlist_id = p.playlist_id
                WHERE v.title LIKE ?
                GROUP BY v.video_id
                ORDER BY v.publish_date DESC
                LIMIT 100
                """
                
                videos_df = pd.read_sql_query(query, conn, params=(f'%{search_query}%',))
                
                if not videos_df.empty:
                    videos_df['duration_formatted'] = videos_df['duration_seconds'].apply(format_duration)
                    
                    st.dataframe(
                        videos_df,
                        column_config={
                            "video_id": None,
                            "playlist_id": None,
                            "duration_seconds": None,
                            "title": "Video Title",
                            "author": "Channel",
                            "publish_date": "Publish Date",
                            "duration_formatted": "Duration",
                            "video_url": st.column_config.LinkColumn("Video Link"),
                            "playlist_title": "Playlist"
                        },
                        hide_index=True
                    )
                else:
                    st.info("No videos found matching your search query.")
            
            if search_options == "Transcripts" or search_options == "Both":
                st.subheader("Transcripts Matching Search")
                
                query = """
                SELECT v.video_id, v.title, v.author, v.video_url, 
                       t.language, t.transcript
                FROM transcripts t
                JOIN videos v ON t.video_id = v.video_id
                WHERE t.transcript LIKE ?
                ORDER BY v.publish_date DESC
                LIMIT 50
                """
                
                transcripts_df = pd.read_sql_query(query, conn, params=(f'%{search_query}%',))
                
                if not transcripts_df.empty:
                    for i, row in transcripts_df.iterrows():
                        with st.expander(f"{row['title']} - {row['author']}"):
                            st.write(f"**Language:** {row['language']}")
                            st.write(f"**Video Link:** [Watch on YouTube]({row['video_url']})")
                            
                            # Extract context around the search term
                            transcript = row['transcript']
                            search_pos = transcript.lower().find(search_query.lower())
                            
                            if search_pos >= 0:
                                start_pos = max(0, search_pos - 100)
                                end_pos = min(len(transcript), search_pos + len(search_query) + 100)
                                
                                # Get context
                                context = transcript[start_pos:end_pos]
                                
                                # Highlight the search term
                                highlighted = context.replace(
                                    search_query, 
                                    f"**{search_query}**"
                                )
                                
                                st.markdown(f"...{highlighted}...")
                                
                                # Display full transcript in a separate text area (not nested in an expander)
                                st.text_area("Full Transcript", transcript, height=300)
                            else:
                                st.text_area("Transcript", transcript, height=200)
                else:
                    st.info("No transcripts found matching your search query.")
    
    # Cross-Links Page
    elif page == "Cross-Links":
        st.header("Cross-Linked Videos")
        st.subheader("Videos That Appear in Multiple Playlists")
        
        # Get videos that appear in multiple playlists
        duplicate_videos = get_duplicate_videos(conn)
        
        if duplicate_videos.empty:
            st.info("No videos found that appear in multiple playlists.")
        else:
            st.write(f"Found {len(duplicate_videos)} videos that appear in multiple playlists.")
            
            # Create dropdown selector for videos
            video_options = {}
            for _, row in duplicate_videos.iterrows():
                # Format as "Title (Author) - in X playlists"
                display_text = f"{row['title']} ({row['author'] if not pd.isna(row['author']) else 'Unknown'}) - in {row['playlist_count']} playlists"
                video_options[row['video_id']] = display_text
            
            selected_video = st.selectbox(
                "Select a video to see its playlists:",
                options=list(video_options.keys()),
                format_func=lambda x: video_options[x],
                key="crosslink_video_select"
            )
            
            if selected_video:
                # Get the video details
                video_row = duplicate_videos[duplicate_videos['video_id'] == selected_video].iloc[0]
                
                # Display video info
                st.markdown(f"### {video_row['title']}")
                st.write(f"**Channel:** {video_row['author'] if not pd.isna(video_row['author']) else 'Unknown'}")
                st.write(f"**Published:** {video_row['publish_date'] if not pd.isna(video_row['publish_date']) else 'Unknown'}")
                st.write(f"**Video Link:** [Watch on YouTube]({video_row['video_url']})")
                
                # Get all playlists containing this video
                playlists_with_video = get_video_playlists(conn, selected_video)
                
                # Display playlists table
                st.subheader(f"Appears in {len(playlists_with_video)} Playlists:")
                st.dataframe(
                    playlists_with_video,
                    column_config={
                        "playlist_id": None,  # Hide playlist_id column
                        "title": "Playlist Title",
                        "url": st.column_config.LinkColumn("Playlist URL")
                    },
                    hide_index=True
                )
                
                # Offer to remove from playlists
                st.subheader("Remove from Playlists")
                st.write("Select playlists to remove this video from:")
                
                # Create checkboxes for each playlist
                selected_playlists = []
                for i, playlist_row in playlists_with_video.iterrows():
                    playlist_id = playlist_row['playlist_id']
                    if st.checkbox(playlist_row['title'], key=f"remove_from_{playlist_id}"):
                        selected_playlists.append(playlist_id)
                
                if selected_playlists and st.button("Remove Selected", key="remove_from_playlists_btn"):
                    cursor = conn.cursor()
                    try:
                        for playlist_id in selected_playlists:
                            cursor.execute(
                                "DELETE FROM playlist_videos WHERE playlist_id = ? AND video_id = ?",
                                (playlist_id, selected_video)
                            )
                        conn.commit()
                        st.success(f"Removed video from {len(selected_playlists)} playlists. Refresh to update.")
                        st.experimental_rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error removing from playlists: {e}")
                    finally:
                        conn.close()
            
            # Show table of all cross-linked videos
            with st.expander("View All Cross-Linked Videos"):
                # Add formatted column for better display
                display_df = duplicate_videos.copy()
                display_df['formatted_title'] = display_df.apply(
                    lambda x: f"{x['title']} ({x['author'] if not pd.isna(x['author']) else 'Unknown'})",
                    axis=1
                )
                
                st.dataframe(
                    display_df,
                    column_config={
                        "video_id": None,  # Hide video_id column
                        "title": None,    # Hide title as we use formatted_title
                        "author": None,   # Hide author as it's in formatted_title
                        "formatted_title": "Video Title",
                        "publish_date": "Published Date",
                        "playlist_count": "# of Playlists",
                        "video_url": st.column_config.LinkColumn("Video Link")
                    },
                    hide_index=True
                )
    
    # Add Video Page
    elif page == "Add Video":
        st.header("Add Video from Text File")
        
        st.markdown("""
        Upload a text file containing video information and transcript. The file should have the following format:
        
        ```
        TITLE: Your Video Title Here
        URL: https://www.youtube.com/watch?v=XXXXXXXXXXX
        
        Transcript content goes here...
        This can be multiple lines.
        The entire rest of the file will be treated as the transcript.
        ```
        """)
        
        # Sample file generation
        st.download_button(
            label="Download Sample File Template",
            data=create_sample_file(),
            file_name="sample_transcript.txt",
            mime="text/plain"
        )
        
        # File uploader
        uploaded_file = st.file_uploader("Choose a text file", type="txt")
        
        # Form for manual input
        with st.expander("Don't have a file? Enter details manually"):
            video_title = st.text_input("Video Title")
            video_url = st.text_input("YouTube URL")
            video_transcript = st.text_area("Transcript", height=300)
            manual_submit = st.button("Add to Database")
            
            if manual_submit and video_title and video_url and video_transcript:
                # Process manually entered data
                process_video_data(video_title, video_url, video_transcript)
        
        if uploaded_file is not None:
            # Read the file
            content = uploaded_file.getvalue().decode("utf-8")
            
            # Display preview
            with st.expander("File Preview"):
                st.text(content[:500] + "..." if len(content) > 500 else content)
            
            # Process file
            if st.button("Add to Database", key="file_upload_button"):
                try:
                    # Parse the file content
                    lines = content.splitlines()
                    title = None
                    url = None
                    transcript_start_line = 0
                    
                    for i, line in enumerate(lines):
                        if line.startswith("TITLE:"):
                            title = line[6:].strip()
                        elif line.startswith("URL:"):
                            url = line[4:].strip()
                        
                        # Assume transcript starts after the URL line and a blank line
                        if url is not None and line.strip() == "":
                            transcript_start_line = i + 1
                            break
                    
                    # If we found title and URL, process the rest as transcript
                    if title and url:
                        transcript = "\n".join(lines[transcript_start_line:])
                        
                        # Process the extracted info
                        process_video_data(title, url, transcript)
                    else:
                        st.error("Could not find TITLE: and URL: in the file. Please check the file format.")
                
                except Exception as e:
                    st.error(f"Error processing file: {e}")
                    import traceback
                    st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
