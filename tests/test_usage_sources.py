"""Usage of every model the stack runs: the shared record (stacklib/usage_log.py), the summary that merges it with the
gateway's traces (stacklib/usage.py), ComfyUI's job history (stacklib/comfy_usage.py), and the programs that record
their own calls (voice typing's engine, the recordings MCP server, stack.py's direct Ollama calls).
Nothing here loads a model, calls a service or writes outside a temporary folder."""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from stacklib import comfy_usage, ollama, services, traces, usage, usage_log  # noqa: E402

NOW = datetime.now(timezone.utc)
TS = NOW.isoformat(timespec="seconds")
OWUI = "Python/3.11 aiohttp/3.14.3"


def gateway(**kw) -> dict:
    row = {"ts": TS, "status": "success", "requested_model": "local-primary", "model": "ollama_chat/qwen3.5:9b",
           "process": "ollama", "prompt_tokens": 1000, "completion_tokens": 100, "latency_ms": 3000,
           "inference_ms": 2000, "model_load_ms": 0, "input_ms": 500, "user_agent": OWUI}
    row.update(kw)
    return row


def record(source: str, model: str, kind: str, **kw) -> dict:
    return usage_log.make(source, model, kind, **kw)


GATEWAY = [
    gateway(),
    gateway(requested_model="local-embed", model="ollama/nomic-embed-text", call_type="aembedding",
            completion_tokens=0, inference_ms=None, user_agent="python-requests/2.32"),
    gateway(requested_model="api-haiku", model="anthropic/claude-haiku-5-5", process="anthropic", data_class="external",
            cost=0.0021, inference_ms=None, user_agent="claude-cli/2.1.302"),
    gateway(requested_model="local-small", user_agent="agent-stack-voice-typing", prompt_tokens=200,
            completion_tokens=50),
]
RECORDS = [
    # Two dictated phrases, one live preview and a recording, all large-v3-turbo on the GPU.
    record("voice-typing", "large-v3-turbo", "transcription", client="Voice typing", latency_ms=400, run_ms=300,
           audio_s=6.0, output_tokens=20),
    record("voice-typing", "large-v3-turbo", "transcription", client="Voice typing", latency_ms=6400, load_ms=6000,
           run_ms=300, audio_s=6.0, output_tokens=22),
    record("voice-typing", "large-v3-turbo", "transcription", client="Voice typing", latency_ms=100,
           run_ms=100, audio_s=2.0, output_tokens=5, detail={"preview": True}),
    record("recordings", "large-v3-turbo", "transcription", client="Claude Desktop", latency_ms=4000, run_ms=4000,
           audio_s=120.0, output_tokens=400),
    record("comfyui", "Z-Image-Turbo int8", "image", client="Open WebUI", latency_ms=12000, run_ms=10000, images=2),
    record("ollama", "qwen3.5:9b", "load", client="Warm-up", latency_ms=23000, load_ms=22500),
]


def summarize(group_by: str = "served", gateway_rows=GATEWAY, usage_rows=RECORDS) -> dict:
    with mock.patch.object(usage.traces, "litellm_rows", return_value=gateway_rows), \
            mock.patch.object(usage.traces, "usage_rows", return_value=usage_rows):
        return usage.summarize(1, group_by)


def row(data: dict, name: str) -> dict:
    return next(m for m in data["models"] if m["model"] == name)


