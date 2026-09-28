"""Minimal OpenRGB SDK client (protocol version 4), standard library only.

The service drives the keyboard through an OpenRGB server instead of opening
it, so OpenRGB is the only program talking to the hardware. The Retro 87 is
one OpenRGB device, "8BitDo Retro 87 Keyboard Device (<connection>)":

  Custom, Static, ... Off   stored effects and the stored per-key picture, over
                            the dongle or the cable; each change is saved.
  Direct                    over the USB cable only: runtime per-key colours
                            (the keyboard's HID LampArray), never saved. Leaving
                            it for the unchanged previous mode only hands the
                            lighting back to the keyboard.

Wire format: OpenRGB NetworkProtocol.h / RGBController.cpp, protocol 4.
"""
import select
import socket
import struct
import threading

PROTOCOL_VERSION = 4
REQUEST_CONTROLLER_COUNT, REQUEST_CONTROLLER_DATA = 0, 1
REQUEST_PROTOCOL_VERSION, SET_CLIENT_NAME, DEVICE_LIST_UPDATED = 40, 50, 100
UPDATE_LEDS, SET_CUSTOM_MODE, UPDATE_MODE = 1050, 1100, 1101
EFFECTS_DESCRIPTION = "8BitDo Retro 87 Keyboard Device"

# Retro 87 key name (keycodes.json / retro87_core.LED_KEYS) -> OpenRGB LED name.
KEY_NAMES = {
    "esc": "Escape", "prtsc": "Print Screen", "scrlk": "Scroll Lock", "pause": "Pause/Break",
    "tilde": "`", "minus": "-", "equal": "=", "backspace": "Backspace", "insert": "Insert",
    "home": "Home", "pgup": "Page Up", "tab": "Tab", "leftbracket": "[", "rightbracket": "]",
    "backslash": "\\", "delete": "Delete", "end": "End", "pgdn": "Page Down", "capslock": "Caps Lock",
    "semicolon": ";", "quotation": "'", "enter": "Enter", "lshift": "Left Shift", "comma": ",",
    "period": ".", "slash": "/", "rshift": "Right Shift", "up": "Up Arrow", "lctrl": "Left Control",
    "lwin": "Left Windows", "lalt": "Left Alt", "space": "Space", "ralt": "Right Alt",
    "ka": "A (Super button)", "kb": "B (Super button)", "rctrl": "Right Control", "left": "Left Arrow",
    "down": "Down Arrow", "right": "Right Arrow",
}
KEY_NAMES.update({f"f{i}": f"F{i}" for i in range(1, 13)})
KEY_NAMES.update({f"num{i}": str(i) for i in range(10)})
KEY_NAMES.update({c: c.upper() for c in "abcdefghijklmnopqrstuvwxyz"})
# Other spellings of the same keys used by OpenRGB's keyboard layouts.
KEY_ALIASES = {"\\ (ANSI)": "backslash"}


class Mode:
    FIELDS = ("name", "value", "flags", "speed_min", "speed_max", "brightness_min", "brightness_max",
              "colors_min", "colors_max", "speed", "brightness", "direction", "color_mode", "colors")

    def __init__(self, **fields):
        for name in self.FIELDS:
            setattr(self, name, fields[name])

    def pack(self):
        name = self.name.encode() + b"\0"
        return (struct.pack("<H", len(name)) + name
                + struct.pack("<iIIIIIIIIIIIH", self.value, self.flags, self.speed_min, self.speed_max,
                              self.brightness_min, self.brightness_max, self.colors_min, self.colors_max,
                              self.speed, self.brightness, self.direction, self.color_mode, len(self.colors))
                + b"".join(struct.pack("<I", c) for c in self.colors))


