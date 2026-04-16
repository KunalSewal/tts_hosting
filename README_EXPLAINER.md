# README_EXPLAINER

Purpose: give strong project context to humans and Copilot agents running on a RunPod pod.

## Project summary

This project hosts an Indic multilingual TTS model behind an HTTP API, with a small input surface for end users:
- utterance
- language
- user_id

The service applies tuned inference defaults server-side and returns generated audio.

## Source model and pipeline context

Base model details:
- Model lineage is based on `snorbyte/snorTTS-Indic-v0`
- Hosted checkpoint currently used by this project: `Mevearth2/Quantized-Merged-TTS`
- Architecture family: LLaMA-style causal LM generating audio tokens
- Audio decode backend: SNAC (`hubertsiuzdak/snac_24khz`)

High-level generation flow:
1. Build prompt with language + speaker id + utterance
2. Generate SNAC token ids with the LM
3. Convert token stream into SNAC codebooks
4. Decode to 24 kHz waveform
5. Apply optional post-process (speed, denoise)

Prompt format used:
`<custom_token_3><|begin_of_text|>{language}{user_id}: {utterance}<|eot_id|><custom_token_4><custom_token_5><custom_token_1>`

## Data context (important for future finetuning)

Training dataset reference:
- HF dataset: `snorbyte/indic-tts-sample-snac-encoded`

Observed splits:
- `stage_1`
- `stage_2`
- `eval`

Common columns in all splits:
- utterance
- language
- emotion
- type
- act
- rating
- gender
- age
- environment
- user
- snac_codes
- stage

Language set:
- hindi
- tamil
- telugu
- marathi
- kannada
- malayalam
- punjabi
- gujarati
- bengali

Note for retraining work:
- The hosted dataset split names are not `train/valid/test`; scripts should use `stage_1`, `stage_2`, `eval` explicitly.

## Speaker mapping context

This project includes language-speaker validation and recommended speed defaults in `app/speaker_map.py`.

Current practical mapping by language:
- hindi: 159, 49, 43
- tamil: 188, 128, 176
- bengali: 125
- malayalam: 189, 124
- kannada: 142, 138, 131, 59
- telugu: 69, 133
- punjabi: 191, 67, 201
- gujarati: 62, 190
- marathi: 205, 82, 199, 203

## What has already been implemented

Production starter API:
- `app/main.py`
  - `POST /v1/tts` (inputs: utterance, language, user_id)
  - `GET /v1/options` (dropdown data for UI)
  - `GET /health`
  - `GET /ready`

Inference runtime:
- `app/runtime.py`
  - one-time model load
  - runtime defaults for generation
  - prompt construction
  - token-to-audio decode
  - wav bytes response

Schemas:
- `app/schemas.py`

Speaker map and validation:
- `app/speaker_map.py`

Load test starter:
- `loadtest/locustfile.py`
- `loadtest/requirements.txt`

RunPod no-docker scripts:
- `scripts/runpod_setup.sh`
- `scripts/runpod_start.sh`

## Important environment variables

Main:
- `MODEL_NAME` (default `Mevearth2/Quantized-Merged-TTS`)
- `HF_TOKEN`

Service behavior:
- `MAX_INFLIGHT_REQUESTS`
- `TTS_TEMPERATURE`
- `TTS_TOP_P`
- `TTS_REPETITION_PENALTY`
- `TTS_MAX_SEQ_LENGTH`
- `TTS_MAX_WORDS`
- `TTS_DENOISE`

Template file:
- `.env.example` (no secrets)
Actual runtime secrets:
- `.env` (do not commit)

## Why no-docker path exists

Docker image builds were unstable due to slow network/timeouts while downloading large Python wheels in some environments.

Current recommended fast path:
1. Open RunPod PyTorch pod
2. Clone `tts_hosting` into `/workspace/tts_hosting`
3. Run `scripts/runpod_setup.sh`
4. Run `scripts/runpod_start.sh`

## Current known constraints

- Generation can be slow for long utterances, so word limits are enforced.
- Denoise dependencies are intentionally optional to reduce deployment friction.
- 5090 GPUs require newer PyTorch builds; verify pod torch compatibility first.

## What to do next (execution plan)

Phase 1: Stabilize endpoint
1. Deploy via no-docker RunPod path
2. Verify `/ready` and sample `/v1/tts` calls
3. Confirm language-user validation behavior

Phase 2: Frontend readiness
1. Use `/v1/options` for language and speaker dropdowns
2. Keep only 3 user inputs in UI
3. Keep generation knobs hidden on backend defaults

Phase 3: Load testing
1. Run Locust against pod URL
2. Sweep concurrency: 1, 2, 4, 8, 12
3. Track p50/p95/p99 latency and error rate
4. Set stable `MAX_INFLIGHT_REQUESTS`

Phase 4: Production hardening
1. Add API authentication
2. Add structured logs and metrics
3. Add queue/backpressure policy and request timeout policy
4. Add autoscaling strategy and cost-per-request reporting

## For Copilot agents on pod

When helping on this repo, prioritize:
1. Reliability over feature creep
2. Keeping API input surface simple
3. Preserving speaker/language validation
4. Avoiding dependency bloat unless requested
5. Not committing secrets from `.env`

If modifying runtime behavior, always keep:
- prompt format compatibility
- speaker mapping checks
- deterministic server defaults unless explicitly changed