class Records(unittest.TestCase):
    def tearDown(self):
        usage_log._configured.clear()

    def test_make_checks_ids_kinds_and_places(self):
        for bad in ({"source": "Voice Typing"}, {"kind": "video"}, {"location": "cloud"}):
            args = {"source": "voice-typing", "model": "m", "kind": "transcription", **bad}
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                usage_log.make(args.pop("source"), args.pop("model"), args.pop("kind"), **args)

    def test_values_that_are_not_numbers_are_left_out(self):
        rec = usage_log.make("ollama", "m", "load", latency_ms=mock.MagicMock(), load_ms=-1, run_ms=float("nan"),
                             output_tokens=mock.MagicMock(), error="x" * 500)
        self.assertNotIn("latency_ms", rec)
        self.assertNotIn("load_ms", rec)
        self.assertNotIn("run_ms", rec)
        self.assertEqual(rec["output_tokens"], 0)
        self.assertEqual(len(rec["error"]), 200)

    def test_each_source_writes_its_own_file_per_local_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = usage_log.make("comfyui", "Z-Image-Turbo int8", "image", images=1,
                                 ts=datetime(2026, 11, 7, 23, 30, tzinfo=timezone.utc))
            self.assertTrue(usage_log.write(rec, Path(tmp)))
            day = datetime(2026, 11, 7, 23, 30, tzinfo=timezone.utc).astimezone().date().isoformat()
            path = Path(tmp) / "comfyui" / f"{day}.jsonl"
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), rec)

    def test_switch_follows_the_profile_and_the_environment(self):
        with mock.patch.dict(os.environ, {usage_log.ENV: "off"}):
            self.assertIsNone(usage_log.directory())
        with mock.patch.dict(os.environ, {usage_log.ENV: "D:/x/usage"}):
            self.assertEqual(usage_log.directory(), Path("D:/x/usage"))
            usage_log.configure({"observability": {"jsonl_traces": False}})
            self.assertIsNone(usage_log.directory())  # the profile wins in the process that configured it
        self.assertEqual(usage_log.env_for({"observability": {"jsonl_traces": False}}), {usage_log.ENV: "off"})
        self.assertEqual(usage_log.env_for({}), {usage_log.ENV: str(usage_log.default_dir())})

    def test_errors_never_carry_file_paths(self):
        for text in (r"OSError: [Errno 2] No such file or directory: 'C:\Users\x\My Recordings\a 1.m4a'",
                     "Invalid data found when processing input: '/home/x/rec/a b.wav'",
                     r"\\server\share\call.wav is missing", r"opened D:\media\rec\talk.mp4 then failed"):
            with self.subTest(text=text):
                err = usage_log.make("recordings", "m", "transcription", error=text)["error"]
                self.assertNotRegex(err, r"Users|home|share|media|\.m4a|\.wav|\.mp4")
        self.assertEqual(usage_log.scrub("HTTP/1.1 500 at http://127.0.0.1:8188/history"),
                         "HTTP/1.1 500 at http://127.0.0.1:8188/history")

    def test_turning_traces_off_reaches_programs_started_earlier(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {usage_log.ENV: tmp}):
            self.assertEqual(usage_log.directory(), Path(tmp))
            usage_log.sync_switch({"observability": {"jsonl_traces": False}}, Path(tmp))
            self.assertIsNone(usage_log.directory())  # a service started with the folder in its environment
            usage_log.sync_switch({"observability": {"jsonl_traces": True}}, Path(tmp))
            self.assertEqual(usage_log.directory(), Path(tmp))

    def test_write_is_quiet_when_off_or_failing(self):
        rec = usage_log.make("ollama", "m", "load")
        usage_log.configure({"observability": {"jsonl_traces": False}})
        self.assertFalse(usage_log.write(rec))
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "file"
            blocker.write_text("not a folder")
            self.assertFalse(usage_log.write(rec, blocker))  # cannot create a folder under a file: no exception


