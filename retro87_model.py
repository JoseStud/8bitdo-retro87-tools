"""Pure desktop state and transactions. No Qt dependency and no implicit I/O."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
import struct
import uuid

import retro87_core as protocol


@dataclass(frozen=True)
class Snapshot:
    profile: bytes
    led: bytes

    def __post_init__(self):
        if len(self.profile) != protocol.PROFILE_SIZE or len(self.led) != 283:
            raise ValueError("Invalid snapshot region sizes")

    @classmethod
    def load(cls, path):
        return cls(*protocol.load_snapshot(Path(path)))

    @classmethod
    def read(cls, device):
        return cls(device.read_all(), device.read_all(15))

    def save(self, path):
        protocol.save_snapshot(Path(path), self.profile, self.led)


def data_dir():
    value = os.environ.get("XDG_DATA_HOME", "")
    root = Path(value) if value and Path(value).is_absolute() else Path.home() / ".local/share"
    return root / "retro87-tools"


def patch_bytes(original, writes):
    result = bytearray(original)
    for offset, data in writes:
        if not data or not 0 <= offset < len(result) or offset + len(data) > len(result):
            raise ValueError("Invalid staged range")
        result[offset:offset + len(data)] = data
    return bytes(result)


def diff_writes(before, after):
    """Parameters first, RGB activation next, profile marker published LAST."""
    if len(before) != protocol.PROFILE_SIZE or len(after) != len(before):
        raise ValueError("Invalid profile length")
    writes = []
    themes = [(offset, offset + size) for offset, size in protocol.THEMES.values()]
    for lo, hi in [(40, 0x5ca), (0x5cb, 0x5d0), *themes, (0x5fb, len(before)),
                   (0x5fa, 0x5fb), (0x5f9, 0x5fa), (0x5ca, 0x5cb), (4, 40), (0, 4)]:
        # Vendor writeXboxJPColor always submits complete theme structs. A
        # matching storage readback does not prove partial writes activate LEDs.
        if (lo, hi) in themes:
            if before[lo:hi] != after[lo:hi]:
                writes.append((lo, after[lo:hi]))
            continue
        i = lo
        while i < hi:
            if before[i] == after[i]:
                i += 1
                continue
            start = i
            while i < hi and before[i] != after[i] and i - start < 53:
                i += 1
            writes.append((start, after[start:i]))
    return writes


def decode(profile):
    valid = protocol.valid_profile(profile)
    mode = next((k for k, v in protocol.MODES.items() if v == profile[0x5ca]), "unknown")
    mappings = {}
    for name, item in protocol.SOURCES.items():
        _, target, kind = struct.unpack_from("<B3xII", profile, 40 + item["slot"] * 12)
        if not valid:
            label = "Unknown / no profile"
        elif kind == 0:
            label = "Default"
        elif kind == 1:
            label = next((k for k, v in protocol.TARGETS.items() if v == target), f"Unknown key {target:#x}")
        else:
            label = f"Preserved assignment (type {kind}, value {target:#x})"
        mappings[name] = label
    lighting = {"mode": mode, "brightness": None, "speed": None, "color": None,
                "echoColor": None, "direction": None, "count": None}
    if mode in protocol.THEMES:
        start, size = protocol.THEMES[mode]
        values = profile[start:start + size]
        if values != b"\xff" * size:
            lighting["brightness"] = round(values[0] * 100 / 255)
            if mode != "solid" and 1 <= values[1] <= 10:
                lighting["speed"] = 11 - values[1]
            flag = {"solid": 1, "breathing": 2, "ripple": 2, "resonance": 2, "starlight": 3}.get(mode)
            if flag is not None and values[flag] == 1:
                lighting["color"] = "#" + values[flag+1:flag+4].hex()
                if mode in ("resonance", "starlight"):
                    lighting["echoColor"] = "#" + values[flag+4:flag+7].hex()
            if mode == "color-ripple" and values[2] <= 5:
                lighting["direction"] = values[2]
            if mode == "starlight" and 5 <= values[2] <= 100:
                lighting["count"] = values[2]
    return {
        "initialized": valid,
        "profileActive": protocol.profile_active(profile),
        "profileName": profile[4:36].decode("utf-16-be", errors="replace").rstrip("\0") if valid else "Not initialized",
        "mappings": mappings, "lighting": lighting,
        "volume": profile[0x5c9] if 1 <= profile[0x5c9] <= 5 else None,
        "sleepSeconds": struct.unpack_from("<I", profile, 0x5cc)[0],
        "customLighting": profile[0x5f9], "lightingEngine": profile[0x5fa],
    }


class Draft:
    def __init__(self, baseline):
        self.baseline = baseline
        self.profile = baseline.profile
        self.led = baseline.led
        self.changes = {}
        self._regions = {}

    @property
    def dirty(self):
        return self.profile != self.baseline.profile or self.led != self.baseline.led

    @property
    def writes(self):
        return diff_writes(self.baseline.profile, self.profile)

    def _stage(self, key, label, writes):
        self.profile = patch_bytes(self.profile, writes)
        self.changes[key] = label
        # Keep earlier edits to inactive presets visible in the review summary.
        self._regions[key] = list(set(self._regions.get(key, []) + [(offset, len(data)) for offset, data in writes]))
        for item in list(self.changes):
            if item == "leds":
                continue
            if all(self.profile[o:o+n] == self.baseline.profile[o:o+n] for o, n in self._regions[item]):
                self.changes.pop(item)
                self._regions.pop(item)

    def create_profile(self, name):
        self._stage("profile", f"Create profile: {name}", protocol.profile_plan(self.profile, name))

    def rename_profile(self, name):
        if not protocol.valid_profile(self.profile):
            raise ValueError("Create a profile first")
        encoded = name.encode("utf-16-be")
        if not name or "\0" in name or len(encoded) > 32:
            raise ValueError("Use 1–16 UTF-16 code units without NUL")
        self._stage("profile", f"Rename profile: {name}", [(4, encoded.ljust(32, b"\0"))])

    def map(self, source, target):
        self._stage("key:" + source, f"{source} → {target}", protocol.mapping_plan(self.profile, source, target))

    def rgb(self, mode, color, brightness, speed, **options):
        self._stage("rgb:" + mode, f"Lighting parameters: {mode}, {brightness}% (see byte review)",
                    protocol.rgb_plan(mode, color, brightness, speed, **options))

    def preset(self, mode):
        if mode not in protocol.MODES:
            raise ValueError("Unknown effect")
        self._stage("preset", f"Select {mode} with stored parameters", protocol.activation_plan(mode))

    def custom_leds(self, colors, *, default="#000000", effect="static", brightness=100, speed=5, count=25):
        """Stage the per-key LED block and enable custom lighting (0x5f9 = 1)."""
        self.led = protocol.led_block(colors, default=default, effect=effect, brightness=brightness, speed=speed, count=count)
        self._regions["leds"] = []
        shown = "off (0% brightness)" if effect == "off" else f"{effect}, {brightness}%"
        self.changes["leds"] = f"Per-key lighting: {shown}, {len(colors)} keys coloured"
        self._stage("custom", "Enable custom per-key lighting", protocol.custom_led_plan(True))
        if self.led == self.baseline.led:
            self.changes.pop("leds", None)
            self._regions.pop("leds", None)

    def volume(self, level):
        if type(level) is not int or not 1 <= level <= 5:
            raise ValueError("Device volume must be a level from 1 to 5")
        self._stage("volume", f"Device sound level: {level}", [(0x5c9, bytes([level]))])

    def restore(self, snapshot):
        self.profile = snapshot.profile
        self.led = self.baseline.led
        self.changes = {"restore": "Restore profile region only (not macros/custom LEDs)"} if self.dirty else {}
        self._regions = {"restore": [(0, len(self.profile))]} if self.dirty else {}

    def discard(self):
        self.profile = self.baseline.profile
        self.led = self.baseline.led
        self.changes.clear()
        self._regions.clear()


class ApplyFailure(RuntimeError):
    """Device may have partially changed; no automatic retry is safe."""
    def __init__(self, backup, cause):
        self.backup = backup
        super().__init__(f"Stopped: device may be partially changed. Backup: {backup}. {cause}. Re-read before recovery; no retry or rollback was attempted.")


def apply_draft(draft, *, approved=False, backup_dir=None, device_factory=protocol.Keyboard):
    """Explicit single transaction. The caller must obtain the user's confirmation first."""
    if not approved:
        raise PermissionError("Writes require explicit confirmation")
    writes = draft.writes
    led_changed = draft.led != draft.baseline.led
    if not writes and not led_changed:
        return draft.baseline, None
    with device_factory(writable=True) as device:
        fresh = Snapshot.read(device)
        if fresh != draft.baseline:
            raise RuntimeError("Device changed since loading (the keyboard's Profile or lighting keys also change it). Export your draft, discard edits and re-read before applying.")
        directory = Path(backup_dir) if backup_dir else data_dir() / "backups"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup = directory / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex + ".json")
        fresh.save(backup)  # Exclusive create, before any configuration command.
        try:
            # Custom LED data first, so enabling custom mode shows the new block.
            if led_changed:
                device.write_led(draft.led)
            if writes:
                device.apply(writes)
            result = Snapshot.read(device)
            if result.profile != draft.profile or result.led != draft.led:
                raise RuntimeError("Full readback mismatch")
        except Exception as exc:
            raise ApplyFailure(backup, exc) from exc
        return result, backup


class SimulatedKeyboard:
    """In-memory transport for automated tests; never opens a HID device."""
    def __init__(self, snapshot, *, writable=False, fail_after=None):
        self.snapshot = snapshot
        self.writable = writable
        self.fail_after = fail_after
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read_all(self, command=2):
        self.calls.append(("read", command))
        return self.snapshot.profile if command == 2 else self.snapshot.led

    def write_led(self, block):
        if not self.writable:
            raise PermissionError("Simulation is read-only")
        if self.fail_after == "led":
            raise OSError("Simulated disconnect")
        self.calls.append(("write_led", block))
        self.snapshot = Snapshot(self.snapshot.profile, block)

    def apply(self, writes):
        if not self.writable:
            raise PermissionError("Simulation is read-only")
        for i, write in enumerate(writes):
            if self.fail_after == i:
                raise OSError("Simulated disconnect")
            self.calls.append(("write", write))
            self.snapshot = Snapshot(patch_bytes(self.snapshot.profile, [write]), self.snapshot.led)
