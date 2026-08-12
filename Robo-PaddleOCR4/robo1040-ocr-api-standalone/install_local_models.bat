@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Installing bundled OCR models into %%USERPROFILE%%\.paddlex\official_models ...
set "TARGET=%USERPROFILE%\.paddlex\official_models"
if not exist "models\PP-OCRv5_mobile_det" (
  echo ERROR: models\ folder missing. Re-copy the package that includes models\.
  exit /b 1
)

mkdir "%TARGET%" 2>nul
xcopy /E /I /Y "models\PP-OCRv5_mobile_det" "%TARGET%\PP-OCRv5_mobile_det\" >nul
xcopy /E /I /Y "models\PP-OCRv5_mobile_rec" "%TARGET%\PP-OCRv5_mobile_rec\" >nul

if not exist "%TARGET%\PP-OCRv5_mobile_det\inference.yml" if not exist "%TARGET%\PP-OCRv5_mobile_det\inference.json" (
  echo WARNING: det model files may be incomplete
)
echo Done.
echo Models at: %TARGET%
echo Next: set USE_PP_STRUCTURE=false and USE_PADDLEOCR_VL=false in .env if offline,
echo then restart run_windows.bat / run_dev_windows.bat
endlocal
exit /b 0
