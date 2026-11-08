"""Blocked sites: keep the stack's web reader away from sites with security problems or that take data from users.

Open WebUI is the one part of the stack that reads the web: its web search, links pasted into a chat, and its fetch
tool. It has two filters, and this module fills both from policy/web-filter.yaml and the profile's `web_filter:`
section (your own sites first, then the lists in the policy's order):

- the page-fetch filter, environment variable WEB_FETCH_FILTER_LIST: Open WebUI checks every page it fetches against it
  before it connects. It is read when Open WebUI starts, and Windows caps a variable at 32,767 characters, so it holds
  what fits in FETCH_BUDGET.
- the web search filter, config row `web.search.domain.filter_list`: results from a blocked site are dropped before the
  model sees them. Open WebUI reads the row on every search, so sync_openwebui() rewrites it when a list changes, with
  no restart. It holds up to web_filter.max_sites sites: Open WebUI compares each result with every entry in turn,
  about 0.5 s per 100,000 entries per result on the reference PC.

Every entry starts with "!", which Open WebUI reads as "block". An entry without it makes an allow-list, which would
block every other site, so this module never writes one. Entries the owner added in Open WebUI's admin page are kept.

Outside the stack (Claude Desktop, Claude Code on Anthropic's servers) nothing here enforces anything (AGENTS.md rule
9). export() writes your sites and the shipped lists into /claude-security-audit's folder, which reports the Claude
Code WebFetch deny rules and the protective DNS that would cover them, and a Chrome URLBlocklist file you may import.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import IS_WINDOWS, REPO

POLICY_FILE = REPO / "policy" / "web-filter.yaml"
SEARCH_KEY = "web.search.domain.filter_list"
FETCH_ENV = "WEB_FETCH_FILTER_LIST"
SEARCH_ENV = "WEB_SEARCH_DOMAIN_FILTER_LIST"   # seeds the search row of a fresh Open WebUI database only
FETCH_BUDGET = 24_000         # characters of WEB_FETCH_FILTER_LIST (Windows caps one variable at 32,767)
SEED_BUDGET = 24_000          # characters of the JSON seed for a fresh database
MAX_DOWNLOAD = 32 * 2 ** 20   # a list larger than this is refused
RETRY_SECONDS = 3600          # after a failed download, the next try waits this long
AGENT = "personal-agent-stack-webfilter/1"   # User-Agent for list downloads; no contact address
AUDIT_FILE = "blocked-sites.txt"
HEADER = "# Written by the agent stack's web filter (stack.py web-filter export)."
CHROME_KEY = r"Software\Policies\Google\Chrome\URLBlocklist"
CHROME_MAX = 1000             # Chrome's URLBlocklist policy takes at most 1,000 entries
OWN = "own"                   # source id of your own sites

# Public resolvers that block malware and phishing domains: (provider, addresses or networks). The same table as
# PROTECTIVE_DNS in .claude/skills/claude-security-audit/scripts/audit.py (tests/test_webfilter.py checks they agree).
PROTECTIVE_DNS = (
    ("Quad9", ("9.9.9.9", "149.112.112.112", "9.9.9.11", "149.112.112.11", "2620:fe::fe", "2620:fe::9", "2620:fe::11",
               "2620:fe::fe:11")),
    ("Cloudflare for Families", ("1.1.1.2", "1.0.0.2", "1.1.1.3", "1.0.0.3", "2606:4700:4700::1112",
                                 "2606:4700:4700::1002", "2606:4700:4700::1113", "2606:4700:4700::1003")),
    ("AdGuard DNS", ("94.140.14.14", "94.140.15.15", "94.140.14.15", "94.140.15.16", "2a10:50c0::ad1:ff",
                     "2a10:50c0::ad2:ff", "2a10:50c0::bad1:ff", "2a10:50c0::bad2:ff")),
    ("CleanBrowsing", ("185.228.168.9", "185.228.169.9", "185.228.168.10", "185.228.169.11", "185.228.168.168",
                       "185.228.169.168", "2a0d:2a00:1::2", "2a0d:2a00:2::2", "2a0d:2a00:1::1", "2a0d:2a00:2::1",
                       "2a0d:2a00:1::", "2a0d:2a00:2::")),
    ("Control D", ("76.76.2.1", "76.76.10.1", "76.76.2.2", "76.76.10.2", "76.76.2.4", "76.76.10.4", "2606:1a40::1",
                   "2606:1a40:1::1", "2606:1a40::2", "2606:1a40:1::2", "2606:1a40::4", "2606:1a40:1::4")),
    ("NextDNS (filtering depends on your profile)", ("45.90.28.0/24", "45.90.30.0/24", "2a07:a8c0::/32",
                                                     "2a07:a8c1::/32")),
)
# The DNS servers of the adapters that are up (Windows lists stale ones for adapters that are down).
WINDOWS_DNS_PS = (
    "$up = @(Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Up' } | "
    "ForEach-Object { $_.ifIndex }); "
    "Get-DnsClientServerAddress -AddressFamily IPv4,IPv6 -ErrorAction Stop | "
    "Where-Object { $_.ServerAddresses -and ($up.Count -eq 0 -or $up -contains $_.InterfaceIndex) } | "
    "ForEach-Object { $_.ServerAddresses }")

_LABEL = re.compile(r"^(?!-)[a-z0-9_-]{1,63}(?<!-)$")
_NOT_PUBLIC = {"localhost", "local", "internal", "lan", "home", "arpa", "invalid", "test", "example", "onion"}
_HOSTS_ADDR = {"0.0.0.0", "127.0.0.1", "::", "::0", "::1"}
_lock = threading.Lock()           # one Open WebUI sync at a time (the tray's poller, Apply)
_refresh_lock = threading.Lock()   # one download round at a time


# ---------------------------------------------------------------- reading sites

def normalize(token: str) -> str | None:
    """A site as Open WebUI's filter matches it (lowercase host name, no port, path or wildcard), or None for anything
    that is not a public host name: IP addresses, single labels, local names."""
    t = (token or "").strip().lower()
    if not t:
        return None
    if "://" in t:
        t = urllib.parse.urlsplit(t).hostname or ""
    t = t.removeprefix("||").split("^", 1)[0]       # adblock ||site^
    t = t.split("/", 1)[0].removeprefix("*.").lstrip(".").rstrip(".")
    if t.count(":") == 1:
        t = t.split(":", 1)[0]                        # site:port
    try:
        ipaddress.ip_address(t)
        return None
    except ValueError:
        pass
    if not t.isascii():
        try:
            t = t.encode("idna").decode("ascii")
        except UnicodeError:
            return None
    labels = t.split(".")
    if len(labels) < 2 or len(t) > 253 or labels[-1].isdigit() or labels[-1] in _NOT_PUBLIC:
        return None
    return t if all(_LABEL.match(label) for label in labels) else None


def parse(text: str) -> list[str]:
    """Sites in a list: one per line or separated by commas or spaces, `#` comments, and the usual blocklist formats
    (plain names, hosts-file lines, adblock `||site^`, `*.site`, URLs). Duplicates are kept; plan() drops them."""
    out = []
    for raw in str(text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("!", "[")):   # adblock comments and headers
            continue
        parts = line.replace(",", " ").split()
        if len(parts) >= 2 and parts[0] in _HOSTS_ADDR:
            parts = parts[1:]
        out.extend(d for d in map(normalize, parts) if d)
    return out


def covered(site: str, pool) -> str | None:
    """The entry of `pool` that covers `site` (itself or a parent domain), or None."""
    labels = site.split(".")
    for i in range(len(labels) - 1):
        cand = ".".join(labels[i:])
        if cand in pool:
            return cand
    return None


# ---------------------------------------------------------------- the policy and the profile

@dataclass(frozen=True)
class SiteList:
    id: str
    title: str
    why: str = ""
    sites: tuple[str, ...] = ()   # shipped with the stack
    url: str = ""                 # downloaded at run time
    homepage: str = ""
    terms: str = ""


_policy_cache: dict[str, object] = {}


def lists(path: Path = POLICY_FILE) -> tuple[SiteList, ...]:
    """The lists in policy/web-filter.yaml, in their order."""
    stamp = (str(path), path.stat().st_mtime_ns)
    if _policy_cache.get("stamp") != stamp:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        out = []
        for lid, d in (data.get("lists") or {}).items():
            d = d or {}
            out.append(SiteList(str(lid), str(d.get("title") or lid), str(d.get("why") or "").strip(),
                                tuple(s for s in map(normalize, d.get("sites") or []) if s), str(d.get("url") or ""),
                                str(d.get("homepage") or ""), str(d.get("terms") or "")))
        _policy_cache.update(stamp=stamp, lists=tuple(out),
                             keep=frozenset(k for k in map(normalize, data.get("keep") or []) if k))
    return _policy_cache["lists"]  # type: ignore[return-value]


def keep() -> frozenset[str]:
    """Shared platforms a downloaded list may not block whole (exact names; their subdomains stay blockable)."""
    lists()
    return _policy_cache["keep"]  # type: ignore[return-value]


def by_id() -> dict[str, SiteList]:
    return {lst.id: lst for lst in lists()}


def config(profile: dict) -> dict:
    return profile.get("web_filter") or {}


def enabled(profile: dict) -> bool:
    return bool(config(profile).get("enabled"))


def chosen(profile: dict) -> list[SiteList]:
    """The lists switched on in the profile."""
    cfg = config(profile)
    return [lst for lst in lists() if cfg.get(lst.id)]


def max_sites(profile: dict) -> int:
    try:
        return max(0, int(config(profile).get("max_sites") or 25000))
    except (TypeError, ValueError):
        return 25000


def refresh_hours(profile: dict) -> float:
    try:
        return max(1.0, float(config(profile).get("refresh_hours") or 24))
    except (TypeError, ValueError):
        return 24.0


# ---------------------------------------------------------------- downloaded lists

def state_dir(profile: dict) -> Path:
    return Path(profile["data_dir"]) / "webfilter"


def _cache(profile: dict, lid: str) -> Path:
    return state_dir(profile) / f"{lid}.txt"


def _meta_file(profile: dict, lid: str) -> Path:
    return state_dir(profile) / f"{lid}.json"


def meta(profile: dict, lid: str) -> dict:
    try:
        d = json.loads(_meta_file(profile, lid).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


_cached_sites: dict[str, tuple[tuple, list[str]]] = {}


def cached(profile: dict, lid: str) -> list[str]:
    """The sites of a downloaded list, as last saved; [] before the first download."""
    path = _cache(profile, lid)
    try:
        stamp = (path.stat().st_mtime_ns, path.stat().st_size)
    except OSError:
        return []
    hit = _cached_sites.get(str(path))
    if hit and hit[0] == stamp:
        return hit[1]
    sites = [ln for ln in path.read_text(encoding="utf-8").split("\n") if ln]
    _cached_sites[str(path)] = (stamp, sites)
    return sites


def require_https(url: str) -> None:
    if not url.startswith("https://"):
        raise ValueError("only https:// lists are downloaded")


def download(url: str, timeout: float = 60) -> str:
    """A list's text, over HTTPS only (a redirect to plain HTTP is refused), at most MAX_DOWNLOAD bytes."""
    require_https(url)
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - https only, checked above
        require_https(str(r.geturl()))   # after redirects
        data = r.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError(f"the list is larger than {MAX_DOWNLOAD // 2 ** 20} MB")
    return data.decode("utf-8", "replace")


