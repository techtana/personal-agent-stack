# Adapted from kunato/wayu-kokoro-thai-v1 (Hugging Face), revision abf63dc118365bea784fa881bdd1dce4b2cc1fd4:
# kokoro_thai/g2p.py, kokoro_thai/word_level.py, kokoro_thai/vocab.py and kokoro_thai/data/name_respell.tsv, licensed
# under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0), as the repository states.
# Changes: the three modules are one; English runs go to a callable the caller gives (read aloud's espeak-ng) instead of
# misaki-en with spaCy; tltk.nlp loads without pandas, nltk and scikit-learn (load_tltk); the optional Rust port of
# th2ipa, the per-word drop reports and the debug helpers are left out; the name table is inline; the vocabulary is the
# model's own (onnx_manifest.json), passed in.
"""Thai text to the phonemes the Thai Kokoro model was trained on.

    text --normalize (Thai numbers, abbreviations, ๆ, ฿, %)--> runs of one script each
      Thai run  --tltk.th2ipa--> Thai IPA with tone digits --> Kokoro's phonemes and tone arrows
      Latin run --english()-----> Kokoro's English phonemes (espeak-ng in read aloud)
    --> one phoneme string in the model's 114 + 1 token vocabulary

Thai has five tones; Kokoro's shared vocabulary has four contour arrows (Mandarin's), so the mid, falling, high and
rising tones reuse them and the low tone gets one new token, ˩ (upstream's vocab.py).

Needs pythainlp and tltk (installed with --no-deps: config/installer.yaml kokoro_th). tltk's module keeps global state,
so one sentence at a time (the engine holds a lock around phonemize).
"""
from __future__ import annotations

import importlib.util
import re
import sys
import types
from typing import Callable

# tltk.th2ipa tone digit -> Kokoro token: 1 mid ->, 2 low (the one new token), 3 falling, 4 high, 5 rising
LOW_TONE_TOKEN = "˩"
TONE_DIGIT_TO_TOKEN = {"1": "→", "2": LOW_TONE_TOKEN, "3": "↘", "4": "↗", "5": "↓"}
NORMALIZE = {"ᴐ": "ɔ"}   # tltk writes ɔ as U+1D10

_TAG = re.compile(r"<[^>]*>")   # tltk's <s/> and <tr/>
# Thai run | Latin run (whole phrases: an English G2P weighs a word by its neighbours) | whitespace | one other char
_SEG = re.compile(r"([฀-๿]+)|([A-Za-z][A-Za-z'\- ]*[A-Za-z]|[A-Za-z])|(\s+)|(.)")

# tltk applies the native ทร -> /s/ rule to loanwords where the cluster is really /tʰr/; spelled out (tltk-format IPA).
THAI_OVERRIDE = {"ทรัมป์": "tʰram1", "ทรู": "tʰruː1", "ทรานส์": "tʰraːn1"}
# Respellings tltk tones right where it mis-reads the written form (substring replacement: hand-curated and tiny).
THAI_RESPELL = {"พยาธิ": "พะยาทิ", "ขอบคุน": "ขอบคุณ"}
# Names whose reading upstream confirmed against a second pronouncer (kokoro_thai/data/name_respell.tsv); replaced as
# whole tokens only, since Thai has no word boundaries and a substring rule would corrupt longer words.
NAME_RESPELL = {
    "คุณาธิป": "คุนนาทิบ", "ชลลดา": "ชนลดา", "ดาวดึงส์": "ดาวดึง", "พฤกษ์ลดา": "พฤกษลดา", "รัตนราช": "รัดตะนะราด",
    "ศรีมหาโพธิ": "สีมะหาโพทิ", "ศุภกานต์": "สุภกาน", "ศุภสารรังสรรค์": "สุภะสารรังสัน", "สุวรรณคูหา": "สุวันคูหา",
    "อาภัสรา": "อาพัดสะรา", "อิศรางกูร": "อิดสะรางกูน",
}
_MAX_NAME_TOKENS = 8
_NAME_RE = re.compile("|".join(re.escape(k) for k in sorted(NAME_RESPELL, key=len, reverse=True)))
_OVERRIDE_RE = re.compile("(" + "|".join(re.escape(k) for k in sorted(THAI_OVERRIDE, key=len, reverse=True)) + ")")

# ---------------------------------------------------------------- tltk without its heavy dependencies

