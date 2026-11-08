"""Small text rules that need no model: joining phrases, dropping filler sounds, spotting Whisper's stock hallucinations."""
from __future__ import annotations

import re
import unicodedata

# Sounds, not words: safe to drop without a language model. "like", "you know" and "I mean" are real words in other
# sentences, so only the cleanup model removes them.
_FILLER = r"(?:u+m+|u+h+m*|u+h+|e+r+m+|e+r+|a+h+|h+m+|m+h+m+|m{2,})"
_FILLER_RE = re.compile(rf"(?<![\w'’-]){_FILLER}(?![\w'’-])", re.IGNORECASE)
# A filler with the comma before it and the punctuation after it, so "that, uh, we" becomes "that we".
_FILLER_SPAN = re.compile(rf"(?:[,;]\s*)?(?<![\w'’-]){_FILLER}(?![\w'’-])(?P<post>\s*[,;.!?…]+)?\s*", re.IGNORECASE)
_CAP = "\x01"  # marks a word that now opens a sentence

# Phrases Whisper writes for noise or silence (it learned them from video subtitles). Dropped only when they are the
# whole transcript.
_STOCK = {
    "thanks for watching", "thank you for watching", "thank you so much for watching", "please subscribe",
    "like and subscribe", "subtitles by the amaraorg community", "subtitles by the amara org community",
    "transcribed by otterai", "you", "bye bye", "ご視聴ありがとうございました",
}


def strip_fillers(text: str) -> str:
    """Drop um/uh/er/hmm-style sounds and the commas around them, and capitalise a word that now opens a sentence.
    'Um, so, I was thinking that, uh, we should' -> 'So, I was thinking that we should'."""
    if not text or not _FILLER_RE.search(text):
        return text

    def repl(m: re.Match) -> str:
        before = text[: m.start()].rstrip()
        opens = not before or before[-1] in ".!?\n"
        post = (m.group("post") or "").strip()
        ends = post[:1] in (".", "!", "?") and not post.startswith("...")
        if ends and not opens:
            return post[0] + " " + _CAP          # "... today, um." keeps its full stop
        return " " + _CAP if opens else " "

    out = _FILLER_SPAN.sub(repl, text)
    out = re.sub(_CAP + r"\s*([^\W\d_])", lambda m: m.group(1).upper(), out).replace(_CAP, "")
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)          # no space before punctuation
    out = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", out)   # ", ," -> ","
    out = re.sub(r"^[\s,;:.]+", "", out)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def _is_cjk(ch: str) -> bool:
    if not ch:
        return False
    name = unicodedata.name(ch, "")
    return name.startswith(("CJK UNIFIED", "HIRAGANA", "KATAKANA", "CJK SYMBOL", "FULLWIDTH", "HANGUL"))


def joiner(before: str, phrase: str) -> str:
    """What to put between text already typed in this session and the next phrase: a space, or nothing before
    punctuation, after a line break, or between Chinese/Japanese characters."""
    if not before or not phrase:
        return ""
    last, first = before[-1], phrase[0]
    if last.isspace() or first.isspace() or first in ",.;:!?)]}…%":
        return ""
    if last in "([{" or (_is_cjk(last) and _is_cjk(first)):
        return ""
    return " "


def normalise(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.lower()).strip().replace(" ", "") if text else ""


def is_stock_hallucination(text: str) -> bool:
    """True when the whole transcript is one of Whisper's subtitle phrases (it writes them for noise)."""
    norm = normalise(text)
    return bool(norm) and norm in {normalise(s) for s in _STOCK}


def tidy(text: str) -> str:
    """Whitespace only: Whisper segments start with a space and may end with one."""
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", text or "")).strip()
