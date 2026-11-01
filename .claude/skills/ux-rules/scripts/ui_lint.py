"""Static first pass for UX rule violations in UI source code.

Finds *candidates* by pattern: every hit needs a human or model look before it counts as a finding,
and a clean run proves little, because most UX problems are invisible to a pattern scan.

Usage:
    python ui_lint.py <file-or-folder> [...]            # text report grouped by rule
    python ui_lint.py src --json > lint.json            # machine-readable
    python ui_lint.py src --rules A11Y,FRM              # only rules whose ID starts with these prefixes

Scans web markup and styles (html, jsx, tsx, vue, svelte, css, scss, ...), plain JS/TS for a few calls,
and Python Tk/Qt code (font sizes, color pairs, stock Yes/No dialogs). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrast import parse_color, ratio  # noqa: E402

MARKUP = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro", ".hbs", ".ejs", ".erb", ".php",
          ".cshtml", ".razor", ".twig", ".njk", ".liquid"}
STYLES = {".css", ".scss", ".sass", ".less"}
SCRIPTS = {".js", ".ts", ".mjs", ".cjs"}
PYTHON = {".py"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".venv", "venv", "__pycache__", ".next", ".nuxt",
             "coverage", "vendor", "target", ".svelte-kit", "out", ".turbo", ".cache"}
MAX_BYTES = 2_000_000


@dataclass
class Hit:
    rule: str
    check: str
    path: str
    line: int
    message: str
    snippet: str


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def snippet(text: str, start: int, end: int) -> str:
    s = re.sub(r"\s+", " ", text[start:end]).strip()
    return s if len(s) <= 140 else s[:137] + "..."


def attr(tag: str, name: str) -> str | None:
    """Value of an attribute in a start tag (HTML or JSX); '' for a bare attribute; None if absent."""
    m = re.search(rf"\s{name}\s*=\s*(\"([^\"]*)\"|'([^']*)'|\{{([^}}]*)\}}|([^\s>]+))", tag, re.I)
    if m:
        return next(g for g in m.groups()[1:] if g is not None)
    if re.search(rf"\s{name}(?=[\s/>])", tag, re.I):
        return ""
    return None


def has_attr(tag: str, *names: str) -> bool:
    return any(attr(tag, n) is not None for n in names)


def tags(text: str, name: str):
    """Yield (match, tag_text) for start tags of an element, multi-line tags included."""
    for m in re.finditer(rf"<{name}\b(?:[^>\"'{{}}]|\"[^\"]*\"|'[^']*'|\{{[^}}]*\}})*>", text, re.I):
        yield m, m.group(0)


FIELD_TOKENS = [  # (name/id pattern, expected autocomplete token, expected type or inputmode)
    (r"e-?mail", "email", 'type="email"'),
    (r"phone|mobile|\btel\b", "tel", 'type="tel"'),
    (r"first.?name|given.?name|fname", "given-name", None),
    (r"last.?name|family.?name|surname|lname", "family-name", None),
    (r"full.?name|^name$", "name", None),
    (r"street|address.?line|addr1|address1", "address-line1", None),
    (r"\bcity\b|town|locality", "address-level2", None),
    (r"postal|post.?code|\bzip", "postal-code", None),
    (r"country", "country-name", None),
    (r"card.?number|cc.?num|ccnumber|cardnumber", "cc-number", 'inputmode="numeric"'),
    (r"cc.?exp|expiry|expiration", "cc-exp", None),
    (r"cvc|cvv|csc|security.?code", "cc-csc", 'inputmode="numeric"'),
    (r"one.?time|otp|verification.?code|2fa|totp", "one-time-code", 'inputmode="numeric"'),
    (r"user.?name|login", "username", None),
    (r"password|passwd|pwd", "current-password or new-password", None),
]
# Copy and code patterns checked in markup and scripts: (rule, check, pattern, message).
TEXT_RULES = [
    ("CHO-06", "confirmshaming",
     r"no,? thanks?,? i(?:'d| would)? (?:rather|prefer|don'?t|do not|hate|like paying)|i don'?t (?:want|like|need) (?:to )?(?:save|savings|discounts|deals|free)",
     "Decline option shames the user (confirmshaming); use a neutral 'No thanks'."),
    ("CHO-03", "page-load-countdown",
     r"(?:Date\.now\(\)|new Date\(\)\.getTime\(\))\s*\+\s*[\d\s*]+(?=[^;]{0,80};)",
     "Deadline computed from page-load time: a countdown that restarts on every visit is fake urgency."),
    ("CHO-03", "scarcity-claim", r"only \d+ (?:left|remaining|seats|rooms|spots|items|in stock)",
     "Scarcity claim; keep it only if it comes from real inventory."),
    ("CHO-05", "cancel-offline", r"to cancel[^.<]{0,60}\b(?:call|phone|telephone|mail us|write to|visit)",
     "Cancellation needs a call or letter while sign-up is online; cancelling must be as easy as joining."),
    ("FRM-07", "forced-account",
     r"account (?:is )?required|create (?:an |your )?account to (?:continue|check ?out|purchase|buy|order)",
     "Account creation forced before purchase; offer guest checkout or defer sign-up."),
    ("FRM-10", "password-composition",
     r"\(\?=\.\*\[A-Z\]\)|\b(?:1|one) (?:uppercase|capital|symbol|special)|special characters?\b",
     "Password composition rules; NIST SP 800-63B advises length and breach checks instead."),
    ("VIS-07", "rotating-slides", r"setInterval\((?:(?!\},\s*\d+\s*\))[\s\S]){0,400}?(?:slide|carousel|banner)",
     "Content rotates on a timer; give it a pause control (WCAG 2.2.2) or stop auto-advance."),
]
CONSENT_WORDS = r"newsletter|marketing|offers|promo|subscribe|consent|partner|third.?part|share my|updates|special deals"
VAGUE_LINKS = r"click here|here|read more|learn more|more|more info|link|this link"
GENERIC_LABELS = r"ok|okay|submit|yes|no|go|click"
GENERIC_ERRORS = (r"something went wrong|an error (has )?occurred|unknown error|invalid input|"
                  r"invalid value|error!|oops!?|please try again later")


def scan_markup(path: str, text: str, hits: list[Hit]) -> None:
    def add(rule, check, pos, end, msg):
        hits.append(Hit(rule, check, path, line_of(text, pos), msg, snippet(text, pos, end)))

    label_for = set(re.findall(r"(?:\bfor|htmlFor)\s*=\s*[\"'{]([^\"'}]+)", text))

    for m, tag in tags(text, "img"):
        if not has_attr(tag, "alt", "aria-label", "aria-labelledby") and attr(tag, "role") not in ("presentation", "none"):
            add("A11Y-04", "img-no-alt", m.start(), m.end(), "Image has no alt attribute (use alt=\"\" if decorative).")

    for m, tag in tags(text, "(?:input|textarea|select)"):
        itype = (attr(tag, "type") or "text").lower().strip("{}'\"")
        if itype in ("hidden", "submit", "button", "reset", "image"):
            continue
        ident = " ".join(filter(None, [attr(tag, "name"), attr(tag, "id"), attr(tag, "autocomplete")])).lower()
        labelled = has_attr(tag, "aria-label", "aria-labelledby", "title") or (attr(tag, "id") or "") in label_for
        before = text[max(0, m.start() - 300):m.start()]
        wrapped = before.rfind("<label") > before.rfind("</label>")
        if not labelled and not wrapped:
            if has_attr(tag, "placeholder"):
                add("FRM-02", "placeholder-as-label", m.start(), m.end(),
                    "Field's only label is its placeholder; add a visible <label> tied to it.")
            elif itype not in ("checkbox", "radio") or not wrapped:
                add("A11Y-04", "field-no-label", m.start(), m.end(), "Form field has no programmatic label.")
        if itype in ("checkbox",) and has_attr(tag, "checked", "defaultChecked"):
            near = text[m.start():m.end() + 250].lower() + ident
            if re.search(CONSENT_WORDS, near):
                add("CHO-01", "prechecked-consent", m.start(), m.end(),
                    "Consent or marketing checkbox is pre-checked; consent must be an active choice.")
        if itype in ("text", "search", "number", "") and ident:
            for pattern, token, better in FIELD_TOKENS:
                if better and re.search(pattern, ident) and not re.search(r"\b(email|tel)\b", itype):
                    if better.startswith("type") or not has_attr(tag, "inputmode"):
                        add("FRM-05", "wrong-input-type", m.start(), m.end(),
                            f"Field looks like '{token}' but uses type=\"{itype}\"; use {better}.")
                    break
        if ident and attr(tag, "autocomplete") is None and itype not in ("checkbox", "radio", "file", "range", "color"):
            for pattern, token, _ in FIELD_TOKENS:
                if re.search(pattern, ident):
                    add("FRM-05", "missing-autocomplete", m.start(), m.end(),
                        f"Personal-data field without autocomplete; add autocomplete=\"{token}\" (WCAG 1.3.5).")
                    break
        if (attr(tag, "autocomplete") or "").lower() == "off" and re.search(r"pass|user|login|email", ident + itype):
            add("FRM-10", "autocomplete-off-login", m.start(), m.end(),
                "autocomplete=\"off\" on a sign-in field blocks password managers.")
        onpaste = attr(tag, "onpaste") or attr(tag, "onPaste") or ""
        if re.search(r"return\s+false|preventDefault", onpaste):
            add("FRM-10", "paste-blocked", m.start(), m.end(),
                "Paste is blocked; this breaks password managers (WCAG 3.3.8).")

    for m, tag in tags(text, "(?:div|span|li|td|tr|p|section|article|img|svg|i)"):
        if re.search(r"\son[Cc]lick\s*=", tag) and not has_attr(tag, "role") and not has_attr(tag, "tabindex", "tabIndex"):
            add("A11Y-03", "click-on-non-control", m.start(), m.end(),
                "Click handler on a non-interactive element without role/tabindex: unreachable by keyboard.")

    for m, tag in tags(text, "a"):
        href = attr(tag, "href")
        if (href is None or href.strip() in ("#", "", "javascript:void(0)")) and re.search(r"\son[Cc]lick\s*=", tag):
            add("A11Y-04", "link-as-button", m.start(), m.end(), "<a> without a real href acts as a button; use <button>.")

    stems: dict[str, list[re.Match]] = {}
    for m, tag in tags(text, "input"):
        name = attr(tag, "name") or ""
        split = re.fullmatch(r"([a-z_]+?)[_-]?([1-4])", name, re.I)
        if split:
            stems.setdefault(split.group(1).lower(), []).append(m)
        if (attr(tag, "type") or "").lower() == "password":
            maxlen = attr(tag, "maxlength") or attr(tag, "maxLength")
            if maxlen and maxlen.strip("{}").isdigit() and int(maxlen.strip("{}")) < 64:
                add("FRM-10", "password-maxlength", m.start(), m.end(),
                    f"Password capped at {maxlen.strip('{}')} characters; allow at least 64 (NIST SP 800-63B).")
    for stem, ms in stems.items():
        if len(ms) >= 2:
            add("FRM-06", "split-field", ms[0].start(), ms[-1].end(),
                f"'{stem}' is split across {len(ms)} inputs; use one field that accepts any format.")

    for m in re.finditer(rf"<a\b[^>]*>\s*({VAGUE_LINKS})\s*\.?\s*</a>", text, re.I):
        add("CON-05", "vague-link-text", m.start(), m.end(), f"Link text \"{m.group(1)}\" says nothing out of context.")

    for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", text, re.I | re.S):
        inner = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if re.fullmatch(GENERIC_LABELS, inner, re.I):
            add("CON-03", "generic-button-label", m.start(), m.end(),
                f"Button labelled \"{inner}\"; name the action (e.g. \"Save changes\").")
        if not inner and "{" not in m.group(2) and not has_attr(" " + m.group(1), "aria-label", "aria-labelledby", "title"):
            add("A11Y-04", "icon-button-no-name", m.start(), m.end(),
                "Button has no text and no aria-label (icon-only buttons need a name, ideally a visible label).")

    for m, tag in tags(text, "meta"):
        content = (attr(tag, "content") or "").lower().replace(" ", "")
        if (attr(tag, "name") or "").lower() == "viewport" and (
                "user-scalable=no" in content or "user-scalable=0" in content
                or re.search(r"maximum-scale=1(\.0)?(,|$)", content)):
            add("A11Y-05", "zoom-disabled", m.start(), m.end(), "Viewport blocks pinch-zoom (WCAG 1.4.4).")

    for m, tag in tags(text, "(?:video|audio)"):
        if has_attr(tag, "autoplay", "autoPlay") and not has_attr(tag, "muted"):
            add("A11Y-06", "autoplay-sound", m.start(), m.end(), "Media autoplays with sound (WCAG 1.4.2).")
    if re.search(r"<video\b", text, re.I) and not re.search(r"<track\b[^>]*kind\s*=\s*[\"']?(captions|subtitles)", text, re.I):
        m = re.search(r"<video\b", text, re.I)
        add("A11Y-06", "video-no-captions", m.start(), m.end() + 60, "Video without a captions <track> in this file.")

    for m in re.finditer(r"\stab[Ii]ndex\s*=\s*[\"'{]?\s*([1-9]\d*)", text):
        add("A11Y-03", "positive-tabindex", m.start(), m.end(), "Positive tabindex reorders focus unpredictably.")

    for m, tag in tags(text, "(?:a|button|input|select|textarea)"):
        if re.search(r"aria-hidden\s*=\s*[\"'{]?true", tag):
            add("A11Y-04", "aria-hidden-focusable", m.start(), m.end(), "Focusable element is aria-hidden.")

    m = re.search(r"<html\b[^>]*>", text, re.I)
    if m and not has_attr(m.group(0), "lang"):
        add("A11Y-04", "html-no-lang", m.start(), m.end(), "<html> has no lang attribute (WCAG 3.1.1).")
    if m and not re.search(r"<title>\s*\S", text, re.I):
        add("NAV-03", "no-page-title", m.start(), m.end(), "Document has no <title> (WCAG 2.4.2).")

    for m in re.finditer(rf"[>\"'`]\s*({GENERIC_ERRORS})", text, re.I):
        add("ERR-04", "generic-error-text", m.start(), m.end() + 40,
            "Generic error text; say what happened and how to fix it.")

    scan_scripts(path, text, hits)
    scan_styles(path, text, hits)


def scan_scripts(path: str, text: str, hits: list[Hit]) -> None:
    def add(rule, check, pos, end, msg):
        hits.append(Hit(rule, check, path, line_of(text, pos), msg, snippet(text, pos, end)))

    for m in re.finditer(r"(?<![\w.])(?:window\.)?confirm\s*\(", text):
        add("ERR-02", "native-confirm", m.start(), m.end() + 60,
            "Native confirm(): prefer undo for reversible actions; for irreversible ones name the consequence.")
    for m in re.finditer(r"(?<![\w.])(?:window\.)?alert\s*\(", text):
        add("ERR-04", "native-alert", m.start(), m.end() + 60, "Native alert() blocks the page; show inline or toast feedback.")
    for m in re.finditer(r"addEventListener\(\s*['\"]paste['\"][^)]*\)", text):
        if "preventDefault" in text[m.start():m.start() + 300]:
            add("FRM-10", "paste-blocked", m.start(), m.end(), "Paste handler calls preventDefault.")
    for m in re.finditer(r"\b(autoplay|autoPlay)\s*:\s*(true|\{|\d)", text):
        if re.search(r"swiper|slick|carousel|splide|embla|glide|flickity|slider", text[max(0, m.start() - 600):m.end() + 200], re.I):
            add("VIS-07", "carousel-autoplay", m.start(), m.end(), "Auto-advancing carousel; WCAG 2.2.2 requires pause.")
    if path.endswith(tuple(SCRIPTS)):
        for m in re.finditer(rf"['\"`]\s*({GENERIC_ERRORS})", text, re.I):
            add("ERR-04", "generic-error-text", m.start(), m.end() + 40,
                "Generic error text; say what happened and how to fix it.")
    for rule, check, pattern, message in TEXT_RULES:
        for m in re.finditer(pattern, text, re.I):
            add(rule, check, m.start(), min(m.end(), m.start() + 120), message)
    for m in re.finditer(r"\.reset\(\)", text):
        if re.search(r"error|invalid", text[max(0, m.start() - 400):m.start()], re.I):
            add("ERR-05", "reset-on-error", m.start(), m.end(), "Form reset in an error path: users lose what they typed.")


def css_px(value: str) -> float | None:
    m = re.match(r"\s*([\d.]+)\s*(px|rem|em|pt)?", value)
    if not m:
        return None
    n, unit = float(m.group(1)), (m.group(2) or "px")
    return {"px": n, "rem": n * 16, "em": n * 16, "pt": n * 4 / 3}[unit]


def scan_styles(path: str, text: str, hits: list[Hit]) -> None:
    def add(rule, check, pos, end, msg):
        hits.append(Hit(rule, check, path, line_of(text, pos), msg, snippet(text, pos, end)))

    has_focus_style = re.search(r":focus(-visible|-within)?[^{]*\{[^}]*(outline|box-shadow|border)", text)
    for m in re.finditer(r"outline\s*:\s*(none|0)\b", text):
        if not has_focus_style:
            add("A11Y-03", "focus-outline-removed", m.start(), m.end(),
                "outline removed and no :focus/:focus-visible style found in this file.")
    for m in re.finditer(r"font-size\s*:\s*([\d.]+\s*(?:px|rem|em|pt)?)", text):
        px = css_px(m.group(1))
        if px is not None and 0 < px < 12:
            add("VIS-03", "small-font", m.start(), m.end(), f"font-size about {px:.0f}px; body text under 12px is hard to read.")
    for m in re.finditer(r"fontSize\s*:\s*['\"]?([\d.]+)(px|rem)?['\"]?", text):
        px = css_px(m.group(1) + (m.group(2) or "px"))
        if px is not None and 0 < px < 12:
            add("VIS-03", "small-font", m.start(), m.end(), f"fontSize about {px:.0f}px; under 12px is hard to read.")
    # Color pairs: both declared in one CSS rule or inline style, or a text color against the page background.
    color_value = r"(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|[a-z]+)\b"
    page = re.search(rf"(?:^|[\s,}}])(?:body|html|:root)\s*\{{[^}}]*?background(?:-color)?\s*:\s*{color_value}", text)
    page_bg = page.group(1) if page else "#ffffff"
    for block in re.finditer(r"([^{}]*)\{([^{}]*)\}|style\s*=\s*\"([^\"]*)\"", text):
        selector, body = (block.group(1) or "").strip(), block.group(2) or block.group(3) or ""
        # The match begins right after the previous rule's "}", so skip whitespace to report the rule's own line.
        start = block.start() + len(block.group(0)) - len(block.group(0).lstrip())
        fg = re.search(rf"(?<![-\w])color\s*:\s*{color_value}", body)
        bg = re.search(rf"background(?:-color)?\s*:\s*{color_value}", body)
        if fg and bg:
            check_pair(path, text, start, block.end(), fg.group(1), bg.group(1), hits)
        elif fg and not re.search(r"background", body) and not re.search(r"\b(header|nav|footer|btn|button|badge|chip)\b", selector):
            check_pair(path, text, start, block.end(), fg.group(1), page_bg, hits,
                       note=f" (against the page background {page_bg}; verify the element's real background)")
        width = re.search(r"(?<![-\w])(?:min-)?width\s*:\s*([\d.]+(?:px|rem|em)?)", body)
        height = re.search(r"(?<![-\w])(?:min-)?height\s*:\s*([\d.]+(?:px|rem|em)?)", body)
        if width and height and re.search(r"btn|button|icon|close|toggle|tab\b|chip|\ba\b", selector, re.I):
            w, h = css_px(width.group(1)), css_px(height.group(1))
            if w and h and min(w, h) < 24:
                add("PLT-03", "small-target", start, block.end(),
                    f"Control sized {w:.0f}x{h:.0f}px; targets need 24x24 CSS px (WCAG 2.5.8) and 44-48 on touch.")
    if re.search(r"@keyframes|animation\s*:", text) and "prefers-reduced-motion" not in text:
        m = re.search(r"@keyframes|animation\s*:", text)
        add("A11Y-05", "motion-without-reduced-motion", m.start(), m.end() + 40,
            "Animations without a prefers-reduced-motion rule in this file.")


def check_pair(path, text, start, end, fg_text, bg_text, hits, rule="A11Y-01", note=""):
    try:
        r = ratio(parse_color(fg_text), parse_color(bg_text))
    except ValueError:
        return
    if r < 4.5:
        level = "fails AA for all text" if r < 3 else "fails AA for normal text (passes only large text)"
        hits.append(Hit(rule, "low-contrast-pair", path, line_of(text, start),
                        f"{fg_text} on {bg_text} = {r:.2f}:1, {level}{note}.", snippet(text, start, end)))


def scan_python_ui(path: str, text: str, hits: list[Hit]) -> None:
    if not re.search(r"import\s+tkinter|from\s+tkinter|PyQt\d|PySide\d|customtkinter|import\s+wx\b", text):
        return

    def add(rule, check, pos, end, msg):
        hits.append(Hit(rule, check, path, line_of(text, pos), msg, snippet(text, pos, end)))

    for m in re.finditer(r"font\s*=\s*\(\s*(?:[\"'][^\"']*[\"']|[A-Za-z_][\w.]*)\s*,\s*(-?\d+)", text):
        size = int(m.group(1))
        if (0 < size < 9) or (-12 < size < 0):  # Tk: positive = points, negative = pixels
            add("VIS-03", "small-font", m.start(), m.end(), f"Font size {size} is small for body text (aim for 9 pt or more).")
    for m in re.finditer(r"messagebox\.(askyesno|askokcancel|askyesnocancel|askquestion)\s*\(", text):
        add("CON-03", "stock-yes-no-dialog", m.start(), m.end() + 80,
            "Stock Yes/No or OK/Cancel dialog; buttons can't name the action. Consider a dialog with verb labels.")
    for m in re.finditer(r"QMessageBox\.(question|warning)\s*\(", text):
        add("CON-03", "stock-yes-no-dialog", m.start(), m.end() + 80,
            "Stock QMessageBox buttons; set custom button text that names the action.")
    for m in re.finditer(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)", text):
        args = m.group(1)
        fg = re.search(r"\b(?:fg|foreground)\s*=\s*[\"']([^\"']+)[\"']", args)
        bg = re.search(r"\b(?:bg|background)\s*=\s*[\"']([^\"']+)[\"']", args)
        if fg and bg:
            check_pair(path, text, m.start(), m.end(), fg.group(1), bg.group(1), hits)
    for m in re.finditer(rf"[\"']\s*({GENERIC_ERRORS})", text, re.I):
        add("ERR-04", "generic-error-text", m.start(), m.end() + 40, "Generic error text; say what happened and how to fix it.")
    scan_styles(path, "\n".join(re.findall(r"setStyleSheet\(\s*[\"']([^\"']*)", text)), hits) if "setStyleSheet" in text else None


TOKEN = re.compile(r"[\"']?(--[\w-]+|[A-Za-z_][\w-]*)[\"']?\s*[:=]\s*[\"']?(#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?)\b")
TEXT_TOKEN = re.compile(r"ink|text|fg|foreground|muted|subtle|secondary|tertiary|label|link|warn|bad|error|danger|"
                        r"good|success|ok\b|info|accent|primary", re.I)
BG_TOKEN = re.compile(r"page|bg|background|card|surface|panel|canvas|paper|window|base|body", re.I)


def scan_tokens(path: str, text: str, hits: list[Hit]) -> None:
    """Contrast of theme or design tokens: text-like colors against background-like colors in one block."""
    found = list(TOKEN.finditer(text))
    if len(found) < 4:
        return
    blocks: dict[int, list[re.Match]] = {}
    stack, k = [], 0
    for i, ch in enumerate(text):  # group tokens by their innermost enclosing { ... }
        while k < len(found) and found[k].start() == i:
            blocks.setdefault(stack[-1] if stack else -1, []).append(found[k])
            k += 1
        if ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            stack.pop()
    for tokens in blocks.values():
        named = {m.group(1).lstrip("-"): m for m in tokens}
        bgs = {n: m for n, m in named.items() if BG_TOKEN.search(n) and not re.search(r"ink|text|fg|border", n, re.I)}
        for name, m in named.items():
            if name in bgs or not TEXT_TOKEN.search(name) or re.search(r"hover|select|border|grid|shadow|focus", name, re.I):
                continue
            # "accent_ink" and "color-on-primary" belong on "accent" and "color-primary"; others on any background.
            base = re.sub(r"[-_]?(ink|text|fg|foreground)$", "", re.sub(r"(^|[-_])on[-_]", r"\1", name, flags=re.I), flags=re.I)
            pairs = [(base, named[base])] if base != name and base in named else list(bgs.items())
            failing = sorted((ratio(parse_color(m.group(2)), parse_color(bg.group(2))), bg_name, bg.group(2))
                             for bg_name, bg in pairs)
            failing = [f for f in failing if f[0] < 4.5]
            if failing:
                r, bg_name, bg_hex = failing[0]
                use = "fails AA for any text" if r < 3 else "fails AA for normal text; large text and icons only"
                more = f"; fails on {len(failing) - 1} other background(s) too" if len(failing) > 1 else ""
                hits.append(Hit("A11Y-01", "token-pair-contrast", path, line_of(text, m.start()),
                                f"Token '{name}' {m.group(2)} on '{bg_name}' {bg_hex} = {r:.2f}:1, {use}{more}"
                                " (if this pair is used together).", snippet(text, m.start(), m.end())))


def iter_files(paths: list[str]):
    for p in map(Path, paths):
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and not any(part in SKIP_DIRS for part in f.parts):
                    yield f


def scan(paths: list[str]) -> list[Hit]:
    hits: list[Hit] = []
    for f in iter_files(paths):
        ext = f.suffix.lower()
        if ext not in MARKUP | STYLES | SCRIPTS | PYTHON | {".json"} or f.stat().st_size > MAX_BYTES:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        name = str(f)
        scan_tokens(name, text, hits)
        if ext in MARKUP:
            scan_markup(name, text, hits)
        elif ext in STYLES:
            scan_styles(name, text, hits)
        elif ext in SCRIPTS:
            if re.search(r"<[A-Za-z][\w.]*[\s>]", text) and re.search(r"return\s*\(|=>\s*\(|React|jsx", text):
                scan_markup(name, text, hits)
            else:
                scan_scripts(name, text, hits)
        elif ext in PYTHON:
            scan_python_ui(name, text, hits)
    seen, unique = set(), []
    for h in hits:  # one hit per check per line
        if (h.rule, h.check, h.path, h.line) not in seen:
            seen.add((h.rule, h.check, h.path, h.line))
            unique.append(h)
    return unique


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a text report")
    ap.add_argument("--rules", help="comma-separated rule-ID prefixes to keep, e.g. A11Y,FRM-05")
    args = ap.parse_args(argv)
    hits = scan(args.paths)
    if args.rules:
        keep = tuple(r.strip().upper() for r in args.rules.split(","))
        hits = [h for h in hits if h.rule.upper().startswith(keep)]
    if args.json:
        print(json.dumps([asdict(h) for h in hits], indent=1))
        return 0
    if not hits:
        print("No candidates found. That doesn't mean the UI follows the rules; most UX issues need a look at the running UI.")
        return 0
    by_rule: dict[str, list[Hit]] = {}
    for h in hits:
        by_rule.setdefault(h.rule, []).append(h)
    print(f"{len(hits)} candidate(s) in {len({h.path for h in hits})} file(s). Verify each one; patterns over-report.\n")
    for rule in sorted(by_rule):
        print(f"## {rule}")
        for h in by_rule[rule]:
            print(f"- {h.path}:{h.line} [{h.check}] {h.message}\n    {h.snippet}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
