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
set "PY="
rem Test what starting the board actually needs (fastapi, aiosqlite).
rem A Python earlier on PATH may import the command layer but lack them.
call python -c "import departures.server" >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto python_ready
call py -3.12 -c "import departures.server" >nul 2>&1
if not errorlevel 1 set "PY=py -3.12"
if defined PY goto python_ready
call py -3.11 -c "import departures.server" >nul 2>&1
if not errorlevel 1 set "PY=py -3.11"
if defined PY goto python_ready
echo DEPARTURES needs Python 3.11 or newer with its dependencies installed.
set "EXIT_CODE=1"
goto finished

:python_ready
call %PY% -m departures %*
set "EXIT_CODE=%errorlevel%"

:finished
if not "%EXIT_CODE%"=="0" if not defined DEPARTURES_SILENT pause
popd
exit /b %EXIT_CODE%
