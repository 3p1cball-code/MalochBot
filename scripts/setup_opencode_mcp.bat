@echo off
REM Richtet die fuer die Jobsuche noetigen opencode-MCP-Server ein (Windows).
setlocal
cd /d "%~dp0"

where npx >nul 2>nul
if errorlevel 1 echo HINWEIS: Node.js/npx fehlt. Bitte Node.js 20+ installieren (https://nodejs.org).
where uvx >nul 2>nul
if errorlevel 1 echo HINWEIS: uv/uvx fehlt. Bitte uv installieren (https://docs.astral.sh/uv/).

set KEY=%BRAVE_API_KEY%
if "%KEY%"=="" set /p KEY=Brave Search API-Key (Enter = ueberspringen):

python "%~dp0mcp_config.py" "%KEY%"
echo Fertig.
