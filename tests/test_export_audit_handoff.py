"""Standalone boundary tests; runnable without the scanner's dependencies."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import json

spec = importlib.util.spec_from_file_location("exporter", Path(__file__).resolve().parents[1] / "scripts" / "export_audit_handoff.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ExportTests(unittest.TestCase):
    def test_ambiguous_anchor_is_not_assigned_to_every_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selection.json"
            path.write_text(json.dumps([{"slug": "example", "anchor": "0x123", "chains": ["Ethereum", "Base"], "tvl": 12345}]))
            result = exporter.export(path, "example", {"core": "https://github.com/example/core"})
            self.assertEqual(result["scope"]["contracts"], [])
            self.assertEqual(result["discovery"]["anchor_unassigned"], "0x123")
            self.assertIsNone(result["discovery"]["observation_time"])
            self.assertEqual(result["repositories"][0]["ref"], "HEAD")
            self.assertEqual(len(result["discovery"]["source_sha256"]), 64)

    def test_explicit_pair_preserved_and_credentials_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ranked.json"
            path.write_text(json.dumps([{"target_name": "example", "chain": "base", "address": "0x123"}]))
            result = exporter.export(path, "example", {"core": "https://github.com/example/core"})
            self.assertEqual(result["scope"]["contracts"][0]["chain"], "base")
            with self.assertRaises(ValueError):
                exporter.export(path, "example", {"core": "https://secret@github.com/example/core"})
            with self.assertRaises(ValueError):
                exporter.export(path, "unknown", {"core": "https://github.com/example/core"})


if __name__ == "__main__":
    unittest.main()
