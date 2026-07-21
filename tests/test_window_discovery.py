import unittest

from nzm_auto.windowing.discovery import WindowInfo, matches_filters


class WindowFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.window = WindowInfo(
            hwnd=123,
            title="Example Game",
            class_name="GameWindowClass",
            window_width=1920,
            window_height=1080,
            client_width=1920,
            client_height=1080,
            visible=True,
            minimized=False,
        )

    def test_title_filter_is_case_insensitive(self) -> None:
        self.assertTrue(matches_filters(self.window, title_filter="example"))

    def test_class_filter_rejects_non_match(self) -> None:
        self.assertFalse(matches_filters(self.window, class_filter="browser"))


if __name__ == "__main__":
    unittest.main()
