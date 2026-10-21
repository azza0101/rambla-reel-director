"""Provider failover for the APP REEL API-first Director."""
from __future__ import annotations

from typing import Any, Callable, Iterable

from .gemini_interactions import GeminiAPIError, GeminiJSONReply
from .groq_api import GroqAPIError


class FailoverDirectorProvider:
    """Try cloud Director providers in order and stick to the first that succeeds."""

    provider_name = "auto"

    def __init__(
        self,
        providers: Iterable[Any],
        *,
        event_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.providers = tuple(providers)
        if not self.providers:
            raise ValueError("at least one Director provider is required")
        self._event_callback = event_callback
        self._active: Any | None = None
        self.model = " -> ".join(str(getattr(row, "model", "unknown")) for row in self.providers)
        self.thinking_level = str(getattr(self.providers[0], "thinking_level", "high"))

    def _emit(self, event: str, **data: Any) -> None:
        if self._event_callback is not None:
            self._event_callback(event, data)

    def generate_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        previous_interaction_id: str | None = None,
    ) -> GeminiJSONReply:
        if self._active is not None:
            return self._active.generate_json(
                prompt,
                schema,
                previous_interaction_id=previous_interaction_id,
            )

        failures: list[str] = []
        for index, provider in enumerate(self.providers):
            if index:
                previous = self.providers[index - 1]
                self._emit(
                    "provider_fallback",
                    from_provider=str(getattr(previous, "provider_name", "unknown")),
                    to_provider=str(getattr(provider, "provider_name", "unknown")),
                )
            try:
                reply = provider.generate_json(prompt, schema, previous_interaction_id=None)
            except (GeminiAPIError, GroqAPIError) as exc:
                failures.append(
                    f"{getattr(provider, 'provider_name', 'unknown')}: {' '.join(str(exc).split())[:300]}"
                )
                continue
            self._active = provider
            self.provider_name = str(getattr(provider, "provider_name", "unknown"))
            self.model = reply.model
            self.thinking_level = str(getattr(provider, "thinking_level", self.thinking_level))
            return reply

        raise RuntimeError("All Director providers failed: " + " | ".join(failures))
