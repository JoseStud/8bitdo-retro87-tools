"""Keyboard lighting from the current waywallen wallpaper.

waywallen (https://github.com/waywallen/waywallen) publishes the playing
wallpaper as the CurrentWallpaperId property of org.waywallen.waywallen.Daemon1.
Its library database gives each wallpaper a preview image, which is analysed
here. Only the pixel analysis needs Qt (QImage), for loading JPEG/GIF/PNG.
"""
import colorsys
import os
from pathlib import Path
import sqlite3

from retro87_core import LED_KEYS
from retro87_layout import keyboard_layout

WAYWALLEN_SERVICE = "org.waywallen.waywallen.Daemon"
WAYWALLEN_PATH = "/org/waywallen/waywallen/Daemon"
WAYWALLEN_IFACE = "org.waywallen.waywallen.Daemon1"
SYNC_MODES = ("off", "color", "keys", "live", "display")


def database_path():
    value = os.environ.get("XDG_DATA_HOME", "")
    root = Path(value) if value and Path(value).is_absolute() else Path.home() / ".local/share"
    return root / "waywallen/waywallen-v2.db"


def wallpaper_info(item_id, db=None):
    """(display name, absolute preview path) for a waywallen library item, or None."""
    try:
        number = int(item_id)
    except (TypeError, ValueError):
        return None
    path = Path(db) if db else database_path()
    if not path.exists():
        return None
    # Read-only: waywallen owns the database.
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "SELECT i.display_name, i.preview_path, l.path FROM item i JOIN library l ON l.id = i.library_id WHERE i.id = ?",
            (number,)).fetchone()
    if not row or not row[1]:
        return None
    preview = Path(row[1]) if Path(row[1]).is_absolute() else Path(row[2]) / row[1]
    return row[0], preview


def pixels(image, width, height):
    """RGB tuples of a QImage scaled to width x height (smooth), row by row."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    small = image.convertToFormat(QImage.Format.Format_RGB888).scaled(
        width, height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    data = bytes(small.constBits())[:small.sizeInBytes()]
    stride = small.bytesPerLine()
    return [[tuple(data[y*stride + x*3:y*stride + x*3 + 3]) for x in range(width)] for y in range(height)]


def vivid(rgb):
    """LED version of a colour: full value and boosted saturation.

    LEDs show dark colours as dim rather than as dark hues, and pale colours
    look white, so both are pushed towards the pure hue.
    """
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    if v < 0.02:
        return "#000000"
    r, g, b = colorsys.hsv_to_rgb(h, s ** 0.5, 1)
    return "#%02x%02x%02x" % (round(r*255), round(g*255), round(b*255))


def accent_color(grid):
    """Dominant saturated hue of a pixel grid, as #rrggbb; white for greyscale images."""
    bins = [[0.0, 0.0, 0.0, 0.0] for _ in range(24)]
    for row in grid:
        for rgb in row:
            h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
            weight = s * s * v
            entry = bins[int(h * 24) % 24]
            entry[0] += weight
            for i in range(3):
                entry[i+1] += rgb[i] * weight
    total = max(bins, key=lambda entry: entry[0])
    if total[0] < 0.5:
        return "#ffffff"
    return vivid(tuple(c / total[0] for c in total[1:]))


def key_colors(grid, *, crop=True):
    """Average the picture under each key; crop to the board, or fit the entire frame."""
    keys = [k for k in keyboard_layout() if k["key"] in LED_KEYS]
    board_w = max(k["x"] + k["units"] for k in keys)
    board_h = max(k["y"] for k in keys) + 1
    rows, cols = len(grid), len(grid[0])
    # Crop the grid to the keyboard's aspect ratio (cover, like a wallpaper).
    if not crop:
        width, height = cols, rows
    elif cols / rows > board_w / board_h:
        width, height = rows * board_w / board_h, rows
    else:
        width, height = cols, cols * board_h / board_w
    left, top = (cols - width) / 2, (rows - height) / 2
    result = {}
    for key in keys:
        x0 = int(left + key["x"] / board_w * width)
        x1 = max(x0 + 1, int(left + (key["x"] + key["units"]) / board_w * width))
        y0 = int(top + key["y"] / board_h * height)
        y1 = max(y0 + 1, int(top + (key["y"] + 1) / board_h * height))
        cells = [grid[y][x] for y in range(y0, min(y1, rows)) for x in range(x0, min(x1, cols))]
        average = tuple(sum(c[i] for c in cells) / len(cells) for i in range(3))
        result[key["key"]] = vivid(average)
    return result


def analyse(path):
    """(accent colour, per-key colours) for an image file, or None if it cannot be read."""
    from PySide6.QtGui import QImage
    image = QImage(str(path))
    if image.isNull():
        return None
    return accent_color(pixels(image, 48, 48)), key_colors(pixels(image, 96, 64))
