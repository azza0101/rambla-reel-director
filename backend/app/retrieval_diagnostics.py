"""Structured retrieval states shared by workers and the curation UI."""

MESSAGES = {
    "available": "Candidates are ready for review.",
    "not_requested": "No new retrieval requested for this visual action.",
    "not_searched": "Not searched yet for this beat.",
    "provider_not_configured": "Provider not configured.",
    "provider_request_failed": "The provider request failed. See retrieval details.",
    "zero_provider_hits": "The provider returned no matches for these queries.",
    "no_hd_candidates": "Matches were found, but none had usable image dimensions.",
    "preview_download_failed": "Matches were found, but their previews could not be downloaded.",
    "ranker_unavailable": "Qwen visual ranking is unavailable. Relevance needs review.",
    "duplicate_only": "Matches repeat visuals already shown in other beats.",
    "visually_rejected": "Sampled content did not sufficiently match this shot.",
    "clip_localization_failed": "Sources were found, but no relevant playable window could be prepared.",
}


def _result(code, counts):
    return {"code": code, "message": MESSAGES[code], "counts": counts}


def empty_reason(c):
    if c.get("accepted"):
        code = "available"
    elif c.get("provider_configured") is False:
        code = "provider_not_configured"
    elif c.get("searched") is False:
        code = "not_searched"
    elif c.get("requests_failed") and not c.get("raw"):
        code = "provider_request_failed"
    elif not c.get("raw"):
        code = "zero_provider_hits"
    elif c.get("clip_failed"):
        code = "clip_localization_failed"
    elif not c.get("hd"):
        code = "no_hd_candidates"
    elif not c.get("preview") and c.get("preview_failed"):
        code = "preview_download_failed"
    elif c.get("ranker_unavailable"):
        code = "ranker_unavailable"
    elif c.get("duplicates") and not c.get("rejected"):
        code = "duplicate_only"
    else:
        code = "visually_rejected"
    return _result(code, c)


def image_diagnostic(row):
    if row.get("visual_action") in {"KEEP_TALKING_HEAD", "CONTINUE_PREVIOUS_VISUAL"}:
        return _result("not_requested", {})

    attempts = list(row.get("search_attempts") or [])
    candidates = list(row.get("candidates") or [])
    stored = dict(row.get("counts") or {})
    counts = {
        "attempts": len(attempts),
        "raw": int(stored.get("raw", row.get("raw_count", sum(int(a.get("hits", 0) or 0) for a in attempts)) or 0)),
        "hd": int(stored.get("hd", 0) or 0),
        "preview": int(stored.get("preview", 0) or 0),
        "preview_failed": int(stored.get("preview_failed", 0) or 0),
        "rejected": int(stored.get("rejected", len(row.get("rejected_candidates") or [])) or 0),
        "duplicates": int(stored.get("duplicates", row.get("duplicates_rejected", 0)) or 0),
        "requests_failed": int(stored.get("requests_failed", sum(bool(a.get("error")) for a in attempts)) or 0),
        "ranker_unavailable": bool(stored.get("ranker_unavailable", row.get("ranking_warning"))),
        "accepted": len(candidates),
        # No provider attempt means no search happened for this beat.  Never
        # translate missing artifacts into a real zero-hit provider response.
        "searched": bool(attempts or candidates),
    }
    return empty_reason(counts)


def _provider_matches(value, provider):
    text = str(value or "").casefold()
    provider = str(provider).casefold()
    return provider in text


def video_diagnostic(rows, provider, configured=True):
    attempts = [
        a
        for r in rows
        for a in r.get("search_attempts", [])
        if _provider_matches(a.get("provider"), provider)
    ]
    errors = [
        e
        for r in rows
        for e in r.get("errors", [])
        if isinstance(e, dict) and _provider_matches(e.get("provider"), provider)
    ]
    candidates = [
        c
        for r in rows
        for c in r.get("candidates", [])
        if _provider_matches(c.get("provider", c.get("source")), provider)
    ]
    counts = {
        "accepted": len(candidates),
        "provider_configured": bool(configured),
        "attempts": len(attempts),
        "raw": sum(int(a.get("hits", 0) or 0) for a in attempts),
        "requests_failed": sum(e.get("code") not in {"clip_preview_failed", "poster_failed"} for e in errors),
        "clip_failed": sum(e.get("code") == "clip_preview_failed" for e in errors),
        "ranker_unavailable": any(r.get("ranking_warning") for r in rows),
        "duplicates": sum(int(r.get("duplicates_rejected", 0) or 0) for r in rows),
        "rejected": sum(len(r.get("rejected_candidates", [])) for r in rows),
        "searched": bool(attempts or candidates or errors),
    }

    if counts["accepted"]:
        code = "available"
    elif not configured:
        code = "provider_not_configured"
    elif not counts["searched"]:
        code = "not_searched"
    elif counts["requests_failed"] and not counts["raw"]:
        code = "provider_request_failed"
    elif not counts["raw"]:
        code = "zero_provider_hits"
    elif counts["clip_failed"]:
        code = "clip_localization_failed"
    elif counts["ranker_unavailable"]:
        code = "ranker_unavailable"
    elif counts["duplicates"] and not counts["rejected"]:
        code = "duplicate_only"
    else:
        code = "visually_rejected"
    return _result(code, counts)
