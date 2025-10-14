"""Lightweight task decomposition stub powered by AG2 (placeholder).

This module acts as a facade for an eventual AG2-powered decomposer. For the
PoC we provide a deterministic fallback that still returns the structured
payload expected by the dispatcher so the rest of the pipeline can be tested.
"""

from __future__ import annotations

import itertools
from typing import Iterable

from shared.schemas import CapabilityDeclaration, DecompositionResponse, SubTask, TaskObjective


class MasterDecomposer:
    """Placeholder decomposer that maps capabilities to basic subtasks."""

    def __init__(self) -> None:
        self._counter = itertools.count(1)

    async def decompose_task(
        self, payload: TaskObjective, capabilities: Iterable[CapabilityDeclaration]
    ) -> DecompositionResponse:
        """Produce a structured decomposition using available capabilities."""
        subtasks: list[SubTask] = []
        for capability in capabilities:
            for cap in capability.capabilities:
                sub_id = f"{payload.task_id}-S{next(self._counter)}"
                subtasks.append(
                    SubTask(
                        task_id=payload.task_id,
                        sub_id=sub_id,
                        command=cap,
                        description=f"Execute capability '{cap}' for objective.",
                        target_capability=cap,
                        metadata={"agent_hint": capability.agent_id},
                    )
                )
        return DecompositionResponse(task_id=payload.task_id, subtasks=subtasks)

