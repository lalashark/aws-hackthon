"""Pipeline orchestration for sequential worker execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from shared.schemas import (
    ErrorResponse,
    ExecutionStatus,
    PipelineResponse,
    PipelineStageResult,
    ResultPayload,
    TaskObjective,
    WorkRequest,
)

from .memory import MemoryAdapter
from .routing import RoutingService


@dataclass(slots=True)
class PipelineOrchestrator:
    """Executes a fixed-capability pipeline with optional finalizer."""

    routing: RoutingService
    memory: MemoryAdapter
    http_client: httpx.AsyncClient
    base_stages: list[str] = field(default_factory=lambda: ["analyze", "retrieve", "evaluate"])
    finalize_capability: str = "finalize"

    async def run(self, task: TaskObjective) -> PipelineResponse:
        capabilities = await self.routing.list_capabilities()
        stage_agents: list[tuple[str, str, str]] = []  # (capability, agent_id, url)

        for capability in self.base_stages:
            agent = self._select_agent(capabilities, capability)
            if not agent:
                raise RuntimeError(f"No registered agent supports capability '{capability}'")
            stage_agents.append((capability, agent.agent_id, str(agent.url)))

        finalizer = self._select_agent(capabilities, self.finalize_capability)
        if finalizer:
            stage_agents.append((self.finalize_capability, finalizer.agent_id, str(finalizer.url)))

        stage_results: list[PipelineStageResult] = []
        intermediate_context: dict[str, Any] = dict(task.context)
        previous_output: dict[str, Any] | None = None

        for idx, (capability, agent_id, url) in enumerate(stage_agents, start=1):
            sub_id = f"{task.task_id}-P{idx}"
            work = WorkRequest(
                task_id=task.task_id,
                sub_id=sub_id,
                command=capability,
                data={
                    "objective": task.objective,
                    "previous_output": previous_output,
                    "context": intermediate_context,
                },
                context=intermediate_context,
                priority="normal",
                reply_mode="sync",
            )

            response = await self.http_client.post(
                f"{url.rstrip('/')}/work",
                json=work.model_dump(mode="json"),
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()

            status_value = payload.get("status", ExecutionStatus.SUCCEEDED.value)
            status = ExecutionStatus(status_value)
            output = payload.get("output") or {}
            error_payload = payload.get("error")
            error_obj = None
            if error_payload:
                error_obj = ErrorResponse.model_validate(error_payload)

            stage_results.append(
                PipelineStageResult(
                    stage=capability,
                    agent_id=agent_id,
                    sub_id=sub_id,
                    status=status,
                    output=output,
                    error=error_obj,
                )
            )

            # Persist result for historical record keeping.
            result_payload = ResultPayload(
                task_id=task.task_id,
                sub_id=sub_id,
                agent_id=agent_id,
                status=status,
                output=output,
                ag2_trace=None,
                error=error_obj,
            )
            await self.memory.record_result(result_payload)

            if status != ExecutionStatus.SUCCEEDED:
                break

            intermediate_context[f"stage_{capability}"] = output
            previous_output = output

        final_output = stage_results[-1].output if stage_results else None
        return PipelineResponse(task_id=task.task_id, stages=stage_results, final_output=final_output)

    @staticmethod
    def _select_agent(capabilities, capability: str):
        for declaration in capabilities:
            if capability in declaration.capabilities:
                return declaration
        return None
