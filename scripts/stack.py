#!/usr/bin/env python3
"""personal-agent-stack CLI. Run with `uv run scripts/stack.py <command>` from PowerShell, Git Bash, WSL or Linux.

Commands
  doctor        detect hardware/tools/ports; --write-profile [--refresh] writes machines/<HOST>.yaml
  profile       print the resolved profile (hardware class, models, Ollama env, cloud on/off)
  build         regenerate .claude/agents, .opencode/agents, config/openwebui, evals, infrastructure/litellm/config.yaml,
                winget/configuration*.winget
  install       installer window: asks where models and Python tools go, then runs setup in the background
                (--no-gui asks in the terminal; --status shows the background run's progress)
  setup         profile + .env secrets + Ollama env + uv tools + build + settings.local.json (+ pull core models unless --no-pull)
  disks         measure each drive's read/write speed and say which drive should hold models, tools and caches
  pull          pull the profile's models (--all includes the reviewer)
  up/down/status  manage native services: phoenix, litellm, orchestrator, open_webui
  bench         measure tok/s and GPU/CPU split for the primary (or --model) via Ollama
  smoke         end-to-end checks through LiteLLM and the orchestrator MCP
  claude-env    print the env for Claude Code profile B (--shell powershell|bash)
  why-routed    show recent gateway routing decisions
  retro         run scripts/retro.py (arguments pass through)
  skills-sync   copy new or changed personal skills into skills/ (--dry-run; rules in skills/sync.yaml)
  tasks         edge-mode supervision: install|remove|start|stop|status|xml one scheduled task per service
                (Windows Task Scheduler, --trigger startup|logon; systemd user units on Linux)
  run           run one service in the foreground and restart it when it exits (what each task runs)
  tray          background tray app: runs the services; its window shows status, usage per model and settings
                (--show, --foreground, --status, --stop, --install-startup, --remove-startup)
  dictate       voice typing in any app: install | run | start | stop | status | toggle | show | hide | check |
                transcribe FILE.wav (the live pipeline on a recording, with the cleanup)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stacklib import REPO, die, info, warn, which  # noqa: E402
from stacklib import agents_build, claude_env, litellm_build, ollama, services, smoke, tasks, traces, winget_build  # noqa: E402
from stacklib import profile as prof  # noqa: E402


def cmd_doctor(a):
    det = prof.detect_hardware()
    defaults = prof.load_defaults()
    info(f"machine     : {prof.machine_name()}")
    for k in ("os", "cpu", "ram_gb", "ram_modules", "gpu", "vram_mib", "idle_vram_mib", "gpu_driver", "disk_free_gb"):
        info(f"  {k:<13}: {det.get(k)}")
    info(f"  class        : {prof.pick_class(defaults, det)}  (from machines/_defaults.yaml)")
    info("tools:")
    for t in ("ollama", "claude", "litellm", "phoenix", "open-webui", "uv", "node", "npx", "docker", "nvidia-smi"):
        info(f"  {t:<11}: {which(t) or '(missing)'}")
    try:
        p = prof.resolve_profile()
        info("services:")
        for r in services.status(p):
            info(f"  {r['service']:<13}: {'UP  ' if r['healthy'] else 'down'}  {r['url']}")
        info(f"external     : {'ON' if p['policy']['external']['enabled'] else 'OFF'} (policy/privacy.yaml)")
    except FileNotFoundError as e:
        warn(str(e))
    if a.write_profile:
        path = prof.write_profile(refresh=a.refresh)
        info(f"profile      : {path.relative_to(REPO)} {'(refreshed)' if a.refresh else '(created or kept)'}")


def cmd_profile(a):
    p = prof.resolve_profile(a.machine)
    p = {k: (str(v) if isinstance(v, Path) else v) for k, v in p.items() if k != "catalog"}
    print(json.dumps(p, indent=2))


def cmd_build(a):
    from stacklib import paths

    p = prof.resolve_profile(getattr(a, "machine", None))
    errors, warnings = paths.check(p)
    for w in warnings:
        warn(w)
    if errors:
        die("path guard: " + "; ".join(errors))
    agents_build.build_all(p)
    litellm_build.build(p)
    winget_build.build()
    info(f"build: machine={p['name']} class={p['hardware_class']} primary={p['models'].get('primary')} external={'on' if p['policy']['external']['enabled'] else 'off'}")


def cmd_setup(a):
    from stacklib import install

    path = prof.write_profile(refresh=a.refresh)
    info(f"profile: {path.relative_to(REPO)}")
    p = prof.resolve_profile()
    store = p["ollama_env"].get("OLLAMA_MODELS") or p["model_store"] or str(Path.home() / ".ollama" / "models")
    if not install.drive_present(store):
        die(f"the models folder {store} is on a drive that is not connected; run `uv run scripts/stack.py install` to choose another")
    plan = install.Plan(model_store=store, pull=not a.no_pull, restart_ollama=not a.no_restart)
    if not install.run(plan):
        die("setup finished with problems (see the failed steps above)")
    info("setup complete. Next: `uv run scripts/stack.py up` then `uv run scripts/stack.py smoke`.")


def cmd_install(a):
    from stacklib import install

    if a.worker:
        raise SystemExit(0 if install.run_worker(Path(a.worker)) else 1)
    if a.status:
        state = install.read_state()
        info(install.summary(state))
        for s in state.get("steps", []):
            info(f"  {s['status']:<8} {s['title']}{': ' + s['detail'] if s['detail'] else ''}")
        return
    if not a.no_gui:
        try:
            import installer  # scripts/installer.py

            raise SystemExit(installer.main())
        except installer.NoDisplay as e:
            warn(f"no window available ({e}); asking in the terminal instead")
    install_in_terminal()


def install_in_terminal():
    """Terminal version of the installer window: same questions, same background worker."""
    import time

    from stacklib import install

    if not install.worker_running():
        prof.write_profile()
        p = prof.resolve_profile()
        d = install.defaults(p)
        if d["model_note"]:
            warn(d["model_note"])

        def ask_dir(label, default, need):
            while True:
                ans = input(f"{label} [{default}]: ").strip().strip('"') or default
                chk = install.check_dir(ans, need)
                info(f"  {chk.message}")
                if chk.ok:
                    return ans

        def ask_yes(q, default=True):
            ans = input(f"{q} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
            return default if not ans else ans.startswith("y")

        pull = ask_yes(f"Download models now ({', '.join(d['models'])}, about {d['models_gb']:.1f} GB)?")
        store = ask_dir("Models folder", d["model_store"], d["models_gb"] if pull else 0.1)
        move = ""
        if d["move_from"] and Path(d["move_from"]) != Path(store):
            if ask_yes(f"Move the {d['move_gb']:.1f} GB of models already in {d['move_from']}?"):
                move = d["move_from"]
        tools_need = install.TOOLS_GB if d["tools_missing"] else 0.1
        tool_dir = ask_dir("Python tools folder (LiteLLM, Phoenix, Open WebUI)", d["tool_dir"], tools_need)
        tool_dir = "" if d["tool_dir"] and Path(tool_dir) == Path(d["tool_dir"]) else tool_dir
        if not d["openclaw_installed"]:
            openclaw = ask_yes("Install OpenClaw with npm and point it at this stack's gateway "
                               "(upgrades Node.js with winget first if it is too old)?")
        else:
            openclaw = bool(d["openclaw_state"]) and ask_yes(
                f"OpenClaw: {d['openclaw_state'].lower()}. Point it at this stack's gateway (keeps a backup)?")
        plan = install.Plan(model_store=store, tool_dir=tool_dir, move_models_from=move,
                            install_ollama=d["ollama_missing"] and ask_yes("Ollama is not installed. Install it with winget?"),
                            pull=pull,
                            check_disks=ask_yes("Check how fast each drive is (writes a 256 MB test file per drive)?"),
                            setup_huggingface=ask_yes(f"Put the Hugging Face cache in {install.default_hf_home(store)} "
                                                      "and install the hf command?"),
                            install_openclaw=not d["openclaw_installed"] and openclaw,
                            setup_openclaw=openclaw,
                            setup_media=ask_yes(f"Install ComfyUI and the image model (about {install.MEDIA_GB:.0f} GB) "
                                                f"in {d['media_root']}? Agent sessions and media tools may use only that folder."),
                            media_root=d["media_root"],
                            start_stack=ask_yes("Start the stack when setup finishes?"))
        install.save_paths(p, store)
        install.spawn_worker(plan)
        info(f"setup runs in the background (log: {install.LOG_FILE.relative_to(REPO)}). Ctrl+C stops watching, not setup.")
    seen: dict[str, str] = {}
    try:
        while True:
            state = install.read_state()
            for s in state.get("steps", []):
                if seen.get(s["id"]) != s["status"] and s["status"] != "pending":
                    seen[s["id"]] = s["status"]
                    info(f"  {s['status']:<8} {s['title']}{': ' + s['detail'] if s['status'] != 'running' and s['detail'] else ''}")
            if state and state.get("status") != "running":
                info(install.summary(state))
                return
            time.sleep(1)
    except KeyboardInterrupt:
        info("stopped watching; `uv run scripts/stack.py install --status` shows progress")


def cmd_disks(a):
    from stacklib import disks, install

    p = prof.resolve_profile()
    store = p["ollama_env"].get("OLLAMA_MODELS") or p["model_store"] or ""
    if not disks.is_admin():
        info("not running as administrator, so winsat cannot run; timing a 256 MB test file per drive instead")
    speeds = disks.measure_all(a.drives or None)
    for s in speeds:
        info(s.summary())
    warnings, suggestion = disks.advise(speeds, store, install.current_tool_dir(),
                                        install.pull_size_gb(p, install.models_to_pull(p)))
    for w in warnings + ([suggestion] if suggestion else []):
        warn(w)
    if not warnings and not suggestion:
        info(f"no slow drives; models in {store}")
    for line in disks.winsat_howto(speeds):
        info(line)


def cmd_openclaw(a):
    from stacklib import clients

    p = prof.resolve_profile()
    if not a.check:
        try:
            info(clients.setup_openclaw(p, lambda m: info(m)))
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as e:
            die(f"OpenClaw setup failed: {e}")
    s = clients.openclaw(p["ports"]["litellm"])
    (info if s.level in ("ok", "off") else warn)(f"OpenClaw: {s.state}. {s.detail}")


def cmd_pull(a):
    p = prof.resolve_profile()
    m = p["models"]
    models = [m.get("fim"), m.get("embed"), m.get("small"), m.get("primary")] + ([m.get("reviewer")] if a.all else [])
    ollama.pull([x for x in models if x])


def cmd_up(a):
    p = prof.resolve_profile()
    svcs = a.services or None
    services.start(p, svcs)
    names = svcs or [s for s in services.SERVICE_ORDER if s in services.commands(p)]
    st = services.wait_healthy(p, names, timeout=a.wait)
    for s, ok in st.items():
        info(f"{'healthy    ' if ok else 'NOT healthy'}  {s:<13} {services.health_url(p, s)}")
    if not a.no_warm:
        info("loading the primary model so the first request does not wait for it (--no-warm skips this)")
        info(ollama.warm_primary(p))


def cmd_down(a):
    services.stop(prof.resolve_profile(), a.services or None)


def cmd_status(a):
    for r in services.status(prof.resolve_profile()):
        info(f"{r['service']:<13} {'UP  ' if r['healthy'] else 'down'}  pid={str(r['pid'] or '-'):<7} {r['url']}")


def cmd_run(a):
    raise SystemExit(tasks.main_run(prof.resolve_profile(), a.service))


def cmd_tasks(a):
    p = prof.resolve_profile()
    names = a.services or None
    if a.action in ("install", "xml"):
        ok = tasks.install(p, names, a.trigger, write_only=a.action == "xml")
        raise SystemExit(0 if ok else 1)
    if a.action == "remove":
        tasks.remove(p, names)
    elif a.action == "start":
        tasks.start(p, names)
    elif a.action == "stop":
        tasks.stop(p, names)
    else:
        rows = tasks.status(p)
        if not rows:
            info("tasks: none registered (`stack.py tasks install` creates them)")
        for r in rows:
            info(f"{r['service']:<13} {'UP  ' if r['healthy'] else 'down'}  task={r['state']:<9} last={r['last_result']:<11} {r['trigger']}")


def cmd_bench(a):
    p = prof.resolve_profile()
    base = f"http://127.0.0.1:{p['ports']['ollama']}"
    m = p["models"]
    for model in a.model or [m.get("primary")]:
        if not model:
            die("no primary model in profile; pass --model")
        ctx = a.num_ctx or m["primary_num_ctx"] or 16384
        # Benchmark with the same load options the gateway uses for this model, unless overridden.
        opts = dict(m.get("primary_options") or {}) if model == m.get("primary") else dict(m.get("reviewer_options") or {}) if model == m.get("reviewer") else {}
        if a.use_mmap != "profile":
            opts["use_mmap"] = a.use_mmap == "true"
        info(f"bench: {model} num_ctx={ctx} options={opts} (loading may take minutes)")
        print(json.dumps(ollama.bench(base, model, ctx, num_predict=a.tokens, runs=a.runs, options=opts), indent=2))


def cmd_smoke(a):
    p = prof.resolve_profile()
    res = smoke.run_media(p) if a.media_only else smoke.run(p, dept=a.dept, skip_mcp=a.skip_mcp)
    if a.media and not a.media_only:
        res += smoke.run_media(p)
    failed = [r for r in res if not r["ok"]]
    info(f"smoke: {len(res) - len(failed)}/{len(res)} passed")
    raise SystemExit(1 if failed else 0)


def cmd_claude_env(a):
    p = prof.resolve_profile()
    claude_env.write_local_profile_settings(p)
    print(claude_env.render(claude_env.local_profile_env(p), a.shell))


def cmd_why_routed(a):
    rows = traces.litellm_rows(days=a.days)
    print(traces.format_routed(rows[-a.last :]))


def cmd_tray(a):
    from stacklib import startup

    if a.install_startup:
        info(f"tray: start at login enabled ({startup.install()})")
    if a.remove_startup:
        startup.remove()
        info("tray: start at login disabled")
    if a.stop:
        startup.stop_tray()
    elif a.status:
        startup.report()
    elif a.foreground:
        raise SystemExit(subprocess.run([sys.executable, str(startup.TRAY_SCRIPT)], cwd=REPO).returncode)
    elif not (a.install_startup or a.remove_startup):
        try:
            if lnk := startup.ensure_menu_shortcut():
                info(f"tray: Start menu entry {lnk}")
        except Exception as e:  # noqa: BLE001 - a missing shortcut must not stop the tray from starting
            warn(f"tray: could not create the Start menu entry: {e}")
        if startup.running_pid():
            if a.show:
                startup.request_show()
                info(f"tray: already running (pid {startup.running_pid()}); opening its window")
            else:
                info(f"tray: already running (pid {startup.running_pid()}); click its icon in the notification area")
            return
        state, msg = startup.launch_and_wait(show=a.show)
        if state == "failed":
            die(f"tray: {msg}")
        elif state == "running":
            warn(f"tray: {msg}")
        else:
            info(f"tray: {msg}; its icon is in the notification area (Windows: under the ^ hidden icons arrow)")


def cmd_skills_sync(a):
    from stacklib import skills_sync

    skills_sync.sync(dry_run=a.dry_run)


def cmd_media(a):
    from stacklib import media, paths

    p = prof.resolve_profile()
    if a.action == "check":
        errors, warnings = paths.check(p)
        for w in warnings:
            warn(w)
        for e in errors:
            print(f"ERROR {e}")
        info(f"comfyui installed: {media.comfyui_installed(p)}; missing models: "
             f"{[m.name for m in media.missing_models(p, p['media'].get('image_workflow') or 'z_image_turbo')] if p['media'].get('root') else 'n/a'}")
        raise SystemExit(1 if errors else 0)
    if a.action == "install":
        info(media.install_comfyui(p, info))
        info(media.install_models(p, p["media"].get("image_workflow") or "z_image_turbo", lambda d=None, f=None: info(d) if d else None))
    if a.action in ("install", "provision"):
        keys = media.provision_openwebui(media.openwebui_db(p), media.image_settings(p))
        info(f"Open WebUI: {len(keys)} settings changed" + ("; restart it (`stack.py down open_webui` then `up open_webui`)" if keys else ""))
    if a.action == "gpu":
        info(media.gpu_mode(p, a.mode))


def cmd_dictate(a):
    import os

    from stacklib import dictation, load_dotenv
    from stacklib.dictation import control

    p = prof.resolve_profile()
    port = int(p["ports"]["dictation"])
    if a.action == "install":
        info(dictation.install(p, info))
        if p["services"].get("dictation") != "native":
            from stacklib.yamledit import set_key

            path = prof.machine_file(p["name"])
            text = set_key(path.read_text(encoding="utf-8"), "services", "dictation", "native")
            path.write_text(text, encoding="utf-8", newline="\n")
            info(f"turned voice typing on in {path.name} (services.dictation: native); the tray starts it with the other services")
        info("start it now with `uv run scripts/stack.py dictate start` (or Start on its row in the tray)")
        return
    if a.action in ("start", "stop"):
        if a.action == "start" and p["services"].get("dictation") != "native":
            die("voice typing is off in the machine profile; run `uv run scripts/stack.py dictate install` first")
        problems = (services.start if a.action == "start" else services.stop)(p, ["dictation"])
        if problems.get("dictation"):
            die(problems["dictation"])
        if a.action == "start":
            ok = services.wait_healthy(p, ["dictation"], timeout=30)["dictation"]
            info("voice typing is running: press " + dictation.hotkey_label(p) + " or click the mic button" if ok
                 else "voice typing did not answer within 30 s; see .run/logs/dictation.log")
        return
    if a.action in ("status", "toggle", "show", "hide"):
        try:
            info(json.dumps(control.call(port, "health" if a.action == "status" else a.action), indent=2))
        except OSError:
            die(f"voice typing is not running (nothing answers on port {port})")
        return
    python = dictation.env_python(p, windowed=False)
    if not python.exists():
        die(f"voice typing is not installed ({python} is missing); run `uv run scripts/stack.py dictate install`")
    env = dictation.app_env(p, {**load_dotenv(), **os.environ})  # .env holds LITELLM_MASTER_KEY for the cleanup
    argv = [str(python), "-P", "-m", "stacklib.dictation", a.action]
    if a.action == "transcribe":
        if not a.file:
            die("transcribe needs a WAV file")
        argv.append(str(Path(a.file).resolve()))
        argv += [x for opt, val in (("--style", a.style), ("--mode", a.mode), ("--language", a.language),
                                    ("--device", a.device), ("--vocabulary", a.vocabulary)) if val for x in (opt, val)]
    raise SystemExit(subprocess.run(argv, cwd=REPO, env=env).returncode)


def cmd_whisper(a):
    from stacklib import whisper

    p = prof.resolve_profile()
    if a.action == "install":
        info(whisper.install(p, info))
    if a.action in ("install", "register"):
        info(whisper.register_desktop(p))
    if a.action == "unregister":
        info(whisper.unregister_desktop())
    if a.action == "entry":
        import json
        print(json.dumps({whisper.SERVER_NAME: whisper.server_entry(p)}, indent=2))


def cmd_retro(a):
    rest = [x for x in a.rest if x != "--"]
    raise SystemExit(subprocess.run([sys.executable, str(REPO / "scripts" / "retro.py"), *rest], cwd=REPO).returncode)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="stack.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("doctor"); s.add_argument("--write-profile", action="store_true"); s.add_argument("--refresh", action="store_true"); s.set_defaults(f=cmd_doctor)
    s = sub.add_parser("profile"); s.add_argument("--machine"); s.set_defaults(f=cmd_profile)
    s = sub.add_parser("build"); s.add_argument("--machine"); s.set_defaults(f=cmd_build)
    s = sub.add_parser("setup"); s.add_argument("--no-pull", action="store_true"); s.add_argument("--no-restart", action="store_true"); s.add_argument("--refresh", action="store_true"); s.set_defaults(f=cmd_setup)
    s = sub.add_parser("install", help="ask where models and tools go, then run setup in the background")
    s.add_argument("--no-gui", action="store_true"); s.add_argument("--status", action="store_true")
    s.add_argument("--worker", help=argparse.SUPPRESS); s.set_defaults(f=cmd_install)
    s = sub.add_parser("disks", help="measure drive speeds and suggest where models, tools and caches go")
    s.add_argument("drives", nargs="*", help="drive roots such as C:\\ D:\\ (default: every local drive)"); s.set_defaults(f=cmd_disks)
    s = sub.add_parser("openclaw", help="make the gateway OpenClaw's only model endpoint (onboards it if needed)")
    s.add_argument("--check", action="store_true", help="only report where OpenClaw's models point"); s.set_defaults(f=cmd_openclaw)
    s = sub.add_parser("pull"); s.add_argument("--all", action="store_true"); s.set_defaults(f=cmd_pull)
    s = sub.add_parser("up"); s.add_argument("services", nargs="*"); s.add_argument("--wait", type=float, default=150)
    s.add_argument("--no-warm", action="store_true", help="do not load the primary model after starting"); s.set_defaults(f=cmd_up)
    s = sub.add_parser("down"); s.add_argument("services", nargs="*"); s.set_defaults(f=cmd_down)
    s = sub.add_parser("status"); s.set_defaults(f=cmd_status)
    s = sub.add_parser("run"); s.add_argument("service", choices=services.SERVICE_ORDER); s.set_defaults(f=cmd_run)
    s = sub.add_parser("tasks"); s.add_argument("action", choices=["install", "remove", "start", "stop", "status", "xml"])
    s.add_argument("services", nargs="*"); s.add_argument("--trigger", choices=["startup", "logon"], default="startup"); s.set_defaults(f=cmd_tasks)
    s = sub.add_parser("bench"); s.add_argument("--model", action="append"); s.add_argument("--num-ctx", type=int); s.add_argument("--tokens", type=int, default=256); s.add_argument("--runs", type=int, default=1); s.add_argument("--use-mmap", choices=["profile", "true", "false"], default="profile"); s.set_defaults(f=cmd_bench)
    s = sub.add_parser("smoke"); s.add_argument("--dept", default="docs"); s.add_argument("--skip-mcp", action="store_true")
    s.add_argument("--media", action="store_true", help="also make a small image through ComfyUI")
    s.add_argument("--media-only", action="store_true", help="only the media checks"); s.set_defaults(f=cmd_smoke)
    s = sub.add_parser("claude-env"); s.add_argument("--shell", choices=["powershell", "bash"], default="bash"); s.set_defaults(f=cmd_claude_env)
    s = sub.add_parser("why-routed"); s.add_argument("--last", type=int, default=10); s.add_argument("--days", type=int, default=7); s.set_defaults(f=cmd_why_routed)
    s = sub.add_parser("skills-sync", help="copy new or changed personal skills into skills/ (rules: skills/sync.yaml)")
    s.add_argument("--dry-run", action="store_true"); s.set_defaults(f=cmd_skills_sync)
    s = sub.add_parser("media", help="ComfyUI and media models under media.root: check, install, provision, gpu chat|media")
    s.add_argument("action", choices=["check", "install", "provision", "gpu"]); s.add_argument("mode", nargs="?", choices=["chat", "media"])
    s.set_defaults(f=cmd_media)
    s = sub.add_parser("dictate", help="voice typing in any app: install, run, start/stop, status, transcribe a WAV")
    s.add_argument("action", choices=["install", "run", "start", "stop", "status", "toggle", "show", "hide", "check", "transcribe"])
    s.add_argument("file", nargs="?"); s.add_argument("--style", choices=["verbatim", "clean", "concise"])
    s.add_argument("--mode", choices=["polish", "live"]); s.add_argument("--language"); s.add_argument("--device", choices=["auto", "cuda", "cpu"])
    s.add_argument("--vocabulary"); s.set_defaults(f=cmd_dictate)
    s = sub.add_parser("whisper", help="local Whisper for recordings: install, register|unregister in Claude Desktop, entry")
    s.add_argument("action", choices=["install", "register", "unregister", "entry"]); s.set_defaults(f=cmd_whisper)
    s = sub.add_parser("retro"); s.add_argument("rest", nargs=argparse.REMAINDER); s.set_defaults(f=cmd_retro)
    s = sub.add_parser("tray", help="background tray app that runs the services and shows their status")
    s.add_argument("--foreground", action="store_true"); s.add_argument("--status", action="store_true"); s.add_argument("--stop", action="store_true")
    s.add_argument("--show", action="store_true", help="open the tray window (also when the tray is already running)")
    s.add_argument("--install-startup", action="store_true"); s.add_argument("--remove-startup", action="store_true"); s.set_defaults(f=cmd_tray)
    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
