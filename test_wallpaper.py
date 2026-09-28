import sqlite3
import tempfile
import unittest
from pathlib import Path

import retro87_core as protocol
import retro87_wallpaper as wallpaper


class WallpaperTests(unittest.TestCase):
    def test_accent_picks_the_dominant_saturated_hue(self):
        grid = [[(20, 20, 20)] * 10 for _ in range(6)]       # dark background, ignored
        grid += [[(30, 120, 40)] * 10 for _ in range(3)]     # green area
        grid += [[(200, 30, 30)] * 2 for _ in range(1)]      # small red patch
        grid[-1] += [(20, 20, 20)] * 8
        color = wallpaper.accent_color(grid)
        r, g, b = (int(color[i:i+2], 16) for i in (1, 3, 5))
        self.assertEqual(max(r, g, b), g)
        self.assertEqual(g, 255)

    def test_greyscale_gives_white(self):
        self.assertEqual(wallpaper.accent_color([[(90, 90, 90)] * 8] * 8), "#ffffff")

    def test_key_colors_follow_the_picture(self):
        # Left half red, right half blue; top rows would be cropped away if taller.
        grid = [[(255, 0, 0)] * 48 + [(0, 0, 255)] * 48 for _ in range(64)]
        colors = wallpaper.key_colors(grid)
        self.assertEqual(set(colors), set(protocol.LED_KEYS))
        self.assertEqual(colors["q"], "#ff0000")
        self.assertEqual(colors["esc"], "#ff0000")
        self.assertEqual(colors["pgdn"], "#0000ff")
        self.assertEqual(colors["right"], "#0000ff")
        protocol.led_block(colors)  # Valid input for the per-key block.

    def test_vivid_brightens_and_saturates(self):
        self.assertEqual(wallpaper.vivid((0, 0, 0)), "#000000")
        self.assertEqual(wallpaper.vivid((64, 0, 0)), "#ff0000")
        r, g, b = (int(wallpaper.vivid((200, 180, 180))[i:i+2], 16) for i in (1, 3, 5))
        self.assertEqual(r, 255)
        self.assertLess(g, 180 * 255 // 200)  # More saturated than the input.

    def test_full_frame_mapping_keeps_top_and_bottom_edges(self):
        grid = [[(255, 0, 0)] * 96 for _ in range(12)]
        grid += [[(0, 255, 0)] * 96 for _ in range(40)]
        grid += [[(0, 0, 255)] * 96 for _ in range(12)]
        colors = wallpaper.key_colors(grid, crop=False)
        self.assertEqual(colors["esc"], "#ff0000")
        self.assertEqual(colors["space"], "#0000ff")
        self.assertNotEqual(wallpaper.key_colors(grid)["esc"], colors["esc"])

    def test_wallpaper_info_reads_the_library_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "waywallen-v2.db"
            with sqlite3.connect(db) as connection:
                connection.execute("CREATE TABLE library (id INTEGER PRIMARY KEY, plugin_id, path TEXT)")
                connection.execute("CREATE TABLE item (id INTEGER PRIMARY KEY, library_id, display_name TEXT, preview_path TEXT)")
                connection.execute("INSERT INTO library VALUES (7, 1, '/steam')")
                connection.execute("INSERT INTO item VALUES (495, 7, 'Forest', 'workshop/1/preview.jpg')")
                connection.execute("INSERT INTO item VALUES (496, 7, 'No preview', NULL)")
            self.assertEqual(wallpaper.wallpaper_info("495", db), ("Forest", Path("/steam/workshop/1/preview.jpg")))
            self.assertIsNone(wallpaper.wallpaper_info("496", db))
            self.assertIsNone(wallpaper.wallpaper_info("999", db))
            self.assertIsNone(wallpaper.wallpaper_info("", db))
            self.assertIsNone(wallpaper.wallpaper_info("1", Path(tmp) / "missing.db"))


if __name__ == "__main__":
    unittest.main()
