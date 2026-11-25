# SmartAI - PowerShell Launcher
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Starting SmartAI - Personal AI Assistant" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

if (-Not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "[ERROR] Virtual environment not found in .\venv!" -ForegroundColor Red
    Write-Host "Please create it first with: python -m venv venv; .\venv\Scripts\pip.exe install -r requirements.txt"
    Exit 1
}

Write-Host "Starting Flask server on http://127.0.0.1:5000 ..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server.`n" -ForegroundColor Yellow

& ".\venv\Scripts\python.exe" app.py

