@echo off
cd /d "%~dp0"
python -m departures --port 4040 %*
