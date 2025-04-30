@echo off
echo ====================================
echo YouTube Data Explorer - Streamlit App
echo ====================================
echo.

REM Activate the virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found, using system Python...
)

REM Install required packages if needed
echo Installing required packages...
pip install -r streamlit_requirements.txt

REM Run the Streamlit app
echo Starting Streamlit app...
streamlit run display.py

pause
