"""Read selected text aloud: the settings, the voices, and how selected text becomes speech-ready pieces. Standard
library only, so the project's tests cover it without the app's environment. tts.py runs the voices, player.py plays
the audio, reader.py runs the flow behind the speaker button and its hotkey.

Two kinds of voice speak, both on this machine; nothing leaves it:
  - Kokoro-82M (Apache-2.0) through ONNX Runtime on the CPU: natural voices in US and UK English, Spanish, French,
    Hindi, Italian and Brazilian Portuguese. espeak-ng turns the text into phonemes first, as kokoro-onnx does.
  - Windows' own voices (SAPI, and the OneCore voices Windows installs with a language's speech pack): instant and
    flatter, in every language that has one (Settings > Time & language > Speech > Add voices).

Selected text is cleaned for listening (Markdown and Logseq markup, bare URLs, list bullets, table rules) and cut into
pieces of a sentence or a few: the first piece is short, so the voice starts within a second, and the next ones are
prepared while it speaks. With `auto_language`, text clearly written in another language than the chosen voice's is
read by a voice for that language when one is available.
"""
from __future__ import annotations

import math
import os
import re
import unicodedata
from dataclasses import dataclass, field, fields

# Kokoro-82M as ONNX (onnx-community's export of hexgrad/Kokoro-82M v1.0), pinned like the Python packages: a new
# revision is a new download to check. 55 voice files of 0.5 MB each; only the languages below are offered.
KOKORO_REPO = "onnx-community/Kokoro-82M-v1.0-ONNX"
KOKORO_REVISION = "1939ad2a8e416c0acfeecc08a694d14ef25f2231"
KOKORO_FILES = {"fp32": "onnx/model.onnx", "int8": "onnx/model_quantized.onnx"}
KOKORO_SIZES_MB = {"fp32": 326, "int8": 92}   # measured downloads, plus about 0.5 MB per voice
SAMPLE_RATE = 24000                            # Kokoro's output; Windows voices are asked for the same

# Kokoro's language letter (first letter of a voice id) -> (espeak-ng language, language family, name)
KOKORO_LANGUAGES = {
    "a": ("en-us", "en", "US English"), "b": ("en-gb", "en", "UK English"), "e": ("es", "es", "Spanish"),
    "f": ("fr-fr", "fr", "French"), "h": ("hi", "hi", "Hindi"), "i": ("it", "it", "Italian"),
    "p": ("pt-br", "pt", "Brazilian Portuguese"),
}
# Japanese and Chinese voices exist too, but Kokoro reads them through its own G2P (misaki with pyopenjtalk or
# jieba), not espeak-ng, so they are not offered.
KOKORO_VOICE_IDS = (
    "af_heart", "af_bella", "af_nicole", "af_aoede", "af_kore", "af_sarah", "af_nova", "af_sky", "af_alloy",
    "af_jessica", "af_river", "am_michael", "am_fenrir", "am_puck", "am_echo", "am_eric", "am_liam", "am_onyx",
    "am_adam", "am_santa",
    "bf_emma", "bf_isabella", "bf_alice", "bf_lily", "bm_george", "bm_fable", "bm_lewis", "bm_daniel",
    "ef_dora", "em_alex", "em_santa", "ff_siwis", "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola", "pf_dora", "pm_alex", "pm_santa",
)
# The voice auto_language picks for a language when you named none (read_aloud.voices).
DEFAULT_FOR_LANGUAGE = {"en": "af_heart", "es": "ef_dora", "fr": "ff_siwis", "hi": "hf_alpha", "it": "if_sara",
                        "pt": "pf_dora"}
LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "hi": "Hindi", "it": "Italian", "pt": "Portuguese",
    "de": "German", "nl": "Dutch", "ru": "Russian", "uk": "Ukrainian", "bg": "Bulgarian", "th": "Thai",
    "ja": "Japanese", "zh": "Chinese", "ko": "Korean", "ar": "Arabic", "fa": "Persian", "he": "Hebrew",
    "el": "Greek", "pl": "Polish", "sv": "Swedish", "da": "Danish", "nb": "Norwegian", "fi": "Finnish",
    "cs": "Czech", "tr": "Turkish", "vi": "Vietnamese", "id": "Indonesian", "ms": "Malay", "ta": "Tamil",
}
SPEEDS = ("0.75", "0.9", "1.0", "1.1", "1.25", "1.5", "1.75", "2.0")
KOKORO_CHOICES = ("fp32", "int8", "off")
DEVICES = ("auto", "gpu", "cpu")   # where Kokoro runs: auto = the GPU when its CUDA libraries are installed


@dataclass(frozen=True)
class Voice:
    id: str           # af_heart, or windows:<Name> for a Windows voice
    name: str         # what menus show: Heart, Zira
    language: str     # en-us, en-gb, fr-fr, th-th, ...
    engine: str       # kokoro | windows
    gender: str = ""  # female | male | ""
    token: str = ""   # Windows: the SAPI token's registry path

    @property
    def family(self) -> str:
        return family(self.language)

    @property
    def label(self) -> str:
        """'Heart (US English, female)', 'Zira (US English, female, Windows)'."""
        bits = [language_label(self.language)] + ([self.gender] if self.gender else [])
        if self.engine == "windows":
            bits.append("Windows")
        return f"{self.name} ({', '.join(bits)})"


def family(language: str) -> str:
    """'en-us' -> 'en'; 'pt-br' -> 'pt'."""
    return (language or "").lower().split("-", 1)[0]


def language_label(language: str) -> str:
    lang = (language or "").lower()
    for _letter, (code, _fam, name) in KOKORO_LANGUAGES.items():
        if code == lang or (lang == "fr" and code == "fr-fr"):
            return name
    return LANGUAGE_NAMES.get(family(lang), lang or "unknown language")


def kokoro_voice(vid: str) -> Voice | None:
    """The Kokoro voice with this id ('af_heart' -> Heart, US English, female), or None."""
    if vid not in KOKORO_VOICE_IDS:
        return None
    lang = KOKORO_LANGUAGES[vid[0]][0]
    gender = {"f": "female", "m": "male"}.get(vid[1], "")
    name = vid.split("_", 1)[1].replace("_", " ").title()
    return Voice(vid, name, lang, "kokoro", gender)


def kokoro_voices() -> list[Voice]:
    return [v for v in (kokoro_voice(i) for i in KOKORO_VOICE_IDS) if v]


# ---------------------------------------------------------------- settings

