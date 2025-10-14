"""Configuration dataclasses for worker agents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AgentConfig:
    """Runtime configuration for a worker agent instance."""

    agent_id: str
    capabilities: list[str]
    callback_url: str
    master_url: str
    ag2_profile: str
    prompt_path: Path
    redis_host: str
    redis_port: int
    public_url: str | None = None
    heartbeat_interval: int = 10
    heartbeat_ttl: int = 30
