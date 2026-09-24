@echo off
REM MalochBot - Installer (Windows)
setlocal
cd /d "%~dp0"

echo == MalochBot Installer ==

where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% --version || (echo FEHLER: Python 3.10+ nicht gefunden. & pause & exit /b 1)

where opencode >nul 2>nul
if errorlevel 1 (
  echo opencode nicht gefunden - Installation ueber npm ...
  where npm >nul 2>nul && (npm install -g opencode-ai) || (
    echo HINWEIS: npm fehlt. Bitte opencode manuell installieren: https://opencode.ai/docs
  )
)

echo Erstelle virtuelle Umgebung ...
%PY% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

echo Initialisiere Datenbank ...
python -c "from app import db; db.init_db(); print('OK')"

echo.
echo Fertig. Starten mit: run.bat
echo Danach im Browser oeffnen und unter 'Einstellungen' Modell + Mailkonto einrichten.
pause