@dataclass
class Config:
    """The machine profile's `read_aloud:` section (machines/_defaults.yaml documents each key)."""
    enabled: bool = False         # an optional feature: the installer (or `stack.py read-aloud install`) turns it on
    hotkey: str = "ctrl+alt+s"
    voice: str = "af_heart"
    speed: float = 1.0
    auto_language: bool = True
    button: bool = True
    esc_stops: bool = True
    kokoro: str = "fp32"          # fp32 | int8 | off (Windows voices only)
    device: str = "auto"          # auto | gpu | cpu
    max_chars: int = 20000
    unload_after_min: float = 30.0
    voices: dict = field(default_factory=dict)   # language family -> voice id, for auto_language

    @classmethod
    def from_profile(cls, profile: dict, warn=lambda msg: None) -> "Config":
        raw = dict(profile.get("read_aloud") or {})
        cfg = cls()
        for f in fields(cls):
            value = raw.get(f.name)
            if value is None:
                continue
            try:
                if f.name == "voices":
                    if not isinstance(value, dict):
                        raise TypeError("expected a mapping of language to voice id")
                    value = {str(k).strip().lower(): str(v).strip() for k, v in value.items() if v}
                elif f.type in ("int", int):
                    value = int(value)
                elif f.type in ("float", float):
                    value = float(value)
                elif f.type in ("bool", bool):
                    value = value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
                else:
                    value = str(value).strip()
            except (TypeError, ValueError):
                warn(f"read_aloud.{f.name}: {value!r} is not valid; using {getattr(cfg, f.name)!r}")
                continue
            setattr(cfg, f.name, value)
        if not math.isfinite(cfg.speed):
            cfg.speed = 1.0
        cfg.speed = min(max(cfg.speed, 0.5), 2.0)
        cfg.max_chars = min(max(cfg.max_chars, 200), 200000)
        cfg.unload_after_min = min(max(cfg.unload_after_min, 0.0), 1440.0) if math.isfinite(cfg.unload_after_min) else 30.0
        cfg.kokoro = cfg.kokoro.lower()
        if cfg.kokoro not in KOKORO_CHOICES:
            warn(f"read_aloud.kokoro: {cfg.kokoro!r} is not one of {', '.join(KOKORO_CHOICES)}; using 'fp32'")
            cfg.kokoro = "fp32"
        cfg.device = cfg.device.lower()
        if cfg.device not in DEVICES:
            warn(f"read_aloud.device: {cfg.device!r} is not one of {', '.join(DEVICES)}; using 'auto'")
            cfg.device = "auto"
        if not cfg.voice:
            cfg.voice = cls.voice
        return cfg


def speed_text(speed: float) -> str:
    """'1.25x'; '1x' for normal speed."""
    return f"{speed:g}x"


def sapi_rate(speed: float) -> int:
    """SAPI's rate (-10..10) for a speed factor: +10 is three times as fast, -10 a third as fast."""
    if speed <= 0 or not math.isfinite(speed):
        return 0
    return max(-10, min(10, round(10 * math.log(speed) / math.log(3))))


# ---------------------------------------------------------------- Windows voices (read from the registry)

