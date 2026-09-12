"""Small, self-contained HTML review surface for an offline Director plan."""

from __future__ import annotations

from html import escape
from typing import Any


def _cell(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def render_report(plan: dict[str, Any]) -> str:
    fps = plan["source"]["fps"]
    rows = []
    for beat in plan["beats"]:
        selected = beat["selected_asset"]
        selected_text = "none" if selected is None else f"{selected['id']} ({selected['path']}; score {selected['score']})"
        alternates = "; ".join(f"{row['id']}: {row['score']} ({row['reason']})" for row in beat["candidates"] if selected is None or row["id"] != selected["id"])
        values = [beat["id"], f"{beat['start_frame'] / fps:.2f}–{beat['end_frame'] / fps:.2f} s [{beat['start_frame']},{beat['end_frame']})",
                  beat["transcript"], beat["action"], beat["broll_query"], selected_text, alternates,
                  beat["caption_text"], beat["rationale"]]
        rows.append("<tr>" + "".join(f"<td>{_cell(value)}</td>" for value in values) + "</tr>")
    caption_rows = "".join(
        f"<tr><td>{_cell(c['start_frame'])}–{_cell(c['end_frame'])}</td><td>{_cell(c['text'])}</td><td>{_cell(c.get('review_state', ''))}</td></tr>"
        for c in plan["captions"]
    )
    return ("<!doctype html><html lang='it'><meta charset='utf-8'><title>RAMBLA Director Review</title>"
            "<style>body{font:15px system-ui;margin:2rem;color:#20242a}table{border-collapse:collapse;width:100%}"
            "th,td{border:1px solid #bbb;padding:.45rem;vertical-align:top;text-align:left}tr:nth-child(even){background:#f5f5f5}"
            "td{overflow-wrap:anywhere}h1,h2{margin-top:2rem}</style>"
            f"<h1>RAMBLA Director — offline draft</h1><p>Client: {_cell(plan['client_id'])}; "
            f"source: {_cell(plan['source'].get('media',''))}; {fps} fps; {plan['source']['duration_frames']} frames; "
            f"beats: {len(plan['beats'])}; captions: {len(plan['captions'])}; hash: {_cell(plan['content_hash'])}</p>"
            "<p>ASR non revisionato. Nessuna modifica a DaVinci Resolve.</p>"
            "<h2>Editorial beats</h2><table><thead><tr>"
            "<th>ID</th><th>Range</th><th>Transcript</th><th>Action</th><th>Semantic query</th>"
            "<th>Selected asset</th><th>Alternates</th><th>Caption text</th><th>Rationale</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
            "<h2>All captions</h2><table><thead><tr><th>Frames</th><th>Text</th><th>Review</th></tr></thead><tbody>"
            + caption_rows + "</tbody></table></html>")
