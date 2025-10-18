"""Runtime module that bridges work requests to the LLM Gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import httpx

from shared.llm_gateway_client import LLMGatewayClient
from shared.schemas import WorkRequest


@dataclass(slots=True)
class AG2Runtime:
    """Executes tasks by delegating to the shared LLM gateway."""

    profile: str
    prompt: str
    llm_client: LLMGatewayClient

    async def execute(self, request: WorkRequest, http_client: httpx.AsyncClient) -> dict[str, Any]:
        """Send composed prompts to the LLM gateway and return structured output."""
        user_prompt = self._build_user_prompt(request)
        response = await self.llm_client.generate(
            http_client=http_client,
            system_prompt=self.prompt,
            user_prompt=user_prompt,
            metadata={"task_id": request.task_id, "sub_id": request.sub_id, "command": request.command},
        )
        return {
            "profile": self.profile,
            "provider": response.get("provider"),
            "text": response.get("output_text"),
            "raw_response": response.get("raw_response"),
            "metadata": response.get("metadata"),
            "input": request.data,
            "context": request.context,
        }

    @staticmethod
    def _build_user_prompt(request: WorkRequest) -> str:
        sections: Dict[str, Any] = {
            "command": request.command,
            "data": request.data,
            "context": request.context,
        }
        if request.priority:
            sections["priority"] = request.priority
        return (
            "You will receive structured task information in JSON format.\n"
            "Use the provided data to produce the best possible response.\n"
            f"{sections}"
        )