_REGISTRY = ((r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens", "OneCore"),
             (r"SOFTWARE\Microsoft\Speech\Voices\Tokens", "SAPI"))


def lcid_tag(lcid: str) -> str:
    """'409' (a SAPI Language attribute, hex, maybe '409;9') -> 'en-us'."""
    first = (lcid or "").split(";", 1)[0].strip()
    try:
        number = int(first, 16)
    except ValueError:
        return ""
    if os.name == "nt":
        import ctypes

        buf = ctypes.create_unicode_buffer(85)
        try:
            if ctypes.windll.kernel32.LCIDToLocaleName(number, buf, 85, 0):
                return buf.value.lower()
        except (AttributeError, OSError):
            pass
    return {0x409: "en-us", 0x809: "en-gb", 0x40C: "fr-fr", 0x407: "de-de", 0x40A: "es-es", 0xC0A: "es-es",
            0x410: "it-it", 0x416: "pt-br", 0x816: "pt-pt", 0x41E: "th-th", 0x411: "ja-jp", 0x804: "zh-cn",
            0x412: "ko-kr", 0x419: "ru-ru", 0x439: "hi-in"}.get(number, "")


def windows_voices() -> list[Voice]:
    """The voices Windows has, OneCore ones first (the newer engine), read from the registry; [] elsewhere."""
    if os.name != "nt":
        return []
    import winreg

    out: list[Voice] = []
    seen: set[str] = set()
    for path, _kind in _REGISTRY:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        except OSError:
            continue
        with key:
            for i in range(winreg.QueryInfoKey(key)[0]):
                token = winreg.EnumKey(key, i)
                try:
                    with winreg.OpenKey(key, token + r"\Attributes") as attrs:
                        values = {}
                        for name in ("Name", "Language", "Gender"):
                            try:
                                values[name] = str(winreg.QueryValueEx(attrs, name)[0])
                            except OSError:
                                values[name] = ""
                except OSError:
                    continue
                full = values["Name"] or token
                vid = "windows:" + full
                if vid in seen:
                    continue
                seen.add(vid)
                short = full[len("Microsoft "):] if full.startswith("Microsoft ") else full
                out.append(Voice(vid, short, lcid_tag(values["Language"]) or "", "windows",
                                 values["Gender"].lower() if values["Gender"].lower() in ("female", "male") else "",
                                 rf"HKEY_LOCAL_MACHINE\{path}\{token}"))
    return out


def voice_choices(installed_windows: list[Voice] | None = None) -> list[tuple[str, str]]:
    """(id, label) of every voice the menus and the tray offer: Kokoro's, then this PC's Windows voices."""
    win = windows_voices() if installed_windows is None else installed_windows
    return [(v.id, v.label) for v in [*kokoro_voices(), *win]]


def find_voice(vid: str, voices: list[Voice]) -> Voice | None:
    return next((v for v in voices if v.id == vid), None)


# ---------------------------------------------------------------- text for listening

_URL = re.compile(r"\b(?:https?://|www\.)([^\s/<>()\[\]\"']+)[^\s<>\"']*", re.I)
_MD_LINK = re.compile(r"!?\[([^\]\n]*)\]\((?:[^()\s]|\([^()\s]*\))+\)")
_PAGE = re.compile(r"#?\[\[([^\[\]\n]+)\]\]")
_BLOCK_REF = re.compile(r"\(\([0-9a-fA-F-]{8,}\)\)")
_MACRO = re.compile(r"\{\{[^{}\n]*\}\}")
_TAG = re.compile(r"(?<![\w#&/])#([A-Za-z][\w/-]*)")
_PROPERTY = re.compile(r"^[\w-]+::(?:\s|$)")            # Logseq block properties: id:: ..., collapsed:: true
_RULE = re.compile(r"^(?:[-*_=]\s*){3,}$|^\|?(?:\s*:?-{2,}:?\s*\|)+\s*:?-{0,}:?\s*\|?$")
_FENCE = re.compile(r"^(?:```|~~~)")
_BULLET = re.compile(r"^(?:[-*+•▪◦]\s+|>\s*)+")
_HEADING = re.compile(r"^#{1,6}\s+")
_CHECKBOX = re.compile(r"^\[[ xX]\]\s+")
_EMPHASIS = (
    re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1"),                     # **bold**, __bold__
    re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])"),    # *italic*
    re.compile(r"(?<!\w)_(?=\S)([^_\n]+?)(?<=\S)_(?!\w)"),            # _italic_ (not snake_case)
    re.compile(r"~~(?=\S)(.+?)(?<=\S)~~"),                            # ~~strike~~
    re.compile(r"==(?=\S)(.+?)(?<=\S)=="),                            # ==highlight==
    re.compile(r"\^\^(?=\S)(.+?)(?<=\S)\^\^"),                        # ^^highlight^^ (Logseq)
    re.compile(r"`([^`\n]+)`"),                                       # `code`
)
_HTML_TAG = re.compile(r"</?[a-zA-Z][^<>\n]{0,200}>")
_ENDS_SENTENCE = re.compile(r"[.!?…:;,。！？]['\"”’)\]]*$")


def _host(m: re.Match) -> str:
    host = m.group(1).rstrip(".,;:!?")
    host = host[4:] if host.lower().startswith("www.") else host
    return host


def _line(s: str) -> str:
    s = _HEADING.sub("", s)
    s = _BULLET.sub("", s)
    s = _CHECKBOX.sub("", s)
    s = _MACRO.sub("", s)
    s = _BLOCK_REF.sub("", s)
    s = _MD_LINK.sub(lambda m: m.group(1), s)
    s = _PAGE.sub(lambda m: m.group(1), s)
    s = _URL.sub(_host, s)
    s = _TAG.sub(lambda m: m.group(1).replace("-", " ").replace("_", " "), s)
    s = _HTML_TAG.sub(" ", s)
    for pattern in _EMPHASIS:
        s = pattern.sub(lambda m: m.group(m.lastindex), s)
    if s.count("|") >= 2 and s.strip().startswith("|"):
        s = ", ".join(c.strip() for c in s.strip().strip("|").split("|") if c.strip())
    return " ".join(s.split())


