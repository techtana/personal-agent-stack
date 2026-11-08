"""Install the stack as its own app, apart from the source checkout.

Every path in the code is relative to the folder the code runs from (`stacklib.REPO`): the tray's pid file and log,
the services' data (`.run`), the gateway traces, `.env`, the machine profile, the generated configs, the shortcuts,
the Claude Desktop entry for recordings. Run from a git checkout, all of that lives in the checkout and points back
at it. `deploy()` therefore copies the app into its own folder (APP_DIR, `%LOCALAPPDATA%\\Programs\\AgentStack` on
Windows), gives it its own Python environment, brings the checkout's live data over once, and setup then runs from
that copy. After that nothing the app does reads or writes the checkout; installing again copies the newer code over
the app and keeps the app's data.

Layout of the app folder:
- the files git tracks in the checkout (without tests/), listed in MANIFEST so the next install can remove files the
  checkout no longer has;
- MARKER, which makes the folder an installed app (`is_app()`);
- its own `.venv`, `.env`, `machines/<HOST>.yaml`, `.run/`, `traces/`, `orchestrator/data/` and `memory/`, which an
  install never overwrites.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import yaml

from . import IS_WINDOWS, REPO, info, warn, which

MARKER = ".agent-stack-app.json"
MANIFEST = ".agent-stack-files.json"
ENV_HOME = "AGENT_STACK_HOME"
# Never copied from the checkout: tests stay with the source, the rest is per-checkout state or secrets.
SKIP_TOP = {"tests", ".git", ".venv", ".run", "traces", "node_modules", ".promptfoo", ".deep-architect"}
SKIP_PATHS = {".env", ".personal-terms", ".claude/settings.local.json", "infrastructure/.env"}
SKIP_PREFIXES = (".claude/worktrees/", "orchestrator/data/")
SKIP_SUFFIXES = (".pyc", ".pyo", ".db", ".db-shm", ".db-wal", ".swp")
# Tracked files the running app changes (orchestrator record_lesson, notes): copied only when the app has none yet.
KEEP_PREFIXES = ("memory/",)
# Data brought over once from the checkout, each only when the app does not have it yet. Inside the data dir
# (`.run` by default) everything except per-run state moves.
DATA_SKIP = {"pids", "logs", "install", "tray.show", "Agent Stack.lnk"}
DATA_TREES = ("traces", "orchestrator/data")


def default_app_dir() -> Path:
    if os.environ.get(ENV_HOME):
        return Path(os.environ[ENV_HOME]).expanduser()
    if IS_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Programs" / "AgentStack"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "agent-stack"


def is_app(root: Path = REPO) -> bool:
    """True when `root` is an installed app folder, not a source checkout."""
    return (Path(root) / MARKER).is_file()


def read_marker(root: Path = REPO) -> dict:
    try:
        return json.loads((Path(root) / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def installed_app() -> Path | None:
    """The installed app folder, when there is one and it is not the folder this code runs from."""
    d = default_app_dir()
    return d if is_app(d) and not _same(d, REPO) else None


def venv_python(root: Path, windowless: bool = False) -> Path:
    if IS_WINDOWS:
        return Path(root) / ".venv" / "Scripts" / ("pythonw.exe" if windowless else "python.exe")
    return Path(root) / ".venv" / "bin" / "python"


def _same(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _inside(child: Path, parent: Path) -> bool:
    c, p = os.path.normcase(os.path.abspath(child)), os.path.normcase(os.path.abspath(parent))
    return c == p or c.startswith(p.rstrip("\\/") + os.sep)


# ---------------------------------------------------------------- which files

def skipped(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    top = rel.split("/", 1)[0]
    if top in SKIP_TOP or rel in SKIP_PATHS or rel.startswith(SKIP_PREFIXES) or rel.endswith(SKIP_SUFFIXES):
        return True
    if "__pycache__/" in rel or rel.startswith("__pycache__"):
        return True
    if top == "machines" and rel.endswith(".yaml") and rel != "machines/_defaults.yaml":
        return True   # machine profiles are per computer; the profile in use is migrated separately
    return rel == MARKER or rel == MANIFEST


def _git_files(src: Path) -> list[str] | None:
    git = which("git")
    if not git or not (src / ".git").exists():
        return None
    try:
        r = subprocess.run([git, "-C", str(src), "ls-files", "-z"], capture_output=True, timeout=30, check=False,
                           creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode:
        return None
    return [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p]


def _walk_files(src: Path) -> list[str]:
    out = []
    for root, dirs, files in os.walk(src):
        rel_root = Path(root).relative_to(src).as_posix()
        rel_root = "" if rel_root == "." else rel_root + "/"
        dirs[:] = [d for d in dirs if not skipped(rel_root + d + "/x") and d != "__pycache__"]
        out += [rel_root + f for f in files]
    return out


def source_files(src: Path) -> list[str]:
    """Files of the app in `src`: what git tracks there (the published app, never local secrets or state), or the
    folder's files minus SKIP_* when it is not a git checkout (an unpacked download)."""
    files = _git_files(src)
    if files is None:
        files = _walk_files(src)
    return sorted(f for f in files if not skipped(f) and (src / f).is_file())


