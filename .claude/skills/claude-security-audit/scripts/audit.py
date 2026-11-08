#!/usr/bin/env python3
"""Claude security and confidentiality audit for this machine (instructions: ../SKILL.md).

    python audit.py collect [--offline] [--repo PATH]...   check everything, write a report, print a JSON summary
    python audit.py scrub [--apply] [--repo PATH]... [--local-only | --no-local] [--include-dirty]
    python audit.py add-analysis < notes.md                append your analysis to the latest report
    python audit.py show                                   print the latest report
    python audit.py mark-reviewed                          make the last collect the baseline for the next one
    python audit.py where                                  print the state and report folders

Standard library only (Python 3.9+). Settings are read, never changed. The owner's identifiers (Claude account email
and name, git email, OS user name) are read only to find and replace them: output shows [owner-email], [owner-name],
~ and %USERPROFILE% instead, and nothing identifying is written to the report or the state. Paths that the owner's
own Read deny rules cover are not read. Online checks (skipped with --offline) fetch public data only: Claude Code's
docs and changelog, its latest npm version, and OSV advisories for package names and versions.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SCHEMA = 1
USER_AGENT = "claude-security-audit/1"
SEVERITIES = ("critical", "high", "medium", "low", "info")
PLACEHOLDER_EMAIL = "you@example.com"
PLACEHOLDER_NAME = "Your Name"
RULE_MARKER = "claude-security-audit:identity-rule"
DOC = "https://code.claude.com/docs/en/"
DOCS_SETTINGS = DOC + "settings-reference.md"
DOCS_ENV = DOC + "env-vars.md"
CHANGELOG_URL = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
NPM_LATEST = "https://registry.npmjs.org/@anthropic-ai%2Fclaude-code/latest"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/"
CC_NPM = "@anthropic-ai/claude-code"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
PRECEDENCE = ("managed", "project-local", "project", "user")

EMAIL_RE = re.compile(r"(?<![\w.+%-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}(?![\w-])")
FILE_TLDS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "css", "js", "mjs", "ts", "tsx", "json", "md",
             "py", "txt", "html", "xml", "yml", "yaml", "lock", "map", "woff", "woff2", "ttf", "otf", "mp3", "mp4", "wav"}
BENIGN_EMAIL = re.compile(r"(?i)(^git@|noreply|no-reply|donotreply|do-not-reply|@users\.noreply\.github\.com$|"
                          r"@(?:[\w-]+\.)*example\.(?:com|org|net)$|@localhost$|\.(?:invalid|test|example|localhost)$)")
SECRET_SHAPES = [re.compile(p) for p in (
    r"sk-ant-[A-Za-z0-9_-]{10,}", r"\bsk-[A-Za-z0-9_-]{20,}", r"\bgh[pousr]_[A-Za-z0-9]{20,}",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}", r"\bxox[abprs]-[A-Za-z0-9-]{10,}", r"\bAKIA[0-9A-Z]{16}\b",
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")]
ID_SHAPES = [re.compile(p) for p in (  # hex-aware edges: claude.ai joins two account UUIDs with "_" in folder names
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-fA-F])",
    r"(?<![0-9A-Za-z])[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}(?![0-9A-Za-z])")]                # cloud billing accounts
SECRET_NAME = re.compile(r"(?i)(api[_-]?key|token|secret|passw(?:or)?d|credential|auth|bearer|private[_-]?key|"
                         r"access[_-]?key|master[_-]?key|(?:^|_)key$|cookie|session[_-]?id|(?:^|_)dsn$)")
VAR_REFERENCE = re.compile(r"^\s*(\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%)\s*$")
NETWORK_CMD = re.compile(r"(?i)(\b(curl|wget|invoke-webrequest|iwr|invoke-restmethod|irm|ncat|scp|ftp)\b|\bnc\s|"
                         r"https?://(?!(localhost|127\.0\.0\.1|\[::1\])))")
CONTACT_HINT = re.compile(r"(?i)(user[-_ ]?agent|mailto[=:]|[?&]email=|[\"']email[\"']\s*[:=,]|\bemail\s*=\s*[\"'])")
GIT_IDENTITY_READ = re.compile(r"(?i)(git\s+config\s+(?:--get\s+)?user\.email|GIT_AUTHOR_EMAIL|GIT_COMMITTER_EMAIL|"
                               r"[\"']user\.email[\"'])")
HTTP_USE = re.compile(r"(?i)(requests\.|urllib|httpx|aiohttp|fetch\(|axios|curl\b|invoke-webrequest|invoke-restmethod|"
                      r"httpclient|http\.get|wget\b)")
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".zsh", ".ps1", ".psm1", ".cmd",
            ".bat", ".cs", ".go", ".rb", ".php", ".java", ".kt", ".rs", ".r", ".jl", ".ipynb", ".swift"}
TEXT_EXT = CODE_EXT | {".md", ".markdown", ".txt", ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg",
                       ".conf", ".csproj", ".props", ".targets", ".xml", ".html", ".htm", ".css", ".scss", ".vue",
                       ".svelte", ".asset", ".env", ".example", ".gradle", ".kts", ".plist", ".sql", ".tf", ".hcl",
                       ".rst", ".adoc", ".tex", ".bib", ".cff", ".gemspec", ".podspec", ".nuspec", ".service"}
NAMED_TEXT = {"license", "licence", "copying", "notice", "authors", "contributors", "codeowners", "dockerfile",
              "makefile", "readme", "maintainers", "funding", "citation"}
SKIP_DIRS = ("node_modules/", ".venv/", "venv/", "vendor/", "Library/", "Temp/", "Logs/", "obj/", "bin/", "dist/",
             "build/", "PackageCache/", ".git/", "__pycache__/", "site-packages/")
LOCK_FILES = re.compile(r"(?i)(\.lock|\.lockb|-lock\.ya?ml|-lock\.json|^package-lock\.json|^npm-shrinkwrap\.json)$")
DOC_EXT = {".md", ".markdown", ".txt", ".rst", ".adoc", ".html", ".htm"}
COMMON_USERNAMES = {"admin", "administrator", "user", "users", "owner", "test", "guest", "dev", "developer", "root",
                    "ubuntu", "default", "public", "home", "pi", "vagrant", "runner", "build", "docker", "local"}
SELF_DIR = Path(__file__).resolve().parent.parent
ANY_ARGS = r"(?:\s*:\s*\*|\s+\*|\*|\s*)\)$"   # the command alone, or followed only by a wildcard
BROAD_ALLOW = [
    (re.compile(r"^(Bash|PowerShell)(\(\s*\*?\s*(:\s*\*)?\s*\))?$"), "any shell command"),
    (re.compile(r"(?i)^(Bash|PowerShell)\((python3?|py|node|deno|bun|ruby|perl|php|powershell|pwsh|cmd|bash|sh|zsh|"
                r"uv run|uv|uvx|npx|pnpm dlx|pnpm|bunx|dotnet run|go run|cargo run)" + ANY_ARGS),
     "a script interpreter or package runner with any arguments, so any code"),
    (re.compile(r"(?i)^(Bash|PowerShell)\((curl|wget|invoke-webrequest|iwr|invoke-restmethod|irm|nc|ncat|scp|ssh|ftp)"
                + ANY_ARGS), "a network tool with any arguments, so it can send data anywhere"),
    (re.compile(r"(?i)^(Bash|PowerShell)\(.*\b(python3?|py|node|deno|bun|ruby|perl|php|powershell|pwsh|bash|sh|zsh|cmd)"
                r"(\.exe)?\b.*\s(-c|-e|--eval|-command|/c|-encodedcommand)\b.*\*"),
     "inline code with any content, so any code"),
    (re.compile(r"^WebFetch(\(\s*\*?\s*\))?$"), "fetching any web address"),
    (re.compile(r"^mcp__\*|^mcp__[A-Za-z0-9_-]*\*$"), "every tool of an MCP server"),
    (re.compile(r"^(Edit|Write)(\(\s*\*{0,2}\s*\))?$"), "editing any file"),
]
OFFICIAL_MARKETS = re.compile(r"(?i)(^claude-plugins-official\b|^anthropic|anthropics/)")
CHANGELOG_SECURITY = re.compile(
    r"(?i)(\bvulnerab\w*|\bcve-\d|\bbypass\w*|\binject\w*|\bexfiltrat\w*|(?<!memory )\bleak\w*|\bsanitiz\w*|"
    r"sandbox escape|escap\w* the sandbox|privilege escalation|\bsecurity (?:fix|issue|bug|hardening|vulnerabilit\w*)|"
    r"without (?:a |any )?(?:permission )?prompt|skip\w* (?:the )?permission check\w*|"
    r"\b(?:deny|ask)(?: and (?:deny|ask))? rules? (?:missed|didn't|did not|failed|could)|missed commands)")
CHANGELOG_NEW_SETTING = re.compile(r"(?i)^added\b.*`(?:[A-Z][A-Z0-9_]{5,}|[A-Za-z][A-Za-z0-9_.-]{3,}`.*\b(?:setting|"
                                   r"environment variable|variable|flag)\b)")
CHANGELOG_PRIVACY = re.compile(r"(?i)\b(privacy|telemetry|redact\w*|secrets?|credentials?|e-?mail|retention|transcripts?|"
                               r"/feedback|/share|attribution|analytics|tracking)\b")
CHANGELOG_POLICY = re.compile(r"(?i)\b(permission rules?|permission modes?|permissions\.\w+|sandbox\w*|deny rules?|denied|"
                              r"trust dialog|workspace trust|auto mode|managed settings|managed-settings|subprocess env\w*|"
                              r"egress|certificates?|oauth)\b")
CHANGELOG_ORDER = ("security", "new-setting", "privacy", "policy")
SAFE_ENV_VALUES = {
    "DISABLE_TELEMETRY", "DISABLE_ERROR_REPORTING", "DISABLE_FEEDBACK_COMMAND", "DISABLE_BUG_COMMAND",
    "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "DISABLE_AUTOUPDATER",
    "DO_NOT_TRACK", "DISABLE_GROWTHBOOK", "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB", "ENABLE_CLAUDEAI_MCP_SERVERS",
    "CLAUDE_CODE_ENABLE_SHARE_BUNDLE", "CLAUDE_CODE_AUTO_MODE_SERVER", "CLAUDE_CODE_ENABLE_TELEMETRY",
    "OTEL_LOG_USER_PROMPTS", "OTEL_LOG_TOOL_DETAILS", "OTEL_METRICS_INCLUDE_ACCOUNT_UUID",
    "OTEL_METRICS_INCLUDE_SESSION_ID", "CLAUDE_CODE_DISABLE_FEATURE_FLAGS", "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS",
}
TRACKED_SETTINGS = ("cleanupPeriodDays", "desktopSessionCleanupPeriodDays", "feedbackDrafts", "feedbackSurveyRate",
                    "skipWebFetchPreflight", "attribution", "enableAllProjectMcpServers", "disableClaudeAiConnectors",
                    "permissions.defaultMode", "permissions.disableBypassPermissionsMode",
                    "permissions.blockReadsOutsideWorkingDirectories", "skipDangerousModePermissionPrompt",
                    "sandbox.enabled", "autoUpdatesChannel", "disableAllHooks")


# ---------------------------------------------------------------- helpers

def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:12]


def vtuple(v) -> tuple:
    nums = re.findall(r"\d+", str(v or ""))
    return tuple(int(n) for n in nums[:4])


def truthy(v) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def read_text(path, limit: int = 2_000_000):
    """File text, or None when missing, too big, not a file or (by a NUL byte) binary."""
    try:
        p = Path(path)
        if not p.is_file() or p.stat().st_size > limit:
            return None
        raw = p.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None
    return raw.decode("utf-8-sig", errors="replace")


def read_json(path, limit: int = 60_000_000):
    text = read_text(path, limit)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def dig(data, dotted: str):
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def benign_email(e: str) -> bool:
    e = (e or "").strip().lower()
    return bool(BENIGN_EMAIL.search(e)) or e.rsplit(".", 1)[-1] in FILE_TLDS


def host_of(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def finding(fid, severity, area, title, detail="", fix="", docs=""):
    return {"id": fid, "severity": severity, "area": area, "title": title, "detail": detail.strip(), "fix": fix.strip(),
            "docs": docs}


class Ctx:
    """Where things are. Tests build one with a temporary home and environment."""

    def __init__(self, home=None, state=None, cwd=None, offline=False, environ=None, system=None):
        self.environ = dict(os.environ if environ is None else environ)
        self.home = Path(home) if home else Path.home()
        self.system = system or ("windows" if os.name == "nt" else "mac" if sys.platform == "darwin" else "linux")
        self.cwd = Path(cwd) if cwd else Path.cwd()
        self.offline = offline
        self.errors: list[str] = []
        self.state = Path(state) if state else self.default_state()
        self.identity = Identity()
        self.red = Redactor(self, self.identity)

    def default_state(self) -> Path:
        if self.environ.get("CLAUDE_SECURITY_AUDIT_DIR"):
            return Path(self.environ["CLAUDE_SECURITY_AUDIT_DIR"]).expanduser()
        if self.system == "windows":
            base = Path(self.environ.get("LOCALAPPDATA") or self.home / "AppData" / "Local")
        elif self.system == "mac":
            base = self.home / "Library" / "Application Support"
        else:
            base = Path(self.environ.get("XDG_STATE_HOME") or self.home / ".local" / "state")
        return base / "claude-security-audit"

    def appdata(self) -> Path:
        return Path(self.environ.get("APPDATA") or self.home / "AppData" / "Roaming")

    def localappdata(self) -> Path:
        return Path(self.environ.get("LOCALAPPDATA") or self.home / "AppData" / "Local")


def run(ctx: Ctx, cmd, cwd=None, timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=ctx.environ,
                           capture_output=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return 127, ""
    return p.returncode, p.stdout.decode("utf-8", "replace")


def git(ctx: Ctx, args, cwd=None, timeout: int = 30) -> str:
    code, out = run(ctx, ["git", *args], cwd=cwd, timeout=timeout)
    return out if code == 0 else ""


def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_post_json(url: str, payload, timeout: int = 25):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------- the owner's identity (run time only)

SEP = r"(?:\\\\|\\|/)"
PATH_END = r"(?=\\|/|[\"'`\s,;:)\]}>*]|$)"


def username_path_rules(user: str):
    """(regex, form) for the OS user name inside home paths. `win` forms become %USERPROFILE%, `posix` forms ~."""
    u = re.escape(user)
    win = re.compile(r"(?i)(?<![A-Za-z0-9])[A-Za-z]:" + SEP + r"users" + SEP + u + PATH_END)
    posix = re.compile(r"(?i)(?<![\w.~])(?:/mnt/[a-z]|//?[a-z])?/(?:users|home)/" + u + PATH_END)
    return [(win, "win"), (posix, "posix")]


def name_regex(name: str, flexible: bool = False):
    words = [re.escape(w) for w in name.split()]
    joiner = r"[\s._-]+" if flexible else r"\s+"
    return re.compile(r"(?i)(?<!\w)" + joiner.join(words) + r"(?!\w)")


class Identity:
    """The owner's identifiers. Held in memory for one run; never printed or saved."""

    def __init__(self):
        self.emails: set[str] = set()
        self.names: set[str] = set()      # full names: found and replaced
        self.parts: set[str] = set()      # long single words of a name: found and reported, never replaced
        self.short: set[str] = set()      # short one-word names: hidden in this script's output only (too common
        #                                   a word to search files for)
        self.username = ""
        self.bare_username = False        # also match the user name on its own (only when it is distinctive)
        self.host = ""                    # computer name, only when it contains the user name or a name part
        self.sources: list[str] = []

    def add_email(self, value, source: str) -> None:
        v = str(value or "").strip().lower()
        if v and EMAIL_RE.fullmatch(v) and not benign_email(v):
            self.emails.add(v)
            self.sources.append(source)

    def add_name(self, value, source: str, single_ok: bool = False) -> None:
        v = " ".join(str(value or "").split())
        if not v or "@" in v:
            return
        words = v.split()
        if len(words) >= 2 and len(v) >= 5:
            self.names.add(v)
            self.sources.append(source)
            for w in words:
                if len(w) >= 8 and w.isalpha():
                    self.parts.add(w)
        elif single_ok and len(v) >= 4:
            self.names.add(v)
            self.sources.append(source)
        elif len(v) >= 8 and v.isalpha():
            self.parts.add(v)
        elif len(v) >= 3:
            self.short.add(v)

    def empty(self) -> bool:
        return not (self.emails or self.names or self.username)


