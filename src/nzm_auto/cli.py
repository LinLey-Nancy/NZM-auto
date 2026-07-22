"""Command-line entry points for the framework."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

from nzm_auto.config.loader import load_config
from nzm_auto.diagnostics.screenshot import ScreenshotError, capture_image, capture_screenshot
from nzm_auto.diagnostics.template_match import (
    TemplateMatchDiagnosticError,
    run_template_match,
)
from nzm_auto.diagnostics.workspace import create_debug_workspace, configure_file_logging
from nzm_auto.runtime.maa_runtime import get_maa_version
from nzm_auto.runtime.task_runtime import TaskRuntimeError, load_task_runtime, run_task
from nzm_auto.runtime.win32_controller import (
    ControllerConnectionError,
    connect_controller,
    create_controller,
    deactivate_controller,
)
from nzm_auto.windowing.discovery import find_windows
from nzm_auto.windowing.selector import (
    WindowSelectionError,
    choose_window_by_index,
    select_target_window,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.json"


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def single_line(value: str) -> str:
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ")


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

    run = subparsers.add_parser(
        "run", help="Choose a window and verify the Maa Win32 controller connection."
    )
    run.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to a JSON config file."
    )
    run.add_argument("--title", help="Optional title substring filter.")
    run.add_argument("--class-name", help="Optional window class substring filter.")
    run.add_argument(
        "--visible-only", action="store_true", help="Only show currently visible windows."
    )
    run.add_argument("--index", type=int, help="Choose an index without an interactive prompt.")

    capture = subparsers.add_parser(
        "capture", help="Choose a window, connect, and save one debug screenshot."
    )
    capture.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to a JSON config file."
    )
    capture.add_argument("--title", help="Optional title substring filter.")
    capture.add_argument("--class-name", help="Optional window class substring filter.")
    capture.add_argument(
        "--visible-only", action="store_true", help="Only show currently visible windows."
    )
    capture.add_argument(
        "--index", type=int, help="Choose an index without an interactive prompt."
    )

    template_match = subparsers.add_parser(
        "template-match", help="Crop a temporary template and run Maa TemplateMatch."
    )
    template_match.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to a JSON config file."
    )
    template_match.add_argument("--title", help="Optional title substring filter.")
    template_match.add_argument("--class-name", help="Optional window class substring filter.")
    template_match.add_argument(
        "--visible-only", action="store_true", help="Only show currently visible windows."
    )
    template_match.add_argument(
        "--index", type=int, help="Choose an index without an interactive prompt."
    )
    template_match.add_argument(
        "--template-roi",
        nargs=4,
        type=int,
        metavar=("X", "Y", "WIDTH", "HEIGHT"),
        required=True,
        help="Crop rectangle in Maa screenshot coordinates.",
    )
    template_match.add_argument(
        "--threshold", type=float, default=0.8, help="TemplateMatch threshold, default 0.8."
    )

    windows = subparsers.add_parser("windows", help="Read-only desktop window tools.")
    window_commands = windows.add_subparsers(dest="windows_command", required=True)
    window_list = window_commands.add_parser("list", help="List desktop windows.")
    window_list.add_argument("--title", help="Case-insensitive title substring filter.")
    window_list.add_argument(
        "--class-name", help="Case-insensitive window class substring filter."
    )
    window_list.add_argument("--json", action="store_true", help="Print JSON output.")
    window_select = window_commands.add_parser(
        "select", help="Select exactly one target window using configuration."
    )
    window_select.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to a JSON config file."
    )
    window_select.add_argument("--json", action="store_true", help="Print JSON output.")
    window_choose = window_commands.add_parser(
        "choose", help="List candidate windows and choose one by index."
    )
    window_choose.add_argument("--title", help="Optional title substring filter.")
    window_choose.add_argument("--class-name", help="Optional window class substring filter.")
    window_choose.add_argument(
        "--visible-only", action="store_true", help="Only show currently visible windows."
    )
    window_choose.add_argument(
        "--index", type=int, help="Choose this index without an interactive prompt."
    )
    window_choose.add_argument("--json", action="store_true", help="Print selection as JSON.")
    return parser


def print_window_table(windows: list) -> None:
    print("INDEX\tHWND\tVISIBLE\tMINIMIZED\tWINDOW\tCLIENT\tCLASS\tTITLE")
    for index, window in enumerate(windows):
        window_size = f"{window.window_width}x{window.window_height}"
        client_size = f"{window.client_width}x{window.client_height}"
        print(
            f"{index}\t0x{window.hwnd:X}\t{window.visible}\t{window.minimized}"
            f"\t{window_size}\t{client_size}\t{single_line(window.class_name)}"
            f"\t{single_line(window.title)}"
        )
    print(f"Total: {len(windows)}")


def run_window_list(
    title_filter: str | None,
    class_filter: str | None,
    as_json: bool,
) -> int:
    windows = find_windows(title_filter=title_filter, class_filter=class_filter)
    if as_json:
        print(json.dumps([window.to_dict() for window in windows], ensure_ascii=False, indent=2))
        return 0

    print_window_table(windows)
    print("Read-only enumeration completed. No controller was created and no input was sent.")
    return 0


def run_window_choose(
    title_filter: str | None,
    class_filter: str | None,
    visible_only: bool,
    selected_index: int | None,
    as_json: bool,
) -> int:
    windows = find_windows(title_filter=title_filter, class_filter=class_filter)
    if visible_only:
        windows = [window for window in windows if window.visible]

    if not windows:
        print("Window selection failed: no candidate windows are available.", file=sys.stderr)
        return 2

    if not as_json or selected_index is None:
        print_window_table(windows)

    if selected_index is None:
        print("Choose window index: ", end="", file=sys.stderr, flush=True)
        value = sys.stdin.readline().strip()
        try:
            selected_index = int(value)
        except ValueError:
            print(f"Window selection failed: {value!r} is not an integer index.", file=sys.stderr)
            return 2

    try:
        window = choose_window_by_index(windows, selected_index)
    except WindowSelectionError as error:
        print(f"Window selection failed: {error}", file=sys.stderr)
        return 2

    if as_json:
        print(json.dumps(window.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Selected: 0x{window.hwnd:X} {window.class_name} {window.title}")
        print("Selection was read-only. No controller was created and no input was sent.")
    return 0


def choose_window_for_run(
    title_filter: str | None,
    class_filter: str | None,
    visible_only: bool,
    selected_index: int | None,
):
    windows = find_windows(title_filter=title_filter, class_filter=class_filter)
    if visible_only:
        windows = [window for window in windows if window.visible]
    if not windows:
        raise WindowSelectionError("No candidate windows are available.")

    print_window_table(windows)
    if selected_index is None:
        print("Choose window index: ", end="", file=sys.stderr, flush=True)
        value = sys.stdin.readline().strip()
        try:
            selected_index = int(value)
        except ValueError as error:
            raise WindowSelectionError(f"{value!r} is not an integer index.") from error
    return choose_window_by_index(windows, selected_index)


def run_program(
    config_path: Path,
    title_filter: str | None,
    class_filter: str | None,
    visible_only: bool,
    selected_index: int | None,
    capture_requested: bool = False,
) -> int:
    config = load_config(config_path)
    workspace = create_debug_workspace(
        PROJECT_ROOT,
        config["diagnostics"]["debug_dir"],
    )
    log_path = configure_file_logging(workspace)
    logger = logging.getLogger(__name__)
    logger.info("Program start; capture_requested=%s", capture_requested)
    print(f"Debug log: {log_path}")
    print(f"MaaFramework: {get_maa_version()}")

    try:
        window = choose_window_for_run(
            title_filter,
            class_filter,
            visible_only,
            selected_index,
        )
    except WindowSelectionError as error:
        print(f"Window selection failed: {error}", file=sys.stderr)
        return 2

    print(f"Selected: 0x{window.hwnd:X} {window.class_name} {window.title}")
    logger.info(
        "Selected window hwnd=0x%X class=%r title=%r",
        window.hwnd,
        window.class_name,
        window.title,
    )
    controller = None
    task_runtime = None
    exit_code = 0
    try:
        controller = create_controller(window, config["controller"])
        connect_controller(controller)
        print("Win32 controller connected successfully.")
        logger.info("Win32 controller connected")
        if capture_requested:
            screenshot_path = workspace.timestamped_path(
                workspace.screenshots,
                "window",
                ".png",
            )
            result = capture_screenshot(controller, screenshot_path)
            print(f"Screenshot: {result.path}")
            print(f"Screenshot size: {result.width}x{result.height}x{result.channels}")
            logger.info(
                "Screenshot saved path=%s size=%sx%s channels=%s",
                result.path,
                result.width,
                result.height,
                result.channels,
            )
        else:
            resource_path = Path(config["runtime"]["resource_path"])
            if not resource_path.is_absolute():
                resource_path = PROJECT_ROOT / resource_path
            task_runtime = load_task_runtime(
                controller,
                resource_path.resolve(),
                workspace.logs / "maa",
            )
            print(f"Resource bundle loaded: {resource_path.resolve()}")
            print("Tasker initialized successfully.")
            task_entry = config["runtime"]["task_entry"]
            run_task(task_runtime, task_entry)
            print(f"Pipeline task succeeded: {task_entry}")
            print("The self-test task performed no click or keyboard input.")
            logger.info("Pipeline task succeeded entry=%s", task_entry)
    except ControllerConnectionError as error:
        print(f"Controller connection failed: {error}", file=sys.stderr)
        logger.exception("Controller connection failed")
        exit_code = 3
    except ScreenshotError as error:
        print(f"Screenshot failed: {error}", file=sys.stderr)
        logger.exception("Screenshot failed")
        exit_code = 5
    except TaskRuntimeError as error:
        print(f"Task runtime failed: {error}", file=sys.stderr)
        logger.exception("Task runtime failed")
        exit_code = 6
    finally:
        if controller is not None:
            try:
                deactivate_controller(controller)
                print("Win32 controller deactivated successfully.")
                logger.info("Win32 controller deactivated")
            except ControllerConnectionError as error:
                print(f"Controller cleanup failed: {error}", file=sys.stderr)
                logger.exception("Controller cleanup failed")
                exit_code = 4
    return exit_code


def run_template_match_program(args) -> int:
    config = load_config(args.config)
    workspace = create_debug_workspace(PROJECT_ROOT, config["diagnostics"]["debug_dir"])
    log_path = configure_file_logging(workspace)
    logger = logging.getLogger(__name__)
    print(f"Debug log: {log_path}")
    print(f"MaaFramework: {get_maa_version()}")

    try:
        window = choose_window_for_run(
            args.title,
            args.class_name,
            args.visible_only,
            args.index,
        )
    except WindowSelectionError as error:
        print(f"Window selection failed: {error}", file=sys.stderr)
        return 2

    print(f"Selected: 0x{window.hwnd:X} {window.class_name} {window.title}")
    controller = None
    exit_code = 0
    try:
        controller = create_controller(window, config["controller"])
        connect_controller(controller)
        resource_path = Path(config["runtime"]["resource_path"])
        if not resource_path.is_absolute():
            resource_path = PROJECT_ROOT / resource_path
        runtime = load_task_runtime(controller, resource_path.resolve(), workspace.logs / "maa")
        image = capture_image(controller)

        template_path = workspace.timestamped_path(workspace.templates, "template", ".png")
        annotated_path = workspace.timestamped_path(
            workspace.screenshots, "template-match", ".png"
        )
        report_path = workspace.timestamped_path(workspace.reports, "template-match", ".json")
        result = run_template_match(
            runtime,
            image,
            tuple(args.template_roi),
            args.threshold,
            template_path,
            annotated_path,
            report_path,
        )
        print(f"TemplateMatch hit: {result.hit}")
        print(f"Score: {result.score}")
        print(f"Box: {result.box}")
        print(f"Template: {result.template_path}")
        print(f"Annotated image: {result.annotated_path}")
        print(f"Report: {result.report_path}")
        logger.info("TemplateMatch result hit=%s score=%s box=%s", result.hit, result.score, result.box)
        if not result.hit:
            exit_code = 7
    except (ControllerConnectionError, TaskRuntimeError, ScreenshotError, TemplateMatchDiagnosticError) as error:
        print(f"TemplateMatch diagnostic failed: {error}", file=sys.stderr)
        logger.exception("TemplateMatch diagnostic failed")
        exit_code = 7
    finally:
        if controller is not None:
            try:
                deactivate_controller(controller)
                print("Win32 controller deactivated successfully.")
            except ControllerConnectionError as error:
                print(f"Controller cleanup failed: {error}", file=sys.stderr)
                exit_code = 4
    return exit_code


def run_window_select(config_path: Path, as_json: bool) -> int:
    config = load_config(config_path)
    window_config = config["window"]
    try:
        window = select_target_window(
            title_filter=window_config["title_pattern"],
            class_filter=window_config["class_name"],
        )
    except WindowSelectionError as error:
        print(f"Window selection failed: {error}", file=sys.stderr)
        return 2

    if as_json:
        print(json.dumps(window.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Selected HWND: 0x{window.hwnd:X}")
        print(f"Title: {window.title}")
        print(f"Class: {window.class_name}")
        print(f"Window size: {window.window_width}x{window.window_height}")
        print(f"Client size: {window.client_width}x{window.client_height}")
        print(f"Visible: {window.visible}")
        print(f"Minimized: {window.minimized}")
        print("Selection was read-only. No controller was created and no input was sent.")
    return 0


def run_self_test(config_path: Path) -> int:
    config = load_config(config_path)
    required_directories = (
        PROJECT_ROOT / "assets" / "resource" / "pipeline",
        PROJECT_ROOT / "assets" / "resource" / "image",
    )
    missing = [path for path in required_directories if not path.is_dir()]
    if missing:
        for path in missing:
            print(f"Missing required directory: {path}")
        return 1

    workspace = create_debug_workspace(PROJECT_ROOT, config["diagnostics"]["debug_dir"])

    print("Framework self-test passed.")
    print(f"Configuration: {config_path.resolve()}")
    print(f"Capture preference: {config['controller']['screencap_mode']}")
    print(f"MaaFramework: {get_maa_version()}")
    print(f"Debug workspace: {workspace.root}")
    print("No window was searched and no input was sent.")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        return run_self_test(args.config)
    if args.command == "maa-version":
        print(get_maa_version())
        return 0
    if args.command == "run":
        return run_program(
            args.config,
            args.title,
            args.class_name,
            args.visible_only,
            args.index,
        )
    if args.command == "capture":
        return run_program(
            args.config,
            args.title,
            args.class_name,
            args.visible_only,
            args.index,
            capture_requested=True,
        )
    if args.command == "template-match":
        return run_template_match_program(args)
    if args.command == "windows" and args.windows_command == "list":
        return run_window_list(args.title, args.class_name, args.json)
    if args.command == "windows" and args.windows_command == "select":
        return run_window_select(args.config, args.json)
    if args.command == "windows" and args.windows_command == "choose":
        return run_window_choose(
            args.title,
            args.class_name,
            args.visible_only,
            args.index,
            args.json,
        )
    return 1