# ---------------------------------------------------------------- copy

def _differs(a: Path, b: Path) -> bool:
    if not b.exists():
        return True
    sa, sb = a.stat(), b.stat()
    if sa.st_size != sb.st_size:
        return True
    return a.read_bytes() != b.read_bytes()


def copy_app(src: Path, dst: Path, report=info) -> dict:
    """Copy the app's files from src to dst; remove files an earlier install copied that src no longer has.
    Returns counts: copied, unchanged, kept (KEEP_PREFIXES the app already has), removed."""
    src, dst = Path(src), Path(dst)
    files = source_files(src)
    old = set()
    try:
        old = set(json.loads((dst / MANIFEST).read_text(encoding="utf-8")).get("files") or [])
    except (OSError, ValueError):
        pass
    counts = {"copied": 0, "unchanged": 0, "kept": 0, "removed": 0}
    for i, rel in enumerate(files):
        s, d = src / rel, dst / rel
        if rel.startswith(KEEP_PREFIXES) and d.exists():
            counts["kept"] += 1
        elif _differs(s, d):
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
            counts["copied"] += 1
        else:
            counts["unchanged"] += 1
        if i % 50 == 0:
            report(f"copying the app: {i + 1} of {len(files)} files")
    for rel in sorted(old - set(files)):
        if rel.startswith(KEEP_PREFIXES) or skipped(rel):
            continue
        try:
            (dst / rel).unlink()
            counts["removed"] += 1
        except FileNotFoundError:
            pass
        except OSError as e:
            warn(f"could not remove {rel} from the app folder: {e}")
    (dst / MANIFEST).write_text(json.dumps({"files": files}, indent=0) + "\n", encoding="utf-8")
    return counts


# ---------------------------------------------------------------- data, once

def _copy_missing(src: Path, dst: Path) -> int:
    """Copy src (file or tree) to dst, file by file, skipping files dst already has. Returns files copied."""
    if src.is_file():
        if dst.exists():
            return 0
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return 1
    n = 0
    for f in (p for p in src.rglob("*") if p.is_file()):
        if "__pycache__" in f.parts:
            continue
        n += _copy_missing(f, dst / f.relative_to(src))
    return n


