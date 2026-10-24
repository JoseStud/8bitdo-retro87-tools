"""Local macro documents. Deliberately contains no device codec or transport.

Delays are milliseconds before an event; repeat is a finite playback count.
These are application semantics, not claims about the keyboard's wire format.
"""
from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot
import retro87_core as protocol

MAX_STEPS = 1008
KEYS = tuple(k for k in protocol.TARGETS if k != "none")


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}")


@dataclass(frozen=True)
class Event:
    key: str
    action: str
    delay_ms: int = 0

    def __post_init__(self):
        if self.key not in KEYS or self.action not in ("down", "up"):
            raise ValueError("Choose a supported key and down/up action")
        integer(self.delay_ms, 0, 65535, "Delay")


@dataclass(frozen=True)
class Macro:
    name: str = "Untitled"
    repeat: int = 1
    events: tuple = ()
    trigger: str = ""

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip() or "\0" in self.name:
            raise ValueError("Macro name must not be empty or contain NUL")
        if len(self.name.encode("utf-16-be")) > 32:
            raise ValueError("Macro name must fit in 16 UTF-16 code units")
        integer(self.repeat, 1, 255, "Repeat count")
        if self.trigger not in ("", *(f"k{i}" for i in range(1, 9))):
            raise ValueError("Choose an extension input K1–K8 or leave it unassigned")
        if not isinstance(self.events, tuple) or len(self.events) > MAX_STEPS or any(type(e) is not Event for e in self.events):
            raise ValueError(f"Use at most {MAX_STEPS} key events")

    @property
    def problems(self):
        held, issues = set(), []
        for i, event in enumerate(self.events, 1):
            if event.action == "down":
                if event.key in held:
                    issues.append(f"Event {i}: {event.key} is already held")
                held.add(event.key)
            else:
                if event.key not in held:
                    issues.append(f"Event {i}: {event.key} has no preceding press")
                held.discard(event.key)
        if held:
            issues.append("Missing release: " + ", ".join(sorted(held)))
        if not self.events:
            issues.append("Add key events to build a macro")
        return issues

    @classmethod
    def load(cls, path):
        with Path(path).open("rb") as stream:
            raw = stream.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            raise ValueError("Macro file is too large")
        try:
            data = json.loads(raw)
            if type(data) is not dict or data.get("format") != "retro87-macro" or type(data.get("version")) is not int:
                raise ValueError("Unsupported macro document")
            fields = {"format", "version", "name", "repeat", "events"}
            if data["version"] == 2:
                fields.add("trigger")
            elif data["version"] != 1:
                raise ValueError("Unsupported macro document version")
            if set(data) != fields or type(data["events"]) is not list:
                raise ValueError("Invalid macro document fields")
            if len(data["events"]) > MAX_STEPS:
                raise ValueError("Too many macro events")
            return cls(data["name"], data["repeat"], tuple(Event(**event) for event in data["events"]), data.get("trigger", ""))
        except (TypeError, KeyError, UnicodeError) as exc:
            raise ValueError("Invalid macro document") from exc

    def save(self, path):
        data = {"format": "retro87-macro", "version": 2, **asdict(self)}
        # Match snapshots: save to a new file, never silently replace a document.
        with Path(path).open("x", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")


class MacroEditor(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = self.baseline = Macro()
        self.error = ""

    @Property("QVariantMap", notify=changed)
    def state(self):
        doc = self.document
        return {"name": doc.name, "repeat": doc.repeat, "trigger": doc.trigger,
                "events": [asdict(e) for e in doc.events], "dirty": doc != self.baseline,
                "problems": doc.problems, "error": self.error,
                "durationMs": sum(e.delay_ms for e in doc.events) * doc.repeat}

    @Property("QStringList", constant=True)
    def keys(self):
        return list(KEYS)

    def _edit(self, operation):
        try:
            self.document = operation()
            self.error = ""
        except (ValueError, OSError) as exc:
            self.error = str(exc)
        self.changed.emit()

    @Slot(str)
    def setTrigger(self, trigger):
        self._edit(lambda: replace(self.document, trigger=trigger))

    @Slot(str, int)
    def configure(self, name, repeat):
        self._edit(lambda: replace(self.document, name=name, repeat=repeat))

    @Slot(str, str, int)
    def append(self, key, action, delay):
        self._edit(lambda: replace(self.document, events=self.document.events + (Event(key, action, delay),)))

    @Slot(int, str, str, int)
    def update(self, index, key, action, delay):
        def operation():
            integer(index, 0, len(self.document.events) - 1, "Event index")
            events = list(self.document.events)
            events[index] = Event(key, action, delay)
            return replace(self.document, events=tuple(events))
        self._edit(operation)

    @Slot(int, int)
    def move(self, index, delta):
        def operation():
            integer(index, 0, len(self.document.events) - 1, "Event index")
            integer(delta, -1, 1, "Move")
            integer(index + delta, 0, len(self.document.events) - 1, "Destination")
            events = list(self.document.events)
            events[index], events[index + delta] = events[index + delta], events[index]
            return replace(self.document, events=tuple(events))
        self._edit(operation)

    @Slot(int)
    def remove(self, index):
        def operation():
            integer(index, 0, len(self.document.events) - 1, "Event index")
            return replace(self.document, events=self.document.events[:index] + self.document.events[index + 1:])
        self._edit(operation)

    @Slot()
    def discard(self):
        self.document = self.baseline
        self.error = ""
        self.changed.emit()

    @Slot()
    def new(self):
        def operation():
            if self.document != self.baseline:
                raise ValueError("Save or discard macro edits before starting another macro")
            self.baseline = Macro()
            return self.baseline
        self._edit(operation)

    @Slot(str)
    def load(self, path):
        def operation():
            if self.document != self.baseline:
                raise ValueError("Save or discard macro edits before opening another file")
            doc = Macro.load(path)
            self.baseline = doc
            return doc
        self._edit(operation)

    @Slot(str)
    def save(self, path):
        def operation():
            self.document.save(path)
            self.baseline = self.document
            return self.document
        self._edit(operation)
