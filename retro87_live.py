"""Bounded live frame delivery, independent of Qt's event loop and capture frontend.

Only explicitly enabled sessions accept frames. A capture request leases one
private PNG path; submissions from previous modes/screens are discarded.

Frames go to the keyboard's HID LampArray when it is connected by USB cable
(runtime colours, up to USB_INTERVAL). Over the 2.4 GHz dongle the only path is
the custom-LED configuration, whose prepare step erases flash on every write
(research/storage-wear.md), so it is used only with --experimental-live.
"""
from pathlib import Path
import tempfile
import time
import uuid

from retro87_wallpaper import key_colors, pixels


class LiveMirror:
    INTERVAL = 0.5
    USB_INTERVAL = 0.1
    LEASE = 5.0

    def __init__(self, controller, runtime_dir, *, allowed=False, screen="", clock=time.monotonic, lamps=None):
        self.controller, self.lamps = controller, lamps
        self.runtime_dir = Path(runtime_dir)
        self.allowed, self.screen, self.clock = allowed, screen, clock
        self.enabled = False
        self.crop = True
        self.error = ""
        self.frames = 0
        self.last_colors = None
        self.next_frame = 0.0
        self.owner = None
        self.owner_seen = 0.0
        self.pending = None
        self.directory = None

    def set_enabled(self, enabled):
        if enabled and not self.allowed and not self.usb():
            raise ValueError("Live mirroring needs the keyboard's USB cable. Over 2.4 GHz every frame "
                             "erases the keyboard's flash; --experimental-live allows that anyway.")
        self.close()
        self.enabled = enabled
        self.error = ""
        self.last_colors = None
        self.next_frame = 0.0

    def usb(self):
        return self.lamps is not None and self.lamps.available()

    def close(self):
        if self.lamps is not None:
            self.lamps.close()
        self.enabled = False
        self.pending = None
        self.owner = None
        if self.directory:
            self.directory.cleanup()
            self.directory = None

    def target(self, screen, *, unlocked):
        now = self.clock()
        if not self.enabled or not unlocked or self.error or now < self.next_frame:
            return ""
        if not screen or len(screen) > 256 or (self.screen and screen != self.screen):
            return ""
        if self.owner != screen:
            if self.owner is not None and now - self.owner_seen < self.LEASE:
                return ""
            self.owner = screen
        self.owner_seen = now
        if self.pending:
            path, created = self.pending
            if now - created < self.LEASE:
                return ""
            path.unlink(missing_ok=True)
        if self.directory is None:
            self.directory = tempfile.TemporaryDirectory(prefix="retro87-live-", dir=self.runtime_dir)
        path = Path(self.directory.name) / (uuid.uuid4().hex + ".png")
        self.pending = (path, now)
        return str(path)

    def submit(self, path, *, unlocked):
        """Consume one granted capture. Errors latch until live mode is reselected."""
        if not self.pending or str(self.pending[0]) != path:
            return False
        frame, created = self.pending
        self.pending = None
        try:
            now = self.clock()
            if (not self.enabled or not unlocked or self.error or
                    now - created >= self.LEASE or now < self.next_frame):
                return False
            from PySide6.QtGui import QImageReader
            if frame.is_symlink() or frame.stat().st_size > 128 * 1024:
                raise ValueError("Invalid live wallpaper frame")
            reader = QImageReader(str(frame), b"png")
            size = reader.size()
            if not (1 <= size.width() <= 192 and 1 <= size.height() <= 192):
                raise ValueError("Live wallpaper frame must be at most 192 × 192 pixels")
            image = reader.read()
            if image.isNull():
                raise ValueError("Cannot decode live wallpaper frame")
            # Preserve capture aspect ratio for the keyboard's centre crop.
            colors = key_colors(pixels(image, image.width(), image.height()), crop=self.crop)
            usb = self.usb()
            self.next_frame = now + (self.USB_INTERVAL if usb else self.INTERVAL)
            if colors == self.last_colors:
                return False
            if usb:
                self.lamps.set_leds(colors)
            elif self.allowed:
                self.controller.set_leds(colors)
            else:
                raise RuntimeError("The keyboard's USB cable was disconnected; live mirroring stopped.")
            self.last_colors = colors
            self.frames += 1
            return True
        except (OSError, RuntimeError, ValueError) as exc:
            self.error = str(exc)
            return False
        finally:
            try:
                frame.unlink(missing_ok=True)
            except OSError as exc:
                self.error = str(exc)
