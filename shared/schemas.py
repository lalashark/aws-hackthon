"""Shared data contracts for the AG2 multi-agent system.

These models are intentionally colocated to guarantee the master and workers
agree on payload formats for HTTP requests, Redis records, and AG2 reasoning
artifacts. They double as documentation for the API surface.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, conlist, constr


class ErrorCode(str, Enum):
    """Enumerates well-known error categories for HTTP responses."""

    VALIDATION_ERROR = "validation_error"
    ROUTING_ERROR = "routing_error"
    WORKER_UNAVAILABLE = "worker_unavailable"
    DISPATCH_FAILED = "dispatch_failed"
    INTERNAL_ERROR = "internal_error"


class ErrorResponse(BaseModel):
    """Consistent error envelope returned by master and workers."""

    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None


class MetricSnapshot(BaseModel):
    """Operational metrics for an agent, used by the router."""

    load: float = Field(ge=0.0, le=1.0, description="Normalized load factor 0-1.")
    avg_latency_ms: float | None = Field(
        default=None, ge=0.0, description="Rolling average latency in milliseconds."
    )
    recent_failures: int = Field(ge=0, description="Count of failures in the last window.")
    last_heartbeat: datetime | None = Field(
        default=None, description="Timestamp of the most recent heartbeat."
    )


class CapabilityDeclaration(BaseModel):
    """Registration payload submitted by a worker to the master."""

    agent_id: constr(strip_whitespace=True, min_length=3)
    url: HttpUrl
    capabilities: conlist(str, min_length=1)
    ag2_profile: constr(strip_whitespace=True, min_length=3)
    description: str | None = None
    metrics: MetricSnapshot | None = None


class TaskObjective(BaseModel):
    """Task received by the master from an external client."""

    task_id: constr(strip_whitespace=True, min_length=2)
    objective: str = Field(min_length=1, description="Natural language objective.")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Optional shared context hints."
    )


class SubTask(BaseModel):
    """Represents a decomposed unit of work to be assigned to a worker."""

    task_id: str
    sub_id: str
    command: str
    description: str
    target_capability: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecompositionResponse(BaseModel):
    """Structured subtasks produced by the AG2 decomposition stage."""

    task_id: str
    subtasks: list[SubTask]


class RouteDecision(BaseModel):
    """Router output describing the selected agent and reasoning."""

    selected_agent: str = Field(description="Agent ID selected for dispatch.")
    reason: str = Field(description="Natural language justification.")
    considered: list[CapabilityDeclaration] = Field(
        default_factory=list, description="Snapshot of candidates considered."
    )
    scores: dict[str, float] = Field(
        default_factory=dict, description="Optional heuristic scores per candidate."
    )


class WorkRequest(BaseModel):
    """Payload sent from master to worker via /work."""

    task_id: str
    sub_id: str
    command: str
    data: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    priority: Literal["low", "normal", "high"] = "normal"


class ExecutionStatus(str, Enum):
    """Worker execution outcome for a subtask."""

    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    FATAL_FAILURE = "fatal_failure"


class ResultPayload(BaseModel):
    """Result submitted by workers after processing a subtask."""

    task_id: str
    sub_id: str
    agent_id: str
    status: ExecutionStatus
    output: dict[str, Any]
    ag2_trace: list[dict[str, Any]] | None = Field(
        default=None, description="Structured trace exported by AG2 runtime."
    )
    error: ErrorResponse | None = None
    metrics: MetricSnapshot | None = Field(
        default=None, description="Latest metrics reported alongside the result."
    )


class HeartbeatPayload(BaseModel):
    """Heartbeat data pushed by workers to Redis."""

    agent_id: str
    load: float
    timestamp: datetime
    active_tasks: list[str] = Field(default_factory=list)


class DispatchLogEntry(BaseModel):
    """Compact record persisted for observability."""

    task_id: str
    sub_id: str
    agent_id: str
    route_reason: str
    status: ExecutionStatus | None = None
    error_code: ErrorCode | None = None
    created_at: datetime