class Summary(unittest.TestCase):
    def test_every_model_appears_in_its_own_units(self):
        data = summarize()
        names = {m["model"] for m in data["models"]}
        self.assertEqual(names, {"qwen3.5:9b", "nomic-embed-text", "claude-haiku-5-5", "large-v3-turbo",
                                 "Z-Image-Turbo int8"})
        whisper = row(data, "large-v3-turbo")
        self.assertEqual(whisper["kind"], "transcription")
        # The live preview re-read speech the finished phrases also hold: kept out of requests and audio.
        self.assertEqual(whisper["requests"], 3)
        self.assertEqual(whisper["previews"], 1)
        self.assertAlmostEqual(whisper["audio_s"], 132.0)
        self.assertAlmostEqual(whisper["rtf"], 132.0 / 4.6)  # audio seconds per second of model time
        self.assertEqual(whisper["audio_loads"], 1)
        self.assertEqual([c["model"] for c in whisper["clients"]], ["Voice typing", "Claude Desktop"])
        cells = usage.cells(whisper)
        self.assertEqual((cells["input"], cells["output"], cells["speed"]), ("2.2 min", "442 tok", "29x"))
        image = row(data, "Z-Image-Turbo int8")
        self.assertEqual((image["images"], image["image_s"], image["image_wall_s"]), (2, 5.0, 6.0))
        self.assertEqual(usage.cells(image)["output"], "2 img")
        self.assertEqual(row(data, "nomic-embed-text")["kind"], "embedding")

    def test_outside_apis_are_marked_and_cost_counts(self):
        data = summarize()
        api = row(data, "claude-haiku-5-5")
        self.assertEqual(api["location"], "external")
        self.assertAlmostEqual(api["cost"], 0.0021)
        self.assertEqual(row(data, "qwen3.5:9b")["location"], "local")
        # An Ollama model reached through /v1/messages: LiteLLM names the adapter ("anthropic") as the provider.
        adapter = usage.from_gateway(gateway(model="ollama/qwen2.5-coder:1.5b-base", provider="anthropic", process=None))
        self.assertEqual(adapter["location"], "local")
        old = usage.from_gateway(gateway(model="anthropic/claude-sonnet-5-5", provider="anthropic", process=None))
        self.assertEqual(old["location"], "external")  # traces from before data_class was recorded
        self.assertIn("API cost $0.0021", usage.breakdown_text(api, "claude-haiku-5-5"))

    def test_totals_keep_tokens_audio_and_images_apart(self):
        tot = summarize()["totals"]
        self.assertEqual(tot["requests"], len(GATEWAY) + len(RECORDS) - 1)  # the preview is not a request
        self.assertEqual(tot["prompt_tokens"], 1000 + 1000 + 1000 + 200)  # text models only
        self.assertEqual(tot["images"], 2)
        self.assertAlmostEqual(tot["audio_s"], 132.0)
        self.assertEqual(sum(tot["daily_requests"]), tot["requests"])

    def test_services_and_clients_group_too(self):
        by_alias = {m["model"] for m in summarize("alias")["models"]}
        self.assertTrue({"Voice typing", "Recordings", "ComfyUI", "Ollama (direct)", "local-primary"} <= by_alias)
        by_client = {m["model"]: m for m in summarize("client")["models"]}
        # Voice typing asked for transcriptions and, through the gateway, for its text clean-up.
        self.assertEqual(by_client["Voice typing"]["kinds"], {"transcription": 2, "chat": 1})
        self.assertIn("Warm-up", by_client)

    def test_breakdown_and_chart_follow_the_kind(self):
        data = summarize()
        whisper, image = row(data, "large-v3-turbo"), row(data, "Z-Image-Turbo int8")
        text = usage.breakdown_text(whisper, "large-v3-turbo")
        self.assertIn("3 transcriptions", text)
        self.assertIn("Plus 1 live preview while you spoke, 0.1 s of model time, not in the totals", text)
        self.assertIn("29x realtime", text)
        self.assertIn("1 waited for the model to load, 6.0 s each", text)
        self.assertIn("2 images, 5.0 s of model time each", usage.breakdown_text(image, "Z-Image-Turbo int8"))
        mixed = usage.breakdown_text(data["totals"], "All models")
        self.assertIn("3 transcriptions", mixed)
        self.assertIn("1 image job", mixed)
        warm = summarize("client")["models"]
        self.assertIn("23.0 s each", usage.breakdown_text(next(m for m in warm if m["model"] == "Warm-up"), "Warm-up"))
        self.assertEqual(usage.measure(whisper), "audio")
        self.assertEqual(usage.measure(image), "images")
        self.assertEqual(usage.measure(row(data, "qwen3.5:9b")), "tokens")
        for _, _, field in usage.MEASURES.values():
            self.assertEqual(len(whisper[field]), 1)

    def test_sorting_mixed_kinds_by_a_column(self):
        data = summarize()
        ranked = sorted(data["models"], key=lambda m: usage.sort_value(m, "input"), reverse=True)
        self.assertEqual(ranked[0]["model"], "qwen3.5:9b")  # 2,200 tokens before 134 s of audio
        self.assertGreater(usage.sort_value(row(data, "Z-Image-Turbo int8"), "speed"), 0)

    def test_components_name_themselves(self):
        self.assertEqual(usage.client_of({"user_agent": "agent-stack-voice-typing"}), "Voice typing")
        self.assertEqual(usage.client_of({"user_agent": "agent-stack-retro"}), "Retrospective")
        self.assertEqual(usage.client_of({"user_agent": "agent-stack-newthing/1.0"}), "newthing")
        self.assertEqual(usage.client_of({"user_agent": "python-requests/2.32.3"}), "Open WebUI")

    def test_uncounted_use_is_named_while_it_can_happen(self):
        with tempfile.TemporaryDirectory() as tmp:
            on = {"services": {"open_webui": "native", "kokoro": "native"}, "data_dir": tmp,
                  "models": {"embed": "nomic-embed-text"}}
            self.assertEqual(len(usage.uncounted(on)), 2)  # no database yet: Open WebUI's own Whisper, and Kokoro
            self.assertEqual(usage.uncounted({"services": {"open_webui": "off", "kokoro": "off"}}), [])


    def test_direct_embeddings_are_named_until_provisioned(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "open-webui").mkdir()
            con = sqlite3.connect(Path(tmp) / "open-webui" / "webui.db")
            con.execute("create table config (key text primary key, value text)")
            con.executemany("insert into config values (?, ?)",
                            [("rag.embedding_engine", '"ollama"'), ("audio.stt.engine", '"openai"'),
                             ("audio.stt.openai.api_base_url", '"http://127.0.0.1:8790/v1"')])  # voice typing's
            con.commit()
            p = {"services": {"open_webui": "native"}, "data_dir": tmp, "models": {"embed": "nomic-embed-text"},
                 "ports": {"dictation": 8790}}
            notes = usage.uncounted(p)
            self.assertEqual(len(notes), 1)
            self.assertIn("document embeddings", notes[0])
            con.execute("update config set value = '\"openai\"' where key = 'rag.embedding_engine'")
            con.commit()
            con.close()
            self.assertEqual(usage.uncounted(p), [])


