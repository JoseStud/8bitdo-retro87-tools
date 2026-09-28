import struct
import unittest

import retro87_core as protocol
import retro87_lamparray as lamparray


def lamp_array(count=len(lamparray.LAMP_KEYS), bindings=None):
    device = lamparray.LampArray.__new__(lamparray.LampArray)
    device.count, device.types, device.autonomous, device.sent = count, {}, None, []
    device.set_report = lambda report, payload: device.sent.append((report, payload))
    bindings = bindings or {}
    device.lamps = [{"id": i, "position": (0, 0, 0), "binding": bindings.get(i, 0)} for i in range(count)]
    return device


class ReportTests(unittest.TestCase):
    def test_report_types_detects_lamparray_feature_reports(self):
        descriptor = bytes.fromhex("0559 0901 a101 8511 b102 8514 b102 9102 c0")
        types, is_lamp_array = lamparray.report_types(descriptor)
        self.assertTrue(is_lamp_array)
        self.assertEqual(types, {0x11: {"feature"}, 0x14: {"feature", "output"}})
        self.assertFalse(lamparray.report_types(bytes.fromhex("0501 0906 a101 c0"))[1])

    def test_update_leaves_autonomous_mode_and_marks_last_report_complete(self):
        device = lamp_array()
        device.update({i: (i, 0, 255) for i in range(10)})
        self.assertEqual(device.sent[0], (lamparray.CONTROL, b"\0"))
        first, last = device.sent[1][1], device.sent[2][1]
        self.assertEqual(len(first), 50)
        count, flags, *rest = struct.unpack("<BB8H32B", first)
        self.assertEqual((count, flags, rest[:8]), (8, 0, list(range(8))))
        self.assertEqual(rest[8:12], [0, 0, 255, 255])
        count, flags, *rest = struct.unpack("<BB8H32B", last)
        self.assertEqual((count, flags, rest[:2]), (2, lamparray.UPDATE_COMPLETE, [8, 9]))

    def test_key_lamps_cover_every_key_and_space_bar(self):
        mapping = lamp_array(bindings={0: 0x29, 29: 0x31, 81: 0x2C}).key_lamps()
        self.assertEqual(set(mapping), set(protocol.LED_KEYS))
        self.assertEqual(mapping["space"], [79, 80, 81, 82, 83])
        self.assertEqual(mapping["backspace"], [29])

    def test_key_lamps_refuse_unknown_firmware_layouts(self):
        with self.assertRaisesRegex(RuntimeError, "lamp count"):
            lamp_array(count=90).key_lamps()
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            lamp_array(bindings={0: 0x04}).key_lamps()

    def test_sink_maps_key_colours_and_releases_device(self):
        device = lamp_array(bindings={0: 0x29})
        device.__enter__ = lambda: device
        exits = []
        device.__exit__ = lambda *args: exits.append(args)
        sink = lamparray.LampArraySink(factory=lambda: device)
        sink.set_leds({"esc": "#ff8000", "space": "#0000ff"})
        frame = {}
        count, _, *rest = struct.unpack("<BB8H32B", device.sent[-1][1])
        for i in range(count):
            frame[rest[i]] = tuple(rest[8 + 4*i:11 + 4*i])
        self.assertEqual(frame, {0: (255, 128, 0), **{i: (0, 0, 255) for i in range(79, 84)}})
        sink.close()
        self.assertEqual(len(exits), 1)


class DiscoveryTests(unittest.TestCase):
    def sysfs(self, driver=None):
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        device = root / "5-2"
        for name, value in (("idVendor", "2dc8"), ("idProduct", "2028"), ("busnum", "5"), ("devnum", "3")):
            (device / name).parent.mkdir(parents=True, exist_ok=True)
            (device / name).write_text(value + "\n")
        interface = device / "5-2:1.3"
        (interface / "ep_06").mkdir(parents=True)
        (interface / "ep_06/direction").write_text("out\n")
        (interface / "bInterfaceClass").write_text("03\n")
        (interface / "bInterfaceNumber").write_text("03\n")
        if driver:
            (root / driver).mkdir()
            (interface / "driver").symlink_to(root / driver)
        return root

    def test_found_unbound_or_claimed_by_usbfs(self):
        for driver in (None, "usbfs"):
            self.assertEqual(lamparray.find_interface(self.sysfs(driver)), ("/dev/bus/usb/005/003", 3))

    def test_skipped_when_a_kernel_driver_owns_it(self):
        self.assertIsNone(lamparray.find_interface(self.sysfs("usbhid")))

    def test_open_sink_stays_available(self):
        sink = lamparray.LampArraySink()
        sink.device = object()
        self.assertTrue(sink.available())


if __name__ == "__main__":
    unittest.main()
