"""Command-line entry points for the framework."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nzm_auto.config.loader import load_config
from nzm_auto.runtime.maa_runtime import get_maa_version
from nzm_auto.windowing.discovery import find_windows


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nzm-auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    self_test = subparsers.add_parser(
        "self-test", help="Validate the framework files and default configuration."
    )
    self_test.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to a JSON config file."
    )

    subparsers.add_parser(
        "maa-version", help="Load MaaFramework and print its native runtime version."
    )

    windows = subparsers.add_parser("windows", help="Read-only desktop window tools.")
    window_commands = windows.add_subparsers(dest="windows_command", required=True)
    window_list = window_commands.add_parser("list", help="List desktop windows.")
    window_list.add_argument("--title", help="Case-insensitive title substring filter.")
    window_list.add_argument(
        "--class-name", help="Case-insensitive window class substring filter."
    )
    window_list.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser


def run_window_list(
    title_filter: str | None,
    class_filter: str | None,
    as_json: bool,
) -> int:
    windows = find_windows(title_filter=title_filter, class_filter=class_filter)
    if as_json:
        print(json.dumps([window.to_dict() for window in windows], ensure_ascii=False, indent=2))
        return 0

    print("INDEX\tHWND\tVISIBLE\tMINIMIZED\tWINDOW\tCLIENT\tCLASS\tTITLE")
    for index, window in enumerate(windows):
        window_size = f"{window.window_width}x{window.window_height}"
        client_size = f"{window.client_width}x{window.client_height}"
        print(
            f"{index}\t0x{window.hwnd:X}\t{window.visible}\t{window.minimized}"
            f"\t{window_size}\t{client_size}\t{window.class_name}\t{window.title}"
        )
    print(f"Total: {len(windows)}")
    print("Read-only enumeration completed. No controller was created and no input was sent.")
    return 0


def run_self_test(config_path: Path) -> int:
    config = load_config(config_path)
    required_directories = (
        PROJECT_ROOT / "assets" / "resource" / "pipeline",
        PROJECT_ROOT / "assets" / "resource" / "image",
        PROJECT_ROOT / "logs",
        PROJECT_ROOT / "screenshots",
    )
    missing = [path for path in required_directories if not path.is_dir()]
    if missing:
        for path in missing:
            print(f"Missing required directory: {path}")
        return 1

    print("Framework self-test passed.")
    print(f"Configuration: {config_path.resolve()}")
    print(f"Capture preference: {config['controller']['screencap_mode']}")
    print(f"MaaFramework: {get_maa_version()}")
    print("No window was searched and no input was sent.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        return run_self_test(args.config)
    if args.command == "maa-version":
        print(get_maa_version())
        return 0
    if args.command == "windows" and args.windows_command == "list":
        return run_window_list(args.title, args.class_name, args.json)
    return 1
