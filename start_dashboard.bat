@echo off
cd /d %~dp0
python generate_data.py
if errorlevel 1 exit /b %errorlevel%
python app.py --open
