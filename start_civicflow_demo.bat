@echo off
setlocal

cd /d "%~dp0"
set "ROOT=%~dp0"

if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT%.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if exist "%ROOT%.venv\Scripts\streamlit.exe" (
    set "STREAMLIT=%ROOT%.venv\Scripts\streamlit.exe"
) else (
    set "STREAMLIT=streamlit"
)

if /I "%~1"=="--dry-run" goto dry_run

echo Starting CivicFlow API...
start "CivicFlow API" cmd /k "cd /d ""%ROOT%"" && ""%PYTHON%"" scripts\run_api.py"

echo Waiting for backend startup...
timeout /t 3 /nobreak >nul

echo Starting CivicFlow Dashboard...
start "CivicFlow Dashboard" cmd /k "cd /d ""%ROOT%"" && ""%STREAMLIT%"" run apps\dashboard\app.py"

echo Opening dashboard in your browser...
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:8501"

echo CivicFlow is launching.
echo Close the two service windows when you are done.
exit /b 0

:dry_run
echo ROOT=%ROOT%
echo PYTHON=%PYTHON%
echo STREAMLIT=%STREAMLIT%
echo start "CivicFlow API" cmd /k "cd /d ""%ROOT%"" ^&^& ""%PYTHON%"" scripts\run_api.py"
echo start "CivicFlow Dashboard" cmd /k "cd /d ""%ROOT%"" ^&^& ""%STREAMLIT%"" run apps\dashboard\app.py"
echo start "" "http://127.0.0.1:8501"
exit /b 0