def _main_checkout(src: Path) -> Path:
    """Where the checkout's live data is: the main working tree when src is a linked git worktree (its profile,
    .env and data are there, see profile.machine_file), else src itself."""
    git = which("git")
    if git and (src / ".git").is_file():
        try:
            out = subprocess.run([git, "-C", str(src), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                 capture_output=True, text=True, timeout=10, check=False,
                                 creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        if out and Path(out).parent.is_dir():
            return Path(out).parent
    return src


def _profile_file(data_src: Path, src: Path, name: str) -> Path | None:
    for root in (src, data_src):
        p = root / "machines" / f"{name}.yaml"
        if p.is_file():
            return p
    return None


def migrate_data(src: Path, dst: Path, machine: str, report=info) -> list[str]:
    """Bring the checkout's .env, machine profile and data over to the app, each only where the app has none yet,
    so the app starts with the same secrets, settings, Open WebUI chats and usage history. Copies, never moves:
    the checkout keeps its files until the owner deletes them. Returns what was brought over."""
    src, dst = Path(src), Path(dst)
    data_src = _main_checkout(src)
    notes: list[str] = []
    env = next((r / ".env" for r in (src, data_src) if (r / ".env").is_file()), None)
    if env and _copy_missing(env, dst / ".env"):
        notes.append(".env")
    data_dir_rel = ".run"
    rebased = 0
    prof_src = _profile_file(data_src, src, machine)
    prof_dst = dst / "machines" / f"{machine}.yaml"
    if prof_src:
        doc = yaml.safe_load(prof_src.read_text(encoding="utf-8")) or {}
        data_dir = str(doc.get("data_dir") or ".run")
        if not prof_dst.exists():
            text = prof_src.read_text(encoding="utf-8")
            if Path(data_dir).is_absolute() and _inside(Path(data_dir), prof_src.parents[1]):
                # an absolute data_dir inside the checkout would keep the app writing there
                rel = Path(data_dir).relative_to(prof_src.parents[1]).as_posix()
                text = _replace_top_key(text, "data_dir", rel)
                data_dir = rel
            prof_dst.parent.mkdir(parents=True, exist_ok=True)
            prof_dst.write_text(text, encoding="utf-8", newline="\n")
            notes.append(f"machines/{machine}.yaml")
        if not Path(data_dir).is_absolute():
            data_dir_rel = data_dir
        else:
            data_dir_rel = ""   # outside the checkout: the app uses the same folder, nothing to move
    if data_dir_rel:
        run_src = data_src / data_dir_rel
        n = 0
        if run_src.is_dir():
            for entry in run_src.iterdir():
                if entry.name in DATA_SKIP or entry.suffix == ".lnk":
                    continue
                report(f"bringing over {data_dir_rel}/{entry.name}")
                copied = _copy_missing(entry, dst / data_dir_rel / entry.name)
                if copied and entry.is_dir():
                    rebased += _rebase_databases(dst / data_dir_rel / entry.name, data_src, dst)
                n += copied
        if n:
            notes.append(f"{n} files of {data_dir_rel}/ (Open WebUI, voice typing and the other services' data)")
    for tree in DATA_TREES:
        if (data_src / tree).is_dir():
            report(f"bringing over {tree}")
            n = _copy_missing(data_src / tree, dst / tree)
            if n:
                notes.append(f"{n} files of {tree}/")
                if tree != "traces":
                    rebased += _rebase_databases(dst / tree, data_src, dst)
    if rebased:
        notes.append(f"{rebased} paths in the copied databases now point into the app folder")
    return notes


def path_variants(old: Path, new: Path) -> list[tuple[str, str]]:
    """(old, new) prefix pairs as a database may hold them: native, with forward slashes, and JSON-escaped. Each
    ends in a separator, so C:\\src never matches C:\\src-other."""
    o, n = str(old).rstrip("\\/"), str(new).rstrip("\\/")
    pairs = [(o + os.sep, n + os.sep)]
    if IS_WINDOWS or "\\" in o:
        pairs.append((o.replace("\\", "/") + "/", n.replace("\\", "/") + "/"))
        pairs.append((o.replace("\\", "\\\\") + "\\\\", n.replace("\\", "\\\\") + "\\\\"))
    return list(dict.fromkeys(pairs))


def rebase_sqlite(db: Path, old: Path, new: Path) -> int:
    """Rewrite absolute paths under `old` to `new` in every text column of a SQLite database (Open WebUI keeps each
    upload's full path in file.path, so a copied database would go on reading the checkout's uploads folder).
    Returns the number of cells changed."""
    import sqlite3

    changed = 0
    con = sqlite3.connect(str(db))
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for t in tables:
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')
                    if (r[2] or "").upper() in ("", "TEXT", "JSON", "VARCHAR") or "CHAR" in (r[2] or "").upper()]
            for c in cols:
                for a, b in path_variants(old, new):
                    cur = con.execute(f'UPDATE "{t}" SET "{c}" = replace("{c}", ?, ?) WHERE instr("{c}", ?) > 0',
                                      (a, b, a))
                    changed += max(cur.rowcount, 0)
        con.commit()
    finally:
        con.close()
    return changed


def _rebase_databases(root: Path, old: Path, new: Path) -> int:
    n = 0
    for db in [p for p in root.rglob("*") if p.is_file() and p.suffix in (".db", ".sqlite", ".sqlite3")]:
        if ".bak" in db.name:
            continue   # backups stay byte-for-byte what they were
        try:
            n += rebase_sqlite(db, old, new)
        except Exception as e:  # noqa: BLE001 - a database we cannot open keeps its old paths; say so
            warn(f"could not update the paths in {db}: {e}")
    return n


def _replace_top_key(text: str, key: str, value: str) -> str:
    import re

    rendered = yaml.safe_dump(value, default_style="'").strip().removesuffix("...").strip()
    pat = re.compile(rf"^{re.escape(key)}:[^\n]*$", re.M)
    if pat.search(text):
        return pat.sub(f"{key}: {rendered}", text, count=1)
    return text.rstrip("\n") + f"\n{key}: {rendered}\n"


# ---------------------------------------------------------------- running stacks, environment

def stop_stack(root: Path, python: Path | None = None) -> None:
    """Stop the tray and services that run from `root` (Ollama keeps running), so the checkout's stack and the app's
    never hold the same ports, and the data copies are taken while nothing writes them."""
    python = python or venv_python(root)
    script = Path(root) / "scripts" / "stack.py"
    if not python.exists() or not script.exists() or not (Path(root) / ".run").is_dir():
        return
    flags = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
    # --here: a checkout's `tray` hands over to the installed app otherwise. Code from before --here existed
    # rejects it (argparse exits 2), so that is retried without it.
    def run(*args: str) -> int | None:
        try:
            return subprocess.run([str(python), str(script), *args], cwd=root, capture_output=True, text=True,
                                  timeout=180, check=False, creationflags=flags, env=_clean_env()).returncode
        except (OSError, subprocess.TimeoutExpired) as e:
            warn(f"could not run `stack.py {' '.join(args)}` in {root}: {e}")
            return None

    if run("tray", "--stop", "--here") == 2:
        run("tray", "--stop")
    run("down")


def _clean_env() -> dict[str, str]:
    """This process's environment without the variables that would point uv at the checkout's environment."""
    return {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONHOME", "PYTHONPATH")}


def make_venv(dst: Path, report=info) -> None:
    """The app's own .venv: on a signed Python where Smart App Control needs one (scripts/signed-venv.ps1), then
    `uv sync` with the app folder as the project."""
    uv = which("uv")
    if not uv:
        raise RuntimeError("uv is not installed; run install.cmd, which installs it")
    env = _clean_env()
    if IS_WINDOWS:
        report("checking that the app's Python environment is signed (Smart App Control)")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(dst / "scripts" / "signed-venv.ps1"), "-Repo", str(dst)], cwd=dst, env=env, check=False)
        if r.returncode:
            raise RuntimeError("scripts/signed-venv.ps1 failed for the app folder; see the messages above")
    report("preparing the app's Python environment (uv sync)")
    r = subprocess.run([uv, "sync", "--quiet", "--project", str(dst)], cwd=dst, env=env, check=False)
    if r.returncode or not venv_python(dst).exists():
        raise RuntimeError(f"uv sync in {dst} failed (exit code {r.returncode}); see the messages above")


