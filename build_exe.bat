@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%CD%"
set "DIST=%ROOT%\dist"
set "STEP="

rem The exes in dist are locked while they run, so PyInstaller cannot replace them.
rem Only processes started from dist count. A copy of the app installed elsewhere is left alone.
set "STEP=check running app"
call :find_running
if errorlevel 1 (
  echo.
  echo StudyPlanner started from "%DIST%" is running. Its files cannot be replaced while it runs.
  choice /c YN /m "Close it now and continue"
  if errorlevel 2 (
    echo Close StudyPlanner, then run build_exe.bat again.
    goto failed
  )
  powershell -NoProfile -Command "$p = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and (@('StudyPlanner.exe','planner-cli.exe' | ForEach-Object { Join-Path $env:DIST $_ }) -contains $_.Path) }; $p | Stop-Process -Force; $p | Wait-Process -Timeout 15 -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500"
  call :find_running
  if errorlevel 1 (
    echo StudyPlanner is still running. Close it from the tray menu, then run build_exe.bat again.
    goto failed
  )
  echo StudyPlanner closed.
)

set "STEP=generate logo"
python generate_logo.py || goto failed

rem App. Only SKILL.md and references\*.md of the skill are bundled (references\local\ is not).
set "STEP=build StudyPlanner.exe"
python -m PyInstaller --noconfirm --onefile --windowed --name StudyPlanner --specpath build ^
  --icon "%ROOT%\assets\app_icon.ico" ^
  --add-data "%ROOT%\web;web" ^
  --add-data "%ROOT%\assets\app_icon.ico;assets" ^
  --add-data "%ROOT%\assets\tray_icon.png;assets" ^
  --add-data "%ROOT%\skills\plan-builder\SKILL.md;skills\plan-builder" ^
  --add-data "%ROOT%\skills\plan-builder\references\*.md;skills\plan-builder\references" ^
  --hidden-import pystray._win32 planner_app.py || goto failed

rem Command-line tool used by the plan-builder skill.
set "STEP=build planner-cli.exe"
python -m PyInstaller --noconfirm --onefile --console --name planner-cli --specpath build ^
  --icon "%ROOT%\assets\app_icon.ico" planner_cli.py || goto failed

set "STEP=create zip"
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\StudyPlanner.exe, dist\planner-cli.exe -DestinationPath dist\StudyPlanner-windows.zip" || goto failed

echo.
echo Build finished:
echo %ROOT%\dist\StudyPlanner.exe
echo %ROOT%\dist\planner-cli.exe
echo %ROOT%\dist\StudyPlanner-windows.zip
pause
exit /b 0

:failed
echo.
echo Build failed at step: %STEP%
echo The messages above show the reason.
pause
exit /b 1

rem Sets errorlevel 1 when StudyPlanner.exe or planner-cli.exe from dist is running, otherwise 0.
:find_running
powershell -NoProfile -Command "$names = @('StudyPlanner.exe','planner-cli.exe' | ForEach-Object { Join-Path $env:DIST $_ }); if (Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and ($names -contains $_.Path) }) { exit 1 } else { exit 0 }"
exit /b %errorlevel%
