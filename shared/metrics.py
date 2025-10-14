"""Metrics hook interfaces shared by master and worker processes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from .schemas import MetricSnapshot


class MetricsRecorder(ABC):
    """Abstract sink for worker-provided metrics."""

    @abstractmethod
    async def record(self, agent_id: str, snapshot: MetricSnapshot) -> None:
        """Persist or forward an updated metrics snapshot."""


class MetricsProvider(Protocol):
    """Protocol implemented by sources capable of supplying metrics on demand."""

    async def get_metrics(self, agent_id: str) -> MetricSnapshot | None:
        ...