def _commit(src: Path) -> str:
    git = which("git")
    if not git:
        return ""
    try:
        r = subprocess.run([git, "-C", str(src), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                           timeout=10, check=False, creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def check_target(src: Path, dst: Path) -> None:
    if _same(src, dst):
        raise ValueError(f"{dst} is the folder the installer runs from; choose another app folder ({ENV_HOME})")
    if _inside(dst, src):
        raise ValueError(f"the app folder {dst} is inside the source folder {src}; choose one outside it ({ENV_HOME})")
    if _inside(src, dst):
        raise ValueError(f"the source folder {src} is inside the app folder {dst}; choose another app folder ({ENV_HOME})")
    if dst.exists() and any(dst.iterdir()) and not is_app(dst):
        raise ValueError(f"{dst} already holds other files and is not an Agent Stack app; choose an empty folder ({ENV_HOME})")


def deploy(src: Path = REPO, dst: Path | None = None, machine: str | None = None, behind: str = "",
           venv: bool = True, stop: bool = True, report=info) -> Path:
    """Install (or update) the app from the checkout `src` into `dst`. Returns the app folder."""
    from . import profile as prof

    src = Path(src).resolve()
    dst = Path(dst or default_app_dir()).expanduser().resolve()
    check_target(src, dst)
    machine = machine or prof.machine_name()
    if stop:
        report("stopping the stack that runs from the source folder, and an earlier install's")
        stop_stack(_main_checkout(src))
        if not _same(_main_checkout(src), src):
            stop_stack(src)
        if is_app(dst):
            stop_stack(dst)
    dst.mkdir(parents=True, exist_ok=True)
    first_installed = read_marker(dst).get("first_installed_at") or time.strftime("%Y-%m-%d %H:%M:%S")
    counts = copy_app(src, dst, report)
    info(f"app: {counts['copied']} files copied, {counts['unchanged']} unchanged, {counts['removed']} removed "
         f"({dst})")
    moved = migrate_data(src, dst, machine, report)
    if moved:
        info(f"app: brought over {', '.join(moved)} from the source folder (the originals stay; delete them when "
             "the app works)")
    (dst / MARKER).write_text(json.dumps({
        "source_commit": _commit(src),
        "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "first_installed_at": first_installed,
        "behind": behind,
    }, indent=1) + "\n", encoding="utf-8")
    if venv:
        make_venv(dst, report)
    return dst


def run_in_app(app: Path, args: list[str], detached: bool = False, env: dict | None = None) -> int:
    """Run `stack.py <args>` (or a script path as args[0]) with the app's own Python, from the app folder."""
    python = venv_python(app)
    first = args[0] if args else ""
    argv = [str(python), str(app / first)] + args[1:] if first.endswith(".py") else \
        [str(python), str(app / "scripts" / "stack.py"), *args]
    run_env = {**_clean_env(), **(env or {})}
    if not detached:
        return subprocess.run(argv, cwd=app, env=run_env, check=False).returncode
    kwargs: dict = {"cwd": app, "env": run_env, "stdin": subprocess.DEVNULL}
    if IS_WINDOWS:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7   # SW_SHOWMINNOACTIVE, like `start /min`; the installer hides it at once
        kwargs.update(startupinfo=si, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(argv, **kwargs)
    return 0

