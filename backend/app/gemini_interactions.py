"""Small dependency-free Gemini Interactions API client.

APP REEL V5 uses the cloud only for bounded reasoning tasks.  Keep the transport
thin and explicit so the product does not depend on a vendor SDK or local GPU.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import httpx


DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_INTERACTIONS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta2/interactions"


class GeminiAPIError(RuntimeError):
    """A sanitized Gemini transport/protocol failure."""


@dataclass(frozen=True, slots=True)
class GeminiJSONReply:
    data: dict[str, Any]
    interaction_id: str | None
    model: str


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
    """Synchronous structured-output client using the current Interactions REST API."""

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_GEMINI_MODEL,
        endpoint: str = DEFAULT_INTERACTIONS_ENDPOINT,
        timeout_seconds: float = 90.0,
        http_client: Any | None = None,
    ) -> None:
        clean_key = str(api_key or "").strip()
        if not clean_key:
            raise ValueError("GEMINI_API_KEY is required")
        self._api_key = clean_key
        self.model = str(model or DEFAULT_GEMINI_MODEL).strip()
        self.endpoint = str(endpoint).strip()
        self.timeout_seconds = float(timeout_seconds)
        self._http_client = http_client

    def generate_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        previous_interaction_id: str | None = None,
    ) -> GeminiJSONReply:
        body: dict[str, Any] = {
            "model": self.model,
            "input": prompt,
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

        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        if self._http_client is not None:
            response = self._http_client.post(
                self.endpoint,
                headers=headers,
                json=body,
                timeout=self.timeout_seconds,
            )
        else:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(self.endpoint, headers=headers, json=body)

        try:
            response.raise_for_status()
        except Exception as exc:
            status = getattr(response, "status_code", "?")
            detail = ""
            try:
                payload = response.json()
                error = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(error, dict):
                    detail = " ".join(str(error.get("message") or "").split())[:300]
            except Exception:
                detail = ""
            suffix = f": {detail}" if detail else ""
            raise GeminiAPIError(f"Gemini request failed ({status}){suffix}") from exc

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
        return GeminiJSONReply(data=data, interaction_id=interaction_id, model=self.model)
