"""Entry point wiring the FastAPI application for the master agent."""

from __future__ import annotations

import os

import httpx
import redis.asyncio as redis
from fastapi import FastAPI

from .ag2_controller.adaptive_router import AdaptiveRouterAgent
from .ag2_controller.controller import AG2Controller
from .ag2_controller.decomposer import MasterDecomposer
from .api import routes
from .core.dispatcher import Dispatcher
from .core.memory import RedisMemoryAdapter
from .core.pipeline import PipelineOrchestrator
from .core.routing import RoutingService


def build_app() -> FastAPI:
    """Create and configure the FastAPI instance."""
    app = FastAPI(title="AG2 Master Agent", version="0.1.0")

    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=False,
    )
    memory = RedisMemoryAdapter(redis_client)
    routing_service = RoutingService(memory)
    controller = AG2Controller(
        decomposer=MasterDecomposer(),
        router=AdaptiveRouterAgent(metrics_provider=memory),
    )
    http_client = httpx.AsyncClient()
    mode = os.getenv("MASTER_MODE", "routing").lower()
    pipeline = None
    if mode == "pipeline":
        pipeline = PipelineOrchestrator(routing=routing_service, memory=memory, http_client=http_client)
    dispatcher = Dispatcher(
        controller=controller,
        routing=routing_service,
        memory=memory,
        http_client=http_client,
        mode=mode,
        pipeline=pipeline,
    )

    app.include_router(routes.router)
    app.dependency_overrides[routes.get_dispatcher] = lambda: dispatcher

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await http_client.aclose()
        await redis_client.aclose()

    return app


app = build_app()
