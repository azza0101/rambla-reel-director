"""Groq Director client for APP REEL V5.

Uses Groq's OpenAI-compatible Chat Completions endpoint with strict Structured
Outputs. Qwen 3.8 27B is the primary model; GPT-OSS 120B is the Groq-side
fallback. The client is intentionally dependency-light and uses httpx directly.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

import httpx

from .gemini_interactions import GeminiJSONReply, gemini_schema_subset


DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
DEFAULT_GROQ_FALLBACK_MODELS = ("openai/gpt-oss-120b",)
DEFAULT_GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


class GroqAPIError(RuntimeError):
    """Sanitized Groq transport/protocol failure."""


class GroqDirectorClient:
    provider_name = "groq"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_GROQ_MODEL,
        fallback_models: tuple[str, ...] | None = DEFAULT_GROQ_FALLBACK_MODELS,
        endpoint: str = DEFAULT_GROQ_ENDPOINT,
        timeout_seconds: float = 120.0,
        thinking_level: str = "high",
        max_retries_per_model: int = 1,
        retry_delays: tuple[float, ...] = (2.0,),
        sleeper: Callable[[float], None] = time.sleep,
        event_callback: Callable[[str, dict[str, Any]], None] | None = None,
        http_client: Any | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        clean_key = str(api_key or "").strip()
        if not clean_key:
            raise ValueError("GROQ_API_KEY is required")
        self.max_output_tokens = max_output_tokens
        if max_output_tokens is not None and (type(max_output_tokens) is not int or max_output_tokens<1):raise ValueError('max_output_tokens must be positive')
        self._api_key = clean_key
        self.model = str(model or DEFAULT_GROQ_MODEL).strip()
        self.fallback_models = tuple(
            item
            for item in (str(value or "").strip() for value in (fallback_models or ()))
            if item and item != self.model
        )
        self.endpoint = str(endpoint).strip()
        self.timeout_seconds = float(timeout_seconds)
        clean_thinking = str(thinking_level or "high").casefold().strip()
        if clean_thinking not in {"low", "medium", "high"}:
            raise ValueError("thinking_level must be low, medium or high")
        self.thinking_level = clean_thinking
        self.max_retries_per_model = max(0, int(max_retries_per_model))
        self.retry_delays = tuple(max(0.0, float(value)) for value in retry_delays)
        self._sleeper = sleeper
        self._event_callback = event_callback
        self._http_client = http_client
        self._successful_model: str | None = None
        self._first_prompt: str | None = None

    def _emit(self, event: str, **data: Any) -> None:
        data.setdefault("provider", "groq")
        if self._event_callback is not None:
            self._event_callback(event, data)

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

    @staticmethod
    def _max_completion_tokens(model: str) -> int:
        # Groq model limits: Qwen 3.8 27B = 16,384; GPT-OSS = 65,536.
        if str(model).startswith("openai/gpt-oss-"):
            return 65536
        if str(model) == "qwen/qwen3.8-27b":
            return 16384
        return 16384

    def _post(self, body: dict[str, Any], headers: dict[str, str]) -> Any:
        from .magic_usage import invoke_http
        return invoke_http('groq', body, lambda: self._post_unbudgeted(body, headers))

    def _post_unbudgeted(self, body: dict[str, Any], headers: dict[str, str]) -> Any:
        if self._http_client is not None:
            return self._http_client.post(
                self.endpoint,
                headers=headers,
                json=body,
                timeout=self.timeout_seconds,
            )
        timeout = httpx.Timeout(
            connect=min(20.0, self.timeout_seconds),
            read=self.timeout_seconds,
            write=min(30.0, self.timeout_seconds),
            pool=min(30.0, self.timeout_seconds),
        )
        with httpx.Client(timeout=timeout) as client:
            return client.post(self.endpoint, headers=headers, json=body)

    def generate_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        previous_interaction_id: str | None = None,
    ) -> GeminiJSONReply:
        requested_model = self.model

        # Groq Chat Completions is stateless here. If deterministic validation asks
        # for one repair pass, resend the original whole-transcript prompt plus the
        # compact repair instruction so editorial context is preserved.
        if previous_interaction_id and self._first_prompt:
            effective_prompt = (
                self._first_prompt
                + "\n\nREPAIR_REQUEST:\n"
                + prompt
            )
            model_chain = tuple(dict.fromkeys((self._successful_model or self.model, *self.fallback_models)))
        else:
            effective_prompt = prompt
            self._first_prompt = prompt
            model_chain = (self.model, *self.fallback_models)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
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
                    timeout_seconds=self.timeout_seconds,
                )

                body = {
                    "model": active_model,
                    "messages": [{"role": "user", "content": effective_prompt}],
                    "reasoning_effort": self.thinking_level,
                    "reasoning_format": "hidden",
                    "temperature": 1.0,
                    "max_completion_tokens": self.max_output_tokens or self._max_completion_tokens(active_model),
                    "stream": False,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "rambla_director",
                            "strict": True,
                            "schema": gemini_schema_subset(schema),
                        },
                    },
                }

                try:
                    response = self._post(body, headers)
                except httpx.RequestError as exc:
                    last_exception = exc
                    if retry_index < self.max_retries_per_model:
                        delay = self._retry_delay(None, retry_index)
                        self._emit(
                            "transport_error",
                            model=active_model,
                            error_type=type(exc).__name__,
                            delay_seconds=delay,
                            detail=" ".join(str(exc).split())[:240],
                        )
                        if delay:
                            self._sleeper(delay)
                        continue
                    if model_index < len(model_chain) - 1:
                        self._emit(
                            "model_exhausted",
                            model=active_model,
                            status="transport_error",
                            detail=type(exc).__name__,
                        )
                        break
                    raise GroqAPIError(
                        f"Groq transport failed ({type(exc).__name__})"
                    ) from exc

                last_response = response
                try:
                    response.raise_for_status()
                except Exception as exc:
                    last_exception = exc
                    status = getattr(response, "status_code", None)
                    detail = self._error_detail(response)
                    truncated = status == 400 and any(t in detail.lower() for t in ('max completion tokens reached', 'max_completion_tokens', 'output was truncated'))
                    if truncated and model_index < len(model_chain) - 1:
                        self._emit('output_truncated', model=active_model, status=status, detail='Structured JSON exceeded output budget; switching to configured fallback')
                        break
                    # Generation failures are recoverable; malformed requests and
                    # authentication failures are not. Never use failed_generation
                    # as a partial plan: ask a configured fallback for a full result.
                    generation_failed = status == 400 and any(
                        marker in detail.casefold() for marker in (
                            "failed to generate json",
                            "generated json does not match the expected schema",
                        )
                    )
                    if generation_failed and model_index < len(model_chain) - 1:
                        self._emit("model_exhausted", model=active_model, status=status, detail=detail)
                        break
                    retryable = generation_failed or (
                        isinstance(status, int) and status in RETRYABLE_HTTP_STATUSES
                    )
                    if status == 429 and model_index < len(model_chain) - 1:
                        self._emit(
                            "quota_exhausted",
                            model=active_model,
                            status=status,
                            detail=detail,
                            cooldown_seconds=self._retry_delay(response, retry_index),
                        )
                        break
                    if retryable and retry_index < self.max_retries_per_model:
                        delay = self._retry_delay(response, retry_index)
                        self._emit(
                            "retry",
                            model=active_model,
                            status=status,
                            delay_seconds=delay,
                            detail=detail,
                        )
                        if delay:
                            self._sleeper(delay)
                        continue
                    if retryable and model_index < len(model_chain) - 1:
                        self._emit(
                            "model_exhausted",
                            model=active_model,
                            status=status,
                            detail=detail,
                        )
                        break
                    suffix = f": {detail}" if detail else ""
                    raise GroqAPIError(f"Groq request failed ({status or '?'}){suffix}") from exc

                try:
                    payload = response.json()
                except Exception as exc:
                    raise GroqAPIError("Groq returned a non-JSON HTTP response") from exc
                if not isinstance(payload, dict):
                    raise GroqAPIError("Groq returned an invalid completion response")

                choices = payload.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise GroqAPIError("Groq response has no choices")
                first = choices[0] if isinstance(choices[0], dict) else {}
                if first.get('finish_reason') == 'length':
                    if model_index < len(model_chain) - 1:
                        self._emit('output_truncated', model=active_model, detail='Completion reached output limit')
                        break
                    raise GroqAPIError('Groq output truncated: completion token limit reached; no complete plan was saved')
                message = first.get("message") if isinstance(first, dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, str) or not content.strip():
                    raise GroqAPIError("Groq response has no final content")
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise GroqAPIError("Groq returned invalid structured JSON") from exc
                if not isinstance(data, dict):
                    raise GroqAPIError("Groq structured output must be a JSON object")

                usage_raw = payload.get("usage")
                usage: dict[str, int] = {}
                if isinstance(usage_raw, dict):
                    mapping = {
                        "prompt_tokens": "total_input_tokens",
                        "completion_tokens": "total_output_tokens",
                        "total_tokens": "total_tokens",
                    }
                    for source_key, target_key in mapping.items():
                        value = usage_raw.get(source_key)
                        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                            usage[target_key] = value

                self._successful_model = active_model
                completion_id = str(payload.get("id") or "").strip() or f"groq-{total_attempts}"
                self._emit(
                    "request_complete",
                    model=active_model,
                    transport_attempts=total_attempts,
                    usage=usage or None,
                )
                return GeminiJSONReply(
                    data=data,
                    interaction_id=completion_id,
                    model=active_model,
                    usage=usage or None,
                    requested_model=requested_model,
                    fallback_used=active_model != requested_model,
                    transport_attempts=total_attempts,
                )

        status = getattr(last_response, "status_code", "?")
        detail = self._error_detail(last_response) if last_response is not None else ""
        suffix = f": {detail}" if detail else ""
        raise GroqAPIError(f"Groq request failed ({status}){suffix}") from last_exception
