"""Routing helpers built on top of the memory adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from shared.schemas import CapabilityDeclaration

from .memory import MemoryAdapter


@dataclass(slots=True)
class RoutingService:
    """Retrieves capability data for routing decisions."""

    memory: MemoryAdapter

    async def candidates_for_command(self, command: str) -> list[CapabilityDeclaration]:
        declarations = await self.memory.get_capabilities()
        return [decl for decl in declarations if command in decl.capabilities]

    async def list_capabilities(self) -> list[CapabilityDeclaration]:
        return await self.memory.get_capabilities()

    async def register(self, declaration: CapabilityDeclaration) -> None:
        await self.memory.register_agent(declaration)

