import unittest

import numpy

from nzm_auto.runtime.win32_controller import (
    ControllerConnectionError,
    combine_screencap_methods,
    connect_controller,
    parse_input_method,
)


class _SuccessfulJob:
    succeeded = True

    def __init__(self, result=None) -> None:
        self.result = result

    def wait(self):
        return self

    def get(self):
        return self.result


class _FakeController:
    connected = True

    def __init__(
        self,
        raw_resolution: tuple[int, int] = (1920, 1080),
        screenshot_resolution: tuple[int, int] = (1280, 720),
    ) -> None:
        self.resolution = raw_resolution
        width, height = screenshot_resolution
        self.screenshot = numpy.zeros((height, width, 3), dtype=numpy.uint8)

    def post_connection(self):
        return _SuccessfulJob()

    def post_screencap(self):
        return _SuccessfulJob(self.screenshot)


CONTROLLER_CONFIG = {
    "expected_raw_resolution": [1920, 1080],
    "expected_screenshot_resolution": [1280, 720],
}


class Win32ControllerConfigTests(unittest.TestCase):
    def test_background_screencap_methods_are_combined(self) -> None:
        self.assertEqual(combine_screencap_methods(["FramePool", "PrintWindow"]), 18)

    def test_post_message_input_is_parsed(self) -> None:
        self.assertEqual(parse_input_method("PostMessage"), 4)

    def test_unknown_screencap_method_is_rejected(self) -> None:
        with self.assertRaises(ControllerConnectionError):
            combine_screencap_methods(["Unknown"])

    def test_matching_resolution_passes_startup_check(self) -> None:
        connect_controller(_FakeController(), CONTROLLER_CONFIG)

    def test_raw_resolution_mismatch_is_rejected_before_input(self) -> None:
        controller = _FakeController(raw_resolution=(2560, 1440))
        with self.assertRaisesRegex(ControllerConnectionError, "Raw resolution"):
            connect_controller(controller, CONTROLLER_CONFIG)

    def test_screenshot_resolution_mismatch_is_rejected_before_input(self) -> None:
        controller = _FakeController(screenshot_resolution=(1280, 800))
        with self.assertRaisesRegex(ControllerConnectionError, "Screenshot resolution"):
            connect_controller(controller, CONTROLLER_CONFIG)
