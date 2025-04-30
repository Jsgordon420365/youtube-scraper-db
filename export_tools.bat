@echo off
echo ====================================
echo YouTube Transcript Export Tools
echo ====================================
echo.

REM Activate the virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found, using system Python...
)

echo Choose an export option:
echo 1. Export a single video transcript
echo 2. Export all transcripts from a playlist
echo 3. Exit
echo.

set /p choice="Enter your choice (1-3): "

if "%choice%"=="1" (
    echo.
    echo === Export Single Video Transcript ===
    set /p video_id="Enter YouTube video ID: "
    set /p output_file="Enter output file name (or press Enter for default): "
    
    if "%output_file%"=="" (
        python export_transcript.py %video_id%
    ) else (
        python export_transcript.py %video_id% %output_file%
    )
) else if "%choice%"=="2" (
    echo.
    echo === Export Playlist Transcripts ===
    set /p playlist_id="Enter YouTube playlist ID: "
    set /p output_dir="Enter output directory (or press Enter for default): "
    
    if "%output_dir%"=="" (
        python export_playlist_transcripts.py %playlist_id%
    ) else (
        python export_playlist_transcripts.py %playlist_id% %output_dir%
    )
) else if "%choice%"=="3" (
    echo Exiting...
    exit /b 0
) else (
    echo Invalid choice!
)

echo.
pause
