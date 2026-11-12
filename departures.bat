@echo off
rem DEPARTURES launcher - runs the board from the code in this folder,
rem so it keeps working wherever the folder lives.
rem Double-click or run from a terminal: if the board fails to start, the
rem window stays open so the error can be read. The silent launcher
rem (departures-launch.vbs) sets DEPARTURES_SILENT and logs errors instead.
setlocal
pushd "%~dp0"
rem Use the first python that can actually import the board. A broken
rem install earlier on PATH (missing DLL) must not stop the launcher.
set "PY=python"
rem Test what starting the board actually needs (fastapi, aiosqlite).
rem A Python earlier on PATH may import the command layer but lack them.
%PY% -c "import departures.server" >nul 2>&1
if errorlevel 1 set "PY=py -3.12"
%PY% -m departures %*
set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" if not defined DEPARTURES_SILENT pause
popd
exit /b %EXIT_CODE%
