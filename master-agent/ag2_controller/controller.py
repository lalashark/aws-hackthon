"""Facade combining the decomposer and adaptive router."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from shared.schemas import (
    CapabilityDeclaration,
    DecompositionResponse,
    RouteDecision,
    SubTask,
    TaskObjective,
)

from .adaptive_router import AdaptiveRouterAgent
from .decomposer import MasterDecomposer


@dataclass(slots=True)
class AG2Controller:
    """High-level orchestrator delegating to AG2-powered components."""

    decomposer: MasterDecomposer
    router: AdaptiveRouterAgent

    async def decompose_task(
        self, payload: TaskObjective, capabilities: Iterable[CapabilityDeclaration]
    ) -> DecompositionResponse:
        return await self.decomposer.decompose_task(payload, capabilities)

    async def decide_route(
        self,
        command: str,
        candidates: Iterable[CapabilityDeclaration],
        context: dict,
    ) -> RouteDecision:
        return await self.router.decide_route(command, candidates, context)

    async def plan_and_route(
        self,
        payload: TaskObjective,
        capabilities: Iterable[CapabilityDeclaration],
        context: dict,
    ) -> tuple[DecompositionResponse, list[tuple[SubTask, RouteDecision]]]:
        """Utility that decomposes and routes all subtasks in one call."""
        decomposition = await self.decompose_task(payload, capabilities)
        routing_results: list[tuple[SubTask, RouteDecision]] = []
        for subtask in decomposition.subtasks:
            candidates = [
                c for c in capabilities if subtask.target_capability in c.capabilities
            ]
            decision = await self.decide_route(subtask.command, candidates, context)
            routing_results.append((subtask, decision))
        return decomposition, routing_results