# tltk/nlp.py imports these at the top but uses them only in its taggers, parsers and classifiers, never in g2p or
# th2ipa; tltk/__init__ also imports tltk.corpus (gensim, requests). Stand-ins let nlp.py load on its own.
_STUBS = {
    "pandas": (), "nltk": (), "nltk.tag": (), "nltk.tag.perceptron": ("PerceptronTagger",), "nltk.parse": ("malt",),
    "sklearn": (), "sklearn.ensemble": ("RandomForestClassifier",), "sklearn.feature_extraction": ("DictVectorizer",),
    "sklearn.pipeline": ("Pipeline",), "sklearn_crfsuite": ("CRF",),
}


def _cached_re() -> types.ModuleType:
    """`re` for tltk with a compile cache that keeps every pattern. tltk's syllable parser tries a few thousand distinct
    patterns per sentence through re.match and re.sub; re's own cache keeps 512, so tltk recompiled them on every
    word, which was most of its time (0.3-1.2 s a sentence on the reference PC). Same patterns, same results."""
    import functools

    mod = types.ModuleType("re")
    mod.__dict__.update({k: v for k, v in vars(re).items() if not k.startswith("__")})
    compiled = functools.lru_cache(maxsize=None)(re.compile)

    def compile(pattern, flags=0):  # noqa: A001 - re's own names
        return compiled(pattern, flags)

    def match(pattern, string, flags=0):
        return compiled(pattern, flags).match(string)

    def fullmatch(pattern, string, flags=0):
        return compiled(pattern, flags).fullmatch(string)

    def search(pattern, string, flags=0):
        return compiled(pattern, flags).search(string)

    def sub(pattern, repl, string, count=0, flags=0):
        return compiled(pattern, flags).sub(repl, string, count)

    def subn(pattern, repl, string, count=0, flags=0):
        return compiled(pattern, flags).subn(repl, string, count)

    def split(pattern, string, maxsplit=0, flags=0):
        return compiled(pattern, flags).split(string, maxsplit)

    def findall(pattern, string, flags=0):
        return compiled(pattern, flags).findall(string)

    def finditer(pattern, string, flags=0):
        return compiled(pattern, flags).finditer(string)

    for f in (compile, match, fullmatch, search, sub, subn, split, findall, finditer):
        setattr(mod, f.__name__, f)
    return mod


def load_tltk():
    """tltk.nlp (th2ipa) without pandas, nltk, scikit-learn and sklearn-crfsuite: stand-in modules for those while
    tltk/nlp.py loads (only where the real one is not installed), taken away afterwards, and tltk/__init__ skipped.
    Loading reads tltk's dictionaries (about 1.5 s). The full tltk gave the same th2ipa on 4,004 words and sentences."""
    if "tltk.nlp" in sys.modules:
        return sys.modules["tltk.nlp"]
    spec = importlib.util.find_spec("tltk")   # finds the package folder without running tltk/__init__
    if spec is None or not spec.submodule_search_locations:
        raise ImportError("tltk is not installed")
    folder = list(spec.submodule_search_locations)[0]
    added = []
    for name, attrs in _STUBS.items():
        try:
            present = name in sys.modules or importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            present = False
        if present:
            continue
        stub = types.ModuleType(name)
        stub.__path__ = []
        for attr in attrs:
            setattr(stub, attr, None)
        sys.modules[name] = stub
        added.append(name)
    package_added = "tltk" not in sys.modules
    try:
        if package_added:
            package = types.ModuleType("tltk")
            package.__path__ = [folder]
            sys.modules["tltk"] = package
        nlp_spec = importlib.util.spec_from_file_location("tltk.nlp", f"{folder}/nlp.py")
        nlp = importlib.util.module_from_spec(nlp_spec)
        sys.modules["tltk.nlp"] = nlp
        try:
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)   # tltk's regexes use "\." in plain strings
                nlp_spec.loader.exec_module(nlp)
        except BaseException:
            sys.modules.pop("tltk.nlp", None)
            if package_added:
                sys.modules.pop("tltk", None)
            raise
        nlp.re = _cached_re()   # its functions look `re` up when they run
        sys.modules["tltk"].nlp = nlp
    finally:
        for name in added:
            sys.modules.pop(name, None)
    return nlp


# ---------------------------------------------------------------- Thai words (upstream's word_level.py)

def _truncated(ipa: str) -> bool:
    """tltk returns '' or a partial conversion ending in a syllable separator for spellings it cannot segment,
    without raising."""
    core = ipa.replace("<s/>", "").strip()
    return not core or core.endswith(".")


def _syllables(chunk: str) -> list:
    try:
        from pythainlp.tokenize import syllable_tokenize

        return syllable_tokenize(chunk)
    except Exception:  # noqa: BLE001 - a fallback of a fallback
        return [chunk]


