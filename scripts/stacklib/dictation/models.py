"""faster-whisper model names, their Hugging Face repositories and the languages they transcribe, without importing
faster-whisper (the project environment does not have it). REPOS mirrors faster_whisper.utils._MODELS for the names
offered in the tray; WHISPER_LANGUAGES matches faster_whisper.tokenizer._LANGUAGE_CODES (faster-whisper 1.2.1: 100
codes, the multilingual models' full set; English-only models accept only English)."""
from __future__ import annotations

import unicodedata

from .. import catalog

REPOS = catalog.whisper_repos()   # config/installer.yaml whisper.models and whisper.other_repos

# Offered in the tray's Settings tab and the installer, in the catalog's order.
CHOICES = list(catalog.whisper_models())

# Whisper's language codes with English names. Whisper's own codes are kept as they are ("jw" for Javanese, "yue" for
# Cantonese), because they are what the model accepts.
WHISPER_LANGUAGES = {
    "af": "Afrikaans", "am": "Amharic", "ar": "Arabic", "as": "Assamese", "az": "Azerbaijani", "ba": "Bashkir",
    "be": "Belarusian", "bg": "Bulgarian", "bn": "Bengali", "bo": "Tibetan", "br": "Breton", "bs": "Bosnian",
    "ca": "Catalan", "cs": "Czech", "cy": "Welsh", "da": "Danish", "de": "German", "el": "Greek", "en": "English",
    "es": "Spanish", "et": "Estonian", "eu": "Basque", "fa": "Persian", "fi": "Finnish", "fo": "Faroese",
    "fr": "French", "gl": "Galician", "gu": "Gujarati", "ha": "Hausa", "haw": "Hawaiian", "he": "Hebrew",
    "hi": "Hindi", "hr": "Croatian", "ht": "Haitian Creole", "hu": "Hungarian", "hy": "Armenian", "id": "Indonesian",
    "is": "Icelandic", "it": "Italian", "ja": "Japanese", "jw": "Javanese", "ka": "Georgian", "kk": "Kazakh",
    "km": "Khmer", "kn": "Kannada", "ko": "Korean", "la": "Latin", "lb": "Luxembourgish", "ln": "Lingala",
    "lo": "Lao", "lt": "Lithuanian", "lv": "Latvian", "mg": "Malagasy", "mi": "Maori", "mk": "Macedonian",
    "ml": "Malayalam", "mn": "Mongolian", "mr": "Marathi", "ms": "Malay", "mt": "Maltese", "my": "Burmese",
    "ne": "Nepali", "nl": "Dutch", "nn": "Norwegian Nynorsk", "no": "Norwegian", "oc": "Occitan", "pa": "Punjabi",
    "pl": "Polish", "ps": "Pashto", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian", "sa": "Sanskrit",
    "sd": "Sindhi", "si": "Sinhala", "sk": "Slovak", "sl": "Slovenian", "sn": "Shona", "so": "Somali",
    "sq": "Albanian", "sr": "Serbian", "su": "Sundanese", "sv": "Swedish", "sw": "Swahili", "ta": "Tamil",
    "te": "Telugu", "tg": "Tajik", "th": "Thai", "tk": "Turkmen", "tl": "Tagalog", "tr": "Turkish", "tt": "Tatar",
    "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek", "vi": "Vietnamese", "yi": "Yiddish", "yo": "Yoruba",
    "zh": "Chinese", "yue": "Cantonese",
}
# Other names people search for (Whisper's own name where it differs, common alternatives, the ISO code for Javanese).
ALIASES = {
    "auto": ("automatic", "detect", "any"),
    "bn": ("Bangla",), "es": ("Castilian",), "fa": ("Farsi",), "jw": ("jv",), "my": ("Myanmar",),
    "nl": ("Flemish",), "nn": ("Nynorsk",), "no": ("Bokmål",), "pa": ("Panjabi",), "si": ("Sinhalese",),
    "sl": ("Slovene",), "tl": ("Filipino",), "zh": ("Mandarin",),
}
AUTO = ("auto", "Detect automatically")
# The picker's order: detection first, then every language by English name.
LANGUAGES = [AUTO, *sorted(WHISPER_LANGUAGES.items(), key=lambda item: item[1])]


def english_only(model: str) -> bool:
    """English-only Whisper models: the `.en` sizes and the distil-whisper models."""
    name = (model or "").rsplit("/", 1)[-1].lower()
    return name.endswith(".en") or name.startswith("distil")


def languages_for(model: str = "") -> list[tuple[str, str]]:
    """(code, name) pairs the model accepts, detection first."""
    return [AUTO, ("en", "English")] if english_only(model) else list(LANGUAGES)


def language_name(code: str) -> str:
    """'en' -> 'English'; an unknown code is shown as it is."""
    return AUTO[1] if code in ("", "auto") else WHISPER_LANGUAGES.get(code, code)


def valid_language(code: str) -> bool:
    return code in ("", "auto") or code in WHISPER_LANGUAGES


def _fold(text: str) -> str:
    """Case- and accent-insensitive form for matching ('Bokmål' matches 'bokmal')."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def search(query: str, items: list[tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    """Substring search over names, other names and codes. Order: the exact code, names (or other names) that start
    with the query, codes that start with it, names that contain it, codes that contain it; ties keep the list order."""
    items = LANGUAGES if items is None else items
    q = _fold(query.strip())
    if not q:
        return list(items)
    ranked = []
    for i, (code, name) in enumerate(items):
        names = [_fold(name), *(_fold(a) for a in ALIASES.get(code, ()))]
        c = _fold(code)
        if c == q:
            rank = 0
        elif any(n.startswith(q) for n in names):
            rank = 1
        elif c.startswith(q):
            rank = 2
        elif any(q in n for n in names):
            rank = 3
        elif q in c:
            rank = 4
        else:
            continue
        ranked.append((rank, i, code, name))
    ranked.sort()
    return [(code, name) for _, _, code, name in ranked]


def repo_for(model: str) -> str:
    """Hugging Face repository of a model name; a name with a slash is already a repository."""
    return model if "/" in model else REPOS.get(model, f"Systran/faster-whisper-{model}")
