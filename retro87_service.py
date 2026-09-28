"""Session D-Bus service for KDE Plasma: backend for the tray widget and keyboard-backlight bridge.

The service owns no long-lived device handle: each call opens the dongle, reads
the current configuration, writes only the changed ranges and verifies them by
readback. One backup per service run is saved before its first write.

D-Bus (session bus), all string-typed so QML can call it without type wrappers:
  io.github.JoseStud.Retro87 /io/github/JoseStud/Retro87
    Status() -> s          cached state as JSON
    Refresh() -> s         re-read the keyboard, return state as JSON
    Set(s field, s value) -> s   state as JSON plus "ok" and "message"
        preset <name> | brightness 0-100 | speed 1-10 | color #RRGGBB |
        echo #RRGGBB | perkey on/off | wallpaper off/color/keys
    OpenApp()              start the full Retro 87 app

Backlight bridge: when /dev/uleds is usable (see install-kde.sh), the service
creates the LED "retro87::kbd_backlight". UPower exposes it as a keyboard
backlight, so Plasma's Brightness applet and keyboard-brightness keys drive the
current lighting brightness.

Wallpaper sync: follows waywallen's current wallpaper (retro87_wallpaper.py),
either putting its accent colour into the current effect or showing it as
per-key colours. It writes at most once per wallpaper change.
"""
import argparse
from datetime import datetime, timezone
import errno
import json
import os
import re
from pathlib import Path
import struct
import subprocess
import sys
import time
import uuid

import retro87_core as protocol
import retro87_wallpaper as wallpaper
from retro87_model import data_dir, decode, patch_bytes

BUS_NAME = "io.github.JoseStud.Retro87"
OBJECT_PATH = "/io/github/JoseStud/Retro87"
LED_NAME = "retro87::kbd_backlight"
LED_MAX = 100


