import json
from pathlib import Path
import unittest


class FrameworkPipelineTests(unittest.TestCase):
    def test_self_test_pipeline_has_no_input_action(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        pipeline_path = project_root / "assets" / "resource" / "pipeline" / "framework.json"
        with pipeline_path.open(encoding="utf-8") as file:
            pipeline = json.load(file)

        node = pipeline["FrameworkSelfTest"]
        self.assertEqual(node["recognition"], "DirectHit")
        self.assertEqual(node["action"], "DoNothing")