def due(profile: dict, lst: SiteList, now: float | None = None) -> bool:
    """Whether a downloaded list should be fetched again: never fetched, its URL changed, older than refresh_hours.
    After a failed try it waits RETRY_SECONDS."""
    now = time.time() if now is None else now
    m = meta(profile, lst.id)
    if m.get("last_error") and now - float(m.get("last_try") or 0) < RETRY_SECONDS:
        return False
    if m.get("url") != lst.url or not _cache(profile, lst.id).exists():
        return True
    return now - float(m.get("fetched_at") or 0) >= refresh_hours(profile) * 3600


@dataclass(frozen=True)
class Result:
    id: str
    ok: bool
    text: str


def refresh(profile: dict, force: bool = False, fetch=None) -> list[Result]:
    """Download the chosen lists that are due (all of them with force). A failed download keeps the last copy.
    `fetch` replaces download() (tests)."""
    with _refresh_lock:
        return _refresh(profile, force, fetch or download)


def _refresh(profile: dict, force: bool, fetch) -> list[Result]:
    out = []
    for lst in chosen(profile):
        if not lst.url or not (force or due(profile, lst)):
            continue
        m = meta(profile, lst.id)
        m["last_try"] = time.time()
        have = _cache(profile, lst.id).exists()
        try:
            sites = list(dict.fromkeys(parse(fetch(lst.url))))
            if not sites:
                raise ValueError("the download held no sites")
            text = "\n".join(sites) + "\n"
            _write(_cache(profile, lst.id), text)
            m.update(url=lst.url, fetched_at=time.time(), count=len(sites), last_error="",
                     sha256=hashlib.sha256(text.encode()).hexdigest())
            out.append(Result(lst.id, True, f"{lst.title}: {len(sites):,} sites"))
        except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException) as e:
            m["last_error"] = f"{type(e).__name__}: {e}"[:300]
            kept = (f"the copy from {time.strftime('%Y-%m-%d', time.localtime(float(m.get('fetched_at') or 0)))} "
                    "stays in use") if have else "nothing from it is blocked yet"
            out.append(Result(lst.id, False, f"{lst.title}: download failed ({e}); {kept}"))
        _write(_meta_file(profile, lst.id), json.dumps(m, indent=1))
    return out


