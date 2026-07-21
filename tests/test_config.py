from pathlib import Path
import unittest

from nzm_auto.config.loader import load_config


class DefaultConfigTests(unittest.TestCase):
    def test_default_config_loads(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        config = load_config(project_root / "config" / "default.json")

        self.assertEqual(config["runtime"]["task_entry"], "FrameworkSelfTest")


if __name__ == "__main__":
    unittest.main()
