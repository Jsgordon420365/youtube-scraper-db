@echo off
echo ====================================
echo YouTube Transcript Processor
echo ====================================
echo.

REM Activate the virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found, using system Python...
)

REM Create inbox directory if it doesn't exist
if not exist inbox (
    echo Creating inbox directory...
    mkdir inbox
)

REM Check if a command line argument was provided
if "%~1"=="" (
    REM No argument provided, run in interactive mode
    echo Running in interactive mode...
    echo Will process any files in the inbox directory first
    python add_transcripts.py
) else (
    REM Argument provided, pass it to the script
    echo Processing video: %~1
    python add_transcripts.py %*
)

echo.
echo ====================================
echo Process completed!
echo ====================================
echo.
echo To add more transcripts:
echo 1. Place .txt files in the 'inbox' folder
echo 2. Run this batch file without arguments
echo Or
echo 3. Run: process_transcripts.bat YOUR_VIDEO_ID
echo.

pause
