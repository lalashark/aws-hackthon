"""Adaptive routing stub leveraging metrics snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from shared.metrics import MetricsProvider
from shared.schemas import CapabilityDeclaration, MetricSnapshot, RouteDecision


@dataclass(slots=True)
class AdaptiveRouterAgent:
    """Selects the best worker for a subtask using simple heuristics."""

    metrics_provider: MetricsProvider

    async def decide_route(
        self,
        command: str,
        candidates: Iterable[CapabilityDeclaration],
        context: dict,
    ) -> RouteDecision:
        """Pick the candidate with the lowest composite score."""
        candidate_list = list(candidates)
        if not candidate_list:
            raise ValueError(f"No candidates available for command '{command}'.")

        scores: dict[str, float] = {}
        for declaration in candidate_list:
            metrics = await self._get_metrics(declaration.agent_id)
            score = self._score_candidate(declaration.agent_id, metrics)
            scores[declaration.agent_id] = score

        selected = min(scores, key=scores.get)
        reason = (
            f"Selected {selected} with lowest score {scores[selected]:.2f} "
            f"among {len(candidate_list)} candidates."
        )
        return RouteDecision(
            selected_agent=selected,
            reason=reason,
            considered=candidate_list,
            scores=scores,
        )

    async def _get_metrics(self, agent_id: str) -> MetricSnapshot | None:
        return await self.metrics_provider.get_metrics(agent_id)

    @staticmethod
    def _score_candidate(agent_id: str, metrics: MetricSnapshot | None) -> float:
        if metrics is None:
            return 1.0
        load_component = metrics.load
        failure_component = min(metrics.recent_failures, 5) * 0.1
        latency_component = (metrics.avg_latency_ms or 1000.0) / 5000.0
        return load_component + failure_component + latency_component

