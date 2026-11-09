"""Everything the stack adds must show up in the tray (AGENTS.md rule 11). These tests fail until a new piece says how:

- Services: each service in machines/_defaults.yaml `services:` has a row label and role in scripts/tray.py, a place
  in services.SERVICE_ORDER (Ollama aside), and a line in stacklib/usage.py SERVICE_MODELS on how its model use is
  counted in the Usage tab.
- Settings: each top-level section of machines/_defaults.yaml has an entry in the tray's Settings tab
  (stacklib/settings.py) or a reason in NOT_IN_TRAY below.
- Model calls: a source file that calls a model directly records each call for the Usage tab (usage_log.record, or
  record_usage in the recordings server), or names itself to the gateway with User-Agent agent-stack-<id>, or is listed
  in NOT_RECORDED below with a reason. Each source and component it names is registered in stacklib/usage.py.

The model-call patterns are a tripwire, not a proof: they catch the usual ways this repository runs models.
"""
from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from stacklib import services, settings, usage  # noqa: E402

DEFAULTS = yaml.safe_load((REPO / "machines" / "_defaults.yaml").read_text(encoding="utf-8"))

# Profile sections without a Settings entry, and why.
NOT_IN_TRAY = {
    "schema_version": "the profile file's format version",
    "hardware_classes": "default models per hardware class; Settings picks the models themselves",
    "ports": "fixed local ports that clients and generated configs are built with",
    "media": "folders and image defaults, chosen in the installer (media.root must be an allowed folder)",
    "agent_access": "the folders agent sessions may touch; the owner decides them (decision D-M6)",
    "claude_code": "Claude Code profile B, set up by scripts/claude-local.ps1 and .sh",
}

# Ways a file runs a model directly: (pattern, what it means).
MODEL_CALLS = (
    (r"WhisperModel\(", "loads a faster-whisper model"),
    (r"/api/(?:generate|chat|embed|embeddings)[\"']", "calls Ollama's generate, chat or embed API"),
    (r"/prompt[\"']", "queues a ComfyUI job"),
    (r"/v1/(?:chat/completions|completions|embeddings|messages|audio/|images/)", "calls a model API"),
    (r"^\s*(?:import|from)\s+(?:anthropic|openai|transformers|diffusers|sentence_transformers|onnxruntime|"
     r"ctranslate2|faster_whisper|llama_cpp|vllm|kokoro|spacy|presidio_analyzer|torch)\b", "imports a model library"),
    (r"InferenceSession\(", "runs an ONNX model"),
    (r"\blitellm\.a?(?:completion|embedding|transcription|image_generation|speech)\(", "calls the LiteLLM SDK"),
)
UA = r"User-Agent[\"']\s*:\s*[\"']agent-stack-"
RECORDS = re.compile(r"usage_log\.(?:record|make|user_agent)\(|\brecord_usage\(|" + UA)

# Files that match a pattern but run no model call the Usage tab should count, and why.
NOT_RECORDED = {
    "scripts/stacklib/dictation/vad.py": "Silero VAD scores every 32 ms audio frame inside a voice typing session, "
                                         "whose Whisper calls are recorded",
    "scripts/stacklib/dictation/__main__.py": "imports the libraries to report their versions (dictate check); "
                                              "its transcribe command goes through engine.py, which records",
    "scripts/stacklib/media.py": "keep_alive 0 unloads Ollama models for the GPU switch; nothing runs",
    "infrastructure/litellm/custom_auth.py": "names the gateway routes Claude's key may use; the gateway's own traces "
                                             "count those calls",
    "scripts/stacklib/dictation/transcriptions.py": "serves /v1/audio/transcriptions for Open WebUI and decodes the "
                                                    "upload; the Whisper call goes through engine.py, which records "
                                                    "it with the caller as client",
    "scripts/stacklib/dictation/control.py": "routes /v1/audio/transcriptions to transcriptions.py; runs no model",
}

SOURCE_DIRS = ("scripts", "orchestrator", "infrastructure")


def _python_files() -> list[Path]:
    return sorted(p for d in SOURCE_DIRS for p in (REPO / d).rglob("*.py") if "__pycache__" not in p.parts)