# ---------------------------------------------------------------- what gets blocked

@dataclass
class Plan:
    on: bool
    ordered: list[str] = field(default_factory=list)   # every blocked site, in priority order, no site twice
    search: list[str] = field(default_factory=list)    # the first max_sites of them (Open WebUI's search filter)
    fetch: list[str] = field(default_factory=list)     # the first ones that fit FETCH_BUDGET (its page-fetch filter)
    counts: dict[str, int] = field(default_factory=dict)  # sites each source adds that no earlier source had
    missing: list[str] = field(default_factory=list)   # downloaded lists that are on but not downloaded yet
    allowed: int = 0                                   # sites left out because the allow list names them
    conflicts: list[tuple[str, str]] = field(default_factory=list)  # (allowed site, blocked parent that still covers it)

    @property
    def total(self) -> int:
        return len(self.ordered)


def _sources(profile: dict) -> tuple[list[tuple[str, list[str]]], list[str]]:
    cfg = config(profile)
    out = [(OWN, parse(str(cfg.get("block") or "")))]
    missing = []
    for lst in chosen(profile):
        if lst.url:
            sites = cached(profile, lst.id)
            if not sites:
                missing.append(lst.id)
            kept = keep()
            sites = [s for s in sites if s not in kept]
        else:
            sites = list(lst.sites)
        out.append((lst.id, sites))
    return out, missing


