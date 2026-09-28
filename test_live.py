import importlib.util
from pathlib import Path
import tempfile
import unittest

from PySide6.QtGui import QColor, QImage

import retro87_core as protocol
from retro87_live import LiveMirror
from retro87_model import SimulatedKeyboard, Snapshot
from retro87_service import Controller


class LiveMirrorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 10.0
        self.device = SimulatedKeyboard(Snapshot(protocol.default_profile("Live", "solid"),
                                                 protocol.led_block({}, brightness=40)), writable=True)
        self.controller = Controller(lambda writable: self.device, backup_dir=Path(self.tmp.name) / "backups")
        self.live = LiveMirror(self.controller, self.tmp.name, allowed=True, clock=lambda: self.now)
        self.addCleanup(self.live.close)
        self.live.set_enabled(True)

    def frame(self, color="red", screen="DP-1"):
        path = self.live.target(screen, unlocked=True)
        self.assertTrue(path)
        image = QImage(192, 108, QImage.Format.Format_RGB32)
        image.fill(QColor(color))
        self.assertTrue(image.save(path))
        return path

    def test_requires_explicit_opt_in(self):
        live = LiveMirror(self.controller, self.tmp.name)
        with self.assertRaisesRegex(ValueError, "experimental-live"):
            live.set_enabled(True)
        self.assertEqual(live.target("DP-1", unlocked=True), "")
        self.assertEqual(self.device.calls, [])

    def test_real_mapping_brightness_backup_and_rate_limit(self):
        self.assertTrue(self.live.submit(self.frame(), unlocked=True))
        led = protocol.decode_led(self.device.snapshot.led)
        self.assertEqual(led["brightness"], 40)
        self.assertEqual(self.device.snapshot.led, protocol.led_block(
            dict.fromkeys(protocol.LED_KEYS, "#ff0000"), brightness=40))
        self.assertTrue(self.controller.status()["perKey"])
        self.assertEqual(self.live.target("DP-1", unlocked=True), "")
        self.now += 0.5
        self.assertTrue(self.live.submit(self.frame("blue"), unlocked=True))
        self.assertEqual(self.live.frames, 2)
        self.assertEqual(len(list((Path(self.tmp.name) / "backups").iterdir())), 1)

    def test_duplicate_frames_do_not_even_open_device(self):
        self.live.submit(self.frame(), unlocked=True)
        count = len(self.device.calls)
        self.now += 0.5
        self.assertFalse(self.live.submit(self.frame(), unlocked=True))
        self.assertEqual(len(self.device.calls), count)

    def test_lock_and_stop_reject_inflight_captures(self):
        path = self.frame()
        self.assertFalse(self.live.submit(path, unlocked=False))
        self.assertFalse(Path(path).exists())
        self.assertEqual(self.live.target("DP-1", unlocked=False), "")
        path = self.frame()
        self.live.set_enabled(False)
        self.assertFalse(self.live.submit(path, unlocked=True))
        self.assertFalse(Path(path).exists())
        self.assertEqual(self.device.calls, [])

    def test_expired_unknown_and_previous_session_frames_ignored(self):
        self.assertFalse(self.live.submit("/unknown", unlocked=True))
        path = self.frame()
        self.now += 6
        self.assertFalse(self.live.submit(path, unlocked=True))
        path = self.frame()
        self.live.set_enabled(True)
        self.assertFalse(self.live.submit(path, unlocked=True))
        self.assertEqual(self.device.calls, [])

    def test_multimonitor_lease_and_explicit_screen(self):
        path = self.frame()
        self.assertEqual(self.live.target("DP-2", unlocked=True), "")
        self.now += 6
        self.assertTrue(self.live.target("DP-2", unlocked=True))
        self.assertFalse(Path(path).exists())
        self.live.set_enabled(True)
        self.live.screen = "DP-2"
        self.assertEqual(self.live.target("DP-1", unlocked=True), "")
        self.assertTrue(self.live.target("DP-2", unlocked=True))

    def test_bad_image_latches_error_without_writes(self):
        path = self.live.target("DP-1", unlocked=True)
        Path(path).write_bytes(b"not a png")
        self.assertFalse(self.live.submit(path, unlocked=True))
        self.assertTrue(self.live.error)
        self.assertEqual(self.live.target("DP-1", unlocked=True), "")
        self.assertEqual(self.device.calls, [])
        self.live.set_enabled(True)
        self.assertTrue(self.live.submit(self.frame(), unlocked=True))

    def test_failed_device_write_stops_stream_and_retains_backup(self):
        self.device.fail_after = 0
        self.assertFalse(self.live.submit(self.frame(), unlocked=True))
        self.assertIn("Backup:", self.live.error)
        self.now += 10
        self.assertEqual(self.live.target("DP-1", unlocked=True), "")
        self.assertEqual(self.live.frames, 0)



