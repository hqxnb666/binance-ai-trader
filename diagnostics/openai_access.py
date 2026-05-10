from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ai.model_router import (
    OpenAIModelRole,
    configured_models,
    resolve_max_output_tokens,
    resolve_openai_model,
)
from config.settings import Settings
from diagnostics.network import safe_details


class OpenAIDiagnosticSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^ok$")
    message: str


def check_openai_api(settings: Settings) -> dict[str, Any]:
    models = configured_models(settings)
    if settings.openai_api_key is None:
        return {
            "status": "MISSING_KEY",
            "latency_ms": None,
            "details": "OPENAI_API_KEY missing",
            "configured_models": models,
            "missing_configured_models": [],
        }
    start = time.perf_counter()
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
        visible_model_ids, model_list_error = _list_visible_models(client)
        if visible_model_ids is None:
            missing_models = []
        else:
            missing_models = sorted(set(models.values()) - visible_model_ids)
        response = client.responses.parse(
            model=resolve_openai_model(settings, OpenAIModelRole.DIAGNOSTIC),
            input=[
                {"role": "system", "content": "Return only the requested JSON."},
                {"role": "user", "content": "Return status ok with a short message."},
            ],
            text_format=OpenAIDiagnosticSchema,
            max_output_tokens=resolve_max_output_tokens(settings, OpenAIModelRole.DIAGNOSTIC),
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("structured output parse returned no object")
        return {
            "status": "OK",
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "details": "OpenAI structured output succeeded",
            "configured_models": models,
            "missing_configured_models": missing_models,
            "model_list_error": model_list_error,
        }
    except Exception as exc:  # noqa: BLE001 - diagnostics should not crash
        return {
            "status": "API_ERROR",
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "details": safe_details(str(exc)),
            "configured_models": models,
            "missing_configured_models": [],
        }


def _list_visible_models(client: Any) -> tuple[set[str] | None, str | None]:
    try:
        response = client.models.list()
        return {item.id for item in response.data}, None
    except Exception as exc:  # noqa: BLE001 - model listing is diagnostic-only
        return None, safe_details(str(exc))