_plan_cache: dict[str, tuple[object, Plan]] = {}


def plan(profile: dict) -> Plan:
    """What the filter blocks now: your sites, then each chosen list in the policy's order. A site is listed once, as
    its widest blocked parent (evil.example covers www.evil.example), at the place of its first mention."""
    cfg = config(profile)
    if not cfg.get("enabled"):
        return Plan(False)
    files = [lst.id for lst in chosen(profile) if lst.url]
    stamp = (json.dumps(cfg, sort_keys=True, default=str), POLICY_FILE.stat().st_mtime_ns,
             tuple((_cache(profile, f).stat().st_mtime_ns if _cache(profile, f).exists() else 0) for f in files))
    key = str(state_dir(profile))
    hit = _plan_cache.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    allow = set(parse(str(cfg.get("allow") or "")))
    sources, missing = _sources(profile)
    pool = {s for _sid, sites in sources for s in sites if not covered(s, allow)}
    p = Plan(True, missing=missing)
    seen: set[str] = set()
    for sid, sites in sources:
        n = 0
        for s in sites:
            if covered(s, allow):
                p.allowed += s not in seen
                seen.add(s)
                continue
            labels = s.split(".")
            top = next((".".join(labels[i:]) for i in range(len(labels) - 1, -1, -1)
                        if ".".join(labels[i:]) in pool and i < len(labels) - 1), s)
            if top not in seen:
                seen.add(top)
                p.ordered.append(top)
                n += 1
        p.counts[sid] = n
    blocked = set(p.ordered)
    p.conflicts = [(a, parent) for a in sorted(allow) if (parent := covered(a, blocked)) and parent != a]
    p.search = p.ordered[:max_sites(profile)]
    size = 0
    for s in p.ordered:
        size += len(s) + 2   # "!" and ","
        if size > FETCH_BUDGET:
            break
        p.fetch.append(s)
    _plan_cache[key] = (stamp, p)
    return p


