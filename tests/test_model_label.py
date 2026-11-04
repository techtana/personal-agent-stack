"""Tests for the model label the gateway appends to chat replies (infrastructure/litellm/custom_callbacks.py) and the
environment `stack.py up` gives it (services.gateway_label_env, media.image_label)."""
from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "infrastructure" / "litellm"))


def _stub_litellm() -> None:
    """custom_callbacks imports LiteLLM, which is a uv tool here, not a project dependency."""
    if "litellm" in sys.modules:
        return

    class _Obj:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    names = ("litellm", "litellm.integrations", "litellm.integrations.custom_logger", "litellm.types",
             "litellm.types.utils")
    mods = {n: types.ModuleType(n) for n in names}
    mods["litellm.integrations.custom_logger"].CustomLogger = object
    for cls in ("Delta", "ModelResponseStream", "StreamingChoices"):
        setattr(mods["litellm.types.utils"], cls, type(cls, (_Obj,), {}))
    sys.modules.update(mods)


_stub_litellm()
import custom_callbacks as cc  # noqa: E402
from stacklib import media, services  # noqa: E402
from test_media import make_profile  # noqa: E402

IMAGE_CONTEXT = ("<context>The requested image has been created by the system successfully and is now being shown to "
                 "the user.</context>")


def request(alias="local-primary", deployment="ollama_chat/qwen3.5:9b", decision=None, messages=None, **extra):
    logging_obj = types.SimpleNamespace(litellm_params={"metadata": {
        "deployment": deployment, "model_info": {"agent_stack_location": "local"}}})
    data = {"model": alias, "messages": messages or [{"role": "user", "content": "hi"}],
            "litellm_logging_obj": logging_obj, "metadata": {}, **extra}
    if decision:
        data["metadata"]["routing_decision"] = decision
    return data


def env(**values):
    base = {"AGENT_STACK_MODEL_LABEL": "1", "AGENT_STACK_IMAGE_LABEL": ""}
    return mock.patch.dict(os.environ, {**base, **values})


class Footer(unittest.TestCase):
    def test_plain_alias_names_model_and_alias(self):
        with env():
            footer = cc._routing_footer(request())
        self.assertEqual(footer, "\n\n---\n**Used:** qwen3.5:9b (Local) via local-primary")

    def test_router_alias_keeps_the_route(self):
        decision = {"tier_label": "SIMPLE", "routed_model": "local-primary", "cause": "heuristic_scorer"}
        with env():
            footer = cc._routing_footer(request(alias="app-dev", decision=decision))
        self.assertEqual(footer, "\n\n---\n**Used:** qwen3.5:9b (Local)  \n**Route:** SIMPLE -> local-primary "
                                 "(heuristic scorer)")

    def test_image_line_after_open_webui_made_an_image(self):
        messages = [{"role": "system", "content": "You write docs.\n" + IMAGE_CONTEXT},
                    {"role": "user", "content": "draw a cat"}]
        with env(AGENT_STACK_IMAGE_LABEL="Z-Image-Turbo int8 (ComfyUI, 1024x1024, 8 steps)"):
            footer = cc._routing_footer(request(messages=messages))
        self.assertTrue(footer.endswith("  \n**Image:** Z-Image-Turbo int8 (ComfyUI, 1024x1024, 8 steps)"), footer)

    def test_edited_image_and_list_content(self):
        text = "<context>The requested image has been edited and created and is now being shown</context>"
        messages = [{"role": "system", "content": [{"type": "text", "text": text}]}]
        with env(AGENT_STACK_IMAGE_LABEL="X"):
            self.assertIn("**Image:** X", cc._routing_footer(request(messages=messages)))

    def test_no_image_line_without_the_context_or_label(self):
        with env(AGENT_STACK_IMAGE_LABEL="X"):
            self.assertNotIn("Image", cc._routing_footer(request()))
        failed = [{"role": "system", "content": "<context>Image generation was attempted but failed.</context>"}]
        with env(AGENT_STACK_IMAGE_LABEL="X"):
            self.assertNotIn("Image", cc._routing_footer(request(messages=failed)))
        with env():
            self.assertNotIn("Image", cc._routing_footer(request(messages=[{"role": "system",
                                                                           "content": IMAGE_CONTEXT}])))

    def test_switched_off(self):
        with env(AGENT_STACK_MODEL_LABEL="0", AGENT_STACK_IMAGE_LABEL="X"):
            self.assertIsNone(cc._routing_footer(request()))

    def test_json_requests_get_no_footer(self):
        with env():
            self.assertIsNone(cc._routing_footer(request(response_format={"type": "json_object"})))

    def test_footer_only_on_text_replies(self):
        reply = {"choices": [{"message": {"content": "OK"}}]}
        self.assertTrue(cc._append_route_footer(reply, "\n\n---\nX"))
        self.assertEqual(reply["choices"][0]["message"]["content"], "OK\n\n---\nX")
        tool = {"choices": [{"message": {"content": "", "tool_calls": [{"id": "1"}]}}]}
        self.assertFalse(cc._append_route_footer(tool, "X"))
        fim = {"choices": [{"text": "def f():"}]}
        self.assertFalse(cc._append_route_footer(fim, "X"))


class GatewayEnv(unittest.TestCase):
    def profile(self, comfyui="native", **obs):
        p = make_profile(r"D:\media", comfyui=comfyui)
        p["observability"] = {"jsonl_traces": True, "model_label": True, **obs}
        return p

    def test_image_label_from_profile(self):
        self.assertEqual(media.image_label(self.profile()), "Z-Image-Turbo int8 (ComfyUI, 1024x1024, 8 steps)")
        self.assertEqual(media.image_label(self.profile(comfyui="off")), "")

    def test_env(self):
        e = services.gateway_label_env(self.profile())
        self.assertEqual(e["AGENT_STACK_MODEL_LABEL"], "1")
        self.assertEqual(e["AGENT_STACK_JSONL_TRACES"], "1")
        self.assertTrue(e["AGENT_STACK_IMAGE_LABEL"].startswith("Z-Image-Turbo"))
        off = services.gateway_label_env(self.profile(model_label=False, jsonl_traces=False))
        self.assertEqual((off["AGENT_STACK_MODEL_LABEL"], off["AGENT_STACK_JSONL_TRACES"],
                          off["AGENT_STACK_IMAGE_LABEL"]), ("0", "0", ""))


if __name__ == "__main__":
    unittest.main()
