"""HID LampArray over direct USB for the wired Retro 87 (2dc8:2028).

The keyboard's LampArray interface has no interrupt-IN endpoint, so Linux's
usbhid leaves it unbound and no hidraw node exists. This module claims it via
usbfs and exchanges HID feature reports with control transfers. Colour updates
are runtime-only (see research/storage-wear.md): unlike the vendor custom-LED
transport, whose 0x0d prepare erases flash, they are meant for streaming.

Report layouts follow the HID Lighting and Illumination page (0x59), as used
by Windows Dynamic Lighting. No third-party dependencies.
"""
import ctypes
import errno
import fcntl
import json
import os
from pathlib import Path
import struct

VENDOR, PRODUCT = 0x2DC8, 0x2028
ATTRIBUTES, LAMP_REQUEST, LAMP_RESPONSE, MULTI_UPDATE, RANGE_UPDATE, CONTROL = 0x11, 0x12, 0x13, 0x14, 0x15, 0x16
MULTI_MAX = 8
UPDATE_COMPLETE = 1
TIMEOUT_MS = 500
TABLES = json.loads((Path(__file__).resolve().parent / "keycodes.json").read_text())
# Lamp id -> key, from the keyboard's lamp attributes (firmware bcdDevice 1.14). The
# firmware's own table is unreliable: several X positions are 10x too large, the
# right arrow reports (0, 0), backspace is bound to the backslash usage, and pause,
# four space-bar LEDs and the A/B keys have no binding. Bound lamps are checked
# against this table on open (see key_lamps).
LAMP_KEYS = (["esc"] + [f"f{i}" for i in range(1, 13)] + ["prtsc", "scrlk", "pause"]
             + ["tilde"] + [f"num{i}" for i in range(1, 10)]
             + ["num0", "minus", "equal", "backspace", "insert", "home", "pgup"]
             + ["tab"] + list("qwertyuiop") + ["leftbracket", "rightbracket", "backslash", "delete", "end", "pgdn"]
             + ["capslock"] + list("asdfghjkl") + ["semicolon", "quotation", "enter"]
             + ["lshift"] + list("zxcvbnm") + ["comma", "period", "slash", "rshift", "up"]
             + ["lctrl", "lwin", "lalt"] + ["space"] * 5 + ["ralt", "ka", "kb", "rctrl", "left", "down", "right"])
KNOWN_MISBINDINGS = {29: "backslash"}


class _Control(ctypes.Structure):
    _fields_ = [("bRequestType", ctypes.c_uint8), ("bRequest", ctypes.c_uint8), ("wValue", ctypes.c_uint16),
                ("wIndex", ctypes.c_uint16), ("wLength", ctypes.c_uint16), ("timeout", ctypes.c_uint32),
                ("data", ctypes.c_void_p)]


def _ioc(direction, number, size):
    return (direction << 30) | (size << 16) | (ord("U") << 8) | number


USBDEVFS_CONTROL = _ioc(3, 0, ctypes.sizeof(_Control))
USBDEVFS_CLAIMINTERFACE = _ioc(2, 15, 4)
USBDEVFS_RELEASEINTERFACE = _ioc(2, 16, 4)


def find_interface(sysfs=Path("/sys/bus/usb/devices")):
    """(usbfs path, interface number) of the wired keyboard's LampArray, or None."""
    for device in sysfs.glob("*"):
        try:
            if (int((device / "idVendor").read_text(), 16), int((device / "idProduct").read_text(), 16)) != (VENDOR, PRODUCT):
                continue
            bus, number = int((device / "busnum").read_text()), int((device / "devnum").read_text())
        except (OSError, ValueError):
            continue
        for interface in sorted(device.glob(device.name + ":*")):
            try:
                if (interface / "bInterfaceClass").read_text().strip() != "03" or (interface / "driver").exists():
                    continue
                endpoints = [(e / "direction").read_text().strip() for e in interface.glob("ep_*")]
                if endpoints == ["out"]:
                    return f"/dev/bus/usb/{bus:03d}/{number:03d}", int((interface / "bInterfaceNumber").read_text(), 16)
            except OSError:
                continue
    return None