def check(profile: dict, site: str) -> str:
    """Whether a site is blocked, by which source, and in which of Open WebUI's filters."""
    host = normalize(site)
    if not host:
        return f"{site!r} is not a public site name"
    p = plan(profile)
    if not p.on:
        return "the web filter is off (web_filter.enabled)"
    allow = set(parse(str(config(profile).get("allow") or "")))
    entry = covered(host, set(p.ordered))
    if not entry:
        a = covered(host, allow)
        return f"{host} is not blocked" + (f" (allowed by {a})" if a else "")
    sources, _missing = _sources(profile)
    src = next((sid for sid, sites in sources if any(covered(s, {entry}) for s in sites)), "?")
    name = "your own sites" if src == OWN else by_id().get(src, SiteList(src, src)).title
    where = [w for w, part in (("web search", p.search), ("page fetches", p.fetch)) if entry in set(part)]
    return (f"{host} is blocked as {entry} (from {name}) in " + (" and ".join(where) if where else
            "no filter: it is past web_filter.max_sites and the page-fetch budget"))


# ---------------------------------------------------------------- Open WebUI

def openwebui_env(profile: dict) -> dict[str, str]:
    """Open WebUI's environment: the page-fetch filter, and the search filter that seeds a fresh database (an existing
    one keeps its row, which sync_openwebui() writes). {} while the filter is off."""
    p = plan(profile)
    if not p.on or not p.ordered:
        return {}
    seed: list[str] = []
    size = 2
    for s in p.search:
        size += len(s) + 5    # "!site", with quotes, comma and space
        if size > SEED_BUDGET:
            break
        seed.append("!" + s)
    from . import media

    if not media.openwebui_db(profile).exists():
        # The seed lands in the new database's search row; remember it, so sync_openwebui() knows those entries are
        # the stack's (and not the owner's) after a list is turned off.
        try:
            _write(_seeded_file(profile), json.dumps({"entries": seed}))
        except OSError:
            pass
    return {FETCH_ENV: ",".join("!" + s for s in p.fetch), SEARCH_ENV: json.dumps(seed)}


def _written_file(profile: dict) -> Path:
    return state_dir(profile) / "written.json"


def _seeded_file(profile: dict) -> Path:
    return state_dir(profile) / "seeded.json"


def _entries(path: Path) -> set[str]:
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("entries") or [])
    except (OSError, ValueError, AttributeError, TypeError):
        return set()


def sync_openwebui(profile: dict, db: Path | None = None) -> str:
    """Write the search filter into Open WebUI's database (one config row; Open WebUI reads it on every search). The
    entries written last time are replaced; the owner's own entries from Open WebUI's admin page stay first. Returns
    what changed, or "" (no change, or no database yet: the environment seeds a fresh one). No backup is made, unlike
    media.provision_openwebui: this runs after every list refresh, rewrites only its own key, and a copy of a large
    database each day would fill the disk."""
    from . import media

    db = db or media.openwebui_db(profile)
    if not db.exists():
        return ""
    p = plan(profile)
    want = ["!" + s for s in p.search] if p.on else []
    ours = _entries(_written_file(profile)) | _entries(_seeded_file(profile)) | {"!" + s for s in p.ordered}
    with _lock:
        con = sqlite3.connect(db, timeout=30)
        try:
            row = con.execute("select value from config where key = ?", (SEARCH_KEY,)).fetchone()
            try:
                current = json.loads(row[0]) if row else []
            except (TypeError, ValueError):
                current = []
            current = current if isinstance(current, list) else []
            theirs = [e for e in current if isinstance(e, str) and e not in ours]
            new = theirs + want
            if new == current:
                return ""
            with con:
                con.execute("insert into config(key, value, updated_at) values(?, ?, ?) on conflict(key) do update "
                            "set value = excluded.value, updated_at = excluded.updated_at",
                            (SEARCH_KEY, json.dumps(new), int(time.time())))
        finally:
            con.close()
        _write(_written_file(profile), json.dumps({"entries": want}))
    kept = f", {len(theirs)} of your own from its admin page kept" if theirs else ""
    return (f"Open WebUI's web search now blocks {len(want):,} sites{kept}" if want else
            f"Open WebUI's web search filter cleared of the stack's sites{kept}")