def discover_identity(ctx: Ctx) -> Identity:
    ident = Identity()
    ident.username = ctx.environ.get("USERNAME") or ctx.environ.get("USER") or ctx.home.name
    ident.bare_username = len(ident.username) >= 5 and ident.username.lower() not in COMMON_USERNAMES
    for cfg in (ctx.home / ".claude.json", ctx.home / ".claude-local" / ".claude.json"):
        data = read_json(cfg)
        acct = data.get("oauthAccount") if isinstance(data, dict) else None
        if isinstance(acct, dict):
            ident.add_email(acct.get("emailAddress"), "claude-account")
            ident.add_name(acct.get("fullName"), "claude-account")
            ident.add_name(acct.get("displayName"), "claude-account")
    for scope in ("--global", "--system"):
        ident.add_email(git(ctx, ["config", scope, "user.email"]).strip(), "git" + scope)
        ident.add_name(git(ctx, ["config", scope, "user.name"]).strip(), "git" + scope)
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL", "EMAIL"):
        ident.add_email(ctx.environ.get(var), "environment")
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        ident.add_name(ctx.environ.get(var), "environment")
    local = read_json(ctx.state / "identity.local.json")
    if isinstance(local, dict):  # optional, written by the owner only, never by this script
        for e in local.get("emails") or []:
            ident.add_email(e, "identity.local.json")
        for n in local.get("names") or []:
            ident.add_name(n, "identity.local.json", single_ok=True)
    host = (ctx.environ.get("COMPUTERNAME") or platform.node() or "").split(".")[0]
    clues = [ident.username.lower()] + [p.lower() for p in ident.parts]
    if host and any(len(c) >= 4 and c in host.lower() for c in clues if c):
        ident.host = host
    return ident


