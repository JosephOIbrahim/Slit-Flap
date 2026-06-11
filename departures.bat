@echo off
rem DEPARTURES launcher — uses the installed `departures` command if present,
rem falls back to running the package from this folder.
cd /d "%~dp0"
where departures >nul 2>nul
if %errorlevel%==0 (
    departures %*
) else (
    python -m departures %*
)
