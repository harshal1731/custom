#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================"
echo " ROBO1040 OCR API - Linux/macOS setup"
echo "============================================"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY

if [[ ! -x .venv/bin/python ]]; then
  echo "Creating virtualenv .venv ..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip

echo "Tip: install poppler for scanned PDFs"
echo "  Debian/Ubuntu: sudo apt-get install -y poppler-utils libgl1 libgomp1"
echo "  macOS:         brew install poppler"

echo "Installing PaddlePaddle CPU ..."
python -m pip install --default-timeout=180 paddlepaddle==3.2.0 \
  || python -m pip install --default-timeout=180 paddlepaddle==3.2.0 \
       -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

python -m pip install --default-timeout=180 -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
python scripts/download_models.py || echo "WARNING: model download incomplete"

echo
echo "Setup complete."
echo "  Run API:      ./run_linux.sh"
echo "  Dev (reload): ./run_dev_linux.sh"
echo "  Health:       http://127.0.0.1:8010/health"
echo "  Docs:         http://127.0.0.1:8010/docs"
echo "  Handoff doc:  KT.md"
