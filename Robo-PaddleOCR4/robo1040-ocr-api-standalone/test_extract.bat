@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Testing local API (same as Docker port 8010)...
curl.exe -s -o NUL -w "health HTTP %%{http_code}\n" http://127.0.0.1:8010/health
if errorlevel 1 (
  echo API not running. Start it with run_windows.bat first.
  exit /b 1
)

if "%~1"=="" (
  echo.
  echo Usage: test_extract.bat path\to\file.pdf
  echo Example: test_extract.bat C:\samples\w2.pdf
  exit /b 0
)

curl.exe -s -H "X-API-Key: robo1040" -F "file=@%~1;type=application/pdf" http://127.0.0.1:8010/api/v1/extract
echo.
endlocal
