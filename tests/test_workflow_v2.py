import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from PIL import Image

from nzm_auto.workflow.actions import WorkflowActionError, execute_action
from nzm_auto.workflow.context import CancellationToken, ExecutionContext
from nzm_auto.workflow.engine import WorkflowEngine, WorkflowExecutionError
from nzm_auto.workflow.events import WorkflowEventType
from nzm_auto.workflow.loader import WorkflowV2ConfigError, load_workflow_v2
from nzm_auto.workflow.model import (
    KeyPressStep,
    MouseClickStep,
    MouseMoveStep,
    TextInputStep,
    WaitStep,
    WorkflowDefinition,
    WorkflowSettings,
)
from nzm_auto.workflow.virtual_keys import resolve_text_character, resolve_virtual_key


class _Job:
    def __init__(self, succeeded: bool = True) -> None:
        self.succeeded = succeeded

    def wait(self):
        return self


class _Controller:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.fail_click = False

    def post_touch_move(self, x: int, y: int):
        self.calls.append(("move", x, y))
        return _Job()

    def post_click(self, x: int, y: int, contact: int = 0):
        self.calls.append(("click", x, y, contact))
        return _Job(not self.fail_click)

    def post_key_down(self, key: int):
        self.calls.append(("key_down", key))
        return _Job()

    def post_click_key(self, key: int):
        self.calls.append(("key", key))
        return _Job()

    def post_key_up(self, key: int):
        self.calls.append(("key_up", key))
        return _Job()

    def post_input_text(self, text: str):
        self.calls.append(("text", text))
        return _Job()


class _Session:
    def __init__(self) -> None:
        self.controller = _Controller()

    def initialize_runtime(self):
        raise AssertionError("Runtime should not be initialized for input-only tests.")


def _context() -> tuple[_Session, ExecutionContext]:
    session = _Session()
    return session, ExecutionContext(session=session, cancellation=CancellationToken())


