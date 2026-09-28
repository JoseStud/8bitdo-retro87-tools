import argparse
import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch, Mock

import retro87 as r

def apply_plan(profile, plan):
    result = bytearray(profile)
    for offset, data in plan:
        result[offset:offset+len(data)] = data
    return bytes(result)

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.original, self.led = r.load_snapshot(r.ROOT / "original-config.json")
        self.profile = apply_plan(self.original, r.profile_plan(self.original, "Linux"))

    def test_known_read_packet_and_response(self):
        expected = bytes.fromhex("81 04 02 00 01 00 ca 05 00 00").ljust(64, b"\0")
        self.assertEqual(r.packet(2, 0x5ca, read_size=1), expected)
        # Actual response received from the user's wireless dongle.
        reply = bytes.fromhex("02 04 03 02 01 00 ca 05 00 00 07").ljust(64, b"\0")
        keyboard = r.Keyboard()
        keyboard.fd = 123
        with patch.object(r.os, "write", return_value=64) as write, patch.object(r.select, "select", return_value=([123], [], [])), patch.object(r.os, "read", return_value=reply):
            self.assertEqual(keyboard.read(0x5ca, 1), b"\x07")
            write.assert_called_once_with(123, expected)

    def test_bad_read_length_rejected(self):
        reply = bytes.fromhex("02 04 03 02 36 00 ca 05 00 00").ljust(64, b"\0")
        keyboard = r.Keyboard()
        keyboard.fd = 123
        with patch.object(r.os, "write", return_value=64), patch.object(r.select, "select", return_value=([123], [], [])), patch.object(r.os, "read", return_value=reply):
            with self.assertRaises(RuntimeError):
                keyboard.read(0x5ca, 1)

    def test_read_timeout_is_bounded(self):
        keyboard = r.Keyboard()
        keyboard.fd = 123
        with patch.object(r.os, "write", return_value=64), patch.object(r.select, "select", return_value=([], [], [])):
            with self.assertRaises(TimeoutError):
                keyboard.read(0, 1)

    def test_capslock_to_escape_vendor_layout(self):
        writes = r.mapping_plan(self.profile, "capslock", "escape")
        self.assertEqual(writes, [(0x334, bytes.fromhex("39 00 00 00 29 00 00 00 01 00 00 00"))])
        expected = bytes.fromhex("81 04 01 00 0c 63 34 03 00 00 39 00 00 00 29 00 00 00 01 00 00 00").ljust(64, b"\0")
        self.assertEqual(r.packet(1, *writes[0]), expected)

    def test_mapping_changes_only_one_record(self):
        writes = r.mapping_plan(self.profile, "a", "b")
        result = apply_plan(self.profile, writes)
        offset, data = writes[0]
        self.assertEqual(result[:offset], self.profile[:offset])
        self.assertEqual(result[offset+len(data):], self.profile[offset+len(data):])
        self.assertEqual(r.mapping_plan(self.profile, "a", "a")[0][1][-4:], bytes(4))

    def test_profile_creation_writes_vendor_defaults_and_commits_header_last(self):
        plan = r.profile_plan(self.original, "Linux")
        self.assertEqual(plan[-1][0], 0)
        self.assertTrue(all(len(data) <= 53 for _, data in plan))
        self.assertEqual(self.profile, r.default_profile("Linux", "ripple"))
        self.assertEqual(self.profile[0x5ca], self.original[0x5ca])
        self.assertEqual(self.profile[:4], bytes.fromhex("02 09 20 20"))
        self.assertEqual(self.profile[4:14], "Linux".encode("utf-16-be"))
        self.assertTrue(r.valid_profile(self.profile))
        self.assertEqual(self.profile[0x334:0x340], bytes.fromhex("39 00 00 00 39 00 00 00 00 00 00 00"))
        with self.assertRaises(ValueError):
            r.profile_plan(self.profile, "replacement")

    def test_uninitialized_remap_rejected(self):
        with self.assertRaises(ValueError):
            r.mapping_plan(self.original, "capslock", "esc")

    def test_solid_and_breathing_fields(self):
        solid = r.rgb_plan("solid", "#8000ff", 50, 5)
        self.assertEqual(solid[0], (0x5d0, bytes.fromhex("7f 01 80 00 ff")))
        self.assertEqual(solid[-1], (0x5ca, b"\x03"))
        self.assertEqual(solid[-2], (0x5f9, b"\0"))
        self.assertNotIn(0x5fa, [offset for offset, _ in solid])
        breathing = r.rgb_plan("breathing", "#ff0000", 100, 10)
        self.assertEqual(breathing[0], (0x5da, bytes.fromhex("ff 01 01 ff 00 00")))
        for params in [("solid", "zz0000", 50, 5), ("solid", "ff0000", 101, 5), ("solid", "ff0000", 50, 0)]:
            with self.assertRaises(ValueError):
                r.rgb_plan(*params)

    def test_vendor_default_profile_image(self):
        image = r.default_profile("Linux", "solid")
        self.assertEqual(len(image), r.PROFILE_SIZE)
        self.assertTrue(r.valid_profile(image))
        self.assertEqual(image[4:14].decode("utf-16-be"), "Linux")
        self.assertEqual(image[0x24:0x28], bytes(4))
        self.assertEqual(image[0x5c8:0x5d0].hex(), "000203002c010000")
        self.assertEqual(image[0x5d0:0x5d5].hex(), "ff01ffa500")
        self.assertEqual(image[0x5ef:0x5f9].hex(), "ff030501000000ffa500")
        self.assertEqual(image[0x5f9:], bytes(3))
        caps = r.SOURCES["capslock"]
        self.assertEqual(image[0x28+caps["slot"]*12:][:12], r.record(caps["code"], caps["code"], 0))
        self.assertEqual(r.default_profile("Linux")[0x5ca], r.MODES["resonance"])

    def test_led_layout_and_block(self):
        self.assertEqual(len(r.LED_KEYS), 87)
        self.assertEqual(len(set(r.LED_KEYS)), 87)
        indices = sorted(i for key in r.LED_KEYS for i in r.led_indices(key))
        self.assertEqual(indices, list(range(91)))
        self.assertEqual(r.led_indices("space"), [3, 4, 5, 6, 7])
        self.assertEqual(r.led_indices("escape"), [75])
        self.assertEqual((r.led_indices("supera"), r.led_indices("kb")), ([9], [10]))
        block = r.led_block({"w": "#ff0000", "space": "#00ff00"}, default="#0000ff", brightness=50, speed=4)
        self.assertEqual(len(block), r.LED_SIZE)
        self.assertEqual(block[:9].hex(), "7f0101071900000000")
        self.assertEqual(block[9+43*3:9+44*3], bytes.fromhex("ff0000"))
        self.assertEqual(block[9+3*3:9+8*3], bytes.fromhex("00ff00") * 5)
        self.assertEqual(block[9:12], bytes.fromhex("0000ff"))
        self.assertEqual(block[-1], 1)
        with self.assertRaises(ValueError):
            r.led_indices("num5x")
        off = r.led_block({}, effect="off", brightness=80)
        self.assertEqual((off[0], off[2]), (0, 1))
        self.assertEqual(r.led_block({}, effect="freeze")[2], 0)

    def test_led_write_sequence(self):
        keyboard = r.Keyboard(writable=True)
        keyboard.fd = 123
        block = r.led_block({}, default="#123456")
        acks = [bytes([2, 4, 3, 13, 0]).ljust(64, b"\0")] + [bytes([2, 4, 3, 14, min(53, r.LED_SIZE - o)]).ljust(64, b"\0") for o in range(0, r.LED_SIZE, 53)]
        with patch.object(r.os, "write", return_value=64) as write, patch.object(r.os, "read", side_effect=acks), \
             patch.object(r.select, "select", return_value=([123], [], [])), patch.object(r.time, "sleep") as sleep, \
             patch.object(keyboard, "read_all", return_value=block):
            keyboard.write_led(block)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [0.01] + [r.LED_CHUNK_DELAY] * 6)
        sent = [call.args[1] for call in write.call_args_list]
        self.assertEqual([p[2] for p in sent], [8, 13] + [14] * 6)
        self.assertEqual(b"".join(p[10:10+p[4]] for p in sent[2:]), block)

    def test_default_preview_never_calls_device(self):
        keyboard = Mock()
        args = argparse.Namespace(command="rgb", mode="solid", color="#8000ff", brightness=50, speed=5, apply=False)
        with contextlib.redirect_stdout(io.StringIO()):
            r.run_command(args, self.original, self.led, keyboard)
        self.assertEqual(keyboard.mock_calls, [])

    def test_write_guard_before_io(self):
        keyboard = r.Keyboard()
        with patch.object(r.os, "write") as write:
            with self.assertRaises(PermissionError):
                keyboard.write_range(0, b"\0")
            with self.assertRaises(PermissionError):
                keyboard.apply([(0, b"\0")])
            write.assert_not_called()

    def test_apply_ack_readback_and_failure_stop(self):
        keyboard = r.Keyboard(writable=True)
        keyboard.fd = 123
        reply = bytes.fromhex("02 04 03 01 01 03 ca 05 00 00").ljust(64, b"\0")
        with patch.object(r.os, "write", return_value=64) as write, patch.object(r.os, "read", return_value=reply), patch.object(r.select, "select", return_value=([123], [], [])), patch.object(keyboard, "read", return_value=b"\x03"):
            with patch.object(r.time, "sleep") as sleep:
                keyboard.apply([(0x5ca, b"\x03")])
            self.assertEqual(write.call_count, 2)
            sleep.assert_called_once_with(0.01)
        with patch.object(r.os, "write", return_value=64), patch.object(keyboard, "write_range") as write, patch.object(keyboard, "read", return_value=b"\xff"):
            with self.assertRaises(RuntimeError):
                keyboard.apply([(0x5ca, b"\x03"), (0x5f9, b"\0")])
            write.assert_called_once()

    def test_backup_roundtrip_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"backup.json"
            r.save_snapshot(path, self.original, self.led)
            self.assertEqual(r.load_snapshot(path), (self.original, self.led))
            with self.assertRaises(FileExistsError):
                r.save_snapshot(path, self.profile, self.led)

if __name__ == "__main__":
    unittest.main()
