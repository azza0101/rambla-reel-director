"""Tonight-only live Resolve slice over the authenticated in-app bridge."""

from __future__ import annotations

import importlib
import json
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts.hashing import canonical_sha256, edit_plan_approval_hash
from .contracts.plans import EditPlan


def is_source_timeline(name: str) -> bool:
    return name.replace(" ", "_").casefold() == "reel_master"


def allocate_generated_name(existing: set[str]) -> str:
    for suffix in range(1, 100):
        candidate = f"REEL_AI_v{suffix:02d}"
        if candidate not in existing:
            return candidate
    raise RuntimeError("no collision-safe generated timeline name is available")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class LiveResolveService:
    """Small duplicate-only service used by the localhost fast-track UI."""

    def __init__(
        self,
        *,
        upstream_root: Path | None = None,
        bridge_config: Path | None = None,
        data_root: Path | None = None,
    ) -> None:
        self.upstream_root = upstream_root or Path(os.environ["RAMBLA_RESOLVE_MCP_ROOT"])
        self.bridge_config = bridge_config or Path(os.environ["RAMBLA_RESOLVE_BRIDGE_CONFIG"])
        self.data_root = data_root or Path(os.environ.get("RAMBLA_LIVE_DATA_ROOT", "work/live-resolve-ui"))
        self._apply_lock = threading.Lock()

    def _connect(self) -> Any:
        root = str(self.upstream_root.resolve())
        if root not in sys.path:
            sys.path.insert(0, root)
        os.environ["DAVINCI_RESOLVE_BRIDGE"] = "1"
        os.environ["DAVINCI_RESOLVE_BRIDGE_CONFIG"] = str(self.bridge_config.resolve())
        bridge_client = importlib.import_module("src.utils.resolve_bridge_client")
        return bridge_client.connect()

    @staticmethod
    def _project(resolve: Any) -> Any:
        project = resolve.GetProjectManager().GetCurrentProject()
        if not project:
            raise RuntimeError("Resolve has no open project")
        return project

    @staticmethod
    def _timelines(project: Any) -> list[Any]:
        return [
            project.GetTimelineByIndex(index)
            for index in range(1, int(project.GetTimelineCount()) + 1)
        ]

    def _source(self, project: Any) -> Any:
        matches = [timeline for timeline in self._timelines(project) if is_source_timeline(timeline.GetName())]
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one REEL_MASTER source, found {len(matches)}")
        return matches[0]

    @staticmethod
    def _snapshot(project: Any, timeline: Any) -> dict[str, Any]:
        clips = timeline.GetItemListInTrack("video", 1) or []
        if not clips:
            raise RuntimeError("REEL_MASTER has no clip on V1")
        clip = clips[0]
        properties = clip.GetProperty()
        transform_keys = ("ZoomX", "ZoomY", "Pan", "Tilt", "AnchorPointX", "AnchorPointY")
        return {
            "project": project.GetName(),
            "timeline": timeline.GetName(),
            "timeline_id": timeline.GetUniqueId(),
            "fps": float(timeline.GetSetting("timelineFrameRate")),
            "video_tracks": int(timeline.GetTrackCount("video")),
            "clip": {
                "name": clip.GetName(),
                "id": clip.GetUniqueId(),
                "start": int(clip.GetStart()),
                "end": int(clip.GetEnd()),
                "duration": int(clip.GetDuration()),
                "transform": {key: properties.get(key) for key in transform_keys},
            },
        }

    def probe(self) -> dict[str, Any]:
        resolve = self._connect()
        project = self._project(resolve)
        source = self._source(project)
        return {
            "connected": True,
            "product": resolve.GetProductName(),
            "version": resolve.GetVersionString(),
            "active_timeline": project.GetCurrentTimeline().GetName(),
            "source": self._snapshot(project, source),
            "transform_read": True,
            "transform_write": hasattr((source.GetItemListInTrack("video", 1) or [None])[0], "SetProperty"),
        }

    def dry_run(self) -> dict[str, Any]:
        resolve = self._connect()
        project = self._project(resolve)
        source = self._source(project)
        before_names = [timeline.GetName() for timeline in self._timelines(project)]
        before = self._snapshot(project, source)
        now = _now()
        plan_id, run_id, decision_id = (str(uuid.uuid4()) for _ in range(3))
        source_hash = canonical_sha256(before)
        payload = {
            "schema_version": "1.0",
            "id": plan_id,
            "run_id": run_id,
            "version": 1,
            "status": "DRAFT",
            "source_timeline_snapshot_ref": f"runtime/{plan_id}.source.json",
            "source_timeline_hash": source_hash,
            "style_snapshot_ref": "runtime/tonight-fast-track-style.json",
            "policy_snapshot_ref": "runtime/duplicate-only-policy.json",
            "controls_snapshot": {
                "density": 0.1,
                "allowed_sources": ["CURRENT_TIMELINE"],
                "allowed_actions": ["PUNCH_IN"],
                "max_decisions": 1,
            },
            "provider_trace": [],
            "decisions": [{
                "id": decision_id,
                "action": "PUNCH_IN",
                "range": {"start_frame": before["clip"]["start"], "end_frame": before["clip"]["end"]},
                "frame": None,
                "intent": "Deterministic live Resolve punch-in proof",
                "reason": "Tonight fast-track safe mutation on duplicate only",
                "confidence": 1.0,
                "queries": [],
                "candidate_refs": [],
                "selected_asset_ref": None,
                "parameters": {"scale": 1.08, "anchor_x": 0.0, "anchor_y": 0.0, "easing": "CUT"},
                "review_state": "PROPOSED",
                "provenance": {"source_kind": "LOCAL_UI", "source_id": "tonight-fast-track"},
            }],
            "validation": {
                "valid": True,
                "plan_hash": "sha256:" + "0" * 64,
                "checked_at": now,
                "validator_version": "tonight-ft3-v1",
                "issues": [],
            },
            "approval": None,
            "apply_result_ref": None,
            "content_hash": "sha256:" + "0" * 64,
        }
        plan = EditPlan.model_validate(payload)
        digest = canonical_sha256(plan.model_dump(mode="json", exclude={"content_hash"}))
        plan = plan.model_copy(update={
            "content_hash": digest,
            "validation": plan.validation.model_copy(update={"plan_hash": digest}),
        })
        after = self._snapshot(project, source)
        after_names = [timeline.GetName() for timeline in self._timelines(project)]
        if before != after or before_names != after_names:
            raise RuntimeError("Dry Run detected an unexpected Resolve mutation")
        self.data_root.mkdir(parents=True, exist_ok=True)
        (self.data_root / f"{plan_id}.source.json").write_text(
            json.dumps(before, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (self.data_root / f"{plan_id}.plan.json").write_text(
            plan.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        return {"status": "DRAFT", "zero_mutation": True, "plan": plan.model_dump(mode="json")}

    def apply(self, plan_id: str) -> dict[str, Any]:
        canonical_id = str(uuid.UUID(plan_id))
        with self._apply_lock:
            plan_path = self.data_root / f"{canonical_id}.plan.json"
            snapshot_path = self.data_root / f"{canonical_id}.source.json"
            report_path = self.data_root / f"{canonical_id}.apply.json"
            if report_path.exists():
                raise RuntimeError("this plan already has an Apply report; refusing a retry")
            plan = EditPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
            expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
            if plan.status != "DRAFT" or len(plan.decisions) != 1 or plan.decisions[0].action != "PUNCH_IN":
                raise RuntimeError("Apply requires one valid DRAFT PUNCH_IN plan")
            resolve = self._connect()
            project = self._project(resolve)
            source = self._source(project)
            before = self._snapshot(project, source)
            if before != expected or canonical_sha256(before) != plan.source_timeline_hash:
                raise RuntimeError("REEL_MASTER changed after Dry Run; refusing Apply")
            names = {timeline.GetName() for timeline in self._timelines(project)}
            target_name = allocate_generated_name(names)
            approved_data = plan.model_dump(mode="json")
            approved_data.update({"status": "APPROVED", "approval": None})
            approved = EditPlan.model_validate(approved_data)
            approval_hash = edit_plan_approval_hash(approved)
            approved_data["approval"] = {
                "actor": "localhost-user",
                "approved_at": _now(),
                "approved_plan_hash": approval_hash,
            }
            approved = EditPlan.model_validate(approved_data)
            (self.data_root / f"{canonical_id}.approved.json").write_text(
                approved.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            duplicate = source.DuplicateTimeline(target_name)
            if not duplicate or duplicate.GetName() != target_name:
                raise RuntimeError("timeline duplication failed or returned an ambiguous target")
            target_clips = duplicate.GetItemListInTrack("video", 1) or []
            if not target_clips:
                raise RuntimeError("duplicate has no V1 clip; refusing transform")
            clip = target_clips[0]
            if (
                clip.GetName() != expected["clip"]["name"]
                or int(clip.GetStart()) != expected["clip"]["start"]
                or int(clip.GetEnd()) != expected["clip"]["end"]
            ):
                raise RuntimeError("duplicate clip identity/range is ambiguous; refusing transform")
            write_x = clip.SetProperty("ZoomX", 1.08)
            write_y = clip.SetProperty("ZoomY", 1.08)
            target_properties = clip.GetProperty()
            source_after = self._snapshot(project, source)
            zoom_ok = all(abs(float(target_properties[key]) - 1.08) < 1e-6 for key in ("ZoomX", "ZoomY"))
            center_ok = all(
                abs(float(target_properties.get(key, 0.0))) < 1e-6
                for key in ("Pan", "Tilt", "AnchorPointX", "AnchorPointY")
            )
            source_ok = source_after == before
            status = "SUCCEEDED" if write_x and write_y and zoom_ok and center_ok and source_ok else "AMBIGUOUS"
            report = {
                "status": status,
                "transport": "bridge-only",
                "plan_id": canonical_id,
                "approved_plan_hash": approval_hash,
                "source": {"name": source.GetName(), "unchanged": source_ok, "transform": source_after["clip"]["transform"]},
                "target": {
                    "name": target_name,
                    "clip": clip.GetName(),
                    "range": [int(clip.GetStart()), int(clip.GetEnd())],
                    "transform": {key: target_properties.get(key) for key in ("ZoomX", "ZoomY", "Pan", "Tilt", "AnchorPointX", "AnchorPointY")},
                    "zoom_verified": zoom_ok,
                    "center_verified": center_ok,
                },
                "finished_at": _now(),
            }
            report_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            if status != "SUCCEEDED":
                raise RuntimeError(f"Apply result is ambiguous; no retry performed: {report}")
            return report
