@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" generate.py basic
if not exist ".venv\Scripts\python.exe" py -3 generate.py basic
echo.
pause