def _rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def _tray_dict(name: str) -> dict:
    tree = ast.parse((REPO / "scripts" / "tray.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"scripts/tray.py has no {name}")


class Services(unittest.TestCase):
    def test_every_service_has_a_tray_row_and_says_how_its_model_use_is_counted(self):
        names = set(DEFAULTS["services"])
        self.assertEqual(names - {"ollama"}, set(services.SERVICE_ORDER),
                         "machines/_defaults.yaml services and services.SERVICE_ORDER disagree")
        labels, roles = _tray_dict("LABELS"), _tray_dict("ROLES")
        for svc in sorted(names):
            with self.subTest(service=svc):
                self.assertIn(svc, labels, f"add {svc} to LABELS in scripts/tray.py (its Overview row)")
                self.assertIn(svc, roles, f"add {svc} to ROLES in scripts/tray.py (what its row says it does)")
                self.assertIn(svc, usage.SERVICE_MODELS,
                              f"say in stacklib/usage.py SERVICE_MODELS how {svc}'s model use reaches the Usage tab "
                              "(None when it runs no model)")
        self.assertEqual(set(usage.SERVICE_MODELS) - names, set(), "SERVICE_MODELS names services that do not exist")

    def test_uncounted_model_use_names_real_services(self):
        for gap in usage.UNCOUNTED:
            self.assertIn(gap.service, DEFAULTS["services"])


class Settings(unittest.TestCase):
    def test_every_profile_section_is_in_settings_or_says_why_not(self):
        in_tray = {s.section for s in settings.SETTINGS}
        for section in DEFAULTS:
            with self.subTest(section=section):
                self.assertTrue(section in in_tray or section in NOT_IN_TRAY,
                                f"machines/_defaults.yaml section {section!r} has no entry in the tray's Settings tab "
                                "(stacklib/settings.py); add one, or give the reason in NOT_IN_TRAY")
        self.assertEqual({s for s in NOT_IN_TRAY if s not in DEFAULTS}, set(), "NOT_IN_TRAY names old sections")


class ModelCalls(unittest.TestCase):
    def test_every_direct_model_call_is_counted_in_the_usage_tab(self):
        missing = []
        for p in _python_files():
            text = p.read_text(encoding="utf-8", errors="replace")
            hits = [what for pattern, what in MODEL_CALLS if re.search(pattern, text, re.MULTILINE)]
            if hits and not RECORDS.search(text) and _rel(p) not in NOT_RECORDED:
                missing.append(f"{_rel(p)}: {', '.join(sorted(set(hits)))}")
        self.assertEqual(missing, [], "these files run models the tray's Usage tab cannot see. Record each call with "
                                      "stacklib.usage_log.record(<source>, ...) and add the source to usage.SOURCES, "
                                      "or call the gateway with User-Agent usage_log.user_agent(<id>) and add the id "
                                      "to usage.COMPONENTS, or explain the file in NOT_RECORDED")

    def test_exemptions_still_match_something(self):
        for rel in NOT_RECORDED:
            text = (REPO / rel).read_text(encoding="utf-8")
            self.assertTrue(any(re.search(pattern, text, re.MULTILINE) for pattern, _ in MODEL_CALLS),
                            f"{rel} no longer calls a model; remove it from NOT_RECORDED")

    def test_sources_and_components_are_registered(self):
        sources, components = set(), set()
        for p in _python_files():
            text = p.read_text(encoding="utf-8", errors="replace")
            sources.update(re.findall(r"usage_log\.(?:record|make)\(\s*[\"']([a-z0-9-]+)[\"']", text))
            if "def record_usage(" in text:  # the recordings server's own writer
                sources.update(re.findall(r"[\"']source[\"']:\s*[\"']([a-z0-9-]+)[\"']", text))
            components.update(re.findall(UA + r"([a-z0-9][a-z0-9-]*)[\"']", text))
            components.update(re.findall(r"usage_log\.user_agent\(\s*[\"']([a-z0-9-]+)[\"']", text))
        self.assertEqual(sources - set(usage.SOURCES), set(), "add these sources to stacklib/usage.py SOURCES")
        self.assertEqual(components - set(usage.COMPONENTS), set(), "add these ids to stacklib/usage.py COMPONENTS")
        self.assertTrue({"voice-typing", "recordings", "comfyui", "ollama"} <= sources)

    def test_registered_sources_point_at_real_code(self):
        for sid, src in usage.SOURCES.items():
            first = src.where.split()[0].rstrip(",:")
            self.assertTrue((REPO / first).is_file(), f"SOURCES[{sid!r}].where names {first}, which does not exist")


if __name__ == "__main__":
    unittest.main()
