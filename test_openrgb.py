import socket
import struct
import threading
import unittest

import retro87_core as protocol
import retro87_openrgb as openrgb


def string(text):
    raw = text.encode() + b"\0"
    return struct.pack("<H", len(raw)) + raw


def mode(name, value, flags=0, brightness=(0, 0, 0), speed=(0, 0, 0), colors=()):
    return (string(name) + struct.pack("<iIIIIIIIIIIIH", value, flags, speed[0], speed[1], brightness[0],
                                       brightness[1], len(colors), len(colors), speed[2], brightness[2], 0,
                                       2 if colors else 0, len(colors))
            + b"".join(struct.pack("<I", c) for c in colors))


def device(name, description, modes, active, leds):
    zone = string("Keyboard") + struct.pack("<IIII", 2, len(leds), len(leds), len(leds)) + struct.pack("<HH", 0, 0)
    body = (struct.pack("<I", 5) + string(name) + string("8BitDo") + string(description) + string("")
            + string("") + string("HID: /dev/hidraw8") + struct.pack("<Hi", len(modes), active) + b"".join(modes)
            + struct.pack("<H", 1) + zone + struct.pack("<H", len(leds))
            + b"".join(string(n) + struct.pack("<I", i) for i, n in enumerate(leds))
            + struct.pack("<H", len(leds)) + b"\0\0\0\0" * len(leds))
    return struct.pack("<I", len(body) + 4) + body


EFFECT_LEDS = ["Key: " + openrgb.KEY_NAMES[k] if k not in ("backslash", "ka", "kb")
               else {"backslash": "Key: \\ (ANSI)", "ka": "Key: A (Super button)", "kb": "Key: B (Super button)"}[k]
               for k in protocol.LED_KEYS]
BRIGHT, SPEED = (0, 255, 153), (10, 1, 6)
STORED_MODES = [
    mode("Custom", 255, 0x230, BRIGHT),
    mode("Static", 3, 0x250, (0, 255, 255), colors=[0x0000FF]),
    mode("Breathing", 6, 0x251, BRIGHT, SPEED, colors=[0x00FF00]),
    mode("Resonance", 1, 0x251, BRIGHT, SPEED, colors=[0, 0x00A5FF]),
    mode("Off", 0, 0x200),
]
# Over the cable the device also has Direct (LampArray), listed first; indices below include it.
EFFECTS = device("8BitDo Retro 87 Mecha BREAK (USB)", "8BitDo Retro 87 Keyboard Device (USB cable)",
                 [mode("Direct", 0x100, 0x20)] + STORED_MODES, 1, EFFECT_LEDS)
DONGLE = device("8BitDo Retro 87 Mecha BREAK", "8BitDo Retro 87 Keyboard Device (2.4 GHz dongle)",
                STORED_MODES, 0, EFFECT_LEDS)


class FakeServer:
    def __init__(self, devices):
        self.devices, self.received = list(devices), []
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.port = self.listener.getsockname()[1]
        self.connection = None
        threading.Thread(target=self.serve, daemon=True).start()

    def read(self, sock, size):
        data = b""
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError
            data += chunk
        return data

    def reply(self, device, packet, data):
        self.connection.sendall(b"ORGB" + struct.pack("<III", device, packet, len(data)) + data)

    def serve(self):
        self.connection, _ = self.listener.accept()
        try:
            while True:
                header = self.read(self.connection, 16)
                index, packet, size = struct.unpack_from("<III", header, 4)
                data = self.read(self.connection, size)
                if packet == openrgb.REQUEST_PROTOCOL_VERSION:
                    self.reply(0, packet, struct.pack("<I", 6))
                elif packet == openrgb.REQUEST_CONTROLLER_COUNT:
                    self.reply(0, packet, struct.pack("<I", len(self.devices)))
                elif packet == openrgb.REQUEST_CONTROLLER_DATA:
                    self.reply(index, packet, self.devices[index])
                elif packet in (openrgb.UPDATE_MODE, openrgb.UPDATE_LEDS):
                    self.received.append((index, packet, data))
        except (ConnectionError, OSError):
            pass

    def notify_list_changed(self):
        self.reply(0, openrgb.DEVICE_LIST_UPDATED, b"")

    def wait(self, count):
        for _ in range(200):
            if len(self.received) >= count:
                return self.received
            threading.Event().wait(0.01)
        raise AssertionError(f"expected {count} packets, got {self.received}")

    def modes(self):
        result = []
        for index, packet, data in self.received:
            if packet == openrgb.UPDATE_MODE:
                size, mode_index = struct.unpack_from("<Ii", data)
                parsed = openrgb._Reader(data[8:]).mode()
                result.append((index, mode_index, parsed))
        return result

    def leds(self):
        return [(i, [struct.unpack_from("<I", d, 6 + 4*n)[0] for n in range(struct.unpack_from("<H", d, 4)[0])])
                for i, p, d in self.received if p == openrgb.UPDATE_LEDS]

    def close(self):
        self.listener.close()
        if self.connection:
            self.connection.close()


class OpenRGBTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeServer([EFFECTS])
        self.addCleanup(self.server.close)
        self.controller = openrgb.Controller(openrgb.Client(port=self.server.port))
        self.addCleanup(self.controller.client.close)

    def test_status_from_effects_device(self):
        state = self.controller.refresh()
        self.assertTrue(state["connected"], state["error"])
        self.assertEqual((state["connection"], state["perKey"], state["brightness"]), ("USB cable", True, 60))
        self.assertEqual(state["preset"], "solid")
        self.assertEqual(len(self.controller.effects.key_leds()), len(protocol.LED_KEYS))

    def test_settings_become_mode_updates(self):
        self.controller.refresh()
        self.controller.set("preset", "breathing")
        state = self.controller.set("speed", "9")
        self.controller.set("color", "#ff8000")
        self.server.wait(3)
        (_, first, _), (_, second, speed), (_, third, color) = self.server.modes()
        self.assertEqual((first, second, third), (3, 3, 3))
        self.assertEqual(speed.speed, 2)
        self.assertEqual(color.colors, [openrgb.rgb("#ff8000")])
        self.assertEqual((state["preset"], state["speed"], state["perKey"]), ("breathing", 9, False))

    def test_perkey_off_returns_to_last_preset(self):
        self.controller.refresh()
        self.controller.set("preset", "resonance")
        self.controller.set("perkey", "on")
        state = self.controller.set("perkey", "off")
        self.server.wait(3)
        self.assertEqual([m for _, m, _ in self.server.modes()], [4, 1, 4])
        self.assertEqual(state["preset"], "resonance")

    def test_brightness_scales_and_off_is_refused(self):
        self.controller.refresh()
        self.controller.set("brightness", "40")
        self.assertEqual(self.server.wait(1) and self.server.modes()[0][2].brightness, 102)
        self.controller.set("preset", "off")
        with self.assertRaisesRegex(ValueError, "off"):
            self.controller.set("brightness", "50")

    def test_picture_on_keys_writes_custom_colours_once(self):
        self.controller.refresh()
        self.controller.set("preset", "solid")
        self.controller.set_leds({"esc": "#ff0000", "space": "#00ff00"})
        self.server.wait(3)
        (_, colors), = self.server.leds()
        self.assertEqual(colors[protocol.LED_KEYS.index("space")], openrgb.rgb("#00ff00"))
        self.assertEqual(colors[EFFECT_LEDS.index("Key: Escape")], openrgb.rgb("#ff0000"))
        self.assertEqual(self.server.modes()[-1][1], 1)

    def test_live_uses_direct_mode_and_returns_to_stored_effect(self):
        self.controller.refresh()
        sink = openrgb.LampSink(self.controller)
        self.assertTrue(sink.available())
        sink.set_leds({"space": "#0000ff"})
        state = self.controller.status()
        self.assertEqual((state["perKey"], state["brightness"]), (True, 60))
        sink.set_leds({"space": "#ff0000"})
        sink.close()
        self.server.wait(4)
        self.assertEqual([(i, m) for i, m, _ in self.server.modes()], [(0, 0), (0, 1)])
        (_, first), (_, second) = self.server.leds()
        # Dimmed like the stored effect it replaces (60 %); OpenRGB fans space out to five lamps.
        self.assertEqual(second[protocol.LED_KEYS.index("space")], openrgb.rgb("#990000"))

    def test_brightness_during_live_only_dims_the_stream(self):
        self.controller.refresh()
        sink = openrgb.LampSink(self.controller)
        sink.set_leds({"esc": "#ffffff"})
        state = self.controller.set("brightness", "20")
        sink.set_leds({"esc": "#ffffff"})
        self.server.wait(3)
        self.assertEqual(state["brightness"], 20)
        self.assertEqual(len(self.server.modes()), 1)
        self.assertEqual(self.server.leds()[-1][1][EFFECT_LEDS.index("Key: Escape")], openrgb.rgb("#333333"))
        with self.assertRaisesRegex(ValueError, "live"):
            self.controller.set("color", "#ff0000")

    def test_direct_in_use_by_another_client_is_not_taken(self):
        self.server.devices = [EFFECTS.replace(struct.pack("<Hi", 6, 1), struct.pack("<Hi", 6, 0), 1)]
        self.controller.refresh()
        sink = openrgb.LampSink(self.controller)
        with self.assertRaisesRegex(RuntimeError, "in use"):
            sink.set_leds({"esc": "#ffffff"})
        sink.close()
        sink.takeover = True
        sink.set_leds({"esc": "#ffffff"})
        self.server.wait(1)
        self.assertEqual(self.server.modes(), [])  # already Direct: no mode change, just frames
        self.assertEqual(len(self.server.leds()), 1)

    def test_own_direct_survives_a_device_list_refresh(self):
        self.controller.refresh()
        sink = openrgb.LampSink(self.controller)
        sink.set_leds({"esc": "#ffffff"})
        self.controller.refresh()  # new Device objects; the keyboard is in Direct, set by us
        self.controller.effects.active_mode = 0
        sink.set_leds({"esc": "#000000"})
        self.server.wait(3)
        self.assertEqual(len(self.server.leds()), 2)

    def test_dongle_has_no_direct_mode(self):
        self.server.devices = [DONGLE]
        self.controller.refresh()
        self.assertFalse(openrgb.LampSink(self.controller).available())

    def test_device_list_change_is_noticed(self):
        self.controller.refresh()
        self.server.devices = []
        self.server.notify_list_changed()
        for _ in range(100):
            if self.controller.client.sync():
                break
            threading.Event().wait(0.01)
        state = self.controller.refresh()
        self.assertFalse(state["connected"])
        self.assertIn("does not see", state["error"])


class UnreachableTests(unittest.TestCase):
    def test_server_not_running(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        listener.close()
        state = openrgb.Controller(openrgb.Client(port=port)).refresh()
        self.assertFalse(state["connected"])
        self.assertIn("OpenRGB is not running", state["error"])


if __name__ == "__main__":
    unittest.main()