def speech_text(text: str) -> str:
    """Selected text as it should be read: markup off, one item or paragraph per line, every line ending in a
    punctuation mark so the voice pauses between list items and headings, blank lines kept as paragraph breaks."""
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\x0b", "\n").replace("\u2028", "\n")
    t = t.replace("\u2029", "\n\n").replace("\xa0", " ").replace("\u200b", "")
    lines: list[str] = []
    for raw in t.split("\n"):
        s = raw.strip()
        if not s:
            if lines and lines[-1]:
                lines.append("")
            continue
        if _PROPERTY.match(s) or _RULE.fullmatch(s) or _FENCE.match(s):
            continue
        s = _line(s)
        if not s or not any(ch.isalnum() for ch in s):
            continue
        if not _ENDS_SENTENCE.search(s):
            s += "."
        lines.append(s)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def cut(text: str, limit: int) -> str:
    """At most `limit` characters, ending at a sentence or line end when one is near."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    end = max(head.rfind(". "), head.rfind("\n"), head.rfind("! "), head.rfind("? "))
    return head[: end + 1].rstrip() if end > limit * 0.6 else head.rstrip()


# ---------------------------------------------------------------- sentences and pieces

ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e", "no", "fig", "approx",
                 "inc", "ltd", "co", "mt", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
                 "nov", "dec", "cf", "al", "ca", "dept", "est", "vol", "p", "pp", "ed", "eds", "rev", "gen", "gov",
                 "sgt", "capt", "lt", "col", "cmdr", "adm", "hon", "u.s", "u.k", "a.m", "p.m"}
_END = re.compile(r"[.!?…]+[\"”’)\]]*(?=\s)|[。！？]+[」』”）]*")
_CLAUSE = re.compile(r"(?<=[,;:—–])\s+|(?<=\))\s+")
FIRST_CHARS = 120    # the first piece: one short sentence or clause, so the voice starts quickly
PIECE_CHARS = 160    # later pieces: a sentence, or short sentences joined up to about this long, so each is ready
                     # long before the one before it finishes playing (several are prepared at once)
HARD_CHARS = 260     # longer sentences are split at commas, then between words


@dataclass(frozen=True)
class Piece:
    text: str
    paragraph_end: bool = False   # a longer pause follows


def sentences(paragraph: str) -> list[str]:
    """A paragraph cut after . ! ? … (and 。！？), but not after an abbreviation such as "Dr." or an initial."""
    out: list[str] = []
    start = 0
    for m in _END.finditer(paragraph):
        if m.group(0).startswith("."):
            word = re.search(r"([\w.]+)$", paragraph[start:m.start()])
            w = word.group(1).lower() if word else ""
            if w in ABBREVIATIONS or (len(w) == 1 and w.isalpha()):
                continue
        piece = paragraph[start:m.end()].strip()
        if piece:
            out.append(piece)
        start = m.end()
    rest = paragraph[start:].strip()
    if rest:
        out.append(rest)
    return out


def _split_long(sentence: str, limit: int) -> list[str]:
    if len(sentence) <= limit:
        return [sentence]
    parts: list[str] = []
    current = ""
    for clause in _CLAUSE.split(sentence):
        if current and len(current) + 1 + len(clause) > limit:
            parts.append(current)
            current = clause
        else:
            current = f"{current} {clause}".strip()
    if current:
        parts.append(current)
    out: list[str] = []
    for part in parts:
        while len(part) > limit:                       # one clause longer than the limit: cut between words
            at = part.rfind(" ", 0, limit)
            at = at if at > limit // 3 else limit
            out.append(part[:at].strip())
            part = part[at:].strip()
        if part:
            out.append(part)
    return out


def pieces(text: str) -> list[Piece]:
    """Speech text (speech_text) in the pieces the voice reads one at a time: the first is one short sentence (or its
    first clause), later ones a sentence each, short ones joined up to PIECE_CHARS; no piece crosses a paragraph or
    list item. Sentence-sized pieces keep every wait short: the reader prepares several ahead, in parallel."""
    out: list[Piece] = []
    for paragraph in (text or "").split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        units: list[str] = []
        for s in sentences(paragraph):
            units.extend(_split_long(s, FIRST_CHARS if not out and not units else HARD_CHARS))
        current = ""
        for u in units:
            limit = FIRST_CHARS if not out else PIECE_CHARS
            if current and len(current) + 1 + len(u) > limit:
                out.append(Piece(current))
                current = u
            elif not out and current:          # the very first piece is a single sentence
                out.append(Piece(current))
                current = u
            else:
                current = f"{current} {u}".strip()
        if current:
            out.append(Piece(current))
        if out:
            out[-1] = Piece(out[-1].text, True)
    return out


# ---------------------------------------------------------------- language

STOPWORDS = {
    "en": set("the and of to is in that it for you was with on are this be have not but at by from or as were "
              "they which will would there their what about can".split()),
    "fr": set("le la les de et est des une un du que qui dans pour pas sur avec ce il elle sont au aux nous vous "
              "je ne ils mais ou leur cette être été fait suis très avons avez".split()),
    "es": set("el la los las y es de que en un una por para con no se del al lo como más pero sus fue este esta "
              "está muy también".split()),
    "it": set("il la le e è di che un una per non con del della sono gli si nel alla anche come questo questa "
              "ma più dei delle".split()),
    "pt": set("o a os as e é de que em um uma para com não do da dos das se mais por na no foi como mas ao "
              "também está".split()),
    "de": set("der die das und ist nicht ein eine zu den mit von sich auf für im dem des auch es sie wir ich "
              "aber oder wird sind".split()),
    "nl": set("de het een en is van dat niet op te zijn met voor er maar ook als bij aan om dit deze wordt".split()),
}
# Letters that mark a language: (characters, language, weight per letter).
MARKS = (("ñ¿¡", "es", 2.0), ("çœ", "fr", 2.0), ("êâîûëïÿ", "fr", 1.0), ("ãõ", "pt", 2.0), ("ß", "de", 3.0),
         ("äöü", "de", 1.0), ("ìòù", "it", 1.0))
# Writing system -> languages that use it, most likely first.
SCRIPT_LANGUAGES = {"DEVANAGARI": ["hi"], "THAI": ["th"], "CYRILLIC": ["ru", "uk", "bg"], "ARABIC": ["ar", "fa"],
                    "HEBREW": ["he"], "GREEK": ["el"], "HANGUL": ["ko"], "KANA": ["ja"], "HAN": ["zh", "ja"],
                    "TAMIL": ["ta"]}


def _script(ch: str) -> str:
    first = unicodedata.name(ch, "").split(" ", 1)[0]
    if first in ("HIRAGANA", "KATAKANA"):
        return "KANA"
    if first == "CJK":
        return "HAN"
    return first


def detect_languages(text: str) -> list[str]:
    """Language families the text is written in, most likely first; [] when it cannot tell (short or mixed text).
    The writing system decides first; Latin text is weighed by common short words and marked letters."""
    counts: dict[str, int] = {}
    for ch in text or "":
        if ch.isalpha():
            s = _script(ch)
            counts[s] = counts.get(s, 0) + 1
    letters = sum(counts.values())
    if not letters:
        return []
    script, n = max(counts.items(), key=lambda kv: kv[1])
    if script == "HAN" and counts.get("KANA", 0) >= 0.1 * letters:
        script = "KANA"   # Japanese mixes kanji with kana
    if n < 0.6 * letters:
        return []
    if script != "LATIN":
        return list(SCRIPT_LANGUAGES.get(script, []))
    words = re.findall(r"[^\W\d_]+", text.lower())
    if len(words) < 4:
        return []
    score = {lang: 0.0 for lang in STOPWORDS}
    for w in words:
        for lang, stop in STOPWORDS.items():
            if w in stop:
                score[lang] += 1.0
    lower = text.lower()
    for chars, lang, weight in MARKS:
        score[lang] += weight * sum(lower.count(c) for c in chars)
    ranked = sorted(score.items(), key=lambda kv: -kv[1])
    (best, top), (_second, runner) = ranked[0], ranked[1]
    if top < 3 or top < 1.5 * runner or top < 0.12 * len(words):
        return []
    return [best]


def pick_voice(cfg: Config, text: str, voices: list[Voice]) -> tuple[Voice | None, str]:
    """(voice, note) for reading `text`: the chosen voice, or with auto_language a voice for the language the text is
    in. The note says why another voice reads it, or why the text's own language has none."""
    chosen = find_voice(cfg.voice, voices)
    note = ""
    if chosen is None:
        if not voices:
            return None, ""
        wanted = kokoro_voice(cfg.voice)
        same = [v for v in voices if wanted and v.family == wanted.family]
        chosen = (same or voices)[0]
        note = f"{wanted.name if wanted else cfg.voice} is not available, so {chosen.name} reads it."
    if not cfg.auto_language:
        return chosen, note
    langs = detect_languages(text)
    if not langs or chosen.family in langs:
        return chosen, note
    for lang in langs:
        named = find_voice(cfg.voices.get(lang, ""), voices) or find_voice(DEFAULT_FOR_LANGUAGE.get(lang, ""), voices)
        same = [v for v in voices if v.family == lang]
        if named is None and same:
            kokoro = [v for v in same if v.engine == "kokoro"]
            named = (kokoro or same)[0]
        if named is not None:
            return named, f"The text is in {LANGUAGE_NAMES.get(lang, lang)}, so {named.name} reads it."
    lang = LANGUAGE_NAMES.get(langs[0], langs[0])
    return chosen, (f"No {lang} voice is installed, so {chosen.name} reads it. Windows adds one in Settings > Time & "
                    "language > Speech.")


