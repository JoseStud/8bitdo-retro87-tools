"""Linux HID access for the Mecha BREAK Retro 87, over its 2.4 GHz dongle (2dc8:202e)
or its USB cable (2dc8:2028); both expose the same configuration interface.

All changes are previews unless --apply is supplied. No third-party dependencies.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import select
import struct
import time
import sys
import uuid

DESCRIPTOR = bytes.fromhex("06a0ff0901a1018502150026ff00190129027508953f81028581150026ff00190129027508953f9182c0")
# HID product id -> connection, in order of preference: while the cable is plugged
# in, the dongle's configuration requests no longer reach the keyboard.
CONNECTIONS = {"00002028": "USB cable", "0000202E": "2.4 GHz dongle"}
PROFILE_SIZE = 0x5fc
PROFILE_FLAG = 0x20200902
PROFILE_ACTIVE_TIP = ("The profile is not active (byte 0x24 is not 1): the keyboard ignores stored lighting "
                      "settings and uses its onboard ones. Press the keyboard's Profile button once to activate it.")
ROOT = Path(__file__).resolve().parent
TABLES = json.loads((ROOT / "keycodes.json").read_text())
SOURCES = {item["name"]: item for item in TABLES["initial"]}
TARGETS = {name: TABLES["targets"][name] for name in SOURCES}
TARGETS = {name: value for name, value in TARGETS.items() if value != 243}
TARGETS.update({f"f{i}": TABLES["targets"][f"f{i}"] for i in range(13, 25)})
TARGETS["none"] = 243
ALIASES = {"escape": "esc", "caps": "capslock", "ctrl": "lctrl", "shift": "lshift", "alt": "lalt", "super": "lwin", "win": "lwin", "supera": "ka", "superb": "kb", "pageup": "pgup", "pagedown": "pgdn", "grave": "tilde", "apostrophe": "quotation"}
ALIASES.update({str(i): f"num{i}" for i in range(10)})
MODES = {"off": 0, "resonance": 1, "starlight": 2, "solid": 3, "cycle": 4, "color-ripple": 5, "breathing": 6, "ripple": 7}
THEMES = {"solid": (0x5d0, 5), "cycle": (0x5d5, 2), "color-ripple": (0x5d7, 3),
          "breathing": (0x5da, 6), "ripple": (0x5e0, 6),
          "resonance": (0x5e6, 9), "starlight": (0x5ef, 10)}

def packet(command, offset=0, payload=b"", read_size=0):
    if command not in (1, 2, 8, 13, 14, 15):
        raise ValueError("Unsupported command")
    size = read_size if command in (2, 15) else len(payload)
    if not 0 <= size <= 53 or not 0 <= offset < PROFILE_SIZE:
        raise ValueError("Invalid packet range")
    if command in (2, 15, 8, 13) and payload:
        raise ValueError("Unexpected payload")
    return (bytes([0x81, 4, command, 0, size, sum(payload) & 255]) + struct.pack("<I", offset) + payload).ljust(64, b"\0")

def normalize(name):
    name = name.lower()
    return ALIASES.get(name, name)

def valid_profile(profile):
    return struct.unpack_from("<I", profile)[0] == PROFILE_FLAG

def profile_active(profile):
    """Vendor XboxJPAdvance.Readflag: native ReadXboxJPflag reads byte 0x24 and tests == 1."""
    return profile[0x24] == 1

def activation_plan(mode):
    """XboxLedView.*_ModeDown for PID_XBOXJP(USB): clear the custom-LED flag, then select the preset.

    The vendor writes 0x5f9 only when it is nonzero; callers drop unchanged ranges. It never
    touches the Dynamic Lighting engine byte 0x5fa here, nor any theme parameters.
    """
    return [(0x5f9, b"\0"), (0x5ca, bytes([MODES[mode]]))]

def record(source, target, mapping_type):
    return struct.pack("<B3xII", source & 255, target, mapping_type)

def mapping_plan(profile, source, target):
    source, target = normalize(source), normalize(target)
    if source not in SOURCES or target not in TARGETS:
        raise ValueError("Unknown key; run list-keys for supported names")
    # The 87-key board has no keypad; its records remain in the shared format.
    item = SOURCES[source]
    if 91 <= item["slot"] <= 107:
        raise ValueError("The Retro 87 has no physical numeric keypad")
    if not valid_profile(profile):
        raise ValueError("No initialized profile. Preview 'profile-create NAME' first; apply it before mapping.")
    kind = 0 if source == target or (item["code"] == 243 and target == "none") else 1
    return [(0x28 + item["slot"]*12, record(item["code"], TARGETS[target], kind))]

def profile_plan(profile, name):
    """Write the vendor's complete new-profile image; the header is published last.

    Lighting settings only take effect while the profile is active, and the
    keyboard's Profile button can only activate an initialized profile. The
    current preset is kept when valid.
    """
    if valid_profile(profile):
        raise ValueError("A profile already exists; profile-create will not replace it")
    mode = next((k for k, v in MODES.items() if v == profile[0x5ca]), "resonance")
    image = default_profile(name, mode)
    writes = [(i, image[i:i+53]) for i in range(0x28, PROFILE_SIZE, 53)]
    writes.append((0, image[:0x28]))
    return writes

def default_profile(name, mode="resonance"):
    """Complete profile image the vendor app writes when creating an XboxJP profile.

    RenameResult (PID_XBOXJP): clearConfig zeroes the device struct, temp_new fills
    defaults, copyFile copies them, then writeAdvance sends the whole struct.
    Theme speeds are the raw stored value 3. The vendor also writes a default
    custom-LED region (writeXboxJPLed); that transport is not implemented here.
    """
    if mode not in MODES:
        raise ValueError("Unknown RGB preset")
    encoded = name.encode("utf-16-be")
    if not name or "\0" in name or len(encoded) > 32:
        raise ValueError("Profile name must occupy 1–16 UTF-16 code units, without NUL")
    image = bytearray(PROFILE_SIZE)
    image[0:36] = struct.pack("<I", PROFILE_FLAG) + encoded.ljust(32, b"\0")
    # 0x24 enable, fn lock and sleep fields stay 0 (not copied by copyFile).
    for item in SOURCES.values():
        start = 0x28 + item["slot"]*12
        image[start:start+12] = record(item["code"], item["code"], 0)
    image[0x5c9] = 2
    image[0x5ca] = MODES[mode]
    struct.pack_into("<I", image, 0x5cc, 300)
    orange, black = bytes.fromhex("ffa500"), bytes(3)
    for offset, data in [(0x5d0, b"\xff\x01" + orange), (0x5d5, b"\xff\x03"), (0x5d7, b"\xff\x03\x00"),
                         (0x5da, b"\xff\x03\x01" + orange), (0x5e0, b"\xff\x03\x01" + orange),
                         (0x5e6, b"\xff\x03\x01" + black + orange),
                         (0x5ef, b"\xff\x03\x05\x01" + black + orange)]:
        image[offset:offset+len(data)] = data
    return bytes(image)

LED_SIZE = 0x11b
# The vendor sleeps 100 ms before each 0x0e chunk. Hardware tests (2026-09-27)
# showed every chunk acknowledged in ~7 ms and correct readback with no delay;
# 20 ms keeps a margin. See research/README.md, "Per-key write timing".
LED_CHUNK_DELAY = 0.02
# XboxLedView.initMappings (PID_XBOXJP): 87 on-screen buttons from ColorPoint.getXboxJP,
# bottom row first, left to right. Button i drives LED i (i < 3) or LED i + 4;
# XboxLedView.writecolor gives the space bar LEDs 3-7.
LED_KEYS = (
    ["lctrl", "lwin", "lalt", "space", "ralt", "ka", "kb", "rctrl", "left", "down", "right",
     "lshift", "z", "x", "c", "v", "b", "n", "m", "comma", "period", "slash", "rshift", "up",
     "capslock", "a", "s", "d", "f", "g", "h", "j", "k", "l", "semicolon", "quotation", "enter",
     "tab", "q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "leftbracket", "rightbracket", "backslash",
     "delete", "end", "pgdn",
     "tilde", "num1", "num2", "num3", "num4", "num5", "num6", "num7", "num8", "num9", "num0",
     "minus", "equal", "backspace", "insert", "home", "pgup",
     "esc"] + [f"f{i}" for i in range(1, 13)] + ["prtsc", "scrlk", "pause"])
# Vendor type 0 ("close") stops the animation and holds the current frame on
# hardware; it does not darken the keys. "off" is static at 0% brightness.
CUSTOM_TYPES = {"static": 1, "breathing": 2, "starlight": 3, "freeze": 0}
CUSTOM_EFFECTS = tuple(CUSTOM_TYPES) + ("off",)

def led_indices(key):
    """LED indices for a key name (aliases allowed)."""
    name = normalize(key)
    if name not in LED_KEYS:
        raise ValueError(f"No LED for key {key!r}")
    button = LED_KEYS.index(name)
    if button < 3:
        return [button]
    return list(range(3, 8)) if button == 3 else [button + 4]

def led_block(colors, *, default="#000000", effect="static", brightness=100, speed=5, count=25):
    """BasicJPAdvanceUIData.getTotalColor: LED_CUSTOM_THEME, 283 bytes.

    brightness, color_flag=1, type, 11-speed, number, 4 reserved, 91 x RGB, is_done=1.
    """
    if effect not in CUSTOM_EFFECTS:
        raise ValueError("Unknown custom lighting effect")
    if effect == "off":
        effect, brightness = "static", 0
    if type(brightness) is not int or not 0 <= brightness <= 100 or type(speed) is not int or not 1 <= speed <= 10:
        raise ValueError("Brightness must be 0–100; speed must be 1–10")
    if type(count) is not int or not 5 <= count <= 100:
        raise ValueError("Starlight count must be 5–100")
    rgb = bytearray(color_bytes(default) * 91)
    for key, color in colors.items():
        value = color_bytes(color)
        for index in led_indices(key):
            rgb[index*3:index*3+3] = value
    header = bytes([brightness * 255 // 100, 1, CUSTOM_TYPES[effect], 11 - speed, count, 0, 0, 0, 0])
    block = header + bytes(rgb) + b"\x01"
    assert len(block) == LED_SIZE
    return block

def decode_led(block):
    """Inverse of led_block for display; None fields mean unknown/blank storage."""
    effect = next((k for k, v in CUSTOM_TYPES.items() if v == block[2]), None)
    valid = block[1] == 1 and effect is not None
    colors = {}
    for key in LED_KEYS:
        index = led_indices(key)[0]
        colors[key] = "#" + block[9+index*3:12+index*3].hex() if valid else None
    return {"valid": valid, "effect": effect if valid else None,
            "brightness": round(block[0] * 100 / 255) if valid else None,
            "speed": 11 - block[3] if valid and 1 <= block[3] <= 10 else None,
            "count": block[4] if valid and 5 <= block[4] <= 100 else None, "colors": colors}

def custom_led_plan(enable=True):
    """Custom_MouseLeftButtonDown: led_custom_enable (0x5f9) = 1 via writeColorFlag."""
    return [(0x5f9, b"\x01" if enable else b"\0")]

def color_bytes(color):
    value = color.removeprefix("#")
    if len(value) != 6:
        raise ValueError("Color must be a six-digit RGB hex value")
    try:
        rgb = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("Color must be a six-digit RGB hex value") from exc
    if len(rgb) != 3:
        raise ValueError("Color must be a six-digit RGB hex value")
    return rgb

def rgb_plan(mode, color, brightness, speed, *, echo_color="#ffffff", direction=0, count=25):
    """Vendor preset codecs, statically recovered; no transport side effects."""
    if mode not in MODES:
        raise ValueError("Unknown RGB preset")
    if type(brightness) is not int or not 0 <= brightness <= 100 or type(speed) is not int or not 1 <= speed <= 10:
        raise ValueError("Brightness must be 0–100; speed must be 1–10")
    if mode == "color-ripple" and (type(direction) is not int or not 0 <= direction <= 5):
        raise ValueError("Direction must be 0–5")
    if mode == "starlight" and (type(count) is not int or not 5 <= count <= 100):
        raise ValueError("Starlight count must be 5–100")
    rgb = color_bytes(color) if mode in ("solid", "breathing", "ripple", "resonance", "starlight") else b""
    echo = color_bytes(echo_color) if mode in ("resonance", "starlight") else b""
    # XboxLedView.up uses integer multiplication/division, not rounding.
    level = brightness * 255 // 100
    writes = []
    if mode == "solid":
        writes.append((0x5d0, bytes([level, 1]) + rgb))
    elif mode in ("breathing", "ripple"):
        writes.append((THEMES[mode][0], bytes([level, 11-speed, 1]) + rgb))
    elif mode == "cycle":
        writes.append((0x5d5, bytes([level, 11-speed])))
    elif mode == "color-ripple":
        writes.append((0x5d7, bytes([level, 11-speed, direction])))
    elif mode == "resonance":
        writes.append((0x5e6, bytes([level, 11-speed, 1]) + rgb + echo))
    elif mode == "starlight":
        writes.append((0x5ef, bytes([level, 11-speed, count, 1]) + rgb + echo))
    writes.extend(activation_plan(mode))
    return writes

# Byte index of each editable field inside a THEMES record; the colour flag sits just before "color".
THEME_FIELDS = {"solid": {"color": 2}, "cycle": {"speed": 1}, "color-ripple": {"speed": 1},
                "breathing": {"speed": 1, "color": 3}, "ripple": {"speed": 1, "color": 3},
                "resonance": {"speed": 1, "color": 3, "echo": 6},
                "starlight": {"speed": 1, "color": 4, "echo": 7}}

def theme_plan(profile, mode, *, brightness=None, speed=None, color=None, echo=None):
    """Edit one preset's stored parameters, keeping the rest of its record.

    Like writeXboxJPColor, the whole theme record is written. An unset (all-ff)
    record starts from the vendor defaults. Does not select the preset.
    """
    if mode not in THEME_FIELDS:
        raise ValueError(f"{mode} has no adjustable parameters")
    start, size = THEMES[mode]
    record = bytearray(profile[start:start+size])
    if record == b"\xff" * size:
        record[:] = default_profile("x")[start:start+size]
    fields = THEME_FIELDS[mode]
    if brightness is not None:
        if type(brightness) is not int or not 0 <= brightness <= 100:
            raise ValueError("Brightness must be 0–100")
        record[0] = brightness * 255 // 100
    if speed is not None:
        if "speed" not in fields:
            raise ValueError(f"{mode} has no speed")
        if type(speed) is not int or not 1 <= speed <= 10:
            raise ValueError("Speed must be 1–10")
        record[1] = 11 - speed
    for name, value in (("color", color), ("echo", echo)):
        if value is not None:
            if name not in fields:
                raise ValueError(f"{mode} has no {'highlight ' if name == 'echo' else ''}colour")
            index = fields[name]
            record[index:index+3] = color_bytes(value)
            record[fields["color"]-1] = 1
    return [(start, bytes(record))]

def load_snapshot(path):
    # Bound input size before parsing, including files that grow during the read.
    with path.open("rb") as handle:
        raw = handle.read(65537)
    if len(raw) > 65536:
        raise ValueError("Snapshot exceeds the 64 KiB limit")
    try:
        snapshot = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Snapshot is not valid JSON") from exc
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be a JSON object")
    if snapshot.get("device") != "2dc8:202e":
        raise ValueError("Snapshot is for a different device")
    try:
        profile = bytes.fromhex(snapshot["profile_hex"])
        led = bytes.fromhex(snapshot["led_hex"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Snapshot needs profile_hex and led_hex hexadecimal strings") from exc
    if len(profile) != PROFILE_SIZE or len(led) != 0x11b:
        raise ValueError("Snapshot has incorrect configuration sizes")
    return profile, led

def save_snapshot(path, profile, led):
    snapshot = {"device": "2dc8:202e", "model": "Mecha BREAK: Panther", "captured_at": datetime.now(timezone.utc).isoformat(), "profile_hex": profile.hex(), "led_hex": led.hex()}
    with path.open("x") as handle:
        json.dump(snapshot, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    # Ensure a pre-write backup survives a crash after the device is changed.
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)

def show_status(profile):
    initialized = valid_profile(profile)
    name = profile[4:36].decode("utf-16-be", errors="replace").rstrip("\0") if initialized else "(not initialized)"
    mode = next((k for k, v in MODES.items() if v == profile[0x5ca]), f"unknown ({profile[0x5ca]})")
    print("Profile:", name)
    print("Profile enable byte:", profile[0x24], "(active)" if profile_active(profile) else "(inactive)")
    print("RGB mode:", mode)
    print("Custom lighting byte:", profile[0x5f9], "Dynamic Lighting byte:", profile[0x5fa])
    if initialized:
        for item in SOURCES.values():
            offset = 0x28+item["slot"]*12
            _, target, kind = struct.unpack_from("<B3xII", profile, offset)
            if kind:
                label = next((k for k, v in TARGETS.items() if v == target), hex(target))
                print(f"  {item['name']} -> {label} (type {kind})")

def find_config_node(sysfs=Path("/sys/class/hidraw")):
    """(/dev/hidrawN, connection name) of the configuration interface, preferring the cable."""
    nodes = {product: [] for product in CONNECTIONS}
    for node in sorted(sysfs.glob("hidraw*")):
        info = (node / "device/uevent").read_text()
        for product in CONNECTIONS:
            if f"HID_ID=0003:00002DC8:{product}" in info and (node / "device/report_descriptor").read_bytes() == DESCRIPTOR:
                nodes[product].append("/dev/" + node.name)
    product = next((product for product, found in nodes.items() if found), None)
    if product is None or len(nodes[product]) != 1:
        raise RuntimeError("Expected one Retro 87 configuration interface (USB cable or 2.4 GHz dongle); "
                           f"found {sum(nodes.values(), [])}")
    return nodes[product][0], CONNECTIONS[product]


class Keyboard:
    def __init__(self, writable=False):
        self.writable = writable

    def __enter__(self):
        self.path, self.connection = find_config_node()
        self.fd = os.open(self.path, os.O_RDWR | os.O_NONBLOCK)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(self.fd)
            raise
        return self

    def __exit__(self, *args):
        os.close(self.fd)

    def read(self, offset, size, command=2):
        if command not in (2, 15):
            raise ValueError("Only profile and LED reads are supported")
        limit = PROFILE_SIZE if command == 2 else 0x11b
        if not 0 <= offset < limit or not 1 <= size <= 53 or offset+size > limit:
            raise ValueError("Invalid read range")
        request = packet(command, offset, read_size=size)
        if os.write(self.fd, request) != 64:
            raise RuntimeError("Short HID request")
        deadline = time.monotonic() + 2
        while (remaining := deadline - time.monotonic()) > 0:
            if not select.select([self.fd], [], [], remaining)[0]:
                break
            response = os.read(self.fd, 64)
            if len(response) < 10 or response[:4] != bytes([2, 4, 3, command]):
                continue
            returned_offset, = struct.unpack_from("<I", response, 6)
            length = response[4]
            if returned_offset != offset:
                continue
            if not 0 < length <= size or len(response) < 10+length:
                raise RuntimeError("Invalid response length")
            return response[10:10+length]
        raise TimeoutError(f"No response for command {command:#x}, offset {offset:#x}")

    def write_range(self, offset, data):
        if not self.writable:
            raise PermissionError("Writes require --apply")
        if not data or len(data) > 53 or offset < 0 or offset+len(data) > PROFILE_SIZE:
            raise ValueError("Invalid write range")
        if os.write(self.fd, packet(1, offset, data)) != 64:
            raise RuntimeError("Short HID write")
        deadline = time.monotonic()+2
        while (remaining := deadline-time.monotonic()) > 0:
            if not select.select([self.fd], [], [], remaining)[0]:
                break
            response = os.read(self.fd, 64)
            if len(response) < 10 or response[:4] != b"\x02\x04\x03\x01":
                continue
            returned_offset, = struct.unpack_from("<I", response, 6)
            if returned_offset != offset:
                continue
            if response[4] != len(data):
                raise RuntimeError("Write acknowledgment length mismatch; stopped")
            return
        raise TimeoutError(f"Write acknowledgment missing at {offset:#x}; stopped without retrying")

    def apply(self, writes):
        if not self.writable:
            raise PermissionError("Writes require --apply")
        if os.write(self.fd, packet(8)) != 64:
            raise RuntimeError("Short configuration-session request")
        for offset, data in writes:
            # Vendor wrappers sleep 10 ms after reportID(0) before every native write call.
            time.sleep(0.01)
            self.write_range(offset, data)
            actual = self.read(offset, len(data))
            if actual != data:
                raise RuntimeError(f"Readback mismatch at {offset:#x}; stopped. Use the saved backup to inspect/recover.")

    def _await(self, command, timeout=2):
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            if not select.select([self.fd], [], [], remaining)[0]:
                break
            response = os.read(self.fd, 64)
            if len(response) >= 10 and response[:4] == bytes([2, 4, 3, command]):
                return response
        raise TimeoutError(f"No acknowledgment for command {command:#x}; stopped without retrying")

    def write_led(self, block):
        """Native writeXboxJPLed: command 0x0d, then 0x0e chunks (LED_CHUNK_DELAY apart); verified by 0x0f readback."""
        if not self.writable:
            raise PermissionError("Writes require --apply")
        if len(block) != LED_SIZE:
            raise ValueError("Custom LED block must be 283 bytes")
        if os.write(self.fd, packet(8)) != 64:
            raise RuntimeError("Short configuration-session request")
        time.sleep(0.01)
        if os.write(self.fd, packet(13)) != 64:
            raise RuntimeError("Short LED preparation request")
        self._await(13)
        offset = 0
        while offset < LED_SIZE:
            time.sleep(LED_CHUNK_DELAY)
            chunk = block[offset:offset+53]
            if os.write(self.fd, packet(14, offset, chunk)) != 64:
                raise RuntimeError("Short LED write")
            accepted = self._await(14)[4]
            if not 0 < accepted <= len(chunk):
                raise RuntimeError(f"LED write acknowledgment length {accepted} at {offset:#x}; stopped")
            offset += accepted
        if self.read_all(15) != block:
            raise RuntimeError("Custom LED readback mismatch; stopped. Use the saved backup to inspect/recover.")

    def read_all(self, command=2):
        size = PROFILE_SIZE if command == 2 else 0x11b
        result = bytearray()
        while len(result) < size:
            result.extend(self.read(len(result), min(53, size-len(result)), command))
        return bytes(result)
