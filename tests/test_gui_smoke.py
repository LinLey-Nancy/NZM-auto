import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nzm_auto.gui.main_window import MainWindow


class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_main_window_builds_and_adds_a_step(self) -> None:
        window = MainWindow()

        self.assertEqual(window.palette.count(), 6)
        self.assertFalse(window.stop_button.isEnabled())
        self.assertTrue(window.run_button.isEnabled())
        window.palette.setCurrentRow(5)
        window.add_selected_action()

        self.assertEqual(window.step_list.count(), 1)
        self.assertEqual(window.document.steps[0]["type"], "wait")
        window.document.dirty = False
        window.close()


if __name__ == "__main__":
    unittest.main()