# ---------------------------------------------------------------- outside the stack: reports and files to import

def audit_dir() -> Path:
    """/claude-security-audit's state folder (its Ctx.default_state)."""
    if os.environ.get("CLAUDE_SECURITY_AUDIT_DIR"):
        return Path(os.environ["CLAUDE_SECURITY_AUDIT_DIR"]).expanduser()
    home = Path.home()
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or home / ".local" / "state")
    return base / "claude-security-audit"


def short_list(profile: dict) -> list[str]:
    """Your sites and the shipped lists (no downloads): what Claude Code deny rules and Chrome's policy can hold."""
    p = plan(profile)
    if not p.on:
        return []
    shipped = {OWN} | {lst.id for lst in chosen(profile) if not lst.url}
    sources, _missing = _sources(profile)
    blocked = set(p.ordered)
    tops = {covered(s, blocked) for sid, sites in sources if sid in shipped for s in sites} - {None}
    return [s for s in p.ordered if s in tops]   # a shipped site a wider downloaded entry covers comes as that entry


def write_audit_file(profile: dict) -> Path | None:
    """blocked-sites.txt for /claude-security-audit, which reports the sites Claude Code can still fetch. Removed (when
    it is ours) while the filter is off."""
    path = audit_dir() / AUDIT_FILE
    sites = short_list(profile)
    if not sites:
        try:
            if path.read_text(encoding="utf-8").startswith(HEADER):
                path.unlink()
        except OSError:
            pass
        return None
    lines = [HEADER, "# Your own sites (web_filter.block) and the lists that ship with the stack, one per line; a site",
             "# covers its subdomains. Edit them in the tray: Settings > Blocked sites.", *sites]
    _write(path, "\n".join(lines) + "\n")
    return path


def claude_rules(sites: list[str]) -> list[str]:
    """Claude Code permission rules that stop WebFetch from reaching these sites and their subdomains."""
    return [rule for s in sites for rule in (f"WebFetch(domain:{s})", f"WebFetch(domain:*.{s})")]


def _chrome_existing() -> list[str]:
    if not IS_WINDOWS:
        return []
    import winreg

    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHROME_KEY) as k:
            i = 0
            while True:
                try:
                    _name, value, _kind = winreg.EnumValue(k, i)
                except OSError:
                    break
                out.append(str(value))
                i += 1
    except OSError:
        pass
    return out


def chrome_reg(sites: list[str], existing: list[str] | None = None) -> str:
    """A .reg file that sets Chrome's URLBlocklist policy for this Windows user (Claude in Chrome runs in Chrome): the
    entries already there first, then these sites, at most CHROME_MAX. Importing it replaces the key's values."""
    existing = _chrome_existing() if existing is None else existing
    entries = list(dict.fromkeys([*existing, *sites]))[:CHROME_MAX]
    esc = [e.replace("\\", "\\\\").replace('"', '\\"') for e in entries]
    return "\r\n".join([
        "Windows Registry Editor Version 5.00", "",
        "; Chrome URLBlocklist for this Windows user, written by `stack.py web-filter export`.",
        "; It keeps the entries the key held when the file was written. Check chrome://policy after importing.",
        f"[-HKEY_CURRENT_USER\\{CHROME_KEY}]", f"[HKEY_CURRENT_USER\\{CHROME_KEY}]",
        *[f'"{i}"="{e}"' for i, e in enumerate(esc, 1)], ""])


def export(profile: dict) -> dict[str, Path]:
    """Files for what the stack cannot enforce: the audit's list, Claude Code deny rules, Chrome's policy."""
    out: dict[str, Path] = {}
    audit = write_audit_file(profile)
    if audit:
        out["audit"] = audit
    sites = short_list(profile)
    rules = state_dir(profile) / "claude-webfetch-deny.json"
    _write(rules, json.dumps({"permissions": {"deny": claude_rules(sites)}}, indent=2) + "\n")
    out["claude"] = rules
    if IS_WINDOWS:
        reg = state_dir(profile) / "chrome-urlblocklist.reg"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(chrome_reg(sites), encoding="utf-16", newline="")   # regedit reads UTF-16 with a BOM
        out["chrome"] = reg
    return out


