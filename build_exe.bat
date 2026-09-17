@echo off
REM ============================================================
REM  Build Pomodoro.exe  (single-file, no console window)
REM  Run this ONCE on your Windows 11 PC. Needs Python installed.
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo  Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python was not found.
    echo  Install it from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^)
    echo  then run this file again.
    pause
    exit /b 1
)

echo  Installing / updating PyInstaller...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo  [ERROR] Could not install PyInstaller. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo  Building Pomodoro.exe ...
python -m PyInstaller --onefile --windowed --clean ^
    --name Pomodoro --icon pomodoro.ico pomodoro.pyw
if errorlevel 1 (
    echo  [ERROR] Build failed.
    pause
    exit /b 1
)

REM move the finished exe next to this script for convenience
if exist "dist\Pomodoro.exe" copy /y "dist\Pomodoro.exe" "Pomodoro.exe" >nul

echo.
echo  ============================================================
echo   DONE!  Your app is:  %~dp0Pomodoro.exe
echo   Double-click it to run. To "install": right-click the exe
echo   and choose "Pin to Start" or "Create shortcut".
echo  ============================================================
echo.
pause