class WorkflowV2LoaderTests(unittest.TestCase):
    def test_complete_input_workflow_is_loaded(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template.png"
            Image.new("RGB", (4, 4)).save(template)
            data = {
                "version": 2,
                "name": "GUI workflow",
                "target": {"title_pattern": "逆战：未来", "class_name": "CabinetWClass"},
                "settings": {"stop_on_error": True, "default_timeout_ms": 5000},
                "steps": [
                    {
                        "id": "find",
                        "type": "template_match",
                        "name": "Find document",
                        "template": "template.png",
                        "result_variable": "document",
                    },
                    {
                        "id": "click",
                        "type": "mouse_click",
                        "name": "Open document",
                        "match_variable": "document",
                        "count": 2,
                    },
                    {
                        "id": "type",
                        "type": "text_input",
                        "name": "Type text",
                        "text": "NZM automation test",
                    },
                ],
            }
            path = root / "workflow.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

            definition = load_workflow_v2(path, root)

            self.assertEqual(definition.name, "GUI workflow")
            self.assertEqual(definition.target.title_pattern, "逆战：未来")
            self.assertEqual(len(definition.steps), 3)
            self.assertEqual(definition.steps[0].template_path, template.resolve())
            self.assertEqual(definition.steps[1].match_variable, "document")

    def test_click_requires_coordinates_or_match(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "workflow.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "name": "invalid",
                        "steps": [
                            {
                                "id": "click",
                                "type": "mouse_click",
                                "name": "click",
                                "x": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(WorkflowV2ConfigError):
                load_workflow_v2(path, root)


class WorkflowV2ActionTests(unittest.TestCase):
    def test_mouse_and_keyboard_actions_use_maa_controller(self) -> None:
        session, context = _context()
        steps = (
            MouseMoveStep(id="move", name="Move", x=10, y=20),
            MouseClickStep(
                id="right-click",
                name="Right click",
                x=30,
                y=40,
                button="right",
            ),
            KeyPressStep(id="shortcut", name="Select all", key="A", modifiers=("CTRL",)),
            TextInputStep(id="text", name="Type", text="hello", strategy="direct"),
        )

        for step in steps:
            execute_action(step, context)

        self.assertEqual(
            session.controller.calls,
            [
                ("move", 10, 20),
                ("click", 30, 40, 1),
                ("key_down", 0x11),
                ("key", ord("A")),
                ("key_up", 0x11),
                ("text", "hello"),
            ],
        )

    def test_failed_controller_job_is_not_treated_as_success(self) -> None:
        session, context = _context()
        session.controller.fail_click = True

        with self.assertRaises(WorkflowActionError):
            execute_action(
                MouseClickStep(id="click", name="Click", x=1, y=2),
                context,
            )

    def test_virtual_key_names_and_codes_are_validated(self) -> None:
        self.assertEqual(resolve_virtual_key("enter"), 0x0D)
        self.assertEqual(resolve_virtual_key("F12"), 0x7B)
        self.assertEqual(resolve_virtual_key(0x41), 0x41)
        with self.assertRaises(ValueError):
            resolve_virtual_key("not-a-key")

    def test_key_sequence_resolves_case_and_punctuation(self) -> None:
        self.assertEqual(resolve_text_character("a"), (ord("A"), False))
        self.assertEqual(resolve_text_character("A"), (ord("A"), True))
        self.assertEqual(resolve_text_character("!"), (ord("1"), True))
        with self.assertRaises(ValueError):
            resolve_text_character("中")

    def test_key_sequence_text_uses_shift_and_character_delay(self) -> None:
        session, context = _context()

        execute_action(
            TextInputStep(
                id="text",
                name="Type",
                text="A!",
                strategy="key_sequence",
                interval_ms=0,
            ),
            context,
        )

        self.assertEqual(
            session.controller.calls,
            [
                ("key_down", 0x10),
                ("key_down", ord("A")),
                ("key_up", ord("A")),
                ("key_up", 0x10),
                ("key_down", 0x10),
                ("key_down", ord("1")),
                ("key_up", ord("1")),
                ("key_up", 0x10),
            ],
        )


class WorkflowV2EngineTests(unittest.TestCase):
    def test_engine_emits_events_and_runs_steps_in_order(self) -> None:
        session = _Session()
        events = []
        definition = WorkflowDefinition(
            name="input",
            steps=(
                MouseMoveStep(id="move", name="Move", x=1, y=2),
                TextInputStep(id="text", name="Text", text="abc"),
            ),
        )

        result = WorkflowEngine(events.append).run(definition, session)

        self.assertFalse(result.cancelled)
        self.assertEqual([item.step_id for item in result.steps], ["move", "text"])
        self.assertEqual(events[0].type, WorkflowEventType.WORKFLOW_STARTED)
        self.assertEqual(events[-1].type, WorkflowEventType.WORKFLOW_SUCCEEDED)

    def test_cancelled_wait_stops_without_later_input(self) -> None:
        session = _Session()
        token = CancellationToken()
        token.cancel()
        definition = WorkflowDefinition(
            name="cancel",
            steps=(
                WaitStep(id="wait", name="Wait", duration_ms=1000),
                TextInputStep(id="text", name="Text", text="must-not-run"),
            ),
        )

        result = WorkflowEngine().run(definition, session, token)

        self.assertTrue(result.cancelled)
        self.assertEqual(session.controller.calls, [])

    def test_stop_policy_raises_after_action_failure(self) -> None:
        session = _Session()
        session.controller.fail_click = True
        definition = WorkflowDefinition(
            name="failure",
            settings=WorkflowSettings(stop_on_error=True),
            steps=(MouseClickStep(id="click", name="Click", x=1, y=2),),
        )

        with self.assertRaises(WorkflowExecutionError):
            WorkflowEngine().run(definition, session)


if __name__ == "__main__":
    unittest.main()
