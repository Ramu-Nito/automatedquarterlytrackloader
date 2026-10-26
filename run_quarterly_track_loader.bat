@echo off
setlocal

if not "%~1"=="" (
  if exist "%~dp0dist\QuarterlyTrackLoader-Web.exe" (
    "%~dp0dist\QuarterlyTrackLoader-Web.exe" --input "%~1" --output "%~2"
    pause
    exit /b
  )
  if exist "%~dp0dist\QuarterlyTrackLoader-Headerless.exe" (
    "%~dp0dist\QuarterlyTrackLoader-Headerless.exe" --input "%~1" --output "%~2"
    pause
    exit /b
  )
  if exist "%~dp0dist\QuarterlyTrackLoader.exe" (
    "%~dp0dist\QuarterlyTrackLoader.exe" --input "%~1" --output "%~2"
    pause
    exit /b
  )
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python is not found in PATH. Install Python 3 and add it to PATH.
    pause
    exit /b 1
  )
  python -c "import openpyxl" >nul 2>&1
  if errorlevel 1 (
    echo Preparing app dependencies. This may take a moment...
    python -m pip install --user -r "%~dp0requirements.txt"
    if errorlevel 1 (
      echo Could not install app dependencies. Check your internet connection.
      pause
      exit /b 1
    )
  )
  python "%~dp0quarterly_track_loader.py" --input "%~1" --output "%~2"
  pause
  exit /b
)

if exist "%~dp0dist\QuarterlyTrackLoader-Web.exe" (
  start "" "%~dp0dist\QuarterlyTrackLoader-Web.exe"
  exit /b 0
)

if exist "%~dp0dist\QuarterlyTrackLoader-Headerless.exe" (
  start "" "%~dp0dist\QuarterlyTrackLoader-Headerless.exe"
  exit /b 0
)

if exist "%~dp0dist\QuarterlyTrackLoader.exe" (
  start "" "%~dp0dist\QuarterlyTrackLoader.exe"
  exit /b 0
)

where python >nul 2>&1
if errorlevel 1 (
  echo Python is not found in PATH. Install Python 3 and add it to PATH.
  pause
  exit /b 1
)

python -c "import openpyxl, webview" >nul 2>&1
if errorlevel 1 (
  echo Preparing app dependencies. This may take a moment...
  python -m pip install --user -r "%~dp0requirements.txt"
  if errorlevel 1 (
    echo Could not install app dependencies. Check your internet connection.
    pause
    exit /b 1
  )
)

where pythonw >nul 2>&1
if not errorlevel 1 (
  start "" pythonw "%~dp0quarterly_track_loader.py"
  exit /b 0
)

python "%~dp0quarterly_track_loader.py"
if errorlevel 1 pause
exit /b
