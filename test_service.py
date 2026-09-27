import tempfile
import unittest
from pathlib import Path

import retro87_core as protocol
from retro87_model import Draft, Snapshot, SimulatedKeyboard
from retro87_service import Controller


class ThemePlanTests(unittest.TestCase):
    def setUp(self):
        self.profile = protocol.default_profile("Test", "breathing")

    def test_edits_one_field_and_keeps_the_rest(self):
        (offset, record), = protocol.theme_plan(self.profile, "breathing", brightness=40)
        self.assertEqual(offset, 0x5da)
        self.assertEqual(record, bytes([40 * 255 // 100, 3, 1, 0xff, 0xa5, 0x00]))
        (_, record), = protocol.theme_plan(self.profile, "breathing", speed=2, color="#0080ff")
        self.assertEqual(record, bytes([0xff, 9, 1, 0x00, 0x80, 0xff]))

    def test_matches_rgb_plan_encoding(self):
        expected = protocol.rgb_plan("starlight", "#112233", 70, 4, echo_color="#445566", count=5)[0]
        self.assertEqual(protocol.theme_plan(self.profile, "starlight", brightness=70, speed=4,
                                             color="#112233", echo="#445566")[0], expected)

    def test_unset_record_starts_from_vendor_defaults(self):
        blank = bytes(self.profile[:0x5d0]) + b"\xff" * (protocol.PROFILE_SIZE - 0x5d0)
        (_, record), = protocol.theme_plan(blank, "solid", brightness=100)
        self.assertEqual(record, b"\xff\x01\xff\xa5\x00")

    def test_rejects_fields_a_preset_does_not_have(self):
        with self.assertRaises(ValueError):
            protocol.theme_plan(self.profile, "solid", speed=5)
        with self.assertRaises(ValueError):
            protocol.theme_plan(self.profile, "cycle", color="#ffffff")
        with self.assertRaises(ValueError):
            protocol.theme_plan(self.profile, "off", brightness=5)
        with self.assertRaises(ValueError):
            protocol.theme_plan(self.profile, "breathing", brightness=101)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        original = Snapshot.load(protocol.ROOT / "original-config.json")
        draft = Draft(original)
        draft.create_profile("Test")
        draft.preset("breathing")
        self.device = SimulatedKeyboard(Snapshot(draft.profile, original.led), writable=True)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.controller = Controller(lambda writable: self.device, backup_dir=self.tmp.name)

    def writes(self):
        return [call[1] for call in self.device.calls if call[0] == "write"]

    def test_refresh_reports_state(self):
        state = self.controller.refresh()
        self.assertTrue(state["connected"])
        self.assertEqual(state["preset"], "breathing")
        self.assertEqual(state["brightness"], 100)
        self.assertTrue(state["hasSpeed"] and state["hasColor"])
        self.assertFalse(state["hasEcho"] or state["perKey"])
        self.assertTrue(state["tip"])  # Profile not active yet.

    def test_brightness_writes_the_theme_record_once_with_one_backup(self):
        state = self.controller.set("brightness", "30")
        self.assertEqual(state["brightness"], 30)
        self.assertEqual(self.writes(), [(0x5da, bytes([76, 3, 1, 0xff, 0xa5, 0x00]))])
        self.controller.set("color", "#00ff00")
        self.controller.set("color", "#00ff00")  # Unchanged: no write.
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(len(list(Path(self.tmp.name).iterdir())), 1)
        self.assertEqual(self.device.snapshot.profile, self.controller.profile)

    def test_preset_uses_the_vendor_activation_sequence(self):
        self.controller.set("preset", "solid")
        self.assertEqual(self.writes(), [(0x5ca, bytes([3]))])
        self.assertFalse(self.controller.status()["hasSpeed"])
        with self.assertRaises(ValueError):
            self.controller.set("speed", "3")

    def test_per_key_brightness_rewrites_only_the_led_header(self):
        self.device.snapshot = Snapshot(self.device.snapshot.profile, protocol.led_block({"a": "#ff0000"}))
        with self.assertRaises(ValueError):
            self.controller.set("perkey", "maybe")
        self.controller.set("perkey", "on")
        state = self.controller.set("brightness", "50")
        self.assertTrue(state["perKey"])
        self.assertEqual(state["brightness"], 50)
        block = self.device.snapshot.led
        self.assertEqual(block[0], 127)
        self.assertEqual(block[1:], protocol.led_block({"a": "#ff0000"})[1:])
        with self.assertRaises(ValueError):
            self.controller.set("color", "#ffffff")
        self.controller.set("preset", "cycle")
        self.assertEqual(self.device.snapshot.profile[0x5f9], 0)

    def test_per_key_needs_a_stored_layout(self):
        self.device.snapshot = Snapshot(self.device.snapshot.profile, b"\xff" * protocol.LED_SIZE)
        with self.assertRaises(ValueError):
            self.controller.set("perkey", "on")
        self.assertEqual(self.writes(), [])

    def test_uninitialized_keyboard_is_never_written(self):
        blank = Snapshot.load(protocol.ROOT / "original-config.json")
        self.device.snapshot = blank
        self.assertFalse(self.controller.refresh()["initialized"])
        with self.assertRaises(ValueError):
            self.controller.set("preset", "solid")
        self.assertEqual(self.writes(), [])

    def test_failed_write_reports_the_backup_and_forgets_state(self):
        self.device.fail_after = 0
        with self.assertRaises(RuntimeError) as caught:
            self.controller.set("brightness", "10")
        self.assertIn("Backup:", str(caught.exception))
        self.assertFalse(self.controller.status()["connected"])

    def test_missing_dongle_is_reported(self):
        def absent(writable):
            raise RuntimeError("Expected one 2dc8:202e configuration interface; found []")
        state = Controller(absent).refresh()
        self.assertFalse(state["connected"])
        self.assertIn("2dc8:202e", state["error"])


if __name__ == "__main__":
    unittest.main()
