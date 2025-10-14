"""Minimal AG2 runtime stub for worker agents."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any

from shared.schemas import WorkRequest


@dataclass(slots=True)
class AG2Runtime:
    """Stub runtime that mimics AG2 execution for PoC purposes."""

    profile: str
    prompt: str

    async def execute(self, request: WorkRequest) -> dict[str, Any]:
        """Pretend to run an AG2 workflow and return structured output."""
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return {
            "profile": self.profile,
            "prompt_excerpt": self.prompt[:120],
            "command": request.command,
            "input": request.data,
            "context": request.context,
            "ag2_trace": [
                {
                    "step": "analyse",
                    "description": f"Executed {request.command} via profile {self.profile}",
                }
            ],
        }