def history_entry(pid: str, start: int, end: int, *, client_id: str | None = None, source: str | None = None,
                  ok: bool = True, images: int = 1) -> dict:
    graph = json.loads((REPO / "config" / "comfyui" / "workflows" / "z_image_turbo.json").read_text(encoding="utf-8"))
    extra = {"create_time": start - 2000}
    if client_id:
        extra["client_id"] = client_id
    if source:
        extra["comfy_usage_source"] = source
    messages = [["execution_start", {"prompt_id": pid, "timestamp": start}],
                ["execution_cached", {"nodes": [], "prompt_id": pid, "timestamp": start}],
                ["execution_success" if ok else "execution_error", {"prompt_id": pid, "timestamp": end}]]
    return {"prompt": [1, pid, graph, extra, ["9"]],
            "outputs": {"9": {"images": [{"filename": f"{pid}-{i}.png", "subfolder": "", "type": "output"}
                                         for i in range(images if ok else 0)]}},
            "status": {"status_str": "success" if ok else "error", "completed": ok, "messages": messages}, "meta": {}}


class ComfyUI(unittest.TestCase):
    T0 = int(NOW.timestamp() * 1000) - 60_000

    def test_an_open_webui_job_becomes_one_record(self):
        end, rec = comfy_usage.record_for("abc", history_entry("abc", self.T0, self.T0 + 10_000,
                                                               client_id="0b7e7c56-1f0a-4c55-9d9e-2f6f3c8b1a10"))
        self.assertEqual(end, self.T0 + 10_000)
        self.assertEqual((rec["source"], rec["model"], rec["kind"], rec["client"]),
                         ("comfyui", "Z-Image-Turbo int8", "image", "Open WebUI"))
        self.assertEqual((rec["images"], rec["run_ms"], rec["latency_ms"]), (1, 10_000, 12_000))
        self.assertEqual(rec["detail"]["steps"], 8)
        self.assertEqual(rec["detail"]["size"], "1024x1024")

    def test_who_asked(self):
        self.assertEqual(comfy_usage.client_of({"comfy_usage_source": "comfyui-frontend"}), "ComfyUI web UI")
        self.assertEqual(comfy_usage.client_of({"client_id": "agent-stack-smoke"}), "Stack scripts")
        self.assertEqual(comfy_usage.client_of({"client_id": "someone"}), "API client")

    def test_failed_and_running_jobs(self):
        _, rec = comfy_usage.record_for("bad", history_entry("bad", self.T0, self.T0 + 500, ok=False))
        self.assertEqual((rec["status"], rec["images"]), ("failure", 0))
        running = history_entry("run", self.T0, self.T0 + 1)
        running["status"] = {"status_str": None, "completed": False,
                             "messages": [["execution_start", {"timestamp": self.T0}]]}
        self.assertIsNone(comfy_usage.record_for("run", running))

    def test_collect_records_each_job_once(self):
        history = {"a": history_entry("a", self.T0, self.T0 + 9_000),
                   "b": history_entry("b", self.T0 + 10_000, self.T0 + 20_000, source="comfyui-frontend")}

        def answer(*_a, **_k):
            body = mock.MagicMock()
            body.__enter__.return_value.read.return_value = json.dumps(history).encode()
            return body

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(usage_log, "directory", return_value=Path(tmp)), \
                mock.patch.object(comfy_usage.urllib.request, "urlopen", side_effect=answer) as urlopen:
            self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 2)
            self.assertTrue(urlopen.call_args_list[0].args[0].endswith(f"max_items={comfy_usage.FIRST}"))
            self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 0)
            self.assertTrue(urlopen.call_args_list[1].args[0].endswith(f"max_items={comfy_usage.RECENT}"))
            history["c"] = history_entry("c", self.T0 + 30_000, self.T0 + 40_000)
            self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 1)
            # More new jobs than a routine poll asks for: the whole history is read again, nothing is missed.
            for i in range(comfy_usage.RECENT + 3):
                history[f"n{i}"] = history_entry(f"n{i}", self.T0 + 50_000 + i * 100, self.T0 + 50_050 + i * 100)
            recent = dict(list(history.items())[-comfy_usage.RECENT:])

            def newest_only(url, **_k):
                body = mock.MagicMock()
                body.__enter__.return_value.read.return_value = json.dumps(
                    recent if url.endswith(f"max_items={comfy_usage.RECENT}") else history).encode()
                return body

            urlopen.side_effect = newest_only
            self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), comfy_usage.RECENT + 3)
            lines = [json.loads(x) for f in (Path(tmp) / "comfyui").glob("*.jsonl")
                     for x in f.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sorted(r["detail"]["job"] for r in lines)[:3], ["a", "b", "c"])
            self.assertEqual(len(lines), 3 + comfy_usage.RECENT + 3)
            self.assertEqual(len({r["detail"]["job"] for r in lines}), len(lines))  # each job once

    @staticmethod
    def serve(history: dict):
        def answer(*_a, **_k):
            body = mock.MagicMock()
            body.__enter__.return_value.read.return_value = json.dumps(history).encode()
            return body
        return mock.patch.object(comfy_usage.urllib.request, "urlopen", side_effect=answer)

    @staticmethod
    def written(tmp: str) -> list[dict]:
        return [json.loads(x) for f in (Path(tmp) / "comfyui").glob("*.jsonl")
                for x in f.read_text(encoding="utf-8").splitlines()]

    def test_odd_and_cached_jobs_do_not_stop_the_others(self):
        cached = history_entry("cached", self.T0, self.T0 + 50)
        cached["status"]["messages"][1][1]["nodes"] = ["3"]  # the KSampler: ComfyUI answered it from its cache
        far = history_entry("far", self.T0, self.T0)
        far["status"]["messages"][-1][1]["timestamp"] = 10 ** 20  # no such date: record_for raises
        history = {"odd": {"prompt": {"not": "a list"}, "outputs": [1, 2], "status": {"messages": "x"}},
                   "far": far, "cached": cached, "real": history_entry("real", self.T0 + 100, self.T0 + 9_000)}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(usage_log, "directory", return_value=Path(tmp)), \
                self.serve(history):
            self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 1)
            self.assertEqual([r["detail"]["job"] for r in self.written(tmp)], ["real"])

    def test_one_collection_at_a_time(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(usage_log, "directory", return_value=Path(tmp)), \
                mock.patch.object(comfy_usage.urllib.request, "urlopen") as urlopen:
            with comfy_usage._lock:  # another thread is collecting
                self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 0)
            urlopen.assert_not_called()

    def test_a_job_that_could_not_be_written_is_tried_again(self):
        history = {"a": history_entry("a", self.T0, self.T0 + 1_000),
                   "b": history_entry("b", self.T0 + 2_000, self.T0 + 3_000)}
        real, calls = usage_log.write, []

        def flaky(rec, directory_=None):
            calls.append(rec["detail"]["job"])
            return real(rec, directory_) if len(calls) == 1 else False

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(usage_log, "directory", return_value=Path(tmp)), \
                self.serve(history):
            with mock.patch.object(usage_log, "write", side_effect=flaky):
                self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 1)
            self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 1)
            self.assertEqual(sorted(r["detail"]["job"] for r in self.written(tmp)), ["a", "b"])

    def test_a_lost_state_file_does_not_record_jobs_twice(self):
        history = {"a": history_entry("a", self.T0, self.T0 + 1_000),
                   "b": history_entry("b", self.T0 + 2_000, self.T0 + 3_000)}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(usage_log, "directory", return_value=Path(tmp)), \
                self.serve(history):
            self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 2)
            (Path(tmp) / "comfyui" / comfy_usage.STATE).unlink()
            self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 0)
            self.assertEqual(len(self.written(tmp)), 2)

    def test_collect_is_quiet_when_comfyui_does_not_answer(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(usage_log, "directory", return_value=Path(tmp)), \
                mock.patch.object(comfy_usage.urllib.request, "urlopen", side_effect=OSError("refused")):
            self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 0)
        with mock.patch.object(usage_log, "directory", return_value=None), \
                mock.patch.object(comfy_usage.urllib.request, "urlopen") as urlopen:
            self.assertEqual(comfy_usage.collect("http://127.0.0.1:8188"), 0)
            urlopen.assert_not_called()  # usage traces off: ComfyUI is not even asked


