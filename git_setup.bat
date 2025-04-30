@echo off
echo ====================================
echo Git Repository Setup
echo ====================================
echo.

REM Check if .git directory exists
if not exist .git (
    echo Initializing new Git repository...
    git init
) else (
    echo Git repository already initialized.
)

echo.
echo Adding essential files to the repository...

REM Add Python scripts
git add *.py

REM Add batch files
git add *.bat

REM Add configuration files
git add README.md
git add requirements.txt
git add streamlit_requirements.txt
git add .gitignore

REM Add sample files
git add sample_transcript_with_timestamps.txt

REM Add the playlists.json file that we explicitly keep
git add playlists.json

REM Exclude database files and logs (just to be safe)
git rm --cached *.db 2>nul
git rm --cached *.log 2>nul

echo.
echo Committing changes...
git commit -m "Complete YouTube scraper with transcript management functionality"

echo.
echo ====================================
echo Git setup complete!
echo ====================================
echo.
echo Remember to set up a remote repository with:
echo   git remote add origin YOUR_REPOSITORY_URL
echo   git push -u origin main
echo.

pause
