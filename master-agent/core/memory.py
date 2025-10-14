"""Redis-backed memory adapter prototype.

This module provides the minimal subset of functionality required by the
dispatcher and router to interact with the shared state described in the spec.
The implementation favors explicit key usage so we can later swap in other
backends via the same interface.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

import redis.asyncio as redis

from shared.metrics import MetricsRecorder, MetricsProvider
from shared.schemas import (
    CapabilityDeclaration,
    DispatchLogEntry,
    MetricSnapshot,
    ResultPayload,
    RouteDecision,
    SubTask,
)


class MemoryAdapter(Protocol):
    """Protocol for shared memory operations."""

    async def register_agent(self, declaration: CapabilityDeclaration) -> None: ...

    async def get_capabilities(self) -> list[CapabilityDeclaration]: ...

    async def store_subtasks(self, subtasks: list[SubTask]) -> None: ...

    async def record_route(self, decision: RouteDecision, subtask: SubTask) -> None: ...

    async def record_result(self, payload: ResultPayload) -> None: ...

    async def append_dispatch_log(self, entry: DispatchLogEntry) -> None: ...

    async def get_results(self, task_id: str) -> list[dict[str, Any]]: ...

    async def get_subtask(self, task_id: str, sub_id: str) -> SubTask | None: ...

    async def set_context(self, key: str, value: dict[str, Any]) -> None: ...

    async def get_context(self, key: str) -> dict[str, Any] | None: ...

    @asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator[redis.client.PubSub]: ...


@dataclass(slots=True)
class RedisMemoryAdapter(MemoryAdapter, MetricsRecorder, MetricsProvider):
    """Concrete Redis implementation of the shared memory adapter."""

    client: redis.Redis
    routing_key: str = "routing"
    results_prefix: str = "results"
    dispatch_log_prefix: str = "dispatch_log"
    metrics_prefix: str = "metrics"
    context_prefix: str = "global:context"

    async def register_agent(self, declaration: CapabilityDeclaration) -> None:
        await self.client.hset(
            self.routing_key,
            declaration.agent_id,
            declaration.model_dump_json(),
        )
        for capability in declaration.capabilities:
            await self.client.sadd(f"cap_index:{capability}", declaration.agent_id)
        if declaration.metrics:
            await self.record(declaration.agent_id, declaration.metrics)

    async def get_capabilities(self) -> list[CapabilityDeclaration]:
        raw = await self.client.hgetall(self.routing_key)
        return [
            CapabilityDeclaration.model_validate_json(value)
            for value in raw.values()
        ]

    async def store_subtasks(self, subtasks: list[SubTask]) -> None:
        if not subtasks:
            return
        pipeline = self.client.pipeline()
        for subtask in subtasks:
            pipeline.rpush(f"subtasks:{subtask.task_id}", subtask.model_dump_json())
            pipeline.set(
                f"subtask:{subtask.task_id}:{subtask.sub_id}",
                subtask.model_dump_json(),
            )
        await pipeline.execute()

    async def record_route(self, decision: RouteDecision, subtask: SubTask) -> None:
        key = f"route:{subtask.task_id}:{subtask.sub_id}"
        await self.client.set(key, decision.model_dump_json())

    async def record_result(self, payload: ResultPayload) -> None:
        key = f"{self.results_prefix}:{payload.task_id}"
        await self.client.rpush(key, payload.model_dump_json())
        if payload.metrics:
            await self.record(payload.agent_id, payload.metrics)

    async def append_dispatch_log(self, entry: DispatchLogEntry) -> None:
        key = f"{self.dispatch_log_prefix}:{entry.task_id}"
        await self.client.rpush(key, entry.model_dump_json())

    async def get_results(self, task_id: str) -> list[dict[str, Any]]:
        key = f"{self.results_prefix}:{task_id}"
        entries = await self.client.lrange(key, 0, -1)
        return [ResultPayload.model_validate_json(item).model_dump() for item in entries]

    async def get_subtask(self, task_id: str, sub_id: str) -> SubTask | None:
        raw = await self.client.get(f"subtask:{task_id}:{sub_id}")
        if raw is None:
            return None
        return SubTask.model_validate_json(raw)

    async def set_context(self, key: str, value: dict[str, Any]) -> None:
        await self.client.hset(self.context_prefix, key, json.dumps(value))

    async def get_context(self, key: str) -> dict[str, Any] | None:
        raw = await self.client.hget(self.context_prefix, key)
        if raw is None:
            return None
        return json.loads(raw)

    async def record(self, agent_id: str, snapshot: MetricSnapshot) -> None:
        payload = {
            key: json.dumps(value)
            for key, value in snapshot.model_dump(exclude_none=True).items()
        }
        await self.client.hset(f"{self.metrics_prefix}:{agent_id}", mapping=payload)

    async def get_metrics(self, agent_id: str) -> MetricSnapshot | None:
        raw = await self.client.hgetall(f"{self.metrics_prefix}:{agent_id}")
        if not raw:
            return None
        decoded: dict[str, Any] = {}
        for key, value in raw.items():
            field_name = key.decode() if isinstance(key, (bytes, bytearray)) else key
            decoded[field_name] = self._convert_metric_value(value)
        return MetricSnapshot.model_validate(decoded)

    @asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator[redis.client.PubSub]:
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        try:
            yield pubsub
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    @staticmethod
    def _convert_metric_value(value: Any) -> Any:
        text = value.decode() if isinstance(value, (bytes, bytearray)) else value
        if isinstance(text, str):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return text
