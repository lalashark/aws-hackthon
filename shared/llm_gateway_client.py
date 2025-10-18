"""Client utility for interacting with the LLM Gateway service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class LLMGatewayClient:
    """Lightweight HTTP client for the shared LLM gateway."""

    base_url: str
    default_provider: str = "mock"

    async def generate(
        self,
        http_client: httpx.AsyncClient,
        system_prompt: str,
        user_prompt: str,
        provider: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "provider": provider or self.default_provider,
            "metadata": metadata or {},
        }
        response = await http_client.post(
            f"{self.base_url.rstrip('/')}/generate",
            json=payload,
            timeout=float(os.getenv("LLM_GATEWAY_TIMEOUT", "60")),
        )
        response.raise_for_status()
        return response.json()


def build_llm_gateway_client() -> LLMGatewayClient:
    return LLMGatewayClient(
        base_url=os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:7000"),
        default_provider=os.getenv("LLM_PROVIDER", "mock"),
    )

