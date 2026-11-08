"""The repository is public: no tracked or about-to-be-added file may name this computer or its owner.

The terms come from the machine running the test (computer name, account name, home folder name, git user.email) plus
the lines of `.personal-terms`, a gitignored file for anything else private (a real name, other computers). The test
therefore stores nothing personal, and its failure message lists only file:line, never the term it found.
"""
from __future__ import annotations

import getpass
import os
import re
import socket
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# Account and host names too common to point at anyone.
GENERIC = {"admin", "administrator", "build", "default", "guest", "home", "localhost", "owner", "public", "root",
           "runner", "test", "ubuntu", "user", "users", "vagrant"}


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8",
                          check=False).stdout


def personal_terms() -> set[str]:
    terms = {os.environ.get("COMPUTERNAME", ""), socket.gethostname().split(".")[0], os.environ.get("USERNAME", ""),
             os.environ.get("USER", ""), Path.home().name, _git("config", "user.email").strip()}
    try:
        terms.add(getpass.getuser())
    except (KeyError, OSError):   # no account name on some CI runners
        pass
    extra = REPO / ".personal-terms"
    if extra.exists():
        terms |= {ln.strip() for ln in extra.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")}
    return {t for t in terms if len(t) >= 4 and t.lower() not in GENERIC}


def find_terms(terms: set[str], files: list[str], root: Path = REPO) -> list[str]:
    """file:line (or `file: path`) for every occurrence of a term, case-insensitive and not inside a longer word."""
    if not terms:
        return []
    pattern = re.compile("|".join(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])"
                                  for t in sorted(terms, key=len, reverse=True)), re.IGNORECASE)
    hits = []
    for rel in files:
        if pattern.search(rel):
            hits.append(f"{rel}: in the path")
        try:
            data = (root / rel).read_bytes()
        except OSError:   # deleted in the working tree, or a directory (submodule)
            continue
        if b"\0" in data[:8192]:
            continue      # binary
        hits += [f"{rel}:{n}" for n, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1)
                 if pattern.search(line)]
    return hits


class PersonalInfoTest(unittest.TestCase):
    def test_finder_matches_whole_words_only(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.md").write_text("path C:\\Users\\Pat\\x and PAT again\npatience, Patrick\n", encoding="utf-8")
            Path(d, "pat-notes.md").write_text("nothing\n", encoding="utf-8")
            Path(d, "b.bin").write_bytes(b"\0Pat")
            self.assertEqual(find_terms({"Pat"}, ["a.md", "pat-notes.md", "b.bin"], Path(d)),
                             ["a.md:1", "pat-notes.md: in the path"])

    def test_tracked_files_do_not_name_this_machine_or_its_owner(self):
        terms = personal_terms()
        if not terms:
            self.skipTest("no personal terms on this machine")
        # Tracked files plus new files `git add -A` would pick up; ignored files (.env, machines/<HOST>.yaml) are local.
        files = [f for f in _git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0") if f]
        hits = find_terms(terms, files)
        self.assertEqual(hits, [], "this computer's or its owner's name appears in files git would publish (the term is "
                                   "not printed; search the lines below):\n" + "\n".join(hits[:50]))


if __name__ == "__main__":
    unittest.main()
