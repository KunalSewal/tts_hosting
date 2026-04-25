# TTS Hosting (RunPod, RTX 5090 Ready)

Production starter for hosting `Mevearth2/Quantized-Merged-TTS` behind a FastAPI endpoint.

Inference behavior is aligned with `snorbyte/snorTTS-Indic-v0`:

- prompt format: `<custom_token_3><|begin_of_text|>{language}{user_id}: {utterance}<|eot_id|><custom_token_4><custom_token_5><custom_token_1>`
- SNAC decode at 24kHz
- language-speaker mapping with recommended speedups

## Features

- `POST /v1/tts` (wav or json response)
- `GET /v1/options` (languages and users for UI)
- `GET /v1/users` (user map)
- `GET /metrics` (inflight and queue metrics)
- `GET /health` and `GET /ready`
- `GET /ui` simple browser UI

## Version Requirements

## Runtime and platform

- RunPod GPU pod
- NVIDIA RTX 5090 class GPU
- Python 3.10+ (tested on Python 3.12 in this pod)
- CUDA 12.8 wheel index for PyTorch

## PyTorch

- `torch>=2.8.0`
- `torchaudio>=2.8.0`

Installed by `scripts/runpod_setup.sh` from:

- `https://download.pytorch.org/whl/cu128`

## Python packages

Pinned in `requirements.txt`:

- fastapi `0.115.12`
- uvicorn `0.34.2`
- pydantic `2.11.3`
- numpy `1.26.4`
- soundfile `0.13.1`
- loguru `0.7.3`
- huggingface_hub `0.31.1`
- transformers `4.51.3`
- snac `1.2.1`

## First-Time Setup (one-time per fresh image)

1. SSH into pod.
2. Go to project.
3. Configure env.
4. Run setup script.

```bash
cd /workspace/tts_hosting
cp .env.example .env
# edit .env and set HF_TOKEN
bash scripts/runpod_setup.sh
```

## Start Service (manual)

```bash
cd /workspace/tts_hosting
bash scripts/runpod_start.sh
```

You do not need to manually activate the venv; the script does it.

## Verify Service

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/v1/options
```

Public URL pattern:

```text
https://<pod-id>-8000.proxy.runpod.net/ui
```

Example for your pod:

```text
https://154vi25zg62qb0-8000.proxy.runpod.net/ui
```

## API Usage

## Generate wav

```bash
curl -X POST "http://127.0.0.1:8000/v1/tts?response_mode=wav" \
  -H "Content-Type: application/json" \
  -d '{"utterance":"नमस्ते, आज आप कैसे हैं?","language":"hindi","user_id":"159"}' \
  --output out.wav
```

## Generate json

```bash
curl -X POST "http://127.0.0.1:8000/v1/tts?response_mode=json" \
  -H "Content-Type: application/json" \
  -d '{"utterance":"नमस्ते, आज आप कैसे हैं?","language":"hindi","user_id":"159"}'
```

## Important Environment Variables

Set in `.env`:

- `MODEL_NAME=Mevearth2/Quantized-Merged-TTS`
- `HF_TOKEN=<your_hf_token>`
- `MAX_INFLIGHT_REQUESTS=2`
- `MAX_QUEUE_REQUESTS=16`
- `TTS_MAX_SEQ_LENGTH=2048`
- `TTS_MAX_NEW_TOKENS=1024`
- `TTS_DO_SAMPLE=false`
- `TTS_TORCH_DTYPE=bfloat16`
- `TTS_DENOISE=false`

## Auto-start on Pod Restart (recommended)

If you set a custom start command that directly launches uvicorn, you can break default RunPod startup (SSH/Jupyter).

Use this Start Command in RunPod settings:

```bash
bash -lc 'cd /workspace/tts_hosting && bash scripts/runpod_autostart.sh'
```

This script:

- preserves RunPod default `/start.sh`
- runs setup only if venv is missing
- starts API in background and logs to `server.log`

## Restart Behavior After Stop/Start

- Without RunPod Start Command: service is not auto-up; run `scripts/runpod_start.sh` manually.
- With the autostart command above: service starts automatically after pod starts.

## Load Testing

```bash
source /workspace/.venv-tts/bin/activate
pip install -r loadtest/requirements.txt
locust -f loadtest/locustfile.py --host http://127.0.0.1:8000
```

Headless example:

```bash
locust -f loadtest/locustfile.py --host http://127.0.0.1:8000 \
  --users 8 --spawn-rate 2 --run-time 5m --headless
```

## Teammate Handoff

If someone else has pod access:

1. SSH in.
2. `cd /workspace/tts_hosting`
3. If first run on fresh image: `bash scripts/runpod_setup.sh`
4. Start: `bash scripts/runpod_start.sh`
5. Open `/ui` on the proxy URL.

## Repository Contents (kept intentionally)

- `app/` API, runtime, UI
- `scripts/` setup, start, autostart
- `loadtest/` Locust workload
- `requirements.txt` pinned app deps
- `.env.example` runtime template
