@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  ROBO1040 OCR API - Windows setup (no Docker)
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found on PATH.
  echo Install Python 3.11+ from https://www.python.org/downloads/
  echo Enable "Add python.exe to PATH" during install.
  exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
  echo ERROR: Need Python 3.10 or newer.
  python --version
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtualenv .venv ...
  python -m venv .venv
  if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat

echo Upgrading pip ...
python -m pip install --upgrade pip

echo Installing PaddlePaddle CPU (this can take several minutes) ...
python -m pip install --default-timeout=180 paddlepaddle==3.2.0
if errorlevel 1 (
  echo Trying PaddlePaddle official CPU index ...
  python -m pip install --default-timeout=180 paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
  if errorlevel 1 exit /b 1
)

echo Installing app requirements ...
python -m pip install --default-timeout=180 -r requirements.txt
if errorlevel 1 exit /b 1

if not exist ".env" (
  copy /Y .env.example .env >nul
  echo Created .env from .env.example
)

echo.
echo Downloading OCR models (first time only, needs internet) ...
set PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
python scripts\download_models.py
if errorlevel 1 (
  echo WARNING: online model download failed — trying bundled models\ folder ...
  call install_local_models.bat
)

if exist "models\PP-OCRv5_mobile_det" (
  if not exist "%USERPROFILE%\.paddlex\official_models\PP-OCRv5_mobile_det" (
    call install_local_models.bat
  )
)

echo.
echo ============================================
echo  Setup complete.
echo  Run API:     run_windows.bat
echo  Dev (reload): run_dev_windows.bat
echo  Health:      http://127.0.0.1:8010/health
echo  Docs:        http://127.0.0.1:8010/docs
echo  API key:     X-API-Key  (default robo1040 in .env)
echo  Handoff doc: KT.md
echo ============================================
echo.
echo NOTE: Scanned PDFs need Poppler on Windows.
echo   1^) Download poppler for Windows
echo   2^) Add its bin folder to PATH
echo   Digital/text PDFs work without Poppler via PyMuPDF.
echo.
endlocal
exit /b 0