class Recorders(unittest.TestCase):
    def test_ollama_warm_up_and_bench_record_themselves(self):
        reply = {"load_duration": 22_000_000_000, "eval_count": 256, "eval_duration": 5_000_000_000,
                 "prompt_eval_count": 54, "prompt_eval_duration": 100_000_000}
        with mock.patch.object(ollama, "api", return_value=reply), mock.patch.object(ollama, "ps", return_value=[]), \
                mock.patch.object(ollama, "nvidia_used_mib", return_value=None), \
                mock.patch.object(usage_log, "write") as write:
            ollama.warm("http://x", "qwen3.5:9b", 32768)
            ollama.bench("http://x", "qwen3.5:9b", 32768)
        warm, bench = (c.args[0] for c in write.call_args_list)
        self.assertEqual((warm["kind"], warm["client"], warm["load_ms"]), ("load", "Warm-up", 22_000))
        self.assertEqual((bench["kind"], bench["output_tokens"], bench["run_ms"]), ("chat", 256, 5000))

    def test_a_failed_warm_up_is_recorded_as_failed(self):
        with mock.patch.object(ollama, "api", side_effect=OSError("refused")), \
                mock.patch.object(usage_log, "write") as write, self.assertRaises(OSError):
            ollama.warm("http://x", "qwen3.5:9b", 32768)
        self.assertEqual(write.call_args.args[0]["status"], "failure")

    def test_recordings_server_writes_records_the_summary_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            usage_dir = Path(tmp) / "traces" / "usage"
            usage_dir.parent.mkdir()
            env = {"AGENT_STACK_USAGE_DIR": str(usage_dir), "AGENT_STACK_CLIENT": "Claude Desktop",
                   "WHISPER_ROOTS": tmp, "WHISPER_TRANSCRIPTS": str(Path(tmp) / "out")}
            with mock.patch.dict(os.environ, env):
                sys.modules.pop("whisper_mcp", None)
                srv = importlib.import_module("whisper_mcp")
                srv.record_usage("large-v3-turbo", "cuda", 125.0, 3.9, 0.4, 3.5, 812, "en")
            sys.modules.pop("whisper_mcp", None)
            files = list((usage_dir / "recordings").glob("*.jsonl"))
            self.assertEqual(len(files), 1)
            rec = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(set(rec) - set(usage_log.make("recordings", "m", "transcription", client="c", load_ms=1,
                                                           run_ms=1, latency_ms=1, detail={"a": 1}, error="e")), set())
            got = usage.from_record(rec)
            self.assertEqual((got["alias"], got["client"], got["kind"], got["audio_s"], got["output_tokens"]),
                             ("Recordings", "Claude Desktop", "transcription", 125.0, 812))

    def test_a_failed_recording_is_recorded_without_its_path(self):
        class Broken:
            def transcribe(self, *_a, **_k):
                raise OSError("Invalid data found when processing input: 'C:\\Users\\x\\call.m4a'")

        with tempfile.TemporaryDirectory() as tmp:
            usage_dir = Path(tmp) / "traces" / "usage"
            usage_dir.parent.mkdir()
            env = {"AGENT_STACK_USAGE_DIR": str(usage_dir), "WHISPER_ROOTS": tmp}
            with mock.patch.dict(os.environ, env):
                sys.modules.pop("whisper_mcp", None)
                srv = importlib.import_module("whisper_mcp")
                srv.ENGINE.name, srv.ENGINE.device = "large-v3-turbo", "cuda"
                # Stub the loader, not sys.modules: patching sys.modules re-imports mcp and cryptography afterwards.
                with mock.patch.object(srv.ENGINE, "_load", return_value=Broken()), self.assertRaises(OSError):
                    srv.ENGINE.transcribe(str(Path(tmp) / "call.m4a"), None, None, {})
                (usage_dir / "RECORDING_OFF").write_text("off")
                srv.record_usage("large-v3-turbo", "cuda", 1.0, 1.0, 0, 1.0, 1, "en")  # turned off since: nothing
            sys.modules.pop("whisper_mcp", None)
            lines = (usage_dir / "recordings").glob("*.jsonl")
            recs = [json.loads(x) for f in lines for x in f.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([(r["status"], r["error"]) for r in recs], [("failure", "OSError")])

    def test_recordings_server_writes_nothing_when_off(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AGENT_STACK_USAGE_DIR": "off",
                                                                                "WHISPER_ROOTS": tmp}):
            sys.modules.pop("whisper_mcp", None)
            srv = importlib.import_module("whisper_mcp")
            with mock.patch("builtins.open") as opened:
                srv.record_usage("large-v3-turbo", "cuda", 1.0, 1.0, 0, 1.0, 1, "en")
            opened.assert_not_called()
        sys.modules.pop("whisper_mcp", None)