def report_types(descriptor):
    """{report id: set of 'input'/'output'/'feature'} and whether the descriptor is a LampArray."""
    result, page, report, lamp_array, position = {}, 0, 0, False, 0
    while position < len(descriptor):
        prefix = descriptor[position]
        size = (0, 1, 2, 4)[prefix & 3]
        value = int.from_bytes(descriptor[position+1:position+1+size], "little")
        tag = prefix & 0xFC
        if tag == 0x04:
            page = value
        elif tag == 0x84:
            report = value
        elif tag == 0x08 and page == 0x59 and value == 0x01:
            lamp_array = True
        elif tag in (0x80, 0x90, 0xB0):
            result.setdefault(report, set()).add({0x80: "input", 0x90: "output", 0xB0: "feature"}[tag])
        position += 1 + size
    return result, lamp_array


class LampArray:
    """Open with `with LampArray() as lamps:`; leaving restores the keyboard's own lighting."""

    def __init__(self, location=None):
        self.location = location

    def __enter__(self):
        location = self.location or find_interface()
        if not location:
            raise FileNotFoundError("The Retro 87 is not connected by USB cable (LampArray needs a wired connection)")
        self.path, self.interface = location
        self.fd = os.open(self.path, os.O_RDWR)
        try:
            fcntl.ioctl(self.fd, USBDEVFS_CLAIMINTERFACE, struct.pack("I", self.interface))
            descriptor = self._control(0x81, 6, 0x2200, 1024)
            self.types, lamp_array = report_types(descriptor)
            if not lamp_array:
                raise RuntimeError("Interface is not a HID LampArray")
            data = self.get_feature(ATTRIBUTES, 23)
            count, width, height, depth, kind, interval = struct.unpack_from("<HIIIII", data, 1)
            self.count, self.size, self.kind, self.interval = count, (width, height, depth), kind, interval / 1e6
            self.lamps = [self.lamp(i) for i in range(count)]
            self.autonomous = None
        except BaseException:
            self._close()
            raise
        return self

    def __exit__(self, *args):
        try:
            if self.autonomous is False:
                self.set_autonomous(True)
        finally:
            self._close()

    def _close(self):
        try:
            fcntl.ioctl(self.fd, USBDEVFS_RELEASEINTERFACE, struct.pack("I", self.interface))
        except OSError:
            pass
        os.close(self.fd)

    def _control(self, request_type, request, value, length, data=b""):
        buffer = ctypes.create_string_buffer(bytes(data), max(length, len(data)))
        transfer = _Control(request_type, request, value, self.interface, max(length, len(data)), TIMEOUT_MS,
                            ctypes.cast(buffer, ctypes.c_void_p))
        done = fcntl.ioctl(self.fd, USBDEVFS_CONTROL, transfer)
        return buffer.raw[:done]

    def get_feature(self, report, length):
        data = self._control(0xA1, 0x01, 0x0300 | report, length)
        if not data or data[0] != report:
            raise RuntimeError(f"Unexpected LampArray report {data[:1].hex()} for {report:#x}")
        return data

    def set_report(self, report, payload):
        kind = 0x03 if "feature" in self.types.get(report, ()) else 0x02
        self._control(0x21, 0x09, (kind << 8) | report, 0, bytes([report]) + payload)

    def lamp(self, lamp_id):
        self.set_report(LAMP_REQUEST, struct.pack("<H", lamp_id))
        data = self.get_feature(LAMP_RESPONSE, 29)
        (returned, x, y, z, latency, purposes,
         red, green, blue, intensity, programmable, binding) = struct.unpack_from("<HIIIIIBBBBBB", data, 1)
        if returned != lamp_id:
            raise RuntimeError(f"Lamp attributes for {returned} returned when {lamp_id} was requested")
        return {"id": lamp_id, "position": (x, y, z), "latency": latency / 1e6, "purposes": purposes,
                "levels": (red, green, blue, intensity), "programmable": bool(programmable), "binding": binding}

    def set_autonomous(self, enabled):
        self.set_report(CONTROL, bytes([1 if enabled else 0]))
        self.autonomous = bool(enabled)

    def update(self, colors):
        """Show {lamp id: (r, g, b)} in one frame; the keyboard applies it on the last report."""
        if self.autonomous is not False:
            self.set_autonomous(False)
        items = sorted(colors.items())
        for start in range(0, len(items), MULTI_MAX):
            chunk = items[start:start+MULTI_MAX]
            flags = UPDATE_COMPLETE if start + MULTI_MAX >= len(items) else 0
            ids = [lamp for lamp, _ in chunk] + [0] * (MULTI_MAX - len(chunk))
            rgbi = [value for _, (r, g, b) in chunk for value in (r, g, b, 255)] + [0] * 4 * (MULTI_MAX - len(chunk))
            self.set_report(MULTI_UPDATE, struct.pack("<BB8H32B", len(chunk), flags, *ids, *rgbi))

    def fill(self, rgb):
        """Show one colour on every lamp with a single range update."""
        if self.autonomous is not False:
            self.set_autonomous(False)
        self.set_report(RANGE_UPDATE, struct.pack("<BHH4B", UPDATE_COMPLETE, 0, self.count - 1, *rgb, 255))

    def key_lamps(self):
        """{key name: [lamp ids]} from LAMP_KEYS, after checking the lamps' own key bindings."""
        if self.count != len(LAMP_KEYS):
            raise RuntimeError(f"Unexpected lamp count {self.count}; expected {len(LAMP_KEYS)}")
        for lamp in self.lamps:
            usage, expected = lamp["binding"], LAMP_KEYS[lamp["id"]]
            if usage and usage != TABLES["targets"].get(KNOWN_MISBINDINGS.get(lamp["id"], expected)):
                raise RuntimeError(f"Lamp {lamp['id']} is bound to usage {usage:#x}, not {expected!r}; "
                                   "the lamp table does not match this firmware")
        result = {}
        for lamp, key in enumerate(LAMP_KEYS):
            result.setdefault(key, []).append(lamp)
        return result


