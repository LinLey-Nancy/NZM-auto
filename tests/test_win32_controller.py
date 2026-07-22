import unittest

from nzm_auto.runtime.win32_controller import (
    ControllerConnectionError,
    combine_screencap_methods,
    parse_input_method,
)


class Win32ControllerConfigTests(unittest.TestCase):
    def test_background_screencap_methods_are_combined(self) -> None:
        self.assertEqual(combine_screencap_methods(["FramePool", "PrintWindow"]), 18)

    def test_post_message_input_is_parsed(self) -> None:
        self.assertEqual(parse_input_method("PostMessage"), 4)

    def test_unknown_screencap_method_is_rejected(self) -> None:
        with self.assertRaises(ControllerConnectionError):
            combine_screencap_methods(["Unknown"])
