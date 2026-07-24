"""Explicit Win32 input profiles and their compatibility trade-offs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class InputProfileName(StrEnum):
    BACKGROUND_MESSAGE = "background-message"
    FOREGROUND_COMPATIBLE = "foreground-compatible"
    DRIVER_INTERCEPTION = "driver-interception"


@dataclass(frozen=True, slots=True)
class InputProfile:
    name: InputProfileName
    mouse_method: str
    keyboard_method: str
    supports_background: bool
    requires_admin: bool
    requires_external_driver: bool
    compatibility: str
    warning: str


INPUT_PROFILES = {
    InputProfileName.BACKGROUND_MESSAGE: InputProfile(
        name=InputProfileName.BACKGROUND_MESSAGE,
        mouse_method="PostMessage",
        keyboard_method="PostMessage",
        supports_background=True,
        requires_admin=False,
        requires_external_driver=False,
        compatibility="medium",
        warning=(
            "Message delivery can report success even when a game ignores synthetic input; "
            "verify an observable application result."
        ),
    ),
    InputProfileName.FOREGROUND_COMPATIBLE: InputProfile(
        name=InputProfileName.FOREGROUND_COMPATIBLE,
        mouse_method="Seize",
        keyboard_method="Seize",
        supports_background=False,
        requires_admin=False,
        requires_external_driver=False,
        compatibility="high",
        warning=(
            "The target must be foreground and the physical mouse/keyboard may be occupied briefly."
        ),
    ),
    InputProfileName.DRIVER_INTERCEPTION: InputProfile(
        name=InputProfileName.DRIVER_INTERCEPTION,
        mouse_method="Interception",
        keyboard_method="Interception",
        supports_background=False,
        requires_admin=True,
        requires_external_driver=True,
        compatibility="medium",
        warning=(
            "Requires the Interception driver and administrator privileges; installation must be "
            "an explicit user action."
        ),
    ),
}


def get_input_profile(name: InputProfileName | str) -> InputProfile:
    try:
        return INPUT_PROFILES[InputProfileName(name)]
    except (KeyError, ValueError) as error:
        supported = ", ".join(profile.value for profile in InputProfileName)
        raise ValueError(f"Unknown input profile {name!r}; choose one of: {supported}.") from error
