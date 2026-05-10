from __future__ import annotations

import time
from typing import Any, TypeVar

from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Session

from ai.model_router import OpenAIModelRole
from journal.openai_usage_store import record_openai_usage

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class StructuredOpenAIClient:
    def __init__(
        self,
        *,
        api_key: SecretStr | str | None,
        model: str,
        role: OpenAIModelRole | str | None = None,
        usage_ledger_enabled: bool = True,
    ):
        self.api_key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        self.model = model
        self.role = str(role) if role else None
        self.usage_ledger_enabled = usage_ledger_enabled
        self.last_model: str | None = None
        self.last_role: str | None = self.role
        self.last_max_output_tokens: int | None = None

    def parse(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        schema: type[SchemaT],
        role: OpenAIModelRole | str | None = None,
        model_override: str | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        usage_session: Session | None = None,
        operation_name: str | None = None,
    ) -> SchemaT:
        if not self.api_key:
            msg = "OPENAI_API_KEY is not configured"
            raise RuntimeError(msg)
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise RuntimeError("openai package is not installed") from exc

        actual_model = (model_override or self.model).strip()
        if not actual_model:
            msg = "OpenAI model is not configured"
            raise RuntimeError(msg)
        self.last_model = actual_model
        self.last_role = str(role or self.role) if role or self.role else None
        self.last_max_output_tokens = max_output_tokens
        usage_role = self.last_role or "unknown"
        usage_operation = operation_name or usage_role
        start = time.perf_counter()

        request_kwargs: dict[str, Any] = {
            "model": actual_model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": schema_json_payload(user_payload)},
            ],
            "text_format": schema,
        }
        if max_output_tokens is not None:
            request_kwargs["max_output_tokens"] = max_output_tokens
        if reasoning_effort is not None:
            request_kwargs["reasoning"] = {"effort": reasoning_effort}
        try:
            client = OpenAI(api_key=self.api_key)
            response = client.responses.parse(**request_kwargs)
            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                msg = "OpenAI response did not include parsed structured output"
                raise ValueError(msg)
            self._record_usage(
                usage_session=usage_session,
                role=usage_role,
                model=actual_model,
                operation_name=usage_operation,
                status="SUCCESS",
                latency_ms=int((time.perf_counter() - start) * 1000),
                response=response,
                input_payload=user_payload,
                output_payload=parsed.model_dump(mode="json"),
            )
            return parsed
        except Exception as exc:
            self._record_usage(
                usage_session=usage_session,
                role=usage_role,
                model=actual_model,
                operation_name=usage_operation,
                status="FAILED",
                latency_ms=int((time.perf_counter() - start) * 1000),
                input_payload=user_payload,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise

    def _record_usage(
        self,
        *,
        usage_session: Session | None,
        role: str,
        model: str,
        operation_name: str,
        status: str,
        latency_ms: int,
        input_payload: dict[str, Any],
        response: Any | None = None,
        output_payload: dict[str, Any] | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if usage_session is None or not self.usage_ledger_enabled:
            return
        usage = getattr(response, "usage", None) if response is not None else None
        input_tokens = _usage_int(usage, "input_tokens", "prompt_tokens")
        output_tokens = _usage_int(usage, "output_tokens", "completion_tokens")
        total_tokens = _usage_int(usage, "total_tokens")
        cached_tokens = _cached_tokens(usage)
        request_id = (
            getattr(response, "id", None)
            or getattr(response, "request_id", None)
            or getattr(response, "_request_id", None)
            if response is not None
            else None
        )
        record_openai_usage(
            usage_session,
            role=role,
            model=model,
            operation_name=operation_name,
            request_id=request_id,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            error_type=error_type,
            error_message=error_message,
            input_payload=input_payload,
            output_payload=output_payload,
        )


def schema_json_payload(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _usage_int(usage: Any, *names: str) -> int | None:
    if usage is None:
        return None
    for name in names:
        value = getattr(usage, name, None)
        if value is not None:
            return int(value)
        if isinstance(usage, dict) and usage.get(name) is not None:
            return int(usage[name])
    return None


def _cached_tokens(usage: Any) -> int | None:
    if usage is None:
        return None
    details = getattr(usage, "input_tokens_details", None)
    if details is None and isinstance(usage, dict):
        details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details")
    if details is None:
        details = getattr(usage, "prompt_tokens_details", None)
    if details is None:
        return None
    value = getattr(details, "cached_tokens", None)
    if value is None and isinstance(details, dict):
        value = details.get("cached_tokens")
    return int(value) if value is not None else None
