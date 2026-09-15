@echo off
REM Change directory to the script location
cd /d "%~dp0"

REM Run the Python script
python main.py

REM Keep the window open after execution (optional)
pause
