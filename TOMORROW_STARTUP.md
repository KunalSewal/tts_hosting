# Tomorrow Startup Handoff

This repo was prepared for a fresh RunPod pod start.

## What is already in place

- RunPod hosting app under `app/`
- UI at `/ui`
- API endpoints:
  - `/health`
  - `/ready`
  - `/v1/options`
  - `/v1/users`
  - `/v1/tts`
- RunPod startup scripts in `scripts/`
- Load test in `loadtest/`
- HF backup repo for this project: `Mevearth2/tts_hosting`
- GitHub remote: `origin` -> `https://github.com/KunalSewal/tts_hosting.git`

## Important known issue from the current pod

The current pod container shows the RTX 5090 in `nvidia-smi`, but PyTorch CUDA initialization fails in this container state.
That means this pod is not a reliable baseline for inference, even though the app code is committed.

Evidence seen on the current pod:

- `nvidia-smi` shows `NVIDIA GeForce RTX 5090`
- `NVIDIA_VISIBLE_DEVICES=void`
- `torch.cuda.is_available()` returns `False`
- CUDA driver init returns error `999`

## Tomorrow start checklist

1. Start from a fresh RunPod pod with GPU attached.
2. Confirm the container sees the GPU.
3. Verify CUDA in Python before starting the app:

```bash
python - <<'PY'
import torch
print(torch.cuda.is_available())
print(torch.cuda.device_count())
if torch.cuda.is_available():
    print(torch.cuda.get_device_name(0))
PY
```

4. Pull or copy this repo into `/workspace/tts_hosting`.
5. Restore `.env` with at least:

```bash
HF_TOKEN=...
MODEL_NAME=Mevearth2/Quantized-Merged-TTS
MAX_INFLIGHT_REQUESTS=1
MAX_QUEUE_REQUESTS=32
```

6. Run setup:

```bash
cd /workspace/tts_hosting
bash scripts/runpod_setup.sh
```

7. Start the host:

```bash
cd /workspace/tts_hosting
bash scripts/runpod_start.sh
```

8. Verify local health:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/v1/users
```

9. Open the UI:

```text
http://127.0.0.1:8000/ui
```

10. If needed, expose RunPod HTTP port `8000` and use the public proxy URL.

## Quick demo request

```bash
curl -X POST "http://127.0.0.1:8000/v1/tts?response_mode=wav" \
  -H "Content-Type: application/json" \
  -d '{"utterance":"नमस्ते, आज आप कैसे हैं?","language":"hindi","user_id":"159"}' \
  --output out.wav
```

## Notes

- The repo already contains the improved speaker mapping and UI.
- The `TOMORROW_STARTUP.md` file is meant to be the first thing to read after pulling the repo.
- Keep this repo under `/workspace/tts_hosting` so it survives pod restarts better.
