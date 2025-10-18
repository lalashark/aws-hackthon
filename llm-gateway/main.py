"""FastAPI service exposing unified LLM access for workers."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

try:
    import boto3
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore[assignment]

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - optional dependency
    genai = None  # type: ignore[assignment]

logger = logging.getLogger("llm-gateway")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


class GenerateRequest(BaseModel):
    system_prompt: str = Field(..., description="High-level instruction for the LLM.")
    user_prompt: str = Field(..., description="User-provided content or question.")
    provider: str | None = Field(
        default=None,
        description="Override default provider (gemini, bedrock, mock).",
    )
    metadata: dict[str, Any] | None = None


class GenerateResponse(BaseModel):
    provider: str
    output_text: str
    raw_response: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


app = FastAPI(title="LLM Gateway", version="0.1.0")


def _detect_provider(request: GenerateRequest) -> str:
    return (request.provider or os.getenv("LLM_PROVIDER", "mock")).lower()


def _ensure_gemini() -> None:
    if genai is None:
        raise RuntimeError("google-generativeai is not installed.")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is required for Gemini provider.")
    genai.configure(api_key=api_key)


def _ensure_bedrock() -> Any:
    if boto3 is None:
        raise RuntimeError("boto3 is not installed.")
    region = os.getenv("AWS_REGION")
    if not region:
        raise RuntimeError("AWS_REGION environment variable is required for Bedrock provider.")
    return boto3.client("bedrock-runtime", region_name=region)


def _invoke_gemini(system_prompt: str, user_prompt: str) -> tuple[str, dict[str, Any]]:
    _ensure_gemini()
    model_name = os.getenv("GEMINI_MODEL", "gemini-pro")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content([system_prompt, user_prompt])
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini response did not contain text output.")
    return text, {"model": model_name}


def _invoke_bedrock(system_prompt: str, user_prompt: str) -> tuple[str, dict[str, Any]]:
    client = _ensure_bedrock()
    model_id = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")
    body = json.dumps({"inputText": user_prompt, "system": system_prompt})
    response = client.invoke_model(modelId=model_id, body=body)
    payload = json.loads(response["body"].read())  # type: ignore[index]
    text = payload.get("outputText")
    if not text:
        raise RuntimeError("Bedrock response missing 'outputText'.")
    return text, {"model": model_id}


def _invoke_mock(system_prompt: str, user_prompt: str) -> tuple[str, dict[str, Any]]:
    text = (
        "MOCK RESPONSE\n"
        f"System Prompt: {system_prompt[:120]}\n"
        f"User Prompt: {user_prompt[:240]}"
    )
    return text, {"model": "mock"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    provider = _detect_provider(request)
    logger.info("Handling /generate with provider=%s", provider)
    try:
        if provider == "gemini":
            text, meta = _invoke_gemini(request.system_prompt, request.user_prompt)
        elif provider == "bedrock":
            text, meta = _invoke_bedrock(request.system_prompt, request.user_prompt)
        elif provider == "mock":
            text, meta = _invoke_mock(request.system_prompt, request.user_prompt)
        else:
            raise ValueError(f"Unsupported provider '{provider}'.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM generation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": str(exc), "provider": provider},
        ) from exc

    return GenerateResponse(
        provider=provider,
        output_text=text,
        raw_response=meta,
        metadata=request.metadata,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
