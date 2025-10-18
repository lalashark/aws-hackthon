"""FastAPI route definitions for the master agent.

Endpoints are stubbed to showcase the expected request/response contracts.
Actual orchestration logic will be supplied by the dispatcher and controller layers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from shared.schemas import (
    CapabilityDeclaration,
    DecompositionResponse,
    ErrorCode,
    ErrorResponse,
    ResultPayload,
    RouteDecision,
    TaskObjective,
    WorkRequest,
)

router = APIRouter()


def get_dispatcher():
    """Dependency placeholder for injecting the dispatcher service."""
    raise NotImplementedError("Dispatcher dependency must be wired in main.py")


@router.post("/task", status_code=status.HTTP_202_ACCEPTED)
async def receive_task(payload: TaskObjective, dispatcher=Depends(get_dispatcher)):
    """Entry point for new tasks. Returns structured decomposition preview."""
    if dispatcher is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                code=ErrorCode.INTERNAL_ERROR, message="Dispatcher not configured."
            ).model_dump(),
        )
    result = await dispatcher.handle_task(payload)
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result


@router.post("/dispatch", response_model=RouteDecision)
async def dispatch_subtask(work: WorkRequest, dispatcher=Depends(get_dispatcher)):
    """Trigger routing and dispatch for a given subtask payload."""
    if dispatcher is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                code=ErrorCode.INTERNAL_ERROR, message="Dispatcher not configured."
            ).model_dump(),
        )
    return await dispatcher.dispatch(work)


@router.post("/result", status_code=status.HTTP_202_ACCEPTED)
async def receive_result(payload: ResultPayload, dispatcher=Depends(get_dispatcher)):
    """Worker callback endpoint. Stores results and updates metrics."""
    if dispatcher is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                code=ErrorCode.INTERNAL_ERROR, message="Dispatcher not configured."
            ).model_dump(),
        )
    await dispatcher.handle_result(payload)
    return {"status": "accepted"}
@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
async def register_agent(payload: CapabilityDeclaration, dispatcher=Depends(get_dispatcher)):
    """Worker self-registration endpoint."""
    if dispatcher is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                code=ErrorCode.INTERNAL_ERROR, message="Dispatcher not configured."
            ).model_dump(),
        )
    await dispatcher.register_agent(payload)
    return {"status": "accepted"}
