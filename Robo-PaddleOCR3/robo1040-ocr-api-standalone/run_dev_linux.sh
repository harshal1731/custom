#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "Virtualenv missing. Run ./setup_linux.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
[[ -f .env ]] || cp .env.example .env

export PYTHONPATH="$PWD"
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"

echo "============================================"
echo " DEV mode --reload  (restart on code change)"
echo " URL:    http://127.0.0.1:8010"
echo " Docs:   http://127.0.0.1:8010/docs"
echo " Auth:   X-API-Key  (see .env)"
echo " Edit:   app/ then save - server reloads"
echo " Press Ctrl+C to stop."
echo "============================================"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