def hex_rgb(color):
    return tuple(bytes.fromhex(color.lstrip("#")))


class LampArraySink:
    """Live-mirror target with the Controller.set_leds(colors) interface, keeping the device open."""

    def __init__(self, factory=LampArray):
        self.factory = factory
        self.device = None

    @staticmethod
    def available():
        return find_interface() is not None

    def set_leds(self, colors):
        try:
            if self.device is None:
                device = self.factory()
                device.__enter__()
                self.device, self.mapping = device, device.key_lamps()
            frame = {lamp: hex_rgb(color) for key, color in colors.items() for lamp in self.mapping.get(key, ())}
            self.device.update(frame)
        except OSError as exc:
            self.close()
            if exc.errno in (errno.EACCES, errno.EPERM):
                raise RuntimeError("No permission for the keyboard's USB lighting interface; "
                                   "re-run install-kde.sh to add the udev rule") from exc
            raise RuntimeError(f"USB lighting stopped: {exc.strerror or exc}") from exc

    def close(self):
        device, self.device = self.device, None
        if device is not None:
            try:
                device.__exit__(None, None, None)
            except OSError:
                pass


if __name__ == "__main__":
    import sys
    with LampArray() as lamps:
        print(f"{lamps.count} lamps, kind {lamps.kind}, bounding box {lamps.size} µm, "
              f"minimum interval {lamps.interval*1000:.0f} ms, report types "
              f"{ {hex(k): sorted(v) for k, v in lamps.types.items()} }")
        if "-v" in sys.argv:
            for lamp in lamps.lamps:
                print(lamp["id"], lamp["position"], lamp["levels"], lamp["programmable"],
                      hex(lamp["binding"]), LAMP_KEYS[lamp["id"]] if lamp["id"] < len(LAMP_KEYS) else "")
        print(json.dumps({k: v for k, v in sorted(lamps.key_lamps().items())}))
