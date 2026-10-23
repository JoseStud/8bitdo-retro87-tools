"""Offline macro documents and editor safety; no HID access."""
import json
from pathlib import Path
import tempfile
import unittest

from retro87_macros import Event, Macro, MacroEditor, MAX_STEPS


class MacroTests(unittest.TestCase):
    def test_chord_and_duration(self):
        editor = MacroEditor()
        for key, action, delay in [("lctrl", "down", 0), ("c", "down", 10),
                                    ("c", "up", 20), ("lctrl", "up", 10)]:
            editor.append(key, action, delay)
        editor.configure("Copy", 3)
        self.assertEqual(editor.state["durationMs"], 120)
        self.assertEqual(editor.state["problems"], [])
        self.assertTrue(editor.state["dirty"])

    def test_event_validation(self):
        for args in [("none", "down", 0), ("c", "tap", 0), ("c", "down", -1),
                     ("c", "down", True), ("c", "up", 65536)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                Event(*args)
        for name, repeat in [("", 1), ("a" * 17, 1), ("a\0", 1), ("😀" * 9, 1),
                             ("a", True), ("a", 0), ("a", 256)]:
            with self.subTest(name=name, repeat=repeat), self.assertRaises(ValueError):
                Macro(name, repeat)
        Macro("😀" * 8)

    def test_sequence_diagnostics(self):
        macro = Macro(events=(Event("a", "up"), Event("b", "down"), Event("b", "down")))
        self.assertEqual(len(macro.problems), 3)
        self.assertIn("Missing release: b", macro.problems)

    def test_roundtrip_and_exclusive_save(self):
        doc = Macro("Copy", 2, (Event("c", "down", 10), Event("c", "up", 20)))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "macro.json"
            doc.save(path)
            self.assertEqual(Macro.load(path), doc)
            with self.assertRaises(FileExistsError):
                Macro().save(path)
            self.assertEqual(Macro.load(path), doc)

    def test_malformed_import_is_atomic(self):
        editor = MacroEditor()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for data in [{}, [], {"format": "retro87-macro", "version": True, "name": "x", "repeat": 1, "events": []},
                         {"format": "retro87-macro", "version": 1, "name": "x", "repeat": 1, "events": [None]}]:
                path.write_text(json.dumps(data))
                editor.load(str(path))
                self.assertTrue(editor.error)
                self.assertEqual(editor.document, Macro())
            path.write_bytes(b"x" * (256 * 1024 + 1))
            editor.load(str(path))
            self.assertIn("too large", editor.error)

    def test_edit_boundaries_and_discard(self):
        editor = MacroEditor()
        editor.append("a", "down", 0)
        editor.append("a", "up", 5)
        original = editor.document
        editor.move(0, -1)
        self.assertEqual(editor.document, original)
        editor.remove(-1)
        self.assertEqual(editor.document, original)
        editor.update(0, "a", "down", 10)
        editor.move(0, 1)
        self.assertEqual(editor.document.events[1].delay_ms, 10)
        editor.remove(0)
        self.assertEqual(len(editor.document.events), 1)
        editor.discard()
        self.assertEqual(editor.document, Macro())
        editor.document = Macro(events=(Event("a", "down"),) * MAX_STEPS)
        editor.append("a", "up", 0)
        self.assertEqual(len(editor.document.events), MAX_STEPS)
        self.assertTrue(editor.error)

    def test_trigger_roundtrip_and_legacy_import(self):
        editor = MacroEditor()
        editor.setTrigger("k1")
        self.assertTrue(editor.state["dirty"])
        editor.setTrigger("a")
        self.assertEqual(editor.document.trigger, "k1")
        self.assertTrue(editor.error)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "macro.json"
            editor.save(str(path))
            self.assertEqual(Macro.load(path).trigger, "k1")
            data = json.loads(path.read_text())
            data["version"] = 1
            del data["trigger"]
            path.write_text(json.dumps(data))
            self.assertEqual(Macro.load(path).trigger, "")

    def test_save_load_lifecycle(self):
        editor = MacroEditor()
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "macro.json")
            editor.append("a", "down", 0)
            editor.new()
            self.assertTrue(editor.state["dirty"])
            editor.save(path)
            self.assertFalse(editor.state["dirty"])
            editor.append("a", "up", 20)
            editor.load(path)
            self.assertTrue(editor.error)
            self.assertEqual(len(editor.document.events), 2)
            editor.save(path)
            self.assertTrue(editor.state["dirty"])
            editor.discard()
            self.assertEqual(len(editor.document.events), 1)
            editor.load(path)
            self.assertFalse(editor.error)
            editor.new()
            self.assertEqual(editor.document, Macro())
            self.assertFalse(editor.state["dirty"])


if __name__ == "__main__":
    unittest.main()
