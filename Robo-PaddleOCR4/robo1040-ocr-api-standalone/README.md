# ROBO1040 OCR API — Developer package

Full source for the colleague who will **own and develop** this project.

**Start here for handoff:** open [KT.md](KT.md) (setup, architecture, where to edit code, tests).

## Quick start

```bat
setup_windows.bat
run_dev_windows.bat
```

- API: http://127.0.0.1:8010  
- Docs: http://127.0.0.1:8010/docs  
- Auth header: `X-API-Key: robo1040` (from `.env`)

Linux/macOS: `./setup_linux.sh` then `./run_dev_linux.sh`

## Daily workflow

1. Activate venv: `.venv\Scripts\activate`
2. Run with reload: `run_dev_windows.bat`
3. Change code under `app/`
4. Test: `pytest -q` and/or upload a PDF in `/docs`

## Install only (manual)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install paddlepaddle==3.2.0
pip install -r requirements.txt
copy .env.example .env
python scripts\download_models.py
```

## Call extract

```bat
curl.exe -s -H "X-API-Key: robo1040" ^
  -F "file=@C:\path\to\form.pdf;type=application/pdf" ^
  http://127.0.0.1:8010/api/v1/extract
```

## Notes

- Scanned PDFs need **Poppler** on PATH; digital PDFs usually do not
- First OCR request can be slow (model warm-up)
- Do not commit secrets; keep real keys only in local `.env`
- See **KT.md** for form extractors, pipeline, and accuracy scripts

### Windows Poppler (required for scanned PDFs)

If `/extract` returns an error about Poppler / page count:

1. Download: https://github.com/oschwartz10612/poppler-windows/releases  
2. Unzip (e.g. `C:\poppler\`)  
3. Add `...\Library\bin` (or `...\bin`) to **System PATH**  
4. Open a **new** terminal and restart `run_windows.bat` / `run_dev_windows.bat`  
5. Check: `pdftoppm -v` should print a version

### Offline / no model hoster

If extract fails with **No available model hosting platforms detected**:

1. Copy the package `models\` folder (PP-OCRv5_mobile_det + rec) onto that PC  
2. Run `install_local_models.bat`  
3. In `.env` set:
   ```env
   USE_PP_STRUCTURE=false
   USE_PADDLEOCR_VL=false
   ```
4. Restart the API  

Models are also read from `.\models\` next to the app if present.
