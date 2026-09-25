@echo off
rem Test the database on this PC with any game code: adds the game, fetches it, builds the site and opens it.
cd /d "%~dp0"
if not exist .env (
  echo First copy .env.example to .env and fill in your Call of War username and password.
  pause
  exit /b
)
if not exist node_modules call npm install
pip install -q -r requirements.txt
set /p GAME=Game code:
set /p NAME=Name (may be empty):
python scripts\manage.py add %GAME% "%NAME%"
python scripts\run.py
start "" site\index.html
pause