def dns_servers() -> list[str]:
    """This PC's DNS servers: those of the Windows adapters that are up, or /etc/resolv.conf. [] when unreadable."""
    if IS_WINDOWS:
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", WINDOWS_DNS_PS],
                               capture_output=True, text=True, timeout=30,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            text = r.stdout
        except (OSError, subprocess.TimeoutExpired):
            return []
    else:
        try:
            text = "\n".join(ln.split()[1] for ln in Path("/etc/resolv.conf").read_text().splitlines()
                             if ln.startswith("nameserver") and len(ln.split()) > 1)
        except OSError:
            return []
    out = []
    for token in text.split():
        try:
            addr = ipaddress.ip_address(token.strip().split("%", 1)[0])
        except ValueError:
            continue
        if addr.version == 6 and addr in ipaddress.ip_network("fec0::/10"):
            continue   # Windows' placeholder site-local servers, never a real resolver
        out.append(str(addr))
    return list(dict.fromkeys(out))


def provider(server: str) -> str | None:
    """The protective resolver a DNS server address belongs to, or None."""
    try:
        addr = ipaddress.ip_address(server)
    except ValueError:
        return None
    for name, nets in PROTECTIVE_DNS:
        for net in nets:
            n = ipaddress.ip_network(net)
            if addr.version == n.version and addr in n:
                return name
    return None


def protective_dns(servers: list[str] | None = None) -> list[str]:
    """Names of the protective resolvers among this PC's DNS servers."""
    return list(dict.fromkeys(p for p in map(provider, dns_servers() if servers is None else servers) if p))


def dns_text(servers: list[str] | None = None) -> str:
    """One sentence on whether this PC's DNS blocks unsafe sites, which covers every app (Claude Desktop included)."""
    servers = dns_servers() if servers is None else servers
    where = ("Windows Settings > Network & internet > your connection > DNS server assignment" if IS_WINDOWS
             else "your network settings")
    found = protective_dns(servers)
    if not servers:
        return "Could not read this PC's DNS servers."
    if found and all(provider(s) for s in servers):
        return f"This PC uses protective DNS ({', '.join(found)}), which covers every app."
    if found:
        return (f"Only some of this PC's DNS servers are protective ({', '.join(found)}); the others answer for unsafe "
                f"sites too. Set every server in {where}.")
    return (f"No protective DNS found (a router or a DoH setting may still filter). Quad9 (9.9.9.9) or Cloudflare for "
            f"Families (1.1.1.2), set in {where}, would cover every app on this PC.")


# ---------------------------------------------------------------- one call for the tray, setup and Apply

def maintain(profile: dict, force: bool = False, fetch=None) -> list[Result]:
    """Download what is due, rewrite Open WebUI's search filter and the audit's list. Safe to call often."""
    out = refresh(profile, force=force, fetch=fetch) if enabled(profile) else []
    try:
        text = sync_openwebui(profile)
        if text:
            out.append(Result("open_webui", True, text))
    except (OSError, sqlite3.Error) as e:
        out.append(Result("open_webui", False, f"could not update Open WebUI's web search filter: {e}"))
    try:
        write_audit_file(profile)
    except OSError as e:
        out.append(Result("audit", False, f"could not write the audit's list: {e}"))
    return out


def summary(profile: dict) -> str:
    """One sentence: what is blocked, where, and what is missing."""
    p = plan(profile)
    if not p.on:
        return "Off: Open WebUI reads any site."
    parts = [f"{len(p.search):,} sites in Open WebUI's web search filter"
             + (f" (of {p.total:,}; web_filter.max_sites)" if len(p.search) < p.total else ""),
             f"{len(p.fetch):,} in its page-fetch filter"]
    text = ", ".join(parts) + "."
    if p.missing:
        text += " Not downloaded yet: " + ", ".join(by_id()[m].title for m in p.missing) + "."
    if p.conflicts:
        text += " " + "; ".join(f"{a} stays blocked because {b} is blocked" for a, b in p.conflicts[:3]) + "."
    return text
