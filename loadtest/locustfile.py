import json
import os
import random

from locust import HttpUser, between, task


LANGUAGE_SPEAKER = {
    "hindi": ["159", "49", "43"],
    "tamil": ["188", "128", "176"],
    "bengali": ["125"],
    "malayalam": ["189", "124"],
    "kannada": ["142", "138", "131", "59"],
    "telugu": ["69", "133"],
    "punjabi": ["191", "67", "201"],
    "gujarati": ["62", "190"],
    "marathi": ["205", "82", "199", "203"],
}

SAMPLE_TEXT = {
    "hindi": "नमस्ते, आज आप कैसे हैं?",
    "tamil": "வணக்கம், இன்று எப்படி இருக்கீங்க?",
    "bengali": "হ্যালো, আজ তুমি কেমন আছো?",
    "malayalam": "നമസ്കാരം, ഇന്ന് എങ്ങനെയുണ്ട്?",
    "kannada": "ನಮಸ್ಕಾರ, ಇಂದು ಹೇಗಿದ್ದೀರಿ?",
    "telugu": "నమస్కారం, ఈరోజు ఎలా ఉన్నారు?",
    "punjabi": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਅੱਜ ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?",
    "gujarati": "નમસ્તે, આજે તમે કેમ છો?",
    "marathi": "नमस्कार, आज तुम्ही कसे आहात?",
}


class TTSUser(HttpUser):
    wait_time = between(0.2, 1.0)
    host = os.getenv("LOCUST_HOST", "http://localhost:8000")

    @task
    def generate_tts(self):
        language = random.choice(list(LANGUAGE_SPEAKER.keys()))
        payload = {
            "utterance": SAMPLE_TEXT[language],
            "language": language,
            "user_id": random.choice(LANGUAGE_SPEAKER[language]),
        }
        with self.client.post(
            "/v1/tts?response_mode=wav",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            catch_response=True,
            timeout=180,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code} body={response.text[:200]}")
            elif not response.content:
                response.failure("empty audio response")
            else:
                response.success()
