# snorTTS Hosting Pipeline (RunPod + Load Testing)

This folder contains a complete starter pipeline for hosting your TTS model with a simple API and testing parallel load.

## 1) What users get

- A single HTTP endpoint: `POST /v1/tts`
- Inputs: `utterance`, `language`, `user_id`
- Defaults are server-side tuned.
- Optional options endpoint for dropdowns: `GET /v1/options`

## 2) API Contract

### POST /v1/tts

Request body:

```json
{
  "utterance": "नमस्ते, आप कैसे हैं?",
  "language": "hindi",
  "user_id": "159"
}
```

Response modes:

- `response_mode=wav` (default): returns `audio/wav`
- `response_mode=json`: returns base64 audio and metadata

Example:

```bash
curl -X POST "http://localhost:8000/v1/tts?response_mode=wav" \
  -H "Content-Type: application/json" \
  -d '{"utterance":"नमस्ते, आप कैसे हैं?","language":"hindi","user_id":"159"}' \
  --output out.wav
```

### GET /v1/options

Returns dropdown-compatible language/speaker map and defaults.

### GET /health

Simple liveness check.

### GET /ready

True once model and decoder are loaded.

## 3) Local run (before RunPod)

1. Copy env:

```bash
cp .env.example .env
```

2. Set `HF_TOKEN` in `.env`.

3. Build image:

```bash
docker build -t snortts-api:latest .
```

4. Run container:

```bash
docker run --gpus all --env-file .env -p 8000:8000 snortts-api:latest
```

Optional (only if you want denoise enabled in production image):

```bash
# Add these to requirements and rebuild only if needed
pip install librosa==0.11.0 deepfilternet==0.5.6
```

5. Smoke test:

```bash
curl http://localhost:8000/ready
```

## 4) RunPod deployment steps

1. Push image to Docker Hub or GHCR.
2. Create RunPod GPU Pod.
3. Set container image to your pushed tag.
4. Expose port `8000`.
5. Add env vars from `.env.example` in RunPod UI.
6. Wait for startup, then test `/ready`.
7. Test `/v1/tts`.

## 4B) RunPod without Docker (recommended if image build is flaky)

You can deploy directly on a standard RunPod PyTorch pod without building an image.

1. Create a GPU Pod from a PyTorch template (CUDA 12.1 compatible).
2. Expose port `8000`.
3. In Pod terminal, clone or upload this `tts_hosting` folder under `/workspace/tts_hosting`.
4. Create `.env` (copy from `.env.example`) and set at least `HF_TOKEN`.
5. Run setup once:

```bash
cd /workspace/tts_hosting
bash scripts/runpod_setup.sh
```

Note: setup installs `torch` and `torchaudio` from the CUDA 12.8 index for better compatibility with newer GPUs (including RTX 5090-class pods).

6. Start API server:

```bash
cd /workspace/tts_hosting
bash scripts/runpod_start.sh
```

7. Check readiness from your local machine:

```bash
curl http://<runpod-public-ip-or-url>:8000/ready
```

8. Test generation:

```bash
curl -X POST "http://<runpod-public-ip-or-url>:8000/v1/tts?response_mode=wav" \
  -H "Content-Type: application/json" \
  -d '{"utterance":"नमस्ते, आप कैसे हैं?","language":"hindi","user_id":"159"}' \
  --output out.wav
```

Tip: if the pod restarts often, keep code and venv under `/workspace` so it persists.

## 5) Load testing with Locust

From this directory:

```bash
pip install -r loadtest/requirements.txt
```

Then run:

```bash
locust -f loadtest/locustfile.py --host http://<your-runpod-url>
```

Or headless:

```bash
locust -f loadtest/locustfile.py --host http://<your-runpod-url> \
  --users 10 --spawn-rate 2 --run-time 5m --headless
```

## 6) Suggested test plan

- Step 1: users 1, 2, 4, 8, 12
- Step 2: record p50, p95, p99 latency
- Step 3: record failure rate and GPU memory usage
- Step 4: choose safe `MAX_INFLIGHT_REQUESTS`

## 7) Key files

- `app/main.py`: FastAPI endpoints
- `app/runtime.py`: model load and synthesis runtime
- `app/speaker_map.py`: language -> speaker IDs + default speed
- `loadtest/locustfile.py`: parallel load test script
- `Dockerfile`: deployable image for RunPod