class FakeLamps:
    def __init__(self):
        self.connected, self.frames, self.closed = True, [], 0

    def available(self):
        return self.connected

    def set_leds(self, colors):
        self.frames.append(colors)

    def close(self):
        self.closed += 1


class UsbLiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 10.0
        self.device = SimulatedKeyboard(Snapshot(protocol.default_profile("Live", "solid"),
                                                 protocol.led_block({}, brightness=40)), writable=True)
        self.controller = Controller(lambda writable: self.device, backup_dir=Path(self.tmp.name) / "backups")
        self.lamps = FakeLamps()
        self.live = LiveMirror(self.controller, self.tmp.name, clock=lambda: self.now, lamps=self.lamps)
        self.addCleanup(self.live.close)

    def frame(self, color="red"):
        path = self.live.target("DP-1", unlocked=True)
        self.assertTrue(path)
        image = QImage(192, 108, QImage.Format.Format_RGB32)
        image.fill(QColor(color))
        self.assertTrue(image.save(path))
        return path

    def test_usb_streams_without_opt_in_and_never_writes_configuration(self):
        self.live.set_enabled(True)
        self.assertTrue(self.live.submit(self.frame(), unlocked=True))
        self.assertEqual(self.lamps.frames[-1], dict.fromkeys(protocol.LED_KEYS, "#ff0000"))
        self.now += LiveMirror.USB_INTERVAL
        self.assertTrue(self.live.submit(self.frame("blue"), unlocked=True))
        self.assertEqual(len(self.lamps.frames), 2)
        self.assertEqual(self.device.calls, [])

    def test_disabling_returns_lighting_to_keyboard(self):
        self.live.set_enabled(True)
        self.live.submit(self.frame(), unlocked=True)
        closed = self.lamps.closed
        self.live.set_enabled(False)
        self.assertGreater(self.lamps.closed, closed)

    def test_without_cable_requires_opt_in(self):
        self.lamps.connected = False
        with self.assertRaisesRegex(ValueError, "USB cable"):
            self.live.set_enabled(True)

    def test_unplugged_cable_stops_instead_of_writing_flash(self):
        self.live.set_enabled(True)
        path = self.frame()
        self.lamps.connected = False
        self.assertFalse(self.live.submit(path, unlocked=True))
        self.assertIn("disconnected", self.live.error)
        self.assertEqual(self.device.calls, [])


class CaptureInstallTests(unittest.TestCase):
    def test_install_upgrade_and_protect_unmanaged_copy(self):
        spec = importlib.util.spec_from_file_location("installer", Path(__file__).with_name("install-live-wallpaper.py"))
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "source", Path(tmp) / "target"
            ui = source / "contents/ui"
            ui.mkdir(parents=True)
            original = "WallpaperItem {\n id: root\n Loader { id: surfaceLoader }\n}\n"
            (ui / "main.qml").write_text(original)
            installer.install(source, target)
            installer.install(source, target)
            self.assertEqual((target / "contents/ui/main.qml").read_text().count("Retro87Capture {"), 1)
            self.assertEqual((ui / "main.qml").read_text(), original)
            self.assertTrue((target / "contents/ui/Retro87Capture.qml").exists())
            (target / installer.MARKER).unlink()
            with self.assertRaises(ValueError):
                installer.install(source, target)


if __name__ == "__main__":
    unittest.main()
