from typing import Literal, Optional

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    utterance: str = Field(min_length=1, max_length=500)
    language: Literal[
        "hindi",
        "tamil",
        "telugu",
        "marathi",
        "kannada",
        "malayalam",
        "punjabi",
        "gujarati",
        "bengali",
    ]
    user_id: str = Field(min_length=1, max_length=8)


class TTSJSONResponse(BaseModel):
    request_id: str
    sample_rate: int
    duration_ms: int
    audio_base64: str
    output_format: Literal["wav_base64"] = "wav_base64"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    ready: bool


class OptionsResponse(BaseModel):
    speakers: dict
    defaults: dict