def _words(chunk: str) -> list:
    try:
        from pythainlp.tokenize import word_tokenize

        return word_tokenize(chunk)
    except Exception:  # noqa: BLE001
        return [chunk]


def _apply_name_respell(chunk: str) -> str:
    if not _NAME_RE.search(chunk):
        return chunk
    toks = _words(chunk)
    out, i = [], 0
    while i < len(toks):
        hit = None
        for j in range(min(len(toks), i + _MAX_NAME_TOKENS), i, -1):
            cand = "".join(toks[i:j])
            if cand in NAME_RESPELL:
                hit = (j, NAME_RESPELL[cand])
                break
        if hit:
            out.append(hit[1])
            i = hit[0]
        else:
            out.append(toks[i])
            i += 1
    return "".join(out)


def thai_chunk_to_ipa(tltk_nlp, chunk: str) -> str:
    """th2ipa on a run of Thai with no spaces, with the overrides, and per syllable (then per word) when tltk fails,
    returns nothing or stops short; '' when nothing works."""
    for bad, good in THAI_RESPELL.items():
        if bad in chunk:
            chunk = chunk.replace(bad, good)
    chunk = _apply_name_respell(chunk)
    if any(k in chunk for k in THAI_OVERRIDE):
        parts = []
        for piece in _OVERRIDE_RE.split(chunk):
            if piece:
                parts.append(THAI_OVERRIDE[piece] if piece in THAI_OVERRIDE else thai_chunk_to_ipa(tltk_nlp, piece))
        return " ".join(p for p in parts if p.strip())
    try:
        out = tltk_nlp.th2ipa(chunk)
    except Exception:  # noqa: BLE001 - tltk raises ValueError on some spellings
        out = ""
    if out and not _truncated(out):
        return out
    for tokenize in (_syllables, _words):
        pieces = tokenize(chunk)
        if len(pieces) < 2:
            continue
        got = []
        for w in pieces:
            w = w.strip()
            if not w:
                continue
            try:
                p = tltk_nlp.th2ipa(w)
            except Exception:  # noqa: BLE001
                continue
            if p and not _truncated(p):
                got.append(p)
        if got:
            return " ".join(got)
    return ""


# ---------------------------------------------------------------- the front-end

class ThaiG2P:
    """Callable front-end: Thai (and English inside it) -> the model's phoneme string.

    vocab: the phoneme tokens the model reads (onnx_manifest.json's vocabulary); anything else tltk writes is dropped.
    english: Latin text -> Kokoro's English phonemes (read aloud passes espeak-ng's, tidied the way Kokoro reads them).
    tltk_nlp: tltk.nlp, or something with its th2ipa (tests); loaded with load_tltk when not given."""

    def __init__(self, vocab, english: Callable[[str], str], tltk_nlp=None) -> None:
        from .normalize import normalize_text   # pythainlp

        self.vocab = frozenset(vocab)
        self.english = english
        self.normalize_text = normalize_text
        self.tltk = tltk_nlp if tltk_nlp is not None else load_tltk()

    def thai_tokens(self, s: str) -> str:
        """A Thai run as model tokens: tone digits become tone tokens (only right after a phoneme; a digit at a
        boundary is a leaked number, dropped), tltk's syllable marks go, anything outside the vocabulary goes."""
        raw = _TAG.sub(" ", " ".join(thai_chunk_to_ipa(self.tltk, chunk) for chunk in s.split()))
        out: list[str] = []
        for ch in raw:
            if ch.isdigit():
                if out and out[-1] != " ":
                    tok = TONE_DIGIT_TO_TOKEN.get(ch)
                    if tok:
                        out.append(tok)
            elif ch in ".+":
                continue
            elif ch.isspace():
                if out and out[-1] != " ":
                    out.append(" ")
            else:
                tok = NORMALIZE.get(ch, ch)
                if tok in self.vocab:
                    out.append(tok)
        return "".join(out)

    def english_tokens(self, s: str) -> str:
        ps = self.english(s) or ""
        return re.sub(r" +", " ", "".join(c for c in ps if c == " " or c in self.vocab)).strip()

    def render(self, text: str) -> str:
        """Normalised text, each run phonemized in its own language."""
        out = []
        for thai, latin, ws, other in _SEG.findall(text):
            if thai:
                out.append(self.thai_tokens(thai))
            elif latin:
                out.append(self.english_tokens(latin))
            elif ws:
                out.append(" ")
            elif other and other in self.vocab:   # , . ! ? and the like
                out.append(other)
        return re.sub(r" +", " ", "".join(out)).strip()

    def phonemize(self, text: str) -> str:
        return self.render(self.normalize_text(text))

    __call__ = phonemize