@unittest.skipUnless(importlib.util.find_spec("numpy"), "voice typing's engine needs numpy (its own environment)")
class VoiceTypingEngine(unittest.TestCase):
    def engine(self, segments, fail: Exception | None = None):
        from stacklib.dictation import Config
        from stacklib.dictation.engine import Engine

        class Model:
            def transcribe(self, audio, **kw):
                if fail:
                    raise fail
                return iter(segments), SimpleNamespace(language="en")

        e = Engine(Config(device="cpu"), log=lambda *_: None)
        e.model, e.state, e.model_name, e.device = Model(), "ready", "large-v3-turbo", "cuda"
        return e

    def test_each_call_is_recorded_without_its_text(self):
        import numpy as np

        seg = SimpleNamespace(text=" Hello there.", tokens=[1, 2, 3, 4], no_speech_prob=0.0, avg_logprob=-0.2)
        e = self.engine([seg])
        with mock.patch.object(usage_log, "write") as write:
            self.assertEqual(e.transcribe(np.zeros(32000, dtype=np.float32))[0], "Hello there.")
            e.transcribe(np.zeros(16000, dtype=np.float32), fast=True)
        final, preview = (c.args[0] for c in write.call_args_list)
        self.assertEqual((final["source"], final["client"], final["audio_s"], final["output_tokens"]),
                         ("voice-typing", "Voice typing", 2.0, 4))
        self.assertEqual(final["detail"], {"device": "cuda", "language": "en"})
        self.assertEqual((preview["client"], preview["detail"]["preview"]), ("Voice typing", True))
        self.assertNotIn("Hello", json.dumps(final))

    def test_a_call_for_open_webui_is_recorded_under_its_client(self):
        import numpy as np

        e = self.engine([SimpleNamespace(text=" Hi.", tokens=[1, 2], no_speech_prob=0.0, avg_logprob=-0.1)])
        with mock.patch.object(usage_log, "write") as write:
            e.transcribe(np.zeros(16000, dtype=np.float32), client="Open WebUI")
            e.transcribe(np.zeros(16000, dtype=np.float32))
        shared, own = (c.args[0] for c in write.call_args_list)
        self.assertEqual((shared["source"], shared["client"], own["client"]), ("voice-typing", "Open WebUI", "Voice typing"))

    def test_auto_detects_even_when_dictation_names_a_language(self):
        import numpy as np

        e = self.engine([])
        e.cfg.language = "en"
        seen: list = []
        e.model.transcribe = lambda audio, **kw: (seen.append(kw["language"]), (iter([]), SimpleNamespace(language="th")))[1]
        with mock.patch.object(usage_log, "write"):
            e.transcribe(np.zeros(1600, dtype=np.float32), language="auto")  # Open WebUI sent no language
            e.transcribe(np.zeros(1600, dtype=np.float32))  # dictation follows its setting
            e.transcribe(np.zeros(1600, dtype=np.float32), language="th")
        self.assertEqual(seen, [None, "en", "th"])

    def test_a_failed_call_is_recorded_and_still_raises(self):
        import numpy as np

        e = self.engine([], fail=ValueError("bad audio"))
        with mock.patch.object(usage_log, "write") as write, self.assertRaises(ValueError):
            e.transcribe(np.zeros(1600, dtype=np.float32))
        self.assertEqual(write.call_args.args[0]["status"], "failure")


