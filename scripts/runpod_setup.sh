#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/workspace/tts_hosting}"
VENV_PATH="${VENV_PATH:-/workspace/.venv-tts}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}"

if [[ ! -d "$ROOT_DIR" ]]; then
  echo "ERROR: ROOT_DIR '$ROOT_DIR' does not exist."
  echo "Clone/copy tts_hosting there first."
  exit 1
fi

retry_pip_install() {
  local install_target="$1"
  for i in 1 2 3 4 5; do
    echo "pip install attempt ${i}/5"
    if pip install --retries 20 --timeout 240 --prefer-binary $install_target; then
      return 0
    fi
    echo "pip install failed, retrying in 20s..."
    sleep 20
  done
  echo "pip install failed after 5 attempts"
  return 1
}

sudo apt-get update
sudo apt-get install -y --no-install-recommends ffmpeg sox libsox-dev libsndfile1

$PYTHON_BIN -m venv "$VENV_PATH"
source "$VENV_PATH/bin/activate"

pip install --upgrade pip setuptools wheel

# Explicit torch install for modern RunPod GPUs (including RTX 5090).
retry_pip_install "--index-url $TORCH_INDEX_URL torch>=2.8.0 torchaudio>=2.8.0"

# Install the remaining app dependencies.
retry_pip_install "-r $ROOT_DIR/requirements.txt"

echo "Setup complete."
echo "Activate with: source $VENV_PATH/bin/activate"
