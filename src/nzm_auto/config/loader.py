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

    title_pattern = config["window"].get("title_pattern")
    if not isinstance(title_pattern, str):
        raise ValueError("window.title_pattern must be a string.")

    class_name = config["window"].get("class_name")
    if class_name is not None and not isinstance(class_name, str):
        raise ValueError("window.class_name must be a string or null.")

    resolution = config["window"].get("client_resolution")
    if not (
        isinstance(resolution, list)
        and len(resolution) == 2
        and all(isinstance(value, int) and value > 0 for value in resolution)
    ):
        raise ValueError("window.client_resolution must be two positive integers.")

    debug_dir = config["diagnostics"].get("debug_dir")
    if not isinstance(debug_dir, str) or not debug_dir.strip():
        raise ValueError("diagnostics.debug_dir must be a non-empty string.")

    resource_path = config["runtime"].get("resource_path")
    if not isinstance(resource_path, str) or not resource_path.strip():
        raise ValueError("runtime.resource_path must be a non-empty string.")

    task_entry = config["runtime"].get("task_entry")
    if not isinstance(task_entry, str) or not task_entry.strip():
        raise ValueError("runtime.task_entry must be a non-empty string.")

    return config
