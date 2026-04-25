#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/workspace/tts_hosting}"
VENV_PATH="${VENV_PATH:-/workspace/.venv-tts}"
PORT="${PORT:-8000}"
LOG_FILE="${LOG_FILE:-/workspace/tts_hosting/server.log}"

if [[ ! -d "$ROOT_DIR" ]]; then
  echo "ERROR: ROOT_DIR '$ROOT_DIR' does not exist."
  exit 1
fi

# Keep RunPod platform services (SSH/Jupyter/nginx) alive.
PLATFORM_PID=""
if [[ -x "/start.sh" ]]; then
  /start.sh &
  PLATFORM_PID="$!"
fi

# First-boot convenience: set up runtime only when venv is missing.
if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
  bash "$ROOT_DIR/scripts/runpod_setup.sh"
fi

cd "$ROOT_DIR"
source "$VENV_PATH/bin/activate"

if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

export HF_HUB_ENABLE_HF_TRANSFER="0"

# Start API only if not already running.
if ! pgrep -f "uvicorn app.main:app" >/dev/null 2>&1; then
  nohup uvicorn app.main:app --host 0.0.0.0 --port "$PORT" >"$LOG_FILE" 2>&1 &
  echo "Started TTS API on :$PORT (log: $LOG_FILE)"
else
  echo "TTS API is already running; skipping duplicate start"
fi

# Keep PID 1 alive by waiting on platform process where available.
if [[ -n "$PLATFORM_PID" ]]; then
  wait "$PLATFORM_PID"
else
  tail -f /dev/null
fi
