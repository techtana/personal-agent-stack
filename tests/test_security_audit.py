"""Tests for the claude-security-audit skill's script (.claude/skills/claude-security-audit/scripts/audit.py).

No network and no real home folder: every test builds a Ctx with a temporary home, state folder and environment and
an empty global git config, so the owner's real identity and settings are never read. The fixture identity is put
together at run time, so no address-like string sits in this file (the audit scans this repository too).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / ".claude" / "skills" / "claude-security-audit"
_spec = importlib.util.spec_from_file_location("claude_security_audit", SKILL / "scripts" / "audit.py")
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

USER = "fixtureuser"
EMAIL = "owner.fixture" + "@" + "mailhost-fixture.net"
OTHER = "someone.else" + "@" + "corp-fixture.org"
NAME = "Fixture " + "Ownerperson"


def make_ctx(tmp: str, system: str = "windows", cwd=None, offline: bool = True) -> "audit.Ctx":
    home = Path(tmp) / "home" / USER
    home.mkdir(parents=True, exist_ok=True)
    gitcfg = Path(tmp) / "gitconfig"
    if not gitcfg.exists():
        gitcfg.write_text("", encoding="utf-8")
    npmrc = Path(tmp) / "npmrc"
    npmrc.write_text("", encoding="utf-8")
    keep = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "SystemRoot", "COMSPEC", "PATHEXT", "TEMP", "TMP")
            if k in os.environ}
    env = {**keep, "USERNAME": USER, "USER": USER, "HOME": str(home), "USERPROFILE": str(home),
           "APPDATA": str(home / "AppData" / "Roaming"), "LOCALAPPDATA": str(home / "AppData" / "Local"),
           "PROGRAMFILES": str(Path(tmp) / "ProgramFiles"), "GIT_CONFIG_GLOBAL": str(gitcfg), "GIT_CONFIG_NOSYSTEM": "1",
           "NPM_CONFIG_USERCONFIG": str(npmrc), "AUDIT_NO_REGISTRY": "1", "COMPUTERNAME": "BUILDBOX"}
    return audit.Ctx(home=home, state=Path(tmp) / "state", cwd=cwd or tmp, offline=offline, environ=env, system=system)


def write_account(ctx, email=EMAIL, name=NAME, display="Fix") -> None:
    (ctx.home / ".claude.json").write_text(json.dumps(
        {"oauthAccount": {"emailAddress": email, "fullName": name, "displayName": display}, "projects": {}}),
        encoding="utf-8")


def git(ctx, *args, cwd=None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=ctx.environ, capture_output=True, text=True, check=True).stdout


def identity_free(text: str) -> bool:
    low = text.lower()
    return EMAIL.lower() not in low and NAME.lower() not in low and not re.search(
        r"(?i)(?<![a-z0-9])" + USER + r"(?![a-z0-9])", text) and "ownerperson" not in low


class Identity(unittest.TestCase):
    def test_discovers_account_and_git_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(tmp)
            write_account(ctx)
            Path(tmp, "gitconfig").write_text("[user]\n\temail = 12345+someone@users.noreply.github.com\n", encoding="utf-8")
            ident = audit.discover_identity(ctx)
            self.assertEqual(ident.emails, {EMAIL.lower()})  # the no-reply git address is not identity
            self.assertIn(NAME, ident.names)
            self.assertIn("Ownerperson", ident.parts)
            self.assertIn("Fix", ident.short)
            self.assertTrue(ident.bare_username)

    def test_common_user_names_are_only_matched_in_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(tmp)
            ctx.environ["USERNAME"] = "admin"
            self.assertFalse(audit.discover_identity(ctx).bare_username)

    def test_redactor_hides_every_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(tmp)
            write_account(ctx)
            audit.set_identity(ctx, audit.discover_identity(ctx))
            text = "\n".join([
                f"mail {EMAIL} or {EMAIL.upper()}", f"by {NAME} and fixture.ownerperson", "signed Fix",
                rf"C:\Users\{USER}\Docs", rf'"C:\\Users\\{USER}\\Docs"', f"Read(//c/Users/{USER}/OneDrive/**)",
                f"/c/Users/{USER}/x", f"/home/{USER}/x", f"~/.claude/projects/C--Users-{USER}-proj/memory",
                f"account {USER} owns it", f"cc {OTHER}", "key sk-ant-" + "a" * 24,
                "bot 41898282+github-actions[bot]@users.noreply.github.com", "art icon@2x.png", "fix the build stays",
                "org 0f8fad5b-d9cb-469f-a165-70867728950e billing 0A1B2C-3D4E5F-6A7B8C",
                "skills/synced/0f8fad5b-d9cb-469f-a165-70867728950e_1b4e28ba-2fa1-11d2-883f-0016d3cca427/x"])
            out = ctx.red(text)
            self.assertTrue(identity_free(out), out)
            for placeholder in ("[owner-email]", "[owner-name]", "[user]", "[email]", "[secret]", "[id]", "~"):
                self.assertIn(placeholder, out)
            self.assertNotIn("0f8fad5b", out)
            self.assertNotIn("1b4e28ba", out)
            self.assertNotIn("0A1B2C-3D4E5F", out)
            self.assertEqual(audit.red_rule(ctx, f"Grep(//c/Users/{USER}/OneDrive/**)"), "Grep(//c/Users/[user]/OneDrive/**)")
            self.assertIn("users.noreply.github.com", out)
            self.assertIn("icon@2x.png", out)
            self.assertIn("fix the build stays", out)  # the short display name "Fix" is matched by exact case only
            self.assertNotIn("signed Fix", out)


class Rules(unittest.TestCase):
    def test_deny_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(tmp)
            deny = [("Read(~/.ssh/**)", "user"), ("Read(//**/.env)", "user"), ("Read(.npmrc)", "user"),
                    (f"Read(//c/Users/{USER}/OneDrive/**)", "user")]
            self.assertTrue(audit.covered(ctx, deny, ctx.home / ".ssh" / "id_ed25519"))
            self.assertFalse(audit.covered(ctx, deny, ctx.home / ".aws" / "credentials"))
            self.assertTrue(audit.covered(ctx, deny, "D:/work/app/.env"))
            self.assertTrue(audit.covered(ctx, deny, f"C:/Users/{USER}/OneDrive/notes.txt"))
            self.assertFalse(audit.covered(ctx, deny, ctx.home / ".npmrc"))  # relative: current project only
            self.assertTrue(audit.relative_covers(deny, ".npmrc"))
            linux = make_ctx(tmp, system="linux")
            self.assertTrue(audit.covered(linux, [("Read(//**/.env)", "user")], "/srv/app/.env"))

    def test_broad_allow(self):
        broad = ["Bash", "Bash(*)", "Bash(uv run *)", "Bash(python:*)", "Bash(curl:*)", "Bash(npx *)", "WebFetch",
                 "mcp__*", "Edit", "PowerShell(*)", "Bash(uv run --no-project python -c ' *)",
                 "Bash(powershell -NoProfile -Command *)"]
        narrow = ["Bash(uv run scripts/stack.py status*)", "Bash(git status:*)", "WebFetch(domain:example.com)",
                  "Bash(curl -s http://127.0.0.1:4000/health)", "Bash(npm test)", "mcp__orchestrator__get_job"]
        match = lambda r: any(rx.search(r) for rx, _ in audit.BROAD_ALLOW)  # noqa: E731
        for r in broad:
            self.assertTrue(match(r), r)
        for r in narrow:
            self.assertFalse(match(r), r)

    def test_permission_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(tmp)
            (ctx.home / ".ssh").mkdir()
            (ctx.home / ".claude").mkdir()
            (ctx.home / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
            layer = audit.Layer("user", ctx.home / ".claude" / "settings.json",
                                {"permissions": {"deny": ["Grep(~/secret/**)"], "allow": ["Bash(uv run *)"]}})
            ids = {f["id"]: f for f in audit.check_permissions(ctx, [layer], ctx.home / ".claude.json")}
            self.assertIn("DENY-SECRETS", ids)
            self.assertIn("Read(~/.ssh/**)", ids["DENY-SECRETS"]["fix"])
            self.assertIn("DENY-NOOP", ids)
            self.assertIn("BROAD-ALLOW", ids)
            self.assertIn("ENV-SCRUB", ids)
            layer.data["permissions"]["deny"] += ["Read(~/.ssh/**)", "Read(~/.claude/.credentials.json)"]
            layer.data["env"] = {"CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1"}
            ids = {f["id"] for f in audit.check_permissions(ctx, [layer], ctx.home / ".claude.json")}
            self.assertNotIn("DENY-SECRETS", ids)
            self.assertNotIn("ENV-SCRUB", ids)

    def test_data_sharing_and_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(tmp)
            empty = [audit.Layer("user", ctx.home / "s.json", {})]
            ids = {f["id"] for f in audit.check_data_sharing(ctx, empty, {})}
            self.assertTrue({"FEEDBACK-UPLOAD", "ERROR-REPORTS", "TELEMETRY", "CONNECTORS"} <= ids)
            off = [audit.Layer("user", ctx.home / "s.json", {"env": {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "0"}})]
            ids = {f["id"] for f in audit.check_data_sharing(ctx, off, {"vscode": "2.1.319"})}
            self.assertNotIn("FEEDBACK-UPLOAD", ids)  # any value, even 0, turns the traffic off
            self.assertIn("AUTO-MODE-SERVER", ids)
            ids = {f["id"] for f in audit.check_retention(ctx, empty)}
            self.assertEqual(ids, {"TRANSCRIPT-RETENTION", "DESKTOP-RETENTION"})


class Mcp(unittest.TestCase):
    def test_runner_package(self):
        rp = audit.runner_package
        self.assertEqual(rp("npx", ["-y", "some-mcp"])[:3], ("npm", "some-mcp", None))
        self.assertEqual(rp("npx.cmd", ["-y", "@scope/tool@1.2.3"])[:3], ("npm", "@scope/tool", "1.2.3"))
        self.assertIsNone(rp("npx", ["-y", "tool@latest"])[2])
        self.assertEqual(rp("cmd", ["/c", "npx", "-y", "tool@2.0.0"])[2], "2.0.0")
        self.assertEqual(rp("uvx", ["mcp-logseq"])[:3], ("PyPI", "mcp-logseq", None))
        self.assertEqual(rp("uvx", ["mcp-x==0.3.1"])[2], "0.3.1")
        self.assertEqual(rp("uvx", ["--from", "pkg==1.0", "cmd"])[:3], ("PyPI", "pkg", "1.0"))
        self.assertEqual(rp("uv", ["tool", "run", "pkg@1.2"])[2], "1.2")
        self.assertIsNone(rp(r"C:\tools\relay_win.exe", ["--port", "1"]))

    def test_literal_secret(self):
        self.assertFalse(audit.literal_secret("Authorization", "Bearer ${ORCHESTRATOR_BEARER}"))
        self.assertFalse(audit.literal_secret("TOKEN", "${TOKEN}"))
        self.assertTrue(audit.literal_secret("API_KEY", "abcd1234efgh5678"))
        self.assertFalse(audit.literal_secret("DEBUG_LEVEL", "verbose-logging-on"))
        self.assertFalse(audit.literal_secret("PASSWORD", "true"))
        self.assertTrue(audit.literal_secret("LITELLM_MASTER_KEY", "sk-" + "Q" * 48))
        self.assertTrue(audit.literal_secret("GATEWAY", "sk-ant-" + "x" * 30))  # a token's shape, whatever the name
        self.assertTrue(audit.literal_secret("OPENAI_KEY", "plain-value-123"))


class DocsAndChangelog(unittest.TestCase):
    SETTINGS = ("| [`cleanupPeriodDays`](#cleanupperioddays) | Choose how many days Claude Code keeps "
                "[transcripts](https://x/y) | Privacy and telemetry | Any file |\n"
                "| [`theme`](#theme) | Pick colours | Interface and terminal | User |\n")
    ENV = "| `DISABLE_TELEMETRY` | Set to `1` to opt out of telemetry |\n| `FOO_BAR` | Something else |\n"
    CHANGELOG = ("# Changelog\n\n## 2.1.3\n\n- Fixed a Bash permission bypass in compound commands\n- Improved spinner\n\n"
                 "## 2.1.2\n\n- Added `CLAUDE_CODE_NEW_SWITCH` to turn something off\n\n## 2.1.1\n\n- Fixed MCP reconnect\n")

    def test_parse_and_diff(self):
        s = audit.parse_settings_reference(self.SETTINGS)
        self.assertEqual(s["cleanupPeriodDays"]["category"], "Privacy and telemetry")
        self.assertNotIn("](", s["cleanupPeriodDays"]["desc"])
        e = audit.parse_env_vars(self.ENV)
        self.assertEqual(set(e), {"DISABLE_TELEMETRY", "FOO_BAR"})
        prev = {"cleanupPeriodDays": audit.sha(s["cleanupPeriodDays"]["desc"])}
        d = audit.docs_diff(prev, s, {"cleanupPeriodDays"})
        self.assertEqual(set(d["new"]), {"theme"})
        self.assertEqual(d["changed"], {})
        s["cleanupPeriodDays"]["desc"] = "changed text"
        self.assertIn("cleanupPeriodDays", audit.docs_diff(prev, s, {"cleanupPeriodDays"})["changed"])

    def test_changelog(self):
        entries = audit.parse_changelog(self.CHANGELOG)
        self.assertEqual([v for v, _ in entries], ["2.1.3", "2.1.2", "2.1.1"])
        lines = audit.changelog_since(entries, "2.1.1")
        self.assertEqual([(x["version"], x["kind"]) for x in lines], [("2.1.3", "security"), ("2.1.2", "new-setting")])
        self.assertEqual(audit.changelog_kind("Improved spinner"), None)
        self.assertEqual(audit.changelog_kind("Added `permissions.denyInsteadOfPrompting` setting"), "new-setting")
        self.assertEqual(audit.changelog_kind("Fixed /share sending the transcript"), "privacy")
        self.assertNotEqual(audit.changelog_kind("Fixed a memory leak in the regex library"), "security")
        for line in ("Fixed a sandbox escape when creating a worktree",
                     "Fixed a case where a `sed` command could skip the permission check in auto mode",
                     "Fixed a case where Bash deny and ask rules missed commands written with quoted words"):
            self.assertEqual(audit.changelog_kind(line), "security", line)
        many = [{"kind": "policy", "version": "2.1.9", "text": str(i)} for i in range(60)] + \
               [{"kind": "security", "version": "2.1.1", "text": "s"}]
        shown = audit.changelog_for_summary(many)
        self.assertEqual(shown[0]["kind"], "security")
        self.assertEqual(len(shown), 45)
        self.assertNotEqual(audit.changelog_kind("Improved titles for sessions started with `/security-review`"),
                            "security")
        self.assertGreater(audit.vtuple("2.1.10"), audit.vtuple("2.1.9"))

    def test_osv_finding(self):
        d = {"summary": "Permission bypass", "aliases": ["CVE-2026-0001"], "published": "2026-10-01T00:00:00Z",
             "database_specific": {"severity": "HIGH"},
             "affected": [{"package": {"name": audit.CC_NPM}, "ranges": [{"events": [{"introduced": "0"},
                                                                                      {"fixed": "2.1.310"}]}]}]}
        f = audit.osv_finding({"ecosystem": "npm", "name": audit.CC_NPM, "version": "2.1.302"}, "GHSA-test", d)
        self.assertEqual((f["severity"], f["fixed"], f["aliases"]), ("high", ["2.1.310"], ["CVE-2026-0001"]))


class ScanAndScrub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ctx = make_ctx(self.tmp.name)
        write_account(self.ctx)
        repo = Path(self.tmp.name) / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "docs").mkdir()
        (repo / "ProjectSettings").mkdir()
        files = {
            "package.json": json.dumps({"name": "x", "author": f"{NAME} <{EMAIL}>"}),
            "LICENSE": f"MIT License\n\nCopyright (c) 2026 {NAME}\n",
            "scripts/geo.py": ("import requests, subprocess\n"
                               f"HEADERS = {{'User-Agent': 'geo/1 ({EMAIL})'}}\n"
                               "who = subprocess.run(['git', 'config', 'user.email'], capture_output=True).stdout\n"
                               "requests.get('https://nominatim.openstreetmap.org/search', headers=HEADERS)\n"),
            "docs/notes.md": f"Files live in C:\\Users\\{USER}\\Projects and {USER} owns them. Ask {OTHER}.\n",
            "ProjectSettings/ProjectSettings.asset": f"PlayerSettings:\n  companyName: {NAME}\n  organizationId: unity_abc\n",
            "pnpm-lock.yaml": f"contact: {OTHER}\n",
        }
        for rel, text in files.items():
            (repo / rel).write_text(text, encoding="utf-8")
        git(self.ctx, "init", "-q", str(repo))
        git(self.ctx, "add", "-A", cwd=repo)
        git(self.ctx, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "fixture", cwd=repo)
        (repo / "docs" / "draft.md").write_text(f"draft by {EMAIL}\n", encoding="utf-8")  # untracked: skipped
        memory = self.ctx.home / ".claude" / "projects" / "p" / "memory"
        memory.mkdir(parents=True)
        (memory / "note.md").write_text(f"Owner mail: {EMAIL}\nRepo at C:\\Users\\{USER}\\repo\n", encoding="utf-8")
        synced = self.ctx.home / ".claude" / "skills" / "synced" / "a_b" / "job-search"
        synced.mkdir(parents=True)
        (synced / "SKILL.md").write_text(f"Apply as {NAME} ({EMAIL})\n", encoding="utf-8")
        self.repo = repo
        self.ctx.cwd = repo
        audit.set_identity(self.ctx, audit.discover_identity(self.ctx))

    def tearDown(self):
        self.tmp.cleanup()

    def test_scan_classifies_findings(self):
        scan = audit.identity_scan(self.ctx, [self.repo], [])
        kinds = {(i["file"].split("/", 1)[-1], i["kind"], i["action"]) for i in scan["items"]}
        self.assertIn(("package.json", "owner-email", "replace"), kinds)
        self.assertIn(("package.json", "owner-name", "replace"), kinds)
        self.assertIn(("LICENSE", "owner-name", "replace"), kinds)
        self.assertIn(("scripts/geo.py", "contact-email", "replace"), kinds)
        self.assertIn(("scripts/geo.py", "contact-from-git", "report"), kinds)
        self.assertIn(("docs/notes.md", "username-path", "replace"), kinds)
        self.assertIn(("docs/notes.md", "username", "replace"), kinds)
        self.assertIn(("docs/notes.md", "other-email", "report"), kinds)
        self.assertIn(("ProjectSettings/ProjectSettings.asset", "unity-org", "report"), kinds)
        self.assertFalse(any(i["file"].endswith("pnpm-lock.yaml") for i in scan["items"]))
        classes = {i["class"] for i in scan["items"]}
        self.assertTrue({"published", "instructions", "kept"} <= classes)
        self.assertTrue(identity_free(json.dumps(scan)), "scan output must be redacted")
        unity = next(i for i in scan["items"] if i["kind"] == "unity-org")
        self.assertEqual(unity["context"], "organizationId: [id]")
        ids = {f["id"] for f in audit.identity_findings(self.ctx, scan)}
        self.assertTrue({"IDENTITY-PUBLISHED", "IDENTITY-INSTRUCTIONS", "IDENTITY-CONTACT-API", "OTHER-EMAILS",
                         "UNITY-ORG", "IDENTITY-KEPT"} <= ids)

    def test_context_shows_the_match_and_checkout(self):
        long_line = "x" * 300 + f" write to {OTHER} please"
        (self.repo / "docs" / "long.md").write_text(long_line + "\n", encoding="utf-8")
        git(self.ctx, "add", "docs/long.md", cwd=self.repo)
        git(self.ctx, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "long", cwd=self.repo)
        scan = audit.identity_scan(self.ctx, [self.repo], [])
        item = next(i for i in scan["items"] if i["file"].endswith("docs/long.md"))
        self.assertIn("[email]", item["context"])
        self.assertTrue(item["current"])
        self.assertTrue(item["checkout"])

    def test_findings_and_scrub_name_other_checkouts(self):
        scan = audit.identity_scan(self.ctx, [self.repo], [])
        elsewhere = dict(next(i for i in scan["items"] if i["file"].endswith("package.json")))
        elsewhere.update(file="repo/docs/only-there.md", checkout="D:/other/repo", current=False)
        scan["items"].append(elsewhere)
        pub = next(f for f in audit.identity_findings(self.ctx, scan) if f["id"] == "IDENTITY-PUBLISHED")
        self.assertIn("In this checkout:", pub["detail"])
        self.assertIn("In D:/other/repo:", pub["detail"])
        self.assertIn("already has the fix", pub["fix"])
        self.ctx.state.mkdir(parents=True, exist_ok=True)
        (self.ctx.state / "last-run.json").write_text(json.dumps({"identity": {"items": scan["items"]}}), encoding="utf-8")
        import contextlib
        import io
        import types
        buf = io.StringIO()
        args = types.SimpleNamespace(apply=False, repo=[str(self.repo)], local_only=False, no_local=True,
                                     include_dirty=False)
        with contextlib.redirect_stdout(buf):
            audit.cmd_scrub(self.ctx, args)
        notes = json.loads(buf.getvalue())["notes"]
        self.assertTrue(any("D:/other/repo" in n for n in notes), notes)

    def test_scrub_dry_run_then_apply(self):
        before = {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file() and ".git" not in p.parts}
        dry = audit.scrub(self.ctx, [self.repo], local=True, published=True, apply=False, include_dirty=False)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        status = {r["file"].split("/")[-1]: r["status"] for r in dry["files"]}
        self.assertEqual(status["package.json"], "would change")
        self.assertEqual(status["draft.md"], "skipped: the file has uncommitted changes")
        self.assertEqual(status["SKILL.md"], "kept on purpose")
        self.assertTrue(identity_free(json.dumps(dry)))
        audit.scrub(self.ctx, [self.repo], local=True, published=True, apply=True, include_dirty=False)
        pkg = (self.repo / "package.json").read_text(encoding="utf-8")
        self.assertIn("Your Name <you@example.com>", pkg)
        self.assertIn("Copyright (c) 2026 The repo Authors", (self.repo / "LICENSE").read_text(encoding="utf-8"))
        notes = (self.repo / "docs" / "notes.md").read_text(encoding="utf-8")
        self.assertIn(r"%USERPROFILE%\Projects and %USERNAME% owns them", notes)
        self.assertIn(OTHER, notes)  # other people's addresses are reported, never replaced
        self.assertIn("companyName: DefaultCompany",
                      (self.repo / "ProjectSettings" / "ProjectSettings.asset").read_text(encoding="utf-8"))
        self.assertIn("you@example.com", (self.repo / "scripts" / "geo.py").read_text(encoding="utf-8"))
        note = (self.ctx.home / ".claude" / "projects" / "p" / "memory" / "note.md").read_text(encoding="utf-8")
        self.assertTrue(identity_free(note), note)
        self.assertIn(EMAIL, (self.repo / "docs" / "draft.md").read_text(encoding="utf-8"))  # uncommitted: untouched
        synced = self.ctx.home / ".claude" / "skills" / "synced" / "a_b" / "job-search" / "SKILL.md"
        self.assertIn(EMAIL, synced.read_text(encoding="utf-8"))  # kept on purpose
        for rel in ("package.json", "LICENSE", "docs/notes.md", "scripts/geo.py", "ProjectSettings/ProjectSettings.asset"):
            self.assertTrue(identity_free((self.repo / rel).read_text(encoding="utf-8").replace(OTHER, "")), rel)

    def test_collect_report_state_and_drift(self):
        r = audit.collect(self.ctx, [], include_projects=False, include_versions=False)
        self.assertTrue(r["first_run"])
        report, last = audit.write_outputs(self.ctx, r)
        for path in (report, last):
            self.assertTrue(identity_free(path.read_text(encoding="utf-8")), path.name)
        self.assertEqual(audit.cmd_mark_reviewed(self.ctx, None), 0)
        state = (self.ctx.state / "state.json").read_text(encoding="utf-8")
        self.assertTrue(identity_free(state))
        r2 = audit.collect(self.ctx, [], include_projects=False, include_versions=False)
        self.assertFalse(r2["first_run"])
        self.assertEqual(r2["drift"], {})
        cj = json.loads((self.ctx.home / ".claude.json").read_text(encoding="utf-8"))
        cj["mcpServers"] = {"new-server": {"command": "npx", "args": ["-y", "brand-new-mcp"]}}
        (self.ctx.home / ".claude.json").write_text(json.dumps(cj), encoding="utf-8")
        audit.write_outputs(self.ctx, r2)
        audit.cmd_mark_reviewed(self.ctx, None)
        r3 = audit.collect(self.ctx, [], include_projects=False, include_versions=False)
        self.assertIn("mcp", r3["drift"])
        drift = next(f for f in r3["findings"] if f["id"] == "DRIFT")
        self.assertEqual(drift["severity"], "medium")
        self.assertIn("MCP-UNPINNED", {f["id"] for f in r3["findings"]})


class SkillFiles(unittest.TestCase):
    def test_frontmatter(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"^---\nname: (\S+)\ndescription: (.+?)\n---\n", text, re.S)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "claude-security-audit")
        self.assertLessEqual(len(m.group(2)), 1024)
        for ref in ("references/checks.md", "references/identity.md", "scheduled-task.md"):
            self.assertTrue((SKILL / ref).is_file(), ref)

    def test_skill_files_hold_no_real_addresses(self):
        for p in SKILL.rglob("*"):
            if p.is_file() and p.suffix in (".md", ".py"):
                for e in audit.EMAIL_RE.findall(p.read_text(encoding="utf-8")):
                    self.assertTrue(audit.benign_email(e), f"{p.name}: {e}")


if __name__ == "__main__":
    unittest.main()