class Device:
    def __init__(self, index, data):
        self.index = index
        reader = _Reader(data)
        self.type = reader.u32()
        self.name, self.vendor, self.description = reader.string(), reader.string(), reader.string()
        self.version, self.serial, self.location = reader.string(), reader.string(), reader.string()
        count, self.active_mode = reader.u16(), reader.i32()
        self.modes = [reader.mode() for _ in range(count)]
        for _ in range(reader.u16()):
            reader.zone()
        self.leds = []
        for _ in range(reader.u16()):
            self.leds.append(reader.string())
            reader.u32()
        self.colors = [reader.u32() for _ in range(reader.u16())]

    def mode(self, name):
        return next((i for i, mode in enumerate(self.modes) if mode.name == name), None)

    def key_leds(self):
        """{Retro 87 key name: [LED index]} for this device's keys."""
        names = {"Key: " + name: key for key, name in KEY_NAMES.items()}
        names.update({"Key: " + name: key for name, key in KEY_ALIASES.items()})
        result = {}
        for index, name in enumerate(self.leds):
            if name in names:
                result.setdefault(names[name], []).append(index)
        return result


class _Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, fmt):
        values = struct.unpack_from("<" + fmt, self.data, self.pos)
        self.pos += struct.calcsize("<" + fmt)
        return values

    def u16(self):
        return self.take("H")[0]

    def u32(self):
        return self.take("I")[0]

    def i32(self):
        return self.take("i")[0]

    def string(self):
        length = self.u16()
        raw = self.data[self.pos:self.pos + length]
        self.pos += length
        return raw.rstrip(b"\0").decode(errors="replace")

    def mode(self):
        name = self.string()
        values = self.take("iIIIIIIIIIIIH")
        colors = [self.u32() for _ in range(values[-1])]
        return Mode(name=name, value=values[0], flags=values[1], speed_min=values[2], speed_max=values[3],
                    brightness_min=values[4], brightness_max=values[5], colors_min=values[6],
                    colors_max=values[7], speed=values[8], brightness=values[9], direction=values[10],
                    color_mode=values[11], colors=colors)

    def zone(self):
        self.string()
        self.take("IIII")
        matrix = self.u16()
        self.pos += matrix
        for _ in range(self.u16()):
            self.string()
            self.take("III")


def rgb(color):
    """'#rrggbb' -> OpenRGB RGBColor (0x00BBGGRR)."""
    r, g, b = bytes.fromhex(color.lstrip("#"))
    return r | g << 8 | b << 16


def hex_color(value):
    return "#%02x%02x%02x" % (value & 0xFF, value >> 8 & 0xFF, value >> 16 & 0xFF)


