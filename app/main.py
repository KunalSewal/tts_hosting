import asyncio
import base64
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from loguru import logger

from app.runtime import TTSRuntime, SAMPLE_RATE
from app.schemas import HealthResponse, OptionsResponse, ReadyResponse, TTSJSONResponse, TTSRequest
from app.speaker_map import SUPPORTED_SPEAKERS, validate_language_user

MAX_INFLIGHT = int(os.getenv("MAX_INFLIGHT_REQUESTS", "2"))
runtime = TTSRuntime()
semaphore = asyncio.Semaphore(MAX_INFLIGHT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime.load()
    yield


app = FastAPI(title="snorTTS Hosting API", version="1.0.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    return ReadyResponse(ready=runtime.is_ready)


@app.get("/v1/options", response_model=OptionsResponse)
def options() -> OptionsResponse:
    defaults = {
        "temperature": float(os.getenv("TTS_TEMPERATURE", "0.4")),
        "top_p": float(os.getenv("TTS_TOP_P", "0.9")),
        "repetition_penalty": float(os.getenv("TTS_REPETITION_PENALTY", "1.05")),
    }
    return OptionsResponse(speakers=SUPPORTED_SPEAKERS, defaults=defaults)


@app.post("/v1/tts", response_class=Response)
async def tts(req: TTSRequest, response_mode: str = "wav"):
    if not validate_language_user(req.language, req.user_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user_id '{req.user_id}' for language '{req.language}'",
        )

    async with semaphore:
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
