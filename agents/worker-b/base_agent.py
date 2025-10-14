"""Re-export BaseAgent for worker-b."""

from agents.common.base_agent import BaseAgent
from agents.common.config import AgentConfig

__all__ = ["BaseAgent", "AgentConfig"]

