import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import retro87_core as protocol
from retro87_model import ApplyFailure, Draft, Snapshot, SimulatedKeyboard, apply_draft, decode, patch_bytes


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.original = Snapshot.load(protocol.ROOT / "original-config.json")
        draft = Draft(self.original)
        draft.create_profile("Test")
        self.initialized = Snapshot(draft.profile, self.original.led)

    def test_staging_does_not_touch_hardware(self):
        with patch.object(protocol.os, "write", side_effect=AssertionError("Unexpected I/O")):
            draft = Draft(self.original)
            draft.create_profile("Linux")
            draft.map("capslock", "esc")
            draft.rgb("solid", "#8000ff", 50, 5)
            self.assertTrue(draft.dirty)
            self.assertEqual(self.original, draft.baseline)
            self.assertEqual(decode(draft.profile)["mappings"]["capslock"], "esc")
            self.assertEqual(patch_bytes(self.original.profile, draft.writes), draft.profile)
            self.assertLess(draft.writes[-1][0], 40)
            draft.discard()
            self.assertFalse(draft.dirty)

    def test_reverted_key_not_listed_while_other_edits_remain(self):
        draft = Draft(self.initialized)
        draft.map("a", "b")
        draft.volume(4)
        draft.map("a", "a")
        self.assertEqual(list(draft.changes), ["volume"])

    def test_apply_requires_approval_before_opening_device(self):
        factory = Mock()
        with self.assertRaises(PermissionError):
            apply_draft(Draft(self.original), device_factory=factory)
        factory.assert_not_called()

    def test_apply_backups_and_verifies(self):
        draft = Draft(self.initialized)
        draft.map("caps", "esc")
        device = SimulatedKeyboard(self.initialized, writable=True)
        with tempfile.TemporaryDirectory() as directory:
            result, backup = apply_draft(draft, approved=True, backup_dir=directory, device_factory=lambda **_: device)
            self.assertEqual(Snapshot.load(backup), self.initialized)
            self.assertEqual(result.profile, draft.profile)
            self.assertEqual(result.led, self.initialized.led)

    def test_conflict_never_writes(self):
        draft = Draft(self.initialized)
        draft.volume(4)
        changed = Snapshot(self.initialized.profile, b"\0" * 283)
        device = SimulatedKeyboard(changed, writable=True)
        with self.assertRaisesRegex(RuntimeError, "changed since"):
            apply_draft(draft, approved=True, device_factory=lambda **_: device)
        self.assertFalse(any(c[0] == "write" for c in device.calls))

    def test_backup_failure_never_writes(self):
        draft = Draft(self.initialized)
        draft.volume(4)
        device = SimulatedKeyboard(self.initialized, writable=True)
        with tempfile.TemporaryDirectory() as directory, patch.object(Snapshot, "save", side_effect=OSError("Disk full")):
            with self.assertRaises(OSError):
                apply_draft(draft, approved=True, backup_dir=directory, device_factory=lambda **_: device)
        self.assertFalse(any(c[0] == "write" for c in device.calls))

    def test_partial_failure_no_retry_or_rollback(self):
        draft = Draft(self.initialized)
        draft.map("a", "b")
        draft.volume(4)
        device = SimulatedKeyboard(self.initialized, writable=True, fail_after=1)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ApplyFailure) as context:
                apply_draft(draft, approved=True, backup_dir=directory, device_factory=lambda **_: device)
            self.assertEqual(Snapshot.load(context.exception.backup), self.initialized)
        self.assertEqual(sum(c[0] == "write" for c in device.calls), 1)
        self.assertTrue(draft.dirty)

    def test_unsupported_values_preserved(self):
        draft = Draft(self.original)
        draft.volume(5)
        self.assertEqual(draft.profile[:0x5c9], self.original.profile[:0x5c9])
        self.assertEqual(draft.profile[0x5ca:], self.original.profile[0x5ca:])
        self.assertEqual(decode(self.original.profile)["lighting"]["mode"], "ripple")
        self.assertIsNone(decode(self.original.profile)["lighting"]["brightness"])

    def test_preset_selection_keeps_parameters(self):
        draft = Draft(self.original)
        draft.preset("starlight")
        self.assertEqual(draft.profile[0x5d0:0x5f9], self.original.profile[0x5d0:0x5f9])

    def test_preset_activation_matches_vendor_sequence(self):
        # XboxLedView.*_ModeDown (PID_XBOXJP): custom flag cleared if set, then the preset.
        for mode in protocol.MODES:
            with self.subTest(mode=mode):
                draft = Draft(self.original)
                draft.preset(mode)
                self.assertEqual(draft.profile[0x5fa], self.original.profile[0x5fa])
                expected = [(0x5ca, bytes([protocol.MODES[mode]]))]
                if self.original.profile[0x5f9]:
                    expected.insert(0, (0x5f9, b"\0"))
                if self.original.profile[0x5ca] == protocol.MODES[mode]:
                    expected.pop()
                self.assertEqual(draft.writes, expected)

    def test_cleared_custom_flag_is_not_rewritten(self):
        profile = bytearray(self.original.profile)
        profile[0x5f9] = 0
        draft = Draft(Snapshot(bytes(profile), self.original.led))
        draft.preset("solid")
        self.assertEqual(draft.writes, [(0x5ca, b"\x03")])

    def test_profile_active_flag_is_decoded(self):
        profile = bytearray(self.original.profile)
        self.assertEqual(decode(bytes(profile))["profileActive"], profile[0x24] == 1)
        profile[0x24] = 1
        self.assertTrue(decode(bytes(profile))["profileActive"])

    def test_custom_leds_stage_apply_and_discard(self):
        draft = Draft(self.initialized)
        draft.custom_leds({"space": "#00ff00"}, default="#0000ff", effect="breathing", brightness=40, speed=3)
        self.assertTrue(draft.dirty)
        self.assertEqual(draft.writes, [(0x5f9, b"\x01")])
        self.assertIn("leds", draft.changes)
        decoded = protocol.decode_led(draft.led)
        self.assertEqual((decoded["effect"], decoded["brightness"], decoded["speed"]), ("breathing", 40, 3))
        self.assertEqual(decoded["colors"]["space"], "#00ff00")
        device = SimulatedKeyboard(self.initialized, writable=True)
        with tempfile.TemporaryDirectory() as folder:
            result, backup = apply_draft(draft, approved=True, backup_dir=folder, device_factory=lambda writable: device)
        self.assertEqual([c[0] for c in device.calls], ["read", "read", "write_led", "write", "read", "read"])
        self.assertEqual(result.led, draft.led)
        draft.discard()
        self.assertFalse(draft.dirty)
        self.assertEqual(draft.led, self.initialized.led)
        draft.custom_leds({"w": "#ff0000"}, effect="off", brightness=100)
        self.assertEqual(protocol.decode_led(draft.led)["brightness"], 0)
        self.assertIn("off (0% brightness)", draft.changes["leds"])
        draft.custom_leds({})
        draft.preset("solid")
        self.assertEqual(draft.profile[0x5f9], 0)

    def test_every_preset_codec_and_preserved_bytes(self):
        expected = {
            "solid": "7f01123456", "cycle": "7f07", "color-ripple": "7f0705",
            "breathing": "7f0701123456", "ripple": "7f0701123456",
            "resonance": "7f0701123456abcdef", "starlight": "7f071e01123456abcdef",
        }
        for mode, raw in expected.items():
            with self.subTest(mode=mode):
                draft = Draft(self.original)
                draft.rgb(mode, "#123456", 50, 4, echo_color="#abcdef", direction=5, count=30)
                offset, size = protocol.THEMES[mode]
                self.assertEqual(draft.profile[offset:offset+size].hex(), raw)
                allowed = set(range(offset, offset+size)) | {0x5f9, 0x5ca}
                for i, (before, after) in enumerate(zip(self.original.profile, draft.profile)):
                    if i not in allowed:
                        self.assertEqual(before, after)
                lighting = decode(draft.profile)["lighting"]
                self.assertEqual(lighting["mode"], mode)
                self.assertEqual(lighting["brightness"], 50)
                if mode != "solid":
                    self.assertEqual(lighting["speed"], 4)
                if mode in ("resonance", "starlight"):
                    self.assertEqual(lighting["echoColor"], "#abcdef")
                if mode == "color-ripple":
                    self.assertEqual(lighting["direction"], 5)
                if mode == "starlight":
                    self.assertEqual(lighting["count"], 30)

    def test_activation_and_profile_marker_written_last(self):
        draft = Draft(self.original)
        draft.create_profile("Linux")
        draft.rgb("solid", "#123456", 50, 5)
        offsets = [o for o, _ in draft.writes]
        self.assertLess(offsets.index(0x5d0), offsets.index(0x5ca))
        self.assertEqual(offsets[-1], 0)
        self.assertEqual(patch_bytes(draft.baseline.profile, draft.writes), draft.profile)
        self.assertTrue(all(len(b) <= 53 for _, b in draft.writes))

    def test_theme_transactions_include_unchanged_bytes(self):
        for mode, (offset, size) in protocol.THEMES.items():
            with self.subTest(mode=mode):
                draft = Draft(self.original)
                draft.rgb(mode, "#00c8ff", 50, 5)
                self.assertIn((offset, draft.profile[offset:offset+size]), draft.writes)
                # Editing only brightness must still send the complete struct.
                baseline = Snapshot(draft.profile, self.original.led)
                changed = Draft(baseline)
                changed.rgb(mode, "#00c8ff", 60, 5)
                self.assertEqual(changed.writes, [(offset, changed.profile[offset:offset+size])])
                self.assertEqual(patch_bytes(baseline.profile, changed.writes), changed.profile)

    def test_brightness_matches_vendor_integer_conversion(self):
        for brightness in range(101):
            writes = protocol.rgb_plan("solid", "#ffffff", brightness, 5)
            self.assertEqual(writes[0][1][0], brightness * 255 // 100)

    def test_inactive_theme_edits_remain_in_review(self):
        draft = Draft(self.original)
        draft.rgb("solid", "#123456", 50, 5)
        draft.rgb("breathing", "#abcdef", 40, 3)
        draft.preset("ripple")
        self.assertIn("rgb:solid", draft.changes)
        self.assertIn("rgb:breathing", draft.changes)

    def test_invalid_effect_parameters_are_atomic(self):
        draft = Draft(self.original)
        for mode, options in [("color-ripple", {"direction": 6}), ("starlight", {"count": 4}),
                              ("starlight", {"count": 101}), ("resonance", {"echo_color": "bad"})]:
            with self.assertRaises(ValueError):
                draft.rgb(mode, "#123456", 50, 5, **options)
            self.assertFalse(draft.dirty)
            self.assertFalse(draft.changes)

    def test_invalid_edits_do_not_mutate(self):
        draft = Draft(self.original)
        for action in [lambda: draft.volume(0), lambda: draft.volume(6), lambda: draft.create_profile("😀" * 9), lambda: draft.rgb("solid", "nope", 50, 5)]:
            with self.assertRaises(ValueError):
                action()
            self.assertFalse(draft.dirty)

    def test_export_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.json"
            self.original.save(path)
            with self.assertRaises(FileExistsError):
                self.initialized.save(path)
            self.assertEqual(Snapshot.load(path), self.original)

    def test_malformed_snapshot_errors(self):
        from io import BytesIO
        for raw in [b"[]", b"not-json", b"\xff", b" " * 65537,
                    b'{"device":"2dc8:202e"}',
                    b'{"device":"2dc8:202e","profile_hex":1,"led_hex":null}']:
            path = Mock()
            path.open.return_value = BytesIO(raw)
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                protocol.load_snapshot(path)


if __name__ == "__main__":
    unittest.main()
