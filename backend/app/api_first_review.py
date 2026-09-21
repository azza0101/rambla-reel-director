"""Deterministic A/B review for V4 vs API-first V5 editorial plans."""
from __future__ import annotations

from collections import Counter
from html import escape
import json
from pathlib import Path
from typing import Any

from .editorial_import import visual_coverage_ratio


def _read_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read visual plan: {path}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("visual_beats"), list):
        raise ValueError(f"invalid visual plan: {path}")
    return value


def _beat_duration(beat: dict[str, Any]) -> float:
    return max(0.0, float(beat.get("end", 0.0)) - float(beat.get("start", 0.0)))


def _queries(plan: dict[str, Any], medium: str) -> list[str]:
    key = "video_queries" if medium == "video" else "image_queries"
    out: list[str] = []
    for beat in plan.get("visual_beats") or []:
        for shot in beat.get("shots") or []:
            out.extend(str(query) for query in shot.get(key) or [])
    return out


def plan_metrics(plan: dict[str, Any]) -> dict[str, Any]:
    beats = list(plan.get("visual_beats") or [])
    actions = Counter(str(beat.get("action") or "") for beat in beats)
    broll = [beat for beat in beats if beat.get("action") == "BROLL"]
    visual_durations = [_beat_duration(beat) for beat in beats]
    shot_count = sum(len(beat.get("shots") or []) for beat in broll)
    video_queries = _queries(plan, "video")
    image_queries = _queries(plan, "image")
    normalized_queries = [q.casefold().strip() for q in video_queries + image_queries if q.strip()]
    duplicate_queries = len(normalized_queries) - len(set(normalized_queries))
    return {
        "beats": len(beats),
        "broll_beats": actions["BROLL"],
        "continue_beats": actions["CONTINUE_PREVIOUS_VISUAL"],
        "talking_head_beats": actions["KEEP_TALKING_HEAD"],
        "visual_coverage_ratio": visual_coverage_ratio(plan),
        "mean_beat_seconds": round(sum(visual_durations) / len(visual_durations), 3) if visual_durations else 0.0,
        "shots": shot_count,
        "video_queries": len(video_queries),
        "image_queries": len(image_queries),
        "duplicate_queries": duplicate_queries,
    }


def _beat_at(beats: list[dict[str, Any]], t: float) -> dict[str, Any] | None:
    for beat in beats:
        if float(beat.get("start", 0.0)) <= t < float(beat.get("end", 0.0)):
            return beat
    return None