class Client:
    """One connection to an OpenRGB SDK server. Not thread-safe beyond its own lock."""

    def __init__(self, host="127.0.0.1", port=6742, name="Retro 87 tools", timeout=3.0):
        self.host, self.port, self.name, self.timeout = host, port, name, timeout
        self.sock = None
        self.lock = threading.Lock()
        self.stale = True

    def connect(self):
        if self.sock is None:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self._send(0, SET_CLIENT_NAME, self.name.encode() + b"\0")
            self._send(0, REQUEST_PROTOCOL_VERSION, struct.pack("<I", PROTOCOL_VERSION))
            server = struct.unpack("<I", self._receive(REQUEST_PROTOCOL_VERSION))[0]
            if server < PROTOCOL_VERSION:
                self.close()
                raise ConnectionError(f"OpenRGB server protocol {server} is too old; version {PROTOCOL_VERSION} is needed")
            self.stale = True
        return self

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _send(self, device, packet, data=b""):
        self.sock.sendall(b"ORGB" + struct.pack("<III", device, packet, len(data)) + data)

    def _read(self, size):
        data = bytearray()
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError("OpenRGB server closed the connection")
            data.extend(chunk)
        return bytes(data)

    def _receive(self, packet):
        """Next reply with this packet id; notifications and acks in between are skipped."""
        while True:
            header = self._read(16)
            if header[:4] != b"ORGB":
                raise ConnectionError("Invalid OpenRGB packet")
            _, kind, size = struct.unpack_from("<III", header, 4)
            data = self._read(size)
            if kind == DEVICE_LIST_UPDATED:
                self.stale = True
            if kind == packet:
                return data

    def _call(self, device, packet, data=b"", reply=None):
        with self.lock:
            try:
                self.connect()
                self._send(device, packet, data)
                return self._receive(reply) if reply is not None else None
            except OSError:
                self.close()
                raise

    def devices(self):
        count = struct.unpack("<I", self._call(0, REQUEST_CONTROLLER_COUNT, reply=REQUEST_CONTROLLER_COUNT))[0]
        devices = []
        for index in range(count):
            data = self._call(index, REQUEST_CONTROLLER_DATA, struct.pack("<I", PROTOCOL_VERSION),
                              reply=REQUEST_CONTROLLER_DATA)
            devices.append(Device(index, data[4:]))
        self.stale = False
        return devices

    def update_mode(self, device, index, mode):
        body = struct.pack("<i", index) + mode.pack()
        self._call(device.index, UPDATE_MODE, struct.pack("<I", len(body) + 4) + body)
        device.active_mode = index

    def update_leds(self, device, colors):
        body = struct.pack("<H", len(colors)) + b"".join(struct.pack("<I", c) for c in colors)
        self._call(device.index, UPDATE_LEDS, struct.pack("<I", len(body) + 4) + body)
        device.colors = list(colors)

    def sync(self):
        """Read pending notifications; True if the device list may have changed."""
        with self.lock:
            if self.sock is None:
                return True
            try:
                while select.select([self.sock], [], [], 0)[0]:
                    header = self._read(16)
                    _, kind, size = struct.unpack_from("<III", header, 4)
                    self._read(size)
                    if kind == DEVICE_LIST_UPDATED:
                        self.stale = True
            except OSError:
                self.close()
                return True
            return self.stale


def find(devices, description):
    return next((d for d in devices if d.description.startswith(description)), None)


def connection_name(device):
    """'USB cable' / '2.4 GHz dongle' from the effects device description."""
    description = device.description
    return description[description.find("(") + 1:-1] if description.endswith(")") and "(" in description else ""


PRESET_MODES = {"off": "Off", "resonance": "Resonance", "starlight": "Starlight", "solid": "Static",
                "cycle": "Spectrum Cycle", "color-ripple": "Rainbow Wave", "breathing": "Breathing",
                "ripple": "Ripple"}
MODE_PRESETS = {mode: preset for preset, mode in PRESET_MODES.items()}
CUSTOM_MODE = "Custom"
DIRECT_MODE = "Direct"
HAS_SPEED = 1 << 0
UNREACHABLE = ("OpenRGB is not running. Start it with: systemctl --user start retro87-openrgb "
               "(or run openrgb --server).")


