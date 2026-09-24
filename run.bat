@echo off
REM MalochBot - Start (Windows). Beendet zuerst eine laufende Instanz auf dem Port und startet neu.
setlocal enabledelayedexpansion
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

set HOST=%MALOCHBOT_HOST%
if "%HOST%"=="" set HOST=127.0.0.1
set PORT=%MALOCHBOT_PORT%
if "%PORT%"=="" set PORT=8765
set URL=http://%HOST%:%PORT%

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT%" ^| findstr LISTENING') do (
  echo Beende laufende Instanz (PID %%p) ...
  taskkill /F /PID %%p >nul 2>nul
)
timeout /t 1 >nul

echo MalochBot laeuft auf %URL%
echo Beenden: Einstellungen ^> Server beenden.
start "" %URL%
python -m uvicorn app.main:app --host %HOST% --port %PORT%
