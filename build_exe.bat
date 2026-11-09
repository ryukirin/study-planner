@echo off
setlocal
cd /d "%~dp0"
python generate_logo.py
python -m PyInstaller --noconfirm --onefile --windowed --name StudyPlanner --icon assets\app_icon.ico --add-data "web;web" --add-data "assets\app_icon.ico;assets" --add-data "assets\tray_icon.png;assets" --hidden-import pystray._win32 planner_app.py
echo.
echo Build finished. EXE path:
echo %~dp0dist\StudyPlanner.exe
pause
