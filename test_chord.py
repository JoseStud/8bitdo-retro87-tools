import unittest
from unittest.mock import Mock

import retro87_chord as chord


class ChordTests(unittest.TestCase):
    def test_fires_once_per_press_and_rearms_after_release(self):
        action = Mock()
        c = chord.Chord(("k7", "k8"), action)
        for held in [("k7",), ("k7", "k8"), ("k7", "k8"), ("k8",), ("k7", "k8")]:
            c.update(held)
        self.assertEqual(action.call_count, 1)  # Releasing one button does not re-arm.
        c.update(())
        c.update(("k8", "k7"))
        self.assertEqual(action.call_count, 2)

    def test_single_button_never_fires(self):
        action = Mock()
        c = chord.Chord(("k7", "k8"), action)
        c.update(("k7",))
        c.update(("k8",))
        c.update(("k1", "k7"))
        action.assert_not_called()


if __name__ == "__main__":
    unittest.main()
