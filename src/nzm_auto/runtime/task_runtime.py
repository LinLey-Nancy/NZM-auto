"""Load a Maa resource bundle and run the minimal framework task."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from maa.controller import Win32Controller
from maa.resource import Resource
from maa.tasker import Tasker


class TaskRuntimeError(RuntimeError):
    """Raised when Maa resources or tasks fail."""


@dataclass(slots=True)
class TaskRuntime:
    resource: Resource
    tasker: Tasker


def load_task_runtime(
    controller: Win32Controller,
    resource_path: Path,
    maa_log_dir: Path,
) -> TaskRuntime:
    maa_log_dir.mkdir(parents=True, exist_ok=True)
    if not Tasker.set_log_dir(maa_log_dir):
        raise TaskRuntimeError(f"Failed to set MaaFramework log directory: {maa_log_dir}")

    resource = Resource()
    load_job = resource.post_bundle(resource_path).wait()
    if not load_job.succeeded or not resource.loaded:
        raise TaskRuntimeError(f"Failed to load Maa resource bundle: {resource_path}")

    tasker = Tasker()
    if not tasker.bind(resource, controller) or not tasker.inited:
        raise TaskRuntimeError("Failed to bind Maa resource and controller to Tasker.")
    return TaskRuntime(resource=resource, tasker=tasker)


def run_task(runtime: TaskRuntime, entry: str) -> None:
    task_job = runtime.tasker.post_task(entry).wait()
    if not task_job.succeeded:
        raise TaskRuntimeError(f"Maa task failed: {entry}")