class Controller:
    """Service backend with retro87_service.Controller's interface, through OpenRGB.

    Every change goes through the OpenRGB server; the keyboard saves effect
    and per-key changes itself (the OpenRGB device has automatic save).
    """

    def __init__(self, client=None):
        self.client = client or Client()
        self.effects = None
        self.devices = []
        self.error = "Not read yet"
        self.last_preset = "solid"
        self.resume = None          # mode index to return to after Direct (live)
        self.live_brightness = 100  # software dimming of Direct colours, percent

    def _devices(self, force=False):
        if force or self.client.sync() or not self.devices:
            self.devices = self.client.devices()
        self.effects = find(self.devices, EFFECTS_DESCRIPTION)
        return self.devices

    def _effects(self, force=False):
        try:
            self._devices(force)
        except OSError as exc:
            self.effects = None
            self.error = UNREACHABLE if isinstance(exc, ConnectionRefusedError) else f"OpenRGB: {exc}"
            raise RuntimeError(self.error) from exc
        if self.effects is None:
            self.error = ("OpenRGB does not see the Retro 87. Switch the keyboard on (2.4 GHz dongle) "
                          "or connect its USB cable.")
            raise RuntimeError(self.error)
        self.error = ""
        return self.effects

    def refresh(self):
        try:
            self._effects(force=True)
        except RuntimeError:
            pass
        return self.status()

    def status(self):
        device = self.effects
        state = {"connected": device is not None and not self.error, "error": self.error,
                 "presets": list(PRESET_MODES), "backup": "", "backend": "openrgb",
                 "connection": connection_name(device) if device else ""}
        if device is None or not device.modes:
            return state
        mode = device.modes[device.active_mode]
        live = mode.name == DIRECT_MODE
        if live and self.resume is not None:
            mode = device.modes[self.resume]  # show the stored effect live mode returns to
        per_key = mode.name == CUSTOM_MODE
        if not per_key and mode.name in MODE_PRESETS:
            self.last_preset = MODE_PRESETS[mode.name]
        has_speed = bool(mode.flags & HAS_SPEED)
        state.update({
            "initialized": True, "profileActive": True, "profileName": device.name,
            "preset": self.last_preset if per_key else MODE_PRESETS.get(mode.name, mode.name),
            "perKey": per_key, "perKeyStored": device.mode(CUSTOM_MODE) is not None,
            "brightness": self.live_brightness if live else
                          round(mode.brightness * 100 / mode.brightness_max) if mode.brightness_max else None,
            "speed": 11 - mode.speed if has_speed else None,
            "color": hex_color(mode.colors[0]) if not per_key and mode.colors else None,
            "echo": hex_color(mode.colors[1]) if not per_key and len(mode.colors) > 1 else None,
            "hasSpeed": has_speed, "hasColor": not per_key and len(mode.colors) > 0,
            "hasEcho": not per_key and len(mode.colors) > 1, "tip": "",
        })
        return state

    def _apply(self, device, index, mode):
        try:
            self.client.update_mode(device, index, mode)
        except OSError as exc:
            self.error = f"OpenRGB: {exc}"
            raise RuntimeError(self.error) from exc

    def set(self, field, value):
        device = self._effects()
        index = device.active_mode
        mode = device.modes[index]
        if field == "preset":
            if value not in PRESET_MODES or device.mode(PRESET_MODES[value]) is None:
                raise ValueError(f"Unknown preset {value!r}")
            index = device.mode(PRESET_MODES[value])
            self._apply(device, index, device.modes[index])
            return self.status()
        if field == "perkey":
            if value not in ("on", "off"):
                raise ValueError("perkey takes on or off")
            name = CUSTOM_MODE if value == "on" else PRESET_MODES[self.last_preset]
            index = device.mode(name)
            if index is None:
                raise ValueError(f"The keyboard has no {name} mode in OpenRGB")
            if index != device.active_mode:
                self._apply(device, index, device.modes[index])
            return self.status()
        if mode.name == DIRECT_MODE:
            if field != "brightness":
                raise ValueError("Live colours are showing; stop live mode first.")
            number = int(value)
            if not 0 <= number <= 100:
                raise ValueError("Brightness must be 0–100")
            self.live_brightness = number  # applied to the next live frame
            return self.status()
        if mode.name == "Off":
            raise ValueError("Lighting is off; choose a preset first.")
        if field == "brightness":
            number = int(value)
            if not 0 <= number <= 100:
                raise ValueError("Brightness must be 0–100")
            mode.brightness = number * mode.brightness_max // 100
        elif field == "speed":
            number = int(value)
            if not 1 <= number <= 10:
                raise ValueError("Speed must be 1–10")
            if not mode.flags & HAS_SPEED:
                raise ValueError(f"{mode.name} has no speed")
            mode.speed = 11 - number
        elif field in ("color", "echo"):
            slot = 0 if field == "color" else 1
            if mode.name == CUSTOM_MODE:
                raise ValueError("Per-key colours are edited in the Retro 87 app or OpenRGB.")
            if len(mode.colors) <= slot:
                raise ValueError(f"{mode.name} has no {'highlight ' if slot else ''}colour")
            mode.colors[slot] = rgb(value)
        else:
            raise ValueError(f"Unknown setting {field!r}")
        self._apply(device, index, mode)
        return self.status()

    def set_leds(self, colors, brightness=None):
        """Store a per-key picture (the keyboard's Custom mode; each write is saved to flash)."""
        device = self._effects()
        index = device.mode(CUSTOM_MODE)
        if index is None:
            raise ValueError("The keyboard has no Custom mode in OpenRGB")
        values = list(device.colors)
        for key, leds in device.key_leds().items():
            if key in colors:
                for led in leds:
                    values[led] = rgb(colors[key])
        mode = device.modes[index]
        if brightness is not None:
            mode.brightness = brightness * mode.brightness_max // 100
        try:
            if values != device.colors:
                # Stored only by OpenRGB until Custom is active; then written to the keyboard.
                self.client.update_leds(device, values)
            if index != device.active_mode or brightness is not None:
                self.client.update_mode(device, index, mode)
        except OSError as exc:
            self.error = f"OpenRGB: {exc}"
            raise RuntimeError(self.error) from exc
        return self.status()


