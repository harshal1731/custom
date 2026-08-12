@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Virtualenv missing. Run setup_windows.bat first.
  exit /b 1
)

if not exist ".env" (
  copy /Y .env.example .env >nul
)

set PYTHONPATH=%CD%
set PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
set OMP_NUM_THREADS=4

echo ============================================
echo  DEV mode --reload  (restart on code change)
echo  URL:    http://127.0.0.1:8010
echo  Docs:   http://127.0.0.1:8010/docs
echo  Auth:   X-API-Key  (see .env)
echo  Edit:   app\  then save - server reloads
echo  Press Ctrl+C to stop.
echo ============================================
echo.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
endlocal