class Controller:
    """Device logic without Qt, so it can be tested with SimulatedKeyboard."""

    def __init__(self, device_factory=protocol.Keyboard, backup_dir=None):
        self.device_factory = device_factory
        self.backup_dir = Path(backup_dir) if backup_dir else data_dir() / "backups"
        self.profile = self.led = None
        self.error = "Not read yet"
        self.backup = None

    def _read(self, device):
        self.profile, self.led = device.read_all(), device.read_all(15)

    def refresh(self):
        try:
            with self.device_factory(writable=False) as device:
                self._read(device)
            self.error = ""
        except BlockingIOError:
            self.error = "The keyboard is in use by another Retro 87 tool; close it and try again."
        except (OSError, RuntimeError) as exc:
            self.profile = self.led = None
            self.error = str(exc)
        return self.status()

    def status(self):
        state = {"connected": self.profile is not None and not self.error, "error": self.error,
                 "presets": list(protocol.MODES), "backup": str(self.backup or "")}
        if self.profile is None:
            return state
        info = decode(self.profile)
        light = info["lighting"]
        led = protocol.decode_led(self.led)
        per_key = self.profile[0x5f9] == 1
        fields = protocol.THEME_FIELDS.get(light["mode"], {})
        state.update({
            "initialized": info["initialized"], "profileActive": info["profileActive"],
            "profileName": info["profileName"], "preset": light["mode"],
            "perKey": per_key, "perKeyStored": led["valid"],
            "brightness": led["brightness"] if per_key else light["brightness"],
            "speed": led["speed"] if per_key else light["speed"],
            "color": None if per_key else light["color"],
            "echo": None if per_key else light["echoColor"],
            "hasSpeed": per_key or "speed" in fields,
            "hasColor": not per_key and "color" in fields,
            "hasEcho": not per_key and "echo" in fields,
            "tip": "" if info["profileActive"] else protocol.PROFILE_ACTIVE_TIP,
        })
        return state

    @staticmethod
    def plan(profile, led, field, value):
        """Return (new LED block, profile writes) for one tray/backlight change."""
        if not protocol.valid_profile(profile):
            raise ValueError("The keyboard has no profile yet. Create one in the Retro 87 app first.")
        per_key = profile[0x5f9] == 1
        mode = next((k for k, v in protocol.MODES.items() if v == profile[0x5ca]), None)
        if field == "preset":
            if value not in protocol.MODES:
                raise ValueError(f"Unknown preset {value!r}")
            return led, protocol.activation_plan(value)
        if field == "perkey":
            if value not in ("on", "off"):
                raise ValueError("perkey takes on or off")
            if value == "on" and not protocol.decode_led(led)["valid"]:
                raise ValueError("No per-key layout is stored yet. Create one in the Retro 87 app.")
            return led, protocol.custom_led_plan(value == "on")
        if field in ("brightness", "speed"):
            number = int(value)
            if per_key:
                block = bytearray(led)
                if field == "brightness":
                    if not 0 <= number <= 100:
                        raise ValueError("Brightness must be 0–100")
                    block[0] = number * 255 // 100
                else:
                    if not 1 <= number <= 10:
                        raise ValueError("Speed must be 1–10")
                    block[3] = 11 - number
                return bytes(block), []
            if mode not in protocol.THEME_FIELDS:
                raise ValueError("Lighting is off; choose a preset first.")
            return led, protocol.theme_plan(profile, mode, **{field: number})
        if field in ("color", "echo"):
            if per_key:
                raise ValueError("Per-key colours are edited in the Retro 87 app.")
            if mode not in protocol.THEME_FIELDS:
                raise ValueError("Lighting is off; choose a preset first.")
            return led, protocol.theme_plan(profile, mode, **{field: value})
        raise ValueError(f"Unknown setting {field!r}")

    def set(self, field, value):
        return self.transaction(lambda profile, led: self.plan(profile, led, field, value))

    def set_leds(self, colors, brightness=None):
        """Show a per-key picture: static effect, keeping the current per-key brightness."""
        def planner(profile, led):
            if not protocol.valid_profile(profile):
                raise ValueError("The keyboard has no profile yet. Create one in the Retro 87 app first.")
            stored = protocol.decode_led(led)
            level = brightness if brightness is not None else stored["brightness"] if stored["valid"] else 100
            return protocol.led_block(colors, effect="static", brightness=level), protocol.custom_led_plan(True)
        return self.transaction(planner)

    def transaction(self, planner):
        """Read, plan with planner(profile, led) -> (LED block, profile writes), write and verify."""
        try:
            device = self.device_factory(writable=True)
            with device:
                self._read(device)
                self.error = ""
                block, writes = planner(self.profile, self.led)
                writes = [(o, d) for o, d in writes if self.profile[o:o+len(d)] != d]
                if block == self.led and not writes:
                    return self.status()
                if self.backup is None:
                    self.backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                    path = self.backup_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                                              + "-" + uuid.uuid4().hex + ".json")
                    protocol.save_snapshot(path, self.profile, self.led)
                    self.backup = path
                try:
                    if block != self.led:
                        device.write_led(block)
                        self.led = block
                    if writes:
                        device.apply(writes)
                        self.profile = patch_bytes(self.profile, writes)
                except Exception as exc:
                    self.profile = self.led = None
                    self.error = f"Write stopped; the keyboard may be partly changed. Backup: {self.backup}. {exc}"
                    raise RuntimeError(self.error) from exc
        except BlockingIOError as exc:
            raise RuntimeError("The keyboard is in use by another Retro 87 tool; close it and try again.") from exc
        return self.status()


def config_dir():
    value = os.environ.get("XDG_CONFIG_HOME", "")
    root = Path(value) if value and Path(value).is_absolute() else Path.home() / ".config"
    return root / "retro87-tools"


