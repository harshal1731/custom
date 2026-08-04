# ROBO1040 OCR API — Knowledge Transfer (KT)

You own this project going forward. This package is the full source so you can **install, run, change code, and test**.

---

## 1. What this project does

Self-hosted FastAPI OCR API for US tax PDFs:

| Form type | Extractor file |
|-----------|----------------|
| W-2 | `app/ocr/extractors/w2.py` |
| 1099-INT | `app/ocr/extractors/form_1099_int.py` |
| 1099-DIV | `app/ocr/extractors/form_1099_div.py` |
| 5498-SA | `app/ocr/extractors/form_5498_sa.py` |
| Consolidated Brokerage Statement | `app/ocr/extractors/brokerage.py` |

**API (same as Docker):**

- Base URL: `http://127.0.0.1:8010`
- Health: `GET /health`
- Extract: `POST /api/v1/extract` with header `X-API-Key` and multipart PDF `file`
- Interactive docs: `http://127.0.0.1:8010/docs`
- Default API key: `robo1040` (change in `.env`)

---

## 2. First-time setup (your machine)

### Requirements

- Python **3.10+** (3.11 recommended)
- Internet (first setup downloads packages + OCR models)
- **Poppler** on PATH for scanned PDFs (digital/text PDFs often work without it via PyMuPDF)

### Windows

```bat
setup_windows.bat
```

### Linux / macOS

```bash
chmod +x setup_linux.sh run_linux.sh run_dev_linux.sh
# Ubuntu/Debian scans:
sudo apt-get install -y poppler-utils libgl1 libgomp1
./setup_linux.sh
```

What setup does:

1. Creates `.venv`
2. `pip install paddlepaddle` + `pip install -r requirements.txt`
3. Copies `.env.example` → `.env`
4. Runs `scripts/download_models.py`

### Manual pip (if you prefer)

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install paddlepaddle==3.2.0
pip install -r requirements.txt
copy .env.example .env
python scripts\download_models.py
```

---

## 3. Run the API

**Normal run:**

```bat
run_windows.bat
```

**Dev run (auto-reload when you edit Python):**

```bat
run_dev_windows.bat
```

Then open http://127.0.0.1:8010/docs

**Test extract:**

```bat
test_extract.bat C:\path\to\form.pdf
```

Or:

```bat
curl.exe -s -H "X-API-Key: robo1040" -F "file=@C:\path\to\form.pdf;type=application/pdf" http://127.0.0.1:8010/api/v1/extract
```

---

## 4. How to change code (day-to-day)

1. Start with `run_dev_windows.bat` (reload on save)
2. Edit files under `app/`
3. Hit `/api/v1/extract` again (or use `/docs`)
4. Run unit tests before committing:

```bat
.venv\Scripts\activate
pytest -q
```

### Where to edit for common tasks

| Goal | Start here |
|------|------------|
| Wrong form type | `app/ocr/classifier.py` |
| Missing/wrong field on a form | matching file under `app/ocr/extractors/` |
| Junk names / money cleanup | `app/ocr/validators.py` |
| Digital PDF vs OCR path | `app/ocr/digital_pdf.py`, `app/ocr/document_loader.py` |
| Pipeline order (OCR → classify → extract) | `app/ocr/pipeline.py` |
| API routes / auth | `app/main.py`, `app/auth.py` |
| Settings / feature flags | `app/config.py` + `.env` |
| Shared field geometry helpers | `app/ocr/field_engine.py` |
| Label memory patterns | `training/learned_patterns.json` |

**Important:** After changing `.env`, restart the API (settings are cached).

---

## 5. Architecture (short)

```
PDF upload
  → document_loader  (digital PDF text OR OCR / PP-Structure / optional VL)
  → classifier       (form_type)
  → extractors       (form-specific fields)
  → KIE merge + schema extract + validators
  → JSON response (fields + confidence)
```

Key modules:

- `app/main.py` — FastAPI entry
- `app/ocr/pipeline.py` — orchestration
- `app/ocr/engine.py` — PaddleOCR
- `app/ocr/structure.py` — PP-StructureV3
- `app/schemas/response.py` — response models

---

## 6. Config (`.env`)

Matches team Docker defaults. Useful flags:

```env
API_KEY=robo1040
USE_DIGITAL_PDF=true
USE_PP_STRUCTURE=true
USE_KIE=true
USE_PADDLEOCR_VL=true
USE_SCHEMA_EXTRACT=true
LABEL_MEMORY_PATH=training/learned_patterns.json
```

If VL is heavy/broken on your PC:

```env
USE_PADDLEOCR_VL=false
```

---

## 7. Accuracy / samples

Team samples historically lived next to the project, e.g.:

`..\01 - ROBO - Sample PDF Document - 10 Set\`

Ground truth:

- `training/ground_truth.json`
- Live eval (API must be running): `scripts/test_all_samples_live.py`
- Retest fails: `scripts/retest_fails_live.py`

Pass rule used recently: correct `form_type` + enough key fields filled (≥70%), or blank-template pass when classified correctly with no identity/money fields.

Last known team eval on samples: **50/50 (100%)** after classifier/extractor fixes — re-run eval after your changes.

---

## 8. Optional Docker later

This package is meant for **local Python development**.  
If you later want Docker like the original team setup, copy `Dockerfile` + `docker-compose.yml` from the original repo (port map `8010:8000`, mount `./app`).

---

## 9. Folder map

```
app/                 ← change code here
scripts/             ← eval, model download, debug helpers
tests/               ← pytest
training/            ← ground truth + learned_patterns.json
requirements.txt     ← pip deps
.env.example         ← template for .env
setup_windows.bat    ← one-time install
run_windows.bat      ← start API
run_dev_windows.bat  ← start API with --reload
KT.md                ← this handoff doc
README.md            ← quick start
```

---

## 10. Handoff checklist

- [ ] `setup_windows.bat` (or Linux setup) completed
- [ ] `http://127.0.0.1:8010/health` returns ok
- [ ] Extract one PDF via `/docs` or `test_extract.bat`
- [ ] Edit a comment in `app/main.py`, confirm `run_dev_*.bat` reloads
- [ ] `pytest -q` passes
- [ ] Read `classifier.py` + one extractor for the form you will work on first

Questions about samples / ground truth / Docker image: ask the previous owner for the sample PDF folder and any private `.env` keys beyond the default.
