"""Load and validate framework configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL_KEYS = {"window", "controller", "runtime", "diagnostics"}


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file does not exist: {path}")

    with path.open(encoding="utf-8") as file:
        config: dict[str, Any] = json.load(file)

    missing_keys = REQUIRED_TOP_LEVEL_KEYS.difference(config)
    if missing_keys:
        names = ", ".join(sorted(missing_keys))
        raise ValueError(f"Configuration is missing required sections: {names}")

    resolution = config["window"].get("client_resolution")
    if not (
        isinstance(resolution, list)
        and len(resolution) == 2
        and all(isinstance(value, int) and value > 0 for value in resolution)
    ):
        raise ValueError("window.client_resolution must be two positive integers.")

    return config
