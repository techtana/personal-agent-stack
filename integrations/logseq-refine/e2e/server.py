"""Test-only stand-in for voice typing in the plugin's end-to-end run: the real control server and plugin API
(stacklib/dictation/control.py, pluginapi.py) on a test port, with a refine log and key of its own.

    uv run python integrations/logseq-refine/e2e/server.py --root .run/logseq-test --key KEY [--port 8791]
        [--model fake | --model gateway [--gateway-port 4010]]

--model fake answers from a fixed table (FAKE below), so the plugin's behaviour can be checked exactly; a text in
SLOW waits two seconds first, long enough for the run to edit the block meanwhile. --model gateway starts a private
copy of the stack's LiteLLM gateway (this checkout's generated config, a random master key, traces under --root) and
refines with the profile's refine.model through it, as voice typing does. Stop it with Ctrl+C or by killing the process.
"""
from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
from stacklib import profile as prof  # noqa: E402
from stacklib import services  # noqa: E402
from stacklib.dictation import control, pluginapi, refine  # noqa: E402
from stacklib.dictation.refinelog import RefineLog  # noqa: E402

FAKE = {
    "this are a first block that mention [[Project Alpha]] and #idea with teh typo":
        "This is a first block that mentions [[Project Alpha]] and #idea, with the typo fixed.",
    "second block with a property": "Second block, with a property",
    "and teh body text": "And the body text.",
    "All good here.": "All good here.",
    "a block that drop its tag #idea": "A block that drops its tag.",
    "this block will be edit meanwhile": "This block will be edited meanwhile.",
    "this are the slash block": "This is the slash block.",
    "this block will be open in the editor": "This block will be open in the editor.",
}
CONCISE = {"this are a first block that mention [[Project Alpha]] and #idea with teh typo":
           "First block: mentions [[Project Alpha]] and #idea."}
SLOW = {"this block will be edit meanwhile", "this block will be open in the editor"}


def fake_refine(text, style, *, model, timeout):
    lead, core, trail = refine.split_space(text)
    if core in SLOW:
        time.sleep(2.0)
    reply = (CONCISE if style.id == "concise" else FAKE).get(core, FAKE.get(core))
    if reply is None:
        return refine.Result(text, False, "the fake model has no answer for this text", 0.01)
    ok, why = refine.check(core, reply, style)
    if not ok:
        return refine.Result(text, False, why, 0.01, suggestion=reply, served="fake")
    if refine.same_text(reply, core):
        return refine.Result(text, True, "no changes needed", 0.01, suggestion=reply, unchanged=True, served="fake")
    return refine.Result(lead + reply + trail, True, "", 0.01, suggestion=reply, served="fake")


def start_gateway(profile: dict, port: int, root: Path) -> tuple[subprocess.Popen, str]:
    cmd = services.commands(profile)["litellm"]
    key = "sk-e2e-" + secrets.token_hex(16)
    argv = list(cmd["cmd"])
    argv[argv.index("--port") + 1] = str(port)
    traces = root / "traces"
    traces.mkdir(parents=True, exist_ok=True)
    env = {**cmd["env"], "LITELLM_MASTER_KEY": key, "TRACES_DIR": str(traces)}
    for name in ("OTEL_EXPORTER", "OTEL_ENDPOINT", "OTEL_SERVICE_NAME"):
        env.pop(name, None)
    log = open(root / "gateway.log", "ab")
    proc = subprocess.Popen(argv, cwd=cmd["cwd"], env=env, stdout=log, stderr=subprocess.STDOUT,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(240):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/liveliness", timeout=2):
                return proc, key
        except OSError:
            if proc.poll() is not None:
                raise SystemExit(f"the test gateway exited with code {proc.returncode}; see {root / 'gateway.log'}")
            time.sleep(0.5)
    proc.kill()
    raise SystemExit("the test gateway did not answer within 2 minutes")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--model", choices=["fake", "gateway"], default="fake")
    ap.add_argument("--gateway-port", type=int, default=4010)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    profile = prof.resolve_profile()
    cfg = refine.Config.from_profile(profile)
    gateway = None
    if a.model == "gateway":
        gateway, master = start_gateway(profile, a.gateway_port, root)

        def refine_fn(text, style, *, model, timeout):
            return refine.refine_text(text, style, base_url=f"http://127.0.0.1:{a.gateway_port}", api_key=master,
                                      model=model, timeout=timeout, user_agent=pluginapi.USER_AGENT)
    else:
        refine_fn = fake_refine
    log = RefineLog(root / "refine-log.jsonl")
    api = pluginapi.PluginApi(cfg=lambda: cfg, refine_fn=refine_fn, log=log, key=lambda: a.key,
                              logline=lambda m: print(m, flush=True))
    server = control.ControlServer(a.port, lambda: {"ok": True, "e2e": True}, lambda name: {"ok": False},
                                   plugin=api, log=lambda m: print(m, flush=True))
    server.start()
    print(f"e2e voice typing on 127.0.0.1:{a.port} ({a.model}); log {log.path}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        api.flush()
        if gateway is not None:
            gateway.kill()


if __name__ == "__main__":
    os.environ.setdefault("AGENT_STACK_USAGE_DIR", "off")
    main()
