# Fine-tuning VI-LayoutXLM KIE on US tax forms

This folder contains scripts to prepare training data and fine-tune **VI-LayoutXLM**
(SER + RE) on your sample PDFs for 90%+ key-value accuracy across issuers.

## Overview

| Step | Script | Output |
|------|--------|--------|
| 1. Label samples | `prepare_training_data.py` | COCO-style KIE JSON + class list |
| 2. Fine-tune SER/RE | PaddleOCR ppstructure (external) | `inference/ser_*`, `inference/re_*` |
| 3. Deploy | Set `KIE_SER_MODEL_DIR` in `.env` | Runtime KIE merge in API |

## Prerequisites

- PaddleOCR source checkout (for `ppstructure/kie/` training scripts)
- 500+ labeled PDF pages with **generic IRS field labels** (not bank names)
- GPU recommended for training (CPU inference works after export)

## Step 1 — Prepare labels

```bash
python scripts/kie/prepare_training_data.py \
  --pdf-dir "path/to/sample/pdfs" \
  --labels path/to/ground_truth.json \
  --out-dir training/kie_tax_forms
```

Ground truth JSON format:

```json
{
  "w2_sample_01.pdf": {
    "Employee's social security number": "XXX-XX-1234",
    "1 Wages, tips, other compensation": "2800.00"
  }
}
```

## Step 2 — Fine-tune (PaddleOCR ppstructure)

Follow [PaddleOCR KIE training docs](https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppstructure/kie/README.md):

1. Convert prepared data to XFUND-style SER/RE format
2. Train SER: `configs/kie/vi_layoutxlm/ser_vi_layoutxlm_*.yml`
3. Train RE: `configs/kie/vi_layoutxlm/re_vi_layoutxlm_*.yml`
4. Export inference models to a directory

Entity classes should use **IRS box labels** only, e.g.:

- `QUESTION`: field label text (Box 1, Payer's TIN, etc.)
- `ANSWER`: field value (amount, TIN, name, address)

## Step 3 — Deploy fine-tuned models

```env
KIE_SER_MODEL_DIR=/models/kie/ser_tax_forms
KIE_RE_MODEL_DIR=/models/kie/re_tax_forms
USE_KIE=true
```

Place `latest_predictions.json` in the SER model dir for batch pre-compute,
or integrate `predict_kie_token_ser_re.py` as a subprocess hook.

## Notes

- Do **not** label by issuer name — use IRS structure only
- Fine-tuning 500 samples typically yields 85–92% on heterogeneous forms
- Combine with PyMuPDF (digital) + PP-StructureV3 (scanned) for best results
