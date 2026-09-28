#!/usr/bin/env python3
"""Install an optional user-local Waywallen capture bridge; no system files changed."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
MARKER = ".retro87-capture"
INJECTION = """
    // Retro 87 wallpaper capture bridge (optional, idle unless live mode is enabled).
    Retro87Capture {
        sourceItem: surfaceLoader.item
        screenName: root.Screen.name
    }
"""


def install(source, target):
    source, target = Path(source), Path(target)
    if target.exists() and not (target / MARKER).is_file():
        raise ValueError(f"Existing user wallpaper is not managed by Retro 87: {target}")
    main = (source / "contents/ui/main.qml").read_text()
    # Fail explicitly if upstream changes the integration points.
    if "id: root" not in main or "id: surfaceLoader" not in main or not main.rstrip().endswith("}"):
        raise ValueError("Unsupported Waywallen wallpaper layout: expected root and surfaceLoader")
    main = main.rstrip()[:-1] + INJECTION + "}\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".retro87-install-", dir=target.parent) as tmp:
        staged = Path(tmp) / target.name
        shutil.copytree(source, staged)
        (staged / "contents/ui/main.qml").write_text(main)
        shutil.copyfile(ROOT / "kde/Retro87Capture.qml", staged / "contents/ui/Retro87Capture.qml")
        (staged / MARKER).write_text(str(source) + "\n")
        if target.exists():
            shutil.rmtree(target)
        staged.rename(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("/usr/share/plasma/wallpapers/org.waywallen.kde"))
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    data = os.environ.get("XDG_DATA_HOME", "")
    base = Path(data) if data and Path(data).is_absolute() else Path.home() / ".local/share"
    target = base / "plasma/wallpapers/org.waywallen.kde"
    if args.uninstall:
        if target.exists():
            if not (target / MARKER).is_file():
                parser.error(f"Refusing to remove unmanaged wallpaper: {target}")
            shutil.rmtree(target)
    else:
        try:
            install(args.source, target)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    print("Capture bridge " + ("removed." if args.uninstall else "installed."))
    print("Log out and back in, or restart Plasma, to reload the wallpaper.")


if __name__ == "__main__":
    main()