# ---------------------------------------------------------------- phonemes (Kokoro's input)

PUNCTUATION = ';:,.!?¡¿—…"«»“”()'
_PUNCT_RUN = re.compile(r"(?:\s*[" + re.escape(PUNCTUATION) + r"]+\s*)+")
_MONEY = re.compile(r"([$£€])(\d[\d,]*)(?:\.(\d{1,2}))?\b")
_UNITS = {"$": ("dollar", "dollars", "cent", "cents"), "£": ("pound", "pounds", "penny", "pence"),
          "€": ("euro", "euros", "cent", "cents")}


def _money(m: re.Match) -> str:
    one, many, sub_one, sub_many = _UNITS[m.group(1)]
    whole = m.group(2).replace(",", "")
    out = f"{whole} {one if whole == '1' else many}"
    cents = (m.group(3) or "").ljust(2, "0") if m.group(3) else ""
    if cents and int(cents):
        out += f" and {int(cents)} {sub_one if int(cents) == 1 else sub_many}"
    return out


def for_phonemes(text: str, language: str) -> str:
    """Text as espeak-ng should see it: plain quotes, brackets as Kokoro's « », and (in English) money and a few
    abbreviations spelt out, which espeak-ng reads awkwardly ('$5.50' as 'dollar five point five zero')."""
    t = text.replace("‘", "'").replace("’", "'").replace("«", "“").replace("»", "”")
    t = t.replace("(", "«").replace(")", "»").replace("[", "«").replace("]", "»")
    for a, b in (("、", ", "), ("。", ". "), ("！", "! "), ("，", ", "), ("：", ": "), ("；", "; "), ("？", "? "),
                 ("–", "—")):
        t = t.replace(a, b)
    if family(language) == "en":
        t = _MONEY.sub(_money, t)
        t = re.sub(r"\bD[Rr]\.(?= [A-Z])", "Doctor", t)
        t = re.sub(r"\b(?:Mr\.|MR\.(?= [A-Z]))", "Mister", t)
        t = re.sub(r"\b(?:Ms\.|MS\.(?= [A-Z]))", "Miss", t)
        t = re.sub(r"\b(?:Mrs\.|MRS\.(?= [A-Z]))", "Mrs", t)
        t = re.sub(r"\betc\.(?! [A-Z])", "etc", t, flags=re.I)
        t = re.sub(r"(?<=\d)-(?=\d)", " to ", t)
    return " ".join(t.split())


