"""Shared BaseAgent implementation for worker services."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import httpx
import redis.asyncio as redis

from shared.schemas import (
    CapabilityDeclaration,
    ErrorCode,
    ErrorResponse,
    ExecutionStatus,
    MetricSnapshot,
    ResultPayload,
    WorkRequest,
)

from .config import AgentConfig

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BaseAgent:
    """Handles registration, heartbeats, task execution, and callbacks."""

    config: AgentConfig
    runtime_execute: Callable[[WorkRequest], Awaitable[dict[str, Any]]]
    redis_client: redis.Redis
    http_client: httpx.AsyncClient
    _heartbeat_task: asyncio.Task | None = field(init=False, default=None)
    _inflight: set[str] = field(init=False, default_factory=set)

    async def startup(self) -> None:
        """Register with the master and begin heartbeats."""
        await self._register_with_master()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Agent %s started with capabilities %s", self.config.agent_id, self.config.capabilities)

    async def shutdown(self) -> None:
        """Clean up tasks and close network clients."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
        await self.http_client.aclose()
        await self.redis_client.aclose()

    async def handle_work(self, request: WorkRequest) -> dict[str, Any]:
        """Execute a WorkRequest and asynchronously callback the master."""
        logger.info("Received work: task=%s sub=%s command=%s", request.task_id, request.sub_id, request.command)
        self._inflight.add(request.sub_id)
        try:
            output = await self.runtime_execute(request)
            payload = ResultPayload(
                task_id=request.task_id,
                sub_id=request.sub_id,
                agent_id=self.config.agent_id,
                status=ExecutionStatus.SUCCEEDED,
                output=output,
                ag2_trace=output.get("ag2_trace"),
                metrics=self._current_metrics(),
            )
        except Exception as exc:  # noqa: BLE001 - capture and report upstream
            logger.exception("Execution failed for task %s sub %s", request.task_id, request.sub_id)
            payload = ResultPayload(
                task_id=request.task_id,
                sub_id=request.sub_id,
                agent_id=self.config.agent_id,
                status=ExecutionStatus.RETRYABLE_FAILURE,
                output={},
                ag2_trace=None,
                error=ErrorResponse(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=str(exc),
                    details={"command": request.command},
                ),
                metrics=self._current_metrics(failed=True),
            )
        finally:
            self._inflight.discard(request.sub_id)
        asyncio.create_task(self._post_result(payload))
        return {"status": "accepted"}

    async def _register_with_master(self) -> None:
        public_url = self.config.public_url or f"http://{self.config.agent_id}:5000"
        declaration = CapabilityDeclaration(
            agent_id=self.config.agent_id,
            url=public_url,
            capabilities=self.config.capabilities,
            ag2_profile=self.config.ag2_profile,
            description=f"Automated worker {self.config.agent_id}",
            metrics=self._current_metrics(),
        )
        register_url = f"{self.config.master_url.rstrip('/')}/register"
        for attempt in range(1, 6):
            try:
                response = await self.http_client.post(
                    register_url,
                    json=declaration.model_dump(mode="json"),
                    timeout=15,
                )
                response.raise_for_status()
                logger.info("Registered with master on attempt %d", attempt)
                return
            except httpx.HTTPError as exc:  # noqa: PERF203 - explicit retry loop
                logger.warning(
                    "Registration attempt %d failed: %s", attempt, exc, exc_info=True
                )
                if attempt == 5:
                    break
                await asyncio.sleep(min(2 ** attempt, 10))
        raise RuntimeError("Exceeded registration retries")

    async def _heartbeat_loop(self) -> None:
        """Periodically update Redis heartbeat keys."""
        key = f"heartbeat:{self.config.agent_id}"
        while True:
            payload = json.dumps(
                {
                    "agent_id": self.config.agent_id,
                    "load": self._load_factor(),
                    "active_tasks": list(self._inflight),
                }
            )
            await self.redis_client.set(
                key,
                payload,
                ex=self.config.heartbeat_ttl,
            )
            await asyncio.sleep(self.config.heartbeat_interval)

    async def _post_result(self, payload: ResultPayload) -> None:
        callback = self.config.callback_url.rstrip("/")
        response = await self.http_client.post(
            callback,
            json=payload.model_dump(mode="json"),
            timeout=30,
        )
        response.raise_for_status()
        logger.info(
            "Result posted: task=%s sub=%s status=%s",
            payload.task_id,
            payload.sub_id,
            payload.status,
        )

    def _current_metrics(self, failed: bool = False) -> MetricSnapshot:
        return MetricSnapshot(
            load=self._load_factor(),
            avg_latency_ms=None,
            recent_failures=1 if failed else 0,
        )

    def _load_factor(self) -> float:
        return min(len(self._inflight) / 5.0, 1.0)
