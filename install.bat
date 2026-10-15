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

REM Zweiter, optionaler Weg: Claude Code mit Claude-Abo (Pro/Max) statt opencode.
where claude >nul 2>nul
if errorlevel 1 (
  echo Optional: Claude Code als zweites Backend ^(Claude-Abo, keine zusaetzlichen API-Tokens^).
  echo   Installieren: https://docs.claude.com/en/docs/claude-code  - danach einmal "claude" zum Anmelden.
) else (
  echo Claude Code gefunden - in den Einstellungen als LLM-Backend waehlbar.
)

echo Erstelle virtuelle Umgebung ...
%PY% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

echo Hinweis PDF: der Export nutzt WeasyPrint im Web-Design. Fehlen unter Windows die
echo   GTK-Bibliotheken, faellt er automatisch auf das einfache fpdf2-Layout zurueck.

echo Zusaetzliche Jobboersen (optional: LinkedIn/Indeed via JobSpy) ...
pip install -r requirements-sources.txt >nul 2>nul
if errorlevel 1 (
  echo Hinweis: JobSpy nicht installiert - nur die Bundesagentur-Quelle ist aktiv.
  echo Fuer LinkedIn/Indeed siehe requirements-sources.txt.
)

echo Initialisiere Konten-Datenbank ...
python -c "from app import auth; auth.init_accounts_db(); print('OK - Konten-Datenbank bereit')"
echo   Konten werden beim ersten Login/Registrieren angelegt; Daten je Benutzer getrennt.

echo.
echo Richte opencode-Websuche ein (Brave-Suche + Fetch) ...
call scripts\setup_opencode_mcp.bat

echo.
echo Fertig. Starten mit: run.bat
echo Danach im Browser oeffnen und unter 'Einstellungen' Modell + Mailkonto einrichten.
pause
