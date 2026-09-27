"""CLI compatibility entry point for the shared Retro 87 backend."""
from retro87_core import *  # Retain the original public import surface.

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="Use an existing backup for offline previews")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    backup = sub.add_parser("backup")
    backup.add_argument("file", type=Path)
    sub.add_parser("list-keys")
    mapping = sub.add_parser("map", help="Remap one key; defaults to preview")
    mapping.add_argument("source")
    mapping.add_argument("target")
    create = sub.add_parser("profile-create", help="Initialize a profile with the vendor defaults, keeping the current preset")
    create.add_argument("name")
    rgb = sub.add_parser("rgb", help="Set a built-in RGB preset; defaults to preview")
    rgb.add_argument("--mode", choices=("solid", "breathing", "off"), default="solid")
    rgb.add_argument("--color", default="#8000ff")
    rgb.add_argument("--brightness", type=int, default=50, help="0–100 percent")
    rgb.add_argument("--speed", type=int, default=5, help="1–10, for breathing")
    led = sub.add_parser("led", help="Per-key custom lighting; defaults to preview")
    led.add_argument("--default", default="#000000", help="Colour for keys not listed")
    led.add_argument("--key", action="append", default=[], metavar="NAME=#RRGGBB", help="Repeatable; see list-keys for LED key names")
    led.add_argument("--effect", choices=CUSTOM_EFFECTS, default="static", help="off = static at 0%% brightness; freeze holds the current frame")
    led.add_argument("--brightness", type=int, default=100, help="0–100 percent")
    led.add_argument("--speed", type=int, default=5, help="1–10, for breathing/starlight")
    led.add_argument("--count", type=int, default=25, help="5–100, starlight density")
    restore = sub.add_parser("restore-profile", help="Restore only the 1532-byte profile region from a backup")
    restore.add_argument("file", type=Path)
    for command in (mapping, create, rgb, led, restore):
        command.add_argument("--apply", action="store_true", help="Send the writes (saves a backup first, then verifies by readback)")
    args = parser.parse_args()
    if args.command == "list-keys":
        print("Source keys:", " ".join(k for k,v in SOURCES.items() if not 91 <= v["slot"] <= 107))
        print("Target keys:", " ".join(TARGETS))
        print("LED keys:", " ".join(LED_KEYS))
        print("Aliases:", ", ".join(f"{k}={v}" for k,v in ALIASES.items()))
        return
    apply = getattr(args, "apply", False)
    if args.snapshot and (apply or args.command == "backup"):
        parser.error("--snapshot is only for offline status and previews")
    if args.snapshot:
        profile, led = load_snapshot(args.snapshot)
        run_command(args, profile, led, None)
    else:
        with Keyboard(writable=apply) as keyboard:
            profile = keyboard.read_all()
            led = keyboard.read_all(15)
            run_command(args, profile, led, keyboard)

def run_command(args, profile, led, keyboard):
    if args.command == "status":
        show_status(profile)
        return
    if args.command == "backup":
        save_snapshot(args.file, profile, led)
        print("Saved:", args.file)
        return
    if args.command == "led":
        run_led(args, profile, led, keyboard)
        return
    if args.command == "map":
        writes = mapping_plan(profile, args.source, args.target)
    elif args.command == "profile-create":
        writes = profile_plan(profile, args.name)
    elif args.command == "rgb":
        writes = rgb_plan(args.mode, args.color, args.brightness, args.speed)
    elif args.command == "restore-profile":
        restored, _ = load_snapshot(args.file)
        writes = [(i, restored[i:i+53]) for i in range(40, PROFILE_SIZE, 53)]
        writes.append((0, restored[:40]))
    else:
        raise ValueError("Unknown command")
    writes = [(offset, data) for offset, data in writes if profile[offset:offset+len(data)] != data]
    if not writes:
        print("No changes needed.")
        return
    for offset, data in writes:
        print(f"{offset:#06x}: {profile[offset:offset+len(data)].hex(' ')} -> {data.hex(' ')}")
    if not args.apply:
        print("Preview only; no settings written. Add --apply to send these changes.")
        return
    backup_dir = ROOT / "backups"
    backup_dir.mkdir(exist_ok=True)
    path = backup_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8] + ".json")
    save_snapshot(path, profile, led)
    print("Backup saved:", path, flush=True)
    keyboard.apply(writes)
    print("Applied and verified by configuration readback.")
    if args.command in ("rgb", "profile-create") and not profile_active(profile):
        print(PROFILE_ACTIVE_TIP)
    if args.command in ("map", "profile-create"):
        print("The keyboard's profile button may need to be enabled for remaps to take effect.")

def run_led(args, profile, led, keyboard):
    colors = {}
    for item in args.key:
        name, sep, color = item.partition("=")
        if not sep:
            raise ValueError("Use --key NAME=#RRGGBB")
        led_indices(name)
        colors[name] = color
    block = led_block(colors, default=args.default, effect=args.effect, brightness=args.brightness, speed=args.speed, count=args.count)
    changed = sum(a != b for a, b in zip(led, block))
    print(f"Custom LED block: {changed} of {LED_SIZE} bytes change; custom lighting flag 0x5f9: {profile[0x5f9]} -> 1")
    if not args.apply:
        print("Preview only; no settings written. Add --apply to send these changes.")
        return
    backup_dir = ROOT / "backups"
    backup_dir.mkdir(exist_ok=True)
    path = backup_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8] + ".json")
    save_snapshot(path, profile, led)
    print("Backup saved:", path, flush=True)
    if led != block:
        keyboard.write_led(block)
    writes = [w for w in custom_led_plan(True) if profile[w[0]:w[0]+len(w[1])] != w[1]]
    if writes:
        keyboard.apply(writes)
    print("Applied and verified by readback.")
    if not profile_active(profile):
        print(PROFILE_ACTIVE_TIP)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
