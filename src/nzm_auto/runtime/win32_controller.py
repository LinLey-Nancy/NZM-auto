"""Create and connect a MaaFramework Win32 controller."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from maa.controller import Win32Controller
from maa.define import MaaWin32InputMethodEnum, MaaWin32ScreencapMethodEnum

from nzm_auto.windowing.discovery import WindowInfo


class ControllerConnectionError(RuntimeError):
    """Raised when a Win32 controller cannot be configured or connected."""


def combine_screencap_methods(method_names: Sequence[str]) -> int:
    if not method_names:
        raise ControllerConnectionError("At least one screenshot method must be configured.")

    combined = 0
    for method_name in method_names:
        try:
            combined |= int(MaaWin32ScreencapMethodEnum[method_name])
        except KeyError as error:
            raise ControllerConnectionError(
                f"Unknown Win32 screenshot method: {method_name!r}."
            ) from error
    return combined


def parse_input_method(method_name: str) -> int:
    try:
        return int(MaaWin32InputMethodEnum[method_name])
    except KeyError as error:
        raise ControllerConnectionError(
            f"Unknown Win32 input method: {method_name!r}."
        ) from error


def create_controller(window: WindowInfo, controller_config: dict[str, Any]) -> Win32Controller:
    screencap_methods = (
        controller_config["background_screencap"]
        if controller_config["screencap_mode"] == "background"
        else controller_config["foreground_screencap"]
    )
    return Win32Controller(
        window.hwnd,
        combine_screencap_methods(screencap_methods),
        parse_input_method(controller_config["mouse_input"]),
        parse_input_method(controller_config["keyboard_input"]),
    )


def connect_controller(controller: Win32Controller) -> None:
    job = controller.post_connection().wait()
    if not job.succeeded or not controller.connected:
        raise ControllerConnectionError("MaaFramework failed to connect the Win32 controller.")


def deactivate_controller(controller: Win32Controller) -> None:
    job = controller.post_inactive().wait()
    if not job.succeeded:
        raise ControllerConnectionError("MaaFramework failed to deactivate the Win32 controller.")
