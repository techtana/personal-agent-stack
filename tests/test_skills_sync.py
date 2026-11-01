"""Tests for scripts/stacklib/skills_sync.py: which skills are copied into skills/.

Run with `uv run python -m unittest discover -s tests`.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from stacklib import skills_sync  # noqa: E402


def _skill(folder: Path, front: str = "") -> None:
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(f"---\nname: {folder.name}\n{front}---\nbody\n", encoding="utf-8")


class DiscoverTest(unittest.TestCase):
    def test_filters_by_source_licence_and_exclude(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _skill(root / "mine")
            _skill(root / "secret")
            _skill(root / "closed", "license: Proprietary. LICENSE.txt has complete terms\n")
            bundle = root / "synced" / "abc"
            _skill(bundle / "uploaded")
            _skill(bundle / "vendor")
            (bundle / "manifest.json").write_text(json.dumps({"skills": [
                {"name": "uploaded", "source": "plugin"}, {"name": "vendor", "source": "anthropic"}]}), encoding="utf-8")
            cfg = {"sources": [str(root)], "synced_sources": ["plugin"], "exclude": ["secret"]}

            found, skipped = skills_sync.discover(cfg)

            self.assertEqual(sorted(found), ["mine", "uploaded"])
            for name in ("secret", "closed", "vendor"):
                self.assertTrue(any(s.startswith(name) for s in skipped), name)


if __name__ == "__main__":
    unittest.main()
