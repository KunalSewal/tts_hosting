#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/workspace/tts_hosting}"
VENV_PATH="${VENV_PATH:-/workspace/.venv-tts}"
PORT="${PORT:-8000}"

if [[ ! -d "$ROOT_DIR" ]]; then
  echo "ERROR: ROOT_DIR '$ROOT_DIR' does not exist."
  exit 1
fi

if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
  echo "ERROR: virtual env not found at '$VENV_PATH'."
  echo "Run scripts/runpod_setup.sh first."
  exit 1
fi

cd "$ROOT_DIR"
source "$VENV_PATH/bin/activate"

if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

# Some pod images set this globally but do not ship hf_transfer,
# which breaks model downloads at startup.
export HF_HUB_ENABLE_HF_TRANSFER="0"

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
