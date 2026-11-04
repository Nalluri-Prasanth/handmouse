@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py
) else (
  "%USERPROFILE%\Downloads\handmouse-upgraded\.venv\Scripts\python.exe" app.py
)
if errorlevel 1 pause
