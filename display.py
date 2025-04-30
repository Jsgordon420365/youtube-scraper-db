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

# Create a connection to the database
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_playlists():
    conn = get_connection()
    query = """
    SELECT p.playlist_id, p.title, p.url, 
           COUNT(pv.video_id) as video_count,
           p.last_updated
    FROM playlists p
    LEFT JOIN playlist_videos pv ON p.playlist_id = pv.playlist_id
    GROUP BY p.playlist_id
    ORDER BY video_count DESC
    """
    df = pd.read_sql_query(query, conn)
    return df

@st.cache_data(ttl=300)
def get_playlist_videos(playlist_id):
    conn = get_connection()
    query = """
    SELECT v.video_id, v.title, v.publish_date, v.duration_seconds, 
           v.view_count, v.author, v.video_url,
           v.last_scraped_timestamp,
           CASE WHEN t.video_id IS NOT NULL THEN 1 ELSE 0 END as has_transcript
    FROM playlist_videos pv
    JOIN videos v ON pv.video_id = v.video_id
    LEFT JOIN transcripts t ON v.video_id = t.video_id
    WHERE pv.playlist_id = ?
    ORDER BY v.publish_date DESC
    """
    df = pd.read_sql_query(query, conn, params=(playlist_id,))
    return df

@st.cache_data(ttl=300)
def get_transcript(video_id):
    conn = get_connection()
    query = """
    SELECT video_id, language, transcript, last_fetched_timestamp
    FROM transcripts
    WHERE video_id = ?
    """
    df = pd.read_sql_query(query, conn, params=(video_id,))
    if not df.empty:
        return df.iloc[0].to_dict()
    return None

@st.cache_data(ttl=300)
def get_summary_stats():
    conn = get_connection()
    
    stats = {}
    
    # Total playlists
    query = "SELECT COUNT(*) as count FROM playlists"
    stats['total_playlists'] = pd.read_sql_query(query, conn).iloc[0]['count']
    
    # Total videos
    query = "SELECT COUNT(*) as count FROM videos"
    stats['total_videos'] = pd.read_sql_query(query, conn).iloc[0]['count']
    
    # Videos with transcripts
    query = "SELECT COUNT(*) as count FROM transcripts"
    stats['videos_with_transcripts'] = pd.read_sql_query(query, conn).iloc[0]['count']
    
    # Last update time
    query = """
    SELECT MAX(last_scraped_timestamp) as last_update 
    FROM videos
    WHERE last_scraped_timestamp IS NOT NULL
    """
    last_update = pd.read_sql_query(query, conn).iloc[0]['last_update']
    if last_update:
        stats['last_update'] = last_update
    else:
        stats['last_update'] = "Never"
    
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
    """Get all playlists for the selection dropdown"""
    cursor = conn.cursor()
    cursor.execute("SELECT playlist_id, title FROM playlists ORDER BY title")
    playlists = cursor.fetchall()
    
    if not playlists:
        return None
    
    # Create a dictionary with playlist_id as key and title as value
    return {playlist[0]: playlist[1] for playlist in playlists}

def process_video_data(title, video_url, transcript, language='en'):
    """Process video data and add it to the database"""
    # Extract video ID from URL
    video_id = extract_video_id(video_url)
    
    if not video_id:
        st.error(f"Could not extract video ID from URL: {video_url}")
        return False
    
    # Connect to database
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Add video to videos table if it doesn't exist
        timestamp = datetime.now().isoformat()
        
        # Check if video already exists
        cursor.execute("SELECT video_id FROM videos WHERE video_id = ?", (video_id,))
        video_exists = cursor.fetchone() is not None
        
        if video_exists:
            # Update existing video
            cursor.execute(
                """UPDATE videos 
                   SET title = ?, video_url = ?, last_scraped_timestamp = ?
                   WHERE video_id = ?""",
                (title, video_url, timestamp, video_id)
            )
            st.success(f"Updated existing video: {title}")
        else:
            # Insert new video
            cursor.execute(
                """INSERT INTO videos 
                   (video_id, title, video_url, last_scraped_timestamp)
                   VALUES (?, ?, ?, ?)""",
                (video_id, title, video_url, timestamp)
            )
            st.success(f"Added new video: {title}")
        
        # Add transcript
        cursor.execute("SELECT video_id FROM transcripts WHERE video_id = ?", (video_id,))
        transcript_exists = cursor.fetchone() is not None
        
        if transcript_exists:
            # Update existing transcript
            cursor.execute(
                """UPDATE transcripts 
                   SET language = ?, transcript = ?, last_fetched_timestamp = ?
                   WHERE video_id = ?""",
                (language, transcript, timestamp, video_id)
            )
            st.success("Updated existing transcript")
        else:
            # Insert new transcript
            cursor.execute(
                """INSERT INTO transcripts 
                   (video_id, language, transcript, last_fetched_timestamp)
                   VALUES (?, ?, ?, ?)""",
                (video_id, language, transcript, timestamp)
            )
            st.success("Added new transcript")
        
        # Add to playlists (optional)
        playlist_options = get_playlists_for_selection(conn)
        
        if playlist_options:
            st.subheader("Add this video to a playlist")
            selected_playlist = st.selectbox(
                "Select a playlist:",
                options=list(playlist_options.keys()),
                format_func=lambda x: playlist_options[x]
            )
            
            if selected_playlist and st.button("Add to Playlist"):
                # Check if the video is already in the playlist
                cursor.execute(
                    "SELECT * FROM playlist_videos WHERE playlist_id = ? AND video_id = ?",
                    (selected_playlist, video_id)
                )
                
                if cursor.fetchone() is None:
                    # Get the highest position in the playlist
                    cursor.execute(
                        "SELECT MAX(position) FROM playlist_videos WHERE playlist_id = ?",
                        (selected_playlist,)
                    )
                    max_position = cursor.fetchone()[0] or 0
                    
                    # Add to playlist with incremented position
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
    page = st.sidebar.radio("Go to", ["Dashboard", "Playlists", "Search", "Add Video"])
    
    # Dashboard Page
    if page == "Dashboard":
        st.header("YouTube Data Dashboard")
        
        stats = get_summary_stats()
        
        # Create three columns for the metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Playlists", stats['total_playlists'])
        
        with col2:
            st.metric("Total Videos", stats['total_videos'])
        
        with col3:
            st.metric("Videos with Transcripts", stats['videos_with_transcripts'])
        
        st.subheader("Last Update")
        if stats['last_update'] != "Never":
            try:
                last_update_dt = datetime.fromisoformat(stats['last_update'].replace('Z', '+00:00'))
                st.info(f"Database was last updated on {last_update_dt.strftime('%B %d, %Y at %H:%M:%S UTC')}")
            except:
                st.info(f"Database was last updated: {stats['last_update']}")
        else:
            st.warning("Database has never been updated. Run the scraper to collect data.")
        
        # Top channels chart
        if not stats['top_channels'].empty:
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
            playlists_df = get_playlists()
            
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
                videos_df = get_playlist_videos(selected_playlist)
                
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
                        transcript_data = get_transcript(selected_video)
                        
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
                                
                                with st.expander("View Full Transcript"):
                                    st.text_area("", transcript, height=300)
                            else:
                                st.text_area("Transcript", transcript, height=200)
                else:
                    st.info("No transcripts found matching your search query.")
    
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
            if st.button("Add to Database"):
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