class LampSink:
    """Live-mirror target (retro87_live.LiveMirror `lamps`): runtime per-key colours
    through the keyboard's Direct mode in OpenRGB, which exists only over the USB cable."""

    IN_USE = ("Direct mode is in use by another OpenRGB client. Stop it (or select another mode "
              "in OpenRGB), then start live colours again.")

    def __init__(self, controller):
        self.controller, self.client = controller, controller.client
        self.device = None
        self.owned = False      # we switched the keyboard to Direct and have not handed it back
        self.takeover = False   # take Direct over from another client once (explicit user choice)

    def _find(self):
        self.controller._devices()
        device = self.controller.effects
        return device if device is not None and device.mode(DIRECT_MODE) is not None else None

    def available(self):
        if self.device is not None:
            return True
        try:
            return self._find() is not None
        except OSError:
            return False

    def set_leds(self, colors):
        try:
            if self.device is not None and self.device is not self.controller.effects:
                self.device = None  # the device list changed; look the keyboard up again
            if self.device is None:
                device = self._find()
                if device is None:
                    raise RuntimeError("Live colours need the keyboard's USB cable (OpenRGB shows no Direct mode).")
                direct = device.mode(DIRECT_MODE)
                if device.active_mode == direct and not (self.owned or self.takeover):
                    raise RuntimeError(self.IN_USE)
                self.takeover = False
                if device.active_mode != direct:
                    mode = device.modes[device.active_mode]
                    self.controller.resume = device.active_mode
                    self.controller.live_brightness = (round(mode.brightness * 100 / mode.brightness_max)
                                                       if mode.brightness_max else 100)
                    self.client.update_mode(device, direct, device.modes[direct])
                self.device, self.mapping, self.owned = device, device.key_leds(), True
            scale = self.controller.live_brightness / 100
            values = list(self.device.colors)
            for key, leds in self.mapping.items():
                if key in colors:
                    r, g, b = bytes.fromhex(colors[key].lstrip("#"))
                    for led in leds:
                        values[led] = round(r * scale) | round(g * scale) << 8 | round(b * scale) << 16
            self.client.update_leds(self.device, values)
        except OSError as exc:
            self.device = None
            raise RuntimeError(f"OpenRGB: {exc}") from exc

    def close(self):
        """Return to the stored effect that was showing; OpenRGB then only hands the
        lighting back to the keyboard, without saving anything."""
        device, self.device = self.device, None
        self.owned = False
        resume, self.controller.resume = self.controller.resume, None
        if device is None or device.active_mode != device.mode(DIRECT_MODE):
            return
        if resume is None:
            resume = device.mode(PRESET_MODES[self.controller.last_preset])
        try:
            self.client.update_mode(device, resume, device.modes[resume])
        except OSError:
            pass
