"""Execute individual workflow v2 steps against MaaFramework."""

from __future__ import annotations

from dataclasses import dataclass

from nzm_auto.automation.template_action import box_center, load_template_image
from nzm_auto.diagnostics.screenshot import capture_image
from nzm_auto.diagnostics.template_match import MatchBox, recognize_template
from nzm_auto.workflow.context import ExecutionContext
from nzm_auto.workflow.model import (
    KeyPressStep,
    MouseClickStep,
    MouseMoveStep,
    TemplateMatchStep,
    TextInputStep,
    WaitStep,
    WorkflowStep,
)
from nzm_auto.workflow.virtual_keys import resolve_text_character, resolve_virtual_key


class WorkflowActionError(RuntimeError):
    """Raised when one workflow action fails."""


@dataclass(frozen=True, slots=True)
class ActionResult:
    output: object | None = None


def _successful(job, description: str) -> None:
    completed = job.wait()
    if not completed.succeeded:
        raise WorkflowActionError(f"MaaFramework action failed: {description}.")


def _match_point(context: ExecutionContext, variable: str) -> tuple[int, int]:
    value = context.variables.get(variable)
    if not isinstance(value, MatchBox):
        raise WorkflowActionError(
            f"Match variable {variable!r} is missing or does not contain a match box."
        )
    return box_center(value)


def _run_template_match(
    step: TemplateMatchStep,
    context: ExecutionContext,
) -> ActionResult:
    runtime = context.session.initialize_runtime()
    template = load_template_image(step.template_path)
    for attempt in range(1, step.attempts + 1):
        context.cancellation.check()
        recognition = recognize_template(
            runtime,
            capture_image(context.session.controller),
            template,
            step.threshold,
        )
        if recognition.hit and recognition.box is not None:
            context.variables[step.result_variable] = recognition.box
            return ActionResult(
                {
                    "attempt": attempt,
                    "score": recognition.score,
                    "box": recognition.box,
                    "variable": step.result_variable,
                }
            )
        if attempt < step.attempts:
            context.cancellation.wait(step.interval_ms / 1000.0)
    raise WorkflowActionError(
        f"Template was not found after {step.attempts} attempt(s): {step.template_path}."
    )


def _run_key_press(step: KeyPressStep, context: ExecutionContext) -> ActionResult:
    controller = context.session.controller
    key = resolve_virtual_key(step.key)
    modifiers = [resolve_virtual_key(value) for value in step.modifiers]
    pressed: list[int] = []
    primary_error: BaseException | None = None
    try:
        for modifier in modifiers:
            _successful(controller.post_key_down(modifier), f"key down {modifier}")
            pressed.append(modifier)
        _successful(controller.post_click_key(key), f"key press {key}")
    except BaseException as error:
        primary_error = error
        raise
    finally:
        for modifier in reversed(pressed):
            try:
                _successful(controller.post_key_up(modifier), f"key up {modifier}")
            except WorkflowActionError as cleanup_error:
                if primary_error is None:
                    raise
                primary_error.add_note(str(cleanup_error))
    return ActionResult({"keycode": key, "modifiers": modifiers})


def _run_text_input(step: TextInputStep, context: ExecutionContext) -> ActionResult:
    controller = context.session.controller
    if step.strategy == "direct":
        _successful(controller.post_input_text(step.text), "direct text input")
    else:
        for character in step.text:
            context.cancellation.check()
            try:
                key, shift_required = resolve_text_character(character)
            except ValueError as error:
                raise WorkflowActionError(str(error)) from error
            if shift_required:
                _successful(controller.post_key_down(0x10), "text shift down")
            try:
                _successful(controller.post_key_down(key), f"text character down {character!r}")
                _successful(controller.post_key_up(key), f"text character up {character!r}")
            finally:
                if shift_required:
                    _successful(controller.post_key_up(0x10), "text shift up")
            if step.interval_ms:
                context.cancellation.wait(step.interval_ms / 1000.0)
    return ActionResult(
        {
            "length": len(step.text),
            "strategy": step.strategy,
            "text": None if step.sensitive else step.text,
        }
    )


def execute_action(step: WorkflowStep, context: ExecutionContext) -> ActionResult:
    context.cancellation.check()
    controller = context.session.controller

    if isinstance(step, WaitStep):
        context.cancellation.wait(step.duration_ms / 1000.0)
        return ActionResult({"duration_ms": step.duration_ms})
    if isinstance(step, MouseMoveStep):
        _successful(controller.post_touch_move(step.x, step.y), f"mouse move to {(step.x, step.y)}")
        return ActionResult({"point": (step.x, step.y)})
    if isinstance(step, MouseClickStep):
        point = (
            _match_point(context, step.match_variable)
            if step.match_variable is not None
            else (step.x, step.y)
        )
        if point[0] is None or point[1] is None:
            raise WorkflowActionError("Mouse click point is incomplete.")
        contact = {"left": 0, "right": 1, "middle": 2}[step.button]
        for click_index in range(step.count):
            _successful(
                controller.post_click(int(point[0]), int(point[1]), contact=contact),
                f"{step.button} click at {point}",
            )
            if click_index + 1 < step.count:
                context.cancellation.wait(step.interval_ms / 1000.0)
        return ActionResult({"point": point, "button": step.button, "count": step.count})
    if isinstance(step, KeyPressStep):
        return _run_key_press(step, context)
    if isinstance(step, TextInputStep):
        return _run_text_input(step, context)
    if isinstance(step, TemplateMatchStep):
        return _run_template_match(step, context)
    raise WorkflowActionError(f"Unsupported workflow step: {type(step).__name__}.")
