"""Small dependency-free Gemini Interactions API client.

APP REEL V5 uses the cloud only for bounded reasoning tasks.  Keep the transport
thin and explicit so the product does not depend on a vendor SDK or local GPU.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Callable

import httpx


DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_INTERACTIONS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_FALLBACK_MODELS = ("gemini-3.7-flash",)
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


class GeminiAPIError(RuntimeError):
    """A sanitized Gemini transport/protocol failure."""


@dataclass(frozen=True, slots=True)
class GeminiJSONReply:
    data: dict[str, Any]
    interaction_id: str | None
    model: str
    usage: dict[str, int] | None = None
    requested_model: str | None = None
    fallback_used: bool = False
    transport_attempts: int = 1


def _final_text(payload: dict[str, Any]) -> str:
    """Return the final contiguous model text from a REST Interaction resource."""
    steps = payload.get("steps")
    if not isinstance(steps, list):
        raise GeminiAPIError("Gemini response has no steps")
    for step in reversed(steps):
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        content = step.get("content")
        if not isinstance(content, list):
            continue
        texts = [
            str(block.get("text") or "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        text = "".join(texts).strip()
        if text:
            return text
    raise GeminiAPIError("Gemini response has no final text output")


def _json_object(text: str) -> dict[str, Any]:
    def unique_object(pairs):
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise GeminiAPIError(f"Gemini returned duplicate JSON field: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise GeminiAPIError("Gemini returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise GeminiAPIError("Gemini structured output must be a JSON object")
    return value


_GEMINI_SCHEMA_KEYS = {
    "$id", "$defs", "$ref", "$anchor", "type", "format", "title", "description",
    "enum", "items", "prefixItems", "minItems", "maxItems", "minimum", "maximum",
    "anyOf", "oneOf", "properties", "additionalProperties", "required", "propertyOrdering",
}


def gemini_schema_subset(value: Any) -> Any:
    """Strip JSON-Schema keywords unsupported by Gemini structured outputs.

    APP REEL still applies its stricter canonical validator after generation.
    """
    if isinstance(value, list):
        return [gemini_schema_subset(item) for item in value]
    if not isinstance(value, dict):
        return value
    output: dict[str, Any] = {}
    for key, item in value.items():
        if key not in _GEMINI_SCHEMA_KEYS:
            continue
        if key == "properties" and isinstance(item, dict):
            output[key] = {name: gemini_schema_subset(schema) for name, schema in item.items()}
        elif key == "$defs" and isinstance(item, dict):
            output[key] = {name: gemini_schema_subset(schema) for name, schema in item.items()}
        else:
            output[key] = gemini_schema_subset(item)
    return output


class GeminiInteractionsClient:
    """Synchronous structured-output client using the current Interactions REST API.

    Transient overloads are retried on the requested model first.  Only after those
    retries fail do we use a configured stable Flash fallback.  Stateful repair calls
    stay on the model that produced the original interaction.
    """

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_GEMINI_MODEL,
        endpoint: str = DEFAULT_INTERACTIONS_ENDPOINT,
        timeout_seconds: float = 90.0,
        thinking_level: str = "high",
        fallback_models: tuple[str, ...] | None = DEFAULT_FALLBACK_MODELS,
        max_retries_per_model: int = 2,
        retry_delays: tuple[float, ...] = (1.5, 4.0),
        sleeper: Callable[[float], None] = time.sleep,
        event_callback: Callable[[str, dict[str, Any]], None] | None = None,
        http_client: Any | None = None,
    ) -> None:
        clean_key = str(api_key or "").strip()
        if not clean_key:
            raise ValueError("GEMINI_API_KEY is required")
        self._api_key = clean_key
        self.model = str(model or DEFAULT_GEMINI_MODEL).strip()
        self.endpoint = str(endpoint).strip()
        self.timeout_seconds = float(timeout_seconds)
        clean_thinking = str(thinking_level or "high").casefold().strip()
        if clean_thinking not in {"low", "medium", "high"}:
            raise ValueError("thinking_level must be low, medium or high")
        self.thinking_level = clean_thinking
        self.fallback_models = tuple(
            item for item in (str(value or "").strip() for value in (fallback_models or ()))
            if item and item != self.model
        )
        if max_retries_per_model < 0:
            raise ValueError("max_retries_per_model must be >= 0")
        self.max_retries_per_model = int(max_retries_per_model)
        self.retry_delays = tuple(max(0.0, float(value)) for value in retry_delays)
        self._sleeper = sleeper
        self._event_callback = event_callback
        self._http_client = http_client
        self._sticky_model: str | None = None

    def _emit(self, event: str, **data: Any) -> None:
        callback = self._event_callback
        if callback is not None:
            callback(event, data)

    @staticmethod
    def _error_detail(response: Any) -> str:
        try:
            payload = response.json()
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                return " ".join(str(error.get("message") or "").split())[:300]
        except Exception:
            pass
        return ""

    def _retry_delay(self, response: Any, retry_index: int) -> float:
        headers = getattr(response, "headers", None)
        if headers is not None:
            try:
                value = headers.get("retry-after")
                if value is not None:
                    return max(0.0, min(float(value), 30.0))
            except (TypeError, ValueError):
                pass
        if not self.retry_delays:
            return 0.0
        return self.retry_delays[min(retry_index, len(self.retry_delays) - 1)]

    def _post(self, body: dict[str, Any], headers: dict[str, str]) -> Any:
        if self._http_client is not None:
            return self._http_client.post(
                self.endpoint,
                headers=headers,
                json=body,
                timeout=self.timeout_seconds,
            )
        with httpx.Client(timeout=self.timeout_seconds) as client:
            return client.post(self.endpoint, headers=headers, json=body)

    def generate_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        previous_interaction_id: str | None = None,
    ) -> GeminiJSONReply:
        requested_model = self.model
        if previous_interaction_id and self._sticky_model:
            model_chain = (self._sticky_model,)
        else:
            model_chain = (self.model, *self.fallback_models)

        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        total_attempts = 0
        last_response: Any | None = None
        last_exception: Exception | None = None

        for model_index, active_model in enumerate(model_chain):
            if model_index > 0:
                self._emit(
                    "fallback",
                    from_model=model_chain[model_index - 1],
                    to_model=active_model,
                )
            for retry_index in range(self.max_retries_per_model + 1):
                total_attempts += 1
                self._emit(
                    "request_start",
                    model=active_model,
                    attempt=retry_index + 1,
                    attempts_for_model=self.max_retries_per_model + 1,
                    transport_attempt=total_attempts,
                )
                body: dict[str, Any] = {
                    "model": active_model,
                    "input": prompt,
                    "generation_config": {"thinking_level": self.thinking_level},
                    "response_format": [
                        {
                            "type": "text",
                            "mime_type": "application/json",
                            "schema": gemini_schema_subset(schema),
                        }
                    ],
                }
                if previous_interaction_id:
                    body["previous_interaction_id"] = previous_interaction_id

                response = self._post(body, headers)
                last_response = response
                try:
                    response.raise_for_status()
                except Exception as exc:
                    last_exception = exc
                    status = getattr(response, "status_code", None)
                    retryable = isinstance(status, int) and status in RETRYABLE_HTTP_STATUSES
                    if retryable and retry_index < self.max_retries_per_model:
                        delay = self._retry_delay(response, retry_index)
                        self._emit(
                            "retry",
                            model=active_model,
                            status=status,
                            delay_seconds=delay,
                            detail=self._error_detail(response),
                        )
                        if delay:
                            self._sleeper(delay)
                        continue
                    if retryable and model_index < len(model_chain) - 1:
                        self._emit(
                            "model_exhausted",
                            model=active_model,
                            status=status,
                            detail=self._error_detail(response),
                        )
                        break
                    detail = self._error_detail(response)
                    suffix = f": {detail}" if detail else ""
                    raise GeminiAPIError(f"Gemini request failed ({status or '?'}){suffix}") from exc

                try:
                    payload = response.json()
                except Exception as exc:
                    raise GeminiAPIError("Gemini returned a non-JSON HTTP response") from exc
                if not isinstance(payload, dict):
                    raise GeminiAPIError("Gemini returned an invalid interaction resource")
                if payload.get("status") not in {None, "completed"}:
                    raise GeminiAPIError(f"Gemini interaction status is {payload.get('status')}")

                data = _json_object(_final_text(payload))
                interaction_id = str(payload.get("id") or "").strip() or None
                raw_usage = payload.get("usage")
                usage: dict[str, int] = {}
                if isinstance(raw_usage, dict):
                    for key in (
                        "total_input_tokens",
                        "total_output_tokens",
                        "total_thought_tokens",
                        "total_cached_tokens",
                        "total_tool_use_tokens",
                        "total_tokens",
                    ):
                        value = raw_usage.get(key)
                        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                            usage[key] = value
                self._sticky_model = active_model
                self._emit(
                    "request_complete",
                    model=active_model,
                    transport_attempts=total_attempts,
                    usage=usage or None,
                )
                return GeminiJSONReply(
                    data=data,
                    interaction_id=interaction_id,
                    model=active_model,
                    usage=usage or None,
                    requested_model=requested_model,
                    fallback_used=active_model != requested_model,
                    transport_attempts=total_attempts,
                )

        status = getattr(last_response, "status_code", "?")
        detail = self._error_detail(last_response) if last_response is not None else ""
        suffix = f": {detail}" if detail else ""
        raise GeminiAPIError(f"Gemini request failed ({status}){suffix}") from last_exception
