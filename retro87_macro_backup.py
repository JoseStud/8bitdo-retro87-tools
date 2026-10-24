"""Read-only, full-allocation macro backup; separate from profile snapshots.

This captures the vendor app's ten 4096-byte allocations. It does not establish
command 5's erase extent and does not enable hardware macro writes/restoration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct

import retro87_core as protocol


def capture(device):
    profile = device.read_all()
    led = device.read_all(15)
    if len(profile) != protocol.PROFILE_SIZE or len(led) != 283:
        raise RuntimeError("Incomplete profile/LED backup")
    for name, address in assignments(profile).items():
        if address % protocol.MACRO_BLOCK_SIZE or not 0 <= address < protocol.MACRO_STORAGE_SIZE:
            raise RuntimeError(f"{name} references unsupported macro address {address:#x}; backup coverage is unknown")
    blocks = {}
    for address in range(0, protocol.MACRO_STORAGE_SIZE, protocol.MACRO_BLOCK_SIZE):
        block = device.read_macro_block(address)
        if len(block) != protocol.MACRO_BLOCK_SIZE:
            raise RuntimeError("Incomplete macro allocation read")
        blocks[address] = block
    # Refuse any change observed between the two reads of each region.
    if device.read_all() != profile or device.read_all(15) != led:
        raise RuntimeError("Keyboard configuration changed during macro backup; stopped")
    for address, block in blocks.items():
        if device.read_macro_block(address) != block:
            raise RuntimeError(f"Macro storage changed during backup at {address:#x}; stopped")
    return {
        "format": "retro87-macro-backup", "version": 1,
        "created": datetime.now(timezone.utc).isoformat(),
        "connection": getattr(device, "connection", "unknown"),
        "profile": profile.hex(), "led": led.hex(),
        "blocks": [{"address": address, "data": block.hex(),
                    "sha256": hashlib.sha256(block).hexdigest()} for address, block in blocks.items()],
    }


def assignments(profile):
    """Existing macro references only; do not mistake defaults for macro zero."""
    if len(profile) != protocol.PROFILE_SIZE:
        raise ValueError("Invalid profile size")
    if not protocol.valid_profile(profile):
        return {}
    return {name: struct.unpack_from("<I", profile, 44 + item["slot"] * 12)[0]
            for name, item in protocol.SOURCES.items()
            if struct.unpack_from("<I", profile, 48 + item["slot"] * 12)[0] == 4}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New JSON backup path (will not overwrite)")
    args = parser.parse_args()
    # Reserve the destination first; never leave a partial file presented as a backup.
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            try:
                with protocol.Keyboard(writable=False) as device:
                    data = capture(device)
                json.dump(data, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                args.output.unlink()
                raise
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Macro backup failed: {exc}\n")
    print(f"Saved ten complete macro blocks plus profile and LEDs: {args.output}")
    print("Hardware macro writes and restoration remain disabled.")


if __name__ == "__main__":
    main()
