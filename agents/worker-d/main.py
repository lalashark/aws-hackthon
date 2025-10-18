"""FastAPI entrypoint for worker-d (finalizer)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import redis.asyncio as redis
from fastapi import FastAPI

from shared.llm_gateway_client import build_llm_gateway_client
from shared.schemas import WorkRequest

from .ag2_runtime import AG2Runtime
from .base_agent import AgentConfig, BaseAgent

app = FastAPI(title="Worker D", version="0.1.0")


def build_agent() -> BaseAgent:
    prompt_path = Path(os.getenv("PROMPT_PATH", "/app/config/prompt_finalize.txt"))
    prompt_text = prompt_path.read_text(encoding="utf-8")
    capabilities = [
        cap.strip()
        for cap in json.loads(os.getenv("CAPABILITIES", "[\"finalize\"]"))
        if cap.strip()
    ]
    public_url = os.getenv("PUBLIC_URL")
    config = AgentConfig(
        agent_id=os.getenv("AGENT_ID", "worker-d"),
        capabilities=capabilities,
        callback_url=os.getenv("CALLBACK_URL", "http://master-agent:8000/result"),
        master_url=os.getenv("MASTER_URL", "http://master-agent:8000"),
        ag2_profile=os.getenv("AG2_PROFILE", "worker-finalize"),
        prompt_path=prompt_path,
        redis_host=os.getenv("REDIS_HOST", "redis"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        public_url=public_url,
    )
    runtime = AG2Runtime(
        profile=config.ag2_profile,
        prompt=prompt_text,
        llm_client=build_llm_gateway_client(),
    )
    redis_client = redis.Redis(host=config.redis_host, port=config.redis_port, decode_responses=False)
    http_client = httpx.AsyncClient()
    return BaseAgent(config=config, runtime=runtime, redis_client=redis_client, http_client=http_client)


@app.on_event("startup")
async def startup() -> None:
    app.state.agent = build_agent()
    await app.state.agent.startup()


@app.on_event("shutdown")
async def shutdown() -> None:
    if agent := getattr(app.state, "agent", None):
        await agent.shutdown()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/work")
async def work_endpoint(request: WorkRequest):
    agent: BaseAgent = app.state.agent
    return await agent.handle_work(request)