def split_punctuation(text: str) -> list[tuple[bool, str]]:
    """[(is_punctuation, text)]: espeak-ng drops punctuation, but Kokoro reads pauses and questions from it, so the
    words go to espeak-ng and the punctuation is put back between them."""
    out: list[tuple[bool, str]] = []
    last = 0
    for m in _PUNCT_RUN.finditer(text):
        if m.start() > last:
            out.append((False, text[last:m.start()]))
        out.append((True, m.group(0)))
        last = m.end()
    if last < len(text):
        out.append((False, text[last:]))
    return out


def tidy_phonemes(ps: str, language: str) -> str:
    """espeak-ng's IPA in the form Kokoro was trained on (the post-processing kokoro and kokoro.js apply)."""
    ps = re.sub(r"\([a-z-]{2,10}\)", "", ps)   # language-switch marks such as (fr) for a foreign word
    ps = ps.replace("kəkˈoːɹoʊ", "kˈoʊkəɹoʊ").replace("kəkˈɔːɹəʊ", "kˈəʊkəɹəʊ")
    ps = ps.replace("ʲ", "j").replace("r", "ɹ").replace("x", "k").replace("ɬ", "l")
    ps = re.sub(r"(?<=[a-zɹː])(?=hˈʌndɹɪd)", " ", ps)
    ps = re.sub(r' z(?=[;:,.!?¡¿—…"«»“” ]|$)', "z", ps)
    if language == "en-us":
        ps = re.sub(r"(?<=nˈaɪn)ti(?!ː)", "di", ps)
    return " ".join(ps.split(" ")).strip()


