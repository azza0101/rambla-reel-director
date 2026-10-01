"""Asynchronous transcript-selection review through a tiny external web app."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import secrets
from typing import Any

import httpx

from .atomic_io import write_json
from .transcript_intents import load_phrase_intents, save_phrase_intents, transcript_document


REVIEW_SCHEMA = "rambla-transcript-review-1"
SUBMISSION_SCHEMA = "rambla-transcript-review-submission-1"
STATE_FILE = "external-review.json"
WORD_FIELDS = ("coverage_word_indices", "animation_word_indices", "highlighted_word_indices")


def build_review_payload(run: Path, project_id: str, project_label: str) -> dict[str, Any]:
    document = transcript_document(run)
    intents = load_phrase_intents(run)
    chunks = []
    for row in document["chunks"]:
        chunks.append({
            "id": str(row["id"]),
            "start": float(row["start"]),
            "end": float(row["end"]),
            "text": str(row["text"]),
            "words": [
                {"text": str(word["text"]), "start": float(word["start"]), "end": float(word["end"])}
                for word in row.get("words", [])
            ],
        })
    selections = {
        chunk_id: {field: list(row.get(field, [])) for field in WORD_FIELDS}
        for chunk_id, row in intents["phrases"].items()
    }
    return {
        "schema_version": REVIEW_SCHEMA,
        "project_id": str(project_id),
        "project_label": str(project_label or project_id),
        "transcript_signature": intents["transcript_signature"],
        "chunks": chunks,
        "intents": selections,
    }


def apply_review_submission(run: Path, submission: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(submission, dict) or submission.get("schema_version") != SUBMISSION_SCHEMA:
        raise ValueError("Unsupported review submission")
    current = load_phrase_intents(run)
    if submission.get("transcript_signature") != current["transcript_signature"]:
        raise ValueError("Transcript changed after the review link was created; publish a new review")
    raw_changes = submission.get("changes")
    if not isinstance(raw_changes, dict) or set(raw_changes) != set(current["phrases"]):
        raise ValueError("Review submission does not match every transcript phrase")
    changes: dict[str, dict[str, list[int]]] = {}
    for chunk_id, row in raw_changes.items():
        if not isinstance(row, dict):
            raise ValueError("Review selection must be an object")
        changes[chunk_id] = {field: row.get(field, []) for field in WORD_FIELDS}
    return save_phrase_intents(run, changes, current["transcript_signature"])


def load_review_state(run: Path) -> dict[str, Any]:
    path = run / STATE_FILE
    if not path.is_file():
        return {}
    try:
        import json
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_review_state(run: Path, value: dict[str, Any]) -> None:
    write_json(run / STATE_FILE, value)


@dataclass
class ReviewBridgeClient:
    webapp_url: str
    owner_secret: str

    @classmethod
    def from_environment(cls) -> "ReviewBridgeClient":
        return cls(
            os.environ.get("RAMBLA_REVIEW_WEBAPP_URL", "").strip(),
            os.environ.get("RAMBLA_REVIEW_OWNER_SECRET", "").strip(),
        )

    @property
    def configured(self) -> bool:
        return self.webapp_url.startswith("https://script.google.com/") and bool(self.owner_secret)

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Online review bridge is not configured")
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.post(self.webapp_url, json={**body, "owner_secret": self.owner_secret})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Review web app request failed: {exc}") from exc
        try:
            value = response.json()
        except ValueError as exc:
            raise RuntimeError("Review web app returned an invalid response") from exc
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise RuntimeError(str(value.get("error") if isinstance(value, dict) else "Review request failed"))
        return value

    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        review_id = secrets.token_urlsafe(12)
        reviewer_token = secrets.token_urlsafe(24)
        value = await self._post({
            "action": "publish",
            "review_id": review_id,
            "reviewer_token": reviewer_token,
            "payload": payload,
        })
        return {
            "review_id": review_id,
            "review_url": str(value.get("review_url") or f"{self.webapp_url}?review={review_id}&token={reviewer_token}"),
            "submitted_revision": 0,
        }

    async def pull(self, review_id: str) -> dict[str, Any]:
        return await self._post({"action": "pull", "review_id": str(review_id)})
