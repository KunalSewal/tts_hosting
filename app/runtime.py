import io
import os
import threading
import time
from typing import Optional

import numpy as np
import soundfile as sf
import torch
import torchaudio
from huggingface_hub import login as hf_login
from loguru import logger
from snac import SNAC
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.speaker_map import recommended_speed


TOKENISER_LENGTH = 128256
END_OF_SPEECH_ID = TOKENISER_LENGTH + 2
PAD_TOKEN_ID = TOKENISER_LENGTH + 7
AUDIO_START_ID = TOKENISER_LENGTH + 10
SAMPLE_RATE = 24000

DEFAULTS = {
    "temperature": float(os.getenv("TTS_TEMPERATURE", "0.4")),
    "top_p": float(os.getenv("TTS_TOP_P", "0.9")),
    "repetition_penalty": float(os.getenv("TTS_REPETITION_PENALTY", "1.05")),
    "max_seq_length": int(os.getenv("TTS_MAX_SEQ_LENGTH", "2048")),
    "max_words": int(os.getenv("TTS_MAX_WORDS", "50")),
    "denoise": os.getenv("TTS_DENOISE", "false").lower() == "true",
}


class TTSRuntime:
    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None
        self._snac = None
        self._df_model = None
        self._df_state = None
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._loaded = False
        self._lock = threading.Lock()

    @property
    def is_ready(self) -> bool:
        return self._loaded

    @staticmethod
    def _resolve_hf_token(cli_token: Optional[str]) -> Optional[str]:
        if cli_token:
            return cli_token
        return (
            os.getenv("HF_TOKEN")
            or os.getenv("HUGGINGFACE_TOKEN")
            or os.getenv("HUGGING_FACE_HUB_TOKEN")
        )

    def load(self, model_name: Optional[str] = None, hf_token: Optional[str] = None) -> None:
        with self._lock:
            if self._loaded:
                return

            # Some environments set HF fast transfer globally without
            # installing hf_transfer, which breaks all downloads.
            os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

            model_name = model_name or os.getenv("MODEL_NAME", "Mevearth2/Quantized-Merged-TTS")
            token = self._resolve_hf_token(hf_token)

            if token:
                try:
                    hf_login(token=token, add_to_git_credential=False)
                    logger.info("HF auth success")
                except Exception as exc:
                    logger.warning(f"HF login warning: {exc}")

            logger.info(f"Loading tokenizer/model from {model_name}")
            self._tokenizer = AutoTokenizer.from_pretrained(model_name, token=token)
            self._model = AutoModelForCausalLM.from_pretrained(
                model_name,
                token=token,
                torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
            )
            self._model.to(self._device)
            self._model.eval()

            pad_token = self._tokenizer.decode([PAD_TOKEN_ID])
            self._tokenizer.pad_token = pad_token
            self._tokenizer.padding_side = "left"

            try:
                from unsloth import FastLanguageModel

                FastLanguageModel.for_inference(self._model)
                logger.info("Unsloth inference enabled")
            except Exception:
                logger.info("Unsloth not enabled")

            logger.info("Loading SNAC decoder")
            self._snac = SNAC.from_pretrained("hubertsiuzdak/snac_24khz")

            if DEFAULTS["denoise"]:
                try:
                    from df.enhance import init_df

                    self._df_model, self._df_state, _ = init_df()
                    logger.info("DeepFilter initialized")
                except Exception as exc:
                    logger.warning(f"DeepFilter unavailable: {exc}")

            self._loaded = True

    @staticmethod
    def _build_prompt(utterance: str, language: str, user_id: str) -> str:
        return (
            "<custom_token_3><|begin_of_text|>"
            f"{language}{user_id}: {utterance}"
            "<|eot_id|><custom_token_4><custom_token_5><custom_token_1>"
        )

    @staticmethod
    def _extract_audio_ids(output_ids: torch.Tensor) -> list[int]:
        raw_audio_ids = [tok.item() for tok in output_ids if tok.item() >= AUDIO_START_ID]
        clean = []
        full_groups = len(raw_audio_ids) // 7
        for i in range(full_groups):
            base = i * 7
            for j in range(7):
                clean.append(raw_audio_ids[base + j] - AUDIO_START_ID)
        return clean

    @staticmethod
    def _snac_tokens_to_codebooks(clean_audio_ids: list[int]):
        codes = [[], [], []]
        full_groups = len(clean_audio_ids) // 7

        for i in range(full_groups):
            b = i * 7
            codes[0].append(clean_audio_ids[b + 0])
            codes[1].append(clean_audio_ids[b + 1] - 4096)
            codes[2].append(clean_audio_ids[b + 2] - (2 * 4096))
            codes[2].append(clean_audio_ids[b + 3] - (3 * 4096))
            codes[1].append(clean_audio_ids[b + 4] - (4 * 4096))
            codes[2].append(clean_audio_ids[b + 5] - (5 * 4096))
            codes[2].append(clean_audio_ids[b + 6] - (6 * 4096))

        if len(codes[0]) == 0 or len(codes[1]) == 0 or len(codes[2]) == 0:
            return None

        return [
            torch.tensor(codes[0]).unsqueeze(0),
            torch.tensor(codes[1]).unsqueeze(0),
            torch.tensor(codes[2]).unsqueeze(0),
        ]

    @staticmethod
    def _apply_speed(audio: np.ndarray, speed: float) -> np.ndarray:
        if abs(speed - 1.0) <= 1e-4:
            return audio
        # Prefer Sox tempo when available; some runtime builds omit sox_effects.
        if hasattr(torchaudio, "sox_effects") and hasattr(torchaudio.sox_effects, "apply_effects_tensor"):
            audio_t = torch.from_numpy(audio).unsqueeze(0)
            out_t, _ = torchaudio.sox_effects.apply_effects_tensor(
                audio_t,
                SAMPLE_RATE,
                effects=[["tempo", f"{speed}"]],
            )
            return out_t.squeeze(0).cpu().numpy()

        # Fallback: lightweight time-stretch via interpolation.
        # This keeps service functional even without Sox bindings.
        in_len = int(audio.shape[0])
        out_len = max(1, int(round(in_len / speed)))
        x_old = np.linspace(0.0, 1.0, num=in_len, dtype=np.float64)
        x_new = np.linspace(0.0, 1.0, num=out_len, dtype=np.float64)
        stretched = np.interp(x_new, x_old, audio.astype(np.float64))
        return stretched.astype(np.float32)

    def _apply_denoise(self, audio: np.ndarray) -> np.ndarray:
        if self._df_model is None or self._df_state is None:
            return audio
        try:
            import librosa
            from df.enhance import enhance

            audio_48k = librosa.resample(audio, orig_sr=SAMPLE_RATE, target_sr=48000)
            audio_48k_t = torch.from_numpy(audio_48k).unsqueeze(0)
            denoised = enhance(self._df_model, self._df_state, audio_48k_t)
            denoised_np = denoised.squeeze(0).cpu().numpy()
            return librosa.resample(denoised_np, orig_sr=48000, target_sr=SAMPLE_RATE)
        except Exception as exc:
            logger.warning(f"Denoise failed: {exc}")
            return audio

    def synthesize_wav_bytes(self, utterance: str, language: str, user_id: str) -> tuple[bytes, int]:
        if not self._loaded:
            raise RuntimeError("Runtime is not loaded")

        start = time.perf_counter()
        safe_utterance = " ".join(utterance.split()[: DEFAULTS["max_words"]])
        prompt = self._build_prompt(safe_utterance, language, user_id)
        inputs = self._tokenizer(prompt, add_special_tokens=False, return_tensors="pt")

        input_ids = inputs.input_ids.to(self._device)
        attention_mask = inputs.attention_mask.to(self._device)
        max_new_tokens = max(32, DEFAULTS["max_seq_length"] - input_ids.shape[1])

        with torch.inference_mode():
            output = self._model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=DEFAULTS["temperature"],
                top_p=DEFAULTS["top_p"],
                repetition_penalty=DEFAULTS["repetition_penalty"],
                eos_token_id=END_OF_SPEECH_ID,
            )

        clean_audio_ids = self._extract_audio_ids(output[0])
        if not clean_audio_ids:
            raise RuntimeError("No audio token IDs generated")

        codes = self._snac_tokens_to_codebooks(clean_audio_ids)
        if codes is None:
            raise RuntimeError("Insufficient audio token IDs for SNAC decode")

        with torch.inference_mode():
            audio = self._snac.decode(codes)

        audio_np = audio.detach().squeeze().cpu().numpy().astype(np.float32)
        audio_np = self._apply_speed(audio_np, recommended_speed(language, str(user_id)))
        audio_np = self._apply_denoise(audio_np)

        wav_buf = io.BytesIO()
        sf.write(wav_buf, audio_np, SAMPLE_RATE, format="WAV")
        wav_bytes = wav_buf.getvalue()
        duration_ms = int((time.perf_counter() - start) * 1000)
        return wav_bytes, duration_ms
