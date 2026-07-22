"""Read-only Windows desktop discovery."""

from nzm_auto.windowing.discovery import WindowInfo, find_windows
from nzm_auto.windowing.selector import select_target_window

__all__ = ["WindowInfo", "find_windows", "select_target_window"]
