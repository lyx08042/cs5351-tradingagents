@echo off
REM Double-click launcher for the CS5351 demo page.
REM Starts a local server on 127.0.0.1 and opens the page in the browser.
REM Nothing is uploaded; no API key is read.

setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python was not found on PATH.
  echo Install Python 3.11 or later, then run this file again.
  echo.
  pause
  exit /b 1
)

echo Starting the demo page...
echo Close this window to stop the server.
echo.
python -m demo.serve
if errorlevel 1 pause
