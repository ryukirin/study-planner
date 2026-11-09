@echo off
setlocal
cd /d "%~dp0"
set ROOT=%CD%
python generate_logo.py || exit /b 1

rem App. Only SKILL.md and references\*.md of the skill are bundled (references\local\ is not).
python -m PyInstaller --noconfirm --onefile --windowed --name StudyPlanner --specpath build ^
  --icon "%ROOT%\assets\app_icon.ico" ^
  --add-data "%ROOT%\web;web" ^
  --add-data "%ROOT%\assets\app_icon.ico;assets" ^
  --add-data "%ROOT%\assets\tray_icon.png;assets" ^
  --add-data "%ROOT%\skills\plan-builder\SKILL.md;skills\plan-builder" ^
  --add-data "%ROOT%\skills\plan-builder\references\*.md;skills\plan-builder\references" ^
  --hidden-import pystray._win32 planner_app.py || exit /b 1

rem Command-line tool used by the plan-builder skill.
python -m PyInstaller --noconfirm --onefile --console --name planner-cli --specpath build ^
  --icon "%ROOT%\assets\app_icon.ico" planner_cli.py || exit /b 1

powershell -NoProfile -Command "Compress-Archive -Force -Path dist\StudyPlanner.exe, dist\planner-cli.exe -DestinationPath dist\StudyPlanner-windows.zip" || exit /b 1

echo.
echo Build finished:
echo %ROOT%\dist\StudyPlanner.exe
echo %ROOT%\dist\planner-cli.exe
echo %ROOT%\dist\StudyPlanner-windows.zip
pause
