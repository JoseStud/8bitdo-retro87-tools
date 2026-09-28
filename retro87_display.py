"""Experimental full-monitor capture. Default: colour JSON preview, no LED writes.

On Wayland, Qt uses the screen-sharing portal to ask which monitor to capture.
--apply forwards sampled frames to the explicitly enabled Retro 87 service.
"""
import argparse
import json
import signal
import sys
import time

from retro87_service import BUS_NAME, OBJECT_PATH
from retro87_wallpaper import key_colors, pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Send colours to the keyboard via the session service")
    parser.add_argument("--screen", help="Qt screen name on X11; Wayland uses the system screen picker")
    args = parser.parse_args()

    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtDBus import QDBusConnection, QDBusInterface
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink

    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName("Retro 87 Display Mirror")
    bus = QDBusConnection.sessionBus()
    service = QDBusInterface(BUS_NAME, OBJECT_PATH, BUS_NAME, bus)
    lock = QDBusInterface("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver", bus)

    def call(method, *values):
        reply = service.call(method, *values)
        if reply.errorName():
            raise RuntimeError(reply.errorMessage())
        return reply.arguments()[0]

    capture = QScreenCapture()
    if args.screen:
        if app.platformName().startswith("wayland"):
            parser.error("On Wayland choose the monitor in the system screen-sharing picker, not --screen")
        screen = next((s for s in app.screens() if s.name() == args.screen), None)
        if screen is None:
            parser.error("Unknown screen; available: " + ", ".join(s.name() for s in app.screens()))
        capture.setScreen(screen)
    session = QMediaCaptureSession()
    sink = QVideoSink()
    session.setScreenCapture(capture)
    session.setVideoSink(sink)
    next_frame = 0.0

    def fail(message):
        print(message, file=sys.stderr, flush=True)
        capture.stop()
        app.exit(1)

    def frame_ready(frame):
        nonlocal next_frame
        now = time.monotonic()
        if now < next_frame or not frame.isValid():
            return
        next_frame = now + 0.1
        # Check even in preview mode; never publish captured lock-screen frames.
        reply = lock.call("GetActive")
        if reply.errorName() or reply.arguments() != [False]:
            return
        try:
            path = ""
            if args.apply:
                state = json.loads(call("Status"))
                if state.get("wallpaperSync") != "display":
                    app.quit()
                    return
                if state.get("wallpaperLiveError"):
                    raise RuntimeError(state["wallpaperLiveError"])
                path = call("DisplayFrameTarget")
                if not path:
                    return
            image = frame.toImage()
            if image.isNull():
                return
            small = image.scaled(192, 192, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if args.apply:
                if not small.save(path, "PNG"):
                    raise RuntimeError("Cannot save display capture")
                state = json.loads(call("WallpaperFrame", path))
                if state.get("wallpaperLiveError"):
                    raise RuntimeError(state["wallpaperLiveError"])
            else:
                print(json.dumps(key_colors(pixels(small, small.width(), small.height()), crop=False)), flush=True)
        except (OSError, RuntimeError, ValueError) as exc:
            fail(str(exc))

    sink.videoFrameChanged.connect(frame_ready)
    capture.errorOccurred.connect(lambda error, message: fail("Screen capture: " + message))
    # The timer lets Python process SIGINT while Qt is idle waiting for frames.
    heartbeat = QTimer(interval=250)
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start()
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())

    if args.apply:
        try:
            state = json.loads(call("Set", "wallpaper", "display"))
            if not state.get("ok"):
                parser.error(state.get("message", "Cannot start display mirroring"))
        except RuntimeError as exc:
            parser.error(str(exc))

    def cleanup():
        capture.stop()
        if args.apply:
            try:
                if json.loads(call("Status")).get("wallpaperSync") == "display":
                    call("Set", "wallpaper", "off")
            except (RuntimeError, ValueError):
                pass

    app.aboutToQuit.connect(cleanup)
    print("Choose a monitor if prompted. Ctrl+C stops mirroring. " +
          ("Keyboard output enabled." if args.apply else "Preview only; no keyboard writes."), file=sys.stderr)
    QTimer.singleShot(0, capture.start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
