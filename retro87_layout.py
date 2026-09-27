"""Independent scalable ANSI TKL geometry; no vendor artwork."""
LABELS = {"esc": "Esc", "backspace": "Backspace", "capslock": "Caps Lock", "lctrl": "Ctrl", "rctrl": "Ctrl", "lshift": "Shift", "rshift": "Shift", "lalt": "Alt", "ralt": "Alt", "lwin": "Win", "rwin": "Win", "space": "Space", "prtsc": "PrtSc", "scrlk": "ScrLk", "pgup": "PgUp", "pgdn": "PgDn", "tilde": "`", "minus": "−", "equal": "=", "leftbracket": "[", "rightbracket": "]", "backslash": "\\", "semicolon": ";", "quotation": "'", "comma": ",", "period": ".", "slash": "/", "up": "↑", "down": "↓", "left": "←", "right": "→", "ka": "A", "kb": "B", "fn": "Fn"}


def label(key):
    return LABELS.get(key, key[3:] if key.startswith("num") and len(key) == 4 else key.upper() if len(key) == 1 or key.startswith("f") else key.title())


def keyboard_layout():
    keys = []
    def row(y, names, x=0):
        for item in names:
            key, width = item if isinstance(item, tuple) else (item, 1)
            if key:
                keys.append({"key": key, "label": label(key), "x": x, "y": y, "units": width, "editable": key != "fn"})
            x += width
    row(0, ["esc", ("", 1), "f1", "f2", "f3", "f4", ("", .5), "f5", "f6", "f7", "f8", ("", .5), "f9", "f10", "f11", "f12"])
    row(0, ["prtsc", "scrlk", "pause"], 15.5)
    row(1.5, ["tilde"] + ["num" + str(i) for i in range(1, 10)] + ["num0", "minus", "equal", ("backspace", 2)])
    row(2.5, [("tab", 1.5)] + list("qwertyuiop") + ["leftbracket", "rightbracket", ("backslash", 1.5)])
    row(3.5, [("capslock", 1.75)] + list("asdfghjkl") + ["semicolon", "quotation", ("enter", 2.25)])
    row(4.5, [("lshift", 2.25)] + list("zxcvbnm") + ["comma", "period", "slash", ("rshift", 2.75)])
    row(5.5, [("lctrl", 1.25), ("lwin", 1.25), ("lalt", 1.25), ("space", 6.25), "ralt", "fn", "kb", "ka", "rctrl"])
    row(1.5, ["insert", "home", "pgup"], 15.5)
    row(2.5, ["delete", "end", "pgdn"], 15.5)
    row(4.5, ["up"], 16.5)
    row(5.5, ["left", "down", "right"], 15.5)
    return keys
