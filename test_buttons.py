import unittest
from unittest.mock import Mock, MagicMock, patch

import retro87_buttons as buttons


class ButtonTests(unittest.TestCase):
    def test_only_extension_bits_are_decoded(self):
        for i in range(8):
            report = bytearray(64)
            report[:4] = b"\x02\x04\x03\x09"
            report[26 + (i + 2) // 8] = 1 << ((i + 2) % 8)
            self.assertEqual(buttons.extension_buttons(report), (f"k{i + 1}",))
        report = bytearray(b"\xff" * 64)
        report[:4] = b"\x02\x04\x03\x09"
        report[26:28] = b"\x03\xfc"  # Every bit except the eight accessory bits.
        self.assertEqual(buttons.extension_buttons(report), ())
        report[3] = 7  # Storage response must never become a button event.
        self.assertIsNone(buttons.extension_buttons(report))
        self.assertIsNone(buttons.extension_buttons(bytes(27)))

    def test_mode_restored_and_lock_closed_on_stop(self):
        device = MagicMock(fd=123)
        monitor = buttons.ButtonMonitor(Mock(return_value=device))
        with patch.object(buttons.os, "write", return_value=64) as write:
            monitor.start()
            monitor.stop()
            monitor.stop()
        self.assertEqual([call.args[1][:4] for call in write.call_args_list],
                         [b"\x81\x04\x08\x01", b"\x81\x04\x08\x00"])
        device.__exit__.assert_called_once_with(None, None, None)

    def test_restore_attempted_after_short_start(self):
        device = MagicMock(fd=123)
        monitor = buttons.ButtonMonitor(Mock(return_value=device))
        with patch.object(buttons.os, "write", side_effect=[1, 64]) as write:
            with self.assertRaises(OSError):
                monitor.start()
        self.assertEqual(write.call_count, 2)
        self.assertIsNone(monitor.device)
        device.__exit__.assert_called_once()

    def test_failed_restore_still_releases_device(self):
        device = MagicMock(fd=123)
        monitor = buttons.ButtonMonitor()
        monitor.device = device
        with patch.object(buttons.os, "write", side_effect=OSError("Disconnected")):
            with self.assertRaises(OSError):
                monitor.stop()
        self.assertIsNone(monitor.device)
        device.__exit__.assert_called_once()

    def test_poll_filters_acknowledgments_and_bounds_work(self):
        monitor = buttons.ButtonMonitor()
        monitor.device = MagicMock(fd=123)
        with patch.object(buttons.select, "select", return_value=([123], [], [])), patch.object(buttons.os, "read", return_value=b"\x02\x04\x03\x08".ljust(64, b"\0")) as read:
            self.assertEqual(monitor.poll(), [])
            self.assertEqual(read.call_count, 64)


if __name__ == "__main__":
    unittest.main()
