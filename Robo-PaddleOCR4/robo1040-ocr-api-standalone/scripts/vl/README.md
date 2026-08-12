# Self-hosted 90%+ path: PaddleOCR-VL + schema extract + fine-tune

This folder prepares labeled data so you can fine-tune document parsing / KIE
on **your** tax PDFs (IRS labels only — no bank/issuer names).

## Current status (this repo)

Already generated:

| Artifact | Path |
|----------|------|
| Draft labels (50 PDFs) | `training/ground_truth_draft.json` |
| Working labels copy | `training/ground_truth.json` |
| Files needing review | `training/needs_review.json` |
| Fine-tune package | `training/vl_finetune/` |
| CPU label memory | `training/learned_patterns.json` |

**Important:** draft labels come from the current OCR API. Wrong/missing fields must be corrected by a human before neural fine-tune, or you will train on errors.

Rebuild drafts:
```bash
python scripts/vl/build_draft_labels.py
```

Mine label memory (CPU, no GPU):
```bash
python scripts/vl/train_from_labels.py --labels training/ground_truth.json --out training/learned_patterns.json
```


```
PDF
 ├─ digital text OK → PyMuPDF
 └─ scan / bad text → PaddleOCR-VL (markdown + layout)
        ↓
 Schema extract (FieldSpec JSON + optional local LLM)
        ↓
 Spatial / validator / confidence
```

## Step 1 — Export empty label template

```bash
python scripts/vl/export_label_template.py --out training/label_template.json
```

## Step 2 — Label samples (ground truth)

Copy the template and fill values from each PDF (human or accountant review):

```json
{
  "01 - Document - Form W-2.pdf": {
    "form_type": "W-2",
    "fields": {
      "Year": "2024",
      "Employee's social security number": "XXX-XX-2930",
      "1 Wages, tips, other compensation": "2800.00"
    }
  }
}
```

Label **IRS field values only**. Do not add employer brand rules in code.

Aim for **200–500** pages across W-2 / 1099-INT / 1099-DIV / 5498-SA / brokerage.

## Step 3 — Build fine-tune package

```bash
python scripts/vl/prepare_finetune_data.py \
  --pdf-dir "path/to/01 - ROBO - Sample PDF Document - 10 Set" \
  --labels training/ground_truth.json \
  --out-dir training/vl_finetune
```

Outputs:
- `manifest.json` — file → fields
- `schemas/` — per-form JSON schemas
- `prompts/` — schema extraction prompts for LoRA / SFT
- `class_list.txt` — QUESTION / ANSWER for LayoutXLM KIE

## Step 4 — Fine-tune options

### A) PaddleOCR-VL (preferred for scans)

1. Install: `pip install -U "paddleocr[doc-parser]"` (PaddlePaddle ≥ 3.2.1; GPU recommended)
2. Download VL model once (first `PaddleOCRVL().predict(...)`)
3. Follow PaddleOCR fine-tune docs for VL / LoRA using `training/vl_finetune/prompts`
4. Point runtime at fine-tuned weights:

```env
USE_PADDLEOCR_VL=true
PADDLEOCR_VL_MODEL_DIR=/models/paddleocr-vl-tax
PADDLEOCR_VL_DEVICE=gpu:0
```

### B) Local schema LLM (Ollama / vLLM)

Fine-tune or instruct-tune a 7B model on `prompts/*.jsonl`, then:

```env
USE_SCHEMA_EXTRACT=true
SCHEMA_LLM_BASE_URL=http://host.docker.internal:11434/v1
SCHEMA_LLM_MODEL=qwen2.5:7b-tax
```

### C) VI-LayoutXLM KIE (SER/RE)

Use `class_list.txt` + XFUND-style conversion (see `scripts/kie/README.md`):

```env
KIE_SER_MODEL_DIR=/models/kie/ser_tax_forms
KIE_RE_MODEL_DIR=/models/kie/re_tax_forms
USE_KIE=true
```

## Step 5 — Evaluate

```bash
python scripts/test_all_samples_live.py
```

Target: **≥90% pass** on the 50-sample set (correct type + ≥70% key-field fill).
Use `field_confidence` to route low-confidence docs to human review.

## Hardware notes

| Mode | Hardware | Latency |
|------|----------|---------|
| PyMuPDF digital | CPU | &lt;1s |
| Schema rules only | CPU | &lt;1s |
| PaddleOCR-VL | GPU strongly preferred | ~3–10s/page |
| Local 7B schema LLM | GPU | +2–8s |

CPU-only VL is possible but often exceeds the 15s SLA.