def token_ids(ps: str, vocab: dict[str, int]) -> list[int]:
    """Phoneme characters as Kokoro token ids; characters outside the vocabulary are dropped, as its tokenizer does."""
    return [vocab[c] for c in ps if c in vocab]


def split_ids(ps: str, vocab: dict[str, int], limit: int = 500) -> list[list[int]]:
    """Token ids in runs of at most `limit` (Kokoro reads 510 at once), cut at spaces where possible."""
    runs: list[list[int]] = []
    rest = ps
    while rest:
        ids = token_ids(rest, vocab)
        if len(ids) <= limit:
            if ids:
                runs.append(ids)
            break
        # find the character position where the limit is reached, then step back to a space
        count, at = 0, len(rest)
        for i, c in enumerate(rest):
            if c in vocab:
                count += 1
                if count >= limit:
                    at = i
                    break
        space = rest.rfind(" ", 0, at)
        at = space if space > at // 3 else at
        head = token_ids(rest[:at], vocab)
        if head:
            runs.append(head)
        rest = rest[at:].lstrip()
    return runs


def seconds_text(seconds: float) -> str:
    """'45 s', '2 min 05 s'."""
    s = max(0, int(round(seconds)))
    return f"{s} s" if s < 60 else f"{s // 60} min {s % 60:02d} s"
