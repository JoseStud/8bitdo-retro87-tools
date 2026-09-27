"""Native desktop app. Launch normally for reads; all hardware writes opt-in."""
import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QObject, Property, QRunnable, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

import retro87_core as protocol
from retro87_layout import keyboard_layout, label
from retro87_model import ApplyFailure, Draft, Snapshot, apply_draft, data_dir, decode


class JobSignals(QObject):
    finished = Signal(object, object)


class Job(QRunnable):
    def __init__(self, work):
        super().__init__()
        self.work = work
        self.signals = JobSignals()

    def run(self):
        try:
            result = self.work()
        except Exception as exc:
            self.signals.finished.emit(None, exc)
        else:
            self.signals.finished.emit(result, None)


class Controller(QObject):
    changed = Signal()

    def __init__(self, snapshot=None, allow_writes=False, device_factory=protocol.Keyboard):
        super().__init__()
        self.draft = Draft(snapshot) if snapshot else None
        self.allow_writes = allow_writes
        self.device_factory = device_factory
        self.live = False
        self.busy = False
        self.failure = False
        self.message = "Offline snapshot — no device I/O" if snapshot else "Connect to read the keyboard, or open a snapshot."
        self.error = ""
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.job = None
        self.callback = None

    @Property("QVariantMap", notify=changed)
    def state(self):
        result = decode(self.draft.profile) if self.draft else {
            "initialized": False, "profileName": "No device loaded", "mappings": {},
            "lighting": {"mode": "unknown", "color": None, "brightness": None, "speed": None},
            "volume": None, "sleepSeconds": None,
        }
        dirty = bool(self.draft and self.draft.dirty)
        result.update({"loaded": self.draft is not None, "live": self.live, "busy": self.busy,
                       "dirty": dirty, "message": self.message, "error": self.error,
                       "canApply": dirty and self.live and self.allow_writes and not self.busy and not self.failure,
                       "writesEnabled": self.allow_writes, "failure": self.failure,
                       "changes": list(self.draft.changes.values()) if dirty else [],
                       "byteCount": (sum(len(b) for _, b in self.draft.writes)
                                     + sum(a != b for a, b in zip(self.draft.baseline.led, self.draft.led))) if dirty else 0,
                       "backupDir": str(data_dir() / "backups")})
        if self.draft:
            result["savedLighting"] = decode(self.draft.baseline.profile)["lighting"]
            result["ranges"] = [f"{o:#06x}: {self.draft.baseline.profile[o:o+len(b)].hex(' ')} → {b.hex(' ')}" for o, b in self.draft.writes]
            if self.draft.led != self.draft.baseline.led:
                changed = sum(a != b for a, b in zip(self.draft.baseline.led, self.draft.led))
                result["ranges"].append(f"custom LED block (283 bytes, commands 0x0d/0x0e): {changed} bytes change")
            result["leds"] = protocol.decode_led(self.draft.led)
            result["savedLeds"] = protocol.decode_led(self.draft.baseline.led)
        else:
            result["savedLighting"] = result["lighting"]
            result["ranges"] = []
            result["leds"] = result["savedLeds"] = {"valid": False, "colors": {}}
        return result

    @Property("QVariantList", constant=True)
    def keyLayout(self):
        return keyboard_layout()

    @Property("QVariantList", constant=True)
    def targets(self):
        return [{"name": k, "label": label(k)} for k in protocol.TARGETS]

    def _run(self, work, callback):
        if self.busy:
            return
        self.busy, self.error = True, ""
        self.callback = callback
        self.job = Job(work)
        self.job.signals.finished.connect(self._finished)
        self.changed.emit()
        self.pool.start(self.job)

    @Slot(object, object)
    def _finished(self, result, error):
        self.busy = False
        if error:
            self.error = str(error)
            if isinstance(error, ApplyFailure):
                self.failure = True
                self.live = False
            if isinstance(error, (OSError, TimeoutError)):
                self.live = False
        else:
            self.callback(result)
        self.job = self.callback = None
        self.changed.emit()

    def _guard_clean(self):
        if self.busy:
            return False
        if self.draft and self.draft.dirty:
            self.error = "Export or discard pending edits before loading another baseline."
            self.changed.emit()
            return False
        return True

    @Slot()
    def connectDevice(self):
        if not self._guard_clean():
            return
        self.live = False
        def read():
            with self.device_factory(writable=False) as device:
                return Snapshot.read(device)
        def done(snapshot):
            self.draft = Draft(snapshot)
            self.live, self.failure = True, False
            self.message = "Dongle read successfully"
        self._run(read, done)

    @staticmethod
    def _path(url):
        parsed = QUrl(url)
        if parsed.isLocalFile():
            return Path(parsed.toLocalFile())
        if parsed.scheme():
            raise ValueError("Choose a local file")
        return Path(url).expanduser()

    @Slot(str)
    def openSnapshot(self, url):
        if not self._guard_clean():
            return
        def done(snapshot):
            self.draft, self.live, self.failure = Draft(snapshot), False, False
            self.message = "Offline snapshot · Apply is unavailable"
        self._run(lambda: Snapshot.load(self._path(url)), done)

    def _edit(self, action):
        if self.busy:
            return
        try:
            if not self.draft:
                raise ValueError("Read the keyboard or load a snapshot first")
            if self.failure:
                raise ValueError("After a partial write, export/discard edits and re-read before continuing")
            action(self.draft)
            self.error = ""
            self.message = "Edits staged locally. Device unchanged."
        except (ValueError, KeyError, PermissionError) as exc:
            self.error = str(exc)
        self.changed.emit()

    @Slot(str)
    def createProfile(self, name):
        self._edit(lambda draft: draft.create_profile(name))

    @Slot(str)
    def renameProfile(self, name):
        self._edit(lambda draft: draft.rename_profile(name))

    @Slot(str, str)
    def stageMap(self, source, target):
        self._edit(lambda draft: draft.map(source, target))

    @Slot(str)
    def stageDefault(self, source):
        def reset(draft):
            name = protocol.normalize(source)
            target = "none" if protocol.SOURCES[name]["code"] == 243 else name
            draft.map(name, target)
        self._edit(reset)

    @Slot(str, str, int, int)
    def stageRgb(self, mode, color, brightness, speed):
        self._edit(lambda draft: draft.rgb(mode, color, brightness, speed))

    @Slot(str, str, int, int, str, int, int)
    def stageEffect(self, mode, color, brightness, speed, echo_color, direction, count):
        self._edit(lambda draft: draft.rgb(mode, color, brightness, speed,
                                         echo_color=echo_color, direction=direction, count=count))

    @Slot(str)
    def stagePreset(self, mode):
        self._edit(lambda draft: draft.preset(mode))

    @Property("QVariantList", constant=True)
    def ledKeys(self):
        return list(protocol.LED_KEYS)

    @Slot("QVariantMap", str, str, int, int, int)
    def stageLeds(self, colors, default, effect, brightness, speed, count):
        self._edit(lambda draft: draft.custom_leds(dict(colors), default=default, effect=effect,
                                                   brightness=brightness, speed=speed, count=count))

    @Slot(int)
    def stageVolume(self, level):
        self._edit(lambda draft: draft.volume(level))

    @Slot()
    def discard(self):
        if self.draft and not self.busy:
            self.draft.discard()
            self.error = ""
            self.message = "Pending edits discarded. Device unchanged."
            self.changed.emit()

    @Slot(str, bool)
    def exportSnapshot(self, url, pending):
        if not self.draft or self.busy:
            return
        snapshot = Snapshot(self.draft.profile, self.draft.led) if pending else self.draft.baseline
        def done(_):
            self.message = "Saved staged profile" if pending else "Saved baseline backup"
            self.message += " · profile + custom LED bytes only; no macro storage"
        self._run(lambda: snapshot.save(self._path(url)), done)

    @Slot(str)
    def restoreProfile(self, url):
        # Read the file asynchronously; stage the result only on the GUI thread.
        if not self.draft or self.busy:
            return
        def done(snapshot):
            self._edit(lambda draft: draft.restore(snapshot))
        self._run(lambda: Snapshot.load(self._path(url)), done)

    @Slot()
    def applyConfirmed(self):
        if not self.state["canApply"]:
            self.error = "Apply unavailable: read the keyboard live (not a snapshot) and launch without --read-only."
            self.changed.emit()
            return
        draft = self.draft
        def done(result):
            snapshot, backup = result
            self.draft = Draft(snapshot)
            self.message = f"Applied and verified by readback. Backup: {backup}"
            if not protocol.profile_active(snapshot.profile):
                self.message += " " + protocol.PROFILE_ACTIVE_TIP
        self._run(lambda: apply_draft(draft, approved=True, device_factory=self.device_factory), done)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="Offline preview; never opens the device")
    parser.add_argument("--read-only", action="store_true", help="Never write to the keyboard (Apply disabled)")
    # Accepted for old launchers; writes are enabled by default since hardware verification.
    parser.add_argument("--allow-experimental-writes", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-test", action="store_true", help="Render offline and exit; no device I/O")
    parser.add_argument("--screenshot", type=Path, help="Save an offline render and exit; no device I/O")
    args = parser.parse_args()

    try:
        snapshot = Snapshot.load(args.snapshot) if args.snapshot else None
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    offline = bool(args.snapshot or args.smoke_test or args.screenshot)
    app = QGuiApplication([sys.argv[0]])
    app.setOrganizationName("Retro87Tools")
    app.setApplicationName("Retro 87 Tools")
    QQuickStyle.setStyle("Basic")
    controller = Controller(snapshot, not args.read_only and not offline)
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"bridge": controller})
    engine.load(QUrl.fromLocalFile(str(protocol.ROOT / "qml/Main.qml")))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    if args.smoke_test or args.screenshot:
        def finish():
            if args.screenshot and not window.grabWindow().save(str(args.screenshot)):
                app.exit(2)
            else:
                app.quit()
        QTimer.singleShot(1200, finish)
    elif not offline:
        QTimer.singleShot(0, controller.connectDevice)
    result = app.exec()
    controller.pool.waitForDone()
    # Destroy QML while its bridge remains alive.
    del engine
    return result


if __name__ == "__main__":
    sys.exit(main())
