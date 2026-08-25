from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_FILES = [
    ROOT / "SKILL.md",
    ROOT / "agents" / "interface.yaml",
    ROOT / "references" / "imagegen-adapter.md",
    ROOT / "references" / "prompt-contract.md",
    ROOT / "references" / "visual-planning.md",
]
RETIRED_ACTIVE_PHRASES = [
    "choose svg",
    "选择 svg",
    "svg fallback",
    "回退到 svg",
    "renderer routing",
    "混合路线先",
    "final.svg",
    "image-only",
]


class DocumentationConsistencyTests(unittest.TestCase):
    def test_retired_routes_do_not_reappear_as_active_instructions(self) -> None:
        for path in ACTIVE_FILES:
            text = path.read_text(encoding="utf-8").lower()
            for phrase in RETIRED_ACTIVE_PHRASES:
                self.assertNotIn(phrase.lower(), text, f"{phrase!r} found in {path}")

    def test_removed_route_files_are_absent(self) -> None:
        self.assertFalse((ROOT / "references" / "renderer-routing.md").exists())
        self.assertFalse((ROOT / "references" / "svg-adapter.md").exists())
        self.assertFalse((ROOT / "scripts" / "audit_svg.py").exists())


if __name__ == "__main__":
    unittest.main()
