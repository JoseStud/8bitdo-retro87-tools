import unittest
from unittest.mock import Mock, patch
import struct

import retro87_core as protocol
from retro87_macro_backup import capture, assignments


class MacroBackupTests(unittest.TestCase):
    def test_macro_reads_and_writes_have_separate_boundaries(self):
        packet = protocol.packet(7, 0x9000, read_size=48)
        self.assertEqual(packet[:10], bytes.fromhex("81 04 07 00 30 00 00 90 00 00"))
        for command in (5, 6):
            with self.assertRaises(ValueError):
                protocol.packet(command)
        for address in (-1, 0xa000, 0x9fff):
            with self.assertRaises(ValueError):
                protocol.packet(7, address, read_size=2)
        with self.assertRaises(ValueError):
            protocol.packet(7, payload=b"x")
        with self.assertRaises(ValueError):
            protocol.packet(1, 0x9000, payload=b"x")

    def test_whole_block_handles_short_reads_and_retains_unused_bytes(self):
        device = protocol.Keyboard()
        device.read = Mock(side_effect=lambda offset, size, command: bytes([offset // 4096]) * min(17, size))
        self.assertEqual(device.read_macro_block(0x9000), b"\x09" * 4096)
        self.assertTrue(all(c.args[2] == 7 for c in device.read.call_args_list))
        last = device.read.call_args_list[-1].args
        self.assertEqual(last[0] + last[1], 0xa000)
        for address in (-4096, 1, True, 0xa000):
            with self.assertRaises(ValueError):
                device.read_macro_block(address)
        with self.assertRaises(ValueError):
            device.read_all(7)

    def test_macro_response_offset_and_length(self):
        device = protocol.Keyboard()
        device.fd = 123
        reply = bytes.fromhex("02 04 03 07 02 00 40 10 00 00 aa bb").ljust(64, b"\0")
        with patch.object(protocol.os, "write", return_value=64), patch.object(protocol.select, "select", return_value=([123], [], [])), patch.object(protocol.os, "read", return_value=reply):
            self.assertEqual(device.read(0x1040, 2, 7), b"\xaa\xbb")
            with self.assertRaises(RuntimeError):
                device.read(0x1040, 1, 7)

    def device(self):
        device = Mock(connection="simulated")
        profile = protocol.default_profile("Test", "solid")
        device.read_all.side_effect = lambda command=2: profile if command == 2 else bytes(283)
        device.read_macro_block.side_effect = lambda address: bytes([address // 4096]) * 4096
        return device

    def test_backup_covers_every_byte_twice_without_writes(self):
        device = self.device()
        result = capture(device)
        self.assertEqual(result["format"], "retro87-macro-backup")
        self.assertEqual(len(result["blocks"]), 10)
        self.assertEqual(device.read_macro_block.call_count, 20)
        self.assertTrue(all(len(bytes.fromhex(block["data"])) == 4096 for block in result["blocks"]))
        device.apply.assert_not_called()
        device.write_range.assert_not_called()

    def test_backup_refuses_changed_or_short_storage(self):
        for reads in ([bytes(4096)] * 10 + [b"x" * 4096], [bytes(48)]):
            device = self.device()
            device.read_macro_block.side_effect = reads
            with self.assertRaises(RuntimeError):
                capture(device)

    def test_backup_refuses_out_of_coverage_reference_before_reading_macros(self):
        device = self.device()
        profile = bytearray(protocol.default_profile("Test", "solid"))
        struct.pack_into("<II", profile, 44 + protocol.SOURCES["k7"]["slot"] * 12, 0xa000, 4)
        device.read_all.side_effect = [bytes(profile), bytes(283)]
        with self.assertRaisesRegex(RuntimeError, "coverage"):
            capture(device)
        device.read_macro_block.assert_not_called()

    def test_backup_refuses_configuration_changes(self):
        device = self.device()
        profile = protocol.default_profile("Test", "solid")
        device.read_all.side_effect = [profile, bytes(283), bytes(protocol.PROFILE_SIZE)]
        with self.assertRaisesRegex(RuntimeError, "configuration changed"):
            capture(device)

    def test_assignment_inspection_uses_mapping_type(self):
        profile = bytearray(protocol.default_profile("Test", "solid"))
        offset = 40 + protocol.SOURCES["k1"]["slot"] * 12
        struct.pack_into("<II", profile, offset + 4, 0, 4)
        self.assertEqual(assignments(profile), {"k1": 0})
        profile[:4] = bytes(4)
        self.assertEqual(assignments(profile), {})


if __name__ == "__main__":
    unittest.main()
