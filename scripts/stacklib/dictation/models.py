"""faster-whisper model names and their Hugging Face repositories, without importing faster-whisper (the project
environment does not have it). Mirrors faster_whisper.utils._MODELS for the names offered in the tray."""
from __future__ import annotations

REPOS = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "small.en": "Systran/faster-whisper-small.en",
    "medium": "Systran/faster-whisper-medium",
    "medium.en": "Systran/faster-whisper-medium.en",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "distil-large-v3.5": "distil-whisper/distil-large-v3.5-ct2",
}

# Offered in the tray's Settings tab: (name, what it is good for). Sizes are the CTranslate2 downloads.
CHOICES = ["large-v3-turbo", "large-v3", "medium", "small", "base"]

# Offered in the button's menu and the tray's Settings tab: detection first, then common languages in alphabetical
# order of their English names. Any other Whisper language code works in dictation.language.
LANGUAGES = [("auto", "Detect automatically"), ("ar", "Arabic"), ("zh", "Chinese"), ("en", "English"),
             ("fr", "French"), ("de", "German"), ("hi", "Hindi"), ("it", "Italian"), ("ja", "Japanese"),
             ("ko", "Korean"), ("pt", "Portuguese"), ("ru", "Russian"), ("es", "Spanish")]


def repo_for(model: str) -> str:
    """Hugging Face repository of a model name; a name with a slash is already a repository."""
    return model if "/" in model else REPOS.get(model, f"Systran/faster-whisper-{model}")
