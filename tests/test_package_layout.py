"""Only canonical definitions and implemented CLI entry points are supported."""
import ast
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

class PackageLayoutTests(unittest.TestCase):
    def test_canonical_definitions_unique_and_importable(self):
        definitions = {}
        for path in (ROOT / "src/replacement").rglob("*.py"):
            module = ".".join(path.relative_to(ROOT / "src").with_suffix("").parts)
            loaded = importlib.import_module(module)
            for node in ast.parse(path.read_text(encoding="utf8")).body:
                if isinstance(node, ast.ClassDef):
                    self.assertNotIn(node.name, definitions)
                    definitions[node.name] = getattr(loaded, node.name)
        from replacement.core.entities import OutputToken, SessionState
        from replacement.resources.gpu import EqualShareGPU
        self.assertIs(definitions["OutputToken"], OutputToken)
        self.assertIs(definitions["SessionState"], SessionState)
        self.assertIs(definitions["EqualShareGPU"], EqualShareGPU)

    def test_removed_forwarding_modules_are_not_importable(self):
        for name in ("compute", "entities", "events", "gpu", "gpu_demo", "gpu_queue",
                     "gpu_queue_demo", "observation", "s0", "workload"):
            with self.subTest(name=name):
                self.assertIsNone(importlib.util.find_spec("replacement." + name))
