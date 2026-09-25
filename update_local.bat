@echo off
cd /d "%~dp0"
if not exist node_modules call npm install
python scripts\run.py
start "" site\index.html
pause