class Redactor:
    """Replaces the owner's identifiers, home paths, secrets and other email addresses in text meant for output."""

    def __init__(self, ctx: Ctx, ident: Identity):
        # Square-bracket placeholders: markdown viewers hide unknown <tags>, which would swallow <owner-email>.
        rules: list = []
        for e in sorted(ident.emails, key=len, reverse=True):
            rules.append((re.compile(re.escape(e), re.I), "[owner-email]"))
        for n in sorted(ident.names, key=len, reverse=True):
            rules.append((name_regex(n, flexible=True), "[owner-name]"))
        for p in sorted(ident.parts, key=len, reverse=True):
            rules.append((re.compile(r"(?i)(?<!\w)" + re.escape(p) + r"(?!\w)"), "[owner-name]"))
        for s in sorted(ident.short, key=len, reverse=True):  # exact case and whole word only: "Ada" yes, "ada" no
            rules.append((re.compile(r"(?<![A-Za-z0-9])" + re.escape(s) + r"(?![A-Za-z0-9])"), "[owner-name]"))
        if ident.username:
            for rx, _form in username_path_rules(ident.username):
                rules.append((rx, "~"))
            rules.append((re.compile(r"(?i)\b([A-Za-z])--Users-" + re.escape(ident.username) + r"(?=-|\b)"),
                          r"\1--Users-[user]"))
        home = str(ctx.home)
        for form in sorted({home, home.replace("\\", "/"), home.replace("\\", "\\\\")}, key=len, reverse=True):
            rules.append((re.compile(re.escape(form), re.I), "~"))
        if ident.host:
            rules.append((re.compile(r"(?i)(?<![A-Za-z0-9])" + re.escape(ident.host) + r"(?![A-Za-z0-9])"), "[host]"))
        if ident.username and ident.bare_username:  # last identity rule: the user name on its own
            rules.append((re.compile(r"(?i)(?<![A-Za-z0-9])" + re.escape(ident.username) + r"(?![A-Za-z0-9])"), "[user]"))
        rules += [(rx, "[id]") for rx in ID_SHAPES]
        rules += [(rx, "[secret]") for rx in SECRET_SHAPES]
        rules.append((re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{16,}"), r"\1[secret]"))
        rules.append((EMAIL_RE, lambda m: m.group(0) if benign_email(m.group(0)) else "[email]"))
        self.rules = rules

    def __call__(self, text) -> str:
        out = str(text)
        for rx, repl in self.rules:
            out = rx.sub(repl, out)
        return out


def set_identity(ctx: Ctx, ident: Identity) -> None:
    ctx.identity = ident
    ctx.red = Redactor(ctx, ident)


def red_rule(ctx: Ctx, rule: str, limit: int = 0) -> str:
    """A permission rule for display: the user name becomes [user] but the path keeps its form, so the owner can
    still find the rule in the settings file (`//c/Users/[user]/x/**`, not `~/x/**`). With `limit`, a rule that is a
    whole approved script (line breaks and all) is flattened to one line and shortened."""
    u = ctx.identity.username
    if u:
        rule = re.sub(r"(?i)(?<![A-Za-z0-9])" + re.escape(u) + r"(?![A-Za-z0-9])", "[user]", rule)
    shown = ctx.red(rule)
    if limit:
        shown = re.sub(r"\s+", " ", shown).strip()
        if len(shown) > limit:
            shown = shown[:limit - 4] + " ...)" if shown.endswith(")") else shown[:limit - 3] + "..."
    return shown


# ---------------------------------------------------------------- where Claude keeps things

class Layer:
    def __init__(self, scope: str, path: Path, data: dict):
        self.scope, self.path, self.data = scope, path, data


def managed_dir(ctx: Ctx) -> Path:
    if ctx.system == "windows":
        return Path(ctx.environ.get("PROGRAMFILES") or r"C:\Program Files") / "ClaudeCode"
    if ctx.system == "mac":
        return Path("/Library/Application Support/ClaudeCode")
    return Path("/etc/claude-code")


def desktop_dir(ctx: Ctx) -> Path:
    if ctx.system == "windows":
        return ctx.appdata() / "Claude"
    if ctx.system == "mac":
        return ctx.home / "Library" / "Application Support" / "Claude"
    return ctx.home / ".config" / "Claude"


def profiles(ctx: Ctx) -> list[tuple[str, Path, Path]]:
    """(label, config folder, global JSON) for the default profile, profile B (~/.claude-local) and CLAUDE_CONFIG_DIR."""
    out = [("A", ctx.home / ".claude", ctx.home / ".claude.json")]
    b = ctx.home / ".claude-local"
    if b.is_dir():
        out.append(("B", b, b / ".claude.json"))
    extra = ctx.environ.get("CLAUDE_CONFIG_DIR")
    if extra:
        p = Path(extra).expanduser()
        try:
            known = {d.resolve() for _, d, _ in out}
            if p.is_dir() and p.resolve() not in known:
                out.append(("custom", p, p / ".claude.json"))
        except OSError:
            pass
    return out


def load_layers(ctx: Ctx, profile_dir: Path, repo) -> list[Layer]:
    layers = []
    paths = [("managed", managed_dir(ctx) / "managed-settings.json"), ("user", profile_dir / "settings.json")]
    if repo:
        paths += [("project", Path(repo) / ".claude" / "settings.json"),
                  ("project-local", Path(repo) / ".claude" / "settings.local.json")]
    for scope, path in paths:
        data = read_json(path)
        if isinstance(data, dict):
            layers.append(Layer(scope, path, data))
    return layers


def get(layers: list[Layer], dotted: str):
    """(value, scope) of a setting, by Claude Code's precedence: managed, local project, shared project, user."""
    for scope in PRECEDENCE:
        for layer in layers:
            if layer.scope == scope:
                v = dig(layer.data, dotted)
                if v is not None:
                    return v, scope
    return None, None


def os_env(ctx: Ctx, name: str):
    if ctx.system == "windows" and "AUDIT_NO_REGISTRY" not in ctx.environ:
        try:
            import winreg  # noqa: PLC0415 - Windows only
            for root, sub, label in ((winreg.HKEY_CURRENT_USER, "Environment", "Windows user environment"),
                                     (winreg.HKEY_LOCAL_MACHINE,
                                      r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                                      "Windows system environment")):
                try:
                    with winreg.OpenKey(root, sub) as key:
                        value, _ = winreg.QueryValueEx(key, name)
                        if str(value) != "":
                            return str(value), label
                except OSError:
                    pass
        except ImportError:
            pass
    v = ctx.environ.get(name)
    return (v, "this session's environment") if v not in (None, "") else (None, None)


def env_value(ctx: Ctx, layers: list[Layer], name: str):
    for scope in PRECEDENCE:
        for layer in layers:
            env = layer.data.get("env") if layer.scope == scope else None
            if isinstance(env, dict) and name in env and str(env[name]) != "":
                return str(env[name]), f"{scope} settings"
    return os_env(ctx, name)


def rules(layers: list[Layer], kind: str) -> list[tuple[str, str]]:
    out = []
    for layer in layers:
        perms = layer.data.get("permissions")
        if isinstance(perms, dict):
            for r in perms.get(kind) or []:
                if isinstance(r, str):
                    out.append((r, layer.scope))
    return out


RULE_RE = re.compile(r"^\s*([A-Za-z_][\w-]*)(?:\((.*)\))?\s*$", re.S)


def parse_rule(rule: str):
    m = RULE_RE.match(rule or "")
    return (m.group(1), m.group(2)) if m else (rule, None)


def posix_path(ctx: Ctx, path) -> str:
    """How Claude Code matches paths on Windows: C:\\Users\\x becomes /c/Users/x (compared case-insensitively here)."""
    s = str(path).replace("\\", "/")
    m = re.match(r"^([A-Za-z]):(/|$)", s)
    if m:
        s = "/" + m.group(1).lower() + s[2:]
    return s.lower() if ctx.system == "windows" else s


def anchor_spec(ctx: Ctx, spec: str):
    """Absolute glob for a rule path, or None for a rule relative to the working directory."""
    s = spec.strip().replace("\\", "/")
    if s.startswith("//"):
        s = s[1:]
    elif s == "~" or s.startswith("~/"):
        s = posix_path(ctx, ctx.home) + s[1:]
    else:
        return None
    return s.lower() if ctx.system == "windows" else s


def glob_rx(glob: str):
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile("^" + out + "(?:/.*)?$")


def covered(ctx: Ctx, deny: list[tuple[str, str]], path) -> bool:
    """True when an absolute or home-relative Read deny rule covers `path` (what applies in every project)."""
    target = posix_path(ctx, path)
    for rule, _scope in deny:
        tool, spec = parse_rule(rule)
        if tool != "Read":
            continue
        if spec is None or spec.strip() in ("", "*", "**"):
            return True
        anchored = anchor_spec(ctx, spec)
        if anchored and glob_rx(anchored).match(target):
            return True
    return False


def relative_covers(deny: list[tuple[str, str]], filename: str) -> bool:
    for rule, _scope in deny:
        tool, spec = parse_rule(rule)
        if tool == "Read" and spec and spec.strip().replace("\\", "/") in (filename, "**/" + filename, "./" + filename):
            return True
    return False


# ---------------------------------------------------------------- inventory

def versions(ctx: Ctx) -> dict:
    out: dict = {}
    code, text = run(ctx, ["claude", "--version"], timeout=30)
    m = re.search(r"\d+\.\d+\.\d+", text) if code == 0 else None
    if m:
        out["cli"] = m.group(0)
        import shutil  # noqa: PLC0415
        where = (shutil.which("claude", path=ctx.environ.get("PATH")) or "").replace("\\", "/").lower()
        out["cli_via"] = ("winget" if "/winget/" in where else "npm" if "/npm" in where or "node_modules" in where
                          else "native" if "/.local/" in where or "/.claude/" in where else "unknown")
    best = None
    for d in (".vscode", ".vscode-insiders", ".cursor", ".windsurf"):
        base = ctx.home / d / "extensions"
        for p in base.glob("anthropic.claude-code-*") if base.is_dir() else []:
            mm = re.search(r"anthropic\.claude-code-(\d+\.\d+\.\d+)", p.name)
            if mm and (best is None or vtuple(mm.group(1)) > vtuple(best)):
                best = mm.group(1)
    if best:
        out["vscode"] = best
    roots = [desktop_dir(ctx) / "claude-code"]
    if ctx.system == "windows":
        roots += list((ctx.localappdata() / "Claude-Data").glob("*/claude-code"))
    best = None
    for root in roots:
        for p in root.iterdir() if root.is_dir() else []:
            if re.fullmatch(r"\d+\.\d+\.\d+", p.name) and (best is None or vtuple(p.name) > vtuple(best)):
                best = p.name
    if best:
        out["desktop_code"] = best
    if ctx.system == "windows":
        code, text = run(ctx, ["powershell", "-NoProfile", "-Command",
                               "(Get-AppxPackage -Name Claude | Select-Object -First 1).Version"], timeout=40)
        if code == 0 and re.search(r"\d+\.\d+", text):
            out["desktop_app"] = text.strip()
        else:
            apps = sorted((ctx.localappdata() / "AnthropicClaude").glob("app-*"), key=lambda p: vtuple(p.name))
            if apps:
                out["desktop_app"] = apps[-1].name[4:]
    elif ctx.system == "mac":
        import plistlib  # noqa: PLC0415
        try:
            with open("/Applications/Claude.app/Contents/Info.plist", "rb") as f:
                out["desktop_app"] = plistlib.load(f).get("CFBundleShortVersionString", "")
        except (OSError, ValueError):
            pass
    return out


def repo_root(ctx: Ctx, path) -> Path | None:
    out = git(ctx, ["-C", str(path), "rev-parse", "--show-toplevel"]).strip()
    return Path(out) if out else None


def discover_repos(ctx: Ctx, extra: list[str], include_projects: bool, deny) -> list[Path]:
    """The current repository, --repo paths, repos listed in config.json, and (optional) every git repository Claude
    Code has worked in (~/.claude.json projects), without worktrees under .claude/worktrees and without denied paths."""
    seen: dict[str, Path] = {}

    def add(path, always=False) -> None:
        p = Path(path)
        if not p.exists() or covered(ctx, deny, p):
            return
        root = repo_root(ctx, p)
        if not root:
            return
        key = str(root).lower() if ctx.system == "windows" else str(root)
        if not always and "/.claude/worktrees/" in str(root).replace("\\", "/"):
            return
        seen.setdefault(key, root)

    cur = repo_root(ctx, ctx.cwd)
    if cur:
        add(cur, always=True)
    for p in extra:
        add(Path(p).expanduser(), always=True)
    cfg = read_json(ctx.state / "config.json")
    for p in (cfg.get("repos") if isinstance(cfg, dict) else None) or []:
        add(Path(str(p)).expanduser())
    if include_projects:
        for _label, _d, gjson in profiles(ctx):
            data = read_json(gjson)
            for p in ((data.get("projects") if isinstance(data, dict) else None) or {}):
                add(p)
    return list(seen.values())


def mcp_servers(ctx: Ctx, repo) -> list[dict]:
    out = []

    def add(scope, origin, name, cfg, tracked=False):
        if not isinstance(cfg, dict):
            return
        out.append({"scope": scope, "origin": origin, "name": str(name),
                    "type": str(cfg.get("type") or ("http" if cfg.get("url") else "stdio")),
                    "command": str(cfg.get("command") or ""), "args": [str(a) for a in cfg.get("args") or []],
                    "url": str(cfg.get("url") or ""),
                    "env": cfg.get("env") if isinstance(cfg.get("env"), dict) else {},
                    "headers": cfg.get("headers") if isinstance(cfg.get("headers"), dict) else {},
                    "tracked": tracked})

    for label, _pdir, gjson in profiles(ctx):
        data = read_json(gjson)
        if not isinstance(data, dict):
            continue
        for n, c in (data.get("mcpServers") or {}).items():
            add(f"user ({label})", "~/.claude.json", n, c)
        for ppath, pc in (data.get("projects") or {}).items():
            if isinstance(pc, dict):
                for n, c in (pc.get("mcpServers") or {}).items():
                    add(f"local ({label})", ctx.red(ppath), n, c)
    if repo:
        data = read_json(Path(repo) / ".mcp.json")
        if isinstance(data, dict):
            tracked = bool(git(ctx, ["-C", str(repo), "ls-files", "--error-unmatch", ".mcp.json"]).strip())
            for n, c in (data.get("mcpServers") or {}).items():
                add("project", ".mcp.json", n, c, tracked)
    data = read_json(managed_dir(ctx) / "managed-mcp.json")
    if isinstance(data, dict):
        for n, c in (data.get("mcpServers") or {}).items():
            add("managed", "managed-mcp.json", n, c)
    data = read_json(desktop_dir(ctx) / "claude_desktop_config.json")
    if isinstance(data, dict):
        for n, c in (data.get("mcpServers") or {}).items():
            add("desktop", "claude_desktop_config.json", n, c)
    return out


def runner_package(command: str, args: list[str]):
    """(ecosystem, package, version or None, spec) when an MCP server is started by a package runner."""
    exe = re.sub(r"\.(exe|cmd|bat|ps1)$", "", Path(str(command).replace("\\", "/")).name.lower())
    a = list(args)
    if exe == "cmd" and a[:1] and a[0].lower() == "/c" and len(a) > 1:
        exe, a = re.sub(r"\.(exe|cmd|bat)$", "", Path(a[1].replace("\\", "/")).name.lower()), a[2:]
    if exe in ("pnpm", "yarn") and a[:1] == ["dlx"]:
        exe, a = "npx", a[1:]
    if exe == "uv" and a[:2] == ["tool", "run"]:
        exe, a = "uvx", a[2:]
    if exe == "pipx" and a[:1] == ["run"]:
        exe, a = "uvx", a[1:]
    spec = None
    if exe in ("npx", "bunx"):
        i = 0
        while i < len(a):
            x = a[i]
            if x in ("-p", "--package"):
                spec = a[i + 1] if i + 1 < len(a) else None
                break
            if x.startswith("--package="):
                spec = x.split("=", 1)[1]
                break
            if x.startswith("-"):
                i += 1
                continue
            spec = x
            break
        if not spec:
            return None
        m = re.match(r"^(@[^/@\s]+/[^@\s]+|[^@\s]+)(?:@(\S+))?$", spec)
        if not m:
            return None
        ver = m.group(2)
        return ("npm", m.group(1), ver if ver and re.match(r"^\d", ver) else None, spec)
    if exe == "uvx":
        i = 0
        while i < len(a):
            x = a[i]
            if x == "--from":
                spec = a[i + 1] if i + 1 < len(a) else None
                break
            if x.startswith("--from="):
                spec = x.split("=", 1)[1]
                break
            if x in ("--python", "-p", "--with", "--index-url", "--index", "--extra-index-url"):
                i += 2
                continue
            if x.startswith("-"):
                i += 1
                continue
            spec = x
            break
        if not spec:
            return None
        m = re.match(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?(?:\s*(==|@)\s*([0-9][^\s;,]*))?", spec)
        if not m:
            return None
        return ("PyPI", m.group(1), m.group(3), spec)
    return None


def literal_secret(name: str, value) -> bool:
    """A written-out credential: a value shaped like a known token, or a credential-like name holding a literal
    value. A `${VAR}` reference, even after `Bearer `, is fine."""
    v = str(value or "")
    if not v:
        return False
    if any(rx.search(v) for rx in SECRET_SHAPES):
        return True
    if not SECRET_NAME.search(str(name)):
        return False
    if VAR_REFERENCE.match(v) or v.strip().lower() in ("true", "false", "1", "0", "none", "null", "yes", "no"):
        return False
    rest = re.sub(r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%", "", v)
    rest = re.sub(r"(?i)^\s*(bearer|basic|token)\s*", "", rest).strip()
    return len(rest) >= 8


def plugin_inventory(pdir: Path):
    plugs: dict = {}
    inst = read_json(pdir / "plugins" / "installed_plugins.json")
    for key, entries in ((inst.get("plugins") if isinstance(inst, dict) else None) or {}).items():
        for e in entries if isinstance(entries, list) else [entries]:
            if isinstance(e, dict):
                plugs[str(key)] = {"version": str(e.get("version") or ""), "path": str(e.get("installPath") or "")}
    markets: dict = {}
    km = read_json(pdir / "plugins" / "known_marketplaces.json")
    for name, m in (km.items() if isinstance(km, dict) else []):
        src = (m or {}).get("source") if isinstance(m, dict) else {}
        src = src if isinstance(src, dict) else {}
        markets[str(name)] = " ".join(str(src.get(k)) for k in ("source", "repo", "url", "path") if src.get(k))
    return plugs, markets


def hook_commands(layers: list[Layer], plugs: dict) -> list[dict]:
    out = []

    def collect(hooks, scope):
        if not isinstance(hooks, dict):
            return
        for event, groups in hooks.items():
            for g in groups if isinstance(groups, list) else []:
                for h in (g.get("hooks") if isinstance(g, dict) else None) or []:
                    if isinstance(h, dict) and h.get("command"):
                        out.append({"scope": scope, "event": str(event), "command": str(h["command"])})

    for layer in layers:
        collect(layer.data.get("hooks"), f"{layer.scope} settings")
    for name, info in plugs.items():
        base = Path(info.get("path") or "")
        for candidate in (base / "hooks" / "hooks.json", base / ".claude-plugin" / "plugin.json"):
            data = read_json(candidate) if info.get("path") else None
            if isinstance(data, dict):
                collect(data.get("hooks"), f"plugin {name}")
    return out


def file_hashes(paths: dict) -> dict:
    out = {}
    for name, p in paths.items():
        text = read_text(p, limit=5_000_000)
        if text is not None:
            out[name] = sha(text)
    return out


def skills_and_tasks(ctx: Ctx, pdir: Path, repo):
    skills = {}
    sdir = pdir / "skills"
    for d in sdir.iterdir() if sdir.is_dir() else []:
        if d.is_dir() and d.name != "synced" and (d / "SKILL.md").is_file():
            skills["user:" + d.name] = d / "SKILL.md"
    for f in (sdir / "synced").glob("*/*/SKILL.md") if (sdir / "synced").is_dir() else []:
        skills["claude.ai:" + f.parent.name] = f
    if repo:
        for f in (Path(repo) / ".claude" / "skills").glob("*/SKILL.md"):
            skills["project:" + f.parent.name] = f
    tasks = {f.parent.name: f for f in (pdir / "scheduled-tasks").glob("*/SKILL.md")}
    return skills, tasks


def desktop_extensions(ctx: Ctx) -> dict:
    out = {}
    base = desktop_dir(ctx) / "Claude Extensions"
    for d in base.iterdir() if base.is_dir() else []:
        man = read_json(d / "manifest.json")
        if isinstance(man, dict):
            out[str(man.get("name") or d.name)] = str(man.get("version") or "")
    return out


# ---------------------------------------------------------------- identity scan

def text_candidate(rel: str) -> bool:
    low = rel.replace("\\", "/")
    if any(low.startswith(d) or ("/" + d) in low for d in SKIP_DIRS):
        return False
    name = low.rsplit("/", 1)[-1].lower()
    if LOCK_FILES.search(name):  # generated, and full of third-party maintainers' addresses
        return False
    stem, dot, ext = name.partition(".")
    if dot and ("." + name.rsplit(".", 1)[-1]) in TEXT_EXT:
        return True
    return stem in NAMED_TEXT or name.startswith((".env", "license", "licence", "copying", "notice"))


class Scanner:
    def __init__(self, ctx: Ctx):
        ident = ctx.identity
        self.ctx = ctx
        self.ident = ident
        self.emails = sorted(ident.emails, key=len, reverse=True)
        self.name_rx = [name_regex(n) for n in sorted(ident.names, key=len, reverse=True)]
        self.part_rx = [re.compile(r"(?i)(?<!\w)" + re.escape(p) + r"(?!\w)") for p in ident.parts]
        self.user_rx = username_path_rules(ident.username) if ident.username else []
        self.bare_rx = re.compile(r"(?i)(?<![A-Za-z0-9])" + re.escape(ident.username) + r"(?![A-Za-z0-9])") \
            if ident.username and ident.bare_username else None
        self.quick = [e for e in self.emails] + [n.lower() for n in ident.names] + [p.lower() for p in ident.parts]
        if ident.username:
            self.quick.append(ident.username.lower())

    def other_emails(self, line: str) -> list[tuple[str, int]]:
        out = []
        for m in EMAIL_RE.finditer(line):
            e = m.group(0)
            if benign_email(e) or e.lower() in self.ident.emails or line[max(0, m.start() - 3):m.start()].endswith("//"):
                continue  # a URL's user part (a Sentry DSN key, for example) is not an address
            out.append((e, m.start()))
        return out

    def context(self, line: str, at: int) -> str:
        """The line around position `at`, redacted: long lines show the part with the match, not only their start."""
        start = max(0, at - 60)
        part = line[start:at + 110].strip()
        return ("..." if start else "") + self.ctx.red(part)[:170]

    def scan(self, text: str, display: str, cls: str, code: bool = False, others_too: bool = True,
             path: Path | None = None) -> list[dict]:
        low = text.lower()
        if "@" not in low and "companyname" not in low and not any(q in low for q in self.quick):
            return []
        items = []
        shown = "/" + display.replace("\\", "/")
        own_code = "/.claude/skills/claude-security-audit/" in shown or shown.endswith("/tests/test_security_audit.py") \
            or (path is not None and is_within(path, SELF_DIR))
        file_http = code and not own_code and bool(HTTP_USE.search(text))
        name = display.rsplit("/", 1)[-1].lower()
        doc_like = Path(name).suffix in DOC_EXT
        for n, line in enumerate(text.splitlines(), 1):
            if len(line) > 6000:
                line = line[:6000]
            ll = line.lower()
            found: dict[str, int] = {}  # kind -> where in the line it was found
            hits = [ll.find(e) for e in self.emails if e in ll]
            has_owner_email = bool(hits)
            if hits:
                found["owner-email"] = min(hits)
            m = next((m for m in (rx.search(line) for rx in self.name_rx) if m), None)
            if m:
                found["owner-name"] = m.start()
            else:
                m = next((m for m in (rx.search(line) for rx in self.part_rx) if m), None)
                if m:
                    found["owner-name-part"] = m.start()
            if cls != "config":
                m = next((m for m in (rx.search(line) for rx, _form in self.user_rx) if m), None)
                stripped = line
                for rx, _form in self.user_rx:
                    stripped = rx.sub(lambda mm: " " * len(mm.group(0)), stripped)  # keep positions
                if m:
                    found["username-path"] = m.start()
                b = self.bare_rx.search(stripped) if self.bare_rx and not has_owner_email else None
                if b:
                    found["username"] = b.start()
            others = self.other_emails(line)
            if others and others_too and cls in ("published", "instructions"):
                found["other-email"] = others[0][1]
            hint = CONTACT_HINT.search(line)
            if (has_owner_email or others) and hint and not own_code:
                found["contact-email"] = hint.start()
            g = GIT_IDENTITY_READ.search(line) if file_http else None
            if g:
                found["contact-from-git"] = g.start()
            unity = re.match(r"\s*(organizationId|cloudProjectId):\s*\S", line) if name == "projectsettings.asset" else None
            if unity:
                found["unity-org"] = 0
            for kind, at in found.items():
                replace = cls in ("published", "instructions") and (
                    kind in ("owner-email", "owner-name", "username-path")
                    or (kind == "contact-email" and has_owner_email)
                    or (kind == "username" and (doc_like or cls == "instructions")))
                context = f"{unity.group(1)}: [id]" if kind == "unity-org" else self.context(line, at)
                items.append({"file": display, "line": n, "kind": kind, "class": cls,
                              "action": "replace" if replace else "report", "context": context})
        return items


def is_within(path: Path, parent: Path) -> bool:
    try:
        Path(path).resolve().relative_to(parent)
        return True
    except (ValueError, OSError):
        return False


def repo_files(ctx: Ctx, repo: Path) -> tuple[list[str], set[str]]:
    out = git(ctx, ["-C", str(repo), "ls-files", "-z", "-co", "--exclude-standard"], timeout=90)
    files = [f for f in out.split("\0") if f][:25000]
    status = git(ctx, ["-C", str(repo), "status", "--porcelain=v1", "-z", "--untracked-files=all"], timeout=90)
    dirty = set()
    for entry in status.split("\0"):
        if len(entry) > 3:
            dirty.add(entry[3:])
    return files, dirty


def keep_patterns(ctx: Ctx, repos: list[Path]) -> tuple[set[str], list[str]]:
    """Skill names and file globs whose identity is kept on purpose: skills excluded from the public skills library
    (skills/sync.yaml `exclude`), plus `keep` in the state folder's config.json."""
    names: set[str] = set()
    for repo in repos:
        text = read_text(repo / "skills" / "sync.yaml") or ""
        block = re.search(r"(?ms)^exclude:\s*\n((?:\s+-.*\n?)+)", text)
        for m in re.finditer(r"^\s+-\s*([A-Za-z0-9_.-]+)", block.group(1) if block else "", re.M):
            names.add(m.group(1))
    cfg = read_json(ctx.state / "config.json")
    globs = [str(g) for g in ((cfg.get("keep") if isinstance(cfg, dict) else None) or [])]
    return names, globs


def local_instruction_files(ctx: Ctx, kept_names: set[str], kept_globs: list[str]) -> list[tuple[Path, str, str]]:
    """(path, display, class) for Claude's own instruction and memory files, outside any repository."""
    out = []
    patterns = ("CLAUDE.md", "CLAUDE.local.md", "rules/**/*", "agents/**/*", "commands/**/*", "output-styles/**/*",
                "skills/**/*", "scheduled-tasks/**/*", "projects/*/memory/**/*")
    for _label, pdir, _gjson in profiles(ctx):
        for pattern in patterns:
            for p in pdir.glob(pattern):
                if not p.is_file() or not text_candidate(p.name if "." in p.name else p.name + ".md"):
                    continue
                rel = p.relative_to(pdir).as_posix()
                display = ctx.red(str(p)).replace("\\", "/")
                cls = "instructions"
                parts = rel.split("/")
                if rel.startswith("skills/synced/"):
                    cls = "kept"
                elif parts[0] == "skills" and len(parts) > 1 and parts[1] in kept_names:
                    cls = "kept"
                elif any(Path(rel).match(g) or Path(display).match(g) for g in kept_globs):
                    cls = "kept"
                out.append((p, display, cls))
    return out


def config_files(ctx: Ctx, repos: list[Path]) -> list[tuple[str, str]]:
    """(display, text) for configuration files, scanned for email addresses only (never changed)."""
    out = []
    paths = [managed_dir(ctx) / "managed-settings.json", desktop_dir(ctx) / "claude_desktop_config.json"]
    for _label, pdir, gjson in profiles(ctx):
        paths += [pdir / "settings.json", pdir / "settings.local.json"]
        data = read_json(gjson)
        if isinstance(data, dict):  # only the MCP parts: the rest holds the account itself
            subset = {"mcpServers": data.get("mcpServers") or {},
                      "projects": {"<project>": (v or {}).get("mcpServers") for v in (data.get("projects") or {}).values()
                                   if isinstance(v, dict) and v.get("mcpServers")}}
            out.append((ctx.red(str(gjson)).replace("\\", "/") + " (MCP servers)", json.dumps(subset, indent=1)))
    for repo in repos:
        paths += [repo / ".claude" / "settings.local.json"]
    for p in paths:
        text = read_text(p)
        if text is not None:
            out.append((ctx.red(str(p)).replace("\\", "/"), text))
    return out


def same_path(ctx: Ctx, a, b) -> bool:
    norm = lambda p: os.path.normcase(os.path.abspath(str(p)))  # noqa: E731
    return norm(a) == norm(b)


def repo_label(ctx: Ctx, root: Path) -> str:
    """The repository's name: the main checkout's folder, also for a linked worktree."""
    common = git(ctx, ["-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"]).strip()
    if common and Path(common).name == ".git":
        return Path(common).parent.name
    return root.name


def identity_scan(ctx: Ctx, repos: list[Path], deny) -> dict:
    sc = Scanner(ctx)
    items: list[dict] = []
    stats = collections.Counter()
    remote_repos = set()
    kept_names, kept_globs = keep_patterns(ctx, repos)
    host_files: set[str] = set()
    current = repo_root(ctx, ctx.cwd)
    for index, repo in enumerate(repos):
        label = repo_label(ctx, repo)
        files, _dirty = repo_files(ctx, repo)
        has_remote = bool(git(ctx, ["-C", str(repo), "remote"]).strip())
        here = current is not None and same_path(ctx, repo, current)
        checkout = ctx.red(str(repo)).replace("\\", "/")
        for rel in files:
            if not text_candidate(rel):
                continue
            p = repo / rel
            if covered(ctx, deny, p):
                stats["denied"] += 1
                continue
            text = read_text(p, limit=1_500_000)
            if text is None:
                continue
            stats["files"] += 1
            display = f"{label}/{rel}"
            # Other people's addresses only in the current repository: elsewhere they are mostly upstream projects'.
            found = sc.scan(text, display, "published", code=Path(rel).suffix.lower() in CODE_EXT,
                            others_too=here, path=p)
            for item in found:
                item["checkout"], item["current"] = checkout, here
            if found and has_remote:
                remote_repos.add(label)
            items += found
            if ctx.identity.host and ctx.identity.host.lower() in (rel + "\n" + text).lower():
                host_files.add(ctx.red(display))
    for p, display, cls in local_instruction_files(ctx, kept_names, kept_globs):
        if covered(ctx, deny, p):
            stats["denied"] += 1
            continue
        text = read_text(p, limit=1_500_000)
        if text is None:
            continue
        stats["files"] += 1
        items += sc.scan(text, display, cls, code=p.suffix.lower() in CODE_EXT, path=p)
    for display, text in config_files(ctx, repos):
        stats["files"] += 1
        items += [i for i in sc.scan(text, display, "config") if i["kind"] in ("owner-email", "other-email")]
    unique, seen = [], set()
    for i in items:  # a worktree and its main checkout hold the same files
        key = (i["file"], i["line"], i["kind"], i["context"])
        if key not in seen:
            seen.add(key)
            unique.append(i)
    return {"items": unique, "stats": dict(stats), "remote_repos": sorted(remote_repos),
            "host_files": sorted(host_files)}


def git_history_identity(ctx: Ctx, repos: list[Path]) -> dict:
    out = {"unpushed": 0, "pushed": 0, "session_links": 0}
    emails = ctx.identity.emails
    for i, repo in enumerate(repos):
        log = git(ctx, ["-C", str(repo), "log", "--branches", "--not", "--remotes", "--format=%ae%x1f%ce%x1f%B%x1e"],
                  timeout=60)
        out["unpushed"] += sum(1 for c in log.split("\x1e") if any(e in c.lower() for e in emails))
        if i == 0:  # the current repository: already published history
            log = git(ctx, ["-C", str(repo), "log", "--remotes", "--format=%ae%x1f%ce%x1f%(trailers:only)%x1e"],
                      timeout=90)
            out["pushed"] += sum(1 for c in log.split("\x1e") if any(e in c.lower() for e in emails))
            out["session_links"] += log.count("Claude-Session:")
    return out


# ---------------------------------------------------------------- scrub (the only thing this script changes)

def scrub_text(ctx: Ctx, text: str, filename: str, repo_name: str,
               bare_ok: bool = False) -> tuple[str, collections.Counter]:
    """Placeholders for the owner's identity. `bare_ok` also replaces the user name on its own (prose and Claude's
    instruction files only: in code it may be a value something depends on)."""
    ident = ctx.identity
    counts = collections.Counter()
    for e in sorted(ident.emails, key=len, reverse=True):
        text, k = re.subn(re.escape(e), PLACEHOLDER_EMAIL, text, flags=re.I)
        counts["owner-email"] += k
    upper = filename.upper()
    if filename.lower() == "projectsettings.asset":
        def company(m):
            if any(name_regex(n).search(m.group(2)) for n in ident.names):
                counts["owner-name"] += 1
                return m.group(1) + "DefaultCompany"
            return m.group(0)
        text = re.sub(r"(?m)^(\s*companyName:\s*)(.+)$", company, text)
    name_repl = f"The {repo_name} Authors" if upper.startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")) else \
        PLACEHOLDER_NAME
    for n in sorted(ident.names, key=len, reverse=True):
        text, k = name_regex(n).subn(name_repl, text)
        counts["owner-name"] += k
    if ident.username:
        for rx, form in username_path_rules(ident.username):
            text, k = rx.subn("%USERPROFILE%" if form == "win" else "~", text)
            counts["username-path"] += k
        if bare_ok and ident.bare_username:
            placeholder = "%USERNAME%" if ctx.system == "windows" else "$USER"
            text, k = re.subn(r"(?i)(?<![A-Za-z0-9%$])" + re.escape(ident.username) + r"(?![A-Za-z0-9%])",
                              placeholder, text)
            counts["username"] += k
    return text, counts


def write_preserving(path: Path, text: str) -> None:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    data = text.encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)


def scrub(ctx: Ctx, repos: list[Path], local: bool, published: bool, apply: bool, include_dirty: bool) -> dict:
    deny = all_deny(ctx)
    results = []
    sc = Scanner(ctx)

    def handle(path: Path, display: str, cls: str, repo_name: str, dirty: bool):
        if covered(ctx, deny, path):
            return
        try:
            raw = path.read_bytes()
            original = raw.decode("utf-8-sig")
        except (OSError, UnicodeDecodeError):
            if sc.scan(path.read_text(encoding="utf-8", errors="replace"), display, cls):
                results.append({"file": display, "class": cls, "status": "skipped: not UTF-8, fix by hand"})
            return
        if b"\x00" in raw[:8192]:
            return
        bare_ok = cls == "instructions" or path.suffix.lower() in DOC_EXT
        new, counts = scrub_text(ctx, original, path.name, repo_name, bare_ok=bare_ok)
        counts = {k: v for k, v in counts.items() if v}
        if not counts:
            return
        if cls == "kept":
            results.append({"file": display, "class": cls, "counts": counts, "status": "kept on purpose"})
            return
        if dirty and not include_dirty:
            results.append({"file": display, "class": cls, "counts": counts,
                            "status": "skipped: the file has uncommitted changes"})
            return
        if apply:
            write_preserving(path, new)
        results.append({"file": display, "class": cls, "counts": counts, "status": "changed" if apply else "would change"})

    if published:
        for repo in repos:
            label = repo_label(ctx, repo)
            files, dirty = repo_files(ctx, repo)
            for rel in files:
                if text_candidate(rel) and (repo / rel).is_file() and not is_within(repo / rel, SELF_DIR):
                    handle(repo / rel, f"{label}/{rel}", "published", label, rel in dirty)
    if local:
        kept_names, kept_globs = keep_patterns(ctx, repos)
        for p, display, cls in local_instruction_files(ctx, kept_names, kept_globs):
            handle(p, display, cls, "", False)
    notes = []
    if any(r.get("counts", {}).get("owner-email") for r in results):
        notes.append("Where an email was a contact for a web API (User-Agent, mailto=, email=), make the code read "
                     "CONTACT_EMAIL from the environment at run time with you@example.com as the default.")
    return {"applied": apply, "files": results, "notes": notes}


def all_deny(ctx: Ctx) -> list[tuple[str, str]]:
    deny = []
    for _label, pdir, _g in profiles(ctx):
        deny += rules(load_layers(ctx, pdir, None), "deny")
    return deny


# ---------------------------------------------------------------- online sources

def fetch_text(ctx: Ctx, url: str, label: str):
    if ctx.offline:
        return None
    try:
        return http_get(url).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError) as e:
        ctx.errors.append(f"{label}: {getattr(e, 'reason', e)}")
        return None


def clean_md(text: str, limit: int = 420) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def parse_settings_reference(md: str) -> dict:
    rows = re.findall(r"^\| \[`([^`]+)`\]\(#[^)]*\) \| (.*?) \| ([^|]+?) \| ([^|]+?) \|\s*$", md or "", re.M)
    return {k: {"category": c.strip(), "desc": clean_md(d)} for k, d, c, _scope in rows}


def parse_env_vars(md: str) -> dict:
    out = {}
    for m in re.finditer(r"^\| `([A-Z][A-Z0-9_]+)` \| (.*)\|\s*$", md or "", re.M):
        out[m.group(1)] = {"desc": clean_md(m.group(2))}
    return out


def docs_diff(prev: dict, cur: dict, interesting: set[str]) -> dict:
    new = {k: v for k, v in cur.items() if k not in prev}
    removed = sorted(k for k in prev if k not in cur)
    changed = {k: v for k, v in cur.items() if k in prev and prev[k] != sha(v.get("desc", "")) and k in interesting}
    return {"new": new, "removed": removed, "changed": changed}


def parse_changelog(md: str) -> list[tuple[str, list[str]]]:
    out = []
    for m in re.finditer(r"^## (\d+\.\d+\.\d+)\s*$(.*?)(?=^## \d|\Z)", md or "", re.M | re.S):
        lines = [re.sub(r"^\s*[-*]\s+", "", ln).strip() for ln in m.group(2).splitlines() if ln.strip().startswith(("-", "*"))]
        out.append((m.group(1), lines))
    return out


def changelog_kind(line: str):
    if CHANGELOG_SECURITY.search(line):
        return "security"
    if CHANGELOG_NEW_SETTING.search(line):
        return "new-setting"
    if CHANGELOG_PRIVACY.search(line):
        return "privacy"
    if CHANGELOG_POLICY.search(line):
        return "policy"
    return None


def changelog_since(entries, since: str, until: str | None = None) -> list[dict]:
    """Relevant lines of releases after `since`: security fixes first, then new settings, privacy, permissions."""
    out = []
    for ver, lines in entries:
        if vtuple(ver) <= vtuple(since) or (until and vtuple(ver) > vtuple(until)):
            continue
        for line in lines:
            kind = changelog_kind(line)
            if kind:
                out.append({"version": ver, "kind": kind, "text": clean_md(line, 300), "security": kind == "security"})
    out.sort(key=lambda e: (CHANGELOG_ORDER.index(e["kind"]), tuple(-n for n in vtuple(e["version"]))))
    return out


OSV_SEVERITY = {"CRITICAL": "critical", "HIGH": "high", "MODERATE": "medium", "MEDIUM": "medium", "LOW": "low"}


def osv_check(ctx: Ctx, packages: list[dict]) -> list[dict]:
    """OSV advisories affecting the given (ecosystem, name, version) packages."""
    if ctx.offline or not packages:
        return []
    queries = [{"package": {"ecosystem": p["ecosystem"], "name": p["name"]}, "version": p["version"]} for p in packages]
    try:
        batch = http_post_json(OSV_BATCH, {"queries": queries})
    except (urllib.error.URLError, OSError, ValueError) as e:
        ctx.errors.append(f"OSV: {getattr(e, 'reason', e)}")
        return []
    found = []
    details: dict = {}
    for pkg, res in zip(packages, batch.get("results") or []):
        for v in (res or {}).get("vulns") or []:
            vid = v.get("id")
            if not vid:
                continue
            if vid not in details and len(details) < 30:
                try:
                    details[vid] = json.loads(http_get(OSV_VULN + urllib.parse.quote(vid)).decode("utf-8"))
                except (urllib.error.URLError, OSError, ValueError):
                    details[vid] = {}
            found.append(osv_finding(pkg, vid, details.get(vid) or {}))
    return found


def osv_finding(pkg: dict, vid: str, d: dict) -> dict:
    sev = OSV_SEVERITY.get(str((d.get("database_specific") or {}).get("severity") or "").upper(), "medium")
    fixed = []
    for aff in d.get("affected") or []:
        if (aff.get("package") or {}).get("name") != pkg["name"]:
            continue
        for rng in aff.get("ranges") or []:
            for ev in rng.get("events") or []:
                if ev.get("fixed"):
                    fixed.append(ev["fixed"])
    aliases = [a for a in d.get("aliases") or [] if a.startswith("CVE-")]
    return {"id": vid, "aliases": aliases, "package": pkg["name"], "ecosystem": pkg["ecosystem"],
            "installed": pkg["version"], "label": pkg.get("label", pkg["name"]), "severity": sev,
            "summary": clean_md(d.get("summary") or d.get("details") or "", 220),
            "fixed": sorted(set(fixed), key=vtuple)[-1:] if fixed else [], "published": str(d.get("published") or "")[:10]}


def uv_tools(ctx: Ctx) -> list[dict]:
    code, out = run(ctx, ["uv", "tool", "list"], timeout=30)
    tools = []
    for line in out.splitlines() if code == 0 else []:
        m = re.match(r"^([A-Za-z0-9._-]+) v(\d[^\s]*)", line.strip())
        if m:
            tools.append({"ecosystem": "PyPI", "name": m.group(1), "version": m.group(2),
                          "label": f"{m.group(1)} (uv tool)"})
    return tools


# ---------------------------------------------------------------- checks

def check_updates(ctx, vers: dict, latest, entries, nonessential: bool) -> list[dict]:
    out = []
    labels = {"cli": "Claude Code CLI", "vscode": "the VS Code extension", "desktop_code": "Claude Desktop's Claude Code"}
    cli_fix = {"winget": "`winget upgrade Anthropic.ClaudeCode`", "npm": "`npm install -g @anthropic-ai/claude-code`",
               "native": "`claude update`"}.get(vers.get("cli_via", ""), "`claude update` (or the package manager "
                                                                         "that installed it)")
    fixes = {"cli": cli_fix, "vscode": "update the Claude Code extension in VS Code",
             "desktop_code": "restart Claude Desktop (it updates its own copy) or update the app"}
    for key, label in labels.items():
        v = vers.get(key)
        if not v or not latest or vtuple(v) >= vtuple(latest):
            continue
        between = [e for e in changelog_since(entries, v, latest) if e["security"]] if entries else []
        n = sum(1 for ver, _ in entries if vtuple(v) < vtuple(ver) <= vtuple(latest)) if entries else 0
        detail = f"{v} installed, {latest} available" + (f" ({n} releases)." if n else ".")
        if between:
            detail += f" {len(between)} changelog lines since then mention security fixes, for example: " + \
                      between[0]["text"]
        out.append(finding("UPDATE-" + key.upper().replace("_", "-"), "medium" if between else "low", "updates",
                           f"{label[0].upper() + label[1:]} is behind", detail, fixes[key]))
    if nonessential and any(vers.get(k) for k in labels):
        out.append(finding("AUTOUPDATE-OFF", "info", "updates", "Auto-updates are off",
                           "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC (or DISABLE_AUTOUPDATER) stops them, so keep this "
                           "audit running: it compares your versions with the latest release every time."))
    return out


def check_data_sharing(ctx, layers, vers) -> list[dict]:
    out = []
    env = lambda name: env_value(ctx, layers, name)[0]  # noqa: E731
    nonessential = env("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC") is not None
    if not (nonessential or truthy(env("DISABLE_FEEDBACK_COMMAND")) or truthy(env("DISABLE_BUG_COMMAND"))):
        out.append(finding("FEEDBACK-UPLOAD", "medium", "data-sharing",
                           "/feedback, /bug and /share can upload whole conversations",
                           "They send the conversation, code included, to Anthropic, which keeps feedback for 5 years.",
                           'Add "DISABLE_FEEDBACK_COMMAND": "1" to the env block of ~/.claude/settings.json.',
                           DOC + "data-usage"))
    drafts, _ = get(layers, "feedbackDrafts")
    if not nonessential and str(drafts or "").lower() != "off":
        out.append(finding("FEEDBACK-DRAFTS", "low", "data-sharing", "Claude can draft feedback reports for you to send",
                           "A draft can include the transcript if you tick it on the review screen.",
                           '"feedbackDrafts": "off" in ~/.claude/settings.json.', DOC + "settings-reference"))
    if not (nonessential or truthy(env("DISABLE_ERROR_REPORTING"))):
        out.append(finding("ERROR-REPORTS", "low", "data-sharing", "Error reports go to a third-party error tracker",
                           "Claude Code redacts secrets, paths and email addresses first. It is on for Pro, Max and Ultra "
                           "sign-ins and costs nothing to turn off.", '"DISABLE_ERROR_REPORTING": "1"',
                           DOC + "data-usage"))
    telemetry_off = nonessential or truthy(env("DISABLE_TELEMETRY")) or truthy(env("DO_NOT_TRACK"))
    if not telemetry_off:
        out.append(finding("TELEMETRY", "info", "data-sharing", "Usage metrics are on",
                           "Metrics never include code, prompts or file paths. Turning them off also stops feature-flag "
                           "fetching, which turns off Remote Control and auto mode's server-side review.",
                           'Optional: "DISABLE_TELEMETRY": "1", if you accept those losses.', DOC + "data-usage"))
    flags_off = telemetry_off or truthy(env("CLAUDE_CODE_DISABLE_FEATURE_FLAGS")) or truthy(env("DISABLE_GROWTHBOOK"))
    affected = [f"{k} {v}" for k, v in vers.items() if k in ("cli", "vscode", "desktop_code") and
                re.match(r"^\d+\.\d+\.\d+$", str(v)) and vtuple(v) >= (2, 1, 319)]
    if flags_off and affected and env("CLAUDE_CODE_AUTO_MODE_SERVER") is None:
        out.append(finding("AUTO-MODE-SERVER", "info", "data-sharing",
                           "Auto mode asks or denies more while telemetry is off",
                           "Since 2.1.319, with telemetry or feature flags off, calls auto mode's server-side check "
                           "can't review are asked about or denied, with no fallback to the built-in classifier. "
                           f"Applies to: {', '.join(affected)}; older installs follow once updated.",
                           'If that gets in the way: "CLAUDE_CODE_AUTO_MODE_SERVER": "0" uses Claude Code\'s own '
                           "classifier requests instead.", DOC + "env-vars"))
    if truthy(env("CLAUDE_CODE_ENABLE_TELEMETRY")):
        endpoint = env("OTEL_EXPORTER_OTLP_ENDPOINT") or env("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT") or \
            env("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT") or ""
        host = host_of(endpoint)
        detailed = truthy(env("OTEL_LOG_USER_PROMPTS")) or truthy(env("OTEL_LOG_TOOL_DETAILS"))
        if host and host not in LOCAL_HOSTS:
            out.append(finding("OTEL-REMOTE", "high" if detailed else "medium", "data-sharing",
                               f"OpenTelemetry events go to {host}",
                               "Every event carries your account email and IDs" +
                               (", and prompts or tool details are logged too." if detailed else "."),
                               "Send them to a local collector, or unset OTEL_LOG_USER_PROMPTS and OTEL_LOG_TOOL_DETAILS "
                               "and set OTEL_METRICS_INCLUDE_ACCOUNT_UUID=false.", DOC + "monitoring-usage"))
    disabled, _ = get(layers, "disableClaudeAiConnectors")
    if str(env("ENABLE_CLAUDEAI_MCP_SERVERS") or "").lower() not in ("0", "false") and disabled is not True:
        out.append(finding("CONNECTORS", "low", "data-sharing", "Claude Code loads your claude.ai connectors",
                           "Every session can call the connectors you added on claude.ai (mail, files, calendar, notes). "
                           "A prompt injection in a file or web page could make Claude read from them.",
                           'If you don\'t use them in Claude Code: "disableClaudeAiConnectors": true in '
                           "~/.claude/settings.json.", DOC + "settings-reference"))
    skip, _ = get(layers, "skipWebFetchPreflight")
    if skip is True:
        out.append(finding("WEBFETCH-PREFLIGHT", "info", "data-sharing", "WebFetch's domain safety check is off",
                           "It sends each hostname to Anthropic before fetching; the fetched page reaches the model "
                           "anyway, so skipping it saves little and loses a safety check.",
                           "Remove skipWebFetchPreflight unless Anthropic is unreachable from this machine."))
    return out


def check_retention(ctx, layers) -> list[dict]:
    out = []
    cp, _ = get(layers, "cleanupPeriodDays")
    days = int(cp) if isinstance(cp, (int, float)) and not isinstance(cp, bool) else 30
    if days > 14:
        out.append(finding("TRANSCRIPT-RETENTION", "low", "retention", f"Session transcripts are kept {days} days",
                           "~/.claude/projects holds every conversation in plain text: file contents, command output "
                           "and the system prompt, which includes your account email.",
                           '"cleanupPeriodDays": 14 (or 7) in ~/.claude/settings.json; older sessions leave /resume.',
                           DOC + "settings-reference"))
    dp, _ = get(layers, "desktopSessionCleanupPeriodDays")
    if dp is None:
        out.append(finding("DESKTOP-RETENTION", "medium", "retention",
                           "Transcripts of Claude Desktop and Cowork sessions are never deleted",
                           "Without desktopSessionCleanupPeriodDays, Claude Code keeps them at any age. A transcript goes "
                           "once it is older than both this value and cleanupPeriodDays.",
                           f'"desktopSessionCleanupPeriodDays": {min(days, 14)} in ~/.claude/settings.json, together '
                           f'with "cleanupPeriodDays": {min(days, 14)} (a transcript is deleted once it is older than both).',
                           DOC + "settings-reference"))
    return out


SECRET_CANDIDATES = [
    (".claude/.credentials.json", "Claude Code's sign-in tokens", "Read(~/.claude/.credentials.json)"),
    (".claude-local/.credentials.json", "profile B's sign-in tokens", "Read(~/.claude-local/.credentials.json)"),
    (".ssh", "SSH keys", "Read(~/.ssh/**)"),
    (".aws", "AWS credentials", "Read(~/.aws/**)"),
    (".azure", "Azure CLI tokens", "Read(~/.azure/**)"),
    (".config/gh", "the GitHub CLI token", "Read(~/.config/gh/**)"),
    (".config/gcloud", "Google Cloud credentials", "Read(~/.config/gcloud/**)"),
    ("AppData/Roaming/GitHub CLI", "the GitHub CLI token", "Read(~/AppData/Roaming/GitHub CLI/**)"),
    ("AppData/Roaming/gcloud", "Google Cloud credentials", "Read(~/AppData/Roaming/gcloud/**)"),
    (".git-credentials", "saved Git passwords", "Read(~/.git-credentials)"),
    (".npmrc", "npm tokens", "Read(~/.npmrc)"),
    (".pypirc", "PyPI tokens", "Read(~/.pypirc)"),
    (".docker/config.json", "Docker registry logins", "Read(~/.docker/config.json)"),
    (".kube", "Kubernetes credentials", "Read(~/.kube/**)"),
    (".netrc", "netrc passwords", "Read(~/.netrc)"),
    ("_netrc", "netrc passwords", "Read(~/_netrc)"),
    (".openclaw/.env", "OpenClaw's gateway key", "Read(~/.openclaw/.env)"),
]
GENERIC_SECRETS = [
    (".env files in every project", "zz/p/.env", "Read(//**/.env)"),
    (".env.* files in every project", "zz/p/.env.local", "Read(//**/.env.*)"),
    ("private key files", "zz/p/server.pem", "Read(//**/*.pem)"),
    ("per-project local settings, where this stack keeps its MCP bearer", "zz/p/.claude/settings.local.json",
     "Read(//**/.claude/settings.local.json)"),
]


def project_allow_rules(ctx, repos: list[Path], current) -> list[tuple[str, str]]:
    """Allow rules in the project settings of the other repositories Claude works in (the current one is a layer)."""
    out = []
    for repo in repos:
        if current is not None and same_path(ctx, repo, current):
            continue
        for rel in (".claude/settings.json", ".claude/settings.local.json"):
            data = read_json(repo / rel)
            perms = data.get("permissions") if isinstance(data, dict) else None
            for r in (perms.get("allow") if isinstance(perms, dict) else None) or []:
                if isinstance(r, str):
                    out.append((r, f"project settings, {ctx.red(str(repo / rel)).replace(chr(92), '/')}"))
    return out


def check_permissions(ctx, layers, global_json, extra_allow=()) -> list[dict]:
    out = []
    env = lambda name: env_value(ctx, layers, name)[0]  # noqa: E731
    deny = rules(layers, "deny")
    missing = []
    for rel, label, rule in SECRET_CANDIDATES:
        p = ctx.home / rel
        if p.exists() and not covered(ctx, deny, p if p.is_file() else p / "x"):
            missing.append((label, rule))
    if missing:
        out.append(finding("DENY-SECRETS", "high", "permissions",
                           f"Claude can read {len(missing)} credential files on this machine",
                           "\n".join(f"- {label}" for label, _ in missing) +
                           "\nAnything Claude reads goes into the conversation, which is sent to Anthropic.",
                           "Add to permissions.deny in ~/.claude/settings.json:\n" +
                           json.dumps(sorted({r for _, r in missing}), indent=2), DOC + "permissions"))
    root = "C:/" if ctx.system == "windows" else "/"
    gaps = []
    for label, test, rule in GENERIC_SECRETS:
        if not covered(ctx, deny, root + test):
            partial = relative_covers(deny, test.rsplit("/", 1)[-1])
            gaps.append((label + (" (only the current project is covered)" if partial else ""), rule))
    if gaps:
        out.append(finding("DENY-SECRET-PATTERNS", "medium", "permissions", "Secret file patterns are not denied everywhere",
                           "\n".join(f"- {label}" for label, _ in gaps) +
                           "\nDeny rules stop Claude's file tools and shell commands that name the file, not a script "
                           "that opens it, and `.env.*` also hides `.env.example` files.",
                           "Add to permissions.deny in ~/.claude/settings.json:\n" + json.dumps([r for _, r in gaps], indent=2),
                           DOC + "permissions"))
    noop = [r for r, _s in deny if parse_rule(r)[0] in ("Grep", "Glob", "Write", "NotebookEdit", "MultiEdit")
            and (parse_rule(r)[1] or "*").strip() not in ("*", "")]
    if noop:
        out.append(finding("DENY-NOOP", "low", "permissions", f"{len(noop)} deny rules do nothing",
                           "Claude Code accepts Grep, Glob and Write rules with a path but never matches them; Read and "
                           "Edit rules for the same path cover those tools.\n" +
                           "\n".join(f"- `{red_rule(ctx, r, limit=90)}`" for r in noop[:10]),
                           "Delete them if Read/Edit rules for those paths exist, otherwise turn them into Read(...) or "
                           "Edit(...) rules.", DOC + "permissions"))
    mode, scope = get(layers, "permissions.defaultMode")
    if mode == "bypassPermissions":
        out.append(finding("BYPASS-DEFAULT", "high", "permissions", "New sessions start in bypassPermissions mode",
                           f"Set in {scope} settings: every tool call runs without any check.",
                           'Use "default", "acceptEdits" or "auto" instead.'))
    dbp, _ = get(layers, "permissions.disableBypassPermissionsMode")
    if dbp != "disable":
        out.append(finding("BYPASS-AVAILABLE", "low", "permissions", "Any session can switch to bypassPermissions mode",
                           "In that mode every tool call runs unchecked, including ones a prompt injection asks for.",
                           '"permissions": {"disableBypassPermissionsMode": "disable"} in ~/.claude/settings.json.',
                           DOC + "settings-reference"))
    skip, _ = get(layers, "skipDangerousModePermissionPrompt")
    if skip is True:
        out.append(finding("BYPASS-PROMPT-SKIPPED", "medium", "permissions",
                           "The warning before bypassPermissions mode is switched off", "",
                           "Remove skipDangerousModePermissionPrompt."))
    allow = []
    for layer in layers:
        perms = layer.data.get("permissions")
        for r in (perms.get("allow") if isinstance(perms, dict) else None) or []:
            if isinstance(r, str):
                allow.append((r, f"{layer.scope} settings, {ctx.red(str(layer.path)).replace(chr(92), '/')}"))
    allow += list(extra_allow)
    data = read_json(global_json)
    for ppath, pc in ((data.get("projects") if isinstance(data, dict) else None) or {}).items():
        for r in (pc.get("allowedTools") if isinstance(pc, dict) else None) or []:
            if isinstance(r, str):
                allow.append((r, "~/.claude.json, project " + ctx.red(ppath).replace("\\", "/")))
    by_file: dict = collections.OrderedDict()
    for r, where in allow:
        why = next((w for rx, w in BROAD_ALLOW if rx.search(r.strip())), None)
        line = f"  - `{red_rule(ctx, r, limit=90)}`: {why}"
        if why and line not in by_file.setdefault(where, []):
            by_file[where].append(line)
    by_file = {k: v for k, v in by_file.items() if v}
    total = sum(len(v) for v in by_file.values())
    if total:
        detail = []
        for where, lines in by_file.items():
            detail.append(f"- {where}:")
            detail += lines[:10] + (["  - ..."] if len(lines) > 10 else [])
        out.append(finding("BROAD-ALLOW", "medium", "permissions",
                           f"{total} allow rules let Claude run a whole class of actions unasked",
                           "\n".join(detail) + "\nA `*` anywhere in a Bash rule matches any text, so a wildcard inside "
                           "inline code admits any command.",
                           "Narrow them to exact commands (`Bash(npm test)`, `Bash(git status:*)`) or move them to ask.",
                           DOC + "permissions"))
    auto, scope = get(layers, "enableAllProjectMcpServers")
    if auto is True:
        out.append(finding("PROJECT-MCP-AUTO", "high" if scope in ("user", "managed") else "medium", "permissions",
                           "Every project's .mcp.json servers start without asking",
                           f"Set in {scope} settings: a cloned repository can start any program as an MCP server.",
                           "Remove enableAllProjectMcpServers and approve servers one by one."))
    dirs = []
    for layer in layers:
        for d in (dig(layer.data, "permissions.additionalDirectories") or []):
            p = posix_path(ctx, Path(str(d)).expanduser())
            if re.fullmatch(r"/[a-z]?/?|" + re.escape(posix_path(ctx, ctx.home)) + "/?", p):
                dirs.append(f"- {ctx.red(d)} ({layer.scope})")
    if dirs:
        out.append(finding("ADDITIONAL-DIRS-BROAD", "medium", "permissions",
                           "Claude may work in your whole home folder or a whole drive", "\n".join(dirs),
                           "List project folders instead."))
    if not truthy(env("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB")):
        out.append(finding("ENV-SCRUB", "medium", "permissions", "Commands, hooks and MCP servers inherit your credentials",
                           "Without CLAUDE_CODE_SUBPROCESS_ENV_SCRUB every Bash command, hook and stdio MCP server Claude "
                           "starts can read API keys and tokens from the environment, which is what a prompt injection "
                           "goes after. GitHub tokens and proxy settings are kept.",
                           '"CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1" in the env block; then check that your MCP servers '
                           "still connect.", DOC + "env-vars"))
    if ctx.system == "windows":
        out.append(finding("NO-SANDBOX", "info", "isolation", "Native Windows has no command sandbox",
                           "Shell commands run with your full rights. Deny rules cover Claude's file tools and commands "
                           "that name a file, not scripts that open files themselves.",
                           "Run Claude Code inside WSL2 when you need the sandbox; until then keep secrets out of reach.",
                           DOC + "sandboxing"))
    else:
        sb, _ = get(layers, "sandbox.enabled")
        if sb is not True:
            out.append(finding("SANDBOX-OFF", "medium", "isolation", "The command sandbox is off",
                               "Shell commands can read and write anywhere you can, and reach any host.",
                               '"sandbox": {"enabled": true} in ~/.claude/settings.json.', DOC + "sandboxing"))
    if not (managed_dir(ctx) / "managed-settings.json").is_file():
        out.append(finding("NO-MANAGED", "info", "isolation", "No managed settings lock your rules",
                           "A project's settings can add allow rules or change the mode for that project. Managed "
                           "settings take precedence over everything and can't be overridden.",
                           f"Optional, as administrator: copy the deny rules and switches you rely on into "
                           f"{managed_dir(ctx)}{os.sep}managed-settings.json.", DOC + "managed-settings"))
    if ctx.system == "windows" and Path(r"C:\ProgramData\ClaudeCode\managed-settings.json").is_file():
        out.append(finding("MANAGED-LEGACY", "low", "isolation", "An old managed-settings.json is ignored",
                           r"Claude Code no longer reads C:\ProgramData\ClaudeCode\managed-settings.json.",
                           r"Move what you need to C:\Program Files\ClaudeCode\ and delete the old file."))
    br, _ = get(layers, "permissions.blockReadsOutsideWorkingDirectories")
    if br is not True:
        out.append(finding("READS-OUTSIDE", "info", "permissions", "Claude's file tools can read outside the project",
                           "permissions.blockReadsOutsideWorkingDirectories makes them refuse other folders in every "
                           "mode; it also blocks legitimate cross-project reads.",
                           'Optional: "permissions": {"blockReadsOutsideWorkingDirectories": true}.',
                           DOC + "settings-reference"))
    for layer in layers:
        names = [k for k, v in (layer.data.get("env") or {}).items() if literal_secret(k, v)] \
            if isinstance(layer.data.get("env"), dict) else []
        if not names:
            continue
        tracked = layer.scope == "project" and bool(git(ctx, ["-C", str(layer.path.parent.parent), "ls-files",
                                                              "--error-unmatch", ".claude/settings.json"]).strip())
        if tracked:
            sev, why = "high", "The file is committed, so the secret is in the repository."
        elif layer.scope == "project-local":
            sev, why = "low", ("The file is git-ignored, which keeps it out of commits; deny Claude reading it "
                               "(DENY-SECRET-PATTERNS) so it stays out of conversations too.")
        else:
            sev, why = "medium", "Every session and every tool that reads the file sees them."
        out.append(finding("SECRET-IN-SETTINGS", sev, "permissions",
                           f"Plaintext secrets in {layer.scope} settings: {', '.join(sorted(names))}", why,
                           "Use apiKeyHelper or the operating system's credential store where you can."))
    base = env("ANTHROPIC_BASE_URL")
    if base:
        host = host_of(base)
        if host in LOCAL_HOSTS:
            out.append(finding("BASE-URL-LOCAL", "info", "data-sharing", "This profile talks to a local gateway",
                               f"ANTHROPIC_BASE_URL points at {host}."))
        elif not host.endswith("anthropic.com"):
            out.append(finding("BASE-URL", "high", "data-sharing", f"Claude Code sends every prompt to {host}",
                               "ANTHROPIC_BASE_URL is set to a host that is neither Anthropic nor this machine.",
                               "Unset it unless you trust that host with your code."))
    return out


def check_profile_b(ctx, label, layers) -> list[dict]:
    deny = {parse_rule(r)[0] for r, _ in rules(layers, "deny") if parse_rule(r)[1] in (None, "", "*")}
    missing = [t for t in ("WebFetch", "WebSearch") if t not in deny]
    if missing:
        return [finding("PROFILE-B-WEB", "medium", "data-sharing", f"Profile {label} can reach the web",
                        f"{' and '.join(missing)} would send requests outside the local gateway.",
                        "Run `uv run scripts/stack.py claude-env` once, which writes the deny rules for profile B.")]
    return []


def check_extensions(ctx, servers, hooks, plugs, markets, tasks) -> list[dict]:
    out = []
    unpinned, plaintext, insecure = [], [], []
    for s in servers:
        where = f"{s['name']} ({s['scope']})"
        pkg = runner_package(s["command"], s["args"]) if s["type"] == "stdio" else None
        if pkg and not pkg[2]:
            unpinned.append(f"- {where}: {pkg[3]}")
        keys = [k for k, v in {**s["env"], **s["headers"]}.items() if literal_secret(k, v)]
        if keys:
            plaintext.append((f"- {where}: {', '.join(sorted(keys))}" + (" (committed in .mcp.json)" if s["tracked"] else ""),
                              s["tracked"]))
        if s["url"].lower().startswith("http://") and host_of(s["url"]) not in LOCAL_HOSTS:
            insecure.append(f"- {where}: {host_of(s['url'])}")
    if unpinned:
        out.append(finding("MCP-UNPINNED", "medium", "extensions",
                           f"{len(unpinned)} MCP servers run whatever version the registry serves today",
                           "\n".join(unpinned), "Pin versions (`npx -y pkg@1.2.3`, `uvx pkg==1.2.3`) and update on purpose.",
                           DOC + "mcp"))
    if plaintext:
        out.append(finding("MCP-PLAINTEXT-SECRET", "high" if any(t for _, t in plaintext) else "medium", "extensions",
                           "MCP server credentials are written in plain text", "\n".join(p for p, _ in plaintext),
                           "Reference an environment variable (`${TOKEN}`) instead of the value.", DOC + "mcp"))
    if insecure:
        out.append(finding("MCP-HTTP", "high", "extensions", "MCP servers over unencrypted http", "\n".join(insecure),
                           "Use https or remove them."))
    third = [f"- {n}: {ctx.red(src)}" for n, src in markets.items() if not OFFICIAL_MARKETS.search(f"{n} {src}")]
    if third:
        out.append(finding("MARKETPLACE-THIRD-PARTY", "medium", "extensions", "Plugin marketplaces not run by Anthropic",
                           "\n".join(third), "Keep only marketplaces you trust; plugins can bring hooks and MCP servers.",
                           DOC + "plugins/security"))
    plugin_hooks = sorted({h["scope"][7:] for h in hooks if h["scope"].startswith("plugin ")})
    if plugin_hooks:
        out.append(finding("PLUGIN-HOOKS", "info", "extensions", "Plugins that run hooks automatically",
                           ", ".join(plugin_hooks), "Review what each hook runs after every plugin update."))
    net = [f"- {h['scope']}, {h['event']}: {ctx.red(h['command'])[:140]}" for h in hooks if NETWORK_CMD.search(h["command"])]
    if net:
        out.append(finding("HOOK-NETWORK", "medium", "extensions", "Hooks that can send data over the network",
                           "\n".join(net), "Check that each one only talks to hosts you trust.", DOC + "hooks"))
    return out


def check_identity_settings(ctx, layers, pdir, repos, history) -> list[dict]:
    out = []
    for scope in ("--global", "--system"):
        e = git(ctx, ["config", scope, "user.email"]).strip()
        if e and not benign_email(e):
            out.append(finding("GIT-EMAIL", "medium", "identity", f"git {scope[2:]} user.email is a personal address",
                               "Every commit made on this machine publishes it, and Claude sees it in git output.",
                               f"git config {scope} user.email <id>+<user>@users.noreply.github.com "
                               "(GitHub > Settings > Emails shows yours)."))
    for repo in repos:
        e = git(ctx, ["-C", str(repo), "config", "--local", "user.email"]).strip()
        if e and not benign_email(e):
            out.append(finding("GIT-EMAIL-REPO", "medium", "identity", f"{repo_label(ctx, repo)} sets its own personal user.email",
                               "Commits in this repository publish it.",
                               f"git -C <repo> config --unset user.email (or set the no-reply address)."))
    code, npm = run(ctx, ["npm", "config", "get", "init-author-email"], timeout=20)
    npm = npm.strip() if code == 0 else ""
    if npm and npm not in ("undefined", "null") and not benign_email(npm):
        out.append(finding("NPM-INIT-AUTHOR", "low", "identity", "npm init writes your address into package.json",
                           "init-author-email is set in your npm config.",
                           "npm config delete init-author-email; npm config delete init-author-name"))
    attribution, _ = get(layers, "attribution")
    link = attribution.get("sessionUrl") if isinstance(attribution, dict) else (False if attribution is False else None)
    if link is not False:
        extra = f" {history['session_links']} commits in this repository's history carry one." if history.get("session_links") else ""
        out.append(finding("ATTRIBUTION-SESSION-LINK", "low", "identity", "Commits can carry a link to your Claude session",
                           "attribution.sessionUrl is on by default; in a public repository the link ties the commit to "
                           "your Claude account." + extra,
                           '"attribution": {"sessionUrl": false} keeps Co-Authored-By; "attribution": false hides all '
                           "attribution (Claude Code 2.1.281 or later).", DOC + "settings-reference"))
    gm = read_text(pdir / "CLAUDE.md") or ""
    if RULE_MARKER not in gm:
        out.append(finding("STANDING-RULE", "low", "identity", "No standing rule keeps your identity out of what Claude writes",
                           "Each session decides on its own whether to copy your email or name into files, scripts, "
                           "commits or API calls.",
                           "Add the identity rule from references/identity.md to ~/.claude/CLAUDE.md."))
    if history.get("unpushed"):
        out.append(finding("IDENTITY-UNPUSHED", "high", "identity",
                           f"{history['unpushed']} commits not pushed yet carry your email address",
                           "Pushing them publishes it in the commit metadata.",
                           "Before pushing: set the no-reply address, then `git rebase -r <upstream> --exec "
                           "\"git commit --amend --no-edit --reset-author\"` (rewrites those local commits)."))
    if history.get("pushed"):
        out.append(finding("IDENTITY-PUSHED", "info", "identity",
                           f"{history['pushed']} commits on the remote of {repo_label(ctx, repos[0]) if repos else 'this repo'} carry "
                           "your email address",
                           "They are already published. Rewriting history breaks every clone, and GitHub keeps old "
                           "commits reachable through pull requests until its support purges them.",
                           "Turn on 'Keep my email addresses private' and 'Block command line pushes that expose my "
                           "email' on GitHub; rewrite only if you accept the cost."))
    return out


def identity_findings(ctx, scan: dict) -> list[dict]:
    out = []
    items = scan["items"]

    def files(sel):
        c = collections.OrderedDict()
        for i in sel:
            c.setdefault(i["file"], collections.Counter())[i["kind"]] += 1
        return c

    pub = [i for i in items if i["class"] == "published" and i["action"] == "replace"]
    if pub:
        cur = repo_root(ctx, ctx.cwd)
        cur_label = repo_label(ctx, cur) if cur else None
        here_files = {i["file"] for i in pub if i.get("current")}
        groups: dict = collections.OrderedDict()
        for i in pub:
            groups.setdefault((i.get("checkout") or "", bool(i.get("current"))), []).append(i)
        detail, fixes = [], []
        for (checkout, here), sel in groups.items():
            f = files(sel)
            detail.append(f"In {'this checkout' if here else checkout}:")
            detail += [f"- {k}: {', '.join(f'{n} {kind}' for kind, n in v.items())}" for k, v in list(f.items())[:20]]
            if here:
                fixes.append("This checkout: `scrub --apply`, then review the diff and commit it.")
            elif cur_label and all(k.split("/", 1)[0] == cur_label and k not in here_files for k in f):
                fixes.append(f"{checkout}: the branch you are on already has the fix; merging it clears these. Don't "
                             "edit that checkout from here.")
            else:
                fixes.append(f"{checkout}: `scrub --apply --repo {checkout}` once it has no uncommitted work, or fix "
                             "it in a branch of that repository.")
        nfiles = len({i["file"] for i in pub})
        out.append(finding("IDENTITY-PUBLISHED", "high" if scan["remote_repos"] else "medium", "identity",
                           f"Your identity is in {nfiles} files in your repositories",
                           "Committed files become public when they are pushed.\n" + "\n".join(detail),
                           "\n".join(fixes)))
    ins = [i for i in items if i["class"] == "instructions" and i["action"] == "replace"]
    if ins:
        f = files(ins)
        out.append(finding("IDENTITY-INSTRUCTIONS", "medium", "identity",
                           f"Your identity is in {len(f)} of Claude's instruction or memory files",
                           "Claude copies from these into what it writes.\n" +
                           "\n".join(f"- {k}: {', '.join(f'{n} {kind}' for kind, n in v.items())}" for k, v in list(f.items())[:25]),
                           "Run `scrub --apply` (placeholders)."))
    contact = [i for i in items if i["kind"] in ("contact-email", "contact-from-git")]
    if contact:
        out.append(finding("IDENTITY-CONTACT-API", "medium", "identity",
                           "Scripts send an email address to web APIs as a contact",
                           "\n".join(f"- {i['file']}:{i['line']}: `{i['context'][:120]}`" for i in contact[:12]),
                           "Read CONTACT_EMAIL from the environment at run time, default you@example.com; never pull it "
                           "from git config or files. See references/identity.md."))
    parts = [i for i in items if i["kind"] == "owner-name-part" and i["class"] in ("published", "instructions")]
    if parts:
        f = files(parts)
        out.append(finding("IDENTITY-NAME-PART", "low", "identity", f"Part of your name appears in {len(f)} files",
                           "Not replaced automatically (it may be another person).\n" +
                           "\n".join(f"- {k}" for k in list(f)[:15]), "Check each by hand."))
    others = [i for i in items if i["kind"] == "other-email" and i["class"] in ("published", "instructions")]
    if others:
        f = files(others)
        out.append(finding("OTHER-EMAILS", "low", "identity", f"Other people's or service email addresses in {len(f)} files",
                           "\n".join(f"- {k}" for k in list(f)[:15]),
                           "Replace personal ones with placeholders by hand; leave project contacts you mean to publish."))
    unity = [i for i in items if i["kind"] == "unity-org"]
    if unity:
        out.append(finding("UNITY-ORG", "info", "identity", "Unity project settings name a Unity organization",
                           "\n".join(f"- {i['file']}:{i['line']}" for i in unity[:10]),
                           "The organization ID is often your Unity account name; unlink the project from Unity "
                           "services if you don't use them."))
    kept = [i for i in items if i["class"] == "kept"]
    if kept:
        out.append(finding("IDENTITY-KEPT", "info", "identity", "Identity kept on purpose", "\n".join(
            f"- {k}" for k in list(files(kept))[:15]),
            "These are excluded from the public skills library or listed under `keep`; nothing to do."))
    cfg = [i for i in items if i["class"] == "config"]
    if cfg:
        out.append(finding("IDENTITY-CONFIG", "low", "identity", "Email addresses in Claude configuration files",
                           "\n".join(f"- {k}" for k in list(files(cfg))[:10]),
                           "Move them out of env and args if Claude doesn't need them; this audit never edits config."))
    if scan.get("host_files"):
        out.append(finding("HOSTNAME-IN-FILES", "info", "identity",
                           f"This computer's name, which contains your user name, is in {len(scan['host_files'])} committed files",
                           "\n".join(f"- {k}" for k in scan["host_files"][:10]),
                           "Leave it if you don't mind; this stack names machine profiles after the computer "
                           "(AGENT_STACK_MACHINE overrides it)."))
    return out


# ---------------------------------------------------------------- drift

def fingerprint(ctx, layers_by_profile, servers, hooks, plugs, markets, skills, tasks, exts, vers) -> dict:
    fp: dict = {"versions": dict(vers), "env": {}, "settings": {}, "rules": {}, "mcp": {}, "hooks": {}, "plugins": {},
                "marketplaces": {}, "skills": file_hashes(skills), "tasks": file_hashes(tasks), "extensions": dict(exts)}
    for label, layers in layers_by_profile.items():
        for layer in layers:
            for k, v in (layer.data.get("env") or {}).items() if isinstance(layer.data.get("env"), dict) else []:
                fp["env"][f"{label}:{layer.scope}:{k}"] = str(v) if k in SAFE_ENV_VALUES else "set"
            for key in TRACKED_SETTINGS:
                v = dig(layer.data, key)
                if v is not None:
                    fp["settings"][f"{label}:{layer.scope}:{key}"] = ctx.red(json.dumps(v, sort_keys=True))
            for kind in ("allow", "deny", "ask"):
                for r in (dig(layer.data, "permissions." + kind) or []):
                    shown = red_rule(ctx, r, limit=90)
                    if shown != red_rule(ctx, r):  # shortened: keep two long rules with the same start apart
                        shown += " #" + sha(r)[:6]
                    fp["rules"][f"{label}:{layer.scope}:{kind}:{shown}"] = "1"
    for s in servers:
        fp["mcp"][f"{s['scope']}:{s['name']}"] = sha(json.dumps([s["command"], s["args"], s["url"]]))
    for i, h in enumerate(hooks):
        fp["hooks"][f"{h['scope']}:{h['event']}:{sha(h['command'])}"] = "1"
    fp["plugins"] = {k: v["version"] for k, v in plugs.items()}
    fp["marketplaces"] = {k: ctx.red(v) for k, v in markets.items()}
    return fp


def diff_fingerprints(prev: dict, cur: dict) -> dict:
    out = {}
    for section, now_items in cur.items():
        before = prev.get(section) or {}
        added = sorted(k for k in now_items if k not in before)
        removed = sorted(k for k in before if k not in now_items)
        changed = sorted(k for k in now_items if k in before and before[k] != now_items[k])
        if added or removed or changed:
            out[section] = {"added": added, "removed": removed, "changed": changed}
    return out


def drift_findings(drift: dict) -> list[dict]:
    if not drift:
        return []
    risky = {"mcp", "hooks", "plugins", "marketplaces", "rules", "tasks", "skills"}
    lines, severity = [], "info"
    for section, ch in drift.items():
        if section == "versions":
            continue
        for kind in ("added", "changed", "removed"):
            for k in ch[kind][:12]:
                lines.append(f"- {section} {kind}: {k}")
                if section in risky and kind != "removed":
                    severity = "medium"
    if not lines:
        return []
    return [finding("DRIFT", severity, "drift", f"{len(lines)} configuration changes since the last audit",
                    "\n".join(lines[:40]), "Check that you made each added or changed item yourself.")]


# ---------------------------------------------------------------- collect

def load_state(ctx) -> dict:
    data = read_json(ctx.state / "state.json")
    return data if isinstance(data, dict) and data.get("schema") == SCHEMA else {"schema": SCHEMA}


def collect(ctx: Ctx, extra_repos: list[str], include_projects: bool = True, include_versions: bool = True) -> dict:
    set_identity(ctx, discover_identity(ctx))
    state = load_state(ctx)
    first_run = "fingerprint" not in state
    profs = profiles(ctx)
    deny_all = all_deny(ctx)
    repos = discover_repos(ctx, extra_repos, include_projects, deny_all)
    current = repos[0] if repos and repo_root(ctx, ctx.cwd) else None
    layers_by_profile = {label: load_layers(ctx, pdir, current) for label, pdir, _g in profs}
    layers_a = layers_by_profile["A"]
    vers = versions(ctx) if include_versions else {}

    changelog_md = fetch_text(ctx, CHANGELOG_URL, "changelog")
    entries = parse_changelog(changelog_md) if changelog_md else []
    latest = None
    if not ctx.offline:
        try:
            latest = json.loads(http_get(NPM_LATEST).decode("utf-8")).get("version")
        except (urllib.error.URLError, OSError, ValueError) as e:
            ctx.errors.append(f"npm latest: {getattr(e, 'reason', e)}")
    if not latest and entries:
        latest = entries[0][0]

    pdir_a, gjson_a = profs[0][1], profs[0][2]
    plugs, markets = plugin_inventory(pdir_a)
    servers = mcp_servers(ctx, current)
    hooks = hook_commands(layers_a, plugs)
    skills, tasks = skills_and_tasks(ctx, pdir_a, current)
    exts = desktop_extensions(ctx)
    nonessential = env_value(ctx, layers_a, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC")[0] is not None

    findings = []
    findings += check_updates(ctx, vers, latest, entries, nonessential)
    findings += check_data_sharing(ctx, layers_a, vers)
    findings += check_retention(ctx, layers_a)
    findings += check_permissions(ctx, layers_a, gjson_a, project_allow_rules(ctx, repos, current))
    for label, _pdir, _g in profs[1:]:
        findings += check_profile_b(ctx, label, layers_by_profile[label])
    findings += check_extensions(ctx, servers, hooks, plugs, markets, tasks)
    history = git_history_identity(ctx, repos) if ctx.identity.emails else {}
    findings += check_identity_settings(ctx, layers_a, pdir_a, repos, history)
    scan = identity_scan(ctx, repos, deny_all)
    findings += identity_findings(ctx, scan)

    packages = [{"ecosystem": "npm", "name": CC_NPM, "version": v, "label": f"Claude Code ({k})"}
                for k, v in vers.items() if k in ("cli", "vscode", "desktop_code")]
    for s in servers:
        pkg = runner_package(s["command"], s["args"]) if s["type"] == "stdio" else None
        if pkg and pkg[2]:
            packages.append({"ecosystem": pkg[0], "name": pkg[1], "version": pkg[2], "label": f"MCP server {s['name']}"})
    if not ctx.offline:
        packages += uv_tools(ctx)
    errors_before = len(ctx.errors)
    advisories = osv_check(ctx, packages)
    osv = {"checked": not ctx.offline and len(ctx.errors) == errors_before and bool(packages),
           "packages": [f"{p['label']}: {p['name']} {p['version']}" for p in packages]}
    seen = set(state.get("advisories_seen") or [])
    for a in advisories:
        fixed = f" Fixed in {a['fixed'][0]}." if a["fixed"] else ""
        cve = f" ({', '.join(a['aliases'])})" if a["aliases"] else ""
        findings.append(finding("ADVISORY " + a["id"], a["severity"], "advisories",
                                f"{a['label']} {a['installed']}: {a['summary'] or a['id']}" + (" (new)" if a["id"] not in seen else ""),
                                f"{a['id']}{cve}, published {a['published'] or 'unknown'}.{fixed}",
                                "Update it." if a["fixed"] else "Check the advisory for a workaround.",
                                "https://osv.dev/vulnerability/" + a["id"]))

    docs = {"first_run": first_run, "available": False}
    settings_md = fetch_text(ctx, DOCS_SETTINGS, "settings docs")
    env_md = fetch_text(ctx, DOCS_ENV, "env-var docs")
    cur_settings = parse_settings_reference(settings_md) if settings_md else {}
    cur_env = parse_env_vars(env_md) if env_md else {}
    if cur_settings and cur_env:
        docs["available"] = True
        configured = set()
        for layers in layers_by_profile.values():
            for layer in layers:
                configured |= set(layer.data) | set((layer.data.get("env") or {}) if isinstance(layer.data.get("env"), dict) else {})
        interesting = configured | SAFE_ENV_VALUES | set(TRACKED_SETTINGS) | {
            k for k, v in cur_settings.items() if v["category"] in (
                "Privacy and telemetry", "Permission settings", "Sandbox settings", "MCP", "Hooks and automation",
                "Enterprise and managed settings", "Git and attribution", "Authentication and providers")}
        prev = state.get("docs") or {}
        if prev:
            docs["settings"] = docs_diff(prev.get("settings") or {}, cur_settings, interesting)
            docs["env"] = docs_diff(prev.get("env") or {}, cur_env, interesting)
        docs["counts"] = {"settings": len(cur_settings), "env": len(cur_env)}
        docs["privacy_category"] = sorted(k for k, v in cur_settings.items() if v["category"] == "Privacy and telemetry")
        docs["email_switch"] = sorted([k for k, v in cur_env.items() if "EMAIL" in k] +
                                      [k for k, v in cur_settings.items() if "email" in (k + v["desc"]).lower()])
    since = state.get("changelog_version") or (min((v for k, v in vers.items() if k in ("cli", "vscode", "desktop_code")),
                                                   key=vtuple, default=None))
    if not since and entries:
        since = entries[min(10, len(entries) - 1)][0]
    changes = changelog_since(entries, since) if entries and since else []

    fp = fingerprint(ctx, layers_by_profile, servers, hooks, plugs, markets, skills, tasks, exts, vers)
    drift = {} if first_run else diff_fingerprints(state.get("fingerprint") or {}, fp)
    findings += drift_findings(drift)
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["area"], f["id"]))

    stamp = now()
    result = {
        "schema": SCHEMA, "generated": stamp.isoformat(timespec="seconds"), "first_run": first_run,
        "system": ctx.system, "offline": ctx.offline, "versions": vers, "latest": latest,
        "counts": dict(collections.Counter(f["severity"] for f in findings)), "findings": findings,
        "identity": {"stats": scan["stats"], "items": scan["items"],
                     "kinds_searched": sorted({"email" if ctx.identity.emails else "", "name" if ctx.identity.names else "",
                                               "username" if ctx.identity.username else ""} - {""})},
        "repos_scanned": sorted({repo_label(ctx, r) for r in repos}), "drift": drift, "docs": docs,
        "changelog": {"since": since, "latest": entries[0][0] if entries else None, "lines": changes},
        "advisories": advisories, "osv": osv, "current": current_view(ctx, layers_a), "errors": ctx.errors,
        "pending_state": {
            "changelog_version": entries[0][0] if entries else state.get("changelog_version"),
            "docs": ({"settings": {k: sha(v["desc"]) for k, v in cur_settings.items()},
                      "env": {k: sha(v["desc"]) for k, v in cur_env.items()}} if docs["available"] else state.get("docs")),
            "advisories_seen": sorted(seen | {a["id"] for a in advisories}),
            "fingerprint": fp,
        },
    }
    return result


def current_view(ctx: Ctx, layers: list[Layer]) -> dict:
    """What the default profile has now, so a fix can be written as a merge, not a repeat."""
    env = {}
    for layer in layers:
        block = layer.data.get("env")
        for k, v in (block.items() if isinstance(block, dict) else []):
            env[f"{k} ({layer.scope})"] = str(v) if k in SAFE_ENV_VALUES else "set"
    settings = {}
    for key in TRACKED_SETTINGS:
        v, scope = get(layers, key)
        if v is not None:
            settings[f"{key} ({scope})"] = v if isinstance(v, (bool, int, float, str)) else json.dumps(v)
    return {"env": env, "settings": settings,
            "deny": [f"{red_rule(ctx, r, limit=90)} ({s})" for r, s in rules(layers, "deny")],
            "ask": [f"{red_rule(ctx, r, limit=90)} ({s})" for r, s in rules(layers, "ask")],
            "allow_count": len(rules(layers, "allow"))}


def changelog_for_summary(lines: list[dict], limit: int = 45) -> list[dict]:
    """Every security fix and new setting, then the rest up to `limit` lines in total."""
    first = [e for e in lines if e.get("kind") in ("security", "new-setting")]
    rest = [e for e in lines if e.get("kind") not in ("security", "new-setting")]
    return first + rest[:max(0, limit - len(first))]


def safety_net(ctx: Ctx, text: str) -> str:
    """Last pass over everything written or printed: nothing identifying may remain."""
    return ctx.red(text)


def write_outputs(ctx: Ctx, result: dict) -> tuple[Path, Path]:
    (ctx.state / "reports").mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.fromisoformat(result["generated"])
    report_name = stamp.strftime("%Y-%m-%d-%H%M") + ".md"
    result["report"] = report_name
    report = ctx.state / "reports" / report_name
    report.write_text(safety_net(ctx, render_report(result)), encoding="utf-8")
    last = ctx.state / "last-run.json"
    last.write_text(safety_net(ctx, json.dumps(result, indent=1, ensure_ascii=False)), encoding="utf-8")
    return report, last


def summary_json(ctx: Ctx, result: dict, report: Path) -> str:
    def trim(f, limit: int = 1200):
        """Cut long details at a line break and say how much is left, rather than mid-line."""
        if len(f["detail"]) <= limit:
            return f
        kept, size, lines = [], 0, f["detail"].splitlines()
        for line in lines:
            if size + len(line) > limit:
                break
            kept.append(line)
            size += len(line) + 1
        return {**f, "detail": "\n".join(kept) + f"\n(... {len(lines) - len(kept)} more lines in the report)"}
    out = {
        "report": ctx.red(str(report)).replace("\\", "/"), "first_run": result["first_run"], "counts": result["counts"],
        "versions": result["versions"], "latest": result["latest"], "findings": [trim(f) for f in result["findings"]],
        "identity_items": [i for i in result["identity"]["items"] if i["class"] != "config"][:40],
        "identity_stats": result["identity"]["stats"], "repos_scanned": result["repos_scanned"],
        "docs": {k: v for k, v in result["docs"].items()},
        "changelog": {**result["changelog"], "lines": changelog_for_summary(result["changelog"]["lines"]),
                      "shown": len(changelog_for_summary(result["changelog"]["lines"])),
                      "total_lines": len(result["changelog"]["lines"]),
                      "note": "security fixes and new settings first; the report and last-run.json have every line"},
        "advisories": result["advisories"], "osv": result["osv"], "current": result["current"],
        "errors": result["errors"],
    }
    return safety_net(ctx, json.dumps(out, indent=1, ensure_ascii=False))


# ---------------------------------------------------------------- report

def render_report(r: dict) -> str:
    sev = r["counts"]
    lines = [f"# Claude security audit, {r['generated'][:16].replace('T', ' ')}", ""]
    lines.append("Findings: " + ", ".join(f"{sev.get(s, 0)} {s}" for s in SEVERITIES) +
                 (" (first run: drift and docs changes start next time)" if r["first_run"] else ""))
    lines += ["", "> This audit reads and reports. It cannot stop Claude Code or Claude Desktop from sending your "
                  "prompts, files and account details to Anthropic; that needs managed settings, the sandbox (WSL2) or "
                  "a local-only profile. It changes nothing except replacing your identity with placeholders when "
                  "asked to (`scrub --apply`).", ""]
    groups = [("Fix first", ("critical", "high")), ("Worth doing", ("medium",)), ("Optional and trade-offs", ("low", "info"))]
    for title, sevs in groups:
        fs = [f for f in r["findings"] if f["severity"] in sevs]
        if not fs:
            continue
        lines += [f"## {title}", ""]
        for f in fs:
            lines.append(f"### [{f['severity']}] {f['title']}  `{f['id']}`")
            if f["detail"]:
                lines += ["", f["detail"]]
            if f["fix"]:
                fix = f["fix"]
                lines += ["", "**Fix:** " + (("\n```\n" + fix + "\n```") if "\n" in fix else fix)]
            if f["docs"]:
                lines += ["", f"Docs: {f['docs']}"]
            lines.append("")
    items = [i for i in r["identity"]["items"] if i["class"] != "config"]
    lines += ["## Identity exposure", ""]
    if items:
        lines += ["| File | Line | Kind | Where | Action |", "|---|---|---|---|---|"]
        for i in items[:80]:
            lines.append(f"| {i['file']} | {i['line']} | {i['kind']} | {i['class']} | {i['action']} |")
        if len(items) > 80:
            lines.append(f"| ... {len(items) - 80} more | | | | |")
    else:
        lines.append("Nothing found in " + str(r["identity"]["stats"].get("files", 0)) + " files.")
    lines += ["", f"Repositories scanned: {', '.join(r['repos_scanned']) or 'none'}. "
                  f"Files skipped because your deny rules cover them: {r['identity']['stats'].get('denied', 0)}.", ""]
    lines += ["## Changes since the last audit", ""]
    if r["first_run"]:
        lines.append("First run: this audit is the baseline.")
    elif not r["drift"]:
        lines.append("No configuration changes.")
    else:
        for section, ch in r["drift"].items():
            for kind in ("added", "changed", "removed"):
                for k in ch[kind][:20]:
                    lines.append(f"- {section} {kind}: `{k}`")
    lines += ["", "## New in Claude Code", ""]
    d = r["docs"]
    if not d.get("available"):
        lines.append("Docs not checked (offline or unreachable).")
    elif r["first_run"] or "settings" not in d:
        lines.append(f"Recorded {d['counts']['settings']} settings and {d['counts']['env']} environment variables as the "
                     "baseline.")
    else:
        for kind, label in (("settings", "Settings"), ("env", "Environment variables")):
            new = d[kind]["new"]
            if new:
                lines += [f"### New {label.lower()}", ""]
                for k, v in sorted(new.items()):
                    lines.append(f"- `{k}`" + (f" ({v['category']})" if v.get("category") else "") + f": {v['desc']}")
                lines.append("")
            if d[kind]["changed"]:
                lines += [f"### {label} whose description changed", ""]
                for k, v in sorted(d[kind]["changed"].items()):
                    lines.append(f"- `{k}`: {v['desc']}")
                lines.append("")
            if d[kind]["removed"]:
                lines.append(f"Removed {label.lower()}: " + ", ".join(f"`{k}`" for k in d[kind]["removed"]))
                lines.append("")
    if d.get("available"):
        lines.append("Settings in the docs' Privacy and telemetry category: " +
                     ", ".join(f"`{k}`" for k in d.get("privacy_category", [])) + ".")
        lines.append("A switch that keeps your account email out of the prompt: " +
                     (", ".join(f"`{k}`" for k in d["email_switch"]) if d.get("email_switch") else "none documented yet") + ".")
    cl = r["changelog"]
    if cl["lines"]:
        lines += ["", f"### Changelog since {cl['since']}: security fixes, new settings, privacy and permissions", ""]
        for e in cl["lines"][:80]:
            lines.append(f"- **{e['version']}** ({e.get('kind', 'security' if e['security'] else 'other')}): {e['text']}")
        if len(cl["lines"]) > 80:
            lines.append(f"- ... {len(cl['lines']) - 80} more lines of lower priority")
    lines += ["", "## Advisories", ""]
    osv = r.get("osv") or {}
    if not osv.get("checked"):
        lines.append("OSV was not checked (offline, unreachable, or nothing to check).")
    elif not r["advisories"]:
        lines.append(f"No OSV advisory affects the {len(osv.get('packages', []))} packages checked: "
                     + "; ".join(osv.get("packages", [])) + ".")
    else:
        for a in r["advisories"]:
            lines.append(f"- [{a['severity']}] {a['label']} {a['installed']}: {a['id']} {a['summary']}"
                         + (f" (fixed in {a['fixed'][0]})" if a["fixed"] else ""))
    lines += ["", "## Versions", ""]
    for k, v in r["versions"].items():
        lines.append(f"- {k}: {v}")
    lines.append(f"- latest Claude Code: {r['latest'] or 'unknown'}")
    lines += ["", "## Manual checks (once a month)", "",
              "- claude.ai > Settings > Privacy: model training ('Help improve Claude') off; with it on, chats are kept 5 years.",
              "- claude.ai > Settings > Connectors: remove connectors you don't use.",
              "- GitHub > Settings > Emails: 'Keep my email addresses private' and 'Block command line pushes that expose my email'.",
              "- Claude Desktop > Settings > Extensions and Developer: remove extensions and MCP servers you don't use.",
              "- Claude Desktop > Scheduled: check each task's permission mode; a task in bypass mode runs unattended "
              "with every check off (the app keeps the mode outside the task file, so this audit can't see it).", ""]
    if r["errors"]:
        lines += ["## Skipped checks", ""] + [f"- {e}" for e in r["errors"]] + [""]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- commands

def cmd_collect(ctx: Ctx, a) -> int:
    result = collect(ctx, a.repo or [], include_projects=not a.no_project_repos)
    report, _last = write_outputs(ctx, result)
    print(summary_json(ctx, result, report))
    return 0


def cmd_scrub(ctx: Ctx, a) -> int:
    set_identity(ctx, discover_identity(ctx))
    repos = []
    for p in (a.repo or [ctx.cwd]):
        root = repo_root(ctx, Path(p).expanduser())
        if root:
            repos.append(root)
    res = scrub(ctx, repos, local=not a.no_local, published=not a.local_only, apply=a.apply,
                include_dirty=a.include_dirty)
    if not a.local_only:
        last = read_json(ctx.state / "last-run.json")
        items = ((last.get("identity") or {}).get("items") if isinstance(last, dict) else None) or []
        done = {ctx.red(str(r)).replace("\\", "/") for r in repos}
        elsewhere = sorted({i["checkout"] for i in items if i.get("class") == "published" and i.get("action") == "replace"
                            and i.get("checkout") and i["checkout"] not in done})
        if elsewhere:
            res["notes"].append("The last collect also found your identity in other checkouts, which this run did not "
                                "touch: " + ", ".join(elsewhere) + ". Pass --repo <path> for each one that has no "
                                "uncommitted work; for a checkout whose fix is already on your branch, merge instead.")
    print(safety_net(ctx, json.dumps(res, indent=1, ensure_ascii=False)))
    return 0


def latest_report(ctx: Ctx):
    last = read_json(ctx.state / "last-run.json")
    if isinstance(last, dict) and last.get("report"):
        p = ctx.state / "reports" / last["report"]
        if p.is_file():
            return p
    reports = sorted((ctx.state / "reports").glob("*.md"))
    return reports[-1] if reports else None


def cmd_add_analysis(ctx: Ctx, a) -> int:
    set_identity(ctx, discover_identity(ctx))
    report = latest_report(ctx)
    if not report:
        print("no report yet: run collect first", file=sys.stderr)
        return 1
    text = (read_text(a.file) if a.file else sys.stdin.read()) or ""
    if not text.strip():
        print("no analysis text given", file=sys.stderr)
        return 1
    body = report.read_text(encoding="utf-8")
    body = re.sub(r"\n## Analysis\n.*\Z", "\n", body, flags=re.S).rstrip() + "\n\n## Analysis\n\n" + text.strip() + "\n"
    report.write_text(safety_net(ctx, body), encoding="utf-8")
    print(ctx.red(str(report)).replace("\\", "/"))
    return 0


def cmd_show(ctx: Ctx, a) -> int:
    report = latest_report(ctx)
    if not report:
        print("no report yet: run collect first", file=sys.stderr)
        return 1
    sys.stdout.write(report.read_text(encoding="utf-8"))
    return 0


def cmd_mark_reviewed(ctx: Ctx, a) -> int:
    set_identity(ctx, discover_identity(ctx))
    last = read_json(ctx.state / "last-run.json")
    if not isinstance(last, dict) or "pending_state" not in last:
        print("no collect to accept: run collect first", file=sys.stderr)
        return 1
    state = load_state(ctx)
    state.update(last["pending_state"])
    state["schema"] = SCHEMA
    state["last_reviewed"] = now().isoformat(timespec="seconds")
    (ctx.state / "state.json").write_text(safety_net(ctx, json.dumps(state, indent=1, ensure_ascii=False)),
                                          encoding="utf-8")
    print(f"baseline updated ({state['last_reviewed']})")
    return 0


def cmd_where(ctx: Ctx, a) -> int:
    set_identity(ctx, discover_identity(ctx))
    report = latest_report(ctx)
    print(json.dumps({"state_dir": ctx.red(str(ctx.state)).replace("\\", "/"),
                      "latest_report": ctx.red(str(report)).replace("\\", "/") if report else None}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="audit.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state-dir", help="state and report folder (default: per-user app data)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("collect")
    s.add_argument("--offline", action="store_true", help="skip docs, changelog, npm and OSV")
    s.add_argument("--repo", action="append", help="also scan this repository (repeatable)")
    s.add_argument("--no-project-repos", action="store_true", help="don't scan the repositories listed in ~/.claude.json")
    s = sub.add_parser("scrub")
    s.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    s.add_argument("--repo", action="append", help="repository to scrub (default: the current one)")
    s.add_argument("--local-only", action="store_true", help="only Claude's own instruction and memory files")
    s.add_argument("--no-local", action="store_true", help="only repository files")
    s.add_argument("--include-dirty", action="store_true", help="also change files with uncommitted changes")
    s = sub.add_parser("add-analysis")
    s.add_argument("--file", help="read the analysis from this file instead of stdin")
    sub.add_parser("show")
    sub.add_parser("mark-reviewed")
    sub.add_parser("where")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ctx = Ctx(state=a.state_dir, offline=getattr(a, "offline", False))
    ctx.state.mkdir(parents=True, exist_ok=True)
    return {"collect": cmd_collect, "scrub": cmd_scrub, "add-analysis": cmd_add_analysis, "show": cmd_show,
            "mark-reviewed": cmd_mark_reviewed, "where": cmd_where}[a.cmd](ctx, a)


if __name__ == "__main__":
    raise SystemExit(main())
