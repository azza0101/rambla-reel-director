from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def has_selected_assets(selection: dict) -> bool:
    """A saved visual-beat choice is an explicit request to export media."""
    chunks=selection.get('chunks') or {}
    if not isinstance(chunks,dict): return False
    return any(isinstance(choice,dict) and not choice.get('no_broll') and
               any(isinstance(row,dict) and row.get('asset_id') for row in choice.get('selected_assets') or [])
               for choice in chunks.values())


class SelectionStore:
    def __init__(self, output_dir: Path, candidate_index: dict[str, dict], chunk_ranges: Iterable[str]) -> None:
        self.output_dir, self.candidate_index, self.chunk_ids = output_dir, candidate_index, set(chunk_ranges)
        self.path = output_dir / "selection-plan.json"

    def load(self) -> dict:
        if not self.path.is_file():
            return {"schema_version": "curation-selection-1", "resolve_calls": 0, "chunks": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def set_chunk_selection(self, chunk_id: str, asset_ids: list[str], *, no_broll: bool) -> dict:
        if chunk_id not in self.chunk_ids:
            raise ValueError("unknown chunk")
        if no_broll and asset_ids:
            raise ValueError("NO_BROLL is exclusive")
        unique = list(dict.fromkeys(asset_ids))
        for asset_id in unique:
            candidate = self.candidate_index.get(asset_id)
            if candidate is None or candidate.get("chunk_id") != chunk_id:
                raise ValueError("unknown or cross-chunk asset")
            if candidate.get("selectable") is False:
                raise ValueError("Source found / preview pending: a verified clip is required before selection")
        payload = self.load()
        payload["chunks"][chunk_id] = {"chunk_id": chunk_id, "no_broll": no_broll, "selected_assets": [] if no_broll else [
            {"asset_id": asset_id, "order": index, "track": f"V{index + 2}"} for index, asset_id in enumerate(unique)
        ]}
        self.output_dir.mkdir(parents=True, exist_ok=True)
        from .atomic_io import write_json
        write_json(self.path, payload)
        return payload["chunks"][chunk_id]
