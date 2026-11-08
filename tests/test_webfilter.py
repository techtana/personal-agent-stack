"""Blocked sites (scripts/stacklib/webfilter.py): parsing lists, what lands in Open WebUI's two filters, downloads, the
search filter row, and the files for what the stack cannot enforce. No network: tests pass their own `fetch`, and
tests/conftest.py makes the real download fail and keeps the audit's folder in a temp dir."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import yaml

from stacklib import features, install, settings, webfilter

REPO = Path(__file__).resolve().parents[1]
DEFAULTS = yaml.safe_load((REPO / "machines" / "_defaults.yaml").read_text(encoding="utf-8"))
SHIPPED = {lst.id: lst for lst in webfilter.lists()}


def make_profile(data_dir: Path, **over) -> dict:
    cfg = dict(DEFAULTS["web_filter"])
    cfg.update(over)
    return {"name": "TESTBOX", "data_dir": data_dir, "web_filter": cfg, "services": dict(DEFAULTS["services"])}


def feed(*sites: str) -> str:
    return "# a downloaded list\n" + "\n".join(sites) + "\n"


class Temp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def profile(self, **over) -> dict:
        return make_profile(self.tmp, **over)

    def download(self, profile: dict, text: str, lid: str = "phishing") -> None:
        url = SHIPPED[lid].url
        webfilter.refresh(profile, force=True, fetch=lambda u: text if u == url else (_ for _ in ()).throw(OSError(u)))


class Parse(unittest.TestCase):
    def test_reads_the_usual_blocklist_formats(self):
        text = ("# comment\n! adblock comment\n[Adblock Plus 2.0]\n0.0.0.0 evil-one.com\n127.0.0.1 evil-two.net\n"
                "||ads.tracker.net^$third-party\nhttps://login.bank-secure.co/x?y#z\n*.wild.org, plain.io  Caps.COM.\n"
                "evil-three.com:8080 # trailing comment\nmünchen.de\n")
        self.assertEqual(webfilter.parse(text), ["evil-one.com", "evil-two.net", "ads.tracker.net",
                                                 "login.bank-secure.co", "wild.org", "plain.io", "caps.com",
                                                 "evil-three.com", "xn--mnchen-3ya.de"])

    def test_drops_what_is_not_a_public_site(self):
        for token in ("10.0.0.1", "::1", "localhost", "printer.local", "single", "a..b.com", "-bad.com", "x.123",
                      "@@||ok.com^", "router.lan", "site.example", "site.test", ""):
            with self.subTest(token=token):
                self.assertIsNone(webfilter.normalize(token))

    def test_covered_matches_on_label_boundaries(self):
        self.assertEqual(webfilter.covered("a.b.evil.com", {"evil.com"}), "evil.com")
        self.assertIsNone(webfilter.covered("notevil.com", {"evil.com"}))


class Policy(unittest.TestCase):
    def test_the_shipped_lists_and_profile_switches_agree(self):
        ids = [lst.id for lst in webfilter.lists()]
        self.assertEqual(ids, ["exfiltration", "data_brokers", "phishing", "threats"])
        for lid in ids:
            self.assertIn(lid, DEFAULTS["web_filter"], f"machines/_defaults.yaml web_filter has no switch for {lid}")
        for lst in webfilter.lists():
            self.assertTrue(bool(lst.sites) != bool(lst.url), f"{lst.id}: either shipped sites or a url")
            if lst.url:
                self.assertTrue(lst.url.startswith("https://"))

    def test_shipped_sites_are_valid_and_unique(self):
        raw = yaml.safe_load(webfilter.POLICY_FILE.read_text(encoding="utf-8"))
        for lid, d in raw["lists"].items():
            sites = d.get("sites") or []
            self.assertEqual(len(sites), len(set(sites)), lid)
            self.assertEqual([webfilter.normalize(s) for s in sites], sites, lid)
        self.assertIn("docs.google.com", webfilter.keep())

    def test_a_new_switch_is_off_or_on_as_documented(self):
        cfg = DEFAULTS["web_filter"]
        self.assertTrue(cfg["enabled"] and cfg["exfiltration"] and cfg["data_brokers"] and cfg["phishing"])
        self.assertFalse(cfg["threats"])


class Plan(Temp):
    def test_off_blocks_nothing(self):
        p = webfilter.plan(self.profile(enabled=False))
        self.assertFalse(p.on)
        self.assertEqual(webfilter.openwebui_env(self.profile(enabled=False)), {})

    def test_own_sites_first_then_the_lists_in_order(self):
        prof = self.profile(block="mine.com\n# note\nother-mine.org", phishing=False)
        p = webfilter.plan(prof)
        self.assertEqual(p.ordered[:3], ["mine.com", "other-mine.org", SHIPPED["exfiltration"].sites[0]])
        self.assertEqual(p.counts["own"], 2)
        self.assertEqual(p.counts["data_brokers"], len(SHIPPED["data_brokers"].sites))
        self.assertEqual(p.missing, [])

    def test_a_parent_takes_the_place_of_its_first_subdomain(self):
        prof = self.profile(block="www.evil-site.com", exfiltration=False, data_brokers=False)
        self.download(prof, feed("a.other.com", "evil-site.com", "x.evil-site.com"))
        p = webfilter.plan(prof)
        self.assertEqual(p.ordered, ["evil-site.com", "a.other.com"])
        self.assertEqual(p.counts["own"], 1)

    def test_allow_removes_sites_and_reports_a_blocked_parent(self):
        prof = self.profile(block="evil-site.com", allow="webhook.site\nok.evil-site.com", data_brokers=False,
                            phishing=False)
        p = webfilter.plan(prof)
        self.assertNotIn("webhook.site", p.ordered)
        self.assertEqual(p.allowed, 1)
        self.assertEqual(p.conflicts, [("ok.evil-site.com", "evil-site.com")])
        self.assertIn("ok.evil-site.com stays blocked because evil-site.com is blocked", webfilter.summary(prof))

    def test_keep_protects_whole_platforms_from_downloaded_lists_only(self):
        prof = self.profile(block="weebly.com", exfiltration=False, data_brokers=False)
        self.download(prof, feed("docs.google.com", "evil.weebly.com", "phish.blogspot.com"))
        p = webfilter.plan(prof)
        self.assertNotIn("docs.google.com", p.ordered)
        self.assertIn("phish.blogspot.com", p.ordered)
        self.assertEqual(p.ordered[0], "weebly.com")   # your own list may block a platform

    def test_the_search_filter_is_capped_and_the_fetch_filter_fits_its_budget(self):
        prof = self.profile(max_sites=50, exfiltration=False, data_brokers=False)
        self.download(prof, feed(*(f"phish-{i:05d}-very-long-name-for-budget.com" for i in range(3000))))
        p = webfilter.plan(prof)
        self.assertEqual(len(p.search), 50)
        self.assertEqual(p.total, 3000)
        env = webfilter.openwebui_env(prof)
        self.assertLessEqual(len(env[webfilter.FETCH_ENV]), webfilter.FETCH_BUDGET)
        self.assertLessEqual(len(env[webfilter.SEARCH_ENV]), webfilter.SEED_BUDGET)
        self.assertTrue(all(e.startswith("!") for e in env[webfilter.FETCH_ENV].split(",")))
        self.assertTrue(all(e.startswith("!") for e in json.loads(env[webfilter.SEARCH_ENV])))
        self.assertIn("(of 3,000; web_filter.max_sites)", webfilter.summary(prof))

    def test_a_list_not_downloaded_yet_is_named(self):
        prof = self.profile()
        self.assertEqual(webfilter.plan(prof).missing, ["phishing"])
        self.assertIn("Not downloaded yet: Phishing sites", webfilter.summary(prof))

    def test_check_says_where_a_site_is_blocked(self):
        prof = self.profile(phishing=False)
        self.assertIn("blocked as webhook.site (from Request catchers and tunnels) in web search and page fetches",
                      webfilter.check(prof, "https://abc.webhook.site/x"))
        self.assertEqual(webfilter.check(prof, "github.com"), "github.com is not blocked")
        self.assertIn("not a public site name", webfilter.check(prof, "10.0.0.1"))


class Refresh(Temp):
    def test_downloads_once_then_waits_for_refresh_hours(self):
        prof = self.profile()
        calls = []
        fetch = lambda u: calls.append(u) or feed("phish-a.com", "phish-a.com", "phish-b.com")  # noqa: E731
        out = webfilter.refresh(prof, fetch=fetch)
        self.assertEqual([(r.id, r.ok) for r in out], [("phishing", True)])
        self.assertEqual(webfilter.cached(prof, "phishing"), ["phish-a.com", "phish-b.com"])
        self.assertEqual(webfilter.refresh(prof, fetch=fetch), [])
        self.assertEqual(len(calls), 1)
        m = webfilter.meta(prof, "phishing")
        m["fetched_at"] = time.time() - 25 * 3600
        (self.tmp / "webfilter" / "phishing.json").write_text(json.dumps(m), encoding="utf-8")
        self.assertTrue(webfilter.due(prof, SHIPPED["phishing"]))

    def test_a_failed_download_keeps_the_last_copy_and_waits_an_hour(self):
        prof = self.profile()
        self.download(prof, feed("phish-a.com"))

        def broken(_u):
            raise OSError("connection reset")

        out = webfilter.refresh(prof, force=True, fetch=broken)
        self.assertFalse(out[0].ok)
        self.assertIn("stays in use", out[0].text)
        self.assertEqual(webfilter.cached(prof, "phishing"), ["phish-a.com"])
        self.assertFalse(webfilter.due(prof, SHIPPED["phishing"]))   # retried after RETRY_SECONDS

    def test_an_empty_download_is_refused(self):
        out = webfilter.refresh(self.profile(), force=True, fetch=lambda u: "# nothing\n")
        self.assertFalse(out[0].ok)
        self.assertIn("nothing from it is blocked yet", out[0].text)

    def test_only_https_is_downloaded(self):
        with self.assertRaises(ValueError):
            webfilter.require_https("http://phishing.army/list.txt")
        webfilter.require_https("https://phishing.army/list.txt")

    def test_tests_never_reach_the_network(self):
        out = webfilter.refresh(self.profile(), force=True)
        self.assertIn("tests do not download", out[0].text)


def openwebui_db(path: Path, value=None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    with con:
        con.execute("create table config (key text primary key, value json not null, updated_at bigint)")
        if value is not None:
            con.execute("insert into config values (?, ?, 0)", (webfilter.SEARCH_KEY, json.dumps(value)))
    con.close()
    return path


def row(db: Path):
    con = sqlite3.connect(db)
    try:
        r = con.execute("select value from config where key = ?", (webfilter.SEARCH_KEY,)).fetchone()
        return json.loads(r[0]) if r else None
    finally:
        con.close()


class OpenWebUI(Temp):
    def test_no_database_yet_writes_nothing(self):
        self.assertEqual(webfilter.sync_openwebui(self.profile()), "")

    def test_writes_the_search_filter_and_keeps_the_owners_entries(self):
        prof = self.profile(phishing=False)
        db = openwebui_db(self.tmp / "open-webui" / "webui.db", ["!owner-block.com", "wikipedia.org"])
        text = webfilter.sync_openwebui(prof)
        self.assertIn("2 of your own from its admin page kept", text)
        v = row(db)
        self.assertEqual(v[:2], ["!owner-block.com", "wikipedia.org"])
        self.assertEqual(v[2:], ["!" + s for s in webfilter.plan(prof).search])
        self.assertEqual(webfilter.sync_openwebui(prof), "")   # nothing changed

    def test_a_smaller_plan_replaces_the_earlier_entries(self):
        db = openwebui_db(self.tmp / "open-webui" / "webui.db")
        webfilter.sync_openwebui(self.profile(phishing=False))
        webfilter.sync_openwebui(self.profile(phishing=False, data_brokers=False))
        self.assertNotIn("!spokeo.com", row(db))
        self.assertIn("!webhook.site", row(db))

    def test_turning_it_off_removes_only_the_stacks_entries(self):
        db = openwebui_db(self.tmp / "open-webui" / "webui.db", ["!owner-block.com"])
        webfilter.sync_openwebui(self.profile(phishing=False))
        self.assertIn("cleared", webfilter.sync_openwebui(self.profile(enabled=False)))
        self.assertEqual(row(db), ["!owner-block.com"])

    def test_entries_seeded_from_the_environment_count_as_the_stacks(self):
        prof = self.profile(phishing=False)
        seed = json.loads(webfilter.openwebui_env(prof)[webfilter.SEARCH_ENV])
        db = openwebui_db(self.tmp / "open-webui" / "webui.db", seed)
        webfilter.sync_openwebui(self.profile(phishing=False, data_brokers=False))
        self.assertEqual(row(db), ["!" + s for s in SHIPPED["exfiltration"].sites])

    def test_open_webui_gets_the_filters_in_its_environment(self):
        from stacklib import services

        prof = self.profile(phishing=False)
        full = {**prof, "ports": dict(DEFAULTS["ports"]), "observability": dict(DEFAULTS["observability"]),
                "models": {}, "media": {}, "dictation": {}, "read_aloud": {}, "refine": {}}
        with mock.patch.object(services, "tool_command", return_value=["open-webui"]), \
                mock.patch.object(services, "_uv_tool_dir", return_value=None):
            env = services.commands(full)["open_webui"]["env"]
        self.assertTrue(env[webfilter.FETCH_ENV].startswith("!webhook.site,"))


class Outside(Temp):
    def test_the_audit_list_holds_own_and_shipped_sites_only(self):
        prof = self.profile(block="mine.com")
        self.download(prof, feed("phish-a.com"))
        path = webfilter.write_audit_file(prof)
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
        self.assertEqual(lines[0], "mine.com")
        self.assertIn("webhook.site", lines)
        self.assertNotIn("phish-a.com", lines)
        self.assertTrue(path.read_text(encoding="utf-8").startswith(webfilter.HEADER))

    def test_the_audit_list_goes_when_the_filter_is_off_but_a_hand_written_one_stays(self):
        path = webfilter.write_audit_file(self.profile(phishing=False))
        self.assertIsNone(webfilter.write_audit_file(self.profile(enabled=False)))
        self.assertFalse(path.exists())
        path.write_text("my-own.com\n", encoding="utf-8")
        webfilter.write_audit_file(self.profile(enabled=False))
        self.assertTrue(path.exists())

    def test_claude_rules_cover_the_site_and_its_subdomains(self):
        self.assertEqual(webfilter.claude_rules(["evil-site.com"]),
                         ["WebFetch(domain:evil-site.com)", "WebFetch(domain:*.evil-site.com)"])

    def test_chrome_policy_keeps_existing_entries_and_stops_at_its_limit(self):
        reg = webfilter.chrome_reg([f"s{i}.com" for i in range(1200)], existing=['old "quoted".com'])
        self.assertTrue(reg.startswith("Windows Registry Editor Version 5.00"))
        self.assertIn('"1"="old \\"quoted\\".com"', reg)
        self.assertIn(f'"{webfilter.CHROME_MAX}"=', reg)
        self.assertNotIn(f'"{webfilter.CHROME_MAX + 1}"=', reg)

    def test_export_writes_the_rules_file(self):
        prof = self.profile(phishing=False)
        with mock.patch.object(webfilter, "_chrome_existing", return_value=[]):
            out = webfilter.export(prof)
        rules = json.loads(out["claude"].read_text(encoding="utf-8"))["permissions"]["deny"]
        self.assertIn("WebFetch(domain:*.webhook.site)", rules)
        self.assertIn("audit", out)


class Dns(unittest.TestCase):
    def test_providers(self):
        self.assertEqual(webfilter.provider("9.9.9.9"), "Quad9")
        self.assertEqual(webfilter.provider("1.1.1.2"), "Cloudflare for Families")
        self.assertIsNone(webfilter.provider("1.1.1.1"))
        self.assertIsNone(webfilter.provider("76.76.2.0"))   # Control D's unfiltered resolver
        self.assertIn("NextDNS", webfilter.provider("45.90.28.17"))

    def test_text_for_all_some_and_none(self):
        self.assertIn("uses protective DNS (Quad9)", webfilter.dns_text(["9.9.9.9", "149.112.112.112"]))
        self.assertIn("Only some", webfilter.dns_text(["9.9.9.9", "192.168.1.1"]))
        self.assertIn("No protective DNS found", webfilter.dns_text(["192.168.1.1"]))
        self.assertIn("Could not read", webfilter.dns_text([]))

    def test_same_resolver_table_as_the_security_audit(self):
        spec = importlib.util.spec_from_file_location(
            "audit_for_webfilter", REPO / ".claude" / "skills" / "claude-security-audit" / "scripts" / "audit.py")
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        self.assertEqual({n: set(a) for n, a in webfilter.PROTECTIVE_DNS}, {n: set(a) for n, a in audit.PROTECTIVE_DNS})


class Wiring(Temp):
    def test_settings_write_numbers_and_site_lists(self):
        by = {settings.setting_id(s): s for s in settings.SETTINGS}
        self.assertEqual(settings._to_file_value(by["web_filter.max_sites"], "50000"), 50000)
        self.assertEqual(settings._to_file_value(by["web_filter.block"], " a.com \n\nb.com "), "a.com\n\nb.com")
        self.assertEqual(by["web_filter.enabled"].effect, "web_filter")

    def test_feature_status(self):
        prof = self.profile()
        s = features.statuses(prof)["web_filter"]
        self.assertEqual((s.state, s.level), ("Lists missing", "warn"))
        self.download(prof, feed("phish-a.com"))
        self.assertEqual(features.statuses(prof)["web_filter"].state, "Installed")
        self.assertEqual(features.statuses(self.profile(enabled=False))["web_filter"].state, "Installed, off")

    def test_setup_step(self):
        plan = install.Plan(model_store=str(self.tmp))
        with self.assertRaises(install.Skip):
            install.step_web_filter(plan, self.profile(enabled=False), lambda *a: None)
        with self.assertRaises(install.Warn) as w:   # the download fails in tests
            install.step_web_filter(plan, self.profile(), lambda *a: None)
        self.assertIn("Phishing sites (Phishing Army): download failed", str(w.exception))
        self.assertIn("Could not read this PC's DNS servers", str(w.exception))
        self.assertIn("78 sites in Open WebUI's web search filter",
                      install.step_web_filter(plan, self.profile(phishing=False), lambda *a: None))


if __name__ == "__main__":
    unittest.main()
