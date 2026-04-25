import asyncio
import base64
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from loguru import logger

from app.runtime import TTSRuntime, SAMPLE_RATE
from app.schemas import HealthResponse, OptionsResponse, ReadyResponse, TTSJSONResponse, TTSRequest
from app.speaker_map import SUPPORTED_SPEAKERS, validate_language_user

MAX_INFLIGHT = int(os.getenv("MAX_INFLIGHT_REQUESTS", "2"))
MAX_QUEUE = int(os.getenv("MAX_QUEUE_REQUESTS", "16"))
runtime = TTSRuntime()
semaphore = asyncio.Semaphore(MAX_INFLIGHT)
_queued_requests = 0
_queue_lock = asyncio.Lock()


async def _try_enter_queue() -> bool:
    global _queued_requests
    async with _queue_lock:
        if _queued_requests >= MAX_QUEUE:
            return False
        _queued_requests += 1
    return True


async def _leave_queue() -> None:
    global _queued_requests
    async with _queue_lock:
        _queued_requests = max(0, _queued_requests - 1)


async def _current_queued() -> int:
    async with _queue_lock:
        return _queued_requests


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime.load()
    yield


app = FastAPI(title="snorTTS Hosting API", version="1.0.0", lifespan=lifespan)


@app.get("/")
def root() -> dict:
    return {
        "service": "snorTTS Hosting API",
        "routes": ["/health", "/ready", "/metrics", "/v1/options", "/v1/users", "/v1/tts", "/ui"],
    }


@app.get("/ui")
def ui() -> FileResponse:
    return FileResponse(Path(__file__).with_name("ui.html"))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    return ReadyResponse(ready=runtime.is_ready)


@app.get("/metrics")
async def metrics() -> dict:
    queued = await _current_queued()
    inflight = MAX_INFLIGHT - semaphore._value
    return {
        "ready": runtime.is_ready,
        "limits": {
            "max_inflight_requests": MAX_INFLIGHT,
            "max_queue_requests": MAX_QUEUE,
        },
        "runtime": {
            "inflight_requests": inflight,
            "queued_requests": queued,
        },
    }


@app.get("/v1/options", response_model=OptionsResponse)
def options() -> OptionsResponse:
    defaults = {
        "temperature": float(os.getenv("TTS_TEMPERATURE", "0.4")),
        "top_p": float(os.getenv("TTS_TOP_P", "0.9")),
        "repetition_penalty": float(os.getenv("TTS_REPETITION_PENALTY", "1.05")),
    }
    return OptionsResponse(speakers=SUPPORTED_SPEAKERS, defaults=defaults)


@app.get("/v1/users")
def users(language: str | None = None) -> dict:
    if language is None:
        return {"languages": sorted(SUPPORTED_SPEAKERS.keys()), "speakers": SUPPORTED_SPEAKERS}

    if language not in SUPPORTED_SPEAKERS:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{language}'")

    return {"language": language, "speakers": SUPPORTED_SPEAKERS[language]}


@app.post("/v1/tts", response_class=Response)
async def tts(req: TTSRequest, response_mode: str = "wav"):
    if not validate_language_user(req.language, req.user_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user_id '{req.user_id}' for language '{req.language}'",
        )

    if not await _try_enter_queue():
        raise HTTPException(status_code=429, detail="Server is busy, queue is full. Please retry.")

    try:
        await semaphore.acquire()
    finally:
        await _leave_queue()

    try:
        wav_bytes, duration_ms = await asyncio.to_thread(
            runtime.synthesize_wav_bytes,
            req.utterance,
            req.language,
            req.user_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("TTS inference failed")
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}") from exc
    finally:
        semaphore.release()

    request_id = str(uuid.uuid4())
    if response_mode == "json":
        payload = TTSJSONResponse(
            request_id=request_id,
            sample_rate=SAMPLE_RATE,
            duration_ms=duration_ms,
            audio_base64=base64.b64encode(wav_bytes).decode("ascii"),
        )
        return payload

    headers = {
        "X-Request-Id": request_id,
        "X-Duration-Ms": str(duration_ms),
    }
    return Response(content=wav_bytes, media_type="audio/wav", headers=headers)