def open_uleds(name=LED_NAME, maximum=LED_MAX):
    """Create a userspace LED class device; it exists while the returned fd stays open."""
    fd = os.open("/dev/uleds", os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        os.write(fd, struct.pack("64si", name.encode(), maximum))
    except BaseException:
        os.close(fd)
        raise
    return fd


def main():
    parser = argparse.ArgumentParser(description="Retro 87 session service for KDE Plasma")
    parser.add_argument("--no-backlight", action="store_true", help="Do not create the keyboard-backlight LED")
    args = parser.parse_args()

    from PySide6.QtCore import ClassInfo, QCoreApplication, QObject, QSocketNotifier, QTimer, Slot
    from PySide6.QtDBus import QDBusConnection, QDBusInterface

    def log(*items):
        print(*items, file=sys.stderr, flush=True)

    class Backlight(QObject):
        """Bridges UPower/PowerDevil brightness requests to the keyboard's current lighting."""

        def __init__(self, controller, on_change):
            super().__init__()
            self.controller, self.on_change = controller, on_change
            self.fd = open_uleds()
            self.created = time.monotonic()
            self.known = None
            self.pending = None
            self.notifier = QSocketNotifier(self.fd, QSocketNotifier.Type.Read, self)
            self.notifier.activated.connect(self._readable)
            self.timer = QTimer(self, singleShot=True, interval=300)
            self.timer.timeout.connect(self._apply)
            self.sysfs = Path("/sys/class/leds") / LED_NAME / "brightness"

        def _readable(self, *args):
            try:
                value, = struct.unpack("i", os.read(self.fd, 4))
            except BlockingIOError:
                return
            # The LED core reports 0 on registration, and our own sysfs sync echoes back.
            if time.monotonic() - self.created < 1 or value == self.known:
                return
            self.pending = value
            self.timer.start()

        def _apply(self):
            value, self.pending = self.pending, None
            try:
                self.controller.set("brightness", str(round(value * 100 / LED_MAX)))
                log(f"Backlight: brightness {value}")
            except (ValueError, RuntimeError, OSError) as exc:
                log("Backlight:", exc)
            self.on_change()

        def _upower(self):
            """The UPower object to set, or None until UPower has seen our LED.

            PowerDevil reads UPower's legacy KbdBacklight object, which keeps its own
            cached value. When it is not bound to another keyboard (empty NativePath),
            setting it updates that cache, our device object and the LED together.
            """
            system = QDBusConnection.systemBus()
            root = "/org/freedesktop/UPower/KbdBacklight"
            def light(path):
                return QDBusInterface("org.freedesktop.UPower", path, "org.freedesktop.UPower.KbdBacklight", system)
            # Introspection XML instead of EnumerateKbdBacklights: PySide6 cannot unpack its "ao" reply.
            xml = QDBusInterface("org.freedesktop.UPower", root, "org.freedesktop.DBus.Introspectable",
                                 system).call("Introspect").arguments()
            for node in re.findall(r'<node name="([^"]+)"', xml[0] if xml else ""):
                ours = light(f"{root}/{node}")
                if str(ours.property("NativePath")).endswith("/" + LED_NAME):
                    legacy = light(root)
                    return legacy if str(legacy.property("NativePath")) in ("", ours.property("NativePath")) else ours
            return None

        def sync(self, percent):
            """Show the keyboard's real brightness in the LED and in UPower/PowerDevil.

            UPower caches the value it read when the LED appeared, so we set it through
            UPower (see _upower), which also notifies PowerDevil. Its write reaches us as a uleds event
            equal to self.known and is ignored. Falls back to sysfs before UPower knows the LED.
            """
            if percent is None:
                return
            value = round(percent * LED_MAX / 100)
            if value == self.known:
                return
            self.known = value
            light = self._upower()
            if light is not None:
                reply = light.call("SetBrightness", value)
                if not reply.errorName():
                    return
                log("Backlight: UPower:", reply.errorMessage())
            try:
                self.sysfs.write_text(str(value))
            except OSError as exc:
                log("Backlight: cannot show the brightness:", exc.strerror)

    class WallpaperSync(QObject):
        """Follows waywallen's current wallpaper (see retro87_wallpaper.py)."""

        def __init__(self, controller, on_change):
            super().__init__()
            self.controller, self.on_change = controller, on_change
            self.settings = config_dir() / "service.json"
            try:
                self.mode = json.loads(self.settings.read_text()).get("wallpaperSync", "off")
            except (OSError, ValueError):
                self.mode = "off"
            self.current = self.applied = None
            self.name = ""
            self.last_write = 0.0
            self.poll = QTimer(self, interval=2000)
            self.poll.timeout.connect(self._check)
            self.poll.start()
            # Rate limit: at most one keyboard write per MIN_INTERVAL seconds.
            self.later = QTimer(self, singleShot=True)
            self.later.timeout.connect(self.apply)

        MIN_INTERVAL = 10

        def set_mode(self, mode):
            if mode not in wallpaper.SYNC_MODES:
                raise ValueError(f"Wallpaper sync takes {', '.join(wallpaper.SYNC_MODES)}")
            self.mode = mode
            self.settings.parent.mkdir(parents=True, exist_ok=True)
            self.settings.write_text(json.dumps({"wallpaperSync": mode}))
            self.applied = None
            self.last_write = 0.0
            self.apply()

        def _check(self):
            daemon = QDBusInterface(wallpaper.WAYWALLEN_SERVICE, wallpaper.WAYWALLEN_PATH,
                                    wallpaper.WAYWALLEN_IFACE, QDBusConnection.sessionBus())
            item = daemon.property("CurrentWallpaperId") if daemon.isValid() else None
            if item != self.current:
                self.current = item
                info = wallpaper.wallpaper_info(item)
                self.name = info[0] if info else ""
                self.apply()

        def apply(self):
            if self.mode == "off" or self.current is None or (self.current, self.mode) == self.applied:
                return
            wait = self.MIN_INTERVAL - (time.monotonic() - self.last_write)
            if wait > 0:
                self.later.start(int(wait * 1000))
                return
            info = wallpaper.wallpaper_info(self.current)
            result = wallpaper.analyse(info[1]) if info else None
            if not result:
                log(f"Wallpaper: no preview for waywallen item {self.current}")
                self.applied = (self.current, self.mode)
                return
            accent, keys = result
            self.last_write = time.monotonic()
            try:
                if self.mode == "keys":
                    self.controller.set_leds(keys)
                else:
                    state = self.controller.status()
                    if state.get("perKey"):
                        self.controller.set("perkey", "off")
                        state = self.controller.status()
                    if not state.get("hasColor"):
                        self.controller.set("preset", "solid")
                        state = self.controller.status()
                    if state.get("hasEcho"):
                        dim = "#%02x%02x%02x" % tuple(int(accent[i:i+2], 16) // 5 for i in (1, 3, 5))
                        self.controller.set("color", dim)
                        self.controller.set("echo", accent)
                    else:
                        self.controller.set("color", accent)
                self.applied = (self.current, self.mode)
                log(f"Wallpaper: {self.mode} from {self.name!r} (accent {accent})")
            except (ValueError, RuntimeError, OSError) as exc:
                self.applied = (self.current, self.mode)
                log("Wallpaper:", exc)
            self.on_change()

    @ClassInfo({"D-Bus Interface": BUS_NAME})
    class Service(QObject):
        # Errors are returned in the JSON reply: QDBusContext.sendErrorReply crashes under PySide6.
        def __init__(self, controller):
            super().__init__()
            self.controller = controller
            self.backlight = None
            self.wallpaper = None

        def changed(self):
            if self.backlight:
                self.backlight.sync(self.controller.status().get("brightness"))

        def _state(self, state, message=""):
            sync = self.wallpaper
            return json.dumps(dict(state, ok=not message, message=message,
                                   wallpaperSync=sync.mode if sync else "off",
                                   wallpaperName=sync.name if sync else ""))

        def _reply(self, state, message=""):
            self.changed()
            return self._state(state, message)

        @Slot(result=str)
        def Status(self):
            return self._state(self.controller.status())

        @Slot(result=str)
        def Refresh(self):
            return self._reply(self.controller.refresh())

        @Slot()
        def OpenApp(self):
            subprocess.Popen([str(protocol.ROOT / "run-gui")], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        @Slot(str, str, result=str)
        def Set(self, field, value):
            try:
                if field == "wallpaper":
                    self.wallpaper.set_mode(value)
                    return self._reply(self.controller.status())
                return self._reply(self.controller.set(field, value))
            except (ValueError, RuntimeError, OSError) as exc:
                return self._reply(self.controller.status(), str(exc))

    app = QCoreApplication(sys.argv)
    controller = Controller()
    service = Service(controller)
    if not args.no_backlight:
        try:
            service.backlight = Backlight(controller, service.changed)
            log(f"Backlight: created {LED_NAME}")
        except OSError as exc:
            hint = " (run install-kde.sh for the one-time setup)" if exc.errno in (errno.ENOENT, errno.EACCES) else ""
            log(f"Backlight: disabled, /dev/uleds unavailable: {exc.strerror}{hint}")
    controller.refresh()
    log("Keyboard:", controller.error or "connected")
    service.wallpaper = WallpaperSync(controller, service.changed)

    bus = QDBusConnection.sessionBus()
    if not bus.registerObject(OBJECT_PATH, service, QDBusConnection.RegisterOption.ExportAllSlots):
        sys.exit("Could not register the D-Bus object")
    if not bus.registerService(BUS_NAME):
        sys.exit(f"{BUS_NAME} is already running")

    def finish_backlight():
        # Give UPower time to pick up the new LED, then show the real brightness there.
        service.changed()
        # PowerDevil only looks for keyboard backlights when it starts. The systemd
        # unit starts us first; if PowerDevil is already running, restart it once.
        powerdevil = QDBusInterface("org.kde.Solid.PowerManagement",
                                    "/org/kde/Solid/PowerManagement/Actions/KeyboardBrightnessControl",
                                    "org.kde.Solid.PowerManagement.Actions.KeyboardBrightnessControl", bus)
        if powerdevil.isValid():
            reply = powerdevil.call("keyboardBrightnessMax")
            if reply.arguments() and reply.arguments()[0] == 0:
                log("Backlight: restarting PowerDevil so it finds the new keyboard backlight")
                subprocess.run(["systemctl", "--user", "try-restart", "plasma-powerdevil.service"], check=False)

    if service.backlight:
        QTimer.singleShot(1500, finish_backlight)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
