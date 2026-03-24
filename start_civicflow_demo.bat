@echo off
setlocal

cd /d "%~dp0"
for %%I in ("%~dp0.") do set "ROOT=%%~fI"

if exist "%ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if /I "%~1"=="--dry-run" goto dry_run

where "%PYTHON%" >nul 2>nul
if errorlevel 1 (
    echo Could not find Python runtime: %PYTHON%
    echo Activate or create the virtual environment first, then try again.
    pause
    exit /b 1
)

echo Clearing any old CivicFlow processes on ports 8000 and 8501...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /PID %%P /F >nul 2>nul
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do taskkill /PID %%P /F >nul 2>nul
timeout /t 1 /nobreak >nul

echo Starting CivicFlow API...
start "CivicFlow API" cmd /k "cd /d ""%ROOT%"" && set PYTHONPATH=%ROOT% && ""%PYTHON%"" -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000"

echo Waiting for backend startup...
powershell -NoProfile -Command "for ($i=0; $i -lt 45; $i++) { try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"
if errorlevel 1 (
    echo Backend did not become ready at http://127.0.0.1:8000/health
    echo Check the 'CivicFlow API' window for the error details.
    pause
    exit /b 1
)

echo Starting CivicFlow Dashboard...
start "CivicFlow Dashboard" cmd /k "cd /d ""%ROOT%"" && set PYTHONPATH=%ROOT% && ""%PYTHON%"" -m streamlit run apps\dashboard\app.py --server.headless true --browser.gatherUsageStats false"

echo Waiting for frontend startup...
powershell -NoProfile -Command "for ($i=0; $i -lt 45; $i++) { try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501 | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"
if errorlevel 1 (
    echo Frontend did not become ready at http://127.0.0.1:8501
    echo Check the 'CivicFlow Dashboard' window for the error details.
    pause
    exit /b 1
)

echo Opening dashboard in your browser...
start "" "http://127.0.0.1:8501"

echo CivicFlow is ready.
echo Close the two service windows when you are done.
exit /b 0

:dry_run
echo ROOT=%ROOT%
echo PYTHON=%PYTHON%
echo for /f "tokens=5" %%%%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /PID %%%%P /F
echo for /f "tokens=5" %%%%P in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do taskkill /PID %%%%P /F
echo start "CivicFlow API" cmd /k "cd /d ""%ROOT%"" ^&^& set PYTHONPATH=%ROOT% ^&^& ""%PYTHON%"" -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000"
echo powershell -NoProfile -Command "for ($i=0; $i -lt 45; $i++) { try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health ^| Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"
echo start "CivicFlow Dashboard" cmd /k "cd /d ""%ROOT%"" ^&^& set PYTHONPATH=%ROOT% ^&^& ""%PYTHON%"" -m streamlit run apps\dashboard\app.py --server.headless true --browser.gatherUsageStats false"
echo powershell -NoProfile -Command "for ($i=0; $i -lt 45; $i++) { try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501 ^| Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"
echo start "" "http://127.0.0.1:8501"
exit /b 0