class Traces(unittest.TestCase):
    def test_callers_cannot_change_the_cached_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "2026-11-07.jsonl"
            f.write_text('{"a": 1}\n', encoding="utf-8")
            traces.read_jsonl([f])[0]["a"] = 2
            self.assertEqual(traces.read_jsonl([f]), [{"a": 1}])


class OpenWebUIEmbeddings(unittest.TestCase):
    P = {"models": {"embed": "nomic-embed-text"}, "ports": {"litellm": 4000, "ollama": 11434}}

    def test_embeddings_go_through_the_local_gateway(self):
        env = services.openwebui_embedding_env(self.P, "sk-test")
        self.assertEqual(env, {"RAG_EMBEDDING_ENGINE": "openai", "RAG_EMBEDDING_MODEL": "local-embed",
                               "RAG_OPENAI_API_BASE_URL": "http://127.0.0.1:4000/v1", "RAG_OPENAI_API_KEY": "sk-test"})
        rows = services.openwebui_embedding_settings(self.P, "sk-test")
        # The engine never changes without the local base URL: Open WebUI's default would be api.openai.com.
        self.assertEqual(rows["rag.openai.api_base_url"], "http://127.0.0.1:4000/v1")
        self.assertEqual(len(rows), 4)

    def test_no_rows_without_a_gateway_key(self):
        self.assertEqual(services.openwebui_embedding_settings(self.P, ""), {})
        self.assertEqual(services.openwebui_embedding_env(self.P, "")["RAG_EMBEDDING_ENGINE"], "ollama")

    def test_without_an_embedding_model_it_keeps_asking_ollama(self):
        p = {"models": {}, "ports": {"litellm": 4000, "ollama": 11434}}
        self.assertEqual(services.openwebui_embedding_settings(p, "k"), {})
        self.assertEqual(services.openwebui_embedding_env(p, "k")["RAG_EMBEDDING_ENGINE"], "ollama")


if __name__ == "__main__":
    unittest.main()
