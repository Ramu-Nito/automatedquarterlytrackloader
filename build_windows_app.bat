@echo off
setlocal

where python >nul 2>&1
if errorlevel 1 (
  echo Python is required to build the standalone app.
  pause
  exit /b 1
)

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo Installing the Windows app builder...
  python -m pip install pyinstaller
  if errorlevel 1 (
    echo Could not install PyInstaller. Check your internet connection.
    pause
    exit /b 1
  )
)

echo Checking app dependencies...
python -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
  echo Could not install app dependencies. Check your internet connection.
  pause
  exit /b 1
)

python -m PyInstaller --noconfirm --clean --onefile --windowed --name QuarterlyTrackLoader-Web --add-data "%~dp0quarterly_track_loader.html;." --distpath "%~dp0dist" --workpath "%~dp0build-web" --specpath "%~dp0build-web" "%~dp0quarterly_track_loader.py"
if errorlevel 1 (
  echo The standalone app could not be built.
  pause
  exit /b 1
)

echo.
echo Standalone app created: "%~dp0dist\QuarterlyTrackLoader-Web.exe"
pause