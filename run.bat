@echo off
echo ===================================================
echo   Starting SmartAI - Personal AI Assistant
echo ===================================================
echo.

IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .\venv!
    echo Please create it first:
    echo   python -m venv venv
    echo   .\venv\Scripts\pip.exe install -r requirements.txt
    pause
    exit /b 1
)

echo Activating virtual environment and starting server...
echo Access the application at: http://127.0.0.1:5000
echo Press Ctrl+C to stop the server.
echo.

.\venv\Scripts\python.exe app.py
pause

