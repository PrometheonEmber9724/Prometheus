@echo off
setlocal
cd /d "%~dp0"
echo [1/3] Creating local virtual environment...
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto :error

echo [2/3] Installing requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/3] Running setup check...
".venv\Scripts\python.exe" check_setup.py
if errorlevel 1 goto :error

echo.
echo SETUP COMPLETE. Run run_windows.bat to launch Prometheus One.
exit /b 0

:error
echo.
echo SETUP FAILED. Read the error above.
exit /b 1
