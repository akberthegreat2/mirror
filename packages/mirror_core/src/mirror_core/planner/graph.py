"""Pure graph and binding-traversal helpers used by the pipeline planner."""

from __future__ import annotations

from collections import deque
from typing import Any

from mirror_core.exceptions import PlannerError
from mirror_core.pipeline import Pipeline


def iter_binding_sources(value: Any) -> Any:
    """Yield every string leaf in a binding value, recursing into literals."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_binding_sources(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_binding_sources(item)


def binding_source_step(source: Any, steps_by_id: dict[str, Any]) -> str | None:
    """Return the referenced step for a binding, or None when it is a literal.

    Only ``$pipeline.<key>`` references and ``<known-step>.<output>``
    bindings are treated as references. Dotted strings whose leading
    segment is not a plan step (for example model import paths) are
    literals.
    """
    if not isinstance(source, str):
        return None
    if source.startswith("$pipeline."):
        return "$pipeline"
    if "." in source:
        step, _ = source.split(".", 1)
        if step in steps_by_id:
            return step
    return None


def build_dependency_graph(pipeline: Pipeline) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    steps_by_id = {step.id: step for step in pipeline.steps}
    dependencies: dict[str, set[str]] = {step.id: set() for step in pipeline.steps}
    reverse: dict[str, set[str]] = {step.id: set() for step in pipeline.steps}
    for step in pipeline.steps:
        for source in step.input.values():
            for binding in iter_binding_sources(source):
                source_step = binding_source_step(binding, steps_by_id)
                if source_step is None or source_step == "$pipeline":
                    continue
                dependencies[step.id].add(source_step)
                reverse[source_step].add(step.id)
    return dependencies, reverse


def topological_sort(
    pipeline: Pipeline,
    dependencies: dict[str, set[str]],
    reverse_dependencies: dict[str, set[str]],
) -> list[str]:
    in_degree = {step.id: len(dependencies[step.id]) for step in pipeline.steps}
    queue = deque(step.id for step in pipeline.steps if in_degree[step.id] == 0)
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for dependent in sorted(reverse_dependencies[node]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
    if len(order) != len(in_degree):
        raise PlannerError("Cycle detected in pipeline graph")
    return order


def compute_parallel_groups(dependencies: dict[str, set[str]], order: list[str]) -> list[list[str]]:
    level: dict[str, int] = {}
    for step_id in order:
        level[step_id] = 0 if not dependencies[step_id] else 1 + max(level[dependency] for dependency in dependencies[step_id])
    groups: dict[int, list[str]] = {}
    for step_id in order:
        groups.setdefault(level[step_id], []).append(step_id)
    return [groups[index] for index in sorted(groups)]
