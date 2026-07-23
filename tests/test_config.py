from pathlib import Path
import json
import tempfile
import unittest

from nzm_auto.config.loader import load_config


class DefaultConfigTests(unittest.TestCase):
    def test_default_config_loads(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        config = load_config(project_root / "config" / "default.json")

        self.assertEqual(config["runtime"]["task_entry"], "FrameworkSelfTest")
        self.assertEqual(config["runtime"]["task_timeout_seconds"], 60)
        self.assertEqual(config["controller"]["expected_raw_resolution"], [1920, 1080])
        self.assertEqual(config["controller"]["expected_screenshot_resolution"], [1280, 720])

    def test_non_positive_task_timeout_is_rejected(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        default_path = project_root / "config" / "default.json"
        config = json.loads(default_path.read_text(encoding="utf-8"))
        config["runtime"]["task_timeout_seconds"] = 0

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "task_timeout_seconds"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
