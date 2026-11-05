import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from stacklib import agents_build  # noqa: E402

AGENT = {"id": "docs", "name": "Docs", "description": "Writes docs.", "system_prompt": "Write."}


class OpenWebUIModelTests(unittest.TestCase):
    def test_orchestrator_tools_on_by_default(self):
        model = agents_build.build_openwebui_model(AGENT)[0]
        self.assertEqual(model["meta"]["toolIds"], ["server:mcp:personal-agent-stack"])
        self.assertEqual(model["params"]["function_calling"], "native")

    def test_agent_can_override_tool_ids(self):
        agent = dict(AGENT, openwebui={"tool_ids": []})
        self.assertEqual(agents_build.build_openwebui_model(agent)[0]["meta"]["toolIds"], [])


if __name__ == "__main__":
    unittest.main()
