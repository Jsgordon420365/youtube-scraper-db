@echo off
echo ====================================
echo YouTube Scraper - Starting Update...
echo ====================================
echo.

REM Activate the virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found, using system Python...
)

REM Run the script
echo Running scraper...
python run_me.py

echo.
echo ====================================
echo Process completed!
echo To view results, check run_me.log
echo ====================================

REM Keep the window open when finished
pause