def timeline_alignment(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    left = list(baseline.get("visual_beats") or [])
    right = list(candidate.get("visual_beats") or [])
    boundaries = sorted({
        float(value)
        for beat in left + right
        for value in (beat.get("start", 0.0), beat.get("end", 0.0))
    })
    rows: list[dict[str, Any]] = []
    for start, end in zip(boundaries, boundaries[1:]):
        if end <= start:
            continue
        middle = start + (end - start) / 2.0
        b = _beat_at(left, middle)
        c = _beat_at(right, middle)
        rows.append({
            "start": start,
            "end": end,
            "baseline_beat_id": b.get("id") if b else None,
            "baseline_action": b.get("action") if b else None,
            "candidate_beat_id": c.get("id") if c else None,
            "candidate_action": c.get("action") if c else None,
            "same_action": bool(b and c and b.get("action") == c.get("action")),
        })
    return rows


def comparison_payload(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    if baseline.get("transcript_signature") != candidate.get("transcript_signature"):
        raise ValueError("baseline and candidate use different transcript signatures")
    alignment = timeline_alignment(baseline, candidate)
    duration = sum(row["end"] - row["start"] for row in alignment)
    same = sum(
        row["end"] - row["start"]
        for row in alignment
        if row["same_action"]
    )
    return {
        "schema_version": "rambla-api-first-ab-review-1",
        "transcript_signature": baseline.get("transcript_signature"),
        "baseline": plan_metrics(baseline),
        "candidate": plan_metrics(candidate),
        "action_agreement_ratio": round(same / duration, 6) if duration > 0 else 0.0,
        "timeline": alignment,
    }


def _shot_text(beat: dict[str, Any]) -> str:
    shots = []
    for shot in beat.get("shots") or []:
        video = ", ".join(str(q) for q in shot.get("video_queries") or [])
        image = ", ".join(str(q) for q in shot.get("image_queries") or [])
        shots.append(
            f"<div class='shot'><b>{escape(str(shot.get('description') or ''))}</b>"
            f"<small>VIDEO: {escape(video)}</small>"
            f"<small>IMAGE: {escape(image)}</small></div>"
        )
    return "".join(shots) or "<span class='muted'>—</span>"


def _beat_card(beat: dict[str, Any] | None) -> str:
    if not beat:
        return "<div class='beat empty'>No beat</div>"
    avoid = ", ".join(str(value) for value in beat.get("avoid") or [])
    return (
        "<div class='beat'>"
        f"<div class='head'><b>{escape(str(beat.get('action') or ''))}</b>"
        f"<span>{float(beat.get('start', 0)):.2f}–{float(beat.get('end', 0)):.2f}s</span></div>"
        f"<p class='speech'>{escape(str(beat.get('original_text') or ''))}</p>"
        f"<p><b>Meaning:</b> {escape(str(beat.get('core_meaning') or ''))}</p>"
        f"<p><b>Function:</b> {escape(str(beat.get('editorial_function') or ''))}</p>"
        f"{_shot_text(beat)}"
        + (f"<small class='avoid'>AVOID: {escape(avoid)}</small>" if avoid else "")
        + "</div>"
    )


def _rows_by_baseline(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> str:
    left = list(baseline.get("visual_beats") or [])
    right = list(candidate.get("visual_beats") or [])
    rows: list[str] = []
    used_right: set[str] = set()
    for beat in left:
        start, end = float(beat["start"]), float(beat["end"])
        overlaps = [
            other for other in right
            if float(other["start"]) < end and float(other["end"]) > start
        ]
        for other in overlaps:
            used_right.add(str(other.get("id")))
        right_html = "".join(_beat_card(other) for other in overlaps) or _beat_card(None)
        rows.append(
            "<section class='pair'>"
            f"<div>{_beat_card(beat)}</div>"
            f"<div>{right_html}</div>"
            "</section>"
        )
    extras = [beat for beat in right if str(beat.get("id")) not in used_right]
    if extras:
        rows.append(
            "<section class='pair'><div class='beat empty'>No baseline overlap</div><div>"
            + "".join(_beat_card(beat) for beat in extras)
            + "</div></section>"
        )
    return "".join(rows)


def render_review_html(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    comparison: dict[str, Any],
) -> str:
    left = comparison["baseline"]
    right = comparison["candidate"]
    metric_names = [
        ("visual_coverage_ratio", "Visual coverage"),
        ("beats", "Beats"),
        ("broll_beats", "B-roll beats"),
        ("talking_head_beats", "Talking head"),
        ("shots", "Shots"),
        ("video_queries", "Video queries"),
        ("image_queries", "Image queries"),
        ("duplicate_queries", "Duplicate queries"),
    ]
    metrics = "".join(
        f"<tr><th>{escape(label)}</th><td>{left[key]}</td><td>{right[key]}</td></tr>"
        for key, label in metric_names
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>APP REEL V5 A/B Director Review</title>
<style>
:root{{--bg:#0a0d12;--panel:#111821;--line:#2a3542;--text:#eef3f8;--muted:#94a3b8;--accent:#93c5fd}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,sans-serif}}
main{{max-width:1500px;margin:auto;padding:28px}}h1{{margin:0 0 6px}}.muted,small{{color:var(--muted)}}
.summary{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:22px 0}}
table{{border-collapse:collapse;width:100%;background:var(--panel);border:1px solid var(--line)}th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:18px 0;border-top:1px solid var(--line);padding-top:18px}}
.beat{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:10px}}.empty{{color:var(--muted)}}
.head{{display:flex;justify-content:space-between;gap:12px}}.head b{{color:var(--accent)}}.speech{{font-size:16px}}
.shot{{border-left:3px solid #4b6b8f;padding:7px 10px;margin:8px 0;background:#0d131b}}.shot small{{display:block;margin-top:4px}}
.avoid{{display:block;margin-top:8px;color:#fbbf24}}.cols{{display:grid;grid-template-columns:1fr 1fr;gap:18px;font-weight:700}}
@media(max-width:900px){{.pair,.summary,.cols{{grid-template-columns:1fr}}}}
</style></head>
<body><main>
<h1>APP REEL V5 — Director A/B</h1>
<p class="muted">Same transcript · V4 baseline vs API-first text-only candidate. No automatic winner is assigned: semantic quality is a human editorial decision.</p>
<div class="summary">
<table><thead><tr><th>Metric</th><th>V4 baseline</th><th>V5 candidate</th></tr></thead><tbody>{metrics}</tbody></table>
<div class="beat"><b>Action agreement</b><p style="font-size:28px;margin:8px 0">{comparison['action_agreement_ratio']:.1%}</p>
<small>This is descriptive only. Agreement is not a quality score.</small></div>
</div>
<div class="cols"><div>V4 BASELINE</div><div>V5 API-FIRST</div></div>
{_rows_by_baseline(baseline, candidate)}
</main></body></html>"""


def build_review(
    run_dir: Path,
    *,
    baseline_path: Path | None = None,
    candidate_path: Path | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    baseline_path = Path(baseline_path or (run_dir / "visual-plan.json"))
    candidate_path = Path(candidate_path or (run_dir / "api-first" / "visual-plan.json"))
    baseline = _read_plan(baseline_path)
    candidate = _read_plan(candidate_path)
    comparison = comparison_payload(baseline, candidate)
    root = run_dir / "api-first"
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "ab-review.json"
    html_path = root / "ab-review.html"
    json_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(
        render_review_html(baseline, candidate, comparison),
        encoding="utf-8",
    )
    return {
        "review_json": str(json_path),
        "review_html": str(html_path),
        **comparison,
    }
