SUPPORTED_SPEAKERS = {
    "hindi": {
        "159": {"speed": 1.05},
        "49": {"speed": 1.10},
        "43": {"speed": 1.10},
    },
    "tamil": {
        "188": {"speed": 1.10},
        "128": {"speed": 1.15},
        "176": {"speed": 1.10},
    },
    "bengali": {
        "125": {"speed": 1.10},
    },
    "malayalam": {
        "189": {"speed": 1.10},
        "124": {"speed": 1.10},
    },
    "kannada": {
        "142": {"speed": 1.05},
        "138": {"speed": 1.10},
        "131": {"speed": 1.10},
        "59": {"speed": 1.10},
    },
    "telugu": {
        "69": {"speed": 1.10},
        "133": {"speed": 1.10},
    },
    "punjabi": {
        "191": {"speed": 1.08},
        "67": {"speed": 1.06},
        "201": {"speed": 1.10},
    },
    "gujarati": {
        "62": {"speed": 1.15},
        "190": {"speed": 1.25},
    },
    "marathi": {
        "205": {"speed": 1.05},
        "82": {"speed": 1.05},
        "199": {"speed": 1.10},
        "203": {"speed": 1.15},
    },
}


def validate_language_user(language: str, user_id: str) -> bool:
    if language not in SUPPORTED_SPEAKERS:
        return False
    return str(user_id) in SUPPORTED_SPEAKERS[language]


def recommended_speed(language: str, user_id: str, default: float = 1.05) -> float:
    if not validate_language_user(language, str(user_id)):
        return default
    return float(SUPPORTED_SPEAKERS[language][str(user_id)]["speed"])
