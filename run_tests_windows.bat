@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Run setup_windows.bat first.
  exit /b 1
)
".venv\Scripts\python.exe" tests\test_services.py
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" tests\test_liquidity.py
if errorlevel 1 exit /b 1
echo.
echo ALL PROMETHEUS ONE TESTS PASSED.
