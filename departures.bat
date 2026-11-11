@echo off
rem DEPARTURES launcher - runs the board from the code in this folder,
rem so it keeps working wherever the folder lives.
rem Double-click or run from a terminal: if the board fails to start, the
rem window stays open so the error can be read. The silent launcher
rem (departures-launch.vbs) sets DEPARTURES_SILENT and logs errors instead.
setlocal
cd /d "%~dp0"
python -m departures %*
set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" if not defined DEPARTURES_SILENT pause
exit /b %EXIT_CODE%
