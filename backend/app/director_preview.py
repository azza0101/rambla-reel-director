"""Small, self-contained HTML review surface for an offline Director plan."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _cell(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _safe_public_href(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    sensitive = {"token", "sig", "signature", "key", "api_key", "apikey", "auth", "authorization", "policy", "expires", "expire"}
    query = urlencode(
        [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True) if key.lower() not in sensitive]
    )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def _local_preview_uri(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("\\", "/")
    if raw.startswith("http://") or raw.startswith("https://"):
        return None
    if re.match(r"^[A-Za-z]:/", raw):
        return "file:///" + raw
    try:
        return Path(raw).expanduser().resolve().as_uri()
    except (OSError, ValueError):
        return None


def _creator_text(candidate: dict[str, Any]) -> str:
    creator = candidate.get("creator")
    if isinstance(creator, dict):
        name = creator.get("name")
        if name:
            return str(name)
    if isinstance(creator, str):
        return creator
    return ""


def _candidate_card(candidate: dict[str, Any], *, selected_id: str | None) -> str:
    candidate_id = str(candidate.get("id", "unknown"))
    selected = candidate_id == selected_id
    preview = _local_preview_uri(candidate.get("preview_path") or candidate.get("path"))
    source_page = _safe_public_href(candidate.get("source_page"))
    source = candidate.get("source") or candidate.get("providers", {}).get("retrieval") or "unknown"
    creator = _creator_text(candidate)
    rights = candidate.get("rights_state", "")
    score = candidate.get("score")
    embedding = candidate.get("embedding_score")
    reranker = candidate.get("reranker_score")
    query = candidate.get("query", "")
    reason = candidate.get("reason", "")

    image = (
        f"<img loading='lazy' src='{_cell(preview)}' alt='{_cell(candidate_id)} preview'>"
        if preview
        else "<div class='no-preview'>no preview</div>"
    )
    source_link = (
        f"<a href='{_cell(source_page)}' target='_blank' rel='noopener noreferrer'>source</a>"
        if source_page
        else "source unavailable"
    )
    badge = "<span class='badge selected'>SELECTED</span>" if selected else "<span class='badge'>alternate</span>"
    return (
        f"<article class='candidate{' picked' if selected else ''}'>"
        f"{image}<div class='candidate-body'>{badge}<strong>{_cell(candidate_id)}</strong>"
        f"<div>{_cell(source)} · {source_link}</div>"
        f"<div>score <b>{_cell(score)}</b> · embedding {_cell(embedding)} · reranker {_cell(reranker)}</div>"
        f"<div>creator {_cell(creator or 'unknown')} · rights {_cell(rights or 'unknown')}</div>"
        f"<div class='muted'>query: {_cell(query)}</div>"
        f"<div class='muted'>{_cell(reason)}</div>"
        "</div></article>"
    )


def _proposal_card(proposal: dict[str, Any], *, label: str, selected_id: str | None) -> str:
    proposal_id = str(proposal.get("id", "unknown"))
    selected = proposal_id == selected_id
    preview = _local_preview_uri(proposal.get("preview_path") or proposal.get("path"))
    source_page = _safe_public_href(proposal.get("source_page"))
    source = proposal.get("source", "unknown")
    qwen = proposal.get("qwen_score", proposal.get("embedding_score"))
    semantic = proposal.get("semantic_score", proposal.get("score", qwen))
    evidence_route = proposal.get("evidence_route_score")
    crop = proposal.get("crop_score")
    taste = proposal.get("taste_score")
    final = proposal.get("final_score", proposal.get("score"))
    rights = proposal.get("rights_state", "unknown")
    creator = _creator_text(proposal) or "unknown"
    start = proposal.get("source_start_seconds")
    end = proposal.get("source_end_seconds")
    source_range = ""
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        source_range = f"<div>source time <b>{start:.2f}–{end:.2f}s</b></div>"
    image = (
        f"<img loading='lazy' src='{_cell(preview)}' alt='{_cell(proposal_id)} preview'>"
        if preview
        else "<div class='no-preview'>no preview</div>"
    )
    source_link = (
        f"<a href='{_cell(source_page)}' target='_blank' rel='noopener noreferrer'>source</a>"
        if source_page
        else "source unavailable"
    )
    selected_badge = "<span class='badge selected'>SELECTED</span>" if selected else ""
    tracking = " · tracking/reframe" if proposal.get("needs_tracking") else ""
    route_text = f" · route {_cell(evidence_route)}" if evidence_route is not None else ""
    taste_text = f" · taste {_cell(taste)}" if taste is not None else ""
    return (
        f"<article class='candidate{' picked' if selected else ''}'>"
        f"{image}<div class='candidate-body'><span class='badge proposal'>{_cell(label)}</span>{selected_badge}"
        f"<strong>{_cell(proposal_id)}</strong><div>{_cell(source)} · {source_link}</div>"
        f"<div>Qwen {_cell(qwen)} · semantic {_cell(semantic)}{route_text} · crop {_cell(crop)}{taste_text} · final <b>{_cell(final)}</b>{_cell(tracking)}</div>"
        f"{source_range}<div>creator {_cell(creator)} · rights {_cell(rights)}</div>"
        "</div></article>"
    )


def render_report(plan: dict[str, Any]) -> str:
    fps = plan["source"]["fps"]
    rows = []
    review_sections = []
    beats_by_id: dict[str, dict[str, Any]] = {}
    for beat in plan["beats"]:
        beats_by_id[str(beat["id"])] = beat
        selected = beat["selected_asset"]
        selected_text = "none" if selected is None else f"{selected['id']} ({selected['path']}; score {selected['score']})"
        alternates = "; ".join(
            f"{row['id']}: {row['score']} ({row['reason']})"
            for row in beat["candidates"]
            if selected is None or row["id"] != selected["id"]
        )
        providers = beat.get("providers", {})
        provider_text = "; ".join(f"{role}: {name or 'none'}" for role, name in providers.items())
        scores = "; ".join(
            f"{row['id']}: embedding={row.get('embedding_score')}, reranker={row.get('reranker_score')}, final={row['score']}"
            for row in beat["candidates"]
        )
        values = [
            beat["id"],
            f"{beat['start_frame'] / fps:.2f}–{beat['end_frame'] / fps:.2f} s [{beat['start_frame']},{beat['end_frame']})",
            beat["transcript"],
            beat["action"],
            beat["broll_query"],
            selected_text,
            alternates,
            scores,
            provider_text,
            beat.get("review_state", ""),
            beat["caption_text"],
            beat["rationale"],
        ]
        rows.append("<tr>" + "".join(f"<td>{_cell(value)}</td>" for value in values) + "</tr>")

        remote_candidates = [
            candidate
            for candidate in beat.get("candidates", [])
            if candidate.get("source") or candidate.get("preview_path") or candidate.get("source_page")
        ]
        if remote_candidates:
            selected_id = str(selected.get("id")) if isinstance(selected, dict) and selected.get("id") else None
            cards = "".join(_candidate_card(candidate, selected_id=selected_id) for candidate in remote_candidates)
            review_sections.append(
                f"<section class='beat-review'><h3>{_cell(beat['id'])} · {_cell(beat['action'])} · {_cell(beat.get('review_state',''))}</h3>"
                f"<p><b>{_cell(beat['start_frame']/fps)}–{_cell(beat['end_frame']/fps)}s</b> · {_cell(beat['transcript'])}</p>"
                f"<p>Search: <code>{_cell(beat['broll_query'])}</code></p><div class='candidate-grid'>{cards}</div></section>"
            )

    coverage_sections = []
    for slot in plan.get("coverage_slots", []):
        selected_id = str(slot.get("selected_proposal_id") or "") or None
        cards = []
        for key, label in (("proposal_A", "Proposal A"), ("proposal_B", "Proposal B"), ("proposal_C", "Proposal C")):
            proposal = slot.get(key)
            if isinstance(proposal, dict):
                cards.append(_proposal_card(proposal, label=label, selected_id=selected_id))
        if not cards:
            continue
        beat = beats_by_id.get(str(slot.get("beat_id")), {})
        transcript = beat.get("transcript", "")
        queries = " · ".join(str(value) for value in slot.get("queries", []) if value)
        start_seconds = float(slot.get("start_seconds", slot.get("start_frame", 0) / fps))
        end_seconds = float(slot.get("end_seconds", slot.get("end_frame", 0) / fps))
        route = slot.get("visual_route")
        taste_version = slot.get("taste_profile_version")
        route_reason = slot.get("route_reason", "")
        route_meta = ""
        if route:
            taste_label = f" · Taste v{_cell(taste_version)}" if taste_version is not None else ""
            reason_label = f" · reason: {_cell(route_reason)}" if route_reason else ""
            route_meta = f"<p><b>Route: {_cell(route)}</b>{taste_label}{reason_label}</p>"
        coverage_sections.append(
            f"<section class='beat-review coverage-review'><h3>{_cell(slot.get('id','coverage'))} · {_cell(slot.get('review_state',''))}</h3>"
            f"<p><b>{start_seconds:.2f}–{end_seconds:.2f}s</b> · {_cell(transcript)}</p>"
            f"{route_meta}"
            f"<p>Intent: {_cell(slot.get('visual_intent',''))}</p>"
            f"<p>Search: <code>{_cell(queries)}</code></p>"
            f"<div class='candidate-grid'>{''.join(cards)}</div></section>"
        )

    caption_rows = "".join(
        f"<tr><td>{_cell(c['start_frame'])}–{_cell(c['end_frame'])}</td><td>{_cell(c['text'])}</td><td>{_cell(c.get('review_state', ''))}</td></tr>"
        for c in plan["captions"]
    )
    style = (
        "body{font:15px system-ui;margin:2rem;color:#20242a;background:#fafafa}"
        "table{border-collapse:collapse;width:100%;background:white}th,td{border:1px solid #ccc;padding:.45rem;vertical-align:top;text-align:left}"
        "tr:nth-child(even){background:#f5f5f5}td{overflow-wrap:anywhere}h1,h2{margin-top:2rem}"
        ".candidate-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}.candidate{background:#fff;border:1px solid #ccc;border-radius:12px;overflow:hidden}"
        ".candidate.picked{border:2px solid #222}.candidate img,.no-preview{width:100%;height:160px;object-fit:cover;background:#eee}.no-preview{display:grid;place-items:center}"
        ".candidate-body{padding:10px;display:grid;gap:5px}.badge{display:inline-block;width:max-content;font-size:11px;padding:2px 6px;border-radius:999px;background:#eee}.badge.selected{background:#222;color:#fff}.badge.proposal{font-weight:700}"
        ".muted{font-size:12px;color:#666}.beat-review{margin:18px 0;padding:16px;background:#f0f1f3;border-radius:14px}.coverage-review{background:#e9eef5}code{white-space:normal}"
    )
    return (
        "<!doctype html><html lang='it'><meta charset='utf-8'><title>RAMBLA Director Review</title>"
        f"<style>{style}</style>"
        f"<h1>RAMBLA Director — offline draft</h1><p>Client: {_cell(plan['client_id'])}; "
        f"source: {_cell(plan['source'].get('media',''))}; {fps} fps; {plan['source']['duration_frames']} frames; "
        f"beats: {len(plan['beats'])}; coverage slots: {len(plan.get('coverage_slots', []))}; captions: {len(plan['captions'])}; hash: {_cell(plan['content_hash'])}</p>"
        "<p>ASR non revisionato. Nessuna modifica a DaVinci Resolve.</p>"
        "<h2>Editorial beats</h2><table><thead><tr>"
        "<th>ID</th><th>Range</th><th>Transcript</th><th>Action</th><th>Semantic query</th>"
        "<th>Selected asset</th><th>Alternates</th><th>Candidate scores</th><th>Providers</th><th>Review</th><th>Caption text</th><th>Rationale</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        + ("<h2>Coverage review</h2>" + "".join(coverage_sections) if coverage_sections else "")
        + ("<h2>Candidate review</h2>" + "".join(review_sections) if review_sections else "")
        + "<h2>All captions</h2><table><thead><tr><th>Frames</th><th>Text</th><th>Review</th></tr></thead><tbody>"
        + caption_rows
        + "</tbody></table></html>"
    )
