"""Dispatcher coordinating decomposition, routing, and result handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from shared.schemas import (
    CapabilityDeclaration,
    DecompositionResponse,
    DispatchLogEntry,
    ResultPayload,
    RouteDecision,
    SubTask,
    TaskObjective,
    WorkRequest,
)

from ..ag2_controller.controller import AG2Controller
from .memory import MemoryAdapter
from .routing import RoutingService


@dataclass(slots=True)
class Dispatcher:
    """Orchestrates the master workflow across decomposition and routing."""

    controller: AG2Controller
    routing: RoutingService
    memory: MemoryAdapter
    http_client: httpx.AsyncClient

    async def handle_task(self, payload: TaskObjective) -> DecompositionResponse:
        capabilities = await self.routing.list_capabilities()
        decomposition = await self.controller.decompose_task(payload, capabilities)
        await self.memory.store_subtasks(decomposition.subtasks)
        return decomposition

    async def register_agent(self, declaration: CapabilityDeclaration) -> None:
        await self.routing.register(declaration)
        if declaration.metrics:
            await self.memory.record(declaration.agent_id, declaration.metrics)

    async def dispatch(self, work: WorkRequest) -> RouteDecision:
        context = await self.memory.get_context(work.task_id) or {}
        candidates = await self.routing.candidates_for_command(work.command)
        decision = await self.controller.decide_route(work.command, candidates, context)

        await self._post_work(decision.selected_agent, work)

        subtask = await self.memory.get_subtask(work.task_id, work.sub_id)
        if subtask is None:
            subtask = self._fallback_subtask(work)
        await self.memory.record_route(decision, subtask)
        await self.memory.append_dispatch_log(
            DispatchLogEntry(
                task_id=work.task_id,
                sub_id=work.sub_id,
                agent_id=decision.selected_agent,
                route_reason=decision.reason,
                created_at=datetime.now(tz=timezone.utc),
            )
        )
        return decision

    async def handle_result(self, payload: ResultPayload) -> None:
        await self.memory.record_result(payload)

    async def _post_work(self, agent_id: str, work: WorkRequest) -> None:
        declaration = await self._find_agent(agent_id)
        target_url = str(declaration.url).rstrip("/")
        response = await self.http_client.post(
            f"{target_url}/work",
            json=work.model_dump(),
            timeout=30,
        )
        response.raise_for_status()

    async def _find_agent(self, agent_id: str):
        capabilities = await self.routing.list_capabilities()
        declaration = next((c for c in capabilities if c.agent_id == agent_id), None)
        if declaration is None:
            raise ValueError(f"Agent {agent_id} not registered")
        return declaration

    @staticmethod
    def _fallback_subtask(work: WorkRequest) -> SubTask:
        return SubTask(
            task_id=work.task_id,
            sub_id=work.sub_id,
            command=work.command,
            description=work.data.get("description", ""),
            target_capability=work.command,
            metadata={"fallback": True},
        )
