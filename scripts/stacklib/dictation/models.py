"""Speech-to-text models voice typing can run (config/installer.yaml speech_to_text): their engine, Hugging Face
repository, size, speed and the languages they transcribe, without importing any engine (the project environment has
none of them). REPOS mirrors faster_whisper.utils._MODELS for the Whisper names; WHISPER_LANGUAGES matches
faster_whisper.tokenizer._LANGUAGE_CODES (faster-whisper 1.2.1: 100 codes, the multilingual models' full set;
English-only models accept only English). Parakeet TDT v3 transcribes 25 European languages and Canary-Qwen English
only (SPEECH[name].languages)."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from .. import catalog

REPOS = catalog.whisper_repos()   # config/installer.yaml speech_to_text.models (faster-whisper) and whisper.other_repos

ENGINES = ("faster-whisper", "onnx-asr", "transcribe.cpp")


@dataclass(frozen=True)
class SpeechModel:
    """One speech-to-text model of the catalog (config/installer.yaml speech_to_text.models)."""
    name: str
    label: str
    engine: str                          # faster-whisper | onnx-asr | transcribe.cpp
    repo: str
    revision: str = ""                   # pinned revision; '' = faster-whisper's own download
    files: dict = field(default_factory=dict)   # file -> sha256 ('' = not checked); {} = the engine fetches its own
    download_gb: float = 0.0
    device: str = "gpu"                  # where dictation.device auto runs it: gpu | cpu
    vram_gb: float = 0.0                 # GPU memory while it is loaded on the GPU
    ram_gb: float = 0.0                  # system memory while it is loaded
    speed_gpu: float = 0.0               # seconds per 15 s of speech on the GPU (0 = not known)
    speed_cpu: float = 0.0               # ... and on the CPU
    languages: tuple[str, ...] = ()      # () = Whisper's 100
    licence: str = ""
    data: str = ""
    measured: bool = False               # the figures were measured on the reference PC
    onnx_asr: str = ""                   # onnx-asr's model type
    quantization: str = ""
    model_file: str = ""                 # transcribe.cpp: the GGUF file among `files`
    n_ctx: int = 0

    @property
    def family(self) -> str:
        """'Whisper', 'Parakeet' or 'Canary-Qwen', for messages such as "Loading Whisper"."""
        if self.engine == "faster-whisper":
            return "Whisper"
        return self.label.replace("NVIDIA ", "").split(" ")[0]

    def speed(self, on_gpu: bool) -> float:
        return self.speed_gpu if on_gpu else self.speed_cpu

    def speaks(self, code: str) -> bool:
        """Whether it transcribes this language (a Whisper code; '' and 'auto' always)."""
        return code in ("", "auto") or not self.languages or code in self.languages


def _speech_model(name: str, m: dict) -> SpeechModel:
    speed = m.get("speed") or {}
    if not speed and m.get("s_per_15s"):   # the older catalog layout: GPU seconds only
        speed = {"gpu": m["s_per_15s"]}
    return SpeechModel(
        name=name, label=str(m.get("label") or name), engine=str(m.get("engine") or "faster-whisper"),
        repo=str(m.get("repo") or ""), revision=str(m.get("revision") or ""),
        files={str(k): str(v or "") for k, v in (m.get("files") or {}).items()},
        download_gb=float(m.get("download_gb") or 0), device=str(m.get("device") or "gpu"),
        vram_gb=float(m.get("vram_gb") or 0), ram_gb=float(m.get("ram_gb") or 0),
        speed_gpu=float(speed.get("gpu") or 0), speed_cpu=float(speed.get("cpu") or 0),
        languages=tuple(str(x) for x in m.get("languages") or ()), licence=str(m.get("licence") or ""),
        data=str(m.get("data") or ""), measured=bool(m.get("measured")), onnx_asr=str(m.get("onnx_asr") or ""),
        quantization=str(m.get("quantization") or ""), model_file=str(m.get("model_file") or ""),
        n_ctx=int(m.get("n_ctx") or 0))


SPEECH: dict[str, SpeechModel] = {name: _speech_model(name, m) for name, m in catalog.speech_models().items()}
# Every engine's packages and the module that must import (config/installer.yaml speech_to_text.engines).
ENGINE_PACKAGES: dict[str, dict] = catalog.speech_engines()

# Offered in the tray's Settings tab and the installer, in the catalog's order.
CHOICES = list(SPEECH)


def speech_model(name: str) -> SpeechModel:
    """The catalog's entry, or a faster-whisper model of that name (a size typed into the machine file, or a folder)."""
    if name in SPEECH:
        return SPEECH[name]
    base = SPEECH.get("small")
    return SpeechModel(name=name, label=f"Whisper {name}", engine="faster-whisper", repo=repo_for(name),
                       vram_gb=base.vram_gb if base else 0.5, ram_gb=base.ram_gb if base else 0.3)


def engine_of(name: str) -> str:
    return speech_model(name).engine


def label(name: str) -> str:
    return speech_model(name).label

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
    """English-only models: the `.en` Whisper sizes, the distil-whisper models and Canary-Qwen."""
    if model in SPEECH and SPEECH[model].languages:
        return SPEECH[model].languages == ("en",)
    name = (model or "").rsplit("/", 1)[-1].lower()
    return name.endswith(".en") or name.startswith("distil")


def languages_for(model: str = "") -> list[tuple[str, str]]:
    """(code, name) pairs the model accepts, detection first."""
    if english_only(model):
        return [AUTO, ("en", "English")]
    m = SPEECH.get(model)
    if m and m.languages:
        return [AUTO, *[(c, n) for c, n in LANGUAGES if c in set(m.languages)]]
    return list(LANGUAGES)


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
    if model in SPEECH and SPEECH[model].repo:
        return SPEECH[model].repo
    return model if "/" in model else REPOS.get(model, f"Systran/faster-whisper-{model}")
